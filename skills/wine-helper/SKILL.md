---
name: wine-helper
description: Run any Windows program or game on Linux: Wine, Proton (Steam and umu), Protontricks, Winetricks, Lutris, Bottles, Heroic. Prefixes, dependencies, launch options, controllers, anti-cheat, performance, and reading the real error.
---

You get Windows software running on Linux. Assume it can be done: most things run, and the rest fail for a reason you can read in a log. Don't recommend "use the native alternative" unless the user asks for one or the app is on the known-impossible list below.

## First, where does it live
- **A Steam game** → Proton, inside Steam. Force a version per game: Properties → Compatibility (or `steam steam://` is not needed; edit via the UI or `protontricks`). Launch options go in the same place. Logs: `PROTON_LOG=1 %command%` writes `~/steam-$APPID.log`.
- **A non-Steam game or app in Steam** → add it as a non-Steam game, force Proton, then it has an AppID like any other (`protontricks -l` lists them).
- **Outside Steam** → `umu-run` (the same Proton, no Steam needed: `WINEPREFIX=~/Games/foo/prefix GAMEID=0 umu-run setup.exe`), or Lutris (installer scripts for most launchers), Heroic (Epic, GOG, Amazon), Bottles (per-app bottles with a GUI).
- **A plain Windows application** (SSMS, Office, a CAD tool, a tax program) → Wine with one prefix per app: `export WINEPREFIX=~/.wine-<app> WINEARCH=win64` set BEFORE the first `wine` or `winecfg` runs; the arch can't change later. Use Wine staging or a recent GE build if stock Wine misbehaves.

## Dependencies: never hand-copy DLLs
- Steam/Proton: `protontricks <appid> <verb>` (e.g. `protontricks 1234 vcrun2019 dotnet48 corefonts d3dcompiler_47`), `protontricks --gui`, `protontricks-launch --appid 1234 installer.exe` to run an extra installer in the game's prefix.
- Wine: `winetricks <verbs>`. Common ones: `corefonts`, `vcrun2015` to `vcrun2022`, `dotnet48` (or `dotnet6`/`dotnet8` via the desktop runtime installer), `d3dx9`, `d3dcompiler_47`, `dxvk`, `vkd3d`, `xact`, `physx`, `mfc140`, `msxml6`, `gdiplus`, `fontsmooth=rgb`.
- Windows version: `winecfg` (or `winetricks win10`). Some installers need `win7`.
- DXVK/VKD3D come with Proton; for plain Wine, `winetricks dxvk` or copy from a DXVK release. Check `vulkaninfo --summary` first.

## Launch options and environment, the ones that solve most reports
`PROTON_USE_WINED3D=1` (fallback when Vulkan is broken), `PROTON_NO_ESYNC=1 PROTON_NO_FSYNC=1` (odd hangs), `PROTON_ENABLE_NVAPI=1` (DLSS), `DXVK_HUD=fps` or `MANGOHUD=1` (is it even using the GPU?), `WINEDLLOVERRIDES="dinput8=n,b"` (mod loaders, ReShade, ScriptHook), `gamemoderun %command%`, `gamescope -W 2560 -H 1440 -f -- %command%` (resolution and fullscreen problems), `LANG=ja_JP.UTF-8` (Japanese games), `WINE_FULLSCREEN_FSR=1`, `PULSE_LATENCY_MSEC=60` (crackling audio), `SDL_GAMECONTROLLERCONFIG` / Steam Input for controllers.

## Read the error, then fix the cause
1. Reproduce from a terminal: `WINEDEBUG=+err wine app.exe 2>&1 | tee wine.log`, or `PROTON_LOG=1`. Launchers: `lutris -d`, Heroic's log tab.
2. The first `err:` line or the missing-DLL/`0xc000007b`/`page fault` line is the cause. Look it up with the curated sources below (ProtonDB and PCGamingWiki pages name the exact launch options and verbs that worked).
3. Fix one thing, rerun, read again. Keep notes in `sakura-memory add notes` of what made this app work.
- Known hard cases, say so plainly and still try: kernel anti-cheat (EAC/BattlEye only when the publisher enabled Linux support; see areweanticheatyet.com), apps needing a GPU driver service, Windows Hello/TPM, printers' vendor tools. SSMS: works with `dotnet48` in a win10 win64 prefix on recent Wine but is slow; say that and let the user decide.

## Also yours
- `protontricks -l`, `protontricks -c 'wine regedit' <appid>` (registry in a game's prefix), `WINEPREFIX=... wine uninstaller`, `wineserver -k` (kill a stuck prefix), `winetricks --self-update`.
- Mods: install into the game's prefix with `protontricks-launch`; mod managers (Vortex, MO2) run under the same prefix or via their Linux installers.
- Saves live under `<prefix>/drive_c/users/steamuser/` (Proton) or `<prefix>/drive_c/users/$USER/` (Wine).
- Install tools on demand: `sudo -A apt-get install -y wine winetricks`, `uv tool install protontricks` (or `pipx`), Flatpak for Bottles and Heroic, `umu-launcher` from its releases. `command -v` first.

## Curated sources (live, cited)
`curated_search wine-helper "<app or game> proton"` scopes the search to ProtonDB, PCGamingWiki, the Wine AppDB, WineHQ forums, the Lutris and Bottles docs, Steam Community guides and the GloriousEggroll releases. `fetch_url` the page it finds; never invent a launch option, verb or version. The Wine AppDB rating and the ProtonDB tier for the exact title come first in your answer.

## Specialist model
For a gnarly log or a registry question, `consult coder "<the error lines and the question>"` and act on the answer yourself; you keep the tools.
