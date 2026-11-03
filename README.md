# JACK Codex MCP

An unofficial Windows MCP server and native C++ plugin for assisted mapping in
**J.A.C.K. Map Editor**. Inspect maps, read live selection, and preview/apply
limited native brush and entity edits through Codex or another stdio MCP client.

**Version 0.3.0-alpha.1 — experimental, not a complete editor SDK.**
Native editing is validated only against **J.A.C.K. 1.1.3773 Freeware x64** with
the exact executable fingerprint in [compatibility](docs/COMPATIBILITY.md).
Other versions fail closed. J.A.C.K. and game assets are not included.

> **Known save issue:** native changes do not reliably trigger JACK's unsaved
> star/close prompt. Editing is opt-in and restricted to staged working copies.
> After each accepted batch, use **File > Save As** to save a JMF and verify it by
> reopening. SDK recovery JSON is not a full JMF backup. See [safety](docs/SAFETY.md).

## Quick start

Requires Windows x64, Python 3.11+, a configured supported JACK installation,
and Codex CLI for automatic registration. Native compilation additionally needs
Git, Visual Studio C++ Build Tools (x64), Windows SDK and CMake 3.20+.

```powershell
git clone https://github.com/AniketSpecter/jack-codex-mcp.git
cd jack-codex-mcp
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1 -BuildNative -DesktopShortcut
```

Setup asks for **your** editor and project paths. It installs dependencies in
`.venv`, builds the plugin, and registers `jack-map` if Codex CLI is present.
An existing registration is preserved unless you explicitly pass `-ReplaceMcp`.
Reconnect/restart your MCP client after installation.

Open **Start JACK Codex.cmd**, import a map **copy**, and maximize the map document
inside JACK. Read-only native sessions are the default. First test experimental
editing on a new disposable map; check its opt-in box when ready.

Ask your assistant:

> Inspect the current JACK document and selection. Do not change anything.

> On this disposable map, preview a 64 × 64 × 64 box at [0, 0, 32]. Show the exact
> operations and wait for my approval before applying them.

[Installation](docs/INSTALL.md) · [Step-by-step tutorial](docs/TUTORIAL.md) ·
[Tools](docs/TOOLS.md) · [Testing](docs/TESTING.md) · [Roadmap](docs/ROADMAP.md)

## What works

| Capability | Status / limits |
|---|---|
| MAP parsing, entity search, compile-log diagnosis | Implemented; heuristic, not a compiler |
| Window discovery / screenshots | Implemented; visible desktop captures can be occluded |
| Native document and selection reads | Automatic editor-thread snapshots; bounded output |
| Create / duplicate / move world brushes | Experimental; convex geometry, bounded inputs |
| Rotate world brushes | Experimental; Z axis only; texture-lock not guaranteed |
| Create / move point entities and edit properties | Experimental; restricted class/key allowlists |
| Change preview / revision checks / checkpoints | Implemented; exact one-use plan tokens |
| Editor Undo transaction recording | Implemented; creation Undo/Redo manually tested |
| Mouse / keyboard MCP tools | Separate opt-in; disabled by setup |
| Native select, delete, Save, Undo/Redo invocation | **Not implemented** |
| Reliable host modified-document notification | **Unresolved — Save As required** |
| All JACK versions, Linux/macOS native plugin | **Not supported** |

The launcher copies the user's installed editor locally and loads the plugin
there. It never patches the executable, installs the plugin into the original
installation, or automatically installs maps into a game.

## Contribute

Read [CONTRIBUTING.md](CONTRIBUTING.md), [architecture](docs/ARCHITECTURE.md) and
[compatibility](docs/COMPATIBILITY.md). Contributions welcome: save notification,
document identity, native selection, broader tests, tutorials and compatibility.
Report security problems through [SECURITY.md](SECURITY.md).

Project code is MIT licensed. SDK headers and other dependencies retain their
own licenses: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
This is independent of the JACK developers, Valve and OpenAI.
