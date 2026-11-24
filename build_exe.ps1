# Build release\MacroHub.exe (single file, no console) and release\MacroHub.zip.
# Usage (from the project folder): powershell -ExecutionPolicy Bypass -File build_exe.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .build-venv\Scripts\python.exe)) {
    python -m venv .build-venv
    .\.build-venv\Scripts\python.exe -m pip install --quiet pyinstaller
}

.\.build-venv\Scripts\pyinstaller.exe --noconfirm --clean --onefile --windowed `
    --name MacroHub `
    --add-data "$PSScriptRoot\data\stratagems.json;data" `
    --distpath build\dist --workpath build\work --specpath build `
    "$PSScriptRoot\MacroHub.pyw"

New-Item -ItemType Directory -Force release | Out-Null
Copy-Item build\dist\MacroHub.exe release\MacroHub.exe -Force
Copy-Item README_FRIEND.txt release\README.txt -Force
Compress-Archive -Path release\MacroHub.exe, release\README.txt -DestinationPath release\MacroHub.zip -Force
Get-Item release\MacroHub.exe, release\MacroHub.zip | Select-Object Name, Length

