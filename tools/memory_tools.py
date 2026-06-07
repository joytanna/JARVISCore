import memory.store as _store
from tools.registry import register


@register(name="remember_fact", description="Remember a fact for future reference.",
    parameters={"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"}}, "required": ["key", "value"]})
def remember_fact(key: str, value: str) -> str:
    _store.remember(key, value)
    return f"Noted, sir. {key} = {value}"


@register(name="recall_fact", description="Recall a previously remembered fact.",
    parameters={"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]})
def recall_fact(key: str) -> str:
    v = _store.recall(key)
    return v if v else f"Nothing stored for '{key}', sir."


@register(name="list_facts", description="List all remembered facts.",
    parameters={"type": "object", "properties": {}, "required": []})
def list_facts() -> str:
    facts = _store.recall_all()
    return "\n".join(f"{k}: {v}" for k, v in sorted(facts.items())) if facts else "No facts in memory, sir."


@register(name="forget_fact", description="Delete a remembered fact.",
    parameters={"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]})
def forget_fact(key: str) -> str:
    _store.forget(key)
    return f"Forgotten: {key}"
