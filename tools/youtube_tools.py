"""
YouTube Tools — Fetch transcripts, summarise videos, extract key points.
Requires: pip install youtube-transcript-api   (falls back gracefully if absent)
Video metadata via YouTube oEmbed API — no API key needed.
"""
import json
import re
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen, Request

import config
from tools.registry import register


def _extract_video_id(url_or_id: str) -> str:
    """Extract YouTube video ID from URL or return as-is if already an ID."""
    s = url_or_id.strip()
    # Already an ID (11 chars)
    if re.match(r'^[A-Za-z0-9_-]{11}$', s):
        return s
    # youtu.be/ID
    m = re.search(r'youtu\.be/([A-Za-z0-9_-]{11})', s)
    if m:
        return m.group(1)
    # youtube.com/watch?v=ID
    m = re.search(r'[?&]v=([A-Za-z0-9_-]{11})', s)
    if m:
        return m.group(1)
    # youtube.com/embed/ID
    m = re.search(r'/embed/([A-Za-z0-9_-]{11})', s)
    if m:
        return m.group(1)
    raise ValueError(f"Could not extract video ID from: {url_or_id!r}")


def _http_get(url: str, timeout: int = 10) -> str:
    req = Request(url, headers={"User-Agent": "JARVIS/1.0"})
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


# ── Video Info ─────────────────────────────────────────────────────────────────
@register(
    name="get_youtube_info",
    description="Get title, channel, duration and description of a YouTube video.",
    parameters={"type": "object", "properties": {
        "url": {"type": "string", "description": "YouTube URL or video ID"},
    }, "required": ["url"]},
)
def get_youtube_info(url: str) -> str:
    try:
        vid  = _extract_video_id(url)
        oemb = json.loads(_http_get(
            f"https://www.youtube.com/oembed?url=https://youtu.be/{vid}&format=json"))
        title   = oemb.get("title", "Unknown")
        channel = oemb.get("author_name", "Unknown")
        watch   = f"https://youtu.be/{vid}"
        return (f"Title:   {title}\n"
                f"Channel: {channel}\n"
                f"URL:     {watch}")
    except Exception as e:
        return f"Could not fetch video info: {e}"


# ── Transcript ─────────────────────────────────────────────────────────────────
@register(
    name="get_youtube_transcript",
    description=(
        "Fetch the transcript/subtitles of a YouTube video. "
        "Requires: pip install youtube-transcript-api"
    ),
    parameters={"type": "object", "properties": {
        "url":      {"type": "string", "description": "YouTube URL or video ID"},
        "language": {"type": "string", "description": "Language code, e.g. 'en', 'hi' (default en)"},
    }, "required": ["url"]},
)
def get_youtube_transcript(url: str, language: str = "en") -> str:
    try:
        vid = _extract_video_id(url)
    except ValueError as e:
        return str(e)
    try:
        from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
        try:
            transcript = YouTubeTranscriptApi.get_transcript(vid, languages=[language, 'en'])
        except NoTranscriptFound:
            # Try auto-generated
            transcript_list = YouTubeTranscriptApi.list_transcripts(vid)
            t = transcript_list.find_generated_transcript(['en'])
            transcript = t.fetch()

        text   = " ".join(s['text'] for s in transcript)
        words  = len(text.split())
        # Trim for readability
        if len(text) > 8000:
            text = text[:8000] + f"... [Transcript truncated — {words} words total]"
        return f"[Transcript — {words} words]\n\n{text}"

    except ImportError:
        return ("youtube-transcript-api is not installed.\n"
                "Run: pip install youtube-transcript-api\n"
                "Then try again, sir.")
    except Exception as e:
        return f"Transcript unavailable: {e}"


# ── Summarise ──────────────────────────────────────────────────────────────────
@register(
    name="summarize_youtube",
    description=(
        "Fetch the transcript of a YouTube video and produce an AI summary "
        "with key points and takeaways."
    ),
    parameters={"type": "object", "properties": {
        "url":      {"type": "string", "description": "YouTube URL or video ID"},
        "language": {"type": "string", "description": "Transcript language code (default en)"},
    }, "required": ["url"]},
)
def summarize_youtube(url: str, language: str = "en") -> str:
    transcript = get_youtube_transcript(url, language)
    if transcript.startswith("youtube-transcript-api") or transcript.startswith("Transcript unavailable"):
        return transcript

    # Info
    info = get_youtube_info(url)

    try:
        from brain.core import get_brain
        # Use first 6000 chars of transcript for LLM
        text_for_llm = transcript[transcript.find("\n\n")+2:][:6000]
        prompt = (
            f"This is the transcript of a YouTube video:\n\n{text_for_llm}\n\n"
            f"Provide:\n"
            f"1. A 2-3 sentence summary\n"
            f"2. 5 key points (bullet list)\n"
            f"3. Main takeaway or actionable insight"
        )
        summary = get_brain().quick(prompt, max_tokens=500)
        return f"{info}\n\n--- Summary ---\n{summary}"
    except Exception as e:
        return f"{info}\n\nCould not summarise: {e}"


# ── Extract Chapters / Timestamps ──────────────────────────────────────────────
@register(
    name="youtube_chapters",
    description="Extract chapter timestamps from a YouTube video description.",
    parameters={"type": "object", "properties": {
        "url": {"type": "string", "description": "YouTube URL or video ID"},
    }, "required": ["url"]},
)
def youtube_chapters(url: str) -> str:
    try:
        vid  = _extract_video_id(url)
        # Fetch page HTML and look for chapter timestamps in description
        html = _http_get(f"https://www.youtube.com/watch?v={vid}")
        # Extract description from page JSON
        m    = re.search(r'"shortDescription":"(.*?)"(?:,"isCrawlable")', html, re.S)
        if not m:
            return "Could not extract description from video page, sir."
        desc = m.group(1).replace('\\n', '\n').replace('\\"', '"')

        # Find timestamp lines  "0:00 Intro"  "1:23:45 Conclusion"
        chapters = re.findall(r'(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)', desc)
        if not chapters:
            return "No chapter timestamps found in this video's description, sir."
        lines = [f"  {ts:12} {title}" for ts, title in chapters[:30]]
        return "Chapters:\n" + "\n".join(lines)
    except Exception as e:
        return f"Could not fetch chapters: {e}"


# ── Save Transcript to Note ───────────────────────────────────────────────────
@register(
    name="save_youtube_transcript",
    description="Fetch a YouTube transcript and save it as a note for later reference.",
    parameters={"type": "object", "properties": {
        "url":   {"type": "string", "description": "YouTube URL"},
        "title": {"type": "string", "description": "Note title (default: video title)"},
    }, "required": ["url"]},
)
def save_youtube_transcript(url: str, title: str = "") -> str:
    transcript = get_youtube_transcript(url)
    if "not installed" in transcript or "Transcript unavailable" in transcript:
        return transcript
    if not title:
        try:
            info  = get_youtube_info(url)
            title = info.split("\n")[0].replace("Title:   ", "")
        except Exception:
            title = "YouTube Transcript"
    try:
        from tools.notes import create_note
        return create_note(f"YT: {title}", transcript, tags="youtube,transcript")
    except Exception as e:
        return f"Could not save note: {e}"
