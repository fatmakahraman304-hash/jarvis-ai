"""Run three harmless Gemini API compatibility probes with the local JARVIS key.

Windows: py -3.13 scripts/diagnose_gemini.py
This sends up to three small requests to the chosen Gemini model (quota may apply).
It never sends your JARVIS conversation, files, SpacePlanner content or passwords.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core import gemini_native, llm  # noqa: E402


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "gemini-3.5-flash-lite"
    if not model.startswith("gemini-"):
        print("Model adı gemini- ile başlamalı.")
        return 2
    key = llm._key("gemini")
    if not key:
        print("GEMINI_API_KEY bulunamadı. JARVIS > Ayarlar > MODELLER üzerinden anahtarını kaydet.")
        return 2

    # Keep the test independent of optional thinking options; user prompt and
    # tool responses are harmless fixed examples, never actual JARVIS history.
    gemini_native._NO_THINK_CFG.add(model)
    ping = [{"type": "function", "function": {
        "name": "jarvis_diagnostic_ping",
        "description": "Diagnostic stub: report a successful local test.",
        "parameters": {"type": "object", "properties": {
            "value": {"type": "integer", "description": "Use the integer 2"}
        }, "required": ["value"]},
    }}]

    def run_stage(name, messages, declarations=None, required=False):
        print(name, end=" ... ", flush=True)
        try:
            events = list(gemini_native.stream(
                key, model, messages, declarations, timeout=20,
                tool_choice="required" if required else "auto"))
        except gemini_native.NativeError as err:
            print(f"HTTP {err.status}")
            if err.status == 429:
                print("Kota/hız sınırı. Google AI Studio > Rate limits bölümünü kontrol et.")
            else:
                print("Google yanıtı:", err.body[:220].replace(key, "[anahtar gizlendi]"))
            return None
        except Exception as err:
            print("BAĞLANTI HATASI:", type(err).__name__)
            return None
        final = next((data for kind, data in reversed(events) if kind == "final"), None)
        print("OK" if final else "YANIT YOK")
        return final

    print("JARVIS Gemini teşhis — model:", model)
    print("Yalnızca sabit test metni gönderilir. API kullanım kotanı tüketebilir.")
    first = run_stage("1/3 Basit metin", [{"role": "user", "content": "Say only: OK"}])
    if first is None:
        print("Sonuç: sorun basit istek aşamasında; JARVIS araç geçmişinden kaynaklanmıyor.")
        return 1

    question = {"role": "user", "content": "Call jarvis_diagnostic_ping with value 2."}
    second = run_stage("2/3 Tek araç çağrısı", [question], ping, required=True)
    if second is None:
        print("Sonuç: araç tanımı veya toolConfig aşamasında hata var.")
        return 1
    calls = second.get("tool_calls") or []
    if len(calls) != 1 or calls[0]["function"]["name"] != "jarvis_diagnostic_ping":
        print("Sonuç: HTTP başarılı ama model beklenen araç çağrısını üretmedi.")
        return 1

    from_model = {"role": "assistant", "content": second.get("content") or "",
                  "tool_calls": calls, "gemini_content": second.get("gemini_content"),
                  "tool_provider": "gemini", "tool_model": model}
    answer = {"role": "tool", "tool_call_id": calls[0]["id"],
              "name": "jarvis_diagnostic_ping", "content": json.dumps({"value": 2, "ok": True})}
    third = run_stage("3/3 Araç sonucundan sonra devam", [question, from_model, answer], ping)
    if third is None:
        print("Sonuç: çok adımlı araç geçmişi/kimlik/imza uyumluluğu incelenmeli.")
        return 1
    print("Sonuç: Üç temel API aşaması çalıştı. JARVIS'in gerçek isteğindeki")
    print("konuşma/araç boyutu veya farklı bir şema sorunu araştırılmalı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
