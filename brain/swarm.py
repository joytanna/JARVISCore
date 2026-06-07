import config
from brain.core import get_brain

_ROUTING = {
    "search": "HERALD", "news": "HERALD", "headline": "HERALD", "weather": "HERALD",
    "stock": "TREASURER", "price": "TREASURER", "crypto": "TREASURER", "market": "TREASURER",
    "code": "ARCHITECT", "debug": "ARCHITECT", "script": "ARCHITECT", "program": "ARCHITECT",
    "write": "SCRIBE", "essay": "SCRIBE", "email": "SCRIBE", "draft": "SCRIBE",
    "research": "SCHOLAR", "explain": "SCHOLAR", "wiki": "SCHOLAR", "history": "SCHOLAR",
    "remind": "CONDUCTOR", "schedule": "CONDUCTOR", "calendar": "CONDUCTOR",
    "health": "MEDIC", "symptom": "MEDIC", "medicine": "MEDIC",
    "security": "SENTRY", "password": "SENTRY", "encrypt": "SENTRY",
    "plan": "STRATEGIST", "strategy": "STRATEGIST", "analyse": "STRATEGIST", "analyze": "STRATEGIST",
    "translate": "DIPLOMAT", "language": "DIPLOMAT",
    "system": "KERNEL", "file": "KERNEL", "process": "KERNEL",
}

_PERSONAS = {
    "HERALD":     "You are HERALD, the information agent. Fetch and summarise news and web data.",
    "TREASURER":  "You are TREASURER, the finance agent. Handle markets, budgets, investments.",
    "ARCHITECT":  "You are ARCHITECT, the code agent. Write clean, efficient code.",
    "SCRIBE":     "You are SCRIBE, the writing agent. Draft, edit and refine text.",
    "SCHOLAR":    "You are SCHOLAR, the knowledge agent. Explain with depth and clarity.",
    "CONDUCTOR":  "You are CONDUCTOR, the scheduling agent. Manage time and tasks.",
    "MEDIC":      "You are MEDIC, the health agent. Provide accurate health information.",
    "SENTRY":     "You are SENTRY, the security agent. Protect and audit systems.",
    "STRATEGIST": "You are STRATEGIST, the planning agent. Build strategies and analyse problems.",
    "DIPLOMAT":   "You are DIPLOMAT, the language agent. Translate and communicate.",
    "KERNEL":     "You are KERNEL, the system agent. Handle OS, files, and processes.",
}


def route(text: str) -> str:
    lower = text.lower()
    scores: dict = {}
    for keyword, agent in _ROUTING.items():
        if keyword in lower:
            scores[agent] = scores.get(agent, 0) + 1
    return max(scores, key=lambda a: scores[a]) if scores else "KERNEL"


class SwarmDispatch:
    def __init__(self):
        self._brain = get_brain()

    def dispatch(self, text: str, history: list = None) -> str:
        agent_name = route(text)
        persona = _PERSONAS.get(agent_name, config.PERSONA)
        system = persona + "\n\nAddress the user as 'sir'. Be concise."
        messages = (history or []) + [{"role": "user", "content": text}]
        return self._brain.chat(messages, system=system, smart=True)


_swarm = None


def get_swarm() -> SwarmDispatch:
    global _swarm
    if _swarm is None:
        _swarm = SwarmDispatch()
    return _swarm
