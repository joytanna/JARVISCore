"""Device control tools — ALL gated behind voice authentication."""
import subprocess, os
from tools.registry import register


# ── auth gate ──────────────────────────────────────────────────────────────

def _check_auth(action: str) -> str | None:
    """Returns error string if voice auth required but not satisfied, else None."""
    try:
        from voice.auth import get_auth
        if not get_auth().is_enrolled():
            return None  # no enrollment → unrestricted
        from voice.session import is_authed
        if not is_authed():
            return (f"Voice authentication required for '{action}', sir. "
                    "Please give this command by voice.")
    except Exception:
        pass
    return None


def _ps(cmd: str) -> str:
    """Run a PowerShell one-liner."""
    r = subprocess.run(["powershell", "-Command", cmd],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=15)
    return (r.stdout + r.stderr).strip()


# ── power ──────────────────────────────────────────────────────────────────

@register(
    name="shutdown_device",
    description="Shut down the computer after a delay (voice auth required)",
    parameters={
        "type": "object",
        "properties": {"delay_seconds": {"type": "integer",
                                         "description": "Seconds before shutdown (default 30)"}},
    },
)
def shutdown_device(delay_seconds: int = 30) -> str:
    err = _check_auth("shutdown")
    if err: return err
    subprocess.Popen(["shutdown", "/s", "/t", str(delay_seconds)])
    return f"Shutting down in {delay_seconds} seconds, sir."


@register(
    name="restart_device",
    description="Restart the computer after a delay (voice auth required)",
    parameters={
        "type": "object",
        "properties": {"delay_seconds": {"type": "integer",
                                         "description": "Seconds before restart (default 30)"}},
    },
)
def restart_device(delay_seconds: int = 30) -> str:
    err = _check_auth("restart")
    if err: return err
    subprocess.Popen(["shutdown", "/r", "/t", str(delay_seconds)])
    return f"Restarting in {delay_seconds} seconds, sir."


@register(
    name="cancel_shutdown",
    description="Cancel a pending shutdown or restart (voice auth required)",
    parameters={"type": "object", "properties": {}},
)
def cancel_shutdown() -> str:
    err = _check_auth("cancel shutdown")
    if err: return err
    subprocess.Popen(["shutdown", "/a"])
    return "Shutdown cancelled, sir."


@register(
    name="sleep_device",
    description="Put the computer to sleep (voice auth required)",
    parameters={"type": "object", "properties": {}},
)
def sleep_device() -> str:
    err = _check_auth("sleep")
    if err: return err
    subprocess.Popen(
        ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"]
    )
    return "Sleeping now, sir."


@register(
    name="lock_screen",
    description="Lock the workstation screen (voice auth required)",
    parameters={"type": "object", "properties": {}},
)
def lock_screen() -> str:
    err = _check_auth("lock screen")
    if err: return err
    subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
    return "Screen locked, sir."


# ── volume ─────────────────────────────────────────────────────────────────

@register(
    name="set_volume",
    description="Set system volume level 0–100 (voice auth required)",
    parameters={
        "type": "object",
        "properties": {"level": {"type": "integer",
                                  "description": "Volume level 0 (mute) to 100 (max)"}},
        "required": ["level"],
    },
)
def set_volume(level: int) -> str:
    err = _check_auth("volume control")
    if err: return err
    level = max(0, min(100, level))
    _ps(
        f"$vol = (New-Object -ComObject WScript.Shell);"
        f"1..100 | ForEach-Object {{$vol.SendKeys([char]174)}};"  # mute all
        f"1..{level} | ForEach-Object {{$vol.SendKeys([char]175)}}"  # set level
    )
    return f"Volume set to {level}%, sir."


@register(
    name="mute_volume",
    description="Toggle system mute (voice auth required)",
    parameters={"type": "object", "properties": {}},
)
def mute_volume() -> str:
    err = _check_auth("mute")
    if err: return err
    _ps("(New-Object -ComObject WScript.Shell).SendKeys([char]173)")
    return "Volume toggled, sir."


# ── display ────────────────────────────────────────────────────────────────

@register(
    name="turn_off_monitor",
    description="Turn off the monitor/display (voice auth required)",
    parameters={"type": "object", "properties": {}},
)
def turn_off_monitor() -> str:
    err = _check_auth("turn off monitor")
    if err: return err
    subprocess.Popen(
        ["powershell", "-Command",
         "(Add-Type '[DllImport(\"user32.dll\")]public static extern int SendMessage(int hWnd,int hMsg,int wParam,int lParam);' "
         "-Name User32 -PassThru)::SendMessage(-1,0x0112,0xF170,2)"],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return "Monitor off, sir."


@register(
    name="set_brightness",
    description="Set screen brightness 0–100 (voice auth required, works on laptops)",
    parameters={
        "type": "object",
        "properties": {"level": {"type": "integer",
                                  "description": "Brightness 0–100"}},
        "required": ["level"],
    },
)
def set_brightness(level: int) -> str:
    err = _check_auth("brightness control")
    if err: return err
    level = max(0, min(100, level))
    result = _ps(
        f"(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods)"
        f".WmiSetBrightness({level}, 0)"
    )
    return f"Brightness set to {level}%, sir." if not result else f"Brightness: {result}"


# ── network ────────────────────────────────────────────────────────────────

@register(
    name="toggle_wifi",
    description="Enable or disable Wi-Fi (voice auth required)",
    parameters={
        "type": "object",
        "properties": {"enable": {"type": "boolean"}},
        "required": ["enable"],
    },
)
def toggle_wifi(enable: bool) -> str:
    err = _check_auth("Wi-Fi toggle")
    if err: return err
    action = "enable" if enable else "disable"
    _ps(f"netsh interface set interface 'Wi-Fi' {action}")
    return f"Wi-Fi {'enabled' if enable else 'disabled'}, sir."
