#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Care Dashboard 1.0: watch the Pepper Care Companion from a laptop or a phone on the same private network.

It only WATCHES. It shows who is with Pepper, what Pepper is doing, carer alerts with their reason, the queue,
medicine reminders and the day's records. Pepper sends its state here (box parameter "Dashboard URL" of the Care
Controller); nothing is sent to the internet and nothing is written to disk.

Standard library only. Python 3.8 or newer.     Run:  python care_dashboard.py        (then open the address it prints)
"""
import argparse
import json
import os
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "1.0.0"
DEFAULT_PORT = 8100
MAX_BODY = 512 * 1024          # one state is a few kilobytes; anything near this is not from Pepper
STALE_S = 12.0                 # the robot posts at least every 4 s; this long without one means "not connected"
HERE = os.path.dirname(os.path.abspath(__file__))


class Hub(object):
    """The newest state Pepper sent. Held in memory only: stopping this program forgets everything."""

    def __init__(self, clock=time.time):
        self.clock = clock
        self.lock = threading.Lock()
        self.state = None
        self.sent_at = None
        self.received = 0.0
        self.remote = ""
        self.was_connected = False

    def put(self, remote, body):
        """Stores one post. Raises ValueError when it is not a Care Companion state."""
        if not isinstance(body, dict) or not isinstance(body.get("state"), dict):
            raise ValueError("expected a JSON object with a 'state' object")
        state = body["state"]
        for key, kind in (("alerts", list), ("history", list), ("queue", list), ("reminders", list)):
            if key in state and not isinstance(state[key], kind):
                raise ValueError("'%s' must be a list" % key)
        for key in ("current", "quiz", "mem", "snl", "exercise", "breathing", "pick"):
            if key in state and state[key] is not None and not isinstance(state[key], dict):
                raise ValueError("'%s' must be an object or null" % key)
        with self.lock:
            self.state = state
            self.sent_at = body.get("sentAt") if isinstance(body.get("sentAt"), (int, float)) else None
            self.received = self.clock()
            self.remote = remote

    def snapshot(self):
        with self.lock:
            now = self.clock()
            age = None if self.state is None else max(0.0, now - self.received)
            connected = age is not None and age <= STALE_S
            return {"connected": connected, "age": None if age is None else round(age, 1), "robot": self.remote,
                    "serverVersion": VERSION, "state": self.state}


HUB = Hub()


def lan_ips():
    """This laptop's addresses on the local network (what the robot and a phone should type)."""
    found = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))                 # no packet is sent; it only picks the outgoing interface
        found.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in found and not ip.startswith("127."):
                found.append(ip)
    except Exception:
        pass
    return [ip for ip in found if not ip.startswith("127.") and not ip.startswith("0.")]


CSP = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src data:; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


class Handler(BaseHTTPRequestHandler):
    server_version = "CareDashboard/" + VERSION
    protocol_version = "HTTP/1.1"
    hub = HUB

    def log_message(self, fmt, *args):
        pass                                             # never log requests: they carry residents' first names

    # ---- helpers
    def _send(self, code, body, ctype, extra=None):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj), "application/json; charset=utf-8")

    def _path(self):
        return self.path.split("?", 1)[0]

    # ---- routes
    def do_GET(self):
        path = self._path()
        if path in ("/", "/index.html", "/dashboard.html"):
            try:
                with open(os.path.join(HERE, "dashboard.html"), "rb") as handle:
                    page = handle.read()
            except OSError:
                self._json(500, {"detail": "dashboard.html is missing next to care_dashboard.py"})
                return
            self._send(200, page, "text/html; charset=utf-8", {"Content-Security-Policy": CSP, "Referrer-Policy": "no-referrer"})
        elif path == "/api/care/state":
            self._json(200, self.hub.snapshot())
        elif path == "/api/health":
            self._json(200, {"ok": True, "version": VERSION})
        else:
            self._json(404, {"detail": "not found"})

    do_HEAD = do_GET

    def do_POST(self):
        if self._path() != "/api/care/state":
            self.close_connection = True                 # the body is not read, so this connection cannot be reused
            self._json(404, {"detail": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self.close_connection = True
            self._json(411, {"detail": "Content-Length is required"})
            return
        if length < 0 or length > MAX_BODY:
            self.close_connection = True
            self._json(413, {"detail": "body too large"})
            return
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8"))
            self.hub.put(self.client_address[0], body)
        except (ValueError, UnicodeDecodeError) as exc:
            self._json(400, {"detail": str(exc)})
            return
        self._json(200, {"ok": True})

    def do_PUT(self):
        self.close_connection = True
        self._json(405, {"detail": "method not allowed"})

    do_DELETE = do_PATCH = do_PUT


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_server(host, port):
    return Server((host, port), Handler)


def banner(port):
    ips = lan_ips()
    lines = ["", "  Care Dashboard " + VERSION + " is running", "",
             "  On this laptop       : http://localhost:%d" % port]
    for ip in ips:
        lines.append("  On a phone or tablet : http://%s:%d   (same Wi-Fi)" % (ip, port))
    lines.append("")
    if ips:
        lines.append("  For Pepper: in Choregraphe, box 'Care Controller', parameter 'Dashboard URL', type:")
        lines.append("      http://%s:%d" % (ips[0], port))
    else:
        lines.append("  No network address found: connect this laptop to the same network as Pepper.")
    lines += ["", "  Use a private network you trust: the page shows residents' first names.",
              "  Nothing is saved to disk. Keep this window open. Press Ctrl+C to stop.", ""]
    print("\n".join(lines), flush=True)


def watch_connection():
    """Prints one line when Pepper starts or stops sending, so the window tells you what is going on."""
    while True:
        time.sleep(1.0)
        snap = HUB.snapshot()
        if snap["connected"] and not HUB.was_connected:
            HUB.was_connected = True
            print("  Pepper connected from %s" % snap["robot"], flush=True)
        elif not snap["connected"] and HUB.was_connected:
            HUB.was_connected = False
            print("  Pepper stopped sending (switched off, stopped, or the network dropped)", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Care Dashboard: watch the Pepper Care Companion")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default="0.0.0.0", help="0.0.0.0 lets Pepper and phones on the network reach it; 127.0.0.1 keeps it on this laptop")
    args = parser.parse_args(argv)
    if not os.path.isfile(os.path.join(HERE, "dashboard.html")):
        print("dashboard.html is missing next to care_dashboard.py")
        return 2
    try:
        server = make_server(args.host, args.port)
    except OSError as exc:
        print("Could not start on port %d (%s). Is the dashboard already running? Try: python care_dashboard.py --port %d" % (args.port, exc, args.port + 1))
        return 2
    threading.Thread(target=watch_connection, daemon=True).start()
    banner(args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
