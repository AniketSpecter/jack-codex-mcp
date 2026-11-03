# Contributing agents

- Read README.md, docs/COMPATIBILITY.md and docs/SAFETY.md first.
- Native SDK calls belong exclusively on the editor UI thread via our message-only dispatcher.
- Preview exact edits and obtain the user's authorization before applying them.
  A returned token binds a plan; it does not prove human approval.
- Test mutations only on disposable maps before working-copy use.
- Never overwrite originals, publish local sessions/maps/tokens or patch the editor.
- Native Undo transaction recording is implemented; native Undo/Redo invocation is not.
- Do not assume document path/metadata recovery is complete. Describe limits honestly.
- Add a regression test when changing IPC, authorization, checkpoint or geometry logic.
