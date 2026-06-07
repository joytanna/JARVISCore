import functools

_TOOLS: dict = {}


def register(name: str, description: str, parameters: dict):
    def decorator(fn):
        _TOOLS[name] = {"name": name, "description": description, "parameters": parameters, "fn": fn}
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def all_tools() -> dict:
    return dict(_TOOLS)


def load_into_agent(agent) -> int:
    for name, info in _TOOLS.items():
        agent.register(name=name, description=info["description"],
                       parameters=info["parameters"], fn=info["fn"])
    return len(_TOOLS)
