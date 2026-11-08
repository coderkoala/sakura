#!/usr/bin/env bash
# evals/in-box.sh EVAL [ARGS...] — run an eval inside a throwaway container, so nothing it installs or leaves behind lands
# on this machine. The model stays on the host: the container shares the host's network and talks to the driver at
# 127.0.0.1:8091 (or Ollama at 11434). The repo is mounted read-only and copied inside; the engine binary comes along.
#   evals/in-box.sh fix.py --only import-typo
#   evals/in-box.sh wall.py
# Needs docker. sudo inside the box is the box's sudo. Results print as usual; nothing is written back to the repo.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
bin="$(command -v sakura || true)"
[ -n "$bin" ] || { echo "in-box: the sakura binary isn't on PATH" >&2; exit 1; }
command -v docker >/dev/null || { echo "in-box: docker is needed" >&2; exit 1; }
image="${SAKURA_BOX_IMAGE:-ubuntu:24.04}"
tty=""; [ -t 0 ] && tty="-it"
exec docker run --rm $tty --network host \
    -v "$here":/src:ro -v "$(readlink -f "$bin")":/usr/local/bin/sakura:ro \
    -e SAKURA_ROUTER_URL="${SAKURA_ROUTER_URL:-http://127.0.0.1:8091/v1}" -e SAKURA_NO_AUTOPULL=1 -e SAKURA_WORKER_NO_WALL="${SAKURA_WORKER_NO_WALL:-0}" \
    "$image" bash -lc '
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/dev/null && apt-get install -y -qq --no-install-recommends python3 git curl ca-certificates sudo ripgrep bubblewrap >/dev/null
useradd -m -s /bin/bash box && echo "box ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/box
cp -r /src /home/box/sakura && chown -R box /home/box/sakura
su - box -c "cd ~/sakura && SAKURA_NO_BINARY=1 ./install.sh >/dev/null 2>&1 || true; export PATH=\$HOME/.local/bin:\$PATH; cd ~/sakura && python3 evals/'"$1"' '"${*:2}"'"
'
