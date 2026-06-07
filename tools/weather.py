import json, urllib.request
from tools.registry import register


@register(name="get_weather", description="Get current weather for a location.",
    parameters={"type": "object", "properties": {"location": {"type": "string", "default": "London"}}, "required": []})
def get_weather(location: str = "London") -> str:
    loc = location.strip().replace(" ", "+")
    try:
        url = f"https://wttr.in/{loc}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        c = data["current_condition"][0]
        area = data.get("nearest_area", [{}])[0]
        city = area.get("areaName", [{}])[0].get("value", location)
        return (f"{city}: {c['weatherDesc'][0]['value']}, {c['temp_C']}C/{c['temp_F']}F "
                f"(feels {c['FeelsLikeC']}C), humidity {c['humidity']}%, wind {c['windspeedKmph']} kmh")
    except Exception:
        pass
    try:
        url = f"https://wttr.in/{loc}?format=3"
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.read().decode("utf-8", errors="replace").strip()
    except Exception as e:
        return f"Weather unavailable for {location}: {e}"
