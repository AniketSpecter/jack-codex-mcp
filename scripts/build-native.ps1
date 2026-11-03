param([string]$CMake='')
$ErrorActionPreference='Stop'
$Root=Split-Path $PSScriptRoot -Parent
& (Join-Path $PSScriptRoot 'fetch-deps.ps1')
if(-not $CMake){
    $Found=Get-Command cmake -ErrorAction SilentlyContinue
    if($Found){$CMake=$Found.Source}else{
        $VsWhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
        if(Test-Path -LiteralPath $VsWhere){
            $Studio=(& $VsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath)
            if($Studio){$CMake=Join-Path $Studio 'Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'}
        }
    }
}
if(-not $CMake -or -not (Test-Path -LiteralPath $CMake)){throw 'Install CMake and Visual Studio C++ Build Tools (x64), or pass -CMake FULL_PATH'}
$Build=Join-Path $Root 'native/build-cmake'
& $CMake -S (Join-Path $Root 'native') -B $Build -A x64
if($LASTEXITCODE -ne 0){throw 'CMake configure failed'}
& $CMake --build $Build --config Release --parallel 2
if($LASTEXITCODE -ne 0){throw 'Native build failed'}
$Contract=Join-Path $Build 'Release/capture_contract.exe'
& $Contract
if($LASTEXITCODE -ne 0){throw 'Native contract test failed'}
$Output=Join-Path $Root 'native/build'
New-Item -ItemType Directory -Path $Output -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $Build 'Release/vpCodexBridgex64.dll') -Destination (Join-Path $Output 'vpCodexBridgex64.dll')
Write-Host ('Built: '+(Join-Path $Output 'vpCodexBridgex64.dll'))
