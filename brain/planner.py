"""
Autonomous Multi-Step Planner — GodMode agentic loop.

Given a high-level goal, JARVIS:
1. Breaks it into an ordered plan of steps
2. Executes each step using registered tools / the agent
3. Evaluates success at each step before proceeding
4. Reports progress in real time
5. Retries failed steps (up to 2 times)
6. Produces a final summary report

Usage:
    from brain.planner import Planner
    p = Planner(jarvis_handle=j.handle, on_progress=callback)
    result = p.run("Research the top 5 AI papers this week and email me a summary")
"""
import json
import re
import threading
import time
from datetime import datetime
from typing import Callable

from brain.core import get_brain
from tools.registry import all_tools


_MAX_STEPS    = 12
_MAX_RETRIES  = 2
_STEP_TIMEOUT = 60   # seconds per step


class Planner:
    def __init__(
        self,
        jarvis_handle: Callable[[str], str],
        on_progress: Callable[[str, str], None] | None = None,
    ):
        """
        jarvis_handle  : Jarvis.handle(text) → str
        on_progress    : callback(message, level) where level = info/ok/warn/error
        """
        self._handle      = jarvis_handle
        self._on_progress = on_progress or (lambda m, l: print(f"[Planner/{l}] {m}"))
        self._brain       = get_brain()
        self._cancelled   = threading.Event()

    def _log(self, msg: str, level: str = "info"):
        self._on_progress(msg, level)

    def cancel(self):
        self._cancelled.set()

    # ── Plan generation ────────────────────────────────────────────────────────
    def _make_plan(self, goal: str) -> list[dict]:
        """Ask LLM to decompose goal into ordered steps with tool suggestions."""
        tool_names = list(all_tools().keys())[:40]  # first 40 registered tools
        tools_str  = ", ".join(tool_names)

        prompt = f"""You are an AI planner. Break this goal into {_MAX_STEPS} or fewer concrete, executable steps.

Goal: {goal}

Available JARVIS tools: {tools_str}

Output ONLY a JSON array of steps, each with:
- "step": short description (max 80 chars)
- "tool": the best tool name to use (or "chat" if conversational)
- "input": exact text/args to pass

Example:
[
  {{"step": "Search for AI papers", "tool": "web_search", "input": "top AI research papers 2024"}},
  {{"step": "Summarise findings", "tool": "chat", "input": "summarise these papers: {{result}}"}}
]

Output ONLY valid JSON, no markdown."""

        raw = self._brain.quick(prompt, max_tokens=800)
        # Extract JSON array
        m = re.search(r"\[.*\]", raw, re.S)
        if not m:
            return [{"step": goal, "tool": "chat", "input": goal}]
        try:
            steps = json.loads(m.group())
            return [s for s in steps if isinstance(s, dict) and "step" in s][:_MAX_STEPS]
        except Exception:
            return [{"step": goal, "tool": "chat", "input": goal}]

    # ── Single step execution ──────────────────────────────────────────────────
    def _execute_step(self, step: dict, prev_result: str) -> str:
        tool_name = step.get("tool", "chat")
        raw_input = step.get("input", "")
        # Inject previous result
        raw_input = raw_input.replace("{result}", prev_result[:500] if prev_result else "")
        raw_input = raw_input.replace("{prev}", prev_result[:500] if prev_result else "")

        tools = all_tools()
        if tool_name in tools and tool_name != "chat":
            fn = tools[tool_name]["fn"]
            try:
                # Try to call with the input as a single positional arg
                # or as 'query' / 'text' keyword
                params = tools[tool_name].get("parameters",{}).get("properties",{})
                first_key = next(iter(params), None)
                if first_key:
                    return fn(**{first_key: raw_input})
                return fn(raw_input)
            except Exception:
                try: return fn(raw_input)
                except Exception as e: return f"Tool error: {e}"
        else:
            # Use Jarvis chat
            return self._handle(raw_input)

    # ── Evaluate step success ──────────────────────────────────────────────────
    def _eval_step(self, step: dict, result: str) -> bool:
        """Ask LLM if the step succeeded. Fast heuristic first."""
        fail_keywords = ["error:", "could not", "failed", "not found", "exception",
                         "traceback", "404", "403", "none", "no results", "unable"]
        low = result.lower()
        if any(k in low for k in fail_keywords) and len(result) < 200:
            return False
        return True

    # ── Main run loop ──────────────────────────────────────────────────────────
    def run(self, goal: str) -> str:
        start_ts = time.time()
        self._cancelled.clear()
        self._log(f"🎯 Planning: {goal}", "info")

        steps = self._make_plan(goal)
        self._log(f"📋 Generated {len(steps)}-step plan", "ok")
        for i, s in enumerate(steps, 1):
            self._log(f"  Step {i}: {s['step']}", "info")

        results:    list[str]  = []
        step_log:   list[dict] = []
        prev_result = ""

        for i, step in enumerate(steps, 1):
            if self._cancelled.is_set():
                self._log("⛔ Plan cancelled.", "warn")
                break

            self._log(f"\n▶ Step {i}/{len(steps)}: {step['step']}", "info")
            success = False

            for attempt in range(1, _MAX_RETRIES + 2):
                if self._cancelled.is_set(): break
                try:
                    result = self._execute_step(step, prev_result)
                except Exception as e:
                    result = f"Error: {e}"

                success = self._eval_step(step, result)
                status  = "✅" if success else "⚠️"
                self._log(f"{status} {result[:200]}", "ok" if success else "warn")

                if success:
                    break
                if attempt <= _MAX_RETRIES:
                    self._log(f"  ↻ Retrying ({attempt}/{_MAX_RETRIES})…", "warn")
                    time.sleep(1)

            results.append(result)
            prev_result = result
            step_log.append({
                "step":    step["step"],
                "result":  result[:500],
                "success": success,
                "attempt": attempt,
            })

        # ── Final summary ──────────────────────────────────────────────────────
        elapsed = round(time.time() - start_ts, 1)
        succeeded = sum(1 for s in step_log if s["success"])
        self._log(f"\n✅ Plan complete — {succeeded}/{len(step_log)} steps succeeded in {elapsed}s", "ok")

        # Ask LLM to synthesise a final answer
        results_txt = "\n".join(
            f"Step {i+1} ({s['step']}): {s['result']}"
            for i, s in enumerate(step_log)
        )
        summary_prompt = (
            f"Goal: {goal}\n\n"
            f"Steps completed:\n{results_txt}\n\n"
            f"Provide a concise final answer or summary of what was accomplished."
        )
        final = self._brain.quick(summary_prompt, max_tokens=500)
        self._log(f"\n📝 Summary:\n{final}", "ok")
        return final


# ── Register as a JARVIS tool ──────────────────────────────────────────────────
_planner_instance: Planner | None = None

def get_planner(handle_fn: Callable | None = None,
                progress_fn: Callable | None = None) -> Planner:
    global _planner_instance
    if _planner_instance is None and handle_fn is not None:
        _planner_instance = Planner(handle_fn, progress_fn)
    return _planner_instance


def register_planner_tool(jarvis_instance):
    """Called from jarvis.py after Jarvis is initialised."""
    from tools.registry import register

    @register(
        name="autonomous_plan",
        description=(
            "Autonomously break a complex goal into steps and execute them. "
            "Use for multi-step tasks like: research + summarise + email, "
            "find info + create report + save note, etc."
        ),
        parameters={"type":"object","properties":{
            "goal":{"type":"string","description":"The high-level goal to accomplish"},
        },"required":["goal"]},
    )
    def autonomous_plan(goal: str) -> str:
        planner = Planner(
            jarvis_handle=jarvis_instance.handle,
            on_progress=lambda m, l: (
                print(f"[Planner] {m}"),
                jarvis_instance._log(m, l),
            ),
        )
        # Run in same thread (blocking) — Jarvis already in executor
        return planner.run(goal)
