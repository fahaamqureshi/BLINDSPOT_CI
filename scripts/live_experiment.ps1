# Real experiment: Muse Spark picks tests with function calling, SAM 3.1 runs them, Python scores them.
# Needs MODEL_API_KEY in .env. Spends a few cents. Run from the project folder:
#   .\scripts\live_experiment.ps1                       (synthetic drawings: a plumbing test only)
#   .\scripts\live_experiment.ps1 -Dataset real         (your labeled photos: the real evidence)
param(
    [ValidateSet("synthetic", "real", "open", "hard", "video", "coco", "generated", "corrupted")][string]$Dataset = "synthetic",
    [int]$Steps = 5
)

$env:BLINDSPOT_PROVIDER = "meta"
$env:LIVE_API_ENABLED = "true"
$env:BLINDSPOT_DATASET = $Dataset
if ($Dataset -eq "synthetic") {
    Write-Host "Synthetic drawings are for checking the plumbing. They are NOT evidence about SAM."
} elseif ($Dataset -eq "generated") {
    Write-Host "Generated variants (Muse Image, boxes inherited) are stress tests, NOT real photos."
}
python -m blindspot_ci.cli experiment --steps $Steps --planner muse
Write-Host "`nDone. Open the report with: python -m blindspot_ci.cli serve   then press Run."
