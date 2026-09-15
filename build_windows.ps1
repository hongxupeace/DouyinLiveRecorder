$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") {
    throw "请在 Windows PowerShell 中执行此脚本。"
}

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "未找到 uv。请先执行：powershell -ExecutionPolicy ByPass -c `"irm https://astral.sh/uv/install.ps1 | iex`""
}

uv sync

$ffmpegCandidates = @()
$projectFfmpeg = Join-Path $projectRoot "ffmpeg.exe"
if (Test-Path $projectFfmpeg) {
    $ffmpegCandidates += Get-Item $projectFfmpeg
}

$ffmpegCommand = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
if ($ffmpegCommand) {
    $ffmpegCandidates += Get-Item $ffmpegCommand.Source
}

if ($env:ChocolateyInstall -and (Test-Path "$env:ChocolateyInstall\lib")) {
    $ffmpegCandidates += Get-ChildItem `
        "$env:ChocolateyInstall\lib" `
        -Recurse `
        -Filter ffmpeg.exe `
        -ErrorAction SilentlyContinue
}

$ffmpegFile = $ffmpegCandidates |
    Where-Object { $_.Length -gt 5MB } |
    Select-Object -First 1

if (-not $ffmpegFile) {
    throw "未找到完整的 ffmpeg.exe。请将 FFmpeg 静态版放到项目根目录，或加入 PATH。"
}

$ffmpegPath = $ffmpegFile.FullName

$arguments = @(
    "--noconfirm",
    "--clean",
    "--windowed",
    "--onedir",
    "--name", "DouyinLiveRecorderDesktop",
    "--hidden-import", "src.spider",
    "--hidden-import", "src.stream",
    "--add-data", "src/javascript;src/javascript",
    "--add-binary", "$ffmpegPath;.",
    "desktop.py"
)

uv run --with pyinstaller pyinstaller @arguments

Write-Host ""
Write-Host "构建完成：$projectRoot\dist\DouyinLiveRecorderDesktop"
Write-Host "运行 DouyinLiveRecorderDesktop.exe 即可启动。"
