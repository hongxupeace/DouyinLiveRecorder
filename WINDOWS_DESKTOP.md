# Windows 桌面版

桌面版是基于 PySide6 的首个 MVP，当前支持：

- 添加、删除抖音直播间和自定义 m3u8/flv 地址
- 展示监控开关、直播状态、录制状态和最近检测时间
- 独立开启或停止监控
- 手动开始或安全停止录制
- SQLite 持久化直播间列表
- 设置监控间隔、代理、抖音 Cookie 和录制目录

监控和录制互不绑定：停止监控不会停止已经开始的录制；点击“开始录制”时会先获取一次最新直播源。

## 在 Windows 上运行源码

要求：

- Windows 10/11 64 位
- Python 3.10 或更高版本
- [uv](https://docs.astral.sh/uv/)
- FFmpeg（放置在项目根目录，或加入系统 `PATH`）

```powershell
uv sync
uv run python desktop.py
```

直播间数据库保存在当前 Windows 用户的应用数据目录，录制文件默认保存在“视频/DouyinLiveRecorder”。

## 构建可分发程序

将 `ffmpeg.exe` 放到项目根目录，然后在 Windows PowerShell 中执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\build_windows.ps1
```

构建结果位于：

```text
dist\DouyinLiveRecorderDesktop\
```

分发时应发送整个 `DouyinLiveRecorderDesktop` 文件夹。接收方双击 `DouyinLiveRecorderDesktop.exe` 即可运行，无需安装 Python。

## 当前限制

- 首版只接入抖音以及直接 m3u8/flv 地址。
- 抖音网页规则变化或触发风控时，可能需要在“设置”中更新 Cookie。
- 仅生成 TS 文件，优先保证异常中断后的文件可恢复性。
- 尚未在 Windows CI 中自动构建安装包；构建脚本需要在真实 Windows 环境验证。
