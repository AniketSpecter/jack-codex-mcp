"""Launch native MCP sessions on persistent, backed-up working copies."""
import argparse,configparser,hashlib,json,os,re,shutil,subprocess,uuid
from datetime import datetime,timezone
from pathlib import Path
from project_config import ROOT,paths,load
from native_bridge import EXPECTED_EXE

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stamp():return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]
def write_json(p,v):
    p=Path(p);t=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp');t.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8');os.replace(t,p)
def initialize():
    _,_,w=paths()
    for sub in ('maps','backups','sessions','exports'):(w/sub).mkdir(parents=True,exist_ok=True)
    return w
def checkpoint(p):
    p=Path(p).resolve();w=initialize()
    if not p.is_relative_to((w/'maps').resolve()) or p.suffix.lower() not in {'.map','.jmf','.rmf'}:raise ValueError('Choose a saved working map inside workspace/maps')
    h=sha(p);d=w/'backups'/stamp();d.mkdir();shutil.copy2(p,d/p.name)
    if sha(d/p.name)!=h or sha(p)!=h:raise RuntimeError('File changed during checkpoint; save and retry')
    write_json(d/'receipt.json',{'source':str(p),'backup':str(d/p.name),'sha256':h,'scope':'saved bytes, not unsaved editor state'})
    return d/p.name
def import_copy(p):
    p=Path(p).resolve();w=initialize()
    if not p.is_file() or p.suffix.lower() not in {'.map','.jmf','.rmf'}:raise ValueError('Choose a MAP/JMF/RMF')
    if p.is_relative_to((w/'maps').resolve()):return p
    d=w/'maps'/(re.sub(r'[^A-Za-z0-9_-]','_',p.stem)+'-'+stamp());d.mkdir()
    # A unique working filename also makes active-document title checks stronger.
    dest=d/('WORKING_'+uuid.uuid4().hex[:8]+'_'+p.name);h=sha(p);shutil.copy2(p,dest)
    if sha(dest)!=h or sha(p)!=h:raise RuntimeError('Source changed during import')
    write_json(d/'source.json',{'original':str(p),'sha256':h,'working_copy':str(dest)})
    checkpoint(dest);return dest
def new_map(name):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,39}',name):raise ValueError('Use a map name starting with a letter, up to 40 letters/numbers/_/-')
    w=initialize();d=w/'maps'/name;d.mkdir(exist_ok=False)
    from scripts.make_fixture import room_text
    p=d/(name+'.map');p.write_text(room_text(load().get('texture','AAATRIGGER'),load().get('wad','')),encoding='ascii');checkpoint(p);return p
def stage(p,native=True):
    project,editor,w=paths();p=Path(p).resolve();initialize()
    if not p.is_relative_to((w/'maps').resolve()):raise ValueError('Import the map first; native sessions never bind an original source')
    if sha(editor/'jack.exe')!=EXPECTED_EXE:raise ValueError('Unsupported editor fingerprint. See docs/COMPATIBILITY.md; do not bypass the check.')
    dll=ROOT/'native/build/vpCodexBridgex64.dll'
    if not dll.is_file():raise ValueError('Build the native plugin or install the published native DLL first. See docs/INSTALL.md.')
    checkpoint(p);session=w/'sessions'/stamp();copy=session/'editor';session.mkdir();shutil.copytree(editor,copy)
    (copy/'CODEX_DISPOSABLE_EDITOR_ONLY.marker').write_text('Isolated working-copy editor; never original source maps.\n')
    shutil.copy2(dll,copy/'plugins'/dll.name)
    cp=configparser.ConfigParser(interpolation=None);cp.optionxform=str;cp.read(copy/'VDKGameCfg.ini',encoding='utf-8-sig')
    sections=[s for s in cp.sections() if s.startswith('Config')]
    requested=load().get('game_profile')
    selected=requested or next((s for s in sections if cp[s].get('Enabled','false').lower()=='true'),None)
    if selected not in sections:raise ValueError('Configure a working game profile in your original JACK first, or set game_profile in config.local.json.')
    for s in sections:cp[s]['Enabled']='true' if s==selected else 'false'
    cp[selected]['Title']=cp[selected].get('Title','Game')+' / Codex working copies'
    cp[selected]['MapSourceFileDirectory']=(w/'exports').as_posix()
    cp[selected]['GameExecutable']='';cp[selected]['GameCommandLine']=''
    with (copy/'VDKGameCfg.ini').open('w',encoding='utf-8') as f:cp.write(f,space_around_delimiters=False)
    (copy/'VDKRunCfg.ini').write_text('[Config0]\nTitle=Export MAP for separate compilation\nCommands\\size=0\n')
    write_json(copy/'codex-edit-session.json',{'enabled':bool(native),'test_fixture':False,'working_file':str(p)})
    m={'mode':'native-working-copy' if native else 'read-only-working-copy','map':str(p),'editor':str(copy/'jack.exe'),
       'endpoint':str(copy/'codex-bridge/endpoint.json'),'workspace':str(w),'root':str(session),'native_mutations':bool(native),
       'map_sha256_at_launch':sha(p),'plugin_sha256':sha(dll)}
    write_json(session/'manifest.json',m);return m
def launch(p,native=True):
    m=stage(p,native);proc=subprocess.Popen([m['editor'],m['map']],cwd=str(Path(m['editor']).parent))
    m['pid']=proc.pid;write_json(ROOT/'mapping-active.json',m);write_json(Path(m['workspace'])/'ACTIVE_SESSION.json',m);return m
def gui():
    import tkinter as tk
    from tkinter import filedialog,messagebox,simpledialog
    app=tk.Tk();app.title('JACK Codex MCP');app.geometry('640x485');app.configure(bg='#081b22')
    tk.Label(app,text='J.A.C.K. + CODEX / NATIVE EDITOR',font=('Segoe UI',17,'bold'),fg='#44e5e7',bg='#081b22').pack(pady=(22,12))
    tk.Label(app,text='Automatic native reads and approved brush/entity edits\nWorking copies, checkpoints and editor Undo transactions',fg='#cbe0e7',bg='#081b22').pack(pady=(0,14))
    native=tk.BooleanVar(value=False)
    tk.Checkbutton(app,text='Experimental native edits (Save As required after edits)',variable=native,fg='white',bg='#081b22',selectcolor='#183d47').pack(pady=4)
    def open_map(action):
        try:
            p=action()
            if not p:return
            if native.get() and not messagebox.askokcancel('Experimental editing / working copies only',
                'JACK may not show an unsaved-change star or prompt after native edits.\nUse File > Save As to save JMF after each accepted batch, then verify by reopening.\nRecovery JSON does not preserve all JMF metadata. Continue on this backed-up COPY?'):return
            m=launch(p,native.get())
            messagebox.showinfo('Editor started','Working file:\n'+m['map']+'\n\nMaximize this document inside JACK. Reconnect MCP after installing new tools. Ask Codex to read or preview an edit; no capture menu click is needed. Native edits: use File > Save As; do not rely on the unsaved-change indicator.')
        except Exception as e:messagebox.showerror('JACK Codex MCP',str(e))
    def choose():
        n=filedialog.askopenfilename(title='Import a source COPY or open a saved working map',initialdir=str(initialize()/'maps'),filetypes=[('JACK maps','*.jmf *.rmf *.map')])
        return import_copy(n) if n else None
    def new():
        n=simpledialog.askstring('New map','Name (letters/numbers/_/-):');return new_map(n) if n else None
    def resume():
        a=ROOT/'mapping-active.json'
        if not a.is_file():return choose()
        if not messagebox.askokcancel('Continue saved map','If an older editor is open, save its work before continuing. This opens the last SAVED file in a new session.'):return
        return Path(json.loads(a.read_text())['map'])
    def backup():
        n=filedialog.askopenfilename(title='Select SAVED working map',initialdir=str(initialize()/'maps'))
        if n:
            try:messagebox.showinfo('Checkpoint',str(checkpoint(n)))
            except Exception as e:messagebox.showerror('Checkpoint',str(e))
    for label,action in [('CONTINUE LAST SAVED MAP',lambda:open_map(resume)),('OPEN / IMPORT MAP COPY',lambda:open_map(choose)),
        ('CREATE NEW MAP',lambda:open_map(new)),('CHECKPOINT SAVED WORK',backup),('OPEN WORKSPACE',lambda:os.startfile(initialize())),
        ('READ TUTORIAL',lambda:os.startfile(ROOT/'docs/TUTORIAL.md'))]:
        tk.Button(app,text=label,command=action,width=54,bg='#153944',fg='white',relief='flat').pack(pady=5,ipady=5)
    app.mainloop()
def main():
    a=argparse.ArgumentParser();g=a.add_mutually_exclusive_group();g.add_argument('--map');g.add_argument('--new');g.add_argument('--checkpoint');a.add_argument('--read-only',action='store_true');a.add_argument('--enable-experimental-edits',action='store_true',help='Accept unreliable host save prompts; use Save As after every edit');a.add_argument('--prepare-only',action='store_true');args=a.parse_args();initialize()
    if args.checkpoint:print(checkpoint(args.checkpoint));return
    if not(args.map or args.new):return gui()
    p=new_map(args.new) if args.new else import_copy(args.map)
    enabled=args.enable_experimental_edits and not args.read_only
    print(json.dumps(stage(p,enabled) if args.prepare_only else launch(p,enabled),indent=2))
if __name__=='__main__':main()
