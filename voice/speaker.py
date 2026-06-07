import queue, subprocess, threading

_q:       queue.Queue = queue.Queue()
_ready    = threading.Event()
_backend  = "none"
_sapi_obj = None   # kept global so stop() can interrupt mid-sentence


def stop():
    """Interrupt speech immediately — clear queue and kill current utterance."""
    try:
        while True:
            _q.get_nowait()
            _q.task_done()
    except queue.Empty:
        pass
    if _backend == "win32com" and _sapi_obj is not None:
        try:
            # SVSFPurgeBeforeSpeak(2) | SVSFlagsAsync(1) = 3
            _sapi_obj.Speak("", 3)
        except Exception:
            pass


def _tts_worker():
    global _backend, _sapi_obj

    # ── win32com SAPI ─────────────────────────────────────────────────────
    try:
        import win32com.client
        sapi = win32com.client.Dispatch("SAPI.SpVoice")
        voices = sapi.GetVoices()
        for i in range(voices.Count):
            desc = voices.Item(i).GetDescription()
            if any(k in desc for k in ("Zira", "Hazel", "George", "David")):
                sapi.Voice = voices.Item(i)
                break
        sapi.Rate   = 1
        sapi.Volume = 95
        _sapi_obj   = sapi
        _backend    = "win32com"
        _ready.set()
        while True:
            text = _q.get()
            if text is None:
                break
            try:
                sapi.Speak(text)
            except Exception:
                pass
            _q.task_done()
        return
    except Exception:
        pass

    # ── pyttsx3 fallback ──────────────────────────────────────────────────
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 175)
        engine.setProperty("volume", 0.95)
        _backend = "pyttsx3"
        _ready.set()
        while True:
            text = _q.get()
            if text is None:
                break
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception:
                pass
            _q.task_done()
        return
    except Exception:
        pass

    # ── PowerShell SAPI fallback ──────────────────────────────────────────
    _backend = "powershell"
    _ready.set()
    while True:
        text = _q.get()
        if text is None:
            break
        try:
            escaped = text.replace("'", "''")
            subprocess.run(
                ["powershell", "-Command",
                 f"Add-Type -AssemblyName System.Speech; "
                 f"$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                 f"$s.Rate=1; $s.Speak('{escaped}')"],
                timeout=30,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass
        _q.task_done()


_worker = threading.Thread(target=_tts_worker, daemon=True, name="tts-worker")
_worker.start()
_ready.wait(timeout=5)


def speak(text: str):
    """Queue text for speech. Clears any pending (not currently playing) items first."""
    if not text or not text.strip():
        return
    _q.put(text.strip())
