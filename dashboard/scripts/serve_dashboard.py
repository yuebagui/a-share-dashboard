#!/usr/bin/env python3
"""
Serve the dashboard locally and expose small local APIs:

- /api/refresh regenerates daily.json.
- /api/score?code=300750&mode=auto runs the stock calculator.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
FETCH_SCRIPT = ROOT / "scripts" / "fetch_daily.py"
CALCULATOR_SCRIPT = PROJECT_ROOT / "skills" / "short-term-stock-calculator" / "scripts" / "calculator.py"


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/refresh":
            self.handle_refresh(parsed.query)
            return
        if parsed.path == "/api/score":
            self.handle_score(parsed.query)
            return
        super().do_GET()

    def handle_refresh(self, query: str) -> None:
        params = parse_qs(query)
        trade_date = params.get("date", [date.today().isoformat()])[0]
        command = [sys.executable, str(FETCH_SCRIPT), "--date", trade_date]
        try:
            result = subprocess.run(
                command,
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
            self.send_json(
                {
                    "ok": result.returncode == 0,
                    "tradeDate": trade_date,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                },
                status=200 if result.returncode == 0 else 500,
            )
        except Exception as exc:  # noqa: BLE001
            self.send_json({"ok": False, "error": str(exc)}, status=500)

    def handle_score(self, query: str) -> None:
        params = parse_qs(query)
        code = params.get("code", [""])[0].strip()
        mode = params.get("mode", ["auto"])[0].strip() or "auto"
        if not code:
            self.send_json({"ok": False, "error": "Missing stock code."}, status=400)
            return
        if mode not in {"auto", "leader", "trend", "20cm"}:
            self.send_json({"ok": False, "error": "Unsupported mode."}, status=400)
            return

        command = [sys.executable, str(CALCULATOR_SCRIPT), code, "--mode", mode, "--json"]
        try:
            result = subprocess.run(
                command,
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
            if result.returncode != 0:
                self.send_json(
                    {
                        "ok": False,
                        "code": code,
                        "mode": mode,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                    },
                    status=500,
                )
                return
            self.send_json(json.loads(result.stdout))
        except Exception as exc:  # noqa: BLE001
            self.send_json({"ok": False, "error": str(exc)}, status=500)

    def send_json(self, payload, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    print(f"Serving dashboard on http://127.0.0.1:{port}/")
    print("Use /api/refresh to regenerate dashboard/data/daily.json")
    print("Use /api/score?code=300750&mode=auto to run the local stock calculator")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
