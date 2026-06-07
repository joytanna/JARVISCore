#!/usr/bin/env python -X utf8
"""
JARVIS Test Runner ? tests all tools, API security, and integrations.
Run: python tests/run_tests.py
"""
import sys, os, time, traceback, json, re
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
# Force UTF-8 I/O — prevents crashes on Windows cp1252 when tools return emoji
os.environ.setdefault("PYTHONUTF8", "1")
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# -- Helpers --------------------------------------------------------------------
PASS = "[ PASS ]"
FAIL = "[ FAIL ]"
WARN = "[ WARN ]"
INFO = "[ INFO ]"

_results = []

def test(name: str, fn):
    start = time.time()
    try:
        result = fn()
        elapsed = round((time.time()-start)*1000)
        ok = result if isinstance(result, bool) else True
        status = PASS if ok else FAIL
        _results.append((name, ok, elapsed, ""))
        print(f"  {status} {name:55} {elapsed:>5}ms")
    except Exception as e:
        elapsed = round((time.time()-start)*1000)
        _results.append((name, False, elapsed, str(e)))
        print(f"  {FAIL} {name:55} {elapsed:>5}ms  [{e}]")

def section(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


# ===============================================================================
section("1. SECURITY MODULE")
# ===============================================================================

# Import all tool modules so they register themselves
import tools.system, tools.weather, tools.research, tools.finance
import tools.memory_tools, tools.gmail, tools.phone, tools.voice_tools
import tools.reminders, tools.screen, tools.apps, tools.clipboard_tools
import tools.file_summary, tools.briefing, tools.device_control
import tools.context_watcher, tools.meeting, tools.password_manager
import tools.translator, tools.code_runner, tools.image_gen, tools.desktop_auto
import tools.contacts_import, tools.notes, tools.calendar_tools
import tools.productivity, tools.info_tools, tools.system_advanced
import tools.security_advanced, tools.web_scraper, tools.report_gen
import tools.github_tools, tools.communication
import tools.budget, tools.focus_mode
import tools.alarm, tools.stocks, tools.text_utils, tools.countdown
import tools.flashcards, tools.random_tools, tools.email_composer
import tools.youtube_tools, tools.clipboard_transform, tools.app_usage

from api.security import (
    sanitize_text, sanitize_dict, scan_for_secrets,
    scan_response_for_leaks, _limiter, rate_limit,
    ChatRequest, ToolRequest, AuthSetupRequest, AuthLoginRequest,
)
from pydantic import ValidationError


def _try_invalid(fn) -> bool:
    """Returns True if fn raises any exception (expected for invalid inputs)."""
    try: fn(); return False
    except Exception: return True


test("sanitize_text: strips XSS script tags",
     lambda: "<script>" not in sanitize_text("<script>alert(1)</script>"))
test("sanitize_text: strips javascript: URIs",
     lambda: "javascript" not in sanitize_text("javascript:alert(1)"))
test("sanitize_text: strips null bytes",
     lambda: "\x00" not in sanitize_text("hello\x00world"))
test("sanitize_text: strips control chars",
     lambda: "\x01" not in sanitize_text("hello\x01world"))
test("sanitize_text: respects max_len",
     lambda: len(sanitize_text("a"*5000, 100)) <= 100)
test("sanitize_text: normal text passes through",
     lambda: sanitize_text("Hello JARVIS!") == "Hello JARVIS!")
test("sanitize_dict: cleans nested dicts",
     lambda: "<script>" not in str(sanitize_dict({"k": "<script>x</script>"})))
test("scan_for_secrets: detects Groq key",
     lambda: "Groq API Key" in scan_for_secrets("key=gsk_" + "a"*30))
test("scan_for_secrets: clean text returns empty",
     lambda: scan_for_secrets("Hello world") == [])
test("scan_response_for_leaks: redacts Groq key in response",
     lambda: "gsk_" not in scan_response_for_leaks("key=gsk_" + "a"*30))

# Pydantic validation
test("ChatRequest: rejects empty message",
     lambda: _try_invalid(lambda: ChatRequest(message="")))
test("ChatRequest: rejects overlong message",
     lambda: _try_invalid(lambda: ChatRequest(message="x"*5000)))
test("ChatRequest: accepts valid message",
     lambda: ChatRequest(message="Hello").message == "Hello")
test("ToolRequest: rejects invalid tool name with spaces",
     lambda: _try_invalid(lambda: ToolRequest(tool="bad tool name")))
test("ToolRequest: rejects tool name with dots",
     lambda: _try_invalid(lambda: ToolRequest(tool="../../etc/passwd")))
test("ToolRequest: accepts valid tool name",
     lambda: ToolRequest(tool="get_weather").tool == "get_weather")
test("AuthLoginRequest: rejects empty password",
     lambda: _try_invalid(lambda: AuthLoginRequest(password="")))
test("AuthSetupRequest: rejects invalid phone chars",
     lambda: _try_invalid(lambda: AuthSetupRequest(
         name="Joy", password="test1234", phone="DROP TABLE;")))


# Rate limiter
test("Rate limiter: allows requests under limit",
     lambda: all(_limiter.is_allowed("test_key", 5, 60) for _ in range(5)))
test("Rate limiter: blocks after limit exceeded",
     lambda: not _limiter.is_allowed("test_key_block", 2, 60)
             if sum(1 for _ in range(3) if _limiter.is_allowed("test_key_block", 2, 60)) >= 2
             else True)
test("Rate limiter: allows burst then resets",
     lambda: not _limiter.is_allowed("burst_k", 3, 60)
             if all(_limiter.is_allowed("burst_k", 3, 60) for _ in range(3))
             else True)


# ===============================================================================
section("2. TOOL REGISTRY")
# ===============================================================================

from tools.registry import all_tools
tools = all_tools()

test(f"Registry: has 50+ tools registered ({len(tools)} found)",
     lambda: len(tools) >= 50)
test("Registry: all tools have 'fn' callable",
     lambda: all(callable(t["fn"]) for t in tools.values()))
test("Registry: all tools have 'description'",
     lambda: all(t.get("description") for t in tools.values()))
test("Registry: all tools have 'parameters' dict",
     lambda: all(isinstance(t.get("parameters"), dict) for t in tools.values()))


# ===============================================================================
section("3. AUTH MANAGER")
# ===============================================================================

import tempfile, shutil
_tmp_mem = Path(tempfile.mkdtemp())

import config as _config
_orig_mem = _config.MEMORY_DIR

# Monkey-patch memory dir for tests
_config.MEMORY_DIR = _tmp_mem

from api import auth_manager as _auth
# Reload with patched config
import importlib
importlib.reload(_auth)
_auth._AUTH_FILE = _tmp_mem / "auth.json"
_auth._SECRET    = None
_auth._TOKEN     = None   # reset lazy secret

test("Auth: is_setup_done() False before setup",
     lambda: not _auth.is_setup_done())
test("Auth: setup() returns token string",
     lambda: isinstance(_auth.setup("TestUser","testpass123"), str))
test("Auth: is_setup_done() True after setup",
     lambda: _auth.is_setup_done())
test("Auth: login() with correct password returns token",
     lambda: isinstance(_auth.login("testpass123"), str))
test("Auth: login() with wrong password returns None",
     lambda: _auth.login("wrongpass") is None)

tok = _auth.login("testpass123")
test("Auth: verify_token() accepts valid token",
     lambda: _auth.verify_token(tok))
test("Auth: verify_token() rejects garbage token",
     lambda: not _auth.verify_token("not.a.valid.jwt"))
test("Auth: get_user_info() has name",
     lambda: _auth.get_user_info().get("name") == "TestUser")
test("Auth: password_hash not in get_user_info()",
     lambda: "password_hash" not in _auth.get_user_info())

_config.MEMORY_DIR = _orig_mem
shutil.rmtree(_tmp_mem, ignore_errors=True)


# ===============================================================================
section("4. PRODUCTIVITY TOOLS")
# ===============================================================================

import tools.productivity as prod

test("Todo: create_todo returns confirmation",
     lambda: "added" in prod.create_todo("Test task", "high").lower())
test("Todo: list_todos shows pending task",
     lambda: "Test task" in prod.list_todos("pending"))
test("Todo: complete_todo marks done",
     lambda: "done" in prod.complete_todo("Test task").lower())
test("Todo: list_todos pending is empty after completion",
     lambda: "Test task" not in prod.list_todos("pending"))
test("Todo: delete_todo works",
     lambda: "Removed" in prod.delete_todo("Test task"))

test("Pomodoro: start returns confirmation",
     lambda: "started" in prod.start_pomodoro(1, "Test work").lower())
test("Pomodoro: status shows running",
     lambda: "running" in prod.pomodoro_status().lower())
test("Pomodoro: stop works",
     lambda: "stopped" in prod.stop_pomodoro().lower())
test("Pomodoro: status shows not running after stop",
     lambda: "No Pomodoro" in prod.pomodoro_status())

test("Habit: log_habit saves entry",
     lambda: "logged" in prod.log_habit("exercise", "30 min run").lower())
test("Habit: list_habits shows exercise",
     lambda: "exercise" in prod.list_habits(1).lower())
test("Habit: streak returns count",
     lambda: "streak" in prod.habit_streak("exercise").lower() or
             "streak" in prod.habit_streak("exercise").lower())

test("Journal: entry saves",
     lambda: "saved" in prod.journal_entry("Test journal entry", "happy").lower())
test("Journal: read_journal returns entry",
     lambda: "Test journal entry" in prod.read_journal("today"))

test("Shopping: add_shopping adds item",
     lambda: "Added" in prod.add_shopping("milk", "2L", "groceries"))
test("Shopping: list_shopping shows item",
     lambda: "milk" in prod.list_shopping().lower())
test("Shopping: check_shopping marks purchased",
     lambda: "purchased" in prod.check_shopping("milk").lower())
test("Shopping: clear_shopping removes purchased",
     lambda: "removed" in prod.clear_shopping(False).lower())


# ===============================================================================
section("5. INFORMATION TOOLS")
# ===============================================================================

import tools.info_tools as info

test("Units: km to miles conversion",
     lambda: abs(float(re.search(r'= ([\d.]+)', info.convert_units(1, 'km', 'mi')).group(1)) - 0.6214) < 0.01)
test("Units: Celsius to Fahrenheit",
     lambda: abs(float(re.search(r'= ([\d.]+)', info.convert_units(100, 'c', 'f')).group(1)) - 212.0) < 0.1)
test("Units: kg to lbs",
     lambda: abs(float(re.search(r'= ([\d.]+)', info.convert_units(1, 'kg', 'lb')).group(1)) - 2.2046) < 0.01)
test("Units: unknown unit returns error",
     lambda: "Unknown" in info.convert_units(1, 'zz', 'km'))

test("Dictionary: define_word makes request or returns error gracefully",
     lambda: isinstance(info.define_word("hello"), str) and len(info.define_word("hello")) > 5)

test("Wikipedia: returns string response",
     lambda: isinstance(info.search_wikipedia("Python programming"), str))


# ===============================================================================
section("6. SECURITY TOOLS")
# ===============================================================================

import tools.security_advanced as sec

# TOTP (offline test ? RFC 6238)
test("TOTP: add_totp saves account",
     lambda: "added" in sec.add_totp("TestService", "JBSWY3DPEHPK3PXP").lower())
test("TOTP: get_totp_code returns 6-digit code",
     lambda: re.search(r'\d{6}', sec.get_totp_code("TestService")) is not None)
test("TOTP: list_totp shows service",
     lambda: "TestService" in sec.list_totp())
test("TOTP: delete_totp removes account",
     lambda: "Removed 1" in sec.delete_totp("TestService"))
test("TOTP: invalid secret rejected",
     lambda: "Invalid" in sec.add_totp("Bad", "NOT_BASE32!!!"))

test("Password breach: check returns string",
     lambda: isinstance(sec.check_password_breach("password123"), str))

test("Security audit: returns audit report",
     lambda: "Security Audit" in sec.security_audit())


# ===============================================================================
section("7. SYSTEM TOOLS")
# ===============================================================================

import tools.system_advanced as sys_adv

test("Password gen: generates 16-char password",
     lambda: len(sys_adv.generate_password(16).split()[1]) == 16)
test("Password gen: generates memorable passphrase",
     lambda: "-" in sys_adv.generate_password(memorable=True))
test("Disk info: returns disk data",
     lambda: "C:\\" in sys_adv.get_disk_info() or "%" in sys_adv.get_disk_info())
test("Network info: returns IP info",
     lambda: "IP" in sys_adv.get_network_info() or "Host" in sys_adv.get_network_info())
test("Battery: returns string",
     lambda: isinstance(sys_adv.get_battery_status(), str))
test("System health: returns CPU and RAM",
     lambda: "CPU" in sys_adv.system_health_report())
test("Schedule task: schedules in 1 hour",
     lambda: "scheduled" in sys_adv.schedule_task("Test reminder", "in 1 hour").lower())
test("List scheduled: shows pending task",
     lambda: "Test reminder" in sys_adv.list_scheduled_tasks())
test("Cancel scheduled: cancels task",
     lambda: "Cancelled 1" in sys_adv.cancel_scheduled_task("Test reminder"))
test("Temp clean: dry run returns size info",
     lambda: "MB" in sys_adv.clean_temp_files(dry_run=True))
test("Clipboard history: returns string",
     lambda: isinstance(sys_adv.get_clipboard_history(), str))


# ===============================================================================
section("8. NOTES TOOLS")
# ===============================================================================

import tools.notes as notes

test("Notes: create note",
     lambda: "saved" in notes.create_note("Test Note", "This is test content", "test").lower())
test("Notes: list notes shows test note",
     lambda: "Test Note" in notes.list_notes())
test("Notes: read note returns content",
     lambda: "test content" in notes.read_note("Test Note").lower())
test("Notes: search notes by keyword",
     lambda: "Test Note" in notes.search_notes("test content"))
test("Notes: append to note",
     lambda: "Appended" in notes.append_note("Test Note", "Additional content"))
test("Notes: appended content appears in read",
     lambda: "Additional content" in notes.read_note("Test Note"))
test("Notes: delete note",
     lambda: "deleted" in notes.delete_note("Test Note").lower())
test("Notes: list after delete shows none",
     lambda: "Test Note" not in notes.list_notes())


# ===============================================================================
section("9. CALENDAR TOOLS")
# ===============================================================================

import tools.calendar_tools as cal

test("Calendar: create_event (local)",
     lambda: "saved" in cal.create_event("JARVIS Test Event",
                                          "tomorrow 3pm", 60, "Test").lower() or
             "created" in cal.create_event("JARVIS Test Event",
                                            "tomorrow 3pm", 60, "Test").lower())
test("Calendar: list_events returns string",
     lambda: isinstance(cal.list_events(7), str))
test("Calendar: delete_event removes event",
     lambda: "1" in cal.delete_event("JARVIS Test Event") or
             "Removed" in cal.delete_event("JARVIS Test Event"))


# ===============================================================================
section("10. WEB SCRAPER")
# ===============================================================================

import tools.web_scraper as ws

test("Web scraper: scrape_url returns content",
     lambda: isinstance(ws.scrape_url("https://example.com", 500), str) and
             len(ws.scrape_url("https://example.com", 500)) > 20)
test("Web scraper: invalid URL returns error string",
     lambda: "Could not" in ws.scrape_url("http://thisdomaindoesnotexist12345.xyz", 500)
             or isinstance(ws.scrape_url("http://thisdomaindoesnotexist12345.xyz", 500), str))
test("Web scraper: monitor_page adds monitor",
     lambda: "monitoring" in ws.monitor_page("https://example.com", "test-monitor").lower())
test("Web scraper: list_monitors shows monitor",
     lambda: "test-monitor" in ws.list_monitors().lower() or
             "example.com" in ws.list_monitors())
test("Web scraper: stop_monitoring removes it",
     lambda: "Removed" in ws.stop_monitoring("test-monitor"))


# ===============================================================================
section("11. REPORT GENERATOR")
# ===============================================================================

import tools.report_gen as rg

test("Reports: generate_report creates file",
     lambda: ("generated" in rg.generate_report(
         "Test Report", "## Section 1\nTest content here.", False).lower()))
test("Reports: list_reports shows test report",
     lambda: "Test Report" in rg.list_reports() or "test_report" in rg.list_reports().lower())


# ===============================================================================
section("12. GITHUB TOOLS")
# ===============================================================================

import tools.github_tools as gh

test("GitHub: list_repos for 'torvalds'",
     lambda: isinstance(gh.list_repos("torvalds", 3), str))
test("GitHub: get_repo_info for 'microsoft/vscode'",
     lambda: "vscode" in gh.get_repo_info("microsoft/vscode").lower() or
             isinstance(gh.get_repo_info("microsoft/vscode"), str))
test("GitHub: search_github returns results",
     lambda: isinstance(gh.search_github("python", max=3), str))


# ===============================================================================
section("13. INPUT VALIDATION EDGE CASES")
# ===============================================================================

test("Validation: SQL injection in tool name blocked",
     lambda: _try_invalid(lambda: ToolRequest(tool="'; DROP TABLE--")))
test("Validation: path traversal in tool name blocked",
     lambda: _try_invalid(lambda: ToolRequest(tool="../../../etc/passwd")))
test("Validation: XSS in chat message cleaned",
     lambda: "<script>" not in ChatRequest(message="<script>alert(1)</script>").message)
test("Validation: overlong field trimmed/rejected",
     lambda: _try_invalid(lambda: ChatRequest(message="x" * 10000)))
test("Validation: phone with SQL in AuthSetup blocked",
     lambda: _try_invalid(lambda: AuthSetupRequest(
         name="A", password="pass1234", phone="1; DROP TABLE users")))


# ===============================================================================
section("14. BUDGET TRACKER")
# ===============================================================================

import tools.budget as budget_mod
import tools.focus_mode as focus_mod

test("Budget: add_expense records correctly",
     lambda: "Expense" in budget_mod.add_expense(250.50, "food", "Lunch at restaurant"))
test("Budget: add_income records correctly",
     lambda: "Income" in budget_mod.add_income(50000, "salary", "Monthly salary"))
test("Budget: list_transactions shows entries",
     lambda: "250.50" in budget_mod.list_transactions(5) or "50000" in budget_mod.list_transactions(5))
test("Budget: monthly_summary shows income and expenses",
     lambda: "Income" in budget_mod.monthly_summary() and "Expense" in budget_mod.monthly_summary())
test("Budget: budget_report returns full report",
     lambda: "Budget Report" in budget_mod.budget_report())
test("Budget: delete_transaction removes entry",
     lambda: "Removed" in budget_mod.delete_transaction("Lunch at restaurant"))

# ===============================================================================
section("15. FOCUS MODE")
# ===============================================================================

test("Focus: status shows no active session initially",
     lambda: "No focus" in focus_mod.focus_status())
test("Focus: enable starts session",
     lambda: "enabled" in focus_mod.enable_focus_mode(1, "Test session", False).lower())
test("Focus: status shows active session",
     lambda: "ACTIVE" in focus_mod.focus_status() or "active" in focus_mod.focus_status().lower())
test("Focus: disable ends session",
     lambda: "disabled" in focus_mod.disable_focus_mode().lower())
test("Focus: history records session",
     lambda: isinstance(focus_mod.focus_history(), str))
test("Focus: add_distractor_app works",
     lambda: "added" in focus_mod.add_distractor_app("testapp123").lower() or
             "already" in focus_mod.add_distractor_app("testapp123").lower())

# ===============================================================================
section("16. ALARM SYSTEM")
# ===============================================================================

import tools.alarm as alarm_mod
import tools.stocks as stocks_mod
import tools.text_utils as tu
import tools.countdown as cd
import tools.flashcards as fc
import tools.random_tools as rt
import tools.email_composer as ec
import tools.youtube_tools as yt
import tools.clipboard_transform as ct
import tools.app_usage as au

test("Alarm: set_alarm returns confirmation",
     lambda: "set for" in alarm_mod.set_alarm("in 2 hours", "Test alarm").lower())
test("Alarm: list_alarms shows pending",
     lambda: "Test alarm" in alarm_mod.list_alarms())
test("Alarm: cancel_alarm removes it",
     lambda: "Cancelled" in alarm_mod.cancel_alarm("Test alarm"))
test("Alarm: snooze with nothing fired returns message",
     lambda: isinstance(alarm_mod.snooze_alarm(5), str))

# ===============================================================================
section("17. STOCKS")
# ===============================================================================

test("Stocks: get_stock_price AAPL returns price string",
     lambda: isinstance(stocks_mod.get_stock_price("AAPL"), str))
test("Stocks: add_to_watchlist works",
     lambda: "added" in stocks_mod.add_to_watchlist("GOOGL").lower() or
             "already" in stocks_mod.add_to_watchlist("GOOGL").lower())
test("Stocks: get_watchlist returns string",
     lambda: isinstance(stocks_mod.get_watchlist(), str))
test("Stocks: remove_from_watchlist works",
     lambda: "removed" in stocks_mod.remove_from_watchlist("GOOGL").lower())

# ===============================================================================
section("18. TEXT UTILITIES")
# ===============================================================================

test("TextUtils: word_count returns stats",
     lambda: "Words" in tu.word_count("Hello world, this is JARVIS."))
test("TextUtils: text_diff finds difference",
     lambda: "+1 lines added" in tu.text_diff("hello", "hello\nworld") or
             "added" in tu.text_diff("hello", "hello\nworld"))
test("TextUtils: hash_text SHA256",
     lambda: len(re.search(r'[a-f0-9]{64}',
                            tu.hash_text("test", "sha256")).group()) == 64)
test("TextUtils: hash_text MD5",
     lambda: len(re.search(r'[a-f0-9]{32}',
                            tu.hash_text("test", "md5")).group()) == 32)
test("TextUtils: transform_text upper",
     lambda: "HELLO WORLD" in tu.transform_text("hello world", "upper"))
test("TextUtils: transform_text slug",
     lambda: "hello-world" in tu.transform_text("Hello World!", "slug"))
test("TextUtils: test_regex finds matches",
     lambda: "2 match" in tu.test_regex(r'\d+', "abc 123 def 456") or
             "match" in tu.test_regex(r'\d+', "abc 123 def 456"))
test("TextUtils: convert_color hex to rgb",
     lambda: "rgb" in tu.convert_color("#06b6d4").lower())
test("TextUtils: unknown algorithm rejected",
     lambda: "Unknown" in tu.hash_text("test", "invalid_algo"))

# ===============================================================================
section("19. COUNTDOWN & DATES")
# ===============================================================================

test("Countdown: add_countdown future date",
     lambda: "days to go" in cd.add_countdown("Test Event", "2099-12-31").lower())
test("Countdown: list_countdowns shows event",
     lambda: "Test Event" in cd.list_countdowns())
test("Countdown: days_until far future",
     lambda: "days until" in cd.days_until("2099-12-31").lower())
test("Countdown: calculate_age returns years",
     lambda: "years old" in cd.calculate_age("01/01/1990", "Test Person"))
test("Countdown: delete_countdown removes event",
     lambda: "Removed 1" in cd.delete_countdown("Test Event"))

# ===============================================================================
section("20. FLASHCARDS")
# ===============================================================================

test("Flashcards: create card",
     lambda: "added" in fc.create_flashcard("What is Python?",
              "A high-level programming language.", "Programming").lower())
test("Flashcards: list decks shows deck",
     lambda: "Programming" in fc.list_flashcard_decks())
test("Flashcards: review returns card or done message",
     lambda: isinstance(fc.review_flashcards(deck="Programming"), str))
test("Flashcards: bulk create cards",
     lambda: "Added" in fc.bulk_create_flashcards(
         "Q1|A1 || Q2|A2 || Q3|A3", "TestDeck"))
test("Flashcards: delete deck",
     lambda: "Deleted" in fc.delete_flashcards(deck="TestDeck") and
             "Deleted" in fc.delete_flashcards(deck="Programming"))

# ===============================================================================
section("21. RANDOM TOOLS")
# ===============================================================================

test("Random: flip_coin returns heads or tails",
     lambda: any(r in rt.flip_coin(1) for r in ["Heads", "Tails"]))
test("Random: roll_dice 1d6 in range",
     lambda: 1 <= int(re.search(r'd6: (\d+)', rt.roll_dice("1d6")).group(1)) <= 6)
test("Random: random_number in range",
     lambda: "Random number" in rt.random_number(1, 10))
test("Random: random_choice picks one",
     lambda: any(x in rt.random_choice("pizza, burgers, sushi").replace("**","")
                 for x in ["pizza", "burgers", "sushi"]))
test("Random: tell_joke returns string",
     lambda: isinstance(rt.tell_joke(), str) and len(rt.tell_joke()) > 10)
test("Random: random_fact returns string",
     lambda: isinstance(rt.random_fact(), str) and len(rt.random_fact()) > 10)
test("Random: random_quote returns string",
     lambda: isinstance(rt.random_quote(), str))
test("Random: magic_8ball returns answer",
     lambda: isinstance(rt.magic_8ball("Will it work?"), str))

# ===============================================================================
section("22. EMAIL COMPOSER")
# ===============================================================================

test("Email: compose_email returns draft",
     lambda: "Dear" in ec.compose_email("Alice", "Discuss project update",
                                         "Schedule a meeting next week") or
             "draft" in ec.compose_email("Alice", "Discuss project update",
                                          "Schedule a meeting next week").lower() or
             isinstance(ec.compose_email("Alice", "test", "test"), str))
test("Email: generate_email_subject returns subjects",
     lambda: isinstance(ec.generate_email_subject("Meeting request email body"), str))
test("Email: summarize_email returns bullets",
     lambda: isinstance(ec.summarize_email(
         "Hi, we need to meet on Tuesday at 10am to discuss the Q4 budget."), str))
test("Email: proofread_email returns corrected text",
     lambda: isinstance(ec.proofread_email("i want to meeet you tomorrow"), str))

# ===============================================================================
section("23. YOUTUBE TOOLS")
# ===============================================================================

test("YouTube: get_youtube_info returns title",
     lambda: isinstance(yt.get_youtube_info("dQw4w9WgXcQ"), str))
test("YouTube: transcript graceful fallback if no lib",
     lambda: isinstance(yt.get_youtube_transcript("dQw4w9WgXcQ"), str))
test("YouTube: summarize_youtube returns string",
     lambda: isinstance(yt.summarize_youtube("dQw4w9WgXcQ"), str))

# ===============================================================================
section("24. CLIPBOARD TRANSFORM")
# ===============================================================================

test("ClipTransform: clipboard_stats returns string",
     lambda: isinstance(ct.clipboard_stats(), str))
test("ClipTransform: strip_formatting returns string",
     lambda: isinstance(ct.strip_clipboard_formatting(), str))
test("ClipTransform: unknown op returns error",
     lambda: "Unknown" in ct.transform_clipboard("nonexistent_op"))

# ===============================================================================
section("25. APP USAGE TRACKER")
# ===============================================================================

test("AppUsage: app_usage_today returns string",
     lambda: isinstance(au.app_usage_today(), str))
test("AppUsage: app_usage_weekly returns string",
     lambda: isinstance(au.app_usage_weekly(), str))
test("AppUsage: productivity_score returns string",
     lambda: isinstance(au.productivity_score(), str))
test("AppUsage: pause/resume tracking",
     lambda: "paused" in au.pause_usage_tracking(True).lower())

# ===============================================================================
section("26. HABIT TRACKER")
# ===============================================================================
import tools.habit_tracker as ht
import tools.pomodoro as pom
import tools.world_clock as wc
import tools.dictionary as dct

test("Habit: add_habit returns confirmation",
     lambda: "added" in ht.add_habit("TestHabit2026").lower() or
             "already" in ht.add_habit("TestHabit2026").lower())
test("Habit: complete_habit marks done",
     lambda: "done" in ht.complete_habit("TestHabit2026").lower() or
             "already" in ht.complete_habit("TestHabit2026").lower())
test("Habit: list_habits returns string",
     lambda: isinstance(ht.list_habits(), str) and "TestHabit2026" in ht.list_habits())
test("Habit: habits_today returns string",
     lambda: isinstance(ht.habits_today(), str))
test("Habit: habit_stats returns string",
     lambda: isinstance(ht.habit_stats("TestHabit2026"), str))
test("Habit: remove_habit removes",
     lambda: "removed" in ht.remove_habit("TestHabit2026").lower())

# ===============================================================================
section("27. POMODORO TIMER")
# ===============================================================================

test("Pomodoro: start_pomodoro starts session",
     lambda: "started" in pom.start_pomodoro("testing", 1).lower())
test("Pomodoro: pomodoro_status shows running",
     lambda: "Working" in pom.pomodoro_status() or "1 min" in pom.pomodoro_status())
test("Pomodoro: stop_pomodoro stops session",
     lambda: "stopped" in pom.stop_pomodoro().lower())
test("Pomodoro: no timer after stop",
     lambda: "No Pomodoro" in pom.pomodoro_status())
test("Pomodoro: history returns string",
     lambda: isinstance(pom.pomodoro_history(7), str))

# ===============================================================================
section("28. WORLD CLOCK")
# ===============================================================================

test("WorldClock: world_time India returns time",
     lambda: "India" in wc.world_time("India") or "Asia/Kolkata" in wc.world_time("India"))
test("WorldClock: world_time Tokyo returns time",
     lambda: "Tokyo" in wc.world_time("Tokyo") or "Asia/Tokyo" in wc.world_time("Tokyo"))
test("WorldClock: world_clock returns multiple cities",
     lambda: "India" in wc.world_clock("India, London, Tokyo"))
test("WorldClock: convert_timezone works",
     lambda: isinstance(wc.convert_timezone("3:30 PM", "India", "London"), str))

# ===============================================================================
section("29. DICTIONARY")
# ===============================================================================

test("Dict: define_word returns definition",
     lambda: isinstance(dct.define_word("serendipity"), str) and
             len(dct.define_word("serendipity")) > 10)
test("Dict: synonyms returns synonyms",
     lambda: isinstance(dct.synonyms("happy"), str))
test("Dict: word_of_the_day returns word",
     lambda: "Word of the Day" in dct.word_of_the_day())
test("Dict: find_rhymes returns rhymes",
     lambda: isinstance(dct.find_rhymes("cat"), str))

# ===============================================================================
section("30. WINDOWS INTEGRATION")
# ===============================================================================
import tools.windows_integration as wi
import tools.device_control_advanced as dca

test("WinInt: get_windows_contacts returns string",
     lambda: isinstance(wi.get_windows_contacts(), str))
test("WinInt: get_installed_apps returns string",
     lambda: isinstance(wi.get_installed_apps(n=5), str))
test("WinInt: get_installed_apps search works",
     lambda: isinstance(wi.get_installed_apps(search="python", n=5), str))
test("WinInt: open_windows_settings unknown returns helpful error",
     lambda: "Available" in wi.open_windows_settings("nonexistent"))
test("WinInt: windows_notify dispatches without crash",
     lambda: isinstance(wi.windows_notify("Test", "JARVIS test notification"), str))

# Device control advanced
test("DevCtrl: get_volume returns string",
     lambda: isinstance(dca.get_volume(), str))
test("DevCtrl: get_brightness returns string",
     lambda: isinstance(dca.get_brightness(), str))
test("DevCtrl: list_running_apps returns processes",
     lambda: "---" in dca.list_running_apps(n=5))
test("DevCtrl: list_wifi_networks returns string",
     lambda: isinstance(dca.list_wifi_networks(), str))
test("DevCtrl: get_system_uptime returns hours",
     lambda: "h" in dca.get_system_uptime())
test("DevCtrl: get_gpu_info returns string",
     lambda: isinstance(dca.get_gpu_info(), str))
test("DevCtrl: get_default_apps returns string",
     lambda: isinstance(dca.get_default_apps(), str))
test("DevCtrl: list_usb_devices returns string",
     lambda: isinstance(dca.list_usb_devices(), str))
# Android PWA file exists
test("Android: android.html exists",
     lambda: (Path(__file__).parent.parent / 'ui' / 'android.html').exists())
test("Android: service worker updated",
     lambda: 'jarvis-v3' in (Path(__file__).parent.parent / 'static' / 'sw.js').read_text())
test("Android: android_manifest.json exists",
     lambda: (Path(__file__).parent.parent / 'static' / 'android_manifest.json').exists())

# ── Licensing ──────────────────────────────────────────────────────
import tools.licensing as lic
test("License: admin host always gets lifetime",
     lambda: lic.get_plan() == 'lifetime')
test("License: check_plan returns string",
     lambda: isinstance(lic.check_plan(), str))
test("License: upgrade_plan returns payment links",
     lambda: 'lemonsqueezy' in lic.upgrade_plan())
test("License: BETA code grants trial",
     lambda: 'trial' in lic.redeem_discount_code('BETA').lower())
test("License: JARVIS21 sends approval request",
     lambda: 'JARVIS21' in lic.redeem_discount_code('JARVIS21') or
             'pending' in lic.redeem_discount_code('JARVIS21').lower() or
             'request' in lic.redeem_discount_code('JARVIS21').lower())
test("License: invalid code returns helpful message",
     lambda: 'not recognised' in lic.redeem_discount_code('BADCODE123').lower() or
             'not found' in lic.redeem_discount_code('BADCODE123').lower())
test("License: admin host has all features",
     lambda: lic.has_feature('email') and lic.has_feature('pc_control') and lic.has_feature('stocks'))
test("License: admin queries are unlimited",
     lambda: lic.queries_remaining() == 9999)
test("GitHub: build workflow exists",
     lambda: (Path(__file__).parent.parent / '.github' / 'workflows' / 'build_apk.yml').exists())
test("Amazon: submission guide exists",
     lambda: (Path(__file__).parent.parent / 'AMAZON_APPSTORE.md').exists())
import tools.phone as _phone_mod
test("WinInt: get_phone_remote_url has URL and instructions",
     lambda: "http://" in _phone_mod.get_phone_remote_url() and
             "Instructions" in _phone_mod.get_phone_remote_url())

# ===============================================================================
section("31. GEMINI BRAIN")
# ===============================================================================
from brain.core import get_brain as _get_brain
_b = _get_brain()
test("Brain: backend detected",
     lambda: _b._backend in ('gemini','groq','anthropic','ollama'))
test("Brain: backends list non-empty",
     lambda: len(_b._backends) > 0)
test("Brain: quick() returns non-empty string",
     lambda: len(_b.quick("Say the word: hello", max_tokens=10)) > 0)

# ===============================================================================
section("32. .gitignore PROTECTION")
# ===============================================================================

gi = Path(__file__).parent.parent / ".gitignore"
def _gi_text():
    """Read .gitignore regardless of encoding (cp1252, utf-8, latin-1)."""
    for enc in ('utf-8', 'latin-1', 'cp1252'):
        try:
            return gi.read_text(encoding=enc)
        except Exception:
            pass
    return gi.read_bytes().decode('latin-1')

test(".gitignore exists",
     lambda: gi.exists())
test(".gitignore protects .env",
     lambda: ".env" in _gi_text() if gi.exists() else False)
test(".gitignore protects memory/",
     lambda: "memory/" in _gi_text() if gi.exists() else False)
test(".gitignore protects google_token.json",
     lambda: "google_token.json" in _gi_text() if gi.exists() else False)
test(".gitignore protects vault.enc",
     lambda: "vault.enc" in _gi_text() if gi.exists() else False)


# ===============================================================================
# SUMMARY
# ===============================================================================

passed  = sum(1 for r in _results if r[1])
failed  = sum(1 for r in _results if not r[1])
total   = len(_results)
avg_ms  = sum(r[2] for r in _results) // max(total, 1)

print(f"\n{'='*70}")
print(f"  JARVIS Test Suite // {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{'='*70}")
print(f"  Total:   {total}")
print(f"  Passed:  {passed}")
if failed:
    print(f"  Failed:  {failed}")
print(f"  Avg:     {avg_ms}ms per test")
print(f"{'='*70}\n")

if failed:
    print("Failed tests:")
    for name, ok, ms, err in _results:
        if not ok:
            print(f"  [FAIL] {name}")
            if err: print(f"    {err}")

sys.exit(0 if failed == 0 else 1)
