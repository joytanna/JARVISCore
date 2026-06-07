"""Shared voice-session auth state — thread-safe."""
import threading

_lock   = threading.Lock()
_authed = False


def mark_authed():
    global _authed
    with _lock:
        _authed = True


def clear_authed():
    global _authed
    with _lock:
        _authed = False


def is_authed() -> bool:
    with _lock:
        return _authed
