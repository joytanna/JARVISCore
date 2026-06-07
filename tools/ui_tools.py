from tools.registry import register

_show_fn = None
_hide_fn = None


def set_ui_callbacks(show, hide):
    global _show_fn, _hide_fn
    _show_fn, _hide_fn = show, hide


@register(
    name="open_fullscreen",
    description="Open the fullscreen UI dashboard",
    parameters={"type": "object", "properties": {}},
)
def open_fullscreen() -> str:
    if _show_fn:
        _show_fn()
        return "Fullscreen UI opened."
    return "UI not available."


@register(
    name="close_fullscreen",
    description="Close the fullscreen UI dashboard",
    parameters={"type": "object", "properties": {}},
)
def close_fullscreen() -> str:
    if _hide_fn:
        _hide_fn()
        return "UI closed."
    return "UI not running."
