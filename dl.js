// ==UserScript==
// @name         YouTube MP3 Auto Downloader
// @namespace    Violentmonkey Scripts
// @version      2.1
// @match        https://www.youtube.com/*
// @grant        none
// @description  Adds a floating button to YouTube pages to download audio as MP3 via a local server.
// ==/UserScript==

(function() {
    'use strict';
    const FLASK_URL = "http://localhost:8888";

    // Create a single, persistent floating button
    const btn = document.createElement('button');
    btn.id = 'yt-dl-floating-btn';
    btn.textContent = '下載 MP3';
    btn.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        z-index: 9999;
        background: #1DA1F2; /* Twitter Blue */
        color: white;
        border: none;
        border-radius: 50px;
        padding: 12px 20px;
        font-size: 16px;
        font-weight: bold;
        cursor: pointer;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        transition: transform 0.2s ease-in-out, background-color 0.2s;
    `;

    btn.onmouseover = () => { btn.style.transform = 'scale(1.05)'; };
    btn.onmouseout = () => { btn.style.transform = 'scale(1)'; };

    btn.onclick = async () => {
        const url = window.location.href;

        // Check if it's a valid video/shorts URL before proceeding
        if (!url.includes('/watch?v=') && !url.includes('/shorts/')) {
            alert('請先進入一個 YouTube 影片或 Shorts 頁面。');
            return;
        }

        const originalText = btn.textContent;
        btn.textContent = '請求中...';
        btn.disabled = true;
        btn.style.cursor = 'wait';
        btn.style.backgroundColor = '#ffc107'; // Yellow for 'in progress'

        function resetButton() {
            setTimeout(() => {
                btn.disabled = false;
                btn.textContent = originalText;
                btn.style.cursor = 'pointer';
                btn.style.backgroundColor = '#1DA1F2'; // Restore original color
            }, 3000);
        }

        function handleError(error) {
            console.error('Download failed:', error);
            alert(`下載失敗！\n請確認伺服器已運行且網路正常。\n\n錯誤詳情: ${error.message}`);
            btn.textContent = '下載失敗';
            btn.style.backgroundColor = '#dc3545'; // Red for error
            resetButton();
        }

        try {
            // Step 1: Start the download and get a task ID
            const startResponse = await fetch(`${FLASK_URL}/start-download?url=${encodeURIComponent(url)}`);
            if (!startResponse.ok) {
                throw new Error(`啟動下載失敗: ${await startResponse.text()}`);
            }
            const { task_id } = await startResponse.json();
            btn.textContent = '處理中...';

            // Step 2: Poll for status
            const pollInterval = setInterval(async () => {
                try {
                    const statusResponse = await fetch(`${FLASK_URL}/status/${task_id}`);
                    if (!statusResponse.ok) {
                        throw new Error(`狀態檢查失敗: ${statusResponse.statusText}`);
                    }
                    const { status, message } = await statusResponse.json();

                    if (status === 'done') {
                        clearInterval(pollInterval);
                        btn.textContent = '準備下載...';

                        // Step 3: Fetch the actual file
                        const fileResponse = await fetch(`${FLASK_URL}/get-file/${task_id}`);
                        if (!fileResponse.ok) {
                            throw new Error(`獲取檔案失敗: ${await fileResponse.text()}`);
                        }

                        const disposition = fileResponse.headers.get('Content-Disposition');
                        let filename = 'audio.mp3';
                        if (disposition && disposition.includes('attachment')) {
                            // Try to parse RFC 5987 filename* first (for non-ASCII characters)
                            const filenameStarMatch = /filename\*=(?:.+?''(.+))/.exec(disposition);
                            if (filenameStarMatch && filenameStarMatch[1]) {
                                try {
                                    filename = decodeURIComponent(filenameStarMatch[1]);
                                } catch (e) {
                                    console.warn("Failed to decode RFC 5987 filename*:", e);
                                }
                            }

                            // Fallback to RFC 2231 filename if filename* was not found or failed to decode
                            if (filename === 'audio.mp3') { // Only try this if filename is still default
                                const filenameMatch = /filename="([^"]+)"/.exec(disposition);
                                if (filenameMatch && filenameMatch[1]) {
                                    try {
                                        // This handles simple URL-encoded filenames
                                        filename = decodeURIComponent(filenameMatch[1]);
                                    } catch (e) {
                                        console.warn("Failed to decode RFC 2231 filename:", e);
                                    }
                                }
                            }
                        }

                        const blob = await fileResponse.blob();
                        const downloadUrl = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.style.display = 'none';
                        a.href = downloadUrl;
                        a.download = filename;
                        document.body.appendChild(a);
                        a.click();
                        window.URL.revokeObjectURL(downloadUrl);
                        a.remove();

                        btn.textContent = '下載完成!';
                        btn.style.backgroundColor = '#28a745';
                        resetButton();

                    } else if (status === 'error') {
                        clearInterval(pollInterval);
                        throw new Error(message || '伺服器發生未知錯誤。');
                    }
                } catch (pollError) {
                    clearInterval(pollInterval);
                    handleError(pollError);
                }
            }, 2000); // Poll every 2 seconds

        } catch (initialError) {
            handleError(initialError);
        }
    };

    // Add the button to the page
    document.body.appendChild(btn);

})();
