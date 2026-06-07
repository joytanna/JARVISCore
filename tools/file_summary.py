"""Summarise files: plain text, PDF, DOCX."""
import os
from pathlib import Path
from tools.registry import register


def _read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def _read_pdf(path: str) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages[:20]]
        return "\n".join(pages)
    except ImportError:
        pass
    try:
        import pypdf
        reader = pypdf.PdfReader(path)
        return "\n".join(p.extract_text() or "" for p in reader.pages[:20])
    except ImportError:
        pass
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(path)
        return "\n".join(p.extract_text() or "" for p in reader.pages[:20])
    except ImportError:
        return "No PDF library installed. Run: pip install pdfplumber"


def _read_docx(path: str) -> str:
    try:
        import docx
        doc = docx.Document(path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        return "python-docx not installed. Run: pip install python-docx"


def _extract(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return _read_pdf(path)
    if ext in (".docx", ".doc"):
        return _read_docx(path)
    if ext in (".txt", ".md", ".py", ".js", ".ts", ".html", ".csv", ".json", ".xml"):
        return _read_text(path)
    # Try plain text as fallback
    try:
        return _read_text(path)
    except Exception as e:
        return f"Cannot read file: {e}"


@register(
    name="summarize_file",
    description="Read and summarise a file (PDF, DOCX, TXT, code, etc.)",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Full file path"},
            "instruction": {"type": "string",
                            "description": "What to do: summarise, extract key points, translate, etc. Default: summarise"},
        },
        "required": ["path"],
    },
)
def summarize_file(path: str, instruction: str = "Summarise this document concisely.") -> str:
    if not os.path.exists(path):
        # Try Desktop
        desktop = Path.home() / "Desktop" / path
        if desktop.exists():
            path = str(desktop)
        else:
            return f"File not found: {path}"

    content = _extract(path)
    if not content.strip():
        return "File appears to be empty, sir."

    from brain.core import get_brain
    brain = get_brain()
    prompt = f"{instruction}\n\nFile: {os.path.basename(path)}\n\n{content[:6000]}"
    return brain.quick(prompt, max_tokens=600)
