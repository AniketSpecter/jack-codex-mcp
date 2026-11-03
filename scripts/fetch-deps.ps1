$ErrorActionPreference='Stop'
$Root=Split-Path $PSScriptRoot -Parent
$Sdk=Join-Path $Root 'native/vendor/JackSDK/sdk'
$SdkCommit='b7141e36e785b15ee658fbb0a3b34dee5b1e3dfe'
if(-not (Test-Path -LiteralPath $Sdk)){
    New-Item -ItemType Directory -Path (Split-Path $Sdk) -Force | Out-Null
    git clone --no-checkout https://github.com/SanyaSho/JackSDK_SDK.git $Sdk
    if($LASTEXITCODE -ne 0){throw 'SDK download failed'}
    git -C $Sdk checkout --detach $SdkCommit
    if($LASTEXITCODE -ne 0){throw 'SDK checkout failed'}
}
$Actual=(& git -C $Sdk rev-parse HEAD).Trim()
if($Actual -ne $SdkCommit){throw 'SDK revision mismatch; use a clean pinned dependency checkout'}
git -C $Sdk diff --exit-code --quiet
if($LASTEXITCODE -ne 0){throw 'SDK contains local changes; review before building'}
$Json=Join-Path $Root 'native/vendor/json'
New-Item -ItemType Directory -Path $Json -Force | Out-Null
$Header=Join-Path $Json 'json.hpp'
if(-not (Test-Path -LiteralPath $Header)){
    Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/nlohmann/json/v3.12.0/single_include/nlohmann/json.hpp' -OutFile $Header
}
if((Get-FileHash -LiteralPath $Header -Algorithm SHA256).Hash.ToLower() -ne 'aaf127c04cb31c406e5b04a63f1ae89369fccde6d8fa7cdda1ed4f32dfc5de63'){
    throw 'JSON header checksum mismatch'
}
if(-not (Test-Path -LiteralPath (Join-Path $Json 'LICENSE.MIT'))){
    Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/nlohmann/json/v3.12.0/LICENSE.MIT' -OutFile (Join-Path $Json 'LICENSE.MIT')
}
Write-Host 'Pinned SDK and JSON dependencies verified.'
