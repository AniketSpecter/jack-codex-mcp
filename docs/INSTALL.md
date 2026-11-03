# Installation

## Requirements

- Windows x64; Python 3.11+ with Tkinter and the `py` launcher.
- Your own J.A.C.K. **1.1.3773 Freeware x64** installation, with a working game
  profile, FGD and textures configured. Other builds are rejected, not guessed.
- Git, CMake 3.20+ and Visual Studio C++ Build Tools with an x64 compiler and
  Windows SDK for native compilation. No editor/game binaries are distributed.
- A stdio MCP client. Codex CLI is optional for automatic registration.

## Build and setup

The Windows alpha release ZIP includes a prebuilt plugin and matching SDK source.
Extract it and run `setup.ps1 -DesktopShortcut` without `-BuildNative` to use the
included DLL. You still supply Python and your own supported JACK installation.
Verify the ZIP against the release's `SHA256SUMS.txt`. Source-only GitHub archives
require building the plugin as described below.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1 `
  -EditorDirectory 'D:\Tools\JACK' -ProjectRoot 'D:\Maps\MyProject' `
  -BuildNative -DesktopShortcut
```

Omit path arguments for interactive prompts. If the correct game profile is not
enabled in JACK, configure it first or pass `-GameProfile Config0` (use the real
section name from `VDKGameCfg.ini`). Setup writes ignored `config.local.json`.

`scripts/fetch-deps.ps1` downloads the pinned SDK revision and checks the JSON
header hash. `scripts/build-native.ps1` builds the DLL and runs a mock capture
contract. To specify CMake explicitly:

```powershell
.\scripts\build-native.ps1 -CMake 'C:\Tools\CMake\bin\cmake.exe'
```

Setup preserves an existing `jack-map` registration. Use `-ReplaceMcp` to replace
it after backing up Codex's config. Use `-SkipRegister` for other clients and
configure the absolute `.venv\Scripts\python.exe` and `server.py` paths manually.
Use [config.example.toml](../config.example.toml) as a template; never commit
your actual paths/tokens.

## Enable the connection

Reconnect `jack-map` or restart your MCP client. Tool metadata is cached by
clients; changing Python source does not hot-install new tool definitions.
Expect **18 tools** from this version. `codex mcp get jack-map --json` checks CLI
registration; it does not prove a running chat has reconnected.

Launch **Start JACK Codex.cmd** or the **JACK Codex MCP** desktop shortcut.
Import a saved map copy or create a new fixture. Maximize the map's MDI document
inside JACK, dismiss modal dialogs, and ask for `jack_native_capabilities` then
`jack_native_document`. No manual capture click is required with plugin 0.3.

The initial session is read-only. Experimental edits require checking the box
and acknowledging the known Save As issue. Opening a different file or Save As
to a different filename invalidates the title-bound editing session. Save first,
then launch the newly saved working JMF through the workspace for further edits.

## Common problems

| Symptom | Action |
|---|---|
| Unsupported fingerprint | Check edition/build; do not remove the hash guard |
| No native endpoint | Launch a fresh copied-editor session; inspect its `codex-bridge/audit.jsonl` |
| Wrong map / document guard | Maximize the bound document; close dialogs; do not rename it mid-session |
| New tools missing | Reconnect/restart client, verify the server's absolute path |
| GUI input disabled | Intentional default; native operations do not need GUI input |
| Timeout / outcome unknown | Do not retry apply; inspect live state and recovery receipts |
| Missing textures | Configure your own WAD/FGD profile; repository supplies no game assets |
| Missing JMF parser | Use native live reads or export MAP; optional MESS is not bundled |

Do not relaunch a previously used session executable: sessions have unique
protected IPC directories and fail closed on reuse. Open the persistent map via
the workspace to create a fresh session instead. Save old editor work first.

## Uninstall

Save your maps. Remove the MCP registration (`codex mcp remove jack-map`) and the
shortcut. Keep `JACKCodexWorkspace/maps` and `backups` if you need your work.
The original editor installation and source maps were not modified by setup.
