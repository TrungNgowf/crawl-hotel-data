# Mo Hotel Price Tool: tu cap nhat ban moi (neu co) roi chay app.
param([switch]$UpdateOnly)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Root = Join-Path $HOME ".hotel-price-tool"
$Port = if ($env:HOTEL_PRICE_PORT) { [int]$env:HOTEL_PRICE_PORT } else { 8765 }
$Repo = (Get-Content "$Root\repo.txt" -Raw).Trim()
$Branch = if (Test-Path "$Root\branch.txt") { (Get-Content "$Root\branch.txt" -Raw).Trim() } else { "main" }
$RawBase = if (Test-Path "$Root\raw_base.txt") { (Get-Content "$Root\raw_base.txt" -Raw).Trim() } else { "https://raw.githubusercontent.com/$Repo/$Branch" }
$ArchiveUrl = if (Test-Path "$Root\archive_url.txt") { (Get-Content "$Root\archive_url.txt" -Raw).Trim() } else { "https://codeload.github.com/$Repo/zip/refs/heads/$Branch" }
$env:Path = "$HOME\.local\bin;$env:Path"
$env:UV_PROJECT_ENVIRONMENT = "$Root\venv"
$env:PYTHONIOENCODING = "utf-8"

# Tool dang mo roi -> chi mo lai giao dien (khong cap nhat khi file dang duoc dung).
if (-not $UpdateOnly) { try {
    Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/" -TimeoutSec 2 | Out-Null
    Write-Host "Tool dang chay, mo giao dien..."
    Start-Process "http://127.0.0.1:$Port"
    exit 0
} catch { } }

function Update-App {
    $AppDir = "$Root\app"
    $LocalV = if (Test-Path "$AppDir\VERSION") { (Get-Content "$AppDir\VERSION" -Raw).Trim() } else { "none" }
    try {
        $RemoteV = (Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/VERSION" -TimeoutSec 8).Content.Trim()
    } catch {
        if (Test-Path $AppDir) { Write-Host "Khong kiem tra duoc ban moi (mat mang?) - dung ban hien co."; return }
        Write-Host "Loi: khong tai duoc tool. Kiem tra mang roi thu lai."; exit 1
    }
    if ($RemoteV -eq $LocalV) { return }
    Write-Host "==> Cap nhat $LocalV -> $RemoteV ..."
    $Tmp = Join-Path ([IO.Path]::GetTempPath()) ("hotel-price-" + [guid]::NewGuid())
    New-Item -ItemType Directory -Path $Tmp | Out-Null
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $ArchiveUrl -OutFile "$Tmp\app.zip"
        Expand-Archive -Path "$Tmp\app.zip" -DestinationPath "$Tmp\x" -Force
    } catch {
        Write-Host "Tai ban moi that bai - dung ban hien co."
        Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue
        if (Test-Path $AppDir) { return } else { exit 1 }
    }
    $Src = Get-ChildItem "$Tmp\x" -Directory | Select-Object -First 1
    if (Test-Path "$Root\app.old") { Remove-Item -Recurse -Force "$Root\app.old" }
    if (Test-Path $AppDir) { Rename-Item $AppDir "app.old" }
    Move-Item $Src.FullName $AppDir
    Remove-Item -Recurse -Force "$Root\app.old", $Tmp -ErrorAction SilentlyContinue
    if (Test-Path "$AppDir\installer\launcher.ps1") { Copy-Item "$AppDir\installer\launcher.ps1" "$Root\launcher.ps1" -Force }
    Push-Location $AppDir
    & uv sync --frozen --no-dev --quiet
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -ne 0) { Write-Host "Loi cai thu vien."; exit 1 }
    Write-Host "==> Da cap nhat len $RemoteV"
}

Update-App
if ($UpdateOnly) { exit 0 }

Set-Location "$Root\app"
& uv run --frozen --no-dev hotel-price --port $Port
