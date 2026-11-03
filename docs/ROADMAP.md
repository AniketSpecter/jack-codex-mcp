# Roadmap

## Implemented alpha

Read-only file/window tools; bounded native document/selection reads; seven
limited experimental edits; plan/revision/token validation; saved-file
checkpoints; SDK geometry recovery JSON; copied-editor workspaces; source build
and documentation.

## Stable native-editing blockers

1. Reliable host modified-document notification and save/close behavior through
   a verified interface. No executable patching or guessed private Qt calls.
2. Exact native document identity/path and full-fidelity unsaved JMF recovery.
3. Real-host Undo/Redo regression coverage for every transform/property operation.
4. Fault injection, partial-batch recovery and timeout outcome verification.
5. Large-world memory/performance measurements and bounded pagination.

## Next editor capabilities

Native select/deselect, deletion, brush entities, arbitrary-axis transforms,
texture lock/material editing, groups/VisGroups, native save and direct Undo/Redo
invocation **if supported by verified APIs**. These are proposals, not existing
tools. Editing working copies does not imply arbitrary map editing is safe.

## Community

More version adapters with pinned ABI tests; mapping tutorials; sanitized
screenshots/videos from contributors; packaging improvements; editor integration
without manual session staging. No delivery date is promised for unverified APIs.
