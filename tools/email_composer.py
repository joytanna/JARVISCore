"""
AI Email Composer — Draft professional emails using Groq LLM, then send via Gmail.
Supports tone control, reply drafting, template application, and subject generation.
"""
from tools.registry import register


def _draft(prompt: str, max_tokens: int = 500) -> str:
    from brain.core import get_brain
    return get_brain().quick(prompt, max_tokens=max_tokens)


# ── Compose ────────────────────────────────────────────────────────────────────
@register(
    name="compose_email",
    description=(
        "Draft a professional email using AI. Specify recipient, subject and key points — "
        "JARVIS writes a polished email in your chosen tone."
    ),
    parameters={"type": "object", "properties": {
        "to":          {"type": "string", "description": "Recipient name or email"},
        "subject":     {"type": "string", "description": "Email subject"},
        "key_points":  {"type": "string",
                        "description": "What to say — bullet points or a brief description"},
        "tone":        {"type": "string",
                        "description": "Tone: professional (default), friendly, formal, apologetic, assertive"},
        "from_name":   {"type": "string", "description": "Your name for the sign-off"},
    }, "required": ["to", "key_points"]},
)
def compose_email(to: str, key_points: str, subject: str = "",
                  tone: str = "professional", from_name: str = "") -> str:
    subj_clause = f"Subject: {subject}\n" if subject else ""
    name_clause = f"Sign it from: {from_name}.\n" if from_name else ""
    prompt = (
        f"Write a {tone} email to '{to}'.\n"
        f"{subj_clause}"
        f"{name_clause}"
        f"Key points to cover:\n{key_points}\n\n"
        f"Format: Subject line first, then the email body. "
        f"Keep it concise, natural, and {tone}. "
        f"Use proper greeting and sign-off."
    )
    draft = _draft(prompt, max_tokens=600)
    return f"--- Email Draft ---\n{draft}\n---\n(Use send_email to send it, sir.)"


# ── Reply Draft ────────────────────────────────────────────────────────────────
@register(
    name="draft_email_reply",
    description="Draft a reply to an existing email.",
    parameters={"type": "object", "properties": {
        "original_email": {"type": "string",
                           "description": "The email you received (paste the text)"},
        "intent":         {"type": "string",
                           "description": "What you want to say back, e.g. 'accept the meeting', 'politely decline'"},
        "tone":           {"type": "string",
                           "description": "Tone: professional, friendly, formal, apologetic (default professional)"},
        "from_name":      {"type": "string", "description": "Your name"},
    }, "required": ["original_email", "intent"]},
)
def draft_email_reply(original_email: str, intent: str,
                      tone: str = "professional", from_name: str = "") -> str:
    name_clause = f"Sign the reply from: {from_name}.\n" if from_name else ""
    prompt = (
        f"Draft a {tone} reply to this email:\n\n"
        f"--- Original ---\n{original_email[:2000]}\n--- End ---\n\n"
        f"{name_clause}"
        f"My intent: {intent}\n\n"
        f"Write only the reply body with a subject line. Keep it concise."
    )
    draft = _draft(prompt, max_tokens=500)
    return f"--- Reply Draft ---\n{draft}\n---\n(Use send_email to send it, sir.)"


# ── Subject Generator ──────────────────────────────────────────────────────────
@register(
    name="generate_email_subject",
    description="Generate 3–5 subject line options for an email.",
    parameters={"type": "object", "properties": {
        "email_body": {"type": "string", "description": "The email content to generate subjects for"},
        "tone":       {"type": "string", "description": "Tone: professional, friendly, urgent, concise"},
    }, "required": ["email_body"]},
)
def generate_email_subject(email_body: str, tone: str = "professional") -> str:
    prompt = (
        f"Generate 5 {tone} subject lines for this email:\n\n"
        f"{email_body[:1500]}\n\n"
        f"Output only the numbered subject lines, nothing else."
    )
    return _draft(prompt, max_tokens=150)


# ── Send Drafted Email ────────────────────────────────────────────────────────
@register(
    name="send_email",
    description="Send an email via your configured Gmail account.",
    parameters={"type": "object", "properties": {
        "to":      {"type": "string", "description": "Recipient email address"},
        "subject": {"type": "string", "description": "Email subject"},
        "body":    {"type": "string", "description": "Email body text"},
    }, "required": ["to", "subject", "body"]},
)
def send_email(to: str, subject: str, body: str) -> str:
    try:
        from tools.gmail import send_email as gmail_send
        return gmail_send(to=to, subject=subject, body=body)
    except ImportError:
        pass
    # Fallback: try smtplib with config
    try:
        import smtplib
        import config
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        gmail_addr = getattr(config, 'GMAIL_ADDRESS', '')
        gmail_pass = getattr(config, 'GMAIL_APP_PASSWORD', '')
        if not gmail_addr or not gmail_pass:
            return ("Gmail not configured. Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD "
                    "in .env, sir.")

        msg = MIMEMultipart()
        msg['From']    = gmail_addr
        msg['To']      = to
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(gmail_addr, gmail_pass)
            server.send_message(msg)

        return f"Email sent to {to}: '{subject}', sir."
    except Exception as e:
        return f"Failed to send email: {e}"


# ── Summarise Received Email ───────────────────────────────────────────────────
@register(
    name="summarize_email",
    description="Paste an email and get a bullet-point summary plus suggested actions.",
    parameters={"type": "object", "properties": {
        "email_text": {"type": "string", "description": "Full email text to summarise"},
    }, "required": ["email_text"]},
)
def summarize_email(email_text: str) -> str:
    prompt = (
        f"Summarise this email in 3–5 bullet points, then list any action items required:\n\n"
        f"{email_text[:3000]}"
    )
    return _draft(prompt, max_tokens=350)


# ── Proofread ─────────────────────────────────────────────────────────────────
@register(
    name="proofread_email",
    description="Check an email draft for grammar, tone and clarity. Returns corrected version.",
    parameters={"type": "object", "properties": {
        "email_text": {"type": "string", "description": "Email draft to proofread"},
        "tone":       {"type": "string", "description": "Target tone: professional, friendly, formal"},
    }, "required": ["email_text"]},
)
def proofread_email(email_text: str, tone: str = "professional") -> str:
    prompt = (
        f"Proofread and improve this {tone} email. "
        f"Fix grammar, improve clarity and natural flow. "
        f"Return the corrected version only:\n\n{email_text[:3000]}"
    )
    return _draft(prompt, max_tokens=600)
