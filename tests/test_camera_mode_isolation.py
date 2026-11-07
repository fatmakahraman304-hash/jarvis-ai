"""Playwright regression for independent camera / globe / single AR effect modes."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sock = socket.socket()
sock.bind(("127.0.0.1", 0))
port = sock.getsockname()[1]
sock.close()
data = Path(tempfile.mkdtemp(prefix="jv_ar_modes_"))
(data / "settings.json").write_text(json.dumps({
    "wake_word": False, "voice_enabled": False,
    "always_listen_migrated": True, "continuous_voice_v2": True
}))
env = dict(os.environ, JARVIS_DATA=str(data), TELEGRAM_BOT_TOKEN="",
           GEMINI_API_KEY="", OPENAI_API_KEY="", GROQ_API_KEY="",
           ANTHROPIC_API_KEY="", CUSTOM_BASE_URL="")
log = tempfile.TemporaryFile(mode="w+")
server = subprocess.Popen(
    [sys.executable, "run.py", "--no-browser", "--port", str(port)],
    cwd=ROOT, env=env, stdout=log, stderr=log
)
base = f"http://127.0.0.1:{port}"
try:
    for _ in range(150):
        try:
            with urllib.request.urlopen(base + "/api/node/hello", timeout=1):
                break
        except Exception:
            time.sleep(0.1)
    else:
        log.seek(0)
        raise RuntimeError(log.read()[-3000:])

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
            **({"executable_path": os.environ["JARVIS_TEST_CHROMIUM"]}
               if os.environ.get("JARVIS_TEST_CHROMIUM") else {})
        )
        try:
            page = browser.new_page(viewport={"width": 1360, "height": 950})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.route("**/*", lambda route: route.continue_()
                       if route.request.url.startswith(base) else route.abort())
            page.goto(base)
            page.wait_for_function("window.JV && JV.state.personas.length > 0")
            page.click("#boot-btn")
            page.wait_for_timeout(750)

            result = page.evaluate("""async () => {
              const H = JV.handfx;
              const FX = ['fire','seal','planet','lightning','blast','trail',
                          'palm','face','mask','draw','library','controls'];
              H.show(null);
              const out = {};
              out.selector = !!document.querySelector('#ar-profile');
              out.initial = H.profile;
              out.oldSettingsMigrated = FX.filter(k => H.opts[k]).length === 1;
              H.setProfile('fire');
              H.frame([{ lm: H._synth(0.5, 0.55, 0.5, 'open'), handed: 'Right' }], null);
              out.fire = H.stats().parts > 0;
              H.setProfile('planet');
              out.noFireAfterSwitch = H.stats().parts === 0 && !H.opts.fire;
              H.frame([{ lm: H._synth(0.5, 0.55, 0.5, 'pinch'), handed: 'Right' }], null);
              out.planet = H.stats().planets.length === 1 && !H.opts.fire;
              H.setProfile('lightning');
              out.planetCleared = H.stats().planets.length === 0 && !H.opts.planet;
              out.exclusive = FX.filter(k => H.opts[k]).join(',') === 'lightning';
              H.setProfile('mask');
              out.helmetOnly = H.opts.mask && !H.opts.fire && !H.opts.face && !H.opts.planet;
              H.setProfile('none');
              out.plainOnly = FX.every(k => !H.opts[k]);
              H.setProfile('fire');
              JV.setView('globe');
              out.globeStopsAR = !H.active && JV.getView() === 'globe';
              JV.setView('core');
              H.show(null);
              JV.gesture.setMode('nesne');
              out.objectModeStopsAR = !H.active && JV.gesture.mode() === 'nesne';
              return out;
            }""")
            assert result["selector"] and result["oldSettingsMigrated"], result
            assert result["fire"] and result["noFireAfterSwitch"], result
            assert result["planet"] and result["planetCleared"], result
            assert result["exclusive"] and result["helmetOnly"] and result["plainOnly"], result
            assert result["globeStopsAR"] and result["objectModeStopsAR"], result

            page.evaluate("JV.handfx.show(null)")
            page.click("#t-camera")
            page.wait_for_selector("#camera", state="visible", timeout=15000)
            assert page.evaluate("!JV.handfx.active && JV.camera.isOpen()")
            page.click("#cam-close")
            assert page.evaluate("!JV.camera.isOpen()")
            assert not errors, errors
            print("CAMERA MODES: independent camera / globe / AR profiles — OK")
        finally:
            browser.close()
finally:
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait()
    log.close()
