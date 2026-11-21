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
$ownedModel = $null
if (!$env:YANFOLIO_AI_BASE_URL) {
    $weights = Join-Path $PSScriptRoot '.local/qwen2.5-1.5b-instruct-q4_k_m.gguf'
    $runtimeDir = Join-Path $PSScriptRoot '.local/llama'
    if ((Test-Path $weights) -and (Test-Path $runtimeDir)) {
        $serverPath = Get-ChildItem -LiteralPath $runtimeDir -Filter llama-server.exe -Recurse | Select-Object -First 1
        if (!$serverPath) { throw 'Local model runtime is incomplete.' }
        $apiRoot = 'http://127.0.0.1:18769'
        $ready = $false
        try {
            $models = Invoke-RestMethod ($apiRoot + '/v1/models') -TimeoutSec 3
            $ready = 'Yanfolio-Qwen2.5-1.5B' -in $models.data.id
            if (!$ready) { throw 'Unexpected model name.' }
        } catch {
            $listener = [Net.Sockets.TcpClient]::new()
            try { $listener.Connect('127.0.0.1',18769); $used = $true } catch { $used = $false } finally { $listener.Dispose() }
            if ($used) { throw 'Port 18769 is occupied by another model service.' }
        }
        if (!$ready) {
            $modelArgs = @('-m',('"' + $weights + '"'),'--host','127.0.0.1','--port','18769','--alias','Yanfolio-Qwen2.5-1.5B','--ctx-size','8192','--parallel','1','--threads','4','--n-gpu-layers','0')
            $ownedModel = Start-Process -FilePath $serverPath.FullName -ArgumentList $modelArgs -WindowStyle Hidden -PassThru
            for ($attempt = 0; $attempt -lt 60; $attempt++) {
                try { $health = Invoke-RestMethod ($apiRoot + '/health') -TimeoutSec 2; if ($health.status -eq 'ok') { $ready = $true; break } } catch {}
                if ($ownedModel.HasExited) { throw 'Local model process stopped during startup.' }
                Start-Sleep -Milliseconds 800
            }
            if (!$ready) { $ownedModel.Kill(); throw 'Local model did not become ready.' }
        }
        $env:YANFOLIO_AI_BASE_URL = $apiRoot + '/v1'
        $env:YANFOLIO_AI_MODEL = 'Yanfolio-Qwen2.5-1.5B'
    }
}
try {
    & $venvPython -m uvicorn app.main:app --host 127.0.0.1 --port $Port
} finally {
    if ($ownedModel -and !$ownedModel.HasExited) { $ownedModel.Kill() }
}

