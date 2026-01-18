"""
YouTube MP3 下載伺服器
功能：
- 系統托盤圖示
- 開機自動執行管理
- 每兩週自動更新 yt-dlp
"""

from flask import Flask, request, send_file, abort, after_this_request, jsonify
import subprocess, os, tempfile, threading, webbrowser, shutil, logging, sys, json, time
from urllib.parse import urlparse, parse_qs
from flask_cors import CORS
import uuid
from datetime import datetime, timedelta

# 系統托盤相關
import pystray
from PIL import Image, ImageDraw

app = Flask(__name__)
CORS(app, expose_headers=['Content-Disposition'])
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ============ 設定檔管理 ============
def get_config_path():
    """取得設定檔路徑"""
    if getattr(sys, 'frozen', False):
        # 打包後，設定檔放在 exe 同目錄
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, 'config.json')

def load_config():
    """載入設定檔"""
    config_path = get_config_path()
    default_config = {
        'auto_start': False,
        'last_update_check': None
    }
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return {**default_config, **json.load(f)}
    except Exception as e:
        logging.error(f"載入設定檔失敗: {e}")
    return default_config

def save_config(config):
    """儲存設定檔"""
    config_path = get_config_path()
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"儲存設定檔失敗: {e}")

# ============ 開機自動執行管理 ============
def get_startup_path():
    """取得開機啟動資料夾路徑"""
    return os.path.join(os.environ['APPDATA'], 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')

def get_shortcut_path():
    """取得捷徑檔案路徑"""
    return os.path.join(get_startup_path(), 'yt_mp3_server.lnk')

def get_executable_path(name=None):
    """取得執行檔路徑"""
    if getattr(sys, 'frozen', False):
        if name:
            return os.path.join(sys._MEIPASS, name)
        return sys.executable
    else:
        if name:
            return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
        return os.path.abspath(__file__)

def is_startup_enabled():
    """檢查是否已設定開機自動執行"""
    return os.path.exists(get_shortcut_path())

def create_startup_shortcut():
    """建立開機啟動捷徑"""
    try:
        # 使用 PowerShell 建立捷徑
        shortcut_path = get_shortcut_path()
        target_path = get_executable_path()
        working_dir = os.path.dirname(target_path)
        
        ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{target_path}"
$Shortcut.WorkingDirectory = "{working_dir}"
$Shortcut.Description = "YouTube MP3 Downloader Server"
$Shortcut.Save()
'''
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        subprocess.run(['powershell', '-Command', ps_script], 
                      capture_output=True, creationflags=creation_flags)
        
        config = load_config()
        config['auto_start'] = True
        save_config(config)
        logging.info("已建立開機啟動捷徑")
        return True
    except Exception as e:
        logging.error(f"建立捷徑失敗: {e}")
        return False

def remove_startup_shortcut():
    """移除開機啟動捷徑"""
    try:
        shortcut_path = get_shortcut_path()
        if os.path.exists(shortcut_path):
            os.remove(shortcut_path)
        
        config = load_config()
        config['auto_start'] = False
        save_config(config)
        logging.info("已移除開機啟動捷徑")
        return True
    except Exception as e:
        logging.error(f"移除捷徑失敗: {e}")
        return False

def toggle_startup(icon, item):
    """切換開機自動執行"""
    if is_startup_enabled():
        remove_startup_shortcut()
    else:
        create_startup_shortcut()

# ============ yt-dlp 更新管理 ============
def should_check_update():
    """檢查是否需要更新（超過 14 天）"""
    config = load_config()
    last_check = config.get('last_update_check')
    
    if not last_check:
        return True
    
    try:
        last_check_date = datetime.fromisoformat(last_check)
        days_since_check = (datetime.now() - last_check_date).days
        return days_since_check >= 14
    except:
        return True

def update_ytdlp(icon=None, item=None, show_notification=True):
    """更新 yt-dlp"""
    def do_update():
        try:
            yt_dlp_path = get_executable_path("yt-dlp.exe")
            creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            
            result = subprocess.run(
                [yt_dlp_path, "-U"],
                capture_output=True,
                text=True,
                creationflags=creation_flags
            )
            
            output = result.stdout + result.stderr
            
            # 更新設定檔中的檢查時間
            config = load_config()
            config['last_update_check'] = datetime.now().isoformat()
            save_config(config)
            
            if "yt-dlp is up to date" in output or "已是最新版本" in output:
                logging.info("yt-dlp 已是最新版本")
                if show_notification and icon:
                    icon.notify("yt-dlp 已是最新版本", "YouTube MP3")
            elif "Updated yt-dlp" in output or "Updating to" in output:
                logging.info("yt-dlp 更新成功")
                if show_notification and icon:
                    icon.notify("yt-dlp 更新成功！", "YouTube MP3")
            else:
                logging.info(f"yt-dlp 更新完成: {output[:100]}")
                if show_notification and icon:
                    icon.notify("yt-dlp 檢查完成", "YouTube MP3")
                    
        except Exception as e:
            logging.error(f"更新 yt-dlp 失敗: {e}")
            if show_notification and icon:
                icon.notify(f"更新失敗: {str(e)[:50]}", "YouTube MP3")
    
    thread = threading.Thread(target=do_update, daemon=True)
    thread.start()

def check_update_on_startup(icon):
    """啟動時檢查更新"""
    if should_check_update():
        logging.info("距離上次更新已超過 14 天，開始更新 yt-dlp...")
        update_ytdlp(icon, show_notification=True)
    else:
        logging.info("距離上次更新未超過 14 天，跳過更新檢查")

# ============ 系統托盤 ============
def create_tray_icon():
    """建立托盤圖示"""
    # 嘗試載入圖示檔
    icon_path = None
    if getattr(sys, 'frozen', False):
        # 打包後
        icon_path = os.path.join(os.path.dirname(sys.executable), 'icon.ico')
    else:
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico')
    
    if icon_path and os.path.exists(icon_path):
        image = Image.open(icon_path)
    else:
        # 建立預設圖示（紅色圓形）
        image = Image.new('RGB', (64, 64), color=(30, 30, 30))
        draw = ImageDraw.Draw(image)
        draw.ellipse([8, 8, 56, 56], fill='#FF0000')
        draw.polygon([(28, 20), (28, 44), (46, 32)], fill='white')
    
    return image

def on_quit(icon, item):
    """結束程式"""
    icon.stop()
    os._exit(0)

def open_youtube(icon, item):
    """開啟 YouTube"""
    webbrowser.open("https://www.youtube.com/")

def setup_tray():
    """設定系統托盤"""
    image = create_tray_icon()
    
    def get_startup_state(item):
        return is_startup_enabled()
    
    def on_toggle_startup(icon, item):
        toggle_startup(icon, item)
    
    def on_open_youtube(icon, item):
        open_youtube(icon, item)
    
    def on_update_ytdlp(icon, item):
        update_ytdlp(icon, item, show_notification=True)
    
    def on_quit_app(icon, item):
        on_quit(icon, item)
    
    menu = pystray.Menu(
        pystray.MenuItem(
            "開機自動執行",
            on_toggle_startup,
            checked=get_startup_state
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("開啟 YouTube", on_open_youtube),
        pystray.MenuItem("更新 yt-dlp", on_update_ytdlp),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("結束", on_quit_app)
    )
    
    icon = pystray.Icon("yt_mp3_server", image, "YouTube MP3 下載器", menu)
    return icon

# ============ Flask 伺服器 ============
DOWNLOAD_TASKS = {}
STALE_TASK_THRESHOLD_SECONDS = 3600

@app.route("/ping")
def ping():
    return "OK"

def download_worker(task_id, clean_url, tmp_dir):
    """背景下載工作，帶進度追蹤"""
    try:
        # 更新狀態：正在獲取影片資訊
        DOWNLOAD_TASKS[task_id].update({"status": "pending", "progress": "正在獲取影片資訊..."})
        
        output_template = os.path.join(tmp_dir, "%(title)s.%(ext)s")
        yt_dlp_path = get_executable_path("yt-dlp.exe")
        ffmpeg_path = get_executable_path("ffmpeg.exe")
        
        cmd = [
            yt_dlp_path, "-x", "--audio-format", "mp3", "--audio-quality", "128K", 
            "--ignore-errors", "--newline", "--progress",
            "--ffmpeg-location", ffmpeg_path, "-o", output_template, clean_url,
        ]
        
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        
        # 使用 Popen 以便即時讀取輸出
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=creation_flags,
            encoding='utf-8',
            errors='replace'
        )
        
        title = None
        
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            
            # 解析影片標題
            if '[download] Destination:' in line:
                try:
                    title = line.split('Destination:')[1].strip()
                    title = os.path.basename(title)
                    DOWNLOAD_TASKS[task_id].update({
                        "status": "downloading",
                        "progress": "正在下載影片...",
                        "title": title
                    })
                except:
                    pass
            
            # 解析下載進度 (簡化版：不統計百分比)
            elif '[download]' in line:
                if "progress" not in DOWNLOAD_TASKS[task_id] or DOWNLOAD_TASKS[task_id]["progress"] != "正在下載中...":
                    DOWNLOAD_TASKS[task_id].update({
                        "status": "downloading",
                        "progress": "正在下載中..."
                    })
            
            # 轉檔階段
            elif '[ExtractAudio]' in line or 'Deleting original file' in line:
                DOWNLOAD_TASKS[task_id].update({
                    "status": "converting",
                    "progress": "轉換為 MP3..."
                })
        
        process.wait()
        
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd)
        
        files = [f for f in os.listdir(tmp_dir) if f.endswith('.mp3')]
        if not files:
            raise FileNotFoundError("yt-dlp ran but no MP3 file was found.")

        DOWNLOAD_TASKS[task_id].update({
            "status": "done",
            "progress": "完成！",
            "file_name": files[0],
            "file_path": os.path.join(tmp_dir, files[0])
        })
        logging.info(f"Task {task_id} completed successfully.")

    except Exception as e:
        error_message = str(e)
        if isinstance(e, subprocess.CalledProcessError):
            error_message = "下載失敗，請稍後再試"
        
        logging.error(f"Task {task_id} failed: {error_message}")
        DOWNLOAD_TASKS[task_id].update({
            "status": "error", 
            "message": error_message,
            "progress": f"錯誤: {error_message[:30]}"
        })

@app.route("/start-download")
def start_download():
    url = request.args.get("url")
    if not url:
        return abort(400, "No URL provided")

    parsed_url = urlparse(url)
    video_id = None
    if 'v' in parse_qs(parsed_url.query):
        video_id = parse_qs(parsed_url.query).get('v')[0]
    elif parsed_url.path.startswith('/shorts/'):
        path_parts = parsed_url.path.split('/')
        if len(path_parts) >= 3 and path_parts[2]:
            video_id = path_parts[2]

    if not video_id:
        return abort(400, "無效的 YouTube 影片/Shorts URL。")
    clean_url = f"https://www.youtube.com/watch?v={video_id}"

    tmp_dir = tempfile.mkdtemp(prefix="ytdl-")
    task_id = str(uuid.uuid4())

    DOWNLOAD_TASKS[task_id] = {"status": "pending", "tmp_dir": tmp_dir, "timestamp": time.time()}
    logging.info(f"Starting task {task_id} for URL {clean_url}")

    thread = threading.Thread(target=download_worker, args=(task_id, clean_url, tmp_dir))
    thread.start()

    return jsonify({"status": "started", "task_id": task_id})

@app.route("/status/<task_id>")
def get_status(task_id):
    task = DOWNLOAD_TASKS.get(task_id)
    if not task:
        return abort(404, "Task not found")
    return jsonify({
        "status": task.get("status", "unknown"), 
        "message": task.get("message", ""),
        "progress": task.get("progress", ""),
        "title": task.get("title", "")
    })

@app.route("/get-file/<task_id>")
def get_file(task_id):
    task = DOWNLOAD_TASKS.get(task_id)
    if not task or task.get("status") != "done":
        return abort(404, "File not ready or task not found")

    file_path = task["file_path"]
    file_name = task["file_name"]
    tmp_dir = task["tmp_dir"]

    def delayed_cleanup(path):
        time.sleep(10)
        try:
            shutil.rmtree(path)
            logging.info(f"Cleaned up temporary directory: {path}")
        except Exception as e:
            logging.error(f"Error cleaning up directory {path}: {e}")

    @after_this_request
    def cleanup(response):
        DOWNLOAD_TASKS.pop(task_id, None)
        threading.Thread(target=delayed_cleanup, args=(tmp_dir,)).start()
        return response

    return send_file(file_path, as_attachment=True, download_name=file_name)

def cleanup_stale_tasks():
    """清理過期任務"""
    while True:
        time.sleep(600)
        stale_tasks = []
        current_time = time.time()

        for task_id, task in list(DOWNLOAD_TASKS.items()):
            task_age = current_time - task.get('timestamp', 0)
            if task_age > STALE_TASK_THRESHOLD_SECONDS and task.get("status") != "done":
                stale_tasks.append(task_id)

        if stale_tasks:
            logging.info(f"Cleaning up {len(stale_tasks)} stale tasks...")
            for task_id in stale_tasks:
                task = DOWNLOAD_TASKS.pop(task_id, None)
                if task and 'tmp_dir' in task:
                    shutil.rmtree(task['tmp_dir'], ignore_errors=True)
                    logging.info(f"Removed stale task {task_id} and its directory.")

def run_flask():
    """在背景執行 Flask 伺服器"""
    app.run(port=8888, threaded=True, use_reloader=False)

# ============ 主程式 ============
if __name__ == '__main__':
    import werkzeug
    # 關閉 werkzeug 的請求日誌
    werkzeug_log = logging.getLogger('werkzeug')
    werkzeug_log.setLevel(logging.ERROR)
    
    # 啟動清理執行緒
    cleanup_thread = threading.Thread(target=cleanup_stale_tasks, daemon=True)
    cleanup_thread.start()
    
    # 啟動 Flask 伺服器（背景執行緒）
    def run_flask_server():
        app.run(host='127.0.0.1', port=8888, threaded=True, use_reloader=False)
    
    flask_thread = threading.Thread(target=run_flask_server, daemon=True)
    flask_thread.start()
    logging.info("Flask 伺服器已在 http://127.0.0.1:8888 啟動")
    
    # 開啟 YouTube
    threading.Timer(1.0, lambda: webbrowser.open("https://www.youtube.com/")).start()
    
    # 設定系統托盤
    icon = setup_tray()
    
    # 啟動時檢查更新
    threading.Timer(2.0, lambda: check_update_on_startup(icon)).start()
    
    # 運行托盤（這會阻塞主執行緒）
    logging.info("系統托盤已啟動")
    icon.run()
