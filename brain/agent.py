import json, re
import config
from brain.core import get_brain, needs_tool

# ── fast-dispatch table ───────────────────────────────────────────────────
# Matched BEFORE any LLM call — zero latency for common commands.
_FAST: list[tuple] = [
    (re.compile(r'^open\s+(.+?)(?:\s+app)?$', re.I),
     'open_app',       lambda m: {'name': m.group(1).strip()}),
    (re.compile(r'^(?:close|kill|quit)\s+(.+)$', re.I),
     'close_app',      lambda m: {'name': m.group(1).strip()}),
    (re.compile(r'^switch\s+to\s+(.+)$', re.I),
     'switch_to_app',  lambda m: {'name': m.group(1).strip()}),
    (re.compile(r'^(?:set\s+)?volume\s+(?:to\s+)?(\d+)%?$', re.I),
     'set_volume',     lambda m: {'level': int(m.group(1))}),
    (re.compile(r'^mute(?:\s+volume)?$', re.I),
     'mute_volume',    lambda m: {}),
    (re.compile(r'^(?:lock|lock\s+screen|lock\s+workstation)$', re.I),
     'lock_screen',    lambda m: {}),
    (re.compile(r'^sleep(?:\s+now)?$', re.I),
     'sleep_device',   lambda m: {}),
    (re.compile(r'^(?:turn\s+off\s+)?monitor$', re.I),
     'turn_off_monitor', lambda m: {}),
    (re.compile(r'^(?:set\s+)?brightness\s+(?:to\s+)?(\d+)%?$', re.I),
     'set_brightness', lambda m: {'level': int(m.group(1))}),
    (re.compile(r'^(?:enable|turn\s+on)\s+wi[-]?fi$', re.I),
     'toggle_wifi',    lambda m: {'enable': True}),
    (re.compile(r'^(?:disable|turn\s+off)\s+wi[-]?fi$', re.I),
     'toggle_wifi',    lambda m: {'enable': False}),
    (re.compile(r'^weather$', re.I),
     'get_weather',    lambda m: {}),
    (re.compile(r'^(?:good\s+morning|morning|briefing|daily\s+brief(?:ing)?)$', re.I),
     'daily_briefing', lambda m: {}),
    (re.compile(r'^list\s+contacts?$', re.I),
     'list_contacts',  lambda m: {}),
    (re.compile(r'^list\s+reminders?$', re.I),
     'list_reminders', lambda m: {}),
    (re.compile(r'^read\s+(?:my\s+)?clipboard$', re.I),
     'read_clipboard', lambda m: {}),
    (re.compile(r"^what'?s?\s+on\s+(?:my\s+)?screen$", re.I),
     'read_screen',    lambda m: {}),
    (re.compile(r'^(?:open\s+)?(?:fullscreen|full\s+screen|dashboard)$', re.I),
     'open_fullscreen', lambda m: {}),
    (re.compile(r'^close\s+(?:fullscreen|full\s+screen|ui|dashboard)$', re.I),
     'close_fullscreen', lambda m: {}),
    (re.compile(r'^(?:show\s+)?remote(?:\s+qr)?$', re.I),
     'show_remote_qr', lambda m: {}),
    (re.compile(r'^list\s+(?:my\s+)?facts?$', re.I),
     'list_facts',     lambda m: {}),
    (re.compile(r'^voice\s+auth\s+status$', re.I),
     'voice_auth_status', lambda m: {}),
    # ── Meeting ──────────────────────────────────────────────────────────────
    (re.compile(r'^(?:start\s+)?meeting(?:\s+record(?:ing)?)?$', re.I),
     'start_meeting',  lambda m: {}),
    (re.compile(r'^stop\s+meeting(?:\s+record(?:ing)?)?$', re.I),
     'stop_meeting',   lambda m: {}),
    (re.compile(r'^(?:last|get\s+)?meeting\s+(?:summary|notes|action\s+items)$', re.I),
     'get_last_meeting', lambda m: {}),
    (re.compile(r'^meeting\s+status$', re.I),
     'meeting_status', lambda m: {}),
    # ── Passwords ────────────────────────────────────────────────────────────
    (re.compile(r'^list\s+passwords?$', re.I),
     'list_passwords', lambda m: {}),
    # ── Google auth ──────────────────────────────────────────────────────────
    (re.compile(r'^(?:connect|setup|set\s+up)\s+(?:my\s+)?google(?:\s+account)?$', re.I),
     'setup_google_auth', lambda m: {}),
    (re.compile(r'^gmail\s+status$', re.I),
     'gmail_status',  lambda m: {}),
    # ── Context ──────────────────────────────────────────────────────────────
    (re.compile(r'^what\s+(?:am\s+i|are\s+you)\s+(?:working\s+on|doing)$', re.I),
     'get_context',   lambda m: {}),
    (re.compile(r'^(?:summarise|summarize)\s+(?:my\s+)?(?:work|context|screen)$', re.I),
     'summarise_context', lambda m: {}),
    # ── Image generation ─────────────────────────────────────────────────────
    (re.compile(r'^(?:list|show)\s+(?:generated\s+)?images?$', re.I),
     'list_generated_images', lambda m: {}),
    (re.compile(r'^(?:open|show)\s+last\s+image$', re.I),
     'open_last_image', lambda m: {}),
    # ── Desktop automation ───────────────────────────────────────────────────
    (re.compile(r'^(?:take\s+a?\s+)?screenshot$', re.I),
     'take_automation_screenshot', lambda m: {}),
    (re.compile(r'^mouse\s+(?:position|where)$', re.I),
     'get_mouse_position', lambda m: {}),
    # ── Productivity ─────────────────────────────────────────────────────────
    (re.compile(r'^(?:list\s+)?(?:my\s+)?(?:to[- ]?do|tasks?|todos?)$', re.I),
     'list_todos',         lambda m: {}),
    # pomodoro — entries consolidated in the Pomodoro section below
    (re.compile(r'^(?:list\s+)?(?:my\s+)?habits?(?:\s+(?:today|this\s+week))?$', re.I),
     'list_habits',        lambda m: {}),
    (re.compile(r'^(?:list\s+)?shopping(?:\s+list)?$', re.I),
     'list_shopping',      lambda m: {}),
    (re.compile(r'^(?:read\s+)?(?:today\'?s?\s+)?journal$', re.I),
     'read_journal',       lambda m: {'date': 'today'}),
    # ── Information ──────────────────────────────────────────────────────────
    (re.compile(r'^(?:bitcoin|btc)\s+price$', re.I),
     'get_crypto_price',   lambda m: {'coin': 'bitcoin'}),
    (re.compile(r'^(?:ethereum|eth)\s+price$', re.I),
     'get_crypto_price',   lambda m: {'coin': 'ethereum'}),
    (re.compile(r'^(?:price\s+of|crypto\s+price)\s+(.+)$', re.I),
     'get_crypto_price',   lambda m: {'coin': m.group(1).strip()}),
    (re.compile(r'^define\s+(.+)$', re.I),
     'define_word',        lambda m: {'word': m.group(1).strip()}),
    (re.compile(r'^wikipedia\s+(.+)$', re.I),
     'search_wikipedia',   lambda m: {'query': m.group(1).strip()}),
    # ── System ───────────────────────────────────────────────────────────────
    (re.compile(r'^(?:clipboard|clip)\s+history$', re.I),
     'get_clipboard_history', lambda m: {}),
    (re.compile(r'^(?:battery|battery\s+status)$', re.I),
     'get_battery_status', lambda m: {}),
    (re.compile(r'^(?:disk\s+(?:info|usage|space)|storage)$', re.I),
     'get_disk_info',      lambda m: {}),
    (re.compile(r'^(?:network|ip|my\s+ip)\s*(?:info|status|address)?$', re.I),
     'get_network_info',   lambda m: {}),
    (re.compile(r'^(?:system|health)\s+(?:report|status|health)$', re.I),
     'system_health_report', lambda m: {}),
    (re.compile(r'^generate\s+password(?:\s+(\d+)\s*chars?)?$', re.I),
     'generate_password',  lambda m: {'length': int(m.group(1)) if m.group(1) else 16}),
    (re.compile(r'^(?:list\s+)?scheduled\s+(?:tasks?|reminders?)$', re.I),
     'list_scheduled_tasks', lambda m: {}),
    (re.compile(r'^clean\s+(?:temp|temporary)\s*(?:files?)?$', re.I),
     'clean_temp_files',   lambda m: {'dry_run': False}),
    # ── Security ─────────────────────────────────────────────────────────────
    (re.compile(r'^list\s+(?:2fa|totp|authenticator)(?:\s+codes?)?$', re.I),
     'list_totp',          lambda m: {}),
    (re.compile(r'^security\s+(?:audit|check|report)$', re.I),
     'security_audit',     lambda m: {}),
    # ── GitHub ───────────────────────────────────────────────────────────────
    (re.compile(r'^(?:trending|trending\s+repos?|github\s+trending)$', re.I),
     'get_trending_repos', lambda m: {}),
    # ── Autonomous planner ────────────────────────────────────────────────────
    (re.compile(r'^(?:plan|autonomous(?:ly)?|godmode)\s+(.+)$', re.I),
     'autonomous_plan',    lambda m: {'goal': m.group(1).strip()}),
    # ── Reports ──────────────────────────────────────────────────────────────
    (re.compile(r'^(?:daily\s+)?briefing\s+(?:pdf|report)$', re.I),
     'generate_daily_briefing_pdf', lambda m: {}),
    (re.compile(r'^list\s+reports?$', re.I),
     'list_reports',       lambda m: {}),
    # ── Web / Communication ───────────────────────────────────────────────────
    (re.compile(r'^(?:list\s+)?(?:page\s+)?monitors?$', re.I),
     'list_monitors',      lambda m: {}),
    (re.compile(r'^(?:list\s+)?email\s+templates?$', re.I),
     'list_email_templates', lambda m: {}),
    # ── Budget ────────────────────────────────────────────────────────────────
    (re.compile(r'^(?:budget|expense)\s+report$', re.I),
     'budget_report',      lambda m: {}),
    (re.compile(r'^(?:list\s+)?(?:transactions?|expenses?)$', re.I),
     'list_transactions',  lambda m: {}),
    (re.compile(r'^(?:monthly\s+)?budget(?:\s+summary)?$', re.I),
     'monthly_summary',    lambda m: {}),
    # ── Focus Mode ────────────────────────────────────────────────────────────
    (re.compile(r'^(?:start\s+)?focus(?:\s+mode)?(?:\s+(\d+)\s*min(?:utes?)?)?$', re.I),
     'enable_focus_mode',  lambda m: {'duration_min': int(m.group(1)) if m.group(1) else 25}),
    (re.compile(r'^(?:stop|end|disable)\s+focus(?:\s+mode)?$', re.I),
     'disable_focus_mode', lambda m: {}),
    (re.compile(r'^focus\s+(?:status|time|remaining)$', re.I),
     'focus_status',       lambda m: {}),
    (re.compile(r'^(?:focus\s+)?history$', re.I),
     'focus_history',      lambda m: {}),
    # ── Alarms ────────────────────────────────────────────────────────────────
    (re.compile(r'^list\s+alarms?$', re.I),
     'list_alarms',        lambda m: {}),
    # ── Stocks ────────────────────────────────────────────────────────────────
    (re.compile(r'^(?:stock\s+)?(?:price\s+of|price)\s+([A-Z.]+)$', re.I),
     'get_stock_price',    lambda m: {'symbol': m.group(1).strip()}),
    (re.compile(r'^([A-Z]{2,5}(?:\.[A-Z]{2})?)\s+(?:stock\s+)?price$', re.I),
     'get_stock_price',    lambda m: {'symbol': m.group(1).strip()}),
    (re.compile(r'^(?:my\s+)?watchlist$', re.I),
     'get_watchlist',      lambda m: {}),
    # ── Countdowns ────────────────────────────────────────────────────────────
    (re.compile(r'^list\s+countdowns?$', re.I),
     'list_countdowns',    lambda m: {}),
    # ── Flashcards ────────────────────────────────────────────────────────────
    (re.compile(r'^(?:list\s+)?(?:flashcard\s+)?decks?$', re.I),
     'list_flashcard_decks', lambda m: {}),
    (re.compile(r'^(?:review|study)\s+(?:flashcards?|cards?)$', re.I),
     'review_flashcards',  lambda m: {}),
    # ── Random ────────────────────────────────────────────────────────────────
    (re.compile(r'^(?:tell\s+(?:me\s+)?a?\s*)?joke$', re.I),
     'tell_joke',          lambda m: {}),
    (re.compile(r'^(?:random\s+)?fact$', re.I),
     'random_fact',        lambda m: {}),
    (re.compile(r'^(?:random\s+)?quote$', re.I),
     'random_quote',       lambda m: {}),
    (re.compile(r'^(?:flip\s+)?(?:a\s+)?coin$', re.I),
     'flip_coin',          lambda m: {}),
    (re.compile(r'^(?:roll\s+)?(?:a\s+)?(?:dice?|d6|d20)$', re.I),
     'roll_dice',          lambda m: {'notation': '1d6'}),
    # ── App Usage ─────────────────────────────────────────────────────────────
    (re.compile(r'^(?:app\s+)?usage(?:\s+today)?$', re.I),
     'app_usage_today',    lambda m: {}),
    (re.compile(r'^(?:app\s+)?usage\s+(?:this\s+)?week$', re.I),
     'app_usage_weekly',   lambda m: {}),
    (re.compile(r'^productivity\s+(?:score|report)$', re.I),
     'productivity_score', lambda m: {}),
    # ── Clipboard Transform ────────────────────────────────────────────────────
    (re.compile(r'^clipboard\s+stats?$', re.I),
     'clipboard_stats',    lambda m: {}),
    # ── Text Utils ────────────────────────────────────────────────────────────
    (re.compile(r'^generate\s+qr(?:\s+code)?(?:\s+for\s+(.+))?$', re.I),
     'generate_qr',        lambda m: {'text': m.group(1) or ''}),
    # ── Habits ────────────────────────────────────────────────────────────────
    (re.compile(r'^(?:list\s+)?(?:my\s+)?habits?(?:\s+today)?$', re.I),
     'list_habits',        lambda m: {}),
    (re.compile(r'^habits?\s+today$', re.I),
     'habits_today',       lambda m: {}),
    (re.compile(r'^done\s+(.+)$', re.I),
     'complete_habit',     lambda m: {'name': m.group(1).strip()}),
    (re.compile(r'^complete(?:d)?\s+habit\s+(.+)$', re.I),
     'complete_habit',     lambda m: {'name': m.group(1).strip()}),
    # ── Pomodoro ──────────────────────────────────────────────────────────────
    (re.compile(r'^(?:start\s+)?pomodoro(?:\s+(.+))?$', re.I),
     'start_pomodoro',     lambda m: {'task': m.group(1) or 'focused work'}),
    (re.compile(r'^stop\s+pomodoro$', re.I),
     'stop_pomodoro',      lambda m: {}),
    (re.compile(r'^pomodoro\s+(?:status|time|remaining)$', re.I),
     'pomodoro_status',    lambda m: {}),
    # ── World Clock ───────────────────────────────────────────────────────────
    (re.compile(r'^(?:what(?:\'?s|\s+is)\s+the\s+time\s+in|time\s+in)\s+(.+)$', re.I),
     'world_time',         lambda m: {'location': m.group(1).strip()}),
    (re.compile(r'^world\s+clock$', re.I),
     'world_clock',        lambda m: {'cities': 'India,London,New York,Tokyo,Sydney,Dubai'}),
    # ── Dictionary ────────────────────────────────────────────────────────────
    (re.compile(r'^(?:define|definition\s+of)\s+(.+)$', re.I),
     'define_word',        lambda m: {'word': m.group(1).strip()}),
    (re.compile(r'^synonyms?\s+(?:for|of)\s+(.+)$', re.I),
     'synonyms',           lambda m: {'word': m.group(1).strip()}),
    (re.compile(r'^word\s+of\s+(?:the\s+)?day$', re.I),
     'word_of_the_day',    lambda m: {}),
    (re.compile(r'^rhymes?\s+(?:for|with)\s+(.+)$', re.I),
     'find_rhymes',        lambda m: {'word': m.group(1).strip()}),
    # ── Phone Remote ─────────────────────────────────────────────────────────
    (re.compile(r'^(?:phone|remote)\s+(?:link|url|qr|connect)$', re.I),
     'get_phone_remote_url', lambda m: {}),
    (re.compile(r'^(?:how\s+do\s+i\s+)?connect\s+(?:my\s+)?phone$', re.I),
     'get_phone_remote_url', lambda m: {}),
    # ── Advanced device control ────────────────────────────────────────────────
    (re.compile(r'^(?:get\s+)?(?:current\s+)?volume$', re.I),
     'get_volume',          lambda m: {}),
    (re.compile(r'^(?:volume|set\s+volume)\s+(?:to\s+)?(\d+)%?$', re.I),
     'set_volume',          lambda m: {'level': int(m.group(1))}),
    (re.compile(r'^(?:mute|unmute)(?:\s+(?:mic|microphone))?$', re.I),
     'mute_volume',         lambda m: {'mute': 'unmute' not in m.group(0).lower()}),
    (re.compile(r'^(?:mute|unmute)\s+mic(?:rophone)?$', re.I),
     'mute_microphone',     lambda m: {'mute': 'unmute' not in m.group(0).lower()}),
    (re.compile(r'^(?:get\s+)?brightness$', re.I),
     'get_brightness',      lambda m: {}),
    (re.compile(r'^brightness\s+(?:to\s+)?(\d+)%?$', re.I),
     'set_brightness',      lambda m: {'level': int(m.group(1))}),
    (re.compile(r'^(?:list\s+)?(?:running\s+)?(?:apps?|processes?)$', re.I),
     'list_running_apps',   lambda m: {}),
    (re.compile(r'^(?:kill|close|end)\s+(?:process\s+)?(.+)$', re.I),
     'kill_process',        lambda m: {'name': m.group(1).strip()}),
    (re.compile(r'^(?:list\s+)?(?:usb|drives?|external)$', re.I),
     'list_usb_devices',    lambda m: {}),
    (re.compile(r'^(?:list\s+)?(?:wifi|wi-fi)\s+networks?$', re.I),
     'list_wifi_networks',  lambda m: {}),
    (re.compile(r'^(?:uptime|system\s+uptime|how\s+long\s+on)$', re.I),
     'get_system_uptime',   lambda m: {}),
    (re.compile(r'^gpu\s+(?:info|status|specs?)$', re.I),
     'get_gpu_info',        lambda m: {}),
    (re.compile(r'^cpu\s+temp(?:erature)?$', re.I),
     'get_cpu_temperature', lambda m: {}),
    (re.compile(r'^(?:read\s+)?clipboard$', re.I),
     'read_clipboard_text', lambda m: {}),
    (re.compile(r'^(?:shutdown|shut\s+down)(?:\s+in\s+(\d+)\s*(?:sec|seconds?|min|minutes?))?$', re.I),
     'shutdown_now',        lambda m: {'delay': int(m.group(1) or 30)*
                                      (60 if 'min' in (m.group(0) or '').lower() else 1)
                                      if m.group(1) else 30}),
    (re.compile(r'^cancel\s+(?:shutdown|restart)$', re.I),
     'cancel_shutdown',     lambda m: {}),
    (re.compile(r'^restart(?:\s+(?:pc|computer|now))?$', re.I),
     'restart_now',         lambda m: {'delay': 30}),
    (re.compile(r'^hibernate(?:\s+(?:pc|now))?$', re.I),
     'hibernate',           lambda m: {}),
    (re.compile(r'^(?:wifi|wi-fi|wireless)\s+password$', re.I),
     'get_wifi_password',   lambda m: {}),
    # ── Licensing ─────────────────────────────────────────────────────────────
    (re.compile(r'^(?:check|my|show)\s+plan$', re.I),
     'check_plan',         lambda m: {}),
    (re.compile(r'^(?:upgrade|pricing|buy\s+pro|get\s+pro)$', re.I),
     'upgrade_plan',       lambda m: {}),
    (re.compile(r'^activate\s+license\s+(.+)$', re.I),
     'activate_license',   lambda m: {'license_key': m.group(1).strip()}),
    (re.compile(r'^redeem\s+(?:code\s+)?([A-Z0-9]+)$', re.I),
     'redeem_discount_code', lambda m: {'code': m.group(1).strip()}),
    (re.compile(r'^approve\s+jarvis21\s+([A-Z0-9]+)$', re.I),
     'approve_jarvis21',   lambda m: {'token': m.group(1).strip()}),
    (re.compile(r'^deny\s+jarvis21\s+([A-Z0-9]+)$', re.I),
     'deny_jarvis21',      lambda m: {'token': m.group(1).strip()}),
    (re.compile(r'^(?:list\s+)?jarvis21\s+(?:requests?|pending)$', re.I),
     'list_jarvis21_requests', lambda m: {}),
    # ── Windows Integration ────────────────────────────────────────────────────
    (re.compile(r'^(?:register|add)\s+(?:to\s+)?(?:windows\s+)?startup$', re.I),
     'register_windows_startup', lambda m: {}),
    (re.compile(r'^(?:set|register)\s+(?:as\s+)?default\s+(?:assistant|agent)$', re.I),
     'register_as_default_assistant', lambda m: {}),
    (re.compile(r'^(?:open\s+)?windows\s+(?:contacts?|people)$', re.I),
     'get_windows_contacts',  lambda m: {}),
    (re.compile(r'^(?:list\s+)?(?:installed\s+)?(?:apps?|programs?)$', re.I),
     'get_installed_apps',    lambda m: {}),
    (re.compile(r'^open\s+(?:default\s+apps?|settings)\s*(?:settings)?$', re.I),
     'open_windows_settings', lambda m: {'page': 'default apps'}),
    (re.compile(r'^open\s+(?:windows\s+)?contacts?$', re.I),
     'open_windows_app',      lambda m: {'app': 'contacts'}),
]


class Agent:
    def __init__(self):
        self._brain = get_brain()
        self._tools: dict = {}

    def register(self, name: str, description: str, parameters: dict, fn):
        self._tools[name] = {"description": description,
                             "parameters": parameters, "fn": fn}

    def _call_tool(self, name: str, args: dict) -> str:
        if name not in self._tools:
            return f"Unknown tool: {name}"
        try:
            return str(self._tools[name]["fn"](**args))[:2000]
        except Exception as e:
            return f"Tool error ({name}): {e}"

    def _fast_dispatch(self, text: str) -> str | None:
        """Try to handle the command without any LLM call."""
        for pattern, tool_name, arg_fn in _FAST:
            m = pattern.match(text.strip())
            if m and tool_name in self._tools:
                try:
                    return self._call_tool(tool_name, arg_fn(m))
                except Exception:
                    pass
        return None

    def run(self, user_input: str, history: list = None,
            context: str = "", on_step=None) -> str:

        # ── 1. Fast dispatch: zero-LLM for known commands ─────────────────
        fast_result = self._fast_dispatch(user_input)
        if fast_result is not None:
            return fast_result

        # ── 2. No tools needed → direct chat ──────────────────────────────
        if not needs_tool(user_input):
            if not self._tools:
                return self._brain.quick(user_input, max_tokens=180)
            messages = (history or []) + [{"role": "user", "content": user_input}]
            return self._brain.chat(messages, max_tokens=220)

        # ── 3. ReAct tool loop ─────────────────────────────────────────────
        history = history or []
        tool_descs = "\n".join(
            f"- {n}: {info['description']}"
            for n, info in self._tools.items()
        )
        system = (
            config.PERSONA + "\n\n"
            "To call a tool output ONLY this JSON on a single line:\n"
            '{"tool":"name","args":{...}}\n'
            "After receiving the result, give your final answer in plain text.\n"
            "Keep answers to 1-2 sentences.\n\n"
            f"Tools:\n{tool_descs}"
        )
        messages = list(history) + [{"role": "user", "content": user_input}]

        for step in range(config.AGENT_MAX_STEPS):
            # Use tight token budget for tool-routing steps
            is_last = (step == config.AGENT_MAX_STEPS - 1)
            max_tok  = 220 if is_last else 120

            response = self._brain.chat(messages, system=system,
                                        smart=False, max_tokens=max_tok)

            # Parse tool call from response
            tool_call = None
            for line in response.splitlines():
                line = line.strip()
                if line.startswith("{") and '"tool"' in line:
                    try:
                        tool_call = json.loads(line)
                        break
                    except Exception:
                        pass

            if tool_call is None:
                return response          # plain-text final answer

            tool_name = tool_call.get("tool", "")
            tool_args = tool_call.get("args", {})

            if on_step:
                try:
                    on_step(f"[{tool_name}]")
                except Exception:
                    pass

            tool_result = self._call_tool(tool_name, tool_args)
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user",
                             "content": f"[{tool_name} result]: {tool_result}"})

        return self._brain.chat(messages, system=system, max_tokens=220)


_agent = None


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent()
    return _agent
