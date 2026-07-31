# ============================================================
# build_gui.ps1
# Rebuilds the Oracle Memory Calculator GUI using PyInstaller
# ============================================================

Write-Host ""
Write-Host "=== Oracle Memory Calculator :: Build Script ===" -ForegroundColor Cyan
Write-Host ""

# Ensure we are running from the script's directory
Set-Location -Path $PSScriptRoot

# Optional: Activate virtual environment if present
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    . .\.venv\Scripts\Activate.ps1
}

# Clean previous builds
Write-Host "Cleaning previous build artifacts..." -ForegroundColor Yellow
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
Remove-Item -Force *.spec -ErrorAction SilentlyContinue

# Run PyInstaller
Write-Host ""
Write-Host "Running PyInstaller..." -ForegroundColor Green
Write-Host ""

pyinstaller `
  --clean `
  --onefile `
  --windowed `
  --name "Oracle Memory Calculator" `
  --icon .\icon\OracleMemoryCalc_transparent.ico `
  --add-data ".\icon\OracleMemoryCalc_transparent.ico;icon" `
  --add-data ".\icon\OracleMemoryCalc_transparent.png;icon" `
  --add-data ".\icon\header.png;icon" `
  --hidden-import PIL.Image `
  --hidden-import PIL.ImageTk `
  oracle_mem_calc_gui.py

# Check result
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Build completed successfully!" -ForegroundColor Green
    Write-Host "Output location:" -ForegroundColor Cyan
    Write-Host "  dist\Oracle Memory Calculator\" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "❌ Build failed. See output above." -ForegroundColor Red
}

Write-Host ""
Write-Host "Press any key to exit..."
[void][System.Console]::ReadKey($true)
