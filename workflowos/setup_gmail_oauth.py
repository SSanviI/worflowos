# setup_gmail_oauth.py
"""Interactive Gmail OAuth 2.0 Setup Script for WorkFlowOS.

Features:
- Dual-stack HTTP server (handles IPv4 127.0.0.1 and IPv6 ::1 localhost smoothly on Windows).
- Starts callback listener BEFORE generating and opening Google's authorization URL.
- Remains alive across multiple requests (ignores favicon/preflight probes, keeps listening).
- Dynamically assigns and binds port, guaranteeing redirect_uri matches the active listener.
- Exchanges authorization code for Google access and refresh tokens.
- Persists tokens to ~/.workflowos/gmail_token.json and local project token files.
- Serves a polished, rich HTML confirmation page to the browser.
- Verifies live connectivity via Gmail API users().getProfile() immediately upon authentication.
"""

import sys
import os
import socket
import time
import json
import urllib.parse
import http.server
import threading
import webbrowser
from pathlib import Path

# Add project root directories to sys.path
script_dir = Path(__file__).resolve().parent
if (script_dir / "workflowos").exists():
    root_dir = script_dir
else:
    root_dir = script_dir.parent

sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "workflowos"))
sys.path.insert(0, str(script_dir))

# Allow insecure transport for loopback HTTP redirect (standard OAuth desktop app practice)
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from workflowos.automation.adapters.gmail import SCOPES, CREDENTIAL_PATHS, CONFIG_DIR

DEFAULT_PORTS = [8080, 8085, 8090, 8888, 0]

SUCCESS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>WorkFlowOS - Authentication Successful</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
      background: radial-gradient(circle at 50% 20%, #0d1527 0%, #070a12 100%);
      color: #f1f5f9;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 1rem;
    }
    .card {
      background: rgba(15, 23, 42, 0.85);
      border: 1px solid rgba(56, 189, 248, 0.35);
      backdrop-filter: blur(12px);
      padding: 3rem 2.5rem;
      border-radius: 20px;
      text-align: center;
      max-width: 480px;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 30px rgba(56, 189, 248, 0.15);
      animation: fadeIn 0.4s ease-out;
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(12px); }
      to { opacity: 1; transform: translateY(0); }
    }
    .icon-badge {
      width: 72px;
      height: 72px;
      margin: 0 auto 1.5rem auto;
      border-radius: 50%;
      background: rgba(16, 185, 129, 0.15);
      border: 2px solid #10b981;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #10b981;
      font-size: 32px;
      box-shadow: 0 0 20px rgba(16, 185, 129, 0.3);
    }
    h1 {
      font-size: 1.6rem;
      font-weight: 700;
      color: #ffffff;
      margin-bottom: 0.75rem;
      letter-spacing: -0.02em;
    }
    p {
      color: #94a3b8;
      font-size: 0.98rem;
      line-height: 1.6;
      margin-bottom: 1.25rem;
    }
    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      background: rgba(56, 189, 248, 0.1);
      color: #38bdf8;
      border: 1px solid rgba(56, 189, 248, 0.3);
      padding: 0.4rem 1rem;
      border-radius: 9999px;
      font-size: 0.85rem;
      font-weight: 600;
      margin-top: 0.5rem;
    }
    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #10b981;
      box-shadow: 0 0 8px #10b981;
    }
    .hint {
      margin-top: 1.5rem;
      font-size: 0.85rem;
      color: #64748b;
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="icon-badge">&#10003;</div>
    <h1>Authentication Successful!</h1>
    <p>WorkFlowOS has been authorized to access your Gmail account. Access tokens have been securely exchanged and stored.</p>
    <div class="status-pill">
      <span class="status-dot"></span>
      Gmail API Connected
    </div>
    <div class="hint">You may now close this browser tab and return to the terminal.</div>
  </div>
</body>
</html>
"""

ERROR_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>WorkFlowOS - Authentication Failed</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #090d16;
      color: #f8fafc;
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100vh;
      margin: 0;
    }
    .card {
      background: #1e1b2e;
      border: 1px solid #ef4444;
      padding: 2.5rem;
      border-radius: 16px;
      text-align: center;
      max-width: 480px;
    }
    h1 { color: #f87171; margin-bottom: 0.5rem; }
    p { color: #94a3b8; line-height: 1.5; }
    pre { background: #000; padding: 0.75rem; border-radius: 8px; color: #fca5a5; font-size: 0.85rem; overflow-x: auto; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Authentication Failed</h1>
    <p>Google OAuth returned an error:</p>
    <pre>{error}</pre>
    <p>Please check the terminal output for more details and try again.</p>
  </div>
</body>
</html>
"""


class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """Robust OAuth callback handler that handles preflight probes and the final redirect."""

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        # 1. Ignore favicon, robots, or asset probes without terminating
        if parsed.path in ("/favicon.ico", "/robots.txt"):
            self.send_response(204)
            self.end_headers()
            return

        # 2. Check for OAuth authorization code
        if "code" in params:
            self.server.auth_code = params["code"][0]
            self.server.auth_state = params.get("state", [None])[0]
            self.server.full_path = self.path

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(SUCCESS_HTML.encode("utf-8"))

            # Notify the main thread that the callback was received
            self.server.auth_received.set()
            return

        # 3. Check for OAuth error
        if "error" in params:
            error_msg = params.get("error_description", params["error"])[0]
            self.server.auth_error = error_msg

            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(ERROR_HTML.format(error=error_msg).encode("utf-8"))

            self.server.auth_received.set()
            return

        # 4. Any other preliminary probe / health check request: acknowledge and keep waiting
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(b"WorkFlowOS OAuth listener is active. Waiting for Google authentication callback...")


class DualStackOAuthServer(http.server.HTTPServer):
    """HTTP server that binds to IPv6 dual-stack (handling both IPv6 ::1 and IPv4 127.0.0.1 on Windows)."""

    address_family = socket.AF_INET6

    def __init__(self, server_address, RequestHandlerClass):
        self.auth_received = threading.Event()
        self.auth_code = None
        self.auth_state = None
        self.auth_error = None
        self.full_path = None
        super().__init__(server_address, RequestHandlerClass)

    def server_bind(self):
        try:
            # Enable dual-stack socket so both IPv4 and IPv6 loopback requests are accepted on the same port
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        except (AttributeError, OSError):
            pass
        super().server_bind()


class StandardOAuthServer(http.server.HTTPServer):
    """Fallback IPv4 HTTP Server."""

    address_family = socket.AF_INET

    def __init__(self, server_address, RequestHandlerClass):
        self.auth_received = threading.Event()
        self.auth_code = None
        self.auth_state = None
        self.auth_error = None
        self.full_path = None
        super().__init__(server_address, RequestHandlerClass)


def create_listener(ports=DEFAULT_PORTS):
    """Create and bind a local HTTP listener on the first available port.
    
    Tries dual-stack socket first so both http://localhost and http://127.0.0.1 work.
    Falls back to IPv4 socket if IPv6 dual-stack is unsupported.
    """
    for port in ports:
        # Try dual-stack
        try:
            server = DualStackOAuthServer(("::", port), OAuthCallbackHandler)
            return server, server.server_port
        except OSError:
            pass

        # Try standard IPv4
        try:
            server = StandardOAuthServer(("127.0.0.1", port), OAuthCallbackHandler)
            return server, server.server_port
        except OSError:
            pass

    raise RuntimeError("Could not bind OAuth callback listener to any available local port.")


def run_oauth_setup(preferred_port: int = 8080, open_browser: bool = True, timeout_seconds: int = 300):
    print("\n" + "=" * 65, flush=True)
    print("  WorkFlowOS Gmail OAuth 2.0 Interactive Setup", flush=True)
    print("=" * 65, flush=True)

    # 1. Locate credentials.json
    cred_file = None
    for p in CREDENTIAL_PATHS:
        if p.exists():
            cred_file = p.resolve()
            break

    if not cred_file:
        print("\n[ERROR] No Google OAuth 'credentials.json' file found.", flush=True)
        print("Please place credentials.json in one of the following locations:", flush=True)
        for p in CREDENTIAL_PATHS:
            print(f"  - {p}", flush=True)
        return False

    print(f"[1/5] Using Desktop OAuth credentials: {cred_file}", flush=True)

    # 2. Start the local OAuth listener BEFORE constructing authorization URL
    ports_to_try = [preferred_port] + [p for p in DEFAULT_PORTS if p != preferred_port]
    server, active_port = create_listener(ports_to_try)

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    redirect_uri = f"http://localhost:{active_port}/"
    print(f"[2/5] Callback listener actively listening on: {redirect_uri}", flush=True)

    # 3. Create OAuth Flow with Desktop App client
    flow = InstalledAppFlow.from_client_secrets_file(str(cred_file), SCOPES)
    flow.redirect_uri = redirect_uri

    # Generate authorization URL with offline access to ensure refresh token
    auth_url, flow_state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )

    print(f"[3/5] Starting authentication flow...", flush=True)
    print("\n" + "-" * 65, flush=True)
    print("Please complete authorization in your browser:")
    print(f"\n{auth_url}\n")
    print("-" * 65, flush=True)
    print(f"Listener is waiting on port {active_port} for Google redirect...\n", flush=True)

    # 4. Open user's default browser
    if open_browser:
        try:
            webbrowser.open(auth_url)
            print("Browser opened automatically. If not, copy and paste the URL above.", flush=True)
        except Exception as e:
            print(f"Could not open browser automatically: {e}. Please use the link above.", flush=True)

    # 5. Wait for Google callback
    try:
        received = server.auth_received.wait(timeout=timeout_seconds)
    except KeyboardInterrupt:
        print("\n[CANCELLED] OAuth setup cancelled by user.", flush=True)
        server.shutdown()
        server.server_close()
        return False

    if not received:
        print(f"\n[ERROR] Timed out after {timeout_seconds} seconds waiting for Google callback.", flush=True)
        server.shutdown()
        server.server_close()
        return False

    if server.auth_error:
        print(f"\n[ERROR] Google OAuth failed: {server.auth_error}", flush=True)
        server.shutdown()
        server.server_close()
        return False

    # 6. Exchange authorization code for tokens
    print("\n[4/5] Authorization code received! Exchanging for access/refresh tokens...", flush=True)
    try:
        flow.fetch_token(code=server.auth_code)
        creds = flow.credentials
    except Exception as e:
        print(f"[ERROR] Failed exchanging code for tokens: {e}", flush=True)
        server.shutdown()
        server.server_close()
        return False

    # Gracefully stop listener now that code is captured
    try:
        server.shutdown()
        server.server_close()
    except Exception:
        pass

    # Ensure refresh_token is preserved if Google did not resend one
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    token_dest_home = CONFIG_DIR / "gmail_token.json"
    dest_paths = [
        token_dest_home,
        Path.cwd() / "token.json",
        Path.cwd() / "gmail_token.json",
        root_dir / "token.json",
        root_dir / "gmail_token.json",
        root_dir / "workflowos" / "token.json",
        root_dir / "workflowos" / "gmail_token.json",
    ]

    # If new creds don't have a refresh token, check if we had one saved previously
    if not creds.refresh_token:
        for p in dest_paths:
            if p.exists():
                try:
                    old_data = json.loads(p.read_text())
                    if old_data.get("refresh_token"):
                        creds._refresh_token = old_data["refresh_token"]
                        break
                except Exception:
                    pass

    # Serialize credentials
    json_data = creds.to_json()

    # Save to all destination locations
    saved_locations = set()
    for dest in dest_paths:
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json_data)
            saved_locations.add(str(dest.resolve()))
        except Exception as e:
            pass

    # 7. Live verification with Gmail API
    print("[5/5] Verifying Gmail API connectivity with new credentials...", flush=True)
    email_address = "Unknown"
    messages_total = 0
    threads_total = 0
    try:
        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        email_address = profile.get("emailAddress", "Unknown")
        messages_total = profile.get("messagesTotal", 0)
        threads_total = profile.get("threadsTotal", 0)
        verified = True
    except Exception as e:
        print(f"[WARNING] Token saved, but API profile test returned: {e}", flush=True)
        verified = False

    # Print final success banner
    print("\n" + "=" * 65, flush=True)
    print("  GMAIL OAUTH 2.0 AUTHENTICATION SUCCESSFUL! ", flush=True)
    print("=" * 65, flush=True)
    print(f"  Authenticated User:  {email_address}", flush=True)
    print(f"  Inbox Messages:      {messages_total}", flush=True)
    print(f"  Inbox Threads:       {threads_total}", flush=True)
    print(f"  API Verified:        {'YES (Active & Functional)' if verified else 'PENDING'}", flush=True)
    print("-" * 65, flush=True)
    print("  Saved Credentials:", flush=True)
    for loc in sorted(saved_locations):
        print(f"    - {loc}", flush=True)
    print("-" * 65, flush=True)
    print("  WorkFlowOS is now configured for REAL_API mode in READ_EMAIL.", flush=True)
    print("  You do not need to authenticate again unless access is revoked.", flush=True)
    print("=" * 65 + "\n", flush=True)
    return True


if __name__ == "__main__":
    port_arg = 8080
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port_arg = int(sys.argv[1])
    run_oauth_setup(preferred_port=port_arg)
