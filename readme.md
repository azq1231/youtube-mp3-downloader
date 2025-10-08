# YouTube MP3 自動下載器

這是一個由「後端伺服器」與「瀏覽器使用者腳本」組成的工具，讓您可以在 YouTube 影片頁面一鍵下載 MP3 音訊，無需離開或複製貼上網址到其他網站。

 <img width="1169" height="862" alt="image" src="https://github.com/user-attachments/assets/d25f2f2a-a400-4907-8166-fdb4d463f8cb" />

---

## ✨ 功能特色

*   **一鍵下載**：在任何 YouTube 影片或 Shorts 頁面，只需點擊右下角的懸浮按鈕即可開始。
*   **本機處理**：所有下載與轉檔工作都在您自己的電腦上完成，安全、可靠且沒有廣告。
*   **非同步作業**：下載過程在背景進行，完全不影響您當前的瀏覽體驗。
*   **即時狀態更新**：按鈕會顯示目前進度（請求中、處理中、下載完成、失敗）。
*   **自動觸發下載**：MP3 檔案準備就緒後，瀏覽器會自動跳出下載視窗。
*   **智慧檔名**：自動抓取影片標題作為 MP3 檔名，並妥善處理特殊字元。

## ⚙️ 運作原理

此工具分為兩部分：
1.  **後端伺服器 (`yt_mp3_server.exe`)**：一個在您電腦本機運行的程式。它負責接收來自瀏覽器的請求，並使用 `yt-dlp` 和 `ffmpeg` 來完成實際的影片下載與轉檔工作。
2.  **使用者腳本 (`dl.js`)**：安裝在您瀏覽器中的腳本。它會在 YouTube 頁面加上「下載 MP3」按鈕，並在您點擊後與本機的後端伺服器溝通。

**流程：** `瀏覽器中的按鈕` -> `發送請求給本機伺服器` -> `伺服器下載並轉檔` -> `伺服器通知瀏覽器` -> `瀏覽器下載 MP3 檔案`

---

## 🚀 安裝與使用 (一般使用者)

請依照以下四個步驟完成安裝。

### 步驟 1：安裝使用者腳本管理器

您的瀏覽器需要一個擴充功能來管理使用者腳本。請根據您的瀏覽器擇一安裝：
*   **Violentmonkey**: (Chrome / Firefox / Edge) (推薦)
*   **Tampermonkey**: (Chrome / Firefox / Edge)

### 步驟 2：下載後端伺服器

1.  前往本專案的 **GitHub Releases 頁面**。 <!-- 請將 YOUR_USERNAME 換成您的 GitHub 使用者名稱 -->
    *   ➡️ **[點此前往下載頁面](https://github.com/azq1231/youtube-mp3-downloader/releases)**
2.  下載最新版本的 `yt_mp3_server.exe` 檔案。

### 步驟 3：安裝使用者腳本

點擊以下連結進行安裝：

➡️ **點此安裝 YouTube MP3 自動下載器腳本**

您的腳本管理器會跳出一個確認頁面，點擊「安裝」即可。

### 步驟 4：開始使用！

1.  找到您下載的 `yt_mp3_server.exe`，**點兩下執行它**。
2.  執行後不會出現一個黑色命令提示字元視窗，**會自動打開youtube**。
3.  開啟或重新整理任何一個 YouTube 影片頁面。
4.  點擊畫面右下角的「**下載 MP3**」按鈕，開始享受一鍵下載的便利！

---

## 👨‍💻 開發者指南 (從原始碼執行)

如果您想自行修改、除錯或從原始碼執行，請參考以下步驟。

### 環境需求

*   Python 3.8+
*   FFmpeg (需將 `ffmpeg.exe` 放在專案根目錄，或設定在系統環境變數 PATH 中)
*   yt-dlp (需將 `yt-dlp.exe` 放在專案根目錄)

### 執行步驟

1.  Clone 本專案儲存庫：
    ```bash
    git clone https://github.com/azq1231/youtube-mp3-downloader.git
    cd youtube-mp3-downloader
    ```

2.  安裝 Python 依賴套件：
    ```bash
    pip install -r requirements.txt
    ```

3.  執行後端伺服器：
    ```bash
    python yt_mp3_server.py
    ```

4.  伺服器將會運行在 `http://localhost:8888`。此時您可以安裝 `dl.js` 腳本並開始測試。

### 如何打包成 .exe

本專案使用 `PyInstaller` 進行打包。

1.  安裝 PyInstaller：
    ```bash
    pip install pyinstaller
    ```

2.  執行打包命令 (請確認 `yt-dlp.exe`, `ffmpeg.exe` 和 `icon.ico` 都在專案根目錄)：
    ```bash
    pyinstaller --onefile --noconsole --name yt_mp3_server --icon="icon.ico" --add-binary "yt-dlp.exe;." --add-binary "ffmpeg.exe;." yt_mp3_server.py
    ```

3.  打包完成的 `yt_mp3_server.exe` 會出現在 `dist` 資料夾中。
