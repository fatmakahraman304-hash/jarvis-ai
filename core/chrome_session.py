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


def background(process):
    """Lower only our Chrome window; keep it rendering instead of minimizing."""
    if os.name != 'nt' or process is None:
        return
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def lower(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == process.pid:
            user32.SetWindowPos(hwnd, 1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)  # HWND_BOTTOM, no size/move/activation
        return True
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows(callback_type(lower), 0)


def launch(pw, profile):
    # Never attach to the user's everyday Chrome profile.
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    args = [executable(), '--user-data-dir=' + str(Path(profile).resolve()),
            '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=' + str(port),
            '--no-first-run', '--no-default-browser-check', '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding', '--disable-background-timer-throttling', 'about:blank']
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
        background(process)
        return browser, browser.contexts[0], process
    except Exception:
        process.terminate()
        raise


@atexit.register
def cleanup():
    for process in _processes:
        if process.poll() is None:
            process.terminate()
