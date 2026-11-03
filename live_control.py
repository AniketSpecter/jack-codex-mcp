"""Windows J.A.C.K. desktop bridge for MCP.

No DLL injection or binary modification. Coordinates are relative to the JACK
client area. File edits and semantic editor APIs are NOT implemented here.

The screenshot and window discovery tools are read-only; keyboard/mouse tools
require JACK_ENABLE_LIVE_CONTROL=1 and an active JACK window.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import re
import sys
from typing import Any

PATTERN = os.environ.get('JACK_WINDOW_PATTERN', r'J\.A\.C\.K\.|Jackhammer')


def _windows_only() -> None:
    if sys.platform != 'win32':
        raise RuntimeError('Live editor control needs local Windows; run Codex and JACK on the same PC.')


def _user32():
    _windows_only()
    u = ctypes.windll.user32
    # Win32 HWNDs are pointer-sized. Explicit prototypes prevent 64-bit truncation.
    u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    u.GetWindowTextLengthW.restype = ctypes.c_int
    u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u.GetWindowTextW.restype = ctypes.c_int
    u.IsWindowVisible.argtypes = [wintypes.HWND]
    u.IsWindowVisible.restype = wintypes.BOOL
    u.GetForegroundWindow.argtypes = []
    u.GetForegroundWindow.restype = wintypes.HWND
    u.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
    u.GetClientRect.restype = wintypes.BOOL
    u.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(POINT)]
    u.ClientToScreen.restype = wintypes.BOOL
    return u


class POINT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


def _window_title(hwnd: int) -> str:
    user32 = _user32()
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def discover_windows() -> list[dict[str, Any]]:
    """List only JACK-looking top-level windows (not arbitrary applications)."""
    user32 = _user32()
    found: list[dict[str, Any]] = []
    cb_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    try:
        regex = re.compile(PATTERN, re.I)
    except re.error as exc:
        raise RuntimeError(f'Invalid JACK_WINDOW_PATTERN: {exc}') from exc

    def callback(hwnd, unused):
        if not user32.IsWindowVisible(hwnd):
            return True
        title = _window_title(hwnd)
        if regex.search(title):
            found.append({'hwnd': int(hwnd), 'title': title,
                          'foreground': int(user32.GetForegroundWindow()) == int(hwnd)})
        return True

    user32.EnumWindows.argtypes = [cb_type, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    enum_cb = cb_type(callback)
    user32.EnumWindows(enum_cb, 0)
    return found


def _selected_window(hwnd: int = 0) -> tuple[int, str]:
    matches = discover_windows()
    if hwnd:
        matches = [w for w in matches if w['hwnd'] == hwnd]
    if not matches:
        raise RuntimeError('J.A.C.K. window not found. Open the editor and retry jack_list_windows.')
    if len(matches) > 1:
        raise RuntimeError('Multiple JACK windows found; pass hwnd from jack_list_windows.')
    return matches[0]['hwnd'], matches[0]['title']


def _client_rectangle(hwnd: int) -> tuple[int, int, int, int]:
    u = _user32()
    rect = RECT()
    if not u.GetClientRect(hwnd, ctypes.byref(rect)):
        raise RuntimeError('Could not retrieve the JACK client area.')
    pt = POINT(0, 0)
    if not u.ClientToScreen(hwnd, ctypes.byref(pt)):
        raise RuntimeError('Could not resolve JACK window position.')
    width, height = rect.right - rect.left, rect.bottom - rect.top
    if width < 100 or height < 100:
        raise RuntimeError('JACK client area is too small or minimized.')
    return int(pt.x), int(pt.y), int(width), int(height)


def describe_window(hwnd: int = 0) -> dict[str, Any]:
    selected, title = _selected_window(hwnd)
    x, y, width, height = _client_rectangle(selected)
    return {'hwnd': selected, 'title': title, 'client_origin_screen_px': [x,y],
            'client_size_px': [width,height],
            'foreground': int(_user32().GetForegroundWindow()) == selected,
            'mouse_keyboard_enabled': os.environ.get('JACK_ENABLE_LIVE_CONTROL') == '1',
            'coordinate_system': 'x/y pixels from top-left of JACK client area'}


def capture_window_png(hwnd: int = 0) -> bytes:
    """Returns an on-screen capture; occluding windows may show in the result."""
    from PIL import ImageGrab
    selected, _ = _selected_window(hwnd)
    x, y, width, height = _client_rectangle(selected)
    from io import BytesIO
    image = ImageGrab.grab(bbox=(x, y, x + width, y + height), all_screens=True)
    data = BytesIO()
    image.save(data, 'PNG')
    return data.getvalue()


def _ensure_mutation_allowed(hwnd: int) -> tuple[int, int, int, int]:
    if os.environ.get('JACK_ENABLE_LIVE_CONTROL') != '1':
        raise PermissionError('Live control disabled. Set JACK_ENABLE_LIVE_CONTROL=1 in Codex MCP environment and restart Codex.')
    u = _user32()
    if int(u.GetForegroundWindow()) != hwnd:
        raise PermissionError('Bring the JACK editor to the foreground yourself before an action; no input sent.')
    return _client_rectangle(hwnd)


def _valid_point(x: int, y: int, width: int, height: int) -> None:
    if not (0 <= x < width and 0 <= y < height):
        raise ValueError(f'Coordinates [{x},{y}] are outside JACK client area {width}x{height}.')


def mouse_click(x: int, y: int, button: str = 'left', clicks: int = 1, hwnd: int = 0) -> dict:
    import pyautogui
    selected, _ = _selected_window(hwnd)
    ox, oy, width, height = _ensure_mutation_allowed(selected)
    _valid_point(x, y, width, height)
    if button not in {'left','right','middle'} or clicks not in {1,2}:
        raise ValueError('button must be left/right/middle and clicks must be 1 or 2.')
    pyautogui.FAILSAFE = True
    pyautogui.click(ox+x, oy+y, clicks=clicks, interval=0.12, button=button)
    return {'ok': True, 'action': 'click', 'client_xy': [x,y], 'button':button, 'clicks': clicks}


def mouse_drag(x1: int, y1: int, x2: int, y2: int, duration: float = 0.6, hwnd: int = 0) -> dict:
    import pyautogui
    selected, _ = _selected_window(hwnd)
    ox, oy, width, height = _ensure_mutation_allowed(selected)
    _valid_point(x1, y1, width, height)
    _valid_point(x2, y2, width, height)
    if not (0.2 <= duration <= 3):
        raise ValueError('Drag duration must be between 0.2 and 3 seconds.')
    pyautogui.FAILSAFE = True
    pyautogui.moveTo(ox + x1, oy + y1, duration=0.1)
    pyautogui.dragTo(ox + x2, oy + y2, duration=duration, button='left')
    return {'ok': True, 'action': 'drag', 'from_xy':[x1,y1], 'to_xy':[x2,y2]}


SAFE_SHORTCUTS = {
    'esc', 'enter', 'ctrl+s', 'ctrl+z', 'ctrl+y', 'ctrl+shift+z',
    'f2', 'f3', 'f4', 'f9', 'delete', 'backspace', 'tab',
}


def send_shortcut(keys: str, hwnd: int = 0, confirm_destructive: bool = False) -> dict:
    import pyautogui
    normalized = keys.strip().lower().replace(' ', '')
    if normalized not in SAFE_SHORTCUTS:
        raise ValueError('Shortcut is not in the explicit allowlist; inspect SAFE_SHORTCUTS in live_control.py.')
    if normalized in {'delete', 'backspace', 'f9'} and not confirm_destructive:
        raise PermissionError('Set confirm_destructive=true for delete/backspace/compile (F9).')
    selected, _ = _selected_window(hwnd)
    _ensure_mutation_allowed(selected)
    pyautogui.FAILSAFE = True
    keys_parts = normalized.split('+')
    if len(keys_parts) > 1:
        pyautogui.hotkey(*keys_parts)
    else:
        pyautogui.press(keys_parts[0])
    return {'ok': True, 'shortcut': normalized}


def type_into_focused_field(text: str, confirm_focused_field: bool, hwnd: int = 0) -> dict:
    import pyautogui
    if not confirm_focused_field:
        raise PermissionError('Explicitly confirm that an editable JACK input field has focus.')
    if not (1 <= len(text) <= 200) or any(ord(ch) < 32 or ord(ch) > 126 for ch in text):
        raise ValueError('Only printable ASCII text of 1-200 chars is supported in this prototype.')
    selected, _ = _selected_window(hwnd)
    _ensure_mutation_allowed(selected)
    pyautogui.FAILSAFE = True
    pyautogui.write(text, interval=0.015)
    return {'ok': True, 'characters_typed': len(text)}
