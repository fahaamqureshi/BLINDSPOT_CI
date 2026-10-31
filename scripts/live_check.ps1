# Live connectivity check: one Muse Spark call and one SAM 3.1 call. Prints summaries only, never the key.
# Run from the project folder:  .\scripts\live_check.ps1
# Optional:                     .\scripts\live_check.ps1 -ImageFile C:\path\to\photo.jpg
param([string]$ImageFile = "", [string]$Prompt = "person")

if (-not (Test-Path ".env")) {
    Write-Host "No .env file. Run: Copy-Item .env.example .env, then paste your key on the MODEL_API_KEY line."
    exit 2
}
python -m pip install -e ".[live]" -q 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "Install failed"; exit 1 }

Write-Host "`n[1/3] Muse Spark text call (expects READY)"
python -m blindspot_ci.cli smoke-meta
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nText call failed. Diagnosing:"
    python -m blindspot_ci.cli diagnose
    exit 1
}

if ($ImageFile -eq "") {
    # Saved outside the project so the sample never ends up in the submission ZIP.
    $ImageFile = Join-Path $env:TEMP "blindspot_sample_bus.jpg"
    if (-not (Test-Path $ImageFile)) {
        # curl.exe follows redirects; Windows PowerShell 5.1 Invoke-WebRequest does not follow 308.
        curl.exe -L -s -f -o $ImageFile "https://ultralytics.com/images/bus.jpg"
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $ImageFile)) {
            Write-Host "Sample download failed. Pass your own photo with -ImageFile."
            exit 1
        }
    }
}
Write-Host "`n[2/3] Muse Spark function calling (picks one test by tool call)"
python -m blindspot_ci.cli smoke-tools
if ($LASTEXITCODE -ne 0) { Write-Host "Tool calling failed. Copy this output into a bug report." }

Write-Host "`n[3/3] SAM 3.1 call (prompt: $Prompt)"
python -m blindspot_ci.cli smoke-sam --image-file $ImageFile --prompt $Prompt
Write-Host "`nsmoke-sam exit code: $LASTEXITCODE (0 means the output parsed cleanly)"
