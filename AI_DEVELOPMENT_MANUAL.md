# YouTube MP3 Downloader - AI 開發維護手冊

本手冊旨在為未來的 AI 協作提供專案背景、核心架構與開發注意事項。

## 1. 專案架構概觀

本專案由兩部分組成：
- **後端伺服器 (`yt_mp3_server.py`)**: Python Flask + pystray (系統托盤)。負責執行 `yt-dlp.exe` 與 `ffmpeg.exe`。
- **前端使用者腳本 (`dl.js`)**: JavaScript Userscript (Violentmonkey/Tampermonkey)。在 YouTube 頁面注入 UI，透過 API 與本機伺服器溝通。

## 2. 核心技術細節 (Version 3.2+)

### 執行緒架構 (Threading)
在 Windows 平台上，`pystray` (系統托盤) 必須運行在 **主執行緒 (Main Thread)** 才能穩定顯示圖示與通知。
- **主執行緒**: 運行 `icon.run()`。
- **背景執行緒**: 運行 Flask 伺服器、過期任務清理、yt-dlp 更新檢查、以及實際的下載任務。

### 外部依賴與 JS 執行期環境 (Deno)
- **JS 執行期環境 (JS Runtime)**: 由於 YouTube 近期更新了播放器簽章機制，`yt-dlp` 需要 JavaScript 執行環境（如 Deno）來解決 EJS/n-sig 簽章挑戰。本專案將免安裝的 `deno.exe` 打包在內。
- **動態 PATH 環境變數**: 執行 `yt-dlp` 下載時，伺服器會動態將主程式目錄（含 `deno.exe`、`yt-dlp.exe`、`ffmpeg.exe`）加入子行程的 `PATH` 環境變數，確保 `yt-dlp` 能成功尋找到並調用 Deno 執行解密挑戰。

### 二進位檔案釋出與更新持久化 (重要更新)
- **釋出機制**: 為了解決 PyInstaller 暫存資料夾 `_MEIPASS` 隨程式關閉即被系統刪除，導致 `yt-dlp -U` 自動更新無法永久保存的問題。程式在啟動時會執行 `check_and_extract_binaries()`，自動檢查主程式同級目錄下是否已存在 `yt-dlp.exe`、`ffmpeg.exe` 及 `deno.exe`。若不存在，則自動從打包資源中複製出來。
- **更新機制**: 之後的所有執行與更新操作均指向主程式同級目錄下的檔案，保證 `yt-dlp` 更新的持久化保存。
- **上次檢查時間**: 更新檢查時間儲存在專案目錄下的 `config.json`。

### 下載進度追蹤
- **簡介**: 捨棄了百分比顯示 (原因：yt-dlp 輸出的百分比在串流下載時可能發生跳躍或不準確，導致前端 UI 閃爍)。
- **文字顯示**: 簡化為「正在下載中...」、「正在轉換為 MP3...」等穩定狀態。
- **API 通訊**: 前端透過 `/status/<task_id>` 獲取 `progress` 與 `status` 欄位。

### 開機自動執行
- **原理**: 透過 PowerShell 指令在 `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup` 建立/刪除 `.lnk` 捷徑。
- **設定檔**: 狀態同步儲存於 `config.json`。

## 3. 開發及打包注意事項

### pystray Callback 簽名
所有菜單項目的動作函數必須嚴格遵守 `def callback(icon, item)` 的簽名。若函數有其他參數，應使用包裝函數：
```python
def on_action(icon, item):
    my_real_function(icon, item, other_param=True)
```

### PyInstaller 打包指令
打包時必須包含 `yt-dlp.exe`、`ffmpeg.exe` 與 `deno.exe` 三個二進制檔案：
使用 spec 檔案打包（推薦）：
```bash
pyinstaller yt_mp3_server.spec --clean
```
或者使用指令打包：
```bash
pyinstaller --onefile --noconsole --name yt_mp3_server --icon="icon.ico" --add-binary "yt-dlp.exe;." --add-binary "ffmpeg.exe;." --add-binary "deno.exe;." yt_mp3_server.py
```

### 常見錯誤與修復
- **兒童影片 (Made for Kids) 下載失敗**: 
  - **現象**: 錯誤為 `UNPLAYABLE` 或 `403 Forbidden`，只有部分特定兒童歌曲或特殊影片下載失敗，其他影片正常。
  - **原因**: 缺少 Deno 執行期環境，導致 `yt-dlp` 無法解鎖 web/ios 管道的簽章挑戰而降級至 `android_vr` 管道；然而 YouTube 限制 `android_vr` 用戶端下載兒童影片。
  - **解決方式**: 確保主程式同級目錄下已正確釋出 `deno.exe`（伺服器已在此版本自動實現）。
- **權限錯誤 (Permission Error)**: 打包或更新時若失敗，通常是因為舊版的 `yt_mp3_server.exe` 仍在背景運行，請在工作管理員或托盤將其關閉後再試。
- **啟動失敗**: 若 Flask 與托盤衝突，請優先檢查 `icon.run()` 是否在最末後調用，且 Flask 確實已在背景啟動。

## 4. 未來優化方向
- **並行下載限制**: 目前支援多任務，但若頻率過高可能導致 YouTube 封鎖 IP。
- **設定檔路徑**: 目前放在 exe 同目錄，未來若需要可考慮移至 `%APPDATA%`。
