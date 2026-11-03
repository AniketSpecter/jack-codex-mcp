"""Package tracked source, rebuilt DLL and matching third-party source only."""
import hashlib,json,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    files={p:ROOT/p for p in tracked if p}
    dll=ROOT/'native/build/vpCodexBridgex64.dll'
    if not dll.is_file():raise SystemExit('Build native plugin first')
    files['native/build/vpCodexBridgex64.dll']=dll
    sdk=ROOT/'native/vendor/JackSDK/sdk'
    for name in subprocess.check_output(['git','ls-files','-z'],cwd=sdk).decode().split('\0'):
        if name:files['native/vendor/JackSDK/sdk/'+name]=sdk/name
    for name in ('json.hpp','LICENSE.MIT'):
        files['native/vendor/json/'+name]=ROOT/'native/vendor/json'/name
    forbidden=('config.local.json','mapping-active.json','endpoint.json')
    if any(Path(n).name in forbidden or Path(n).suffix.lower() in {'.jmf','.bsp','.wad','.pak','.exe'} for n in files):
        raise SystemExit('Refusing private/proprietary build input')
    out=ROOT/'dist';out.mkdir(exist_ok=True)
    artifact=out/'jack-codex-mcp-0.3.0-alpha.1-windows-x64.zip'
    with zipfile.ZipFile(artifact,'w',zipfile.ZIP_DEFLATED) as z:
        for name,p in sorted(files.items()):z.write(p,'jack-codex-mcp/'+name)
        z.writestr('jack-codex-mcp/BUILD.json',json.dumps({'version':'0.3.0-alpha.1',
            'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
            'dll_sha256':hashlib.sha256(dll.read_bytes()).hexdigest(),
            'editor_included':False,'experimental':True,'save_as_required':True},indent=2))
    checksum=out/'SHA256SUMS.txt';checksum.write_text(hashlib.sha256(artifact.read_bytes()).hexdigest()+'  '+artifact.name+'\n')
    print(artifact);print(checksum)

if __name__=='__main__':main()
