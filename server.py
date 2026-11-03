"""Codex MCP: JACK map inspection plus opt-in Windows desktop control."""
from mcp.server import MCPServer
from mcp.server.mcpserver import Image
from core import (
    list_maps, map_summary, find_entities as search_entities,
    validate_map as check_map, diagnose_log, help_topic,
)
from live_control import (
    discover_windows, describe_window, capture_window_png,
    mouse_click, mouse_drag, send_shortcut, type_into_focused_field,
)
import native_bridge

mcp = MCPServer('JACK Codex Companion')


@mcp.tool()
def list_project_maps(max_results: int = 100) -> dict:
    """List maps within JACK_PROJECT_ROOT (.map/.jmf/.rmf)."""
    return list_maps(max_results)


@mcp.tool()
def inspect_map(relative_path: str) -> dict:
    """Read-only geometry, entities, and texture summary. Binary maps need MESS_EXE."""
    return map_summary(relative_path)


@mcp.tool()
def find_map_entities(relative_path: str, classname: str = '', key: str = '', contains: str = '', limit: int = 40) -> dict:
    """Search entities for classnames, key-values, targets and origins."""
    return search_entities(relative_path, classname, key, contains, limit)


@mcp.tool()
def check_map_issues(relative_path: str) -> dict:
    """Heuristic map integrity check (not a compiler)."""
    return check_map(relative_path)


@mcp.tool()
def explain_compile_log(relative_path: str, max_issues: int = 40) -> dict:
    """Explain common errors in a compilation .log or .txt file."""
    return diagnose_log(relative_path, max_issues)


@mcp.tool()
def jack_help(topic: str = 'workflow') -> dict:
    """Learn JACK mapping workflows and limitations."""
    return help_topic(topic)


@mcp.tool()
def jack_list_windows() -> list[dict]:
    """Discover running JACK editor windows on Windows. No editor modification."""
    return discover_windows()


@mcp.tool()
def jack_window_info(hwnd: int = 0) -> dict:
    """Get running JACK window client-area coordinates and control status."""
    return describe_window(hwnd)


@mcp.tool()
def jack_screenshot(hwnd: int = 0) -> Image:
    """Capture visible JACK client area for Codex visual inspection (may be occluded)."""
    return Image(data=capture_window_png(hwnd), format='png')


@mcp.tool()
def jack_click(x: int, y: int, button: str = 'left', clicks: int = 1, hwnd: int = 0) -> dict:
    """OPT-IN: click JACK client-relative x/y. Only when JACK is foreground."""
    return mouse_click(x, y, button, clicks, hwnd)


@mcp.tool()
def jack_drag(x1: int, y1: int, x2: int, y2: int, duration: float = 0.6, hwnd: int = 0) -> dict:
    """OPT-IN: left-drag between JACK client-relative points when JACK is foreground."""
    return mouse_drag(x1, y1, x2, y2, duration, hwnd)


@mcp.tool()
def jack_shortcut(keys: str, hwnd: int = 0, confirm_destructive: bool = False) -> dict:
    """OPT-IN: send allowlisted shortcut (ctrl+z, ctrl+s, esc, etc) to foreground JACK."""
    return send_shortcut(keys, hwnd, confirm_destructive)


@mcp.tool()
def jack_type_text(text: str, confirm_focused_field: bool = False, hwnd: int = 0) -> dict:
    """OPT-IN: type ASCII into explicitly confirmed focused JACK text field."""
    return type_into_focused_field(text, confirm_focused_field, hwnd)


@mcp.tool()
def jack_native_capabilities() -> dict:
    """Verified native capabilities, automatic dispatcher and edit enablement."""
    return native_bridge.capabilities()


@mcp.tool()
def jack_native_document() -> dict:
    """Read a fresh automatic editor-thread snapshot (native 0.3 sessions)."""
    return native_bridge.read_snapshot()


@mcp.tool()
def jack_native_selection() -> dict:
    """Read the current native selection automatically on the editor thread."""
    return native_bridge.read_snapshot(selection_only=True)


@mcp.tool()
def jack_native_plan_edits(operations: list[dict]) -> dict:
    """Preview native brush/entity edits. Returns revision-bound one-use approval token.

    Supported op values: create_brush(min,max,texture), duplicate_brush(brush_id,delta),
    move_brush(brush_id,delta), rotate_brush_z(brush_id,pivot,degrees),
    create_entity(classname,origin), move_entity(entity_id,delta),
    set_entity_property(entity_id,key,value). Does not modify the map.
    """
    return native_bridge.plan_edits(operations)


@mcp.tool()
def jack_native_apply_edits(plan_id: str, approval_token: str) -> dict:
    """Apply the exact preview after user approval; fixture tests are preauthorized.

    Runs native SDK commands on the editor thread, checkpoints current geometry
    and saved source, records an Undo transaction and verifies state changes.
    Never replay after an outcome_unknown timeout. Does not save the document.
    """
    return native_bridge.apply_edits(plan_id, approval_token)


if __name__ == '__main__':
    mcp.run(transport='stdio')
