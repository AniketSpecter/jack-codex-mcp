# Tutorial: manual mapping with an assistant

## 1. Start safely

Complete [installation](INSTALL.md). Open **Start JACK Codex.cmd**. Choose
**Create new map**, name it `mcp_training`, and leave native editing off for the
first read. The generator creates an enclosed eight-brush room and player spawn.
It is an editor fixture, not a verified gameplay/compile-ready map. Configure a
real texture and WAD in `config.local.json` for your own game before compiling.

Maximize the document inside JACK. Ask:

> Read the current JACK document, report entity/brush counts, then show the
> selection. Do not modify anything.

Select a brush manually and ask again. Counts/IDs should match the editor.
Screenshots capture the visible window; bring JACK in front before using them.

## 2. First native edit

Save and close the disposable fixture. Relaunch it from the workspace with
**Experimental native edits** enabled. Read the Save As warning.

Ask:

> In this disposable map only, preview creating a box from [-24, 64, 0] to
> [24, 96, 40], using my configured texture. Show the operation and wait.

The assistant calls `jack_native_plan_edits` and presents the exact operation.
After your approval it calls `jack_native_apply_edits` with that plan's ID/token.
The result lists changed IDs, revisions and a recovery directory. Inspect the
new brush in JACK. Ordinary editor Ctrl+Z / Ctrl+Y can undo/redo creation; direct
native Undo/Redo tools are not implemented.

**Use File > Save As to save a JMF even if JACK displays no unsaved star.**
Reopen that JMF and verify the brush before using this workflow on larger copies.
After Save As changes the filename, launch the JMF as a fresh session to edit it.

## 3. Transform and annotate

Read a fresh native snapshot to obtain current IDs. Ask for a preview to move
the test brush 32 units in X, rotate it 90 degrees around `[32,80,0]`, or duplicate
it with a 96-unit X offset. IDs must come from this session, not an old report.

For a point entity, preview creating `info_target` at `[0,160,32]`, then setting
its `targetname` to `mcp_training_target`. These are separate plans if the entity
ID is not known until creation. Restricted keys must not be changed through a
generic property edit; read [TOOLS.md](TOOLS.md).

Save As and verify after every accepted batch. Revision errors require a new
preview. An expired/consumed plan or timed-out apply must never be replayed.

## 4. Work on your own map

Save all current editor work first. **Open / import map copy** creates a uniquely
named working copy and a hash-verified saved-byte checkpoint. The original file
stays untouched. Edit manually as usual; ask the assistant to inspect, explain
compile errors, or preview small native operations on this copy.

Only promote a saved, reopened, visually checked map to your normal project
through your own deliberate workflow. No tool automatically installs a level
into your game. Compile externally or configure JACK manually after export.

## 5. Recovery

Persistent maps: `<project>/JACKCodexWorkspace/maps`.
Saved checkpoints: `backups/<timestamp>`.
Per-session logs/recovery: `sessions/<id>/editor/codex-bridge`.

If an edit faults, stop mutations. Preserve the session directory, inspect the
receipt and live map, try editor Undo if appropriate, or restore a saved backup
as a **new copy**. `before-sdk.json` describes geometry/properties but does not
restore all JMF metadata automatically. Never upload endpoint files or private
maps with a bug report.
