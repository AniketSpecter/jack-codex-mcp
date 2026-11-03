"""Authenticated local IPC client for editor-thread reads and planned edits.

IDs are session-local. Native 0.3 captures automatically on the editor thread.
"""
from __future__ import annotations
import ctypes as ct
from ctypes import wintypes as wt
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

ROOT = Path(__file__).resolve().parent
EXPECTED_EXE = "1dcd13dbc6ded7181ae47b611a11f6c08c8e2da85af14f03c4ca9bc705bfdac8"
MAX_RESPONSE = 256 * 1024
METHODS = {"capabilities", "snapshot", "plan_edits", "apply_edits"}


def _endpoint_path() -> Path:
    configured = os.environ.get("JACK_NATIVE_ENDPOINT", "").strip()
    if configured:
        return Path(configured).resolve()
    manifest = ROOT / "mapping-active.json"
    if not manifest.is_file():
        manifest = ROOT / "native/last-probe.json"
    if not manifest.is_file():
        raise RuntimeError("No editor session; open Start JACK Codex.cmd")
    return Path(json.loads(manifest.read_text())["endpoint"]).resolve()


def _load_endpoint(path: Path) -> dict:
    if path.stat().st_size > 4096:
        raise ValueError("Invalid native endpoint size")
    ep = json.loads(path.read_text(encoding="utf-8"))
    pid, sid, token = ep.get("pid"), ep.get("session_id"), ep.get("token")
    if (ep.get("protocol") != 1 or type(pid) is not int or pid <= 0
            or not isinstance(sid, str) or not re.fullmatch(r"[0-9a-f]{32}", sid)
            or not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{64}", token)
            or ep.get("exe_sha256") != EXPECTED_EXE):
        raise ValueError("Unsupported native endpoint")
    if ep.get("pipe") != rf"\\.\pipe\JACKCodex-{pid}-{sid}":
        raise ValueError("Native pipe is not a local session endpoint")
    return ep


def _decode_reply(raw: bytes, request_id: str, session: str) -> dict:
    if not raw or len(raw) > MAX_RESPONSE:
        raise ValueError("Invalid native response size")
    reply = json.loads(raw)
    if reply.get("id") != request_id or reply.get("session_id") != session:
        raise ValueError("Native request/session mismatch or rejected authentication")
    if not isinstance(reply.get("result"), dict):
        raise ValueError("Invalid native response payload")
    return reply["result"]


class _Pipe:
    def __init__(self, ep: dict):
        if os.name != "nt":
            raise RuntimeError("Native bridge requires Windows")
        self.k = ct.WinDLL("kernel32", use_last_error=True)
        k = self.k
        self.h = None
        k.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ct.c_void_p, wt.DWORD, wt.DWORD, wt.HANDLE]
        k.CreateFileW.restype = wt.HANDLE
        k.CloseHandle.argtypes = [wt.HANDLE]
        k.WaitNamedPipeW.argtypes = [wt.LPCWSTR, wt.DWORD]
        k.GetNamedPipeServerProcessId.argtypes = [wt.HANDLE, ct.POINTER(wt.ULONG)]
        k.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
        k.OpenProcess.restype = wt.HANDLE
        k.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ct.POINTER(wt.DWORD)]
        k.SetNamedPipeHandleState.argtypes = [wt.HANDLE, ct.POINTER(wt.DWORD), ct.c_void_p, ct.c_void_p]
        if not k.WaitNamedPipeW(ep["pipe"], 2000):
            raise RuntimeError("Native pipe unavailable/busy; editor may have closed")
        h = k.CreateFileW(ep["pipe"], 0xC0000000, 0, None, 3, 0x40000000, None)
        if h == ct.c_void_p(-1).value:
            raise ct.WinError(ct.get_last_error())
        self.h = h
        try:
            pid = wt.ULONG()
            if not k.GetNamedPipeServerProcessId(h, ct.byref(pid)) or pid.value != ep["pid"]:
                raise RuntimeError("Named pipe server PID mismatch")
            ph = k.OpenProcess(0x1000, False, pid.value)
            if not ph:
                raise RuntimeError("Cannot verify native editor process")
            try:
                buf = ct.create_unicode_buffer(32768); size = wt.DWORD(len(buf))
                if not k.QueryFullProcessImageNameW(ph, 0, buf, ct.byref(size)):
                    raise ct.WinError(ct.get_last_error())
                exe = Path(buf.value)
                if (exe.name.lower() != "jack.exe"
                        or hashlib.sha256(exe.read_bytes()).hexdigest() != EXPECTED_EXE
                        or not (exe.parent / "CODEX_DISPOSABLE_EDITOR_ONLY.marker").is_file()):
                    raise RuntimeError("Pipe process is not the supported disposable editor")
            finally:
                k.CloseHandle(ph)
            mode = wt.DWORD(2)  # message mode, local pipe, no remote host accepted
            if not k.SetNamedPipeHandleState(h, ct.byref(mode), None, None):
                raise ct.WinError(ct.get_last_error())
        except Exception:
            self.close(); raise

    def close(self):
        if self.h is not None:
            self.k.CloseHandle(self.h); self.h = None

    def transfer(self, data: bytes | None) -> bytes:
        class Overlapped(ct.Structure):
            _fields_ = [("internal", ct.c_size_t), ("internal_high", ct.c_size_t),
                        ("offset", wt.DWORD), ("offset_high", wt.DWORD), ("event", wt.HANDLE)]
        k = self.k
        k.CreateEventW.argtypes = [ct.c_void_p, wt.BOOL, wt.BOOL, wt.LPCWSTR]
        k.CreateEventW.restype = wt.HANDLE
        k.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
        k.GetOverlappedResult.argtypes = [wt.HANDLE, ct.POINTER(Overlapped), ct.POINTER(wt.DWORD), wt.BOOL]
        k.CancelIoEx.argtypes = [wt.HANDLE, ct.POINTER(Overlapped)]
        op = k.ReadFile if data is None else k.WriteFile
        op.argtypes = [wt.HANDLE, ct.c_void_p, wt.DWORD, ct.POINTER(wt.DWORD), ct.POINTER(Overlapped)]
        buf = ct.create_string_buffer(MAX_RESPONSE if data is None else data)
        size = MAX_RESPONSE if data is None else len(data)
        ov = Overlapped(); ov.event = k.CreateEventW(None, True, False, None)
        if not ov.event: raise ct.WinError(ct.get_last_error())
        done = wt.DWORD()
        try:
            if not op(self.h, buf, size, ct.byref(done), ct.byref(ov)):
                if ct.get_last_error() != 997: raise ct.WinError(ct.get_last_error())
                if k.WaitForSingleObject(ov.event, 4000) != 0:
                    k.CancelIoEx(self.h, ct.byref(ov))
                    k.GetOverlappedResult(self.h, ct.byref(ov), ct.byref(done), True)
                    raise TimeoutError("Native IPC timed out")
                if not k.GetOverlappedResult(self.h, ct.byref(ov), ct.byref(done), False):
                    raise ct.WinError(ct.get_last_error())
            if data is not None and done.value != len(data):
                raise RuntimeError("Partial native request")
            reply = buf.raw[:done.value]
            if data is None:
                self.transfer(b"ACK")
            return reply
        finally:
            k.CloseHandle(ov.event)


def request(method: str, params: dict | None = None) -> dict:
    if method not in METHODS:
        raise ValueError("Unsupported native method; use the plan/apply protocol")
    try:
        ep = _load_endpoint(_endpoint_path())
    except FileNotFoundError as exc:
        raise RuntimeError("Native editor not running or plugin rejected; no endpoint published") from exc
    rid = uuid.uuid4().hex
    payload = json.dumps({"id": rid, "token": ep["token"], "method": method, "params": params or {}}).encode()
    if len(payload)>8192:
        raise ValueError("Native request exceeds 8 KiB; use a smaller operation batch")
    pipe = _Pipe(ep)
    try:
        pipe.transfer(payload)
        result = _decode_reply(pipe.transfer(None), rid, ep["session_id"])
    finally:
        pipe.close()
    result["session_id"] = ep["session_id"]
    result["pid"] = ep["pid"]
    return result


def capabilities() -> dict:
    return request("capabilities")


def read_snapshot(selection_only: bool = False) -> dict:
    result = request("snapshot")
    result["refresh_required"] = not result.get("ok") or result.get("age_ms", 10001) > 10000
    result["refresh_instruction"] = "Current native 0.3 sessions capture automatically when this tool is called; reconnect an older editor session if needed."
    result["consistency"] = "Explicit snapshot; IDs/fingerprint are not durable handles or a full document revision"
    if selection_only and "document" in result:
        doc = result["document"]
        selected = doc.get("selection", {})
        result["selection"] = selected
        result["entities"] = [e for e in doc.get("entities", []) if e["editor_id"] in selected.get("entities", [])]
        result["brushes"] = [b for b in doc.get("brushes", []) if b["editor_id"] in selected.get("brushes", [])]
        del result["document"]
    return result


def plan_edits(operations: list[dict]) -> dict:
    """Preview an exact revision-bound plan; does not change map contents."""
    return request('plan_edits', {'operations':operations})


def apply_edits(plan_id: str, approval_token: str) -> dict:
    """Only call after the user authorizes the exact returned plan (or fixture tests)."""
    return request('apply_edits', {'plan_id':plan_id,'approval_token':approval_token})
