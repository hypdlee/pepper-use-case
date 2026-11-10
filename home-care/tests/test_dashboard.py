# Care Dashboard server: every route, bad input, staleness, and an end-to-end run with the REAL Care Controller (from behavior.xar)
# posting over real HTTP on localhost. Python 3 only (the dashboard runs on the laptop).
import json, os, sys, threading, urllib.request, urllib.error, socket, subprocess, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "dashboard"))
sys.path.insert(0, HERE)
import care_dashboard as cd
import test_controller as tc

fails = []
def check(c, m):
    if not c: fails.append(m)

def call(port, method, path, body=None, headers=None, raw=None):
    data = raw if raw is not None else (None if body is None else json.dumps(body).encode("utf-8"))
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path), data=data, method=method, headers=headers or ({"Content-Type": "application/json"} if data is not None else {}))
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)

def serve(clock=None):
    hub = cd.Hub(clock) if clock else cd.Hub()
    class H(cd.Handler): pass
    H.hub = hub
    srv = cd.Server(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, hub, srv.server_address[1]

def run():
    now = [1000.0]
    srv, hub, port = serve(lambda: now[0])
    # before the robot has said anything
    st, body, h = call(port, "GET", "/api/care/state")
    j = json.loads(body)
    check(st == 200 and j["connected"] is False and j["state"] is None and j["age"] is None, "empty state: %r" % j)
    check(call(port, "GET", "/api/health")[0] == 200, "health")
    st, body, h = call(port, "GET", "/")
    check(st == 200 and b"Care Dashboard" in body and "text/html" in h.get("Content-Type", ""), "page: %r" % st)
    check("Content-Security-Policy" in h and "default-src 'none'" in h["Content-Security-Policy"] and h.get("Cache-Control") == "no-store", "page headers: %r" % h)
    check(call(port, "GET", "/index.html")[0] == 200 and call(port, "GET", "/nope")[0] == 404 and call(port, "GET", "/api/care/nope")[0] == 404, "routes")
    # a good post
    good = {"sentAt": 1.5, "state": {"v": "4.1.1", "current": {"name": "Maria", "start": "10:00"}, "alerts": [], "history": [], "queue": [], "reminders": []}}
    st, body, h = call(port, "POST", "/api/care/state", good)
    check(st == 200 and json.loads(body) == {"ok": True}, "post: %r %r" % (st, body))
    j = json.loads(call(port, "GET", "/api/care/state")[1])
    check(j["connected"] is True and j["state"]["current"]["name"] == "Maria" and j["robot"] == "127.0.0.1" and j["age"] == 0.0, "stored: %r" % j)
    # stale after 12 s, connected again after a new post
    now[0] += 11.0; check(json.loads(call(port, "GET", "/api/care/state")[1])["connected"] is True, "still connected after 11 s")
    now[0] += 2.0; j = json.loads(call(port, "GET", "/api/care/state")[1])
    check(j["connected"] is False and j["age"] == 13.0 and j["state"] is not None, "stale after 13 s: %r" % j)
    call(port, "POST", "/api/care/state", good); check(json.loads(call(port, "GET", "/api/care/state")[1])["connected"] is True, "reconnect")
    # bad input never stores anything and never kills the server
    keep = json.loads(call(port, "GET", "/api/care/state")[1])["state"]
    bad = [("not json", b"{nope"), ("a list", b"[1,2]"), ("no state", b'{"x":1}'), ("state is a list", b'{"state":[1]}'),
           ("alerts is a string", b'{"state":{"alerts":"x"}}'), ("current is a list", b'{"state":{"current":[1]}}'), ("bad utf8", b"\xff\xfe"), ("empty", b"")]
    for label, raw in bad:
        st, body, h = call(port, "POST", "/api/care/state", raw=raw)
        check(st == 400, "%s: status %r" % (label, st))
    check(json.loads(call(port, "GET", "/api/care/state")[1])["state"] == keep, "a bad post changed the stored state")
    sk = socket.create_connection(("127.0.0.1", port), timeout=3)         # a body over the limit is refused from the header alone
    sk.sendall(("POST /api/care/state HTTP/1.1\r\nHost: x\r\nContent-Length: %d\r\n\r\n" % (cd.MAX_BODY + 1)).encode()); reply = sk.recv(200); sk.close()
    check(b" 413 " in reply, "a huge body: %r" % reply[:40])
    check(call(port, "GET", "/api/health")[0] == 200, "server alive after a huge post")
    check(call(port, "POST", "/somewhere", {"a": 1})[0] == 404 and call(port, "PUT", "/api/care/state", {"a": 1})[0] == 405 and call(port, "DELETE", "/api/care/state")[0] == 405, "other routes and methods")
    # no Content-Length
    s = socket.create_connection(("127.0.0.1", port), timeout=3)
    s.sendall(b"POST /api/care/state HTTP/1.1\r\nHost: x\r\n\r\n"); reply = s.recv(200); s.close()
    check(b" 411 " in reply, "missing Content-Length: %r" % reply[:40])
    # many parallel posts and reads
    errs = []
    def worker(i):
        try:
            for k in range(20):
                call(port, "POST", "/api/care/state", {"state": {"current": {"name": "N%d" % i, "start": "x"}, "alerts": []}})
                call(port, "GET", "/api/care/state")
        except Exception as e: errs.append(repr(e))
    ts = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    check(not errs, "parallel use: %r" % errs[:2])
    srv.shutdown(); srv.server_close()

    # ---- end to end: the real controller posts real HTTP, the dashboard shows what the tablet would
    srv, hub, port = serve()
    w, box, ns, t = tc.start_with("Dashboard URL", "http://127.0.0.1:%d/" % port)
    check(box.dashUrl == "http://127.0.0.1:%d" % port, "e2e url: %r" % box.dashUrl)
    check(box._dashOnce() is True, "first post failed")
    j = json.loads(call(port, "GET", "/api/care/state")[1])
    check(j["connected"] and j["state"]["v"] == "4.1.1" and j["state"]["current"] is None, "first state: %r" % (j["state"] or {}).get("v"))
    w.mem.d["pepperName"] = "anna"; tc.tick(box, t)
    tc.cmd(w, box, t, "quiz"); tc.tick(box, t, 3.0); tc.tick(box, t, 3.0)
    box._dashOnce(); s1 = json.loads(call(port, "GET", "/api/care/state")[1])["state"]
    check(s1["current"]["name"] == "Anna" and s1["mode"] == "quiz" and s1["quiz"] and s1["quiz"]["n"] == 1, "quiz not shown on the dashboard: %r" % (s1["mode"],))
    check("opts" in s1["quiz"] and not any(k in s1["quiz"] for k in ("answer", "right", "correct")), "the dashboard state carries a quiz answer key: %r" % list(s1["quiz"]))
    tc.cmd(w, box, t, "stop"); t[0] += 40
    tc.cmd(w, box, t, "needfall"); tc.tick(box, t, 1.0)
    box._dashOnce(); s2 = json.loads(call(port, "GET", "/api/care/state")[1])["state"]
    check(s2["alertsOpen"] == 1 and s2["alerts"][-1]["reason"] == "has fallen" and s2["alerts"][-1]["name"] == "Anna", "the fall alert did not reach the dashboard: %r" % (s2["alerts"],))
    w.mem.d["Pepper/TabletCmd"] = json.dumps({"cmd": "ack"}); tc.tick(box, t, 1.0)
    box._dashOnce(); s3 = json.loads(call(port, "GET", "/api/care/state")[1])["state"]
    check(s3["alertsOpen"] == 0 and s3["alerts"][-1]["seen"] is True, "seen on the tablet did not reach the dashboard: %r" % (s3["alerts"],))
    # the laptop stops: the robot's sender copes, and picks up again when the dashboard returns
    srv.shutdown(); srv.server_close()
    t0 = time.time(); ok = box._dashOnce(); dt = time.time() - t0
    check(ok is False and box.dashDown is True and dt < 3.0, "a dead dashboard must fail fast: ok=%r dt=%.2f" % (ok, dt))
    srv2 = cd.Server(("127.0.0.1", port), cd.Handler); threading.Thread(target=srv2.serve_forever, daemon=True).start()
    check(box._dashOnce() is True and box.dashDown is False, "the robot did not reconnect to a restarted dashboard")
    srv2.shutdown(); srv2.server_close()
    # an address nobody answers at: the post gives up inside the timeout
    w4, box4, ns4, t4 = tc.start_with("Dashboard URL", "http://10.255.255.1:8100")
    t0 = time.time(); ok = box4._dashOnce(); dt = time.time() - t0
    check(ok is False and dt < 4.0, "an unreachable address must fail within the timeout: ok=%r dt=%.2f" % (ok, dt))

    # ---- the program itself starts, serves, and refuses a busy port
    port2 = (lambda s: (s.bind(("127.0.0.1", 0)), s.getsockname()[1], s.close())[1])(socket.socket())
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "..", "dashboard", "care_dashboard.py"), "--port", str(port2), "--host", "127.0.0.1"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        for _ in range(50):
            try:
                if call(port2, "GET", "/api/health")[0] == 200: break
            except Exception: time.sleep(0.1)
        check(call(port2, "GET", "/api/health")[0] == 200, "the program did not start")
        call(port2, "POST", "/api/care/state", {"state": {"current": {"name": "Zedekiah", "start": "10:00"}, "alerts": []}}); call(port2, "GET", "/api/care/state"); call(port2, "GET", "/")
        p2 = subprocess.run([sys.executable, os.path.join(HERE, "..", "dashboard", "care_dashboard.py"), "--port", str(port2), "--host", "127.0.0.1"], capture_output=True, text=True, timeout=20)
        check(p2.returncode == 2 and "Could not start" in p2.stdout, "a busy port: %r %r" % (p2.returncode, p2.stdout[:120]))
    finally:
        p.terminate()
        out = p.communicate(timeout=10)[0].decode("utf-8", "replace")
    check("Zedekiah" not in out and "/api/care/state" not in out and "GET /" not in out, "the program logs requests or names: %r" % out[-300:])
    check("Care Dashboard 1.0.0 is running" in out and "http://localhost:%d" % port2 in out and "Nothing is saved to disk" in out, "banner: %r" % out[:400])

if __name__ == "__main__":
    try:
        run()
    except Exception:
        import traceback; traceback.print_exc(); fails.append("exception")
    fails.extend(tc.fails)
    if fails:
        print("FAIL:"); [print(" -", f) for f in fails]; print("DASHBOARD FAILED"); sys.exit(1)
    print("dashboard server checks passed"); print("DASHBOARD OK")
