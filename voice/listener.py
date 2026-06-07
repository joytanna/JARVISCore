import queue, threading
import config


class Listener:
    def __init__(self, on_command):
        self._cb = on_command
        self._stop = threading.Event()

    def start(self):
        t = threading.Thread(target=self._run, daemon=True, name="listener")
        t.start()
        return t

    def _run(self):
        try:
            import speech_recognition as sr
        except ImportError:
            print("[Listener] speech_recognition not installed — voice disabled.")
            return

        r = sr.Recognizer()
        r.dynamic_energy_threshold = False

        try:
            mic = sr.Microphone(sample_rate=config.SAMPLE_RATE)
        except Exception as e:
            print(f"[Listener] Microphone error: {e}")
            return

        print("[Listener] Calibrating...", end=" ", flush=True)
        try:
            with mic as source:
                r.adjust_for_ambient_noise(source, duration=config.SILENCE_SECS)
            print(f"done. Threshold={r.energy_threshold:.0f}")
        except Exception as e:
            print(f"failed: {e}")
            return

        def _on_audio(recognizer, audio):
            try:
                text = recognizer.recognize_google(audio).lower().strip()
                wake = next((w for w in config.WAKE_WORDS if text.startswith(w)), None)
                if wake:
                    try:
                        from voice.auth import get_auth
                        if not get_auth().verify(audio.get_raw_data(convert_rate=config.SAMPLE_RATE, convert_width=2)):
                            print("[Listener] Voice auth failed — ignoring command.")
                            return
                    except Exception:
                        pass
                    # Interrupt any ongoing speech immediately
                    try:
                        from voice.speaker import stop as stop_speaking
                        stop_speaking()
                    except Exception:
                        pass
                    # Mark this as a voice-authenticated session
                    try:
                        from voice.session import mark_authed
                        mark_authed()
                    except Exception:
                        pass
                    cmd = text[len(wake):].strip()
                    self._cb(cmd if cmd else "yes?")
            except Exception:
                pass

        try:
            stop_fn = r.listen_in_background(mic, _on_audio, phrase_time_limit=10)
            print("[Listener] Background listening active.")
            while not self._stop.is_set():
                self._stop.wait(timeout=1)
            stop_fn(wait_for_stop=False)
        except Exception as e:
            print(f"[Listener] Falling back to polling ({e})")
            self._poll(r, mic)

    def _poll(self, r, mic):
        import speech_recognition as sr
        while not self._stop.is_set():
            try:
                with mic as source:
                    audio = r.listen(source, timeout=3, phrase_time_limit=10)
                text = r.recognize_google(audio).lower().strip()
                wake = next((w for w in config.WAKE_WORDS if text.startswith(w)), None)
                if wake:
                    self._cb(text[len(wake):].strip() or "yes?")
            except Exception:
                continue

    def stop(self):
        self._stop.set()
