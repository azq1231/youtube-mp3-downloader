from flask import Flask, request, send_file, abort, after_this_request, jsonify
import subprocess, os, tempfile, threading, webbrowser, shutil, logging, sys
from urllib.parse import urlparse, parse_qs
from flask_cors import CORS
import uuid
import time

app = Flask(__name__)
# Enable CORS and explicitly expose the Content-Disposition header
CORS(app, expose_headers=['Content-Disposition'])
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# In-memory dictionary to track download tasks
DOWNLOAD_TASKS = {}
STALE_TASK_THRESHOLD_SECONDS = 3600 # 1 hour

def get_executable_path(name):
    """Gets the path to an executable, accommodating for PyInstaller."""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        return os.path.join(base_path, name)
    return name

@app.route("/ping")
def ping():
    return "OK"

def download_worker(task_id, clean_url, tmp_dir):
    """This function runs in a background thread to download and convert the video."""
    try:
        output_template = os.path.join(tmp_dir, "%(title)s.%(ext)s")
        yt_dlp_path = get_executable_path("yt-dlp.exe")
        ffmpeg_path = get_executable_path("ffmpeg.exe")
        cmd = [
            yt_dlp_path, "-x", "--audio-format", "mp3", "--audio-quality", "128K", "--ignore-errors",
            "--ffmpeg-location", ffmpeg_path, "-o", output_template, clean_url,
        ]
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        result = subprocess.run(cmd, capture_output=True, creationflags=creation_flags)
        result.check_returncode()

        files = [f for f in os.listdir(tmp_dir) if f.endswith('.mp3')]
        if not files:
            raise FileNotFoundError("yt-dlp ran but no MP3 file was found.")

        DOWNLOAD_TASKS[task_id].update({
            "status": "done",
            "file_name": files[0],
            "file_path": os.path.join(tmp_dir, files[0])
        })
        logging.info(f"Task {task_id} completed successfully.")

    except Exception as e:
        error_message = str(e)
        if isinstance(e, subprocess.CalledProcessError):
            error_message = e.stderr.decode(errors='ignore') if e.stderr else "Unknown yt-dlp error."
        
        logging.error(f"Task {task_id} failed: {error_message}")
        DOWNLOAD_TASKS[task_id].update({"status": "error", "message": error_message})

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
    return jsonify({"status": task.get("status", "unknown"), "message": task.get("message", "")})

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

def open_browser():
    webbrowser.open("https://www.youtube.com/")

def cleanup_stale_tasks():
    while True:
        time.sleep(600) # Run every 10 minutes
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

if __name__ == '__main__':
    cleanup_thread = threading.Thread(target=cleanup_stale_tasks, daemon=True)
    cleanup_thread.start()
    threading.Timer(1.0, open_browser).start()
    app.run(port=8888)
