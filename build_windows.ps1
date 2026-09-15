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

$ffmpegPath = Join-Path $projectRoot "ffmpeg.exe"
if (-not (Test-Path $ffmpegPath)) {
    $ffmpegCommand = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
    if ($ffmpegCommand) {
        $ffmpegPath = $ffmpegCommand.Source
    } else {
        throw "未找到 ffmpeg.exe。请将它放到项目根目录，或加入 PATH。"
    }
}

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
