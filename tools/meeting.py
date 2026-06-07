"""
Meeting assistant — record, transcribe, and extract action items.
"""
import threading
import time
from datetime import datetime
from pathlib import Path

import config
from tools.registry import register

_SAVE_DIR = config.MEMORY_DIR / "meetings"
_recording = False
_chunks: list[str] = []
_lock = threading.Lock()
_record_thread = None


def _record_loop():
    global _recording
    try:
        import speech_recognition as sr
        r = sr.Recognizer()
        r.energy_threshold = 280
        r.dynamic_energy_threshold = True
        r.pause_threshold = 1.2
        with sr.Microphone(sample_rate=config.SAMPLE_RATE) as source:
            r.adjust_for_ambient_noise(source, duration=1.5)
            print("[Meeting] Recording started")
            while _recording:
                try:
                    audio = r.listen(source, timeout=6, phrase_time_limit=45)
                    text = r.recognize_google(audio)
                    if text:
                        with _lock:
                            _chunks.append(text)
                        print(f"[Meeting] {text}")
                except sr.WaitTimeoutError:
                    pass
                except sr.UnknownValueError:
                    pass
                except Exception as e:
                    if _recording:
                        print(f"[Meeting] {e}")
    except Exception as e:
        print(f"[Meeting recorder] {e}")
        _recording = False


@register(
    name="start_meeting",
    description="Start recording and transcribing a meeting or conversation.",
    parameters={"type": "object", "properties": {}},
)
def start_meeting() -> str:
    global _recording, _chunks, _record_thread
    if _recording:
        return "Already recording a meeting, sir."
    _SAVE_DIR.mkdir(parents=True, exist_ok=True)
    _recording = True
    _chunks.clear()
    _record_thread = threading.Thread(target=_record_loop, daemon=True, name="meeting_rec")
    _record_thread.start()
    return "Meeting recording started, sir. Say 'stop meeting' when you're done."


@register(
    name="stop_meeting",
    description="Stop meeting recording and generate a summary with action items.",
    parameters={"type": "object", "properties": {}},
)
def stop_meeting() -> str:
    global _recording
    if not _recording:
        return "No active meeting recording, sir."
    _recording = False
    time.sleep(1.5)  # flush last chunk

    with _lock:
        chunks = list(_chunks)

    if not chunks:
        return "No speech was detected during the meeting, sir."

    transcript = " ".join(chunks)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save transcript
    t_path = _SAVE_DIR / f"meeting_{ts}.txt"
    t_path.write_text(transcript)

    # Summarise via LLM
    from brain.core import get_brain
    brain = get_brain()
    prompt = (
        "You are a meeting assistant. Extract key points and action items from "
        "this transcript. Format:\n"
        "SUMMARY: (2-3 sentences)\n\n"
        "ACTION ITEMS:\n- ...\n- ...\n\n"
        "KEY DECISIONS:\n- ...\n\n"
        f"TRANSCRIPT:\n{transcript[:5000]}"
    )
    summary = brain.quick(prompt, max_tokens=500)

    s_path = _SAVE_DIR / f"meeting_{ts}_summary.txt"
    s_path.write_text(summary)

    return f"Meeting ended. {len(chunks)} segments captured.\n\n{summary}"


@register(
    name="get_last_meeting",
    description="Retrieve the summary from the most recent meeting.",
    parameters={"type": "object", "properties": {}},
)
def get_last_meeting() -> str:
    _SAVE_DIR.mkdir(parents=True, exist_ok=True)
    summaries = sorted(_SAVE_DIR.glob("*_summary.txt"), reverse=True)
    if not summaries:
        return "No meeting summaries found, sir."
    content = summaries[0].read_text()
    return f"Most recent meeting ({summaries[0].stem.replace('_summary','')}):\n\n{content}"


@register(
    name="meeting_status",
    description="Check if a meeting is currently being recorded.",
    parameters={"type": "object", "properties": {}},
)
def meeting_status() -> str:
    if _recording:
        with _lock:
            n = len(_chunks)
        return f"Recording in progress, sir. {n} segments captured so far."
    return "No meeting is currently being recorded, sir."
