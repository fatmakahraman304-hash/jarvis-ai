"""Offline Vosk WAV transcription. Model must already exist on the user's machine."""
import io
import json
import threading
import wave
from pathlib import Path
from .config import env

_lock=threading.Lock()
_models={}

def transcribe(data):
    from vosk import Model, KaldiRecognizer
    path=Path(env('VOSK_MODEL_PATH'))
    if not env('VOSK_MODEL_PATH') or not (path/'am').is_dir():
        raise RuntimeError('VOSK_MODEL_PATH içinde indirilmiş Vosk dil modeli gerekli. Çevrimdışı mod buluta yedek geçmez.')
    with wave.open(io.BytesIO(data),'rb') as wav:
        if wav.getnchannels()!=1 or wav.getsampwidth()!=2 or wav.getcomptype()!='NONE':
            raise ValueError('Çevrimdışı tanıma mono 16-bit PCM WAV ister; tarayıcı WAV kaydını kullan.')
        rate=wav.getframerate()
        if not 8000<=rate<=48000 or wav.getnframes()/rate>60:raise ValueError('8–48kHz, en fazla 60 saniye WAV gerekli.')
        with _lock:
            key=str(path.resolve())
            if key not in _models:
                _models.clear();_models[key]=Model(key)
            model=_models[key]
        rec=KaldiRecognizer(model,rate);parts=[]
        while True:
            chunk=wav.readframes(4000)
            if not chunk:break
            if rec.AcceptWaveform(chunk):parts.append(json.loads(rec.Result()).get('text',''))
        parts.append(json.loads(rec.FinalResult()).get('text',''))
        return ' '.join(x for x in parts if x).strip()
