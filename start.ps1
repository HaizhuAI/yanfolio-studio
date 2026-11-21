param([int]$Port = 8769)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$venvPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (!(Test-Path $venvPython)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Unable to create Python virtual environment.' }
}
$dependencyStamp = Join-Path $PSScriptRoot '.venv/yanfolio-requirements.sha256'
$requirementsHash = (Get-FileHash -Algorithm SHA256 requirements.txt).Hash
if (!(Test-Path $dependencyStamp) -or (Get-Content $dependencyStamp -Raw).Trim() -ne $requirementsHash) {
    & $venvPython -m pip install --disable-pip-version-check -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Unable to install dependencies.' }
    Set-Content -LiteralPath $dependencyStamp -Value $requirementsHash
}
& $venvPython scripts/serve_local.py --port $Port
exit $LASTEXITCODE
