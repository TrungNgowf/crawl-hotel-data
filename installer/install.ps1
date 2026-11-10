# Install Hotel Price Tool on Windows.
#   powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/<user>/<repo>/main/installer/install.ps1 | iex"
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# >>> Doi dong nay thanh <github-user>/<repo> cua ban truoc khi day len GitHub <<<
$Repo = if ($env:HOTEL_PRICE_REPO) { $env:HOTEL_PRICE_REPO } else { "TrungNgowf/crawl-hotel-data" }
$Branch = if ($env:HOTEL_PRICE_BRANCH) { $env:HOTEL_PRICE_BRANCH } else { "main" }
$RawBase = if ($env:HOTEL_PRICE_RAW_BASE) { $env:HOTEL_PRICE_RAW_BASE } else { "https://raw.githubusercontent.com/$Repo/$Branch" }

$Root = Join-Path $HOME ".hotel-price-tool"
Write-Host "==> Cai Hotel Price Tool vao $Root"
New-Item -ItemType Directory -Force -Path $Root | Out-Null
Set-Content -Path "$Root\repo.txt" -Value $Repo
Set-Content -Path "$Root\branch.txt" -Value $Branch
if ($env:HOTEL_PRICE_RAW_BASE) { Set-Content -Path "$Root\raw_base.txt" -Value $env:HOTEL_PRICE_RAW_BASE }
if ($env:HOTEL_PRICE_ARCHIVE_URL) { Set-Content -Path "$Root\archive_url.txt" -Value $env:HOTEL_PRICE_ARCHIVE_URL }

# 1. uv
$env:Path = "$HOME\.local\bin;$env:Path"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "==> Cai uv..."
    powershell -NoProfile -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$HOME\.local\bin;$env:Path"
}

# 2. Launcher + tai code lan dau + cai thu vien
Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/installer/launcher.ps1" -OutFile "$Root\launcher.ps1"
& powershell -NoProfile -ExecutionPolicy Bypass -File "$Root\launcher.ps1" -UpdateOnly
if ($LASTEXITCODE -ne 0) { throw "Cai dat that bai." }

# 3. Shortcut tren Desktop
$Desktop = [Environment]::GetFolderPath("Desktop")
$Shell = New-Object -ComObject WScript.Shell
$Lnk = $Shell.CreateShortcut((Join-Path $Desktop "Hotel Price Tool.lnk"))
$Lnk.TargetPath = "powershell.exe"
$Lnk.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$Root\launcher.ps1`""
$Lnk.WorkingDirectory = $Root
$Lnk.IconLocation = "$env:SystemRoot\System32\imageres.dll,186"
$Lnk.Save()

Write-Host ""
Write-Host "Xong! Bam dup 'Hotel Price Tool' tren Desktop de mo tool."
