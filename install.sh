#!/usr/bin/env bash
# Install Sakura for this user. Safe to run again: it re-renders config and re-links everything.
#   ./install.sh [--profile FILE]
# FILE (default ~/.config/sakura/profile.md) holds your own notes for the agent, added to its instructions.
# It doesn't build the binary or download models; it tells you what's still missing at the end.
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
if [ -L "$SAKURA_HOME/AGENTS.md" ]; then rm -f "$SAKURA_HOME/AGENTS.md"; fi
{
    cat "$ROOT/AGENTS.md"
    if [ -r "$PROFILE" ]; then printf '\n## About this user\n\n'; cat "$PROFILE"; fi
} > "$SAKURA_HOME/AGENTS.md"
link "$ROOT/rules" "$SAKURA_HOME/rules"
link "$ROOT/skills" "$HOME/.agents/skills"
for tool in web_search wikipedia fetch_url curated_search consult sakura-model sakura-launch sakura-worker sakura-memory sakura-recall sakura-tool sakura-browser sakura-web-setup live; do
    ln -sf "$ROOT/bin/$tool" "$HOME/.local/bin/$tool"
done

echo "Sakura $(cat "$ROOT/VERSION") installed to $SAKURA_HOME."
missing=0
need() { missing=1; echo "  needed: $*"; }
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) need "add ~/.local/bin to your PATH" ;; esac
command -v python3 >/dev/null || need "install python3"
command -v git >/dev/null || need "install git"
if ! command -v sakura >/dev/null && [ ! -x "$HOME/.local/bin/sakura" ]; then
    need "build the binary: see $ROOT/patches/README.md"
fi
if ! command -v ollama >/dev/null; then
    need "install Ollama: https://ollama.com/download"
elif ! ollama list 2>/dev/null | grep -q 'qwen3.5-abliterated:9b'; then
    need "ollama pull huihui_ai/qwen3.5-abliterated:9b"
fi
echo "  driver: $("$ROOT/bin/sakura-model" plan 2>&1 || true)"
[ "$missing" = 1 ] || echo "  nothing else needed."
[ -x "${XDG_DATA_HOME:-$HOME/.local/share}/sakura/webenv/bin/python" ] || echo "  optional: sakura-web-setup, for better search and fetching and the browser"
echo
echo "Run it with: sakura-launch"
echo "For a ? key, add to ~/.bashrc:  alias '?'=sakura-launch"
echo "For a coordinator that hands work to disposable workers:  sakura-launch --coordinator"
