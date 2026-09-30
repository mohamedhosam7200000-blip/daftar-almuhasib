# Khabeer offline launcher: checks Ollama and Python, picks a model that fits
# this computer's memory, downloads it once, then starts the local app.
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
# The khabeer package sits next to this script (release zip) or one level up (repository).
$root = $PSScriptRoot
if (-not (Test-Path (Join-Path $root "khabeer"))) { $root = Split-Path $PSScriptRoot -Parent }
Set-Location -LiteralPath $root

function Say($en, $ar) { Write-Host "$en`n  $ar`n" }
function Fail($en, $ar, $url) {
    Write-Host ""
    Say $en $ar
    if ($url) { Start-Process $url }
    Read-Host "Press Enter to close"
    exit 1
}

# 1. Ollama (runs the model)
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Fail "Ollama is not installed. Install it from the page that just opened, then run Khabeer again." `
         "برنامج Ollama غير مثبّت. ثبّته من الصفحة التي فُتحت ثم شغّل خبير مرّة أخرى." `
         "https://ollama.com/download/windows"
}

# 2. Python (runs the app)
$python = $null
foreach ($cmd in @("py", "python")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { continue }
    $pre = @()
    if ($cmd -eq "py") { $pre = @("-3") }
    # The Microsoft Store "python" stub exists even when Python is not installed.
    try { $ok = & $cmd @pre -c "import sys; print(sys.version_info >= (3, 9))" 2>$null } catch { $ok = $null }
    if ($ok -eq "True") { $python = @($cmd) + $pre; break }
}
if (-not $python) {
    Fail "Python 3.9+ is not installed. Install it (tick 'Add python.exe to PATH'), then run Khabeer again." `
         "بايثون 3.9 أو أحدث غير مثبّت. ثبّته (وفعّل خيار Add python.exe to PATH) ثم شغّل خبير مرّة أخرى." `
         "https://www.python.org/downloads/windows/"
}

# 3. Model: bigger is smarter but needs more memory.
# To force a model, put its name in model.txt next to this script (e.g. qwen3:4b).
$model = $env:KHABEER_LOCAL_MODEL
$modelFile = Join-Path $PSScriptRoot "model.txt"
if (-not $model -and (Test-Path $modelFile)) { $model = (Get-Content $modelFile -TotalCount 1).Trim() }
if (-not $model) {
    $ramGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
    if ($ramGB -ge 30) { $model = "qwen3:14b" }
    elseif ($ramGB -ge 15) { $model = "qwen3:8b" }
    else { $model = "qwen3:4b" }
    Say "Memory: $ramGB GB -> model $model" "الذاكرة: $ramGB جيجا ← النموذج $model"
}
$env:KHABEER_LOCAL_MODEL = $model

# Make sure the Ollama service is up (the installer usually starts it).
try { Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3 | Out-Null }
catch {
    Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 4
}

# 4. Download the model once (several GB; later runs skip this).
$have = (& ollama list) -join "`n"
if ($have -notmatch [regex]::Escape($model)) {
    Say "Downloading $model (first time only, a few GB)..." "جارٍ تنزيل النموذج $model (أوّل مرّة فقط، عدّة جيجابايت)..."
    & ollama pull $model
    if ($LASTEXITCODE -ne 0) {
        Fail "Model download failed. Check the internet connection and try again." `
             "فشل تنزيل النموذج. تحقّق من الإنترنت وأعد المحاولة." $null
    }
}

# 5. Start the app (opens the browser). Files are saved to Documents\Khabeer.
$env:KHABEER_OUTPUT_DIR = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "Khabeer"
Say "Starting Khabeer... keep this window open while you use it." "جارٍ تشغيل خبير... أبقِ هذه النافذة مفتوحة أثناء الاستخدام."
$pyExe = $python[0]
$pyArgs = @($python | Select-Object -Skip 1)
& $pyExe @pyArgs -m khabeer.local.server
if ($LASTEXITCODE -ne 0) { Read-Host "Press Enter to close" }
