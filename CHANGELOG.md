# Changelog

## 0.3.0-alpha.1 — 2026-11-02

- Portable local configuration and copied-editor mapping workspace.
- Automatic native snapshots through an editor-thread dispatcher.
- Experimental box creation, duplication, movement, Z rotation, restricted point
  entity creation/movement and property edits.
- Exact plan previews, revision checks, expiring one-use tokens, checkpoints,
  operation receipts and fault locking.
- Public source build with pinned SDK/JSON dependencies, tests and tutorials.
- Known blocker: native edits may not notify the host of unsaved changes.
  Editing is opt-in; File > Save As and reopen verification remain necessary.
