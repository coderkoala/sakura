#!/usr/bin/env bash
# tools/build-engine.sh [TARGET] [OUT_DIR] — build the `sakura` engine from source, the same way every time: Open Interpreter
# at patches/ENGINE_BASE, plus patches/engine.patch. Prints the asset it made.
#   tools/build-engine.sh                               this machine's own target (links against its glibc)
#   tools/build-engine.sh x86_64-unknown-linux-musl     static: runs on any x86_64 Linux, however old its glibc
#   tools/build-engine.sh aarch64-unknown-linux-musl    static ARM64 (a Pi 5, an ARM laptop or server); cross-compiled with
#                                                       `cross` or `cargo zigbuild` when this machine isn't ARM
#   --check                                             fetch the source and prove the patch applies; compile nothing
# The asset is sakura-linux-ARCH[-musl].tar.gz with its .sha256, the names install.sh looks for. Needs git and cargo (rustup
# picks the toolchain the source pins), and about 20 GB of RAM at link time: SAKURA_BUILD_JOBS (default 3) trades time for memory.
set -euo pipefail
case "${1:-}" in -h|--help) sed -n '2,/^[^#]/{/^#/s/^# \{0,1\}//p}' "$0"; exit 0 ;; esac
here="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
check=0; args=()
for a in "$@"; do case "$a" in --check) check=1 ;; *) args+=("$a") ;; esac; done
host="$(rustc -vV 2>/dev/null | sed -n 's/^host: //p' || true)"
target="${args[0]:-${host:-x86_64-unknown-linux-gnu}}"
out="${args[1]:-$here/dist}"
case "$target" in
    x86_64-unknown-linux-gnu) asset=sakura-linux-x86_64 ;;
    x86_64-unknown-linux-musl) asset=sakura-linux-x86_64-musl ;;
    aarch64-unknown-linux-gnu) asset=sakura-linux-aarch64-gnu ;;
    aarch64-unknown-linux-musl) asset=sakura-linux-aarch64 ;;   # ARM ships static only, so it takes the plain name
    *) echo "build-engine: no asset name for $target (x86_64 or aarch64, -gnu or -musl)" >&2; exit 2 ;;
esac
base="$(cat "$here/patches/ENGINE_BASE")"
src="${SAKURA_ENGINE_SRC:-${XDG_CACHE_HOME:-$HOME/.cache}/sakura/engine-src}"
if [ ! -d "$src/.git" ]; then
    mkdir -p "$(dirname "$src")"
    git clone --quiet --filter=blob:none --no-checkout "${SAKURA_ENGINE_REPO:-https://github.com/OpenInterpreter/open-interpreter}" "$src"
fi
git -C "$src" fetch --quiet origin "$base" 2>/dev/null || true
git -C "$src" checkout --quiet --force "$base"
git -C "$src" clean -qfd -e codex-rs/target
git -C "$src" apply --check "$here/patches/engine.patch" || { echo "build-engine: patches/engine.patch doesn't apply to $base; rebase it (patches/README.md)" >&2; exit 1; }
if [ "$check" = 1 ]; then echo "the patch applies to $base; nothing compiled"; exit 0; fi
git -C "$src" apply "$here/patches/engine.patch"
cd "$src/codex-rs"
jobs="${SAKURA_BUILD_JOBS:-3}"
build=(cargo build)
if [ "$target" != "$host" ]; then
    rustup target add "$target" >/dev/null 2>&1 || true
    case "$target:$(uname -m)" in
        aarch64-*:aarch64|x86_64-*:x86_64) ;;   # same CPU, another libc: cargo can do it with the musl target installed
        *) if command -v cross >/dev/null 2>&1; then build=(cross build)
           elif cargo zigbuild --help >/dev/null 2>&1; then build=(cargo zigbuild)
           else echo "build-engine: building $target on $(uname -m) needs \`cross\` (cargo install cross, with docker) or \`cargo zigbuild\`" >&2; exit 1; fi ;;
    esac
fi
"${build[@]}" --release -j "$jobs" -p codex-cli --bin codex --target "$target"
bin="target/$target/release/codex"
[ -x "$bin" ] || { echo "build-engine: the build finished without $bin" >&2; exit 1; }
mkdir -p "$out"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
cp "$bin" "$tmp/sakura"
strip "$tmp/sakura" 2>/dev/null || true
tar -czf "$out/$asset.tar.gz" -C "$tmp" sakura
(cd "$out" && sha256sum "$asset.tar.gz" > "$asset.tar.gz.sha256")
echo "$out/$asset.tar.gz"
