# Engine patch

The `sakura` binary is Open Interpreter (a Rust fork of Codex) plus `engine.patch`. `install.sh` downloads the matching build from this version's GitHub release (Linux x86_64) and verifies its checksum, so you only need this page to build it yourself, with `SAKURA_NO_BINARY=1`. The short way is `tools/build-engine.sh [TARGET]` (`x86_64-unknown-linux-musl` for a static binary that runs on any glibc, `aarch64-unknown-linux-musl` for ARM; `--check` only proves the patch applies), which makes the asset `install.sh` looks for. By hand:

    git clone https://github.com/OpenInterpreter/open-interpreter sakura-src && cd sakura-src
    git checkout "$(cat <this repo>/patches/ENGINE_BASE)"
    git apply <this repo>/patches/engine.patch
    cd codex-rs && cargo build --release -j 3 -p codex-cli --bin codex   # -j 3: linking peaks near 20 GB of RAM
    cd <dotfiles> && SAKURA_BIN=$PWD/target/release/codex ./install.sh --only sakura

What it changes: Sakura's name and config home, no network at startup, and in the qwen-code harness: thinking
off (answers were landing in `reasoning` and reaching the user as silence), `<lookup>` context placed beside the
question instead of mid system prompt, and Stop hook prompts actually delivered to the model. It also cuts the oldest tool output before a small context can overflow, and hides the MCP resource tools nothing here serves.

Regenerate after changing the engine: `git -C ~/sakura-src diff "$(cat patches/ENGINE_BASE)" > patches/engine.patch`
