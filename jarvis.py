#!/usr/bin/env python
import os, queue, re, sys, threading, time, tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import config
from brain.core import get_brain
from brain.agent import get_agent
from memory import store as mem
from voice.speaker import speak
from voice.listener import Listener
import tools.system
import tools.weather
import tools.research
import tools.finance
import tools.memory_tools
import tools.gmail
import tools.phone
import tools.qr_remote
import tools.voice_tools
import tools.contacts
import tools.ui_tools
import tools.reminders
import tools.screen
import tools.apps
import tools.clipboard_tools
import tools.file_summary
import tools.briefing
import tools.device_control
import tools.context_watcher
import tools.meeting
import tools.password_manager
import tools.translator
import tools.code_runner
import tools.image_gen
import tools.desktop_auto
import tools.contacts_import
import tools.notes
import tools.calendar_tools
import tools.productivity
import tools.info_tools
import tools.system_advanced
import tools.security_advanced
import tools.web_scraper
import tools.report_gen
import tools.github_tools
import tools.communication
import tools.budget
import tools.focus_mode
import tools.alarm
import tools.stocks
import tools.text_utils
import tools.countdown
import tools.flashcards
import tools.random_tools
import tools.email_composer
import tools.youtube_tools
import tools.clipboard_transform
import tools.app_usage
import tools.habit_tracker
import tools.pomodoro
import tools.world_clock
import tools.dictionary
import tools.windows_integration
import tools.device_control_advanced
import tools.licensing
from tools.registry import load_into_agent, all_tools


def _prepare_for_speech(text: str) -> str:
    """Clean markdown and produce a complete-but-concise speech string.

    Speaks the full response if short. If long, speaks complete sentences
    up to ~380 chars then says 'Details on screen, sir.' — never cuts mid-thought.
    """
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*",     r"\1", text)
    text = re.sub(r"`(.+?)`",       r"\1", text)
    text = re.sub(r"#{1,6}\s+",     "",    text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"\n+", " ", text).strip()

    if len(text) <= 380:
        return text

    # Fit as many complete sentences as possible within 380 chars
    sentences = re.split(r"(?<=[.!?])\s+", text)
    parts: list[str] = []
    used = 0
    for sent in sentences:
        if used + len(sent) + 1 > 340:
            break
        parts.append(sent)
        used += len(sent) + 1

    if parts:
        return " ".join(parts) + " Details on screen, sir."
    # Single very long sentence — truncate at word boundary
    truncated = text[:340].rsplit(" ", 1)[0]
    return truncated + "... details on screen, sir."


# ── WebSocket remote state (module-level so web_ui.py can call _push_to_remotes) ─
_ws_clients: dict = {}   # id → WebSocket object
_api_loop          = None  # asyncio event loop of the FastAPI thread
_stop_event        = threading.Event()  # set to interrupt current response


def _push_to_remotes(data: dict):
    """Broadcast a dict to every connected remote WebSocket client."""
    if not _ws_clients or _api_loop is None:
        return
    import asyncio

    async def _blast():
        dead = []
        for cid, ws in list(_ws_clients.items()):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(cid)
        for cid in dead:
            _ws_clients.pop(cid, None)

    try:
        asyncio.run_coroutine_threadsafe(_blast(), _api_loop)
    except Exception:
        pass


_REMOTE_PAGE = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>JARVIS Remote</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#05070c;color:#e2e8f0;font-family:'Segoe UI',sans-serif;
     display:flex;flex-direction:column;height:100dvh;overflow:hidden}
#hdr{background:#070b14;border-bottom:1px solid #1e293b;padding:12px 16px;
     display:flex;align-items:center;justify-content:space-between;shrink:0}
#hdr .brand{font-family:monospace;font-size:.75rem;letter-spacing:.15em;color:#22d3ee;font-weight:700}
#conn-dot{width:8px;height:8px;border-radius:50%;background:#ef4444;transition:background .4s}
#conn-dot.live{background:#10b981}
#state-strip{height:2px;background:#06b6d4;transition:background .5s}
#state-lbl{font-family:monospace;font-size:.65rem;letter-spacing:.12em;
           text-align:center;padding:6px 0;color:#22d3ee99;transition:color .5s}
#log{flex:1;overflow-y:auto;padding:12px 14px;display:flex;flex-direction:column;gap:10px}
.bubble{padding:10px 14px;border-radius:12px;font-size:.875rem;line-height:1.55;max-width:88%;word-break:break-word}
.you{background:#0f2a3d;color:#94c5e0;border:1px solid #1e3a52;align-self:flex-end;border-bottom-right-radius:3px}
.ai{background:#0b1220;color:#e2e8f0;border:1px solid #1e2a40;align-self:flex-start;border-bottom-left-radius:3px}
.sys{color:#475569;font-size:.75rem;font-family:monospace;text-align:center;align-self:center}
#bar{background:#070b14;border-top:1px solid #1e293b;padding:10px 12px;
     display:flex;gap:8px;align-items:flex-end;shrink:0}
#inp{flex:1;background:#0d1220;border:1px solid #1e293b;color:#e2e8f0;
     border-radius:10px;padding:10px 12px;font-size:.9rem;outline:none;resize:none;
     max-height:96px;min-height:40px;line-height:1.4}
#inp:focus{border-color:#06b6d4}
#send-btn,#mic-btn{background:#0e7490;border:none;color:#fff;border-radius:10px;
                   width:40px;height:40px;font-size:1rem;cursor:pointer;
                   display:flex;align-items:center;justify-content:center;shrink:0;
                   transition:background .2s}
#send-btn:active,#mic-btn:active{background:#0891b2}
#mic-btn.recording{background:#dc2626}
::-webkit-scrollbar{width:3px}
::-webkit-scrollbar-thumb{background:#1e293b;border-radius:2px}
</style></head><body>
<div id="hdr">
  <span class="brand">JARVIS // REMOTE</span>
  <div style="display:flex;align-items:center;gap:8px">
    <span id="conn-label" style="font-family:monospace;font-size:.65rem;color:#475569">CONNECTING</span>
    <div id="conn-dot"></div>
  </div>
</div>
<div id="state-strip"></div>
<div id="state-lbl">◈  OFFLINE</div>
<div id="log"><div class="bubble sys">Connecting to JARVIS…</div></div>
<div id="bar">
  <button id="mic-btn" title="Hold to speak">🎤</button>
  <textarea id="inp" rows="1" placeholder="Send a command…"></textarea>
  <button id="send-btn">➤</button>
</div>
<script>
const STATE_COLORS={idle:'#06b6d4',listening:'#10b981',thinking:'#f59e0b',speaking:'#a78bfa'};
let ws=null, retries=0;
const log=document.getElementById('log');
const strip=document.getElementById('state-strip');
const slbl=document.getElementById('state-lbl');
const dot=document.getElementById('conn-dot');
const clbl=document.getElementById('conn-label');

function add(t,cls){
  const d=document.createElement('div');
  d.className='bubble '+cls; d.textContent=t;
  log.appendChild(d); log.scrollTop=log.scrollHeight;
}

function connect(){
  const proto=location.protocol==='https:'?'wss:':'ws:';
  ws=new WebSocket(proto+'//'+location.host+'/ws');
  ws.onopen=()=>{
    dot.classList.add('live'); clbl.textContent='CONNECTED';
    add('Connected to JARVIS.','sys');
    ws.send(JSON.stringify({type:'hello',label:'Remote '+navigator.platform}));
    retries=0;
  };
  ws.onmessage=e=>{
    const d=JSON.parse(e.data);
    if(d.type==='response'){add('JARVIS: '+d.text,'ai');}
    else if(d.type==='state'){
      const c=STATE_COLORS[d.state]||STATE_COLORS.idle;
      strip.style.background=c; slbl.style.color=c+'aa';
      slbl.textContent='◈  '+(d.state||'idle').toUpperCase();
    }
    else if(d.type==='push'){add('📡 '+d.text,'sys');}
  };
  ws.onclose=()=>{
    dot.classList.remove('live'); clbl.textContent='OFFLINE';
    slbl.textContent='◈  OFFLINE'; strip.style.background='#1e293b';
    if(retries<10){retries++;setTimeout(connect,2000+retries*500);}
    else{add('Connection lost. Reload to reconnect.','sys');}
  };
  ws.onerror=()=>ws.close();
}
connect();

function send(){
  const t=document.getElementById('inp').value.trim(); if(!t||!ws||ws.readyState!==1)return;
  document.getElementById('inp').value='';
  document.getElementById('inp').style.height='auto';
  add('You: '+t,'you');
  ws.send(JSON.stringify({type:'command',text:t}));
}
document.getElementById('send-btn').onclick=send;
document.getElementById('inp').addEventListener('keydown',e=>{
  if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}
});
document.getElementById('inp').addEventListener('input',function(){
  this.style.height='auto';this.style.height=Math.min(this.scrollHeight,96)+'px';
});

// Voice input via Web Speech API
const micBtn=document.getElementById('mic-btn');
let recog=null;
if('webkitSpeechRecognition' in window||'SpeechRecognition' in window){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  recog=new SR(); recog.lang='en-US'; recog.interimResults=false;
  recog.onresult=e=>{
    const t=e.results[0][0].transcript;
    document.getElementById('inp').value=t; send();
  };
  recog.onend=()=>micBtn.classList.remove('recording');
  micBtn.onclick=()=>{
    if(micBtn.classList.contains('recording')){recog.stop();}
    else{recog.start();micBtn.classList.add('recording');}
  };
} else { micBtn.style.display='none'; }
</script></body></html>"""


def _start_api(jarvis_instance):
    global _api_loop
    try:
        import asyncio, socket, psutil
        from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Request
        from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
        from fastapi.staticfiles import StaticFiles
        from fastapi.middleware.cors import CORSMiddleware
        import uvicorn
        from api.auth_manager import (
            is_setup_done, setup as auth_setup, login as auth_login,
            verify_token, get_user_info,
        )

        # ── Resolve local IP ───────────────────────────────────────────────
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            local_ip = "127.0.0.1"

        _APP_HTML = Path(__file__).parent / "ui" / "app.html"
        _STATIC   = Path(__file__).parent / "static"

        from api.security import (
            SecurityHeadersMiddleware, RequestSizeMiddleware,
            rate_limit, require_auth,
            ChatRequest, ToolRequest, AuthSetupRequest, AuthLoginRequest,
            scan_response_for_leaks,
        )
        from fastapi import Depends

        # Restrict CORS to LAN (same origin + localhost)
        allowed_origins = [
            "http://localhost", f"http://localhost:{config.API_PORT}",
            "http://127.0.0.1", f"http://127.0.0.1:{config.API_PORT}",
            f"http://{local_ip}:{config.API_PORT}",
            "null",   # file:// for pywebview
        ]
        fapp = FastAPI(title="JARVIS", docs_url=None, redoc_url=None)  # disable public docs
        fapp.add_middleware(SecurityHeadersMiddleware)
        fapp.add_middleware(RequestSizeMiddleware)
        fapp.add_middleware(CORSMiddleware,
                            allow_origins=allowed_origins,
                            allow_credentials=True,
                            allow_methods=["GET","POST","OPTIONS"],
                            allow_headers=["Authorization","Content-Type"])

        # Static files
        if _STATIC.exists():
            fapp.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

        @fapp.on_event("startup")
        async def _save_loop():
            global _api_loop
            _api_loop = asyncio.get_event_loop()

        # ── Auth ───────────────────────────────────────────────────────────
        @fapp.get("/api/auth/status")
        async def auth_status(request: Request):
            rate_limit(request, "default")
            return {"setup_done": is_setup_done()}

        @fapp.post("/api/auth/setup")
        async def auth_setup_ep(body: AuthSetupRequest, request: Request):
            rate_limit(request, "auth")
            if is_setup_done():
                raise HTTPException(403, "Setup already complete.")
            tok = auth_setup(
                name=body.name, password=body.password,
                phone=body.phone, email=body.email,
            )
            return {"token": tok}

        @fapp.post("/api/auth/login")
        async def auth_login_ep(body: AuthLoginRequest, request: Request):
            rate_limit(request, "auth")
            tok = auth_login(body.password)
            if tok:
                return {"token": tok}
            raise HTTPException(401, "Incorrect password.")

        @fapp.get("/api/auth/verify")
        async def auth_verify(token: str = Depends(require_auth)):
            return {"ok": True}

        _ANDROID_HTML = Path(__file__).parent / "ui" / "android.html"

        # ── Main app HTML ──────────────────────────────────────────────────
        @fapp.get("/app", response_class=HTMLResponse)
        async def serve_app():
            return _APP_HTML.read_text(encoding="utf-8") if _APP_HTML.exists() else "<h1>App not found</h1>"

        @fapp.get("/", response_class=HTMLResponse)
        async def root():
            return _APP_HTML.read_text(encoding="utf-8") if _APP_HTML.exists() else _REMOTE_PAGE

        # ── Android PWA — served at /android and /remote ───────────────────
        @fapp.get("/android", response_class=HTMLResponse)
        async def android_app():
            if _ANDROID_HTML.exists():
                return _ANDROID_HTML.read_text(encoding="utf-8")
            return _REMOTE_PAGE

        @fapp.get("/remote", response_class=HTMLResponse)
        async def remote_page():
            """Redirect to Android PWA instead of the old basic remote page."""
            if _ANDROID_HTML.exists():
                return _ANDROID_HTML.read_text(encoding="utf-8")
            return _REMOTE_PAGE

        # ── Chat (authenticated + rate limited) ────────────────────────────
        @fapp.post("/api/chat")
        async def chat_ep(body: ChatRequest, request: Request,
                          _tok: str = Depends(require_auth)):
            rate_limit(request, "chat")
            _stop_event.clear()
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(None, jarvis_instance.handle, body.message)
            # Redact any accidental secret leaks in AI responses
            resp = scan_response_for_leaks(resp)
            return {"response": resp}

        @fapp.post("/api/stop")
        async def stop_ep(request: Request, _tok: str = Depends(require_auth)):
            rate_limit(request, "default")
            _stop_event.set()
            try:
                from voice.speaker import stop as spk_stop
                spk_stop()
            except Exception:
                pass
            return {"ok": True}

        # ── Generic tool caller (authenticated + rate limited) ─────────────
        @fapp.post("/api/tool")  # noqa
        async def tool_ep(body: ToolRequest, request: Request,
                          _tok: str = Depends(require_auth)):
            rate_limit(request, "tool")
            tool_name = body.tool
            args      = body.args
            fn = all_tools().get(tool_name, {}).get("fn")
            if not fn:
                raise HTTPException(404, f"Tool '{tool_name}' not found.")
            try:
                loop   = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: fn(**args))
                return {"result": scan_response_for_leaks(str(result))}
            except Exception as e:
                return {"result": f"Error: {e}"}

        # ── File upload (authenticated + size-limited) ─────────────────────
        @fapp.post("/api/upload")
        async def upload_ep(request: Request, file: UploadFile = File(...),
                            _tok: str = Depends(require_auth)):
            import tempfile, os
            rate_limit(request, "upload")
            # Validate file type (allow common doc types)
            allowed_ext = {".txt",".pdf",".docx",".md",".csv",".json",".py",
                           ".js",".ts",".html",".css",".png",".jpg",".jpeg"}
            suffix = Path(file.filename or "file.bin").suffix.lower()
            if suffix not in allowed_ext:
                raise HTTPException(415, f"File type '{suffix}' not allowed.")
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(await file.read())
                tmp_path = tmp.name
            try:
                loop = asyncio.get_event_loop()
                resp = await loop.run_in_executor(
                    None, jarvis_instance.handle,
                    f"summarise this file: {tmp_path}")
            finally:
                try: os.unlink(tmp_path)
                except Exception: pass
            return {"response": scan_response_for_leaks(resp)}

        # ── User info ──────────────────────────────────────────────────────
        @fapp.get("/api/user")
        async def user_ep(_tok: str = Depends(require_auth)):
            return get_user_info()

        # ── Contact sync (from Android PWA) ───────────────────────────────
        @fapp.post("/api/sync_contacts")
        async def sync_contacts_ep(request: Request, _tok: str = Depends(require_auth)):
            """Receive contacts pushed from Android Contact Picker API."""
            import json as _json
            rate_limit(request, "default")
            try:
                body = await request.json()
                incoming = body.get("contacts", [])
                if not isinstance(incoming, list):
                    raise HTTPException(400, "contacts must be a list")
                contacts_file = config.MEMORY_DIR / "contacts.json"
                existing = []
                if contacts_file.exists():
                    try:
                        existing = _json.loads(contacts_file.read_text())
                        if not isinstance(existing, list):
                            existing = []
                    except Exception:
                        existing = []
                # Merge: deduplicate by name (case-insensitive)
                exist_names = {c.get("name","").lower() for c in existing}
                added = 0
                for c in incoming:
                    name = c.get("name","").strip()
                    if name and name.lower() not in exist_names:
                        existing.append({
                            "name":  name,
                            "phone": c.get("phone","").strip(),
                            "email": c.get("email","").strip(),
                        })
                        exist_names.add(name.lower())
                        added += 1
                contacts_file.write_text(_json.dumps(existing, indent=2))
                return {"message": f"Synced {added} new contacts ({len(existing)} total).", "total": len(existing)}
            except HTTPException:
                raise
            except Exception as e:
                return {"message": f"Sync error: {e}"}

        # ── Contacts ───────────────────────────────────────────────────────
        @fapp.get("/api/contacts")
        async def contacts_ep(_tok: str = Depends(require_auth)):
            try:
                contacts_file = config.MEMORY_DIR / "contacts.json"
                if contacts_file.exists():
                    import json
                    return json.loads(contacts_file.read_text())
            except Exception:
                pass
            return []

        # ── Status ─────────────────────────────────────────────────────────
        @fapp.get("/api/status")
        async def status_ep(request: Request, _tok: str = Depends(require_auth)):
            rate_limit(request, "default")
            gmail_ok = (config.MEMORY_DIR / "google_token.json").exists()
            voice_ok = any((config.MEMORY_DIR / f).exists()
                           for f in ("voice_profile.npy","voice_model.pkl"))
            try:
                cpu = round(psutil.cpu_percent(interval=None))
                ram = round(psutil.virtual_memory().percent)
            except Exception:
                cpu = ram = 0
            try:
                from brain.core import get_brain
                b = get_brain()
                ai_backend = b._backend
                ai_model   = getattr(config, "GEMINI_MODEL", "") if ai_backend == "gemini" \
                             else getattr(config, "GROQ_MODEL", "")
            except Exception:
                ai_backend = "unknown"
                ai_model   = ""
            return {"cpu": cpu, "ram": ram, "gmail": gmail_ok,
                    "voice_enrolled": voice_ok, "devices": len(_ws_clients),
                    "ai_backend": ai_backend, "ai_model": ai_model}

        # ── Remote info ────────────────────────────────────────────────────
        @fapp.get("/api/remote_info")
        async def remote_info_ep():
            url = f"http://{local_ip}:{config.API_PORT}/remote"
            return {"url": url, "ip": local_ip, "port": config.API_PORT}

        # ── Voice enroll ───────────────────────────────────────────────────
        @fapp.post("/api/enroll_voice")
        async def enroll_voice_ep(request: Request, _tok: str = Depends(require_auth)):
            rate_limit(request, "default")
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(None, jarvis_instance.handle,
                                              "enroll my voice")
            return {"result": resp}

        # ── TWA digital asset link ─────────────────────────────────────────
        @fapp.get("/.well-known/assetlinks.json")
        async def assetlinks():
            _al = Path(__file__).parent / "static" / ".well-known" / "assetlinks.json"
            if _al.exists():
                import json as _j; return _j.loads(_al.read_text())
            return [{"relation":["delegate_permission/common.handle_all_urls"],
                     "target":{"namespace":"android_app","package_name":"ai.jarvis.app",
                                "sha256_cert_fingerprints":["REPLACE_WITH_YOUR_SIGNING_CERT_FINGERPRINT"]}}]

        # ── License API ─────────────────────────────────────────────────────
        @fapp.get("/api/license")
        async def license_status_ep(_tok: str = Depends(require_auth)):
            try:
                from tools.licensing import get_plan, PLAN_FEATURES
                plan = get_plan()
                return {"plan": plan, "features": PLAN_FEATURES.get(plan, {})}
            except Exception as e:
                return {"plan": "free", "error": str(e)}

        @fapp.post("/api/license/activate")
        async def license_activate_ep(request: Request, _tok: str = Depends(require_auth)):
            rate_limit(request, "default")
            try:
                body = await request.json()
                from tools.licensing import activate_license, get_plan
                msg  = activate_license(body.get("license_key",""))
                return {"message": msg, "plan": get_plan()}
            except Exception as e:
                return {"message": str(e), "plan": "free"}

        @fapp.post("/api/license/admin_login")
        async def admin_login_ep(request: Request, _tok: str = Depends(require_auth)):
            """Android owner login — grants Lifetime on that device."""
            rate_limit(request, "auth")
            try:
                body = await request.json()
                from tools.licensing import admin_login
                msg  = admin_login(body.get("email",""), body.get("password",""))
                from tools.licensing import get_plan
                return {"message": msg, "plan": get_plan()}
            except Exception as e:
                return {"message": str(e), "plan": "free"}

        @fapp.post("/api/license/redeem")
        async def license_redeem_ep(request: Request, _tok: str = Depends(require_auth)):
            rate_limit(request, "default")
            try:
                body = await request.json()
                from tools.licensing import redeem_discount_code, get_plan
                msg  = redeem_discount_code(body.get("code",""))
                return {"message": msg, "plan": get_plan()}
            except Exception as e:
                return {"message": str(e)}

        # ── Health ─────────────────────────────────────────────────────────
        @fapp.get("/health")
        async def health():
            return {"status": "online", "devices": len(_ws_clients)}

        # ── WebSocket ──────────────────────────────────────────────────────
        @fapp.websocket("/ws")
        async def ws_endpoint(websocket: WebSocket):
            await websocket.accept()
            cid = str(id(websocket))
            _ws_clients[cid] = websocket
            label = f"Device {len(_ws_clients)}"

            devices = [{"id": k, "label": f"Device {i+1}"}
                       for i, k in enumerate(_ws_clients.keys())]
            jarvis_instance._set_devices(devices)

            try:
                await websocket.send_json({
                    "type": "state",
                    "state": jarvis_instance._cur_state or "idle"
                })
            except Exception:
                pass

            try:
                while True:
                    raw = await asyncio.wait_for(websocket.receive_json(), timeout=90)
                    t = raw.get("type", "")
                    if t == "hello":
                        label = raw.get("label", label)
                        # Broadcast updated device list to all clients
                        _push_to_remotes({"type": "devices",
                                          "devices": [{"id": k, "label": f"Device {i+1}"}
                                                      for i, k in enumerate(_ws_clients.keys())]})
                    elif t == "command":
                        text = (raw.get("text") or "").strip()
                        if text:
                            ev = asyncio.get_event_loop()
                            resp = await ev.run_in_executor(
                                None, jarvis_instance.handle, text)
                            try:
                                await websocket.send_json({"type": "response", "text": resp})
                            except Exception:
                                pass
                    elif t == "ping":
                        await websocket.send_json({"type": "pong"})
            except (WebSocketDisconnect, asyncio.TimeoutError, Exception):
                pass
            finally:
                _ws_clients.pop(cid, None)
                devices = [{"id": k, "label": f"Device {i+1}"}
                           for i, k in enumerate(_ws_clients.keys())]
                jarvis_instance._set_devices(devices)

        threading.Thread(
            target=lambda: uvicorn.run(fapp, host="0.0.0.0",
                                       port=config.API_PORT, log_level="warning"),
            daemon=True, name="api",
        ).start()
        print(f"[API] http://{local_ip}:{config.API_PORT}/app  ← Main UI")
        print(f"[API] http://{local_ip}:{config.API_PORT}/remote  ← Phone remote")
    except ImportError as e:
        print(f"[API] Missing package: {e}")
    except Exception as e:
        print(f"[API] {e}")


class Jarvis:
    def __init__(self):
        self._agent         = get_agent()
        load_into_agent(self._agent)
        self._history: list = []
        self._listener      = None
        self._ui_set_state  = None
        self._ui_set_text   = None
        self._ui_set_devices = None
        self._ui_log        = None        # fn(msg, type) → exec log in UI
        self._cur_state     = "idle"
        self._input_q: queue.Queue = queue.Queue()

    def _set_state(self, state: str):
        self._cur_state = state
        # Push to desktop UI
        if self._ui_set_state:
            try:
                self._ui_set_state(state)
            except Exception:
                pass
        # Push to remote WebSocket clients
        _push_to_remotes({"type": "state", "state": state})

    def _set_text(self, text: str, tag: str = "jarvis"):
        if self._ui_set_text:
            try:
                self._ui_set_text(text, tag)
            except Exception:
                pass

    def _set_devices(self, devices: list):
        if self._ui_set_devices:
            try:
                self._ui_set_devices(devices)
            except Exception:
                pass

    def _log(self, msg: str, ltype: str = "info"):
        if self._ui_log:
            try:
                self._ui_log(msg, ltype)
            except Exception:
                pass

    def handle(self, text: str) -> str:
        text = text.strip()
        if not text:
            return ""
        _stop_event.clear()
        self._set_state("thinking")
        print(f"\n[You] {text}")
        threading.Thread(target=mem.save, args=("user", text), daemon=True).start()

        try:
            result = self._agent.run(
                text, self._history.copy(),
                on_step=lambda s: (
                    print(f"  [Agent] {s}"),
                    self._set_state("thinking"),
                    self._log(f"Tool call: {s}", "tool"),
                ),
            )
        except Exception as e:
            result = f"I ran into a problem: {e}"

        response = result.strip() if result else "Got it."

        # ── Auto-translate responses if mode is active ─────────────────────
        speech_response = response
        try:
            from tools.translator import get_auto_translate_settings, _do_translate
            auto, to_lang, from_lang = get_auto_translate_settings()
            if auto and to_lang.lower() not in ("en", "english"):
                speech_response = _do_translate(response, to_lang, from_lang)
                response = f"{response}\n\n[{to_lang.title()}] {speech_response}"
        except Exception:
            pass

        self._history.append({"role": "user",      "content": text})
        self._history.append({"role": "assistant",  "content": response})
        if len(self._history) > 30:
            self._history = self._history[-30:]

        threading.Thread(target=mem.save, args=("assistant", response), daemon=True).start()

        # Clear voice-auth session flag after response is complete
        try:
            from voice.session import clear_authed
            clear_authed()
        except Exception:
            pass

        print(f"\n[AI] {response}\n")
        self._set_text(response, "jarvis")

        if _stop_event.is_set():
            self._set_state("idle")
            return "[Interrupted]"

        speech = _prepare_for_speech(speech_response)
        self._set_state("speaking")
        speak(speech)
        self._set_state("idle")
        return response

    def _voice_loop(self):
        def on_command(text: str):
            self._set_state("listening")
            self._input_q.put(text)

        self._listener = Listener(on_command=on_command)
        self._listener.start()
        print("[Listener] Listening for wake word...")

        while True:
            try:
                text = self._input_q.get(timeout=1)
                self.handle(text)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[Jarvis] {e}")

    def start(self, voice: bool = True, api: bool = True, tray: bool = True):
        # Register autonomous planner with self as handle
        try:
            from brain.planner import register_planner_tool
            register_planner_tool(self)
            load_into_agent(self._agent)  # re-register so planner tool is included
        except Exception as e:
            print(f"[Planner] {e}")
        try:
            from channels.sidecar import start as sidecar_start
            sidecar_start(command_fn=self.handle)
        except Exception as e:
            print(f"[Sidecar] {e}")

        try:
            from workflows.engine import get_engine
            get_engine(command_fn=self.handle)
        except Exception as e:
            print(f"[Workflows] {e}")

        if api:
            _start_api(self)

        greeting = "Online. All systems ready."
        print(f"\n[AI] {greeting}\n")
        speak(greeting)

        if voice:
            threading.Thread(target=self._voice_loop,
                             daemon=True, name="voice").start()

        # System tray icon — only when a UI is running
        if tray:
            try:
                from tray import start_tray
                self._tray_icon = start_tray(
                    self,
                    open_fn=getattr(self, "_ui_show", None),
                    hide_fn=getattr(self, "_ui_hide", None),
                )
            except Exception as e:
                print(f"[Tray] {e}")

        return self

    def cli(self):
        print("Type your command (Ctrl+C to quit):\n")
        while True:
            try:
                text = input("[You] ").strip()
                if not text:
                    continue
                if text.lower() in ("exit", "quit", "bye"):
                    speak("Goodbye.")
                    break
                self.handle(text)
            except (KeyboardInterrupt, EOFError):
                speak("Goodbye.")
                break


def main():
    cli_only = "--cli"      in sys.argv
    voice    = "--no-voice" not in sys.argv and not cli_only
    ui       = "--no-ui"    not in sys.argv and not cli_only
    api      = "--no-api"   not in sys.argv
    tray     = "--no-tray"  not in sys.argv and not cli_only

    j = Jarvis()

    if cli_only:
        j.start(voice=False, api=api, tray=False)
        j.cli()
        return

    if not ui:
        j.start(voice=voice, api=api, tray=tray)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            speak("Goodbye.")
        return

    # ── UI mode: try pywebview HTML dashboard, fall back to tkinter ──────
    def _wire_web(app):
        """Wire JARVIS callbacks to a WebUI instance."""
        from tools.ui_tools import set_ui_callbacks
        from tools.reminders import set_callbacks as set_reminder_cbs

        j._ui_set_state   = app.set_state
        j._ui_set_text    = app.add_message
        j._ui_set_devices = app.update_devices
        j._ui_log         = app.append_log
        j._ui_show        = app.show
        j._ui_hide        = app.hide
        set_ui_callbacks(show=app.show, hide=app.hide)
        set_reminder_cbs(speak=speak, notify=app.add_message)
        j.start(voice=voice, api=api, tray=tray)
        app.add_message("Online. All systems ready.", "jarvis")
        app.append_log("JARVIS initialised", "ok")

    def _wire_tk(app):
        """Wire JARVIS callbacks to a FullscreenUI (tkinter) instance."""
        from tools.ui_tools import set_ui_callbacks
        from tools.reminders import set_callbacks as set_reminder_cbs

        j._ui_set_state = app.set_state
        j._ui_set_text  = app.add_message
        set_ui_callbacks(show=app.show, hide=app.hide)
        set_reminder_cbs(speak=speak, notify=app.add_message)
        j.start(voice=voice, api=api)
        app.add_message("Online. All systems ready.", "jarvis")

    # ── Attempt 1: pywebview HTML dashboard ───────────────────────────────
    try:
        from ui.web_ui import WebUI

        app = WebUI(on_input=lambda t: j._input_q.put(t))
        _wire_web(app)

        try:
            import keyboard
            keyboard.add_hotkey("ctrl+shift+space",
                                lambda: app.hide() if True else app.show())
            print("[Hotkey] Ctrl+Shift+Space → toggle UI")
        except Exception as e:
            print(f"[Hotkey] {e}")

        print("[UI] WebView dashboard launching…")
        app.run()   # blocks on main thread
        speak("Goodbye.")
        return

    except Exception as e:
        import traceback as tb
        print(f"[WebUI] {e} — falling back to tkinter")
        tb.print_exc()

    # ── Attempt 2: tkinter FullscreenUI ───────────────────────────────────
    try:
        from ui.fullscreen import FullscreenUI
        root = tk.Tk()
        root.withdraw()

        app = FullscreenUI(on_input=lambda t: j._input_q.put(t))
        _wire_tk(app)

        try:
            import keyboard
            keyboard.add_hotkey("ctrl+shift+space",
                                lambda: app.hide() if app._root and
                                app._root.state() == "zoomed" else app.show())
        except Exception:
            pass

        print("[UI] Tkinter dashboard launching…")
        root.after(800, app._do_show)
        app.run(root)

    except Exception as e:
        import traceback as tb
        print(f"[UI] Both UIs failed: {e}")
        tb.print_exc()
        j.start(voice=voice, api=api)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    speak("Goodbye.")


if __name__ == "__main__":
    main()
