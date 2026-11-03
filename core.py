"""Read-only GoldSrc/J.A.C.K. map analysis helpers for an MCP server.

No editor binary patches or invasive hooks are used. Files must be under
JACK_PROJECT_ROOT; .jmf/.rmf read support depends on optional MESS.exe.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
import os
import re
import subprocess

MAX_FILE_BYTES = 128 * 1024 * 1024
SUPPORTED_MAPS = {".map", ".jmf", ".rmf"}
KEY_VALUE = re.compile(r'^\s*"((?:\\.|[^"\\])*)"\s+"((?:\\.|[^"\\])*)"\s*$')
FACE = re.compile(r'^\s*(?:\([^)]*\)\s*){3}(\S+)')
POINT = re.compile(r'\(\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s*\)')


def project_root() -> Path:
    root = Path(os.environ.get("JACK_PROJECT_ROOT", os.getcwd())).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"JACK_PROJECT_ROOT is not an existing directory: {root}")
    return root


def allowed_path(relative_path: str, extensions: set[str]) -> Path:
    root = project_root()
    candidate = (root / relative_path).expanduser().resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("The requested path is outside JACK_PROJECT_ROOT")
    if candidate.suffix.lower() not in extensions:
        raise ValueError(f"Unsupported file extension: {candidate.suffix}")
    if not candidate.is_file():
        raise FileNotFoundError(f"File not found: {relative_path}")
    if candidate.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("File is above the 128 MiB analysis limit")
    return candidate


def _strip_comment(line: str) -> str:
    """Strip // line comments outside quoted key/value strings."""
    quoted = False
    escaped = False
    for i, ch in enumerate(line):
        if ch == '"' and not escaped:
            quoted = not quoted
        if ch == '/' and i + 1 < len(line) and line[i + 1] == '/' and not quoted:
            return line[:i]
        if ch == '\\' and not escaped:
            escaped = True
        else:
            escaped = False
    return line


def parse_map_text(content: str) -> dict[str, Any]:
    """Basic Valve/Quake .map parser, not a full geometry compiler."""
    entities: list[dict[str, Any]] = []
    entity: dict[str, Any] | None = None
    depth = 0
    texture_counts: Counter[str] = Counter()
    points: list[tuple[float, float, float]] = []
    syntax_warnings: list[str] = []
    brush_count = face_count = 0

    for line_num, raw in enumerate(content.splitlines(), 1):
        line = _strip_comment(raw).strip()
        if not line:
            continue
        if line == "{":
            depth += 1
            if depth == 1:
                entity = {"index": len(entities), "line": line_num, "properties": {}, "brushes": 0}
            elif depth == 2 and entity is not None:
                brush_count += 1
                entity["brushes"] += 1
            elif depth > 2:
                syntax_warnings.append(f"Unexpected nesting depth {depth} at line {line_num}")
            continue
        if line == "}":
            if depth == 1 and entity is not None:
                entities.append(entity)
                entity = None
            depth -= 1
            if depth < 0:
                syntax_warnings.append(f"Extra closing brace at line {line_num}")
                depth = 0
            continue
        if depth == 1 and entity is not None:
            match = KEY_VALUE.fullmatch(line)
            if match:
                key, value = match.groups()
                entity["properties"][key] = value
            else:
                syntax_warnings.append(f"Unparsed entity field on line {line_num}")
        elif depth == 2:
            match = FACE.match(line)
            if match:
                face_count += 1
                texture_counts[match.group(1)] += 1
                for p in POINT.findall(line)[:3]:
                    points.append(tuple(float(v) for v in p))
    if depth:
        syntax_warnings.append(f"Unclosed brace nesting at end of map (depth {depth})")

    class_counts: Counter[str] = Counter(
        e["properties"].get("classname", "<missing>") for e in entities
    )
    bounds = None
    if points:
        bounds = {
            "min": [round(min(p[axis] for p in points), 2) for axis in range(3)],
            "max": [round(max(p[axis] for p in points), 2) for axis in range(3)],
        }
        bounds["dimensions"] = [round(b - a, 2) for a, b in zip(bounds["min"], bounds["max"])]

    return {
        "entities": entities,
        "entity_count": len(entities),
        "brush_count": brush_count,
        "face_count": face_count,
        "classes": dict(class_counts.most_common()),
        "textures": dict(texture_counts.most_common(30)),
        "bounds": bounds,
        "syntax_warnings": syntax_warnings[:100],
    }


def _read_map(path: Path) -> tuple[str, str]:
    if path.suffix.lower() == ".map":
        return path.read_text(encoding="utf-8-sig", errors="replace"), "native .map"

    mess = os.environ.get("MESS_EXE", "").strip()
    if not mess or not Path(mess).is_file():
        raise ValueError(
            "For binary JMF/RMF maps, install MESS and set MESS_EXE to its "
            "executable path; or export a .map from J.A.C.K. (File > Export Map)."
        )
    with TemporaryDirectory(prefix="jack_map_mcp_") as temp_dir:
        output = Path(temp_dir) / "analysis.map"
        command = [mess, "-convert", str(path), str(output)]
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=120, check=False
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("MESS map conversion timed out (120 seconds)") from exc
        if result.returncode != 0 or not output.is_file():
            raise RuntimeError(
                "MESS conversion failed: " + (result.stderr or result.stdout)[-700:]
            )
        return output.read_text(encoding="utf-8-sig", errors="replace"), "MESS temporary .map conversion"


def read_parsed_map(relative_path: str) -> dict[str, Any]:
    path = allowed_path(relative_path, SUPPORTED_MAPS)
    map_text, source = _read_map(path)
    parsed = parse_map_text(map_text)
    parsed["file"] = str(path.relative_to(project_root()))
    parsed["source"] = source
    return parsed


def list_maps(max_results: int = 100) -> dict[str, Any]:
    root = project_root()
    max_results = min(max(max_results, 1), 500)
    maps = sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_MAPS
    )
    return {
        "project_root": str(root),
        "total": len(maps),
        "files": [str(p.relative_to(root)) for p in maps[:max_results]],
        "truncated": len(maps) > max_results,
    }


def map_summary(relative_path: str) -> dict[str, Any]:
    parsed = read_parsed_map(relative_path)
    return {k: v for k, v in parsed.items() if k != "entities"}


def find_entities(relative_path: str, classname: str = "", key: str = "", contains: str = "", limit: int = 40) -> dict[str, Any]:
    parsed = read_parsed_map(relative_path)
    limit = min(max(limit, 1), 200)
    hits = []
    for entity in parsed["entities"]:
        props = entity["properties"]
        if classname and classname.lower() not in props.get("classname", "").lower():
            continue
        if key:
            if key not in props or (contains and contains.lower() not in props[key].lower()):
                continue
        elif contains and not any(contains.lower() in str(v).lower() for v in props.values()):
            continue
        hits.append({"index": entity["index"], "line": entity["line"], "brushes": entity["brushes"], "properties": props})
    return {"file": parsed["file"], "matched": len(hits), "results": hits[:limit], "truncated": len(hits) > limit}


def validate_map(relative_path: str) -> dict[str, Any]:
    parsed = read_parsed_map(relative_path)
    problems: list[dict[str, Any]] = [
        {"severity": "warning", "message": warning} for warning in parsed["syntax_warnings"]
    ]
    entities = parsed["entities"]
    classes = parsed["classes"]
    if classes.get("worldspawn", 0) != 1:
        problems.append({"severity": "warning", "message": "Expected one worldspawn entity."})
    if not any(c.startswith("info_player_") for c in classes):
        problems.append({"severity": "suggestion", "message": "No info_player_* spawn was found. Check the target game's spawn conventions."})
    targets = {e["properties"].get("targetname", "") for e in entities}
    for e in entities:
        target = e["properties"].get("target", "")
        if target and target not in targets:
            problems.append({"severity": "suggestion", "message": f"Entity #{e['index']} ({e['properties'].get('classname', '?')}) targets '{target}' without a matching targetname. This can be valid in custom mods."})
            if len(problems) >= 60:
                break
    return {
        "file": parsed["file"],
        "entity_count": parsed["entity_count"],
        "brush_count": parsed["brush_count"],
        "issues": problems,
        "caveat": "Heuristic checks only. This is not a compile, full FGD validator, or leak detector.",
    }


LOG_RULES = [
    (re.compile(r"\bleak(?:ed|ing)?\b", re.I), "Possible leak: inspect entity leak points and sealing world geometry in the editor."),
    (re.compile(r"invalid solid|non.planar|invalid brush", re.I), "Potential invalid brush: review vertex manipulation; try J.A.C.K.'s triangulation tool."),
    (re.compile(r"max_map_|too many|exceeded|limit exceeded|allocblock", re.I), "Engine/compiler limit reached: identify the exact limit and check the chosen GoldSrc/Xash/PrimeXT compiler build."),
    (re.compile(r"texture.*not found|could not find.*texture|missing texture", re.I), "Missing texture: check WAD paths and worldspawn wad key or game configuration."),
    (re.compile(r"\b(?:warning|error|fatal)\b", re.I), "Check the preceding and following compile-log lines for context."),
]


def diagnose_log(relative_path: str, max_issues: int = 40) -> dict[str, Any]:
    path = allowed_path(relative_path, {".log", ".txt"})
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    issues = []
    for number, line in enumerate(lines, 1):
        for pattern, advice in LOG_RULES:
            if pattern.search(line):
                issues.append({"line": number, "text": line[:500], "suggestion": advice})
                break
    max_issues = min(max(max_issues, 1), 100)
    return {"file": str(path.relative_to(project_root())), "lines": len(lines), "matches": len(issues), "issues": issues[:max_issues], "truncated": len(issues) > max_issues}


JACK_TIPS = {
    "formats": "Keep native .jmf project files for J.A.C.K. editor metadata (VisGroups/cameras). Export .map for compiling or external tooling. RMF is a possible interchange format; VMF import/export is limited.",
    "compile": "In J.A.C.K., F9 opens Run/Compile. Configure your game profile's compiler paths. Export .map manually with File > Export Map when external compile tooling needs it.",
    "large_map": "J.A.C.K. can edit large coordinate spaces, but in-game limits depend on the actual engine, BSP format and compiler. Confirm limits for your Xash/PrimeXT build before extending terrain.",
    "workflow": "Use JMF as the master file, export MAP for analysis, keep versioned backups, then test a compiled BSP inside the target engine. Do not assume UE5-style live scene manipulation.",
    "sdk": "For an eventual in-editor bridge, investigate SanyaSho/JackSDK (unofficial C++ plugin SDK); test against your precise J.A.C.K. version and use official plugin interfaces where available.",
}


def help_topic(topic: str = "workflow") -> dict[str, str]:
    topic = topic.lower().strip()
    if topic not in JACK_TIPS:
        return {"error": "Unknown topic", "available_topics": ", ".join(JACK_TIPS)}
    return {"topic": topic, "guidance": JACK_TIPS[topic]}
