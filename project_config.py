"""Portable local configuration. config.local.json is never committed."""
import json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def load():
    p=ROOT/'config.local.json'
    return json.loads(p.read_text(encoding='utf-8-sig')) if p.is_file() else {}
def paths():
    c=load()
    project=os.environ.get('JACK_PROJECT_ROOT') or c.get('project_root')
    editor=os.environ.get('JACK_EDITOR_DIR') or c.get('editor_directory')
    if not project or not editor:raise ValueError('Run setup.ps1 or create config.local.json first. See docs/INSTALL.md.')
    project=Path(project).expanduser().resolve();editor=Path(editor).expanduser().resolve()
    if not project.is_dir() or not (editor/'jack.exe').is_file():raise ValueError('Configured project/editor path does not exist')
    workspace=Path(c.get('workspace_directory') or project/'JACKCodexWorkspace').expanduser().resolve()
    return project,editor,workspace
