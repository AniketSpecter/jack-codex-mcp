[CmdletBinding()]
param([string]$EditorDirectory,[string]$ProjectRoot,[string]$GameProfile='',
      [switch]$ReplaceMcp,[switch]$SkipRegister,[switch]$BuildNative,[switch]$DesktopShortcut)
$ErrorActionPreference='Stop'
$Root=$PSScriptRoot
if(-not $EditorDirectory){$EditorDirectory=(Read-Host 'J.A.C.K. installation folder containing jack.exe').Trim('"')}
if(-not $ProjectRoot){$ProjectRoot=(Read-Host 'Your mapping project folder (original maps stay unchanged)').Trim('"')}
if(-not (Test-Path -LiteralPath (Join-Path $EditorDirectory 'jack.exe'))){throw 'jack.exe not found'}
if(-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)){throw 'Project folder does not exist'}
$Config=[ordered]@{editor_directory=(Resolve-Path -LiteralPath $EditorDirectory).Path;project_root=(Resolve-Path -LiteralPath $ProjectRoot).Path}
if($GameProfile){$Config.game_profile=$GameProfile}
$Config | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Root 'config.local.json') -Encoding UTF8
$Python=Join-Path $Root '.venv/Scripts/python.exe'
if(-not (Test-Path -LiteralPath $Python)){
    py -3 -m venv (Join-Path $Root '.venv')
    if($LASTEXITCODE -ne 0){throw 'Python 3.11+ and the Windows Python launcher are required'}
}
& $Python -c 'import sys; assert sys.version_info >= (3,11)'
if($LASTEXITCODE -ne 0){throw 'Python 3.11+ required'}
& $Python -m pip install -r (Join-Path $Root 'requirements.txt')
if($LASTEXITCODE -ne 0){throw 'Dependency installation failed'}
if($BuildNative){& (Join-Path $Root 'scripts/build-native.ps1')}
if(-not $SkipRegister -and (Get-Command codex -ErrorAction SilentlyContinue)){
    & codex mcp get jack-map --json 1>$null 2>$null
    $Exists=$LASTEXITCODE -eq 0
    if($Exists -and -not $ReplaceMcp){throw 'jack-map is already registered. Preserve it or rerun setup.ps1 -ReplaceMcp to update it.'}
    if($Exists){
        $Backup=Join-Path $Root '.local-backups';New-Item -ItemType Directory -Path $Backup -Force | Out-Null
        $CodexConfig=Join-Path $env:USERPROFILE '.codex/config.toml'
        if(Test-Path -LiteralPath $CodexConfig){Copy-Item -LiteralPath $CodexConfig -Destination (Join-Path $Backup ('config-'+(Get-Date -Format yyyyMMddHHmmss)+'.toml'))}
        & codex mcp remove jack-map
        if($LASTEXITCODE -ne 0){throw 'Could not remove previous jack-map registration'}
    }
    & codex mcp add jack-map --env ('JACK_PROJECT_ROOT='+$Config.project_root) --env 'JACK_ENABLE_LIVE_CONTROL=0' -- $Python (Join-Path $Root 'server.py')
    if($LASTEXITCODE -ne 0){throw 'MCP registration failed; use config.example.toml'}
}
if($DesktopShortcut){
    $Shell=New-Object -ComObject WScript.Shell
    $Link=$Shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'JACK Codex MCP.lnk'))
    $Link.TargetPath=Join-Path $Root '.venv/Scripts/pythonw.exe';$Link.Arguments='"'+(Join-Path $Root 'workspace.py')+'"';$Link.WorkingDirectory=$Root
    $Link.IconLocation=(Join-Path $Config.editor_directory 'jack.exe')+',0';$Link.Save()
}
Write-Host 'Configured. Open Start JACK Codex.cmd. Reconnect jack-map in Codex to discover updated tools.'
if(-not (Test-Path -LiteralPath (Join-Path $Root 'native/build/vpCodexBridgex64.dll'))){Write-Host 'Native DLL not installed yet: build with scripts/build-native.ps1 or install the matching release DLL.'}
