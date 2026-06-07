import base64, hashlib, hmac, json, os, socket, struct, threading, time
from pathlib import Path

_SECRET_FILE = Path(__file__).parent.parent / ".sidecar_secret"
_CRLF = b"\r\n"


def _get_secret():
    if _SECRET_FILE.exists():
        return _SECRET_FILE.read_bytes().strip()
    secret = os.urandom(32)
    _SECRET_FILE.write_bytes(secret)
    return secret


def _b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _make_token(payload):
    secret = _get_secret()
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64url(json.dumps({**payload, "iat": int(time.time())}).encode())
    sig = hmac.new(secret, f"{header}.{body}".encode(), hashlib.sha256).digest()
    return f"{header}.{body}.{_b64url(sig)}"


def _verify_token(token):
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        secret = _get_secret()
        expected = hmac.new(secret, f"{parts[0]}.{parts[1]}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, base64.urlsafe_b64decode(parts[2] + "==")):
            return None
        return json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
    except Exception:
        return None


def _ws_handshake(conn, data):
    try:
        req = data.decode("utf-8", errors="replace")
        key_line = next((l for l in req.splitlines() if "Sec-WebSocket-Key" in l), "")
        key = key_line.split(": ", 1)[1].strip()
        magic = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        accept = base64.b64encode(hashlib.sha1((key + magic).encode()).digest()).decode()
        conn.sendall(_CRLF.join([
            b"HTTP/1.1 101 Switching Protocols",
            b"Upgrade: websocket", b"Connection: Upgrade",
            b"Sec-WebSocket-Accept: " + accept.encode(), b"", b"",
        ]))
        return True
    except Exception:
        return False


def _ws_recv(conn):
    try:
        hdr = conn.recv(2)
        if len(hdr) < 2:
            return None
        b1, b2 = hdr
        masked = bool(b2 & 0x80)
        length = b2 & 0x7F
        if length == 126:
            length = struct.unpack(">H", conn.recv(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", conn.recv(8))[0]
        mask = conn.recv(4) if masked else b""
        payload = conn.recv(length)
        if masked:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        return payload.decode("utf-8", errors="replace")
    except Exception:
        return None


def _ws_send(conn, msg):
    data = msg.encode("utf-8")
    n = len(data)
    hdr = bytes([0x81, n]) if n < 126 else (bytes([0x81, 126]) + struct.pack(">H", n))
    try:
        conn.sendall(hdr + data)
    except Exception:
        pass


def _handle_client(conn, command_fn):
    try:
        data = conn.recv(4096)
        if b"Upgrade: websocket" in data:
            if not _ws_handshake(conn, data):
                return
            while True:
                msg = _ws_recv(conn)
                if msg is None:
                    break
                try:
                    req = json.loads(msg)
                except Exception:
                    _ws_send(conn, json.dumps({"error": "invalid json"}))
                    continue
                if not _verify_token(req.get("token", "")):
                    _ws_send(conn, json.dumps({"error": "unauthorized"}))
                    continue
                result = command_fn(req.get("command", "")) if req.get("command") else "No command."
                _ws_send(conn, json.dumps({"result": result}))
        else:
            token = _make_token({"role": "client"})
            body = json.dumps({"token": token}).encode()
            conn.sendall(_CRLF.join([
                b"HTTP/1.1 200 OK", b"Content-Type: application/json",
                b"Access-Control-Allow-Origin: *",
                b"Content-Length: " + str(len(body)).encode(), b"", b"",
            ]) + body)
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def start(command_fn, port=8765):
    def _server():
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            srv.bind(("127.0.0.1", port))
            srv.listen(5)
        except Exception as e:
            print(f"[Sidecar] {e}")
            return
        print(f"[Sidecar] ws://127.0.0.1:{port}")
        while True:
            try:
                conn, _ = srv.accept()
                threading.Thread(target=_handle_client, args=(conn, command_fn), daemon=True).start()
            except Exception:
                break
    threading.Thread(target=_server, daemon=True, name="sidecar").start()
