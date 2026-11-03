# Safety and known limits

## Data boundaries

Setup stores your paths locally in ignored files. The workspace imports copies,
checks saved-file hashes, and stages a copy of your own editor installation.
The original installation, source maps and game directory are not edit targets.
Do not redistribute staged editor binaries or third-party maps/assets.

**Native edits may not trigger JACK's modified-document star/close prompt.**
This is an open blocker for a stable release. Experimental editing is opt-in;
use File > Save As JMF after each batch and reopen to verify. The plugin does not
claim to save natively or preserve unsaved state when the editor closes.

## Authorization and validation

- Agent previews exact operations and obtains user approval for real edits.
- One-use tokens bind a five-minute plan, world identity and full SDK geometry/
  property fingerprint. Tokens are not an independent human approval mechanism.
- Only the bound filename may be edited; it must appear in the maximized document
  title, with no modal dialog. **The SDK does not expose a verified full document
  path.** Filename/title checks cannot prove identity between identical filenames.
  Working-copy filenames are unique; do not open ambiguous documents.
- Saved source bytes and SDK geometry/property JSON are captured before editing;
  after-state and receipt are written following mutation. SDK JSON does not
  preserve all JMF cameras/groups/metadata and has no automatic full restore.
- One editor Undo transaction wraps a batch. Errors may leave partial changes;
  the session locks after mutation faults. This is not an atomic database commit.
- Limits, finite coordinates, ownership and linked-list checks reject malformed
  requests/state. Native code still runs inside JACK and can crash the editor.

## Transport

Local named pipes reject remote clients, use current-user ACLs and per-session
tokens, and check PID/executable identity. Requests are bounded to 8 KiB, replies
to 256 KiB. Tokens/raw requests are not logged. Private endpoint files and map
snapshots must not be uploaded. This does not protect against malware running as
the same Windows user.

SDK calls execute on the editor UI thread through our message-only window.
Requests have deadlines; a timeout can mean **unknown outcome**. Never replay an
apply after a timeout: inspect the map and receipts, then form a new plan.

## Recovery

Save/checkpoint before experimentation. Keep session logs and receipts locally.
Use editor Undo where appropriate or restore a saved backup into a new copy.
Save As, reopen, compare geometry, and compile/playtest before promoting a map.
The absence of a compiler warning is not proof of a valid level.
