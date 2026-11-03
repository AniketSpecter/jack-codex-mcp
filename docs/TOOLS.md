# MCP tools and native operation schema

The server advertises 18 tools. Calls use normal MCP structured arguments.

| Tools | Purpose |
|---|---|
| `list_project_maps`, `inspect_map` | Enumerate/analyze files inside `JACK_PROJECT_ROOT` |
| `find_map_entities`, `check_map_issues` | Search and heuristic validation |
| `explain_compile_log`, `jack_help` | Diagnostics and workflow guidance |
| `jack_list_windows`, `jack_window_info`, `jack_screenshot` | Read-only desktop inspection |
| `jack_click`, `jack_drag`, `jack_shortcut`, `jack_type_text` | Separate optional GUI input |
| `jack_native_capabilities` | Exact supported host, read/edit availability |
| `jack_native_document`, `jack_native_selection` | Fresh editor-thread bounded snapshots |
| `jack_native_plan_edits` | Validate exact operations and return an expiring preview |
| `jack_native_apply_edits` | Apply an approved, unchanged, one-use plan |

Native mutation example:

```json
{"operations":[{"op":"create_brush","min":[-24,64,0],"max":[24,96,40],"texture":"AAATRIGGER"}]}
```

Check the implementation's `validateOps` for the authoritative field names and
limits. This table is a guide; never guess IDs or unsupported operations.

| `op` | Other fields |
|---|---|
| `create_brush` | `min`, `max`, `texture` |
| `duplicate_brush` | `brush_id`, `delta` |
| `move_brush` | `brush_id`, `delta` |
| `rotate_brush_z` | `brush_id`, `pivot`, `degrees` |
| `create_entity` | `classname`, `origin` |
| `move_entity` | `entity_id`, `delta` |
| `set_entity_property` | `entity_id`, `key`, `value` |

All vectors are XYZ arrays. Transforms/duplicates accept worldspawn brushes,
not brush entities. Point classes currently allowed: `info_target`, `light`,
`info_player_start`, `info_player_deathmatch`. Properties are ASCII and reject
special structural keys including `classname`, `origin`, `angles`, `mapversion`
and `wad`. Coordinate components are limited to ±30,000 for this API, not a claim
about engine map limits. New box dimensions are 1–8192 units per axis.

Plans expire after five minutes. A new plan invalidates the previous plan.
Apply takes `plan_id` and `approval_token`. A token ties the request to the exact
plan; it is **not evidence that a human approved it**. The assistant must obtain
approval before edits to real working copies. Returned SDK IDs are session-local.

GUI control requires `JACK_ENABLE_LIVE_CONTROL=1`, matching editor foreground
state and tool-specific confirmations. Window-title matching is weaker than
native PID/hash validation. Leave GUI input disabled unless you need it. It is
not a replacement for semantic native commands or per-edit authorization.
