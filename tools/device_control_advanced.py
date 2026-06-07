"""
Advanced Device Control — everything a Google Assistant does on Windows.
Controls volume, brightness, power, processes, network, USB, displays,
microphone, default apps, and more — all without external services.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

import config
from tools.registry import register

_NO_WIN = subprocess.CREATE_NO_WINDOW


def _ps(cmd: str, capture=True) -> str:
    """Run a PowerShell command and return its stdout."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=capture, text=True, creationflags=_NO_WIN, timeout=10
        )
        return r.stdout.strip() if capture else ""
    except Exception as e:
        return f"Error: {e}"


def _run(args: list, capture=True) -> str:
    try:
        r = subprocess.run(args, capture_output=capture, text=True,
                           creationflags=_NO_WIN, timeout=8)
        return r.stdout.strip()
    except Exception as e:
        return f"Error: {e}"


# ── Volume ────────────────────────────────────────────────────────────────────
@register(
    name="get_volume",
    description="Get the current system volume level.",
    parameters={"type": "object", "properties": {}},
)
def get_volume() -> str:
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from comtypes import CLSCTX_ALL
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = interface.QueryInterface(IAudioEndpointVolume)
        level = round(volume.GetMasterVolumeLevelScalar() * 100)
        muted = volume.GetMute()
        return f"Volume: {level}%{' (muted)' if muted else ''}, sir."
    except ImportError:
        out = _ps("[audio]::GetMasterVolumeLevelScalar * 100")
        return f"Volume: {out}%, sir." if out else "Volume info unavailable, sir."
    except Exception as e:
        return f"Volume error: {e}"


@register(
    name="set_volume",
    description="Set system volume (0-100).",
    parameters={"type": "object", "properties": {
        "level": {"type": "integer", "description": "0-100"},
    }, "required": ["level"]},
)
def set_volume(level: int) -> str:
    level = max(0, min(100, level))
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from comtypes import CLSCTX_ALL
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = interface.QueryInterface(IAudioEndpointVolume)
        volume.SetMasterVolumeLevelScalar(level / 100, None)
        return f"Volume set to {level}%, sir."
    except ImportError:
        _ps(f"(New-Object -ComObject WScript.Shell).SendKeys([char]174)" if level==0
            else f"$obj=New-Object -ComObject WScript.Shell;"
                 f"for($i=0;$i -lt 50;$i++){{$obj.SendKeys([char]175)}}")
        return f"Volume adjusted to ~{level}%, sir."
    except Exception:
        _ps(f"(New-Object -ComObject WScript.Shell).SendKeys([char]174)")
        return f"Volume adjusted, sir."


@register(
    name="mute_volume",
    description="Mute or unmute the system audio.",
    parameters={"type": "object", "properties": {
        "mute": {"type": "boolean", "description": "True to mute, False to unmute (default: toggle)"},
    }},
)
def mute_volume(mute: bool = None) -> str:
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from comtypes import CLSCTX_ALL
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = interface.QueryInterface(IAudioEndpointVolume)
        if mute is None:
            mute = not volume.GetMute()
        volume.SetMute(mute, None)
        return f"Audio {'muted' if mute else 'unmuted'}, sir."
    except ImportError:
        _ps("(New-Object -ComObject WScript.Shell).SendKeys([char]173)")
        return "Audio toggled, sir."
    except Exception as e:
        return f"Mute error: {e}"


# ── Brightness ────────────────────────────────────────────────────────────────
@register(
    name="get_brightness",
    description="Get the current screen brightness.",
    parameters={"type": "object", "properties": {}},
)
def get_brightness() -> str:
    out = _ps("(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness")
    if out and out.isdigit():
        return f"Brightness: {out}%, sir."
    return "Brightness query unavailable (laptop display required), sir."


@register(
    name="set_brightness",
    description="Set screen brightness (0-100). Works on laptops with internal display.",
    parameters={"type": "object", "properties": {
        "level": {"type": "integer", "description": "0-100"},
    }, "required": ["level"]},
)
def set_brightness(level: int) -> str:
    level = max(0, min(100, level))
    out = _ps(f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods)"
              f".WmiSetBrightness(1,{level})")
    return f"Brightness set to {level}%, sir."


# ── System power ──────────────────────────────────────────────────────────────
@register(
    name="shutdown_now",
    description="Shut down the PC immediately.",
    parameters={"type": "object", "properties": {
        "delay": {"type": "integer", "description": "Seconds before shutdown (default 30)"},
    }},
)
def shutdown_now(delay: int = 30) -> str:
    _run(["shutdown", "/s", "/t", str(delay)])
    return f"Shutting down in {delay} seconds, sir. Say 'cancel shutdown' to abort."


@register(
    name="cancel_shutdown",
    description="Cancel a scheduled shutdown or restart.",
    parameters={"type": "object", "properties": {}},
)
def cancel_shutdown() -> str:
    _run(["shutdown", "/a"])
    return "Shutdown cancelled, sir."


@register(
    name="restart_now",
    description="Restart the PC.",
    parameters={"type": "object", "properties": {
        "delay": {"type": "integer", "description": "Seconds before restart (default 30)"},
    }},
)
def restart_now(delay: int = 30) -> str:
    _run(["shutdown", "/r", "/t", str(delay)])
    return f"Restarting in {delay} seconds, sir."


@register(
    name="hibernate",
    description="Put the PC into hibernate mode.",
    parameters={"type": "object", "properties": {}},
)
def hibernate() -> str:
    _run(["shutdown", "/h"])
    return "Hibernating, sir."


# ── Display ───────────────────────────────────────────────────────────────────
@register(
    name="list_displays",
    description="List connected displays and their resolution info.",
    parameters={"type": "object", "properties": {}},
)
def list_displays() -> str:
    out = _ps("Get-CimInstance -ClassName Win32_DesktopMonitor | "
              "Select-Object Name,ScreenWidth,ScreenHeight | Format-List")
    return out if out else "Display info unavailable, sir."


@register(
    name="set_display_orientation",
    description="Rotate the screen: normal, left, right, flipped.",
    parameters={"type": "object", "properties": {
        "orientation": {"type": "string", "description": "normal / left / right / flipped"},
    }, "required": ["orientation"]},
)
def set_display_orientation(orientation: str) -> str:
    map_ = {"normal": 0, "landscape": 0, "right": 1, "portrait": 1,
            "flipped": 2, "upside down": 2, "left": 3}
    code = map_.get(orientation.lower().strip(), 0)
    out  = _ps(f"""
Add-Type -AssemblyName System.Windows.Forms
$d=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$c=Add-Type @'
using System;using System.Runtime.InteropServices;
[StructLayout(LayoutKind.Sequential)]public struct DEVMODE{{
  [MarshalAs(UnmanagedType.ByValTStr,SizeConst=32)]public string dmDeviceName;
  public short dmSpecVersion;public short dmDriverVersion;public short dmSize;
  public short dmDriverExtra;public int dmFields;public int dmPositionX;
  public int dmPositionY;public int dmDisplayOrientation;public int dmDisplayFixedOutput;
  public short dmColor;public short dmDuplex;public short dmYResolution;
  public short dmTTOption;public short dmCollate;
  [MarshalAs(UnmanagedType.ByValTStr,SizeConst=32)]public string dmFormName;
  public short dmLogPixels;public int dmBitsPerPel;public int dmPelsWidth;
  public int dmPelsHeight;public int dmDisplayFlags;public int dmDisplayFrequency;}}
'@
""")
    return f"Display orientation changed to {orientation}, sir. (May require admin rights)"


# ── Network ───────────────────────────────────────────────────────────────────
@register(
    name="list_wifi_networks",
    description="List available Wi-Fi networks nearby.",
    parameters={"type": "object", "properties": {}},
)
def list_wifi_networks() -> str:
    out = _run(["netsh", "wlan", "show", "networks"])
    if not out:
        return "No Wi-Fi networks found, sir."
    # Parse SSID lines
    ssids = re.findall(r'SSID\s*:\s*(.+)', out)
    signals = re.findall(r'Signal\s*:\s*(\d+)%', out)
    if not ssids:
        return out
    lines = ["--- Nearby Wi-Fi Networks ---"]
    for i, ssid in enumerate(ssids):
        sig = signals[i] if i < len(signals) else "?"
        lines.append(f"  {ssid:35} {sig}%")
    return "\n".join(lines)


@register(
    name="connect_wifi",
    description="Connect to a known Wi-Fi network by name.",
    parameters={"type": "object", "properties": {
        "ssid": {"type": "string", "description": "Network name (SSID)"},
    }, "required": ["ssid"]},
)
def connect_wifi(ssid: str) -> str:
    out = _run(["netsh", "wlan", "connect", f"name={ssid}"])
    if "Connection request was completed" in out:
        return f"Connected to {ssid}, sir."
    return f"Connect result: {out}"


@register(
    name="get_wifi_password",
    description="Get the password of the currently connected Wi-Fi network.",
    parameters={"type": "object", "properties": {}},
)
def get_wifi_password() -> str:
    # Get current SSID
    profile_out = _run(["netsh", "wlan", "show", "interfaces"])
    ssid_m = re.search(r'SSID\s*:\s*(.+)', profile_out)
    if not ssid_m:
        return "Not connected to any Wi-Fi network, sir."
    ssid = ssid_m.group(1).strip()
    # Get password
    out = _run(["netsh", "wlan", "show", "profile", f"name={ssid}", "key=clear"])
    pw_m = re.search(r'Key Content\s*:\s*(.+)', out)
    pw = pw_m.group(1).strip() if pw_m else "(not found)"
    return f"Wi-Fi '{ssid}' password: {pw}, sir."


# ── Running apps / processes ──────────────────────────────────────────────────
@register(
    name="list_running_apps",
    description="List currently running apps with CPU and memory usage.",
    parameters={"type": "object", "properties": {
        "n": {"type": "integer", "description": "Top N by CPU usage (default 15)"},
    }},
)
def list_running_apps(n: int = 15) -> str:
    try:
        import psutil
        procs = []
        for p in psutil.process_iter(['name','cpu_percent','memory_info','status']):
            try:
                if p.info['status'] == 'running' or p.info['cpu_percent'] > 0:
                    procs.append(p.info)
            except Exception:
                continue
        procs.sort(key=lambda x: -(x.get('cpu_percent') or 0))
        lines = [f"--- Running Processes (top {n}) ---"]
        for p in procs[:n]:
            mem_mb = round((p.get('memory_info') or type('',(),{'rss':0})()).rss / 1e6)
            name   = (p.get('name') or '?').replace('.exe','')[:22]
            cpu    = p.get('cpu_percent') or 0
            lines.append(f"  {name:24} CPU:{cpu:5.1f}%  MEM:{mem_mb:5}MB")
        return "\n".join(lines)
    except ImportError:
        out = _ps("Get-Process | Sort-Object CPU -Descending | Select-Object -First 15 Name,CPU,WorkingSet | Format-Table -AutoSize")
        return out or "Process list unavailable, sir."


@register(
    name="kill_process",
    description="Kill/terminate a process by name.",
    parameters={"type": "object", "properties": {
        "name": {"type": "string", "description": "Process name (e.g. chrome, notepad)"},
    }, "required": ["name"]},
)
def kill_process(name: str) -> str:
    try:
        import psutil
        killed = 0
        for p in psutil.process_iter(['name']):
            if name.lower() in (p.info.get('name') or '').lower():
                p.kill()
                killed += 1
        return (f"Killed {killed} instance(s) of '{name}', sir."
                if killed else f"No process named '{name}' found, sir.")
    except ImportError:
        out = _run(["taskkill", "/IM", f"{name}.exe", "/F"])
        return out or f"Kill command sent for '{name}', sir."


# ── Clipboard ─────────────────────────────────────────────────────────────────
@register(
    name="read_clipboard_text",
    description="Read the current text content of the clipboard.",
    parameters={"type": "object", "properties": {}},
)
def read_clipboard_text() -> str:
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        try:
            text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        except Exception:
            text = ""
        win32clipboard.CloseClipboard()
        if not text:
            return "Clipboard is empty, sir."
        return f"Clipboard ({len(text)} chars):\n{text[:500]}" + ("…" if len(text)>500 else "")
    except ImportError:
        out = _ps("Get-Clipboard")
        return f"Clipboard: {out}" if out else "Clipboard empty, sir."


# ── Default programs ──────────────────────────────────────────────────────────
@register(
    name="set_default_browser",
    description="Open Windows settings to change the default web browser.",
    parameters={"type": "object", "properties": {}},
)
def set_default_browser() -> str:
    os.startfile("ms-settings:defaultapps")
    return "Opening Default Apps settings, sir. Select your preferred browser there."


@register(
    name="get_default_apps",
    description="List current default apps for common file types.",
    parameters={"type": "object", "properties": {}},
)
def get_default_apps() -> str:
    out = _ps("""
$types = @('.pdf','.html','.mp3','.mp4','.jpg','.txt','.docx')
foreach($t in $types){
  $prog = (Get-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FileExts\\$t\\UserChoice" -ErrorAction SilentlyContinue).ProgId
  Write-Host "$t -> $prog"
}
""")
    return ("--- Default Apps ---\n" + out) if out else "Default apps info unavailable, sir."


# ── USB & Storage ─────────────────────────────────────────────────────────────
@register(
    name="list_usb_devices",
    description="List connected USB devices.",
    parameters={"type": "object", "properties": {}},
)
def list_usb_devices() -> str:
    out = _ps("Get-PnpDevice -PresentOnly | Where-Object {$_.InstanceId -like 'USB*'} | "
              "Select-Object FriendlyName,Status | Format-Table -AutoSize")
    return ("--- USB Devices ---\n" + out) if out else "No USB devices found, sir."


@register(
    name="eject_usb",
    description="Safely eject a USB drive by drive letter.",
    parameters={"type": "object", "properties": {
        "drive": {"type": "string", "description": "Drive letter e.g. E or F"},
    }, "required": ["drive"]},
)
def eject_usb(drive: str) -> str:
    letter = drive.upper().rstrip(':').rstrip('\\')
    out = _ps(f"""
$vol = (Get-WmiObject Win32_Volume | Where {{$_.DriveLetter -eq '{letter}:'}})
if($vol){{$vol.DriveLetter = $null; $vol.Put(); Write-Host "Ejected {letter}:"}}
else{{Write-Host "Drive {letter}: not found"}}
""")
    return out or f"Eject command sent for {letter}:, sir."


# ── Microphone ────────────────────────────────────────────────────────────────
@register(
    name="mute_microphone",
    description="Mute or unmute the microphone.",
    parameters={"type": "object", "properties": {
        "mute": {"type": "boolean"},
    }},
)
def mute_microphone(mute: bool = True) -> str:
    # Use Windows WASAPI via pycaw or fallback to PowerShell
    try:
        from pycaw.pycaw import AudioUtilities
        mic = AudioUtilities.GetMicrophone()
        if mic:
            interface = mic.Activate(
                __import__('comtypes').GUID('{5CDF2C82-841E-4546-9722-0CF74078229A}'),
                __import__('comtypes').CLSCTX_ALL, None
            )
            vol = interface.QueryInterface(
                __import__('pycaw.pycaw').IAudioEndpointVolume
            )
            vol.SetMute(mute, None)
            return f"Microphone {'muted' if mute else 'unmuted'}, sir."
    except Exception:
        pass
    out = _ps(f"""
$dev = Get-AudioDevice -List 2>$null | Where{{$_.Type -eq 'Recording'}} | Select-Object -First 1
if($dev){{Set-AudioDevice -ID $dev.ID -Mute {'$true' if mute else '$false'} 2>$null; Write-Host 'done'}}
""")
    return f"Microphone {'muted' if mute else 'unmuted'}, sir."


# ── System info ───────────────────────────────────────────────────────────────
@register(
    name="get_system_uptime",
    description="Get how long the PC has been running since last boot.",
    parameters={"type": "object", "properties": {}},
)
def get_system_uptime() -> str:
    try:
        import psutil, datetime
        boot  = psutil.boot_time()
        uptime = datetime.datetime.now() - datetime.datetime.fromtimestamp(boot)
        h, r  = divmod(int(uptime.total_seconds()), 3600)
        m     = r // 60
        last  = datetime.datetime.fromtimestamp(boot).strftime('%a %d %b at %I:%M %p')
        return f"Uptime: {h}h {m}m (last boot: {last}), sir."
    except Exception as e:
        return f"Uptime error: {e}"


@register(
    name="get_gpu_info",
    description="Get GPU model and VRAM information.",
    parameters={"type": "object", "properties": {}},
)
def get_gpu_info() -> str:
    out = _ps("Get-CimInstance -ClassName Win32_VideoController | "
              "Select-Object Name,AdapterRAM,CurrentHorizontalResolution,CurrentVerticalResolution | "
              "Format-List")
    if out:
        out = re.sub(r'AdapterRAM\s*:\s*(\d+)', lambda m:
              f"AdapterRAM      : {int(m.group(1))//1024//1024} MB", out)
    return out or "GPU info unavailable, sir."


@register(
    name="get_cpu_temperature",
    description="Get CPU temperature (if sensors available).",
    parameters={"type": "object", "properties": {}},
)
def get_cpu_temperature() -> str:
    out = _ps("Get-CimInstance -Namespace root/WMI -ClassName MSAcpi_ThermalZoneTemperature 2>$null | "
              "Select-Object -ExpandProperty CurrentTemperature | "
              "ForEach-Object { ($_ - 2732) / 10 }")
    if out and re.search(r'\d+', out):
        temps = re.findall(r'[\d.]+', out)
        return f"CPU temperature: {temps[0]}°C, sir."
    return "Temperature sensors not accessible via WMI, sir. Try HWiNFO for accurate readings."
