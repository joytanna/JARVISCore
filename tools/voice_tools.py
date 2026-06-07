from tools.registry import register


@register(
    name="enroll_voice",
    description="Enroll the user's voice for authentication (records 3 samples of 4 seconds each)",
    parameters={"type": "object", "properties": {}},
)
def enroll_voice() -> str:
    try:
        from voice.auth import get_auth
        return get_auth().enroll()
    except Exception as e:
        return f"Voice enrollment error: {e}"


@register(
    name="voice_auth_status",
    description="Check whether voice authentication is enrolled",
    parameters={"type": "object", "properties": {}},
)
def voice_auth_status() -> str:
    try:
        from voice.auth import get_auth
        auth = get_auth()
        if auth.is_enrolled():
            return "Voice authentication is active and enrolled, sir."
        return "Voice authentication is not yet enrolled, sir. Say 'enroll my voice' to set it up."
    except Exception as e:
        return f"Voice auth status error: {e}"
