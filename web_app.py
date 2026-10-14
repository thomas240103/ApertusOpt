"""Loopback-only development UI. Not a production/public web server."""

import argparse
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import perf_counter

import requests
from dotenv import load_dotenv
from pydantic import ValidationError

from main import build_prompt
from src.apertus_client import ApertusClient, MOCK_PALLET_RESPONSE
from src.parser import ParseError, parse_knapsack_response
from src.presentation import optimize_pallets

ROOT = Path(__file__).resolve().parent
MAX_BODY = 256_000
EXAMPLE_TEXT = """A truck has 10000 kg of available payload and 25 m3 of available volume.
Pallet A weighs 4000 kg, occupies 12 m3 and has a profit margin of EUR 300.
Pallet B weighs 3500 kg, occupies 10 m3 and has a profit margin of EUR 280.
Pallet C weighs 3000 kg, occupies 8 m3 and has a profit margin of EUR 220.
Pallet D weighs 2500 kg, occupies 6 m3 and has a profit margin of EUR 200.
Pallet E weighs 2000 kg, occupies 5 m3 and has a profit margin of EUR 120.
Each pallet is optional, indivisible and available once. All pallets are compatible
and travel to the same destination. Maximize total margin within both limits."""


def extract_problem(data: dict) -> dict:
    text, mode = data.get("text"), data.get("mode")
    if not isinstance(text, str) or not text.strip() or len(text) > 16000:
        raise ValueError("Enter a problem description of 1 to 16000 characters.")
    if mode not in ("demo", "live"):
        raise ValueError("Select Demo or Apertus API mode.")
    start = perf_counter()
    if mode == "demo":
        raw = MOCK_PALLET_RESPONSE
    else:
        client = ApertusClient.from_env(pallets=True)
        if os.getenv("MOCK_APERTUS", "").lower() == "true":
            raise ValueError("Live extraction is disabled by MOCK_APERTUS=true in .env.")
        if not client.api_url:
            raise ValueError("Set APERTUS_API_URL, APERTUS_MODEL and APERTUS_API_KEY in .env first.")
        try:
            raw = client.generate(build_prompt(text, pallets=True))
        except (requests.RequestException, ValueError, TypeError, AttributeError):
            # Provider errors can contain response bodies or configuration secrets.
            raise ValueError("Apertus request failed. Check API configuration, access and connectivity.") from None
    try:
        problem = parse_knapsack_response(raw, require_volume=True)
    except ParseError:
        raise ValueError("Apertus could not produce valid pallet data. Check for missing numbers or unsupported constraints.") from None
    if len(problem.items) > 500:
        raise ValueError("The web demo supports at most 500 pallets.")
    return {"problem": problem.model_dump(exclude_none=True), "mode": mode,
            "extract_seconds": round(perf_counter() - start, 3)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Do not log problem text or credentials.

    def reply(self, status, payload, content_type="application/json; charset=utf-8"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def local_request(self):
        port = self.server.server_port
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        host = self.headers.get("Host")
        return host in hosts and self.headers.get("Origin", f"http://{host}") == f"http://{host}"

    def do_GET(self):
        if not self.local_request():
            return self.reply(403, {"error": "Local requests only."})
        if self.path == "/api/example":
            return self.reply(200, {"text": EXAMPLE_TEXT, "problem": json.loads(MOCK_PALLET_RESPONSE)})
        files = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
                 "/style.css": ("style.css", "text/css")}
        if self.path not in files:
            return self.reply(404, {"error": "Not found."})
        filename, mime = files[self.path]
        self.reply(200, (ROOT / "web" / filename).read_bytes(), mime + "; charset=utf-8")

    def do_POST(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BODY:
                return self.reply(413, {"error": "Request is empty or too large."})
            self.connection.settimeout(10)
            raw = self.rfile.read(size)
            # Consume bounded bodies before rejection to avoid a TCP reset on Windows.
            if (not self.local_request() or self.headers.get("X-ApertusOpt") != "1"
                    or self.headers.get("Content-Type", "").split(";")[0] != "application/json"):
                return self.reply(403, {"error": "Local JSON requests only."})
            if self.path not in ("/api/extract", "/api/solve"):
                return self.reply(404, {"error": "Not found."})
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object.")
        except (ValueError, UnicodeError, OSError):
            return self.reply(400, {"error": "Invalid JSON request."})
        if not self.server.work_lock.acquire(blocking=False):
            return self.reply(429, {"error": "Another calculation is running. Please try again shortly."})
        try:
            result = extract_problem(data) if self.path == "/api/extract" else optimize_pallets(data)
            self.reply(200, result)
        except ValidationError as exc:
            errors = [f"{'.'.join(map(str, e['loc'])) or 'problem'}: {e['msg']}" for e in exc.errors()]
            self.reply(400, {"error": "Invalid pallet data. " + "; ".join(errors)})
        except ValueError as exc:
            self.reply(400, {"error": str(exc)})
        except Exception:
            self.reply(500, {"error": "An unexpected error occurred. No result was accepted."})
        finally:
            self.server.work_lock.release()


def create_server(port=8765):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.work_lock = threading.Lock()
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the local ApertusOpt load planner.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    args = parser.parse_args()
    load_dotenv(args.env_file)
    with create_server(args.port) as server:
        print(f"ApertusOpt: http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
