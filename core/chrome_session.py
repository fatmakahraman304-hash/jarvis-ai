"""Dedicated regular Chrome process with a loopback-only automation connection."""
import atexit
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import urllib.request

_processes = []


def executable():
    candidates = [shutil.which('chrome'), shutil.which('google-chrome')]
    for root in (os.environ.get('PROGRAMFILES'), os.environ.get('PROGRAMFILES(X86)'), os.environ.get('LOCALAPPDATA')):
        if root:
            candidates.append(str(Path(root) / 'Google/Chrome/Application/chrome.exe'))
    candidates.append('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
    for path in candidates:
        if path and Path(path).is_file():
            return path
    raise RuntimeError('Google Chrome bulunamadı. Chrome kurup JARVIS’i yeniden başlat.')


def launch(pw, profile):
    # Never attach to the user's everyday Chrome profile.
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    args = [executable(), '--user-data-dir=' + str(Path(profile).resolve()),
            '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=' + str(port),
            '--no-first-run', '--no-default-browser-check', '--start-minimized', 'about:blank']
    if os.environ.get('JARVIS_BROWSER_HEADLESS') == '1':
        args[1:1] = ['--headless=new']
    process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    endpoint = f'http://127.0.0.1:{port}'
    # Ignore HTTP proxy variables for the loopback control channel.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError('JARVIS Chrome profili kullanılıyor olabilir; JARVIS’e ait eski Chrome penceresini kapatıp tekrar dene.')
            try:
                with opener.open(endpoint + '/json/version', timeout=.5) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(.1)
        else:
            raise RuntimeError('Chrome kontrol bağlantısı zaman aşımına uğradı.')
        browser = pw.chromium.connect_over_cdp(endpoint, timeout=10000)
        _processes.append(process)
        return browser, browser.contexts[0], process
    except Exception:
        process.terminate()
        raise


@atexit.register
def cleanup():
    for process in _processes:
        if process.poll() is None:
            process.terminate()
