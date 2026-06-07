import os, platform, subprocess, sys
from tools.registry import register


@register(name="shell", description="Run a shell command and return the output.",
    parameters={"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]})
def shell(command: str) -> str:
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True,
            timeout=30, encoding="utf-8", errors="replace")
        out = result.stdout.strip()
        err = result.stderr.strip()
        if err and not out:
            return f"[stderr]\n{err}"
        return f"{out}\n[stderr]\n{err}" if err else (out or "(no output)")
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as e:
        return f"Error: {e}"


@register(name="read_file", description="Read the contents of a file.",
    parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]})
def read_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(8000)
    except Exception as e:
        return f"Error reading {path}: {e}"


@register(name="write_file", description="Write content to a file.",
    parameters={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]})
def write_file(path: str, content: str) -> str:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Written: {path}"
    except Exception as e:
        return f"Error writing {path}: {e}"


@register(name="list_dir", description="List files and folders in a directory.",
    parameters={"type": "object", "properties": {"path": {"type": "string", "default": "."}}, "required": []})
def list_dir(path: str = ".") -> str:
    try:
        return "\n".join(sorted(os.listdir(path))) or "(empty)"
    except Exception as e:
        return f"Error: {e}"


@register(name="system_info", description="Get system information: OS, CPU, RAM.",
    parameters={"type": "object", "properties": {}, "required": []})
def system_info() -> str:
    lines = [f"OS: {platform.system()} {platform.version()}", f"Python: {sys.version.split()[0]}"]
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        lines += [f"CPU: {cpu}%", f"RAM: {ram.percent}% ({ram.used//1024**2}MB/{ram.total//1024**2}MB)"]
    except ImportError:
        pass
    return "\n".join(lines)


@register(name="open_app", description="Open an application or file.",
    parameters={"type": "object", "properties": {"app": {"type": "string"}}, "required": ["app"]})
def open_app(app: str) -> str:
    try:
        subprocess.Popen(["cmd", "/c", "start", "", app], shell=False,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Opened: {app}"
    except Exception as e:
        return f"Error: {e}"


@register(name="list_processes", description="List running processes.",
    parameters={"type": "object", "properties": {}, "required": []})
def list_processes() -> str:
    try:
        import psutil
        return "\n".join(f"{p.pid:6} {p.name()}"
                         for p in sorted(psutil.process_iter(["pid", "name"]), key=lambda p: p.name()))[:2000]
    except ImportError:
        result = subprocess.run("tasklist /FO CSV /NH", shell=True, capture_output=True,
                                text=True, encoding="utf-8", errors="replace")
        return result.stdout[:2000]
