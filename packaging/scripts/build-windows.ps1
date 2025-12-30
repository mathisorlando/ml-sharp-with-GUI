Param(
  [string]$Python = "python",
  [string]$VenvDir = ""
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not $VenvDir) {
  $Version = & $Python -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"
  $VenvDir = Join-Path $Root ".venv-packaging-py$Version"
}

$Venv = $VenvDir

if (-not (Test-Path $Venv)) {
  & $Python -m venv $Venv
}

$Py = Join-Path $Venv "Scripts\python.exe"
$PyInstaller = Join-Path $Venv "Scripts\pyinstaller.exe"

& $Py -m pip install --upgrade pip
& $Py -m pip install -r (Join-Path $Root "requirements.txt") pyinstaller

Push-Location $Root
& $PyInstaller --clean --noconfirm (Join-Path $Root "packaging\pyinstaller\sharp-studio.spec")
Pop-Location

Write-Host "Output: $(Join-Path $Root "dist\SHARP Studio")"
