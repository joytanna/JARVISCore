import array, math, pickle

import config

_AUTH_FILE = config.MEMORY_DIR / "voice_auth.pkl"
_SAMPLE_RATE = config.SAMPLE_RATE
_ENROLL_SECONDS = 4
_ENROLL_SAMPLES = 3
_THRESHOLD = 0.72
_FRAME_SAMPLES = int(_SAMPLE_RATE * 0.05)  # 50 ms frames


def _features(pcm_bytes: bytes) -> list:
    """Extract (RMS, ZCR) per 50ms frame."""
    frame_bytes = _FRAME_SAMPLES * 2  # 16-bit
    frames = []
    for i in range(0, len(pcm_bytes) - frame_bytes, frame_bytes):
        chunk = array.array("h", pcm_bytes[i : i + frame_bytes])
        n = len(chunk)
        if n == 0:
            continue
        rms = math.sqrt(sum(s * s for s in chunk) / n) / 32768.0
        zcr = sum(1 for j in range(1, n) if (chunk[j] >= 0) != (chunk[j - 1] >= 0)) / n
        frames.append((rms, zcr))
    return frames


def _cosine(a: list, b: list) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    dot = sum(a[i][0] * b[i][0] + a[i][1] * b[i][1] for i in range(n))
    ma = math.sqrt(sum(x[0] ** 2 + x[1] ** 2 for x in a[:n]))
    mb = math.sqrt(sum(x[0] ** 2 + x[1] ** 2 for x in b[:n]))
    return dot / (ma * mb) if ma and mb else 0.0


class VoiceAuth:
    def __init__(self):
        self._fingerprint: list = []
        self._enrolled = False
        self._load()

    def _load(self):
        if _AUTH_FILE.exists():
            try:
                data = pickle.loads(_AUTH_FILE.read_bytes())
                self._fingerprint = data.get("fingerprint", [])
                self._enrolled = bool(self._fingerprint)
            except Exception:
                pass

    def _save(self):
        _AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
        _AUTH_FILE.write_bytes(pickle.dumps({"fingerprint": self._fingerprint}))

    def is_enrolled(self) -> bool:
        return self._enrolled

    def enroll(self) -> str:
        try:
            import pyaudio
        except ImportError:
            return "pyaudio not available — cannot enroll voice."

        all_feats: list = []
        pa = pyaudio.PyAudio()
        try:
            for i in range(_ENROLL_SAMPLES):
                print(f"[VoiceAuth] Sample {i + 1}/{_ENROLL_SAMPLES} — speak for {_ENROLL_SECONDS}s now...")
                stream = pa.open(
                    format=pyaudio.paInt16, channels=1,
                    rate=_SAMPLE_RATE, input=True, frames_per_buffer=1024,
                )
                chunks = []
                for _ in range(int(_SAMPLE_RATE / 1024 * _ENROLL_SECONDS)):
                    chunks.append(stream.read(1024, exception_on_overflow=False))
                stream.stop_stream()
                stream.close()
                all_feats.extend(_features(b"".join(chunks)))
                print(f"[VoiceAuth] Sample {i + 1} captured.")
        finally:
            pa.terminate()

        if not all_feats:
            return "Enrollment failed — no audio captured."

        self._fingerprint = all_feats
        self._enrolled = True
        self._save()
        return f"Voice enrollment complete, sir. {len(all_feats)} frames stored."

    def verify(self, pcm_bytes: bytes) -> bool:
        """Return True if audio matches enrolled voice (or no enrollment exists)."""
        if not self._enrolled:
            return True
        feats = _features(pcm_bytes)
        if not feats:
            return False
        return _cosine(feats, self._fingerprint) >= _THRESHOLD


_auth: VoiceAuth | None = None


def get_auth() -> VoiceAuth:
    global _auth
    if _auth is None:
        _auth = VoiceAuth()
    return _auth
