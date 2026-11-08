#!/usr/bin/env bash
# Install Sakura for this user. Safe to run again: it re-renders config and re-links everything.
#   ./install.sh [--profile FILE]
# FILE (default ~/.config/sakura/profile.md) holds your own notes for the agent, added to its instructions.
# It downloads the engine from this version's release, then every model that suits this machine in the background
# (sakura-model models; SAKURA_NO_AUTOPULL=1 skips that). It tells you what's still missing at the end.
set -eu
ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
SAKURA_HOME="$HOME/.sakura"
PROFILE="$HOME/.config/sakura/profile.md"
if [ "${1:-}" = --profile ]; then PROFILE="${2:?--profile needs a file}"; fi

if [ "$(uname -s)" != Linux ]; then
    echo "Sakura runs on Linux only." >&2
    exit 1
fi
mkdir -p "$SAKURA_HOME" "$HOME/.agents" "$HOME/.local/bin" "$HOME/.config/sakura"

# Point a path at ours. Anything there that isn't already a link is kept beside it.
link() {
    if [ -e "$2" ] && [ ! -L "$2" ]; then mv "$2" "$2.bak-$(date +%Y%m%d%H%M%S)"; fi
    ln -sfn "$1" "$2"
}
# config.toml and hooks.json are copies, not links: the app writes runtime state into its config, and
# re-rendering resets that and keeps it out of version control.
render() {
    if [ -L "$2" ]; then rm -f "$2"; fi
    sed "s#__SAKURA_DIR__#$ROOT#g" "$1" > "$2"
    chmod 0644 "$2"
}
render "$ROOT/config.toml" "$SAKURA_HOME/config.toml"
render "$ROOT/hooks.json" "$SAKURA_HOME/hooks.json"
# The guard runs from its root-owned copy once sakura-guard-install has put it there; then it's left out here, or it
# would run twice, once from a copy Sakura can edit. Until then it stays, so no machine runs unguarded.
if "$ROOT/bin/sakura-guard-install" --check >/dev/null 2>&1; then
    python3 - "$SAKURA_HOME/hooks.json" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
for event, groups in list(d["hooks"].items()):
    for g in groups:
        g["hooks"] = [h for h in g["hooks"] if not any(n in h.get("command", "") for n in ("tool_guard.py", "claim_check.py", "undo_snapshot.py"))]
    d["hooks"][event] = [g for g in groups if g["hooks"]]
    if not d["hooks"][event]:
        del d["hooks"][event]
json.dump(d, open(p, "w"), indent=2)
PY
fi
if [ -L "$SAKURA_HOME/AGENTS.md" ]; then rm -f "$SAKURA_HOME/AGENTS.md"; fi
{
    cat "$ROOT/AGENTS.md"
    if [ -r "$PROFILE" ]; then printf '\n## About this user\n\n'; cat "$PROFILE"; fi
} > "$SAKURA_HOME/AGENTS.md"
link "$ROOT/rules" "$SAKURA_HOME/rules"
link "$ROOT/skills" "$HOME/.agents/skills"
for tool in web_search wikipedia fetch_url curated_search consult sakura-model sakura-guard-install sakura-launch sakura-worker sakura-memory sakura-recall sakura-tool sakura-browser sakura-web-setup live view_file edit_file rag sakura-mail-setup pa sakura-fix sakura-undo sakura-recap sakura-tour sakura-tonight sakura-teach sakura-learn sakura-guardian sakura-trust look sakura-pr sakura-review clip dq procwatch fleet sakura-try sakura-morning schema hear say docpack ledger sakura-red sakura-decide sakura-setup; do
    ln -sf "$ROOT/bin/$tool" "$HOME/.local/bin/$tool"
done

# The engine, from this version's release, so a machine doesn't need 20 GB of RAM and half an hour to compile it. A failure
# here keeps whatever binary is already there. Set SAKURA_NO_BINARY=1 to skip this, as when you build your own.
install_binary() {
    local version tag url tmp asset="sakura-linux-$(uname -m).tar.gz"
    version="$(cat "$ROOT/VERSION")"
    tag="v$version"
    [ "${SAKURA_NO_BINARY:-0}" != 1 ] || return 0
    [ "$(cat "$SAKURA_HOME/binary-version" 2>/dev/null)" != "$version" ] || return 0
    url="${SAKURA_RELEASE_URL:-https://github.com/coderkoala/sakura/releases/download/$tag}"
    tmp="$(mktemp -d)"
    if ! curl -fsSL --max-time 900 -o "$tmp/$asset" "$url/$asset" || ! curl -fsSL --max-time 60 -o "$tmp/$asset.sha256" "$url/$asset.sha256"; then
        echo "  couldn't download the engine for $tag; keeping the current one. To build it instead, see $ROOT/patches/README.md"
        rm -rf "$tmp"; return 0
    fi
    if ! (cd "$tmp" && sha256sum -c --quiet "$asset.sha256" >/dev/null 2>&1) || ! tar -xzf "$tmp/$asset" -C "$tmp" sakura; then
        echo "  the engine download failed its checksum; not installing it. To build it instead, see $ROOT/patches/README.md"
        rm -rf "$tmp"; return 0
    fi
    chmod 755 "$tmp/sakura"
    # Too new a system library is the likely failure on an older distro, so prove it runs before replacing anything.
    if ! "$tmp/sakura" --version >/dev/null 2>&1; then
        echo "  the prebuilt engine won't run on this system, usually an older glibc; keeping the current one. To build it, see $ROOT/patches/README.md"
        rm -rf "$tmp"; return 0
    fi
    if [ -e "$HOME/.local/bin/sakura" ]; then cp -f "$(readlink -f "$HOME/.local/bin/sakura")" "$HOME/.local/bin/sakura.prev" 2>/dev/null || true; fi
    mv -f "$tmp/sakura" "$HOME/.local/bin/sakura.new" && mv -f "$HOME/.local/bin/sakura.new" "$HOME/.local/bin/sakura"
    printf '%s\n' "$version" > "$SAKURA_HOME/binary-version"
    rm -rf "$tmp"
    echo "  engine: $tag installed from the release"
}
install_binary

echo "Sakura $(cat "$ROOT/VERSION") installed to $SAKURA_HOME."
missing=0
need() { missing=1; echo "  needed: $*"; }
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) need "add ~/.local/bin to your PATH" ;; esac
command -v python3 >/dev/null || need "install python3"
command -v git >/dev/null || need "install git"
if ! command -v sakura >/dev/null && [ ! -x "$HOME/.local/bin/sakura" ]; then
    need "the engine: it couldn't be downloaded, so build it: see $ROOT/patches/README.md"
fi
if ! command -v ollama >/dev/null; then
    need "install Ollama: https://ollama.com/download, then: sakura-model pull-all"
elif [ "${SAKURA_NO_AUTOPULL:-0}" != 1 ] && "$ROOT/bin/sakura-model" models 2>/dev/null | grep -q '^  missing'; then
    # Every model that suits this machine, most needed first, while the disk allows. sakura-model models lists them.
    "$ROOT/bin/sakura-model" pull-all --background | sed 's/^/  /' || need "sakura-model pull-all"
fi
echo "  driver: $("$ROOT/bin/sakura-model" plan 2>&1 || true)"
# The guardian checks the machine once a day and says what's about to hurt; quiet when nothing is.
command -v systemctl >/dev/null 2>&1 && "$ROOT/bin/sakura-guardian" on >/dev/null 2>&1 || true
"$ROOT/bin/sakura-guard-install" --check >/dev/null 2>&1 || need "the guard where Sakura can't edit it: sudo $ROOT/bin/sakura-guard-install"
[ "$missing" = 1 ] || echo "  nothing else needed."
[ -x "${XDG_DATA_HOME:-$HOME/.local/share}/sakura/webenv/bin/python" ] || echo "  optional: sakura-web-setup, for better search and fetching and the browser"
echo
echo "Run it with: sakura-launch"
echo "For the ? keys (?, ??, ?fix, ?undo, ?recap, ?remind, ?pa), add to ~/.bashrc:  source $ROOT/shell/sakura.bash"
