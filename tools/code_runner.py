"""
Code execution — run Python snippets or shell commands and return output.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import config
from tools.registry import register

_TIMEOUT = 30   # seconds
_OUT_DIR  = config.MEMORY_DIR / "code_output"


@register(
    name="run_python",
    description="Execute Python code and return the output. Great for calculations, data processing, file ops.",
    parameters={
        "type": "object",
        "properties": {
            "code":    {"type": "string", "description": "Python code to run"},
            "timeout": {"type": "integer", "description": "Max seconds (default 30)"},
        },
        "required": ["code"],
    },
)
def run_python(code: str, timeout: int = _TIMEOUT) -> str:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False,
                                     dir=str(_OUT_DIR)) as f:
        f.write(code)
        tmpfile = f.name
    try:
        result = subprocess.run(
            [sys.executable, tmpfile],
            capture_output=True, text=True,
            timeout=min(timeout, 60),
            cwd=str(config.BASE_DIR),
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        # Filter out noisy tracebacks vs real output
        if result.returncode != 0 and stderr:
            return f"Error (exit {result.returncode}):\n{stderr[:1200]}"
        if stdout and stderr:
            return f"{stdout[:1500]}\n\n[stderr]:\n{stderr[:400]}"
        return stdout[:2000] if stdout else "(No output)"

    except subprocess.TimeoutExpired:
        return f"Execution timed out after {timeout}s, sir."
    except Exception as e:
        return f"Runner error: {e}"
    finally:
        try:
            os.unlink(tmpfile)
        except Exception:
            pass


@register(
    name="run_shell",
    description="Execute a Windows shell/PowerShell command and return output.",
    parameters={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to run"},
        },
        "required": ["command"],
    },
)
def run_shell(command: str) -> str:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
            cwd=str(config.BASE_DIR),
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        combined = "\n".join(filter(None, [out, err]))
        return combined[:2000] if combined else f"(Exit code: {result.returncode}, no output)"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {_TIMEOUT}s, sir."
    except Exception as e:
        return f"Shell error: {e}"


@register(
    name="evaluate_expression",
    description="Evaluate a simple mathematical or Python expression and return the result instantly.",
    parameters={
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "Python expression, e.g. '2**32' or 'import math; math.pi*5**2'"},
        },
        "required": ["expression"],
    },
)
def evaluate_expression(expression: str) -> str:
    # Safe quick eval for simple expressions
    try:
        import math, statistics
        safe_globals = {
            "__builtins__": {},
            "math": math, "statistics": statistics,
            "abs": abs, "round": round, "min": min, "max": max,
            "sum": sum, "len": len, "range": range, "list": list,
            "int": int, "float": float, "str": str, "pow": pow,
        }
        result = eval(expression, safe_globals)
        return str(result)
    except Exception:
        # Fall back to subprocess for complex expressions
        return run_python(f"print({expression})")
