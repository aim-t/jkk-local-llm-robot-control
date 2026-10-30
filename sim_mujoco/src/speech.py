"""Speech to text with a local Whisper model (whisper.cpp through pywhispercpp). No internet needed.

The web page records while the microphone button is held, then sends the raw sound as
16-bit numbers at 16 000 samples per second, which is what Whisper expects. transcribe()
turns that into text, which then goes into the same pipeline as a typed command.

Model: speech_models/ggml-base.en.bin (148 MB, English only), from
https://huggingface.co/ggerganov/whisper.cpp. Download it again with download_assets.sh.

Test on a sound file without the web page:
    sim_mujoco/.venv/bin/python sim_mujoco/src/speech.py some_16khz_mono.wav
"""

import os
import re
import threading
import time
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(ROOT, "speech_models", "ggml-base.en.bin")
SAMPLE_RATE = 16000
MIN_SECONDS = 0.3   # shorter than this is a click, not speech
MAX_SECONDS = 15.0
# Whisper sometimes writes a sound description instead of words when it hears no speech.
NON_SPEECH = re.compile(r"^\s*[\[(].*[\])]\s*$")

_model = None
_lock = threading.Lock()


def load():
    """Load the model once; later calls reuse it."""
    global _model
    with _lock:
        if _model is None:
            from pywhispercpp.model import Model
            _model = Model(MODEL_PATH, language="en", n_threads=4, print_progress=False,
                           print_realtime=False, no_context=True, single_segment=True,
                           redirect_whispercpp_logs_to=None)
    return _model


def transcribe(samples):
    """16 kHz mono sound as int16 or float numbers -> (text, details)."""
    audio = np.asarray(samples)
    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32768.0
    audio = audio.astype(np.float32)
    seconds = len(audio) / SAMPLE_RATE
    details = {"audio_s": round(seconds, 2), "model": os.path.basename(MODEL_PATH)}
    if seconds < MIN_SECONDS:
        return "", {**details, "error": "too short to be speech"}
    audio = audio[: int(MAX_SECONDS * SAMPLE_RATE)]
    if np.abs(audio).max() < 0.01:
        return "", {**details, "error": "silence: check the microphone"}

    model = load()
    started = time.perf_counter()
    with _lock:
        segments = model.transcribe(audio)
    text = " ".join(s.text.strip() for s in segments).strip()
    details["transcribe_s"] = round(time.perf_counter() - started, 2)
    if not text or NON_SPEECH.match(text):
        return "", {**details, "error": f"no words recognised ({text or 'empty'})"}
    return text, details


def read_wav(path):
    with wave.open(path) as w:
        if w.getframerate() != SAMPLE_RATE or w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError("expected a 16 kHz, mono, 16-bit WAV file")
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


if __name__ == "__main__":
    import sys
    load()
    for wav_path in sys.argv[1:]:
        text, info = transcribe(read_wav(wav_path))
        print(f"{os.path.basename(wav_path)}: {text!r}  {info}")
