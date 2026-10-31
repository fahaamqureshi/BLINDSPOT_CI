# Live check of Muse Wonder, Muse Image and Muse Voice Transcribe. A few cents at most.
# Makes a spoken test WAV with Windows text-to-speech in your temp folder (never in the project).
# Run from the project folder:  .\scripts\live_models_check.ps1
if (-not (Test-Path ".env")) { Write-Host "No .env file."; exit 2 }
$env:LIVE_API_ENABLED = "true"
$wav = Join-Path $env:TEMP "blindspot_note.wav"
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$synth.SetOutputToWaveFile($wav, $format)
$synth.Speak("The red tag is visible but the model box is too low. Please check the low light photos next.")
$synth.Dispose()
python -m blindspot_ci.cli smoke-models --wav $wav
Write-Host "`nsmoke-models exit code: $LASTEXITCODE (0 means all three answered)"
