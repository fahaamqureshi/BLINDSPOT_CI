# Full live demo on the sample bus photo, with and without the Muse Spark planner.
# Run from the project folder:  .\scripts\live_demo.ps1
# The truth below is what the sample photo is known to contain: 4 people and 1 bus.
# Check it yourself: the script opens the photo first. Change -Truth if you use your own image.
param(
    [string]$ImageFile = (Join-Path $env:TEMP "blindspot_sample_bus.jpg"),
    [string]$Probes = "person,bus",
    [string]$Truth = "person=4,bus=1:high"
)

if (-not (Test-Path $ImageFile)) {
    curl.exe -L -s -f -o $ImageFile "https://ultralytics.com/images/bus.jpg"
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $ImageFile)) {
        Write-Host "Download failed. Pass your own photo: .\scripts\live_demo.ps1 -ImageFile C:\path\photo.jpg -Truth 'person=2'"
        exit 1
    }
}
Write-Host "Opening the photo so you can confirm the truth ($Truth) is right..."
Start-Process $ImageFile

Write-Host "`n=== Run 1: heuristic planner ==="
python -m blindspot_ci.cli live-run --image-file $ImageFile --probes $Probes --truth $Truth
Write-Host "`n=== Run 2: Muse Spark planner ==="
python -m blindspot_ci.cli live-run --image-file $ImageFile --probes $Probes --truth $Truth --planner muse
Write-Host "`nDone. Keep both outputs with your notes."
