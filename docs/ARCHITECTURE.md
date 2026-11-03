# Architecture

```text
MCP client -> Python stdio server -> authenticated local named pipe
                                       |
                               C++ transport worker
                                       |
                                bounded job queue
                                       |
                       message-only Win32 window / UI thread
                                       |
                     guarded JACK SDK capture / plan / mutation
```

`server.py` declares 18 tools. `core.py` handles read-only file analysis;
`live_control.py` handles optional foreground GUI input. `native_bridge.py`
validates endpoints, process identity and bounded IPC responses.

`workspace.py` stages local copied-editor sessions and persistent working maps.
It writes `mapping-active.json` for endpoint discovery. Each fresh editor owns
its own protected `codex-bridge` directory and token. Explicit
`JACK_NATIVE_ENDPOINT` selects a session when running multiple editors.

`native/bridge.cpp` validates the ABI, captures read-only state, and runs the
named-pipe transport. `native/native_edits.h` implements bounded job dispatch,
validation, plans, recovery snapshots and seven native operations. A private
message-only window is created on the verified editor thread; its procedure
executes queued SDK work. Pipe workers never call SDK mutations directly.

Brush transforms update vertices, face planes and bounds, then rebuild editor
geometry through the SDK. Plans fingerprint all exposed geometry/texture and
entity property state, excluding transient selection/render state. This is not
a full document serialization or proof of group/camera metadata consistency.

No HTTP service, cloud account or external LLM key is required by this server.
The MCP client supplies the assistant; the server does not implement an agent.
