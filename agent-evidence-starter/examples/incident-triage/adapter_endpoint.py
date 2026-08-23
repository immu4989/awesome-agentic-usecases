#!/usr/bin/env python3
"""Minimal local JSON endpoint for incident-triage."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from adapter_command import handle


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/evaluate":
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 1_000_000:
                raise ValueError("invalid request size")
            response = json.dumps(handle(json.loads(self.rfile.read(size)))) + "
"
            body = response.encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (ValueError, json.JSONDecodeError, KeyError):
            self.send_error(400)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    print("AAU reference endpoint: http://127.0.0.1:8000/evaluate")
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
