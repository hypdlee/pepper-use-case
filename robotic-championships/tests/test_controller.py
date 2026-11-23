# -*- coding: utf-8 -*-
# Runs the Host Controller exactly as stored inside behavior.xar against a fake NAOqi. Works on Python 3 and 2.7:
#   python3 tests/test_controller.py      (also starts the Python 2.7 run when PY27 exists)
from __future__ import print_function
import json, sys, os, io, re, shutil, tempfile, subprocess, calendar

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY27 = "/tmp/claude-0/-home-claude/b05a1f0c-dd7e-5d57-999d-12aa7eb13b58/scratchpad/py27/bin/python2.7"
FAILS = []

def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print("FAIL:", msg)

def load_script():
    txt = io.open(os.path.join(ROOT, "ChampionshipHost", "behavior_1", "behavior.xar"), encoding="utf-8").read()
    a = txt.index('<Box name="Host Controller"')
    c0 = txt.index("<![CDATA[", a) + 9
    return txt[c0:txt.index("]]></content>", c0)]

def utc(y, mo, d, h, mi):
    return calendar.timegm((y, mo, d, h, mi, 0, 0, 0, 0))

class World(object):
    def __init__(self, app):
        self.t = utc(2026, 11, 28, 12, 0)          # Sat 13:00 Malta
        self.mem = {}
        self.calls, self.said, self.js, self.forced, self.concepts, self.events, self.logs = [], [], [], [], [], [], []
        self.app = app
        self.dialog_alive = True
        self.loaded, self.active, self.subs = ["Host"], ["Host"], []     # an old copy left loaded by an earlier run
        self.fresh = False
        self.ping_fail = 0
        self.no_async = False
        self.stopped = -1
        self.sent = 0
        self.tablet_cb = None
        self.links = {}

class Rec(object):
    def __init__(self, name, w):
        self._n, self._w = name, w
    def __getattr__(self, m):
        if m.startswith("__") or m == "post":       # like the robot: services from session.service() have no .post
            raise AttributeError("'Object' object has no attribute '%s'" % m)
        def f(*a):
            self._w.calls.append((self._n, m, a))
            return None
        return f

class Mem(Rec):
    def getData(self, k):
        if k not in self._w.mem:
            raise RuntimeError("no key %s" % k)
        return self._w.mem[k]
    def getListData(self, ks):
        return [self._w.mem.get(k) for k in ks]
    def insertData(self, k, v):
        assert isinstance(v, str), "ALMemory value must be str, got %r" % type(v)
        self._w.mem[k] = v
    def raiseEvent(self, k, v):
        self._w.events.append(k)

class Fut(object):
    """A qi future for a sentence that takes 3 seconds (or less, if speech is stopped)."""
    def __init__(self, w):
        w.sent += 1
        self.w, self.n, self.end = w, w.sent, w.t + getattr(w, 'speech_s', 3)
    def isFinished(self):
        return self.w.t >= self.end or self.w.stopped >= self.n
    def cancel(self):
        self.w.calls.append(("future", "cancel", ()))

class Speech(Rec):
    def say(self, text, conf=None, _async=False):
        assert isinstance(text, str), "speech must be str"
        if self._w.no_async and _async:
            raise TypeError("say() got an unexpected keyword argument '_async'")
        self._w.said.append(text)
        return Fut(self._w) if _async else None

class TTS(Rec):
    def say(self, text, _async=False):
        assert isinstance(text, str)
        self._w.said.append(text)
        return Fut(self._w) if _async else None
    def stopAll(self):
        self._w.calls.append(("ALTextToSpeech", "stopAll", ()))
        self._w.stopped = self._w.sent

class Tablet(Rec):
    def executeJS(self, code):
        assert isinstance(code, str)
        self._w.js.append(code)
    @property
    def onJSEvent(self):
        w = self._w
        class S(object):
            # like the robot: a link stays until it is disconnected, even after the box that made it has stopped
            def connect(self, cb):
                w.tablet_cb = cb
                w.links[len(w.links) + 1] = cb
                return len(w.links)
            def disconnect(self, link):
                w.calls.append(("ALTabletService", "onJSEvent.disconnect", (link,)))
                w.links.pop(link, None)
        return S()

class Dialog(Rec):
    def forceInput(self, t):
        assert isinstance(t, str)
        self._w.forced.append(t)
        if t == "robotcmd ping":
            w = self._w
            if w.ping_fail > 0:
                w.ping_fail -= 1
            elif w.dialog_alive and w.fresh and "Host" in w.active and w.subs:
                w.mem["hostPong"] = "ok1"
    def setConcept(self, name, lang, words):
        assert all(isinstance(x, str) for x in words)
        self._w.concepts.append((name, lang, list(words)))
    def getAllLoadedTopics(self):
        return list(self._w.loaded)
    def getActivatedTopics(self):
        return list(self._w.active)
    def activateTopic(self, n):
        self._w.calls.append(("ALDialog", "activateTopic", (n,)))
        self._w.active.append("Host")
    def subscribe(self, n):
        self._w.calls.append(("ALDialog", "subscribe", (n,)))
        self._w.subs.append(n)
    def loadTopic(self, p):
        self._w.calls.append(("ALDialog", "loadTopic", (p,)))
        if "Host" in self._w.loaded:                  # what Pepper says when an earlier run left the topic loaded
            raise RuntimeError("LoadTopic::ALDialog A topic named %s is already loaded" % p)
        self._w.loaded.append("Host")
        self._w.fresh = True
        return "Host"
    def unloadTopic(self, n):
        self._w.calls.append(("ALDialog", "unloadTopic", (n,)))
        self._w.loaded = [x for x in self._w.loaded if x != n]
        self._w.fresh = False
    def deactivateTopic(self, n):
        self._w.calls.append(("ALDialog", "deactivateTopic", (n,)))
        self._w.active = [x for x in self._w.active if x != n]
    def unsubscribe(self, n):
        self._w.calls.append(("ALDialog", "unsubscribe", (n,)))
        self._w.subs = [x for x in self._w.subs if x != n]

class Aware(Rec):
    def getTrackingMode(self):
        return "BodyRotation"
    def getEngagementMode(self):
        return "Unengaged"

class Frame(Rec):
    def getBehaviorPath(self, bid):
        return os.path.join(self._w.app, "behavior_1")

class Logger(object):
    def __init__(self, w):
        self.w = w
    def __getattr__(self, lvl):
        return lambda m: self.w.logs.append((lvl, m))

def make(w, params=None):
    ns = {}
    class Session(object):
        def service(self, name):
            return {"ALMemory": Mem, "ALAnimatedSpeech": Speech, "ALTextToSpeech": TTS, "ALTabletService": Tablet,
                    "ALDialog": Dialog, "ALBasicAwareness": Aware, "ALFrameManager": Frame}.get(name, Rec)(name, w)
    P = {"Staff PIN": "2468", "Match calls": True, "Greet visitors": True, "Intro when idle (minutes)": 10, "Announce match starts": False, "Intro at start": False}
    P.update(params or {})
    class GeneratedClass(object):
        behaviorId = "bid"
        def __init__(self):
            self.logger = Logger(w)
        def session(self):
            return Session()
        def getParameter(self, n):
            return P[n]
        def onStopped(self):
            w.calls.append(("box", "onStopped", ()))
    ns["GeneratedClass"] = GeneratedClass
    exec(compile(load_script(), "host_controller", "exec"), ns)
    import threading as _th
    class _NoThread(object):           # the tests drive tick() themselves: no background threads
        def __init__(self, target=None, **k):
            self.daemon = True
        def start(self):
            w.calls.append(("thread", "start", ()))
    class _Th(object):
        Lock = _th.Lock
        Thread = _NoThread
    ns["threading"] = _Th
    box = ns["MyClass"]()
    box.clock = lambda: w.t
    box.sleep = lambda s: None
    box.onLoad()
    return box, ns

def start(w, params=None, store=None):
    box, ns = make(w, params)
    if store:
        ns["STORE_DIR"] = store
    n0 = w.calls.count(("thread", "start", ()))
    box.onInput_onStart()
    assert w.calls.count(("thread", "start", ())) - n0 == 2, "worker and tablet sender should both start"
    box.sender = None
    box._flushJs()
    return box, ns

def tick(w, box, secs=0.1):
    steps = max(1, int(round(secs / 0.1)))
    for _ in range(steps):
        w.t += 0.1
        box.tick()
        box._flushJs()

_N = [0]
def tab(w, box, msg):
    _N[0] += 1
    msg.setdefault("id", "m%d" % _N[0])
    box.onTablet(json.dumps(msg))
    box._flushJs()

def dlg(w, box, cmd, **extra):
    for k, v in extra.items():
        w.mem[k] = v
    w.mem["hostCmd"] = cmd
    tick(w, box)

def last_state(w):
    for c in reversed(w.js):
        if c.startswith("try{HostUI.update("):
            return json.loads(c[len("try{HostUI.update("):-len(")}catch(e){}")])
    return None

def run():
    tmp = tempfile.mkdtemp()
    app = os.path.join(tmp, "app")
    shutil.copytree(os.path.join(ROOT, "ChampionshipHost"), app)
    store = os.path.join(tmp, "store")
    io.open(os.path.join(app, "html", "data", "teams.csv"), "w", encoding="utf-8").write(
        u"# note\nname,country,category,say_as\nTeam Falcon,Croatia,arena,\n\"Orion, The\",Greece,Arena,\nArmStrong,Portugal,arm,Arm Strong\n,ignored,arena,\n")
    io.open(os.path.join(app, "html", "data", "schedule.csv"), "w", encoding="utf-8").write(
        u"day,time,minutes,title,category,game,side_a,side_b,done\nsat,14:00,30,Opening Ceremony,stage,,,,\n"
        u"sat,14:40,15,Time of Fall,arena,tof,Team Falcon,\"Orion, The\",\nsat,15:00,15,Colour Sort,arm,colour,ArmStrong,,\n"
        u"sat,16:00,15,Shape Sort,arm,shape,ArmStrong,,yes\nsat,25:00,15,Bad time,arena,,,,\nfri,10:00,15,Bad day,arena,,,,\nsun,18:00,45,Awards Ceremony,stage,,,,\n")

    # ---- start-up
    w = World(app)
    box, ns = start(w, store=store)
    st = last_state(w)
    check(st is not None and st["v"] == "1.2.2", "no first state pushed")
    check([t["name"] for t in st["teams"]] == ["Team Falcon", "Orion, The", "ArmStrong"], "teams from CSV: %r" % [t["name"] for t in st["teams"]])
    check([t["cat"] for t in st["teams"]] == ["arena", "arena", "arm"], "team categories")
    check([x["title"] for x in st["schedule"]] == ["Opening Ceremony", "Time of Fall", "Colour Sort", "Shape Sort", "Awards Ceremony"], "schedule rows: %r" % [x["title"] for x in st["schedule"]])
    check(w.concepts and w.concepts[-1][0] == "teamnames" and "team falcon" in w.concepts[-1][2] and "arm strong" in w.concepts[-1][2] and "orion the" in w.concepts[-1][2],
          "team names not loaded into the dialog: %r" % (w.concepts[-1:],))
    check(("ALBasicAwareness", "setTrackingMode", ("Head",)) in w.calls, "Pepper not set to head tracking")
    check(w.mem.get("Host/ControllerToken") == box.token, "token not written")
    check(w.tablet_cb is not None, "tablet events not connected")
    check(box.content and len(box.content["games"]) == 10, "content.json not read")
    dc = [(c[1], c[2]) for c in w.calls if c[0] == "ALDialog"]
    names = [x[0] for x in dc]
    check(names.index("unloadTopic") < names.index("loadTopic") and names.count("loadTopic") == 1, "old topic not removed before loading: %r" % names)
    check(any(x[0] == "loadTopic" and x[1][0].endswith(os.path.join("Host", "Host_enu.top")) for x in dc), "topic path")
    check(("activateTopic", ("Host",)) in dc and ("subscribe", ("HostController",)) in dc, "topic not activated / not listening")
    check(not any("could not start the dialog" in m for _, m in w.logs), "dialog start failed: %r" % [m for _, m in w.logs if "dialog" in m])

    # ---- dialog check: alive
    tick(w, box, 4.5)
    check(w.forced.count("robotcmd ping") == 1 and box.listen is True, "voice check: %r %r" % (w.forced, box.listen))

    # ---- dialog commands
    dlg(w, box, "game", hostGame="tof")
    check(w.said[-1].startswith("Time of Fall is a robot tug of war"), "game explain: %r" % w.said[-1:])
    check(any('HostUI.go("game","tof")' in j for j in w.js), "tablet not moved to the game")
    dlg(w, box, "game", hostGame="nonsense")
    check(w.said[-1].startswith("Time of Fall"), "unknown game made Pepper speak")
    dlg(w, box, "team", hostTeam="team falcon")
    check("Team Falcon from Croatia competes in the Arena. Their next match: Time of Fall, at 14:40." == w.said[-1], "team info: %r" % w.said[-1])
    dlg(w, box, "team", hostTeam="arm strong")
    check(w.said[-1].startswith("Arm Strong from Portugal competes in the Robot Arm AI Challenge"), "say-as for team: %r" % w.said[-1])
    dlg(w, box, "team", hostTeam="unknown team")
    check("could not find" in w.said[-1], "unknown team")
    dlg(w, box, "next")
    check("Next. At 14:00: Opening Ceremony." in w.said[-1], "next line: %r" % w.said[-1])
    dlg(w, box, "scores")
    check("There are no scores yet" in w.said[-1], "no scores line")
    dlg(w, box, "teams")
    check(w.said[-1] == "3 teams are taking part: 2 teams in the Arena and 1 team in the Robot Arm AI Challenge.", "teams line: %r" % w.said[-1])
    dlg(w, box, "time")
    check(w.said[-1] == "It is 13:00.", "time line (Malta): %r" % w.said[-1])
    n = len(w.said)
    dlg(w, box, "nu"); dlg(w, box, "nu")
    check(len(w.said) == n, "not-understood spoke while Pepper was talking / too often")
    w.mem["ALBasicAwareness/HumanTracked"] = -1; tick(w, box, 61); dlg(w, box, "nu")
    check(len(w.said) == n, "not-understood answered noise with nobody at Pepper")
    w.mem["ALBasicAwareness/HumanTracked"] = 2; dlg(w, box, "nu")
    check(w.said[-1].startswith("Sorry, I did not catch that"), "not understood line")
    tick(w, box, 30); dlg(w, box, "nu"); check(len(w.said) == n + 1, "not-understood more than once a minute")
    tick(w, box, 31); box.quizOn = 0; dlg(w, box, "nu"); check(len(w.said) == n + 1, "not-understood during the quiz")
    box.quizOn = None; dlg(w, box, "nu"); check(len(w.said) == n + 2, "not-understood after the quiz")
    w.mem["ALBasicAwareness/HumanTracked"] = -1
    dlg(w, box, "stop")
    check(("ALTextToSpeech", "stopAll", ()) in w.calls, "stop did not stop speech")
    dlg(w, box, "ans", hostAns="2")
    check(w.js[-1].endswith("HostUI.answer(2)}catch(e){}") or any("HostUI.answer(2)" in j for j in w.js[-3:]), "voice answer not passed to the tablet")
    dlg(w, box, "quiz")
    check(any("HostUI.quizStart()" in j for j in w.js[-3:]), "voice quiz start")
    for c in ("hello", "who", "about", "thanks", "bye", "arena", "arm", "games"):
        k = len(w.said); dlg(w, box, c); check(len(w.said) == k + 1, "dialog command %s did not speak" % c)
    dlg(w, box, "info", hostInfo="0")
    check(w.said[-1] == "Please ask a volunteer at the information desk.", "info line")
    check(all(w.mem.get(k) == "" for k in ("hostCmd", "hostGame", "hostTeam", "hostAns")), "dialog keys not cleared")

    # ---- volunteer
    dlg(w, box, "help")
    st = last_state(w)
    check(len(st["alerts"]) == 1 and not st["alerts"][0]["seen"], "volunteer alert not in the state")
    check(w.said[-1] == "I have called a volunteer. Please wait here with me.", "volunteer line")
    tab(w, box, {"cmd": "volunteer"})
    check(len(last_state(w)["alerts"]) == 1 and "already on the way" in w.said[-1], "second call within 2 minutes made a second alert")

    # ---- tablet commands
    tab(w, box, {"cmd": "game", "game": "pour"})
    check(w.said[-1].startswith("In Pouring"), "tablet game explain")
    k = len(w.said)
    tab(w, box, {"cmd": "game", "game": "pour", "id": "same"}); tab(w, box, {"cmd": "game", "game": "pour", "id": "same"})
    check(len(w.said) == k + 1, "repeated tablet message not ignored")
    # every tap gets an answer: one short line per screen, not repeated within 15 s for the same screen
    lines = {}
    for v, a in (("home", ""), ("games", "arena"), ("games", "arm"), ("teams", ""), ("schedule", ""), ("scores", ""), ("quiz", ""), ("help", "")):
        k = len(w.said); tab(w, box, {"cmd": "view", "view": v, "arg": a})
        check(len(w.said) == k + 1 and len(w.said[-1]) < 200, "no short line for the %s screen: %r" % (v + "/" + a, w.said[k:]))
        lines[v + "/" + a] = w.said[-1]
    check(lines["teams/"].startswith("3 teams are taking part") and lines["games/arm"].startswith("This is the Robot Arm AI Challenge")
          and "provisional" in lines["scores/"] and "red button" in lines["help/"] and lines["schedule/"].startswith("Here is the programme."), "screen lines: %r" % lines)
    k = len(w.said); tab(w, box, {"cmd": "view", "view": "teams", "arg": ""}); tick(w, box, 10); tab(w, box, {"cmd": "view", "view": "teams", "arg": ""})
    check(len(w.said) == k, "the same screen line was repeated within 15 s")
    tick(w, box, 6); tab(w, box, {"cmd": "view", "view": "teams", "arg": ""})
    check(len(w.said) == k + 1, "the screen line did not come back after 15 s")
    tab(w, box, {"cmd": "quizq", "i": 0, "opts": [2, 0, 1]})
    check(w.said[-1] == "In Time of Fall, what do the robots try to do?", "quiz question (question only): %r" % w.said[-1])
    tab(w, box, {"cmd": "quiza", "i": 0, "ok": False})
    check(w.said[-1] == "Not quite.", "quiz wrong: %r" % w.said[-1])
    tab(w, box, {"cmd": "quiza", "i": 0, "ok": True})
    check(w.said[-1] in ("Correct!", "Yes! Well done!", "That is right!"), "quiz right: %r" % w.said[-1])
    tab(w, box, {"cmd": "quizend", "score": 5, "total": 5})
    check(w.said[-1].startswith("You got 5 out of 5. Brilliant"), "quiz end")
    tab(w, box, {"cmd": "quizq", "i": 99})
    tab(w, box, "not a dict" and {"cmd": "nothing"})
    box.onTablet("{broken json")

    # ---- staff
    tab(w, box, {"cmd": "team-save", "team": {"name": "Sneaky"}, "token": "guess"})
    check(not any(t["name"] == "Sneaky" for t in box.teams) and "HostUI.staffClosed()" in w.js[-1], "staff command without login accepted")
    tab(w, box, {"cmd": "staff-login", "pin": "0000"})
    check('"ok": false' in w.js[-1], "wrong PIN accepted")
    tab(w, box, {"cmd": "staff-login", "pin": "2468"})
    tok = json.loads(w.js[-1][len("try{HostUI.staff("):-len(")}catch(e){}")])["token"]
    check(len(tok) == 16, "no staff token")
    tab(w, box, {"cmd": "team-save", "team": {"name": "  Team <b>Kestrel</b>^start(x)  ", "country": "Malta", "cat": "arm"}, "token": tok})
    t = [x for x in box.teams if "Kestrel" in x["name"]]
    check(t and t[0]["name"] == "Team <b>Kestrel</b> start(x)" and t[0]["cat"] == "arm", "team add / cleaning: %r" % t)
    check("team kestrel b start x" not in str(w.concepts[-1]) and any("kestrel" in x for x in w.concepts[-1][2]), "concept not refreshed after team add")
    tab(w, box, {"cmd": "team-save", "team": {"name": "team falcon"}, "token": tok})
    check(sum(1 for x in box.teams if x["name"].lower() == "team falcon") == 1, "duplicate team added")
    fal = [x for x in box.teams if x["name"] == "Team Falcon"][0]
    tab(w, box, {"cmd": "score-save", "teamId": fal["id"], "points": 120, "token": tok})
    tab(w, box, {"cmd": "score-save", "teamId": fal["id"], "points": "130.5", "token": tok})
    tab(w, box, {"cmd": "score-save", "teamId": "nope", "points": 5, "token": tok})
    tab(w, box, {"cmd": "score-save", "teamId": fal["id"], "points": 1e9, "token": tok})
    check(len(box.scores) == 1 and box.scores[0]["points"] == 130.5, "score save/upsert/validation: %r" % box.scores)
    tab(w, box, {"cmd": "team-save", "team": {"id": fal["id"], "name": "Team Falcon X", "country": "Croatia", "cat": "arena"}, "token": tok})
    tof = [x for x in box.schedule if x["title"] == "Time of Fall"][0]
    check(tof["a"] == "Team Falcon X" and box.scores[0]["team"] == "Team Falcon X", "rename did not update schedule and scores")
    dlg(w, box, "scores")
    check("first, Team Falcon X with 130.5 points" in w.said[-1] and "provisional" in w.said[-1], "scores line: %r" % w.said[-1])
    tab(w, box, {"cmd": "sched-save", "item": {"day": "sat", "time": "9:5", "title": "x"}, "token": tok})
    check("Check the day" in w.js[-1], "bad time accepted")
    tab(w, box, {"cmd": "sched-save", "item": {"day": "sun", "time": "9:30", "mins": 20, "title": "Hanging Hazard final", "cat": "arena", "game": "hh", "a": "Team Falcon X", "b": "Orion, The"}, "token": tok})
    new = [x for x in box.schedule if x["title"] == "Hanging Hazard final"]
    check(new and new[0]["time"] == "09:30" and new[0]["mins"] == 20, "schedule add: %r" % new)
    tab(w, box, {"cmd": "sched-save", "item": dict(new[0], done=True), "token": tok})
    check([x for x in box.schedule if x["title"] == "Hanging Hazard final"][0]["done"] is True, "mark done")
    tab(w, box, {"cmd": "sched-del", "key": new[0]["id"], "token": tok})
    check(not any(x["title"] == "Hanging Hazard final" for x in box.schedule), "schedule delete")
    aid = box.alerts[0]["id"]
    tab(w, box, {"cmd": "alert-seen", "key": aid, "token": tok})
    check(box.alerts[0]["seen"] is True, "alert seen")
    tab(w, box, {"cmd": "announce", "text": "Hello \\pau=500\\ everyone ^run(x) " + "x" * 400, "token": tok})
    check(w.said[-1].startswith("Hello pau=500 everyone run(x) x") and len(w.said[-1]) <= 300, "announce cleaning: %r" % w.said[-1][:60])
    kid = [x for x in box.teams if "Kestrel" in x["name"]][0]["id"]
    tab(w, box, {"cmd": "team-del", "key": kid, "token": tok})
    check(not any("Kestrel" in x["name"] for x in box.teams), "team delete")

    # ---- persistence across a restart
    w2 = World(app); w2.t = w.t
    box2, _ = start(w2, store=store)
    check([t["name"] for t in box2.teams] == [t["name"] for t in box.teams] and len(box2.scores) == 1 and box2.alerts[0]["seen"], "staff changes not kept after restart")
    tab(w2, box2, {"cmd": "staff-login", "pin": "2468"})
    tok2 = json.loads(w2.js[-1][len("try{HostUI.staff("):-len(")}catch(e){}")])["token"]
    tab(w2, box2, {"cmd": "reload", "token": tok2})
    check([t["name"] for t in box2.teams] == ["Team Falcon", "Orion, The", "ArmStrong"] and len(box2.scores) == 1, "reload from files")
    tab(w2, box2, {"cmd": "calls", "on": False, "token": tok2})
    check(box2.calls is False, "calls toggle")
    w2.t += 400; tick(w2, box2, 5.1)
    check("HostUI.staffClosed()" in "".join(w2.js[-5:]), "staff session did not expire")
    tab(w2, box2, {"cmd": "calls", "on": True, "token": tok2})
    check(box2.calls is False, "expired token accepted")

    # ---- PIN rate limit
    for i in range(6):
        tab(w2, box2, {"cmd": "staff-login", "pin": "1111"})
    tab(w2, box2, {"cmd": "staff-login", "pin": "2468"})
    check('"wait": true' in w2.js[-1], "PIN tries not limited")

    # ---- match calls (fresh store)
    store3 = os.path.join(tmp, "store3")
    w3 = World(app); w3.t = utc(2026, 11, 28, 13, 29)          # 14:29 Malta, TOF at 14:40
    box3, ns3 = start(w3, store=store3)
    w3.mem["hostPong"] = "ok1"
    tick(w3, box3, 5.2)
    check(not any("Attention teams" in s for s in w3.said), "called too early")
    w3.t = utc(2026, 11, 28, 13, 30) + 1; tick(w3, box3, 5.2)
    calls = [s for s in w3.said if "Attention teams" in s]
    check(len(calls) == 1 and calls[0] == "Attention teams. In ten minutes, in the Arena: Time of Fall. First match: Team Falcon in the red corner, against Orion, The in the blue corner. Please get ready.",
          "match call: %r" % calls)
    tick(w3, box3, 20)
    check(len([s for s in w3.said if "Attention teams" in s]) == 1, "match call repeated")
    w3b = World(app); w3b.t = w3.t
    w3.t = utc(2026, 11, 28, 13, 40) + 2; tick(w3, box3, 5.2)
    check(not any(s.startswith("Starting now") for s in w3.said), "match start announced although that setting is off")
    w3b.t = w3.t - 600
    box3b, _ = start(w3b, params={"Announce match starts": True}, store=store3); w3b.mem["hostPong"] = "ok1"; tick(w3b, box3b, 6)
    check(not any("Attention teams" in s for s in w3b.said), "match call repeated after a restart")
    w3b.t = utc(2026, 11, 28, 13, 40) + 2; tick(w3b, box3b, 5.2)
    check(any(s == "Starting now: Time of Fall! Red corner: Team Falcon. Blue corner: Orion, The. Good luck to both teams!" for s in w3b.said), "start announcement: %r" % w3b.said[-1:])
    w3b.t = utc(2026, 11, 28, 13, 50) + 2; tick(w3b, box3b, 5.2)
    check(any(s == "Attention teams. In ten minutes, at the Robot Arm AI Challenge: Colour Sort. First up: Arm Strong. Please get ready." for s in w3b.said), "arm call: %r" % w3b.said[-2:])
    k = len(w3b.said); w3b.t = utc(2026, 11, 28, 14, 50) + 2; tick(w3b, box3b, 5.2); w3b.t = utc(2026, 11, 28, 15, 0) + 2; tick(w3b, box3b, 5.2)
    check(len(w3b.said) == k, "a finished (done) match was called: %r" % w3b.said[k:])
    w3b.t = utc(2026, 11, 29, 16, 50) + 2; tick(w3b, box3b, 5.2)
    check(w3b.said[-1] == "Attention please. The Awards Ceremony starts in ten minutes.", "stage call: %r" % w3b.said[-1:])
    store4 = os.path.join(tmp, "store4")
    w4 = World(app); w4.t = utc(2026, 11, 28, 13, 35)            # restarted 5 minutes before: too late for the call
    box4, _ = start(w4, store=store4); w4.mem["hostPong"] = "ok1"; tick(w4, box4, 6)
    check(not any("Attention teams" in s for s in w4.said), "late call after a restart")
    w5 = World(app); w5.t = utc(2026, 11, 28, 13, 30) + 1
    box5, _ = start(w5, params={"Match calls": False}, store=os.path.join(tmp, "store5")); w5.mem["hostPong"] = "ok1"; tick(w5, box5, 6)
    check(not any("Attention" in s for s in w5.said), "calls made while switched off")

    # ---- one call per block: three Time of Fall matches 4 minutes apart, then a later block
    blk = os.path.join(tmp, "blk"); shutil.copytree(app, blk)
    io.open(os.path.join(blk, "html", "data", "schedule.csv"), "w", encoding="utf-8").write(
        u"day,time,minutes,title,category,game,side_a,side_b,done\nsat,15:20,4,Time of Fall,arena,tof,Team Falcon,ArmStrong,\n"
        u"sat,15:24,4,Time of Fall,arena,tof,Orion,Team Falcon,\nsat,15:28,4,Time of Fall,arena,tof,ArmStrong,Orion,\n"
        u"sat,18:15,12,Climate CHAOS,arena,chaos,Team Falcon,,\nsat,18:27,12,Climate CHAOS,arena,chaos,Orion,,\n"
        u"sat,17:50,10,AI for Humanity Pitch 4,stage,,,,\n")
    wb = World(blk); wb.t = utc(2026, 11, 28, 14, 9)
    boxb, _ = start(wb, store=os.path.join(tmp, "sb")); wb.mem["hostPong"] = "ok1"
    for _ in range(30):
        wb.t += 60; tick(wb, boxb, 0.1); boxb.lastCallCheck = 0
    calls = [x for x in wb.said if x.startswith("Attention")]
    check(len(calls) == 1 and "Time of Fall" in calls[0], "a block of three matches should get one call: %r" % calls)
    wb.t = utc(2026, 11, 28, 16, 40)
    for _ in range(140):
        wb.t += 60; tick(wb, boxb, 0.1); boxb.lastCallCheck = 0
    calls = [x for x in wb.said if x.startswith("Attention")]
    check(len(calls) == 2 and calls[1] == "Attention teams. In ten minutes, in the Arena: Climate Chaos. First up: Team Falcon. Please get ready.",
          "second block / short stage items: %r" % calls)

    # ---- Pepper's intro
    wi = World(app); wi.t = utc(2026, 11, 28, 13, 26)
    boxi, nsi = start(wi, store=os.path.join(tmp, "si")); wi.mem["hostPong"] = "ok1"; tick(wi, boxi, 5)
    scenes = boxi.content["intro"]
    wi.speech_s = 9   # a long first sentence: the scene must wait for Pepper to finish
    dlg(wi, boxi, "intro")
    check(boxi.intro is not None and boxi.intro["i"] == 0 and any('HostUI.go("intro","")' in j for j in wi.js), "intro did not start by voice")
    check(wi.said[-1].startswith("Hello everyone, and welcome to the I triple E Robot Championships 2026"), "intro scene 1: %r" % wi.said[-1])
    st = last_state(wi)["intro"]
    check(st["i"] == 0 and st["n"] == len(scenes) == 12 and st["kind"] == "title" and st["head"] == "Hello! I am Pepper", "intro state: %r" % st)
    tick(wi, boxi, 7)
    check(boxi.intro["i"] == 0, "scene left while Pepper was still talking")
    wi.speech_s = 3; tick(wi, boxi, 3)
    check(boxi.intro["i"] == 1, "scene did not move on after Pepper finished: %r" % boxi.intro)
    seen = [0, boxi.intro["i"]]
    for _ in range(1500):
        tick(wi, boxi, 0.1)
        if boxi.intro is None:
            break
        if boxi.intro["i"] != seen[-1]:
            seen.append(boxi.intro["i"])
    check(seen == list(range(12)) and boxi.intro is None, "intro scenes not shown in order: %r" % seen)
    said = wi.said[-12:]
    check(said[1] == "This weekend, 3 university teams compete in two competitions: 2 teams in the Arena, and 1 teams in the new Robot Arm AI Challenge.", "event scene: %r" % said[1])
    check(said[9] == "Please give a big welcome to our Arena teams: Orion, The and Team Falcon. And to our Robot Arm teams: Arm Strong.", "teams scene: %r" % said[9])
    check(said[10].startswith("Coming up next, at 14:40: Time of Fall in the Arena"), "next scene: %r" % said[10])
    check(not any("{" in x for x in said), "a template was not filled: %r" % [x for x in said if "{" in x])
    check(any('HostUI.go("home","")' in j for j in wi.js[-3:]) and last_state(wi)["intro"] is None, "intro end did not return home")
    tab(wi, boxi, {"cmd": "intro"}); tick(wi, boxi, 1)
    check(boxi.intro is not None, "intro did not start from the tablet")
    n0 = len(wi.said); dlg(wi, boxi, "nu"); check(len(wi.said) == n0, "not-understood spoke during the intro")
    tab(wi, boxi, {"cmd": "intro-stop"})
    check(boxi.intro is None and ("ALTextToSpeech", "stopAll", ()) in wi.calls, "intro did not stop")
    dlg(wi, boxi, "intro"); dlg(wi, boxi, "stop"); check(boxi.intro is None, "voice stop did not end the intro")
    # a match call during the intro ends the intro first
    wi.t = utc(2026, 11, 28, 13, 30) + 1; tab(wi, boxi, {"cmd": "intro"}); boxi.lastCallCheck = 0; tick(wi, boxi, 0.2)
    check(boxi.intro is None and wi.said[-1].startswith("Attention teams. In ten minutes, in the Arena: Time of Fall"), "match call during the intro: %r" % wi.said[-1:])
    # a quiz left half way must not keep Pepper quiet for ever
    wqz = World(app); wqz.t = utc(2026, 11, 28, 9, 0)
    boxqz, _ = start(wqz, store=os.path.join(tmp, "sqz")); wqz.mem["hostPong"] = "ok1"; tick(wqz, boxqz, 5)
    tab(wqz, boxqz, {"cmd": "quizq", "i": 3, "opts": [0, 1, 2]}); check(boxqz.quizOn == 3, "quiz flag not set")
    tab(wqz, boxqz, {"cmd": "view", "view": "teams", "arg": ""}); check(boxqz.quizOn is None, "quiz flag kept after the visitor left the quiz")
    tab(wqz, boxqz, {"cmd": "quizq", "i": 4, "opts": [0, 1, 2]}); tick(wqz, boxqz, 120)
    tab(wqz, boxqz, {"cmd": "quiza", "i": 4, "ok": True}); tick(wqz, boxqz, 120)
    check(boxqz.quizOn == 4, "quiz flag cleared while the visitor was still answering")
    tick(wqz, boxqz, 70); check(boxqz.quizOn is None, "quiz flag kept after 3 minutes without an answer")
    wqz.mem["ALBasicAwareness/HumanTracked"] = 1
    for _ in range(12):
        wqz.t += 60; tick(wqz, boxqz, 0.1); boxqz.lastCallCheck = 0
    check(boxqz.intro is not None, "no automatic intro after an abandoned quiz")

    # once at every start, a few seconds after launch (box parameter "Intro at start", on by default in the app)
    wst = World(app); wst.t = utc(2026, 11, 28, 9, 0)
    boxst, _ = start(wst, params={"Intro at start": True}, store=os.path.join(tmp, "sst")); wst.mem["hostPong"] = "ok1"
    tick(wst, boxst, 6); check(boxst.intro is None, "intro started before the tablet had time to load")
    tick(wst, boxst, 3); check(boxst.intro is not None and boxst.intro["i"] == 0 and wst.said[-1].startswith("Hello everyone"), "no intro at start")
    for _ in range(1500):
        tick(wst, boxst, 0.1)
        if boxst.intro is None:
            break
    tick(wst, boxst, 30); check(boxst.intro is None, "intro at start played more than once")
    wso = World(app); boxso, _ = start(wso, store=os.path.join(tmp, "sso")); tick(wso, boxso, 12)
    check(boxso.intro is None, "intro at start played although the parameter is off")
    view_k = len(wi.said); tab(wi, boxi, {"cmd": "intro"}); tab(wi, boxi, {"cmd": "view", "view": "teams", "arg": ""})
    check(wi.said[-1].startswith("Hello everyone"), "a screen line interrupted the intro: %r" % wi.said[-1:])
    tab(wi, boxi, {"cmd": "intro-stop"})

    # by itself after 10 quiet minutes, only when someone is near, and staff can switch it off
    wa = World(app); wa.t = utc(2026, 11, 28, 9, 0)
    boxa, _ = start(wa, store=os.path.join(tmp, "sa")); wa.mem["hostPong"] = "ok1"
    wa.mem["ALBasicAwareness/HumanTracked"] = -1
    for _ in range(12):
        wa.t += 60; tick(wa, boxa, 0.1); boxa.lastCallCheck = 0
    check(boxa.intro is None, "intro started with nobody near")
    wa.mem["ALBasicAwareness/HumanTracked"] = 2; tick(wa, boxa, 0.1); boxa.lastCallCheck = 0; tick(wa, boxa, 0.1)
    check(boxa.intro is not None, "no intro after 10 quiet minutes with someone near")
    tab(wa, boxa, {"cmd": "intro-stop"})
    for _ in range(5):
        wa.t += 60; tick(wa, boxa, 0.1); boxa.lastCallCheck = 0
    check(boxa.intro is None, "intro came back too soon after a touch")
    tab(wa, boxa, {"cmd": "staff-login", "pin": "2468"})
    ta = json.loads(wa.js[-1][len("try{HostUI.staff("):-len(")}catch(e){}")])["token"]
    tab(wa, boxa, {"cmd": "intro-auto", "on": False, "token": ta})
    for _ in range(15):
        wa.t += 60; tick(wa, boxa, 0.1); boxa.lastCallCheck = 0
    check(boxa.intro is None and last_state(wa)["introAuto"] is False, "intro started although staff switched it off")
    tab(wa, boxa, {"cmd": "staff-login", "pin": "2468"})
    ta = json.loads(wa.js[-1][len("try{HostUI.staff("):-len(")}catch(e){}")])["token"]
    tab(wa, boxa, {"cmd": "intro-start", "token": ta}); check(boxa.intro is not None, "staff could not start the intro")
    tab(wa, boxa, {"cmd": "intro-auto", "on": True, "token": ta})
    for _ in range(1500):
        tick(wa, boxa, 0.1)
        if boxa.intro is None:
            break
    check(boxa.intro is None, "staff intro did not finish")
    again = False
    for _ in range(5):
        wa.t += 60; tick(wa, boxa, 0.1); boxa.lastCallCheck = 0; again = again or boxa.intro is not None
    check(not again, "intro started again right after it finished")
    w0 = World(app); w0.t = utc(2026, 11, 28, 9, 0)
    box0, _ = start(w0, params={"Intro when idle (minutes)": 0}, store=os.path.join(tmp, "s0")); w0.mem["ALBasicAwareness/HumanTracked"] = 3
    ever = False
    for _ in range(30):
        w0.t += 60; tick(w0, box0, 0.1); box0.lastCallCheck = 0; ever = ever or box0.intro is not None
    check(not ever, "intro started by itself although the box parameter is 0")
    tab(w0, box0, {"cmd": "staff-login", "pin": "2468"})
    t0 = json.loads(w0.js[-1][len("try{HostUI.staff("):-len(")}catch(e){}")])["token"]
    tab(w0, box0, {"cmd": "intro-auto", "on": True, "token": t0})
    for _ in range(30):
        w0.t += 60; tick(w0, box0, 0.1); box0.lastCallCheck = 0; ever = ever or box0.intro is not None
    check(not ever, "parameter 0 and staff switched the automatic intro on: it must still wait to be asked")
    check(nsi["MyClass"]._introFill is not None, "intro helpers missing")

    # ---- dialog check: repair and failure
    w6 = World(app); w6.ping_fail = 1
    box6, _ = start(w6, store=os.path.join(tmp, "s6")); tick(w6, box6, 12)
    check(box6.listen is True and [c[1] for c in w6.calls if c[0] == "ALDialog"].count("loadTopic") == 2, "dialog repair (reload): %r" % box6.listen)
    w7 = World(app); w7.dialog_alive = False
    box7, _ = start(w7, store=os.path.join(tmp, "s7")); tick(w7, box7, 12)
    check(box7.listen is False and last_state(w7)["voice"] is False, "dead dialog not reported")
    check(not any("voice" in s.lower() for s in w7.said), "Pepper spoke about the dead dialog")
    dlg(w7, box7, "hello")
    check(box7.listen is True, "listening not restored after the dialog spoke")

    # ---- greeting
    w8 = World(app); box8, _ = start(w8, store=os.path.join(tmp, "s8")); w8.mem["hostPong"] = "ok1"
    w8.mem["ALBasicAwareness/HumanTracked"] = -1; tick(w8, box8, 25)
    k = len(w8.said)
    w8.mem["ALBasicAwareness/HumanTracked"] = 3; tick(w8, box8, 5.2)
    check(len(w8.said) == k + 1, "no greeting for a new visitor")
    w8.mem["ALBasicAwareness/HumanTracked"] = -1; tick(w8, box8, 25); w8.mem["ALBasicAwareness/HumanTracked"] = 4; tick(w8, box8, 5.2)
    check(len(w8.said) == k + 1, "greeting not rate limited (2 minutes)")
    w8.mem["ALBasicAwareness/HumanTracked"] = -1; tick(w8, box8, 95); w8.mem["ALBasicAwareness/HumanTracked"] = 5; tick(w8, box8, 5.2)
    check(len(w8.said) == k + 2, "no greeting after the 2 minute pause")

    # ---- Pepper's clock was 11 hours wrong on the robot: staff correct it, every timer moves with it, it survives a restart
    wc = World(app); wc.t = utc(2026, 11, 21, 5, 35)          # Pepper thinks it is 06:35 in Malta, it is really 17:52
    boxc, _ = start(wc, store=os.path.join(tmp, "sclk")); wc.mem["hostPong"] = "ok1"; tick(wc, boxc, 3)
    tab(wc, boxc, {"cmd": "staff-login", "pin": "2468"})
    tc = json.loads(wc.js[-1][len("try{HostUI.staff("):-len(")}catch(e){}")])["token"]
    act_before = boxc.lastActivity
    tab(wc, boxc, {"cmd": "set-clock", "date": "2026-11-21", "time": "17:52", "token": tc})
    check(abs(boxc.clock() - utc(2026, 11, 21, 16, 52)) < 2, "clock not corrected: %s" % boxc.clock())
    check(ns["malta_hhmm"](boxc.clock()) == "17:52", "Malta time after the correction")
    check(boxc.lastActivity - act_before > 11 * 3600 - 60, "timers did not move with the clock")
    boxc._flushJs(); st = json.loads(wc.mem["Host/State"])
    check(abs(st["now"] / 1000.0 - utc(2026, 11, 21, 16, 52)) < 2 and st["clockFix"] == 677, "tablet not told the corrected time: %r" % st.get("clockFix"))
    tab(wc, boxc, {"cmd": "calls", "on": True, "token": tc}); check(boxc.calls is True, "staff session expired because of the clock correction")
    n = len(wc.said); tick(wc, boxc, 2); check(boxc.intro is None, "the clock jump started the intro")
    boxc.onInput_onStop()
    boxc2, _ = start(wc, store=os.path.join(tmp, "sclk")); wc.mem["hostPong"] = "ok1"; tick(wc, boxc2, 1)
    check(ns["malta_hhmm"](boxc2.clock()) == "17:53" or ns["malta_hhmm"](boxc2.clock()) == "17:52", "clock correction lost after a restart: %s" % ns["malta_hhmm"](boxc2.clock()))
    tab(wc, boxc2, {"cmd": "staff-login", "pin": "2468"})
    tc2 = json.loads(wc.js[-1][len("try{HostUI.staff("):-len(")}catch(e){}")])["token"]
    tab(wc, boxc2, {"cmd": "set-clock", "date": "21/11/2026", "time": "nonsense", "token": tc2})
    check(ns["malta_hhmm"](boxc2.clock()) in ("17:52", "17:53"), "a bad date changed the clock")
    tab(wc, boxc2, {"cmd": "set-clock", "date": "2026-11-21", "time": "17:52"})
    tab(wc, boxc2, {"cmd": "set-clock", "reset": True, "token": "wrong"})
    check(boxc2.clockOffset != 0, "the clock changed without a staff login")
    tab(wc, boxc2, {"cmd": "set-clock", "reset": True, "token": tc2}); check(boxc2.clockOffset == 0, "undo the correction")
    boxc2.onInput_onStop()

    # ---- pronunciation: Pepper's voice would spell out IEEE, Ctrl and CHAOS, and read symbols aloud
    sp = ns["speakable"]
    for a, b in (("the IEEE Robot Championships", "the I triple E Robot Championships"), ("Ctrl Alt Defeat", "Control Alt Defeat"),
                 ("Climate CHAOS", "Climate Chaos"), ("BRIS - SWERVY", "BRIS SWERVY"), ("Tower C +150", "Tower C 150"),
                 ("Red: A vs Blue: B", "Red: A versus Blue: B"), ("cat & dog", "cat and dog"), (u"8 Arena \u00b7 5 Robot Arm", u"8 Arena, 5 Robot Arm"), (u"a \u2013 b", u"a b"), ("There are 2 teams", "There are 2 teams"),
                 ("What is a LiDAR?", "What is a lidar?"), ("Pick-and-Place", "Pick and Place"), ("IEEEE", "IEEEE")):
        check(sp(a) == b, "speakable(%r) = %r, want %r" % (a, sp(a), b))
    wsp = World(app); boxsp, _ = start(wsp, store=os.path.join(tmp, "ssp")); wsp.mem["hostPong"] = "ok1"; tick(wsp, boxsp, 3)
    for v, a in (("home", ""), ("games", "arena"), ("games", "arm"), ("teams", ""), ("schedule", ""), ("scores", ""), ("quiz", ""), ("help", "")):
        tab(wsp, boxsp, {"cmd": "view", "view": v, "arg": a})
    for g in boxsp.content["games"]:
        tab(wsp, boxsp, {"cmd": "game", "game": g["id"]})
    tab(wsp, boxsp, {"cmd": "intro"})
    for _ in range(1500):
        tick(wsp, boxsp, 0.1)
        if boxsp.intro is None:
            break
    for i in range(len(boxsp.content["quiz"])):
        tab(wsp, boxsp, {"cmd": "quizq", "i": i, "opts": [0, 1, 2]})
    bad = [x for x in wsp.said if re.search(r"\bIEEE\b|\bCHAOS\b|\bCtrl\b|\u00b7| - |&|\+\d|\bvs\b|\u2014", x)]
    print("spoken lines checked:", len(wsp.said)); check(len(wsp.said) > 60 and not bad, "Pepper would misread: %r" % bad[:5])
    tab(wsp, boxsp, {"cmd": "staff-login", "pin": "2468"})
    tsp = json.loads(wsp.js[-1][len("try{HostUI.staff("):-len(")}catch(e){}")])["token"]
    tab(wsp, boxsp, {"cmd": "say-teams", "token": tsp})
    check(wsp.said[-1].startswith("Our teams: ") and all(sp(boxsp._name(t["name"])) in wsp.said[-1] for t in boxsp.teams), "say every team name: %r" % wsp.said[-1])
    n = len(wsp.said); tab(wsp, boxsp, {"cmd": "say-teams", "token": "wrong"}); check(len(wsp.said) == n, "say-teams without a staff login")
    boxsp.onInput_onStop()

    # ---- two copies running (Play pressed twice): only the newest answers, the other lets go of the tablet
    wd = World(app); wd.mem["hostPong"] = "ok1"
    boxA, _ = start(wd, store=os.path.join(tmp, "sdA")); tick(wd, boxA, 5)
    boxB, _ = start(wd, store=os.path.join(tmp, "sdB")); tick(wd, boxB, 0.1)
    tick(wd, boxA, 0.2)
    check(boxA.running is False and len(wd.links) == 1, "older copy still connected to the tablet: %r" % sorted(wd.links))
    n = len(wd.said)
    for cb in list(wd.links.values()):
        cb(json.dumps({"cmd": "game", "game": "tof", "id": "dup1"}))
    boxB._flushJs()
    check(len(wd.said) == n + 1, "a tap was answered %d times" % (len(wd.said) - n))
    n = len(wd.said); boxA.onTablet(json.dumps({"cmd": "game", "game": "tof", "id": "dup2"}))
    check(len(wd.said) == n, "a replaced copy still answers the tablet")
    boxB.onInput_onStop()
    check(wd.links == {} and ("ALTabletService", "onJSEvent.disconnect", (2,)) in wd.calls, "stop left the tablet connected")
    n = len(wd.said); boxB.onTablet(json.dumps({"cmd": "game", "game": "tof", "id": "dup3"}))
    check(len(wd.said) == n, "a stopped copy still answers the tablet")

    # ---- takeover and stop
    w.mem["Host/ControllerToken"] = "someone-else"; box.running = True; tick(w, box)
    check(box.running is False, "older controller did not step down")
    box.running = True; box.onInput_onStop()
    check(("box", "onStopped", ()) in w.calls and ("ALBasicAwareness", "setTrackingMode", ("BodyRotation",)) in w.calls, "stop did not restore tracking")
    check("Host" in w.loaded, "an older controller unloaded the topic a newer one uses")
    wq = World(app); boxq, _ = start(wq, store=os.path.join(tmp, "sq")); boxq.onInput_onStop()
    check(("ALDialog", "unsubscribe", ("HostController",)) in wq.calls and "Host" not in wq.loaded and wq.subs == [], "stop left the dialog loaded: %r %r" % (wq.loaded, wq.subs))
    wq2 = World(app); wq2.loaded, wq2.active = [], []
    boxq2, _ = start(wq2, store=os.path.join(tmp, "sq")); tick(wq2, boxq2, 5)
    check(boxq2.listen is True and not any(c[1] == "unloadTopic" for c in wq2.calls if c[0] == "ALDialog"), "clean start should just load")
    # speech: a future when NAOqi knows _async, a thread when it does not; never .post
    ws = World(app); boxs, _ = start(ws, store=os.path.join(tmp, "ss"))
    boxs.say("Hello there.")
    check(boxs.sayJob and boxs.sayJob[0] == "future" and boxs.speaking and ws.said[-1] == "Hello there.", "speech not started as a future")
    ws.t += 4; boxs._checkSpeaking()
    check(not boxs.speaking and boxs.sayJob is None, "speech end not noticed")
    boxs.say("One"); boxs.say("Two")
    check(("future", "cancel", ()) in ws.calls and ("ALTextToSpeech", "stopAll", ()) in ws.calls, "new sentence did not stop the old one")
    ws.no_async = True; n0 = ws.calls.count(("thread", "start", ()))
    boxs.say("Without async.")
    check(boxs.sayJob and boxs.sayJob[0] == "thread" and ws.calls.count(("thread", "start", ())) == n0 + 1 and boxs.speaking, "no thread fallback")
    check(not any("speech failed" in m for _, m in ws.logs + w.logs), "speech failed: %r" % [m for _, m in ws.logs if "speech" in m])

    # ---- the official team list shipped in the package (8 Arena teams, 5 Robot Arm teams; one name with accents)
    real = os.path.join(tmp, "real")
    shutil.copytree(os.path.join(ROOT, "ChampionshipHost"), real)
    wr = World(real)
    boxr, nsr = start(wr, store=os.path.join(tmp, "sr"))
    arena = [t["name"] for t in boxr.teams if t["cat"] == "arena"]
    arms = [t["name"] for t in boxr.teams if t["cat"] == "arm"]
    check(len(arena) == 8 and len(arms) == 4, "official list: %d arena, %d arm" % (len(arena), len(arms)))
    check(u"Troda\u00ed" in arena and "BRIS - SWERVY" in arena and arms == ["thumbi", "JARVIS", "TORC", "Indiarm"], "official names: %r %r" % (arena, arms))
    st = last_state(wr)
    check(len(st["teams"]) == 12 and any(t["name"] == u"Troda\u00ed" for t in st["teams"]), "accented name lost on the way to the tablet")
    words = wr.concepts[-1][2]
    check("trodai" in words and "bris swervy" in words and "ctrl alt defeat" in words and "electro nexus" in words and "jarvis" in words and "torc" in words and "electronexus" not in words,
          "dialog words: %r" % words)
    check(all(isinstance(x, str) and all(ord(c) < 128 for c in x) for x in words), "dialog words must be plain letters")
    dlg(wr, boxr, "teams")
    check(wr.said[-1] == "12 teams are taking part: 8 teams in the Arena and 4 teams in the Robot Arm AI Challenge.", "teams line: %r" % wr.said[-1])
    dlg(wr, boxr, "team", hostTeam="trodai")
    check(wr.said[-1].startswith(u"Troda\u00ed competes in the Arena".encode("utf-8") if str is bytes else u"Troda\u00ed competes in the Arena"),
          "accented team: %r" % wr.said[-1])
    dlg(wr, boxr, "team", hostTeam="electro nexus")
    check(wr.said[-1].startswith("Electro Nexus competes in the Arena."), "one team with that name now: %r" % wr.said[-1])
    dlg(wr, boxr, "team", hostTeam="bris swervy")
    check(wr.said[-1] == "BRIS SWERVY competes in the Arena. Their next match: Time of Fall, at 15:20.", "punctuation in a name: %r" % wr.said[-1])
    dlg(wr, boxr, "team", hostTeam="bua")
    check("could not find" in wr.said[-1], "a 3-letter fragment matched a team")
    dlg(wr, boxr, "team", hostTeam="indiarm")
    check(wr.said[-1] == "Indiarm competes in the Robot Arm AI Challenge. Their next match: Colour Sort, at 16:45.", "arm team from the official programme: %r" % wr.said[-1])
    tab(wr, boxr, {"cmd": "staff-login", "pin": "2468"})
    tokr = json.loads(wr.js[-1][len("try{HostUI.staff("):-len(")}catch(e){}")])["token"]
    tab(wr, boxr, {"cmd": "team-save", "team": {"name": "Indiarm", "cat": "arena"}, "token": tokr})
    check(len([t for t in boxr.teams if t["name"] == "Indiarm"]) == 2, "the same name in the other competition was refused")
    tab(wr, boxr, {"cmd": "team-save", "team": {"name": "indiarm", "cat": "arm"}, "token": tokr})
    check(len([t for t in boxr.teams if t["name"].lower() == "indiarm"]) == 2 and "already on the list" in wr.js[-1], "duplicate in the same competition accepted")
    tab(wr, boxr, {"cmd": "team-save", "team": {"name": "ElectroNexus", "cat": "arm"}, "token": tokr})     # a look-alike of an Arena team
    dlg(wr, boxr, "team", hostTeam="electro nexus")
    check(wr.said[-1] == "There are 2 teams with that name: Electro Nexus in the Arena and ElectroNexus in the Robot Arm AI Challenge.", "look-alike names: %r" % wr.said[-1])
    fx = [t for t in boxr.teams if t["name"] == u"Troda\u00ed"][0]
    tab(wr, boxr, {"cmd": "score-save", "teamId": fx["id"], "points": 42, "token": tokr})
    dlg(wr, boxr, "scores")
    check(u"first, Troda\u00ed with 42 points" in (wr.said[-1].decode("utf-8") if isinstance(wr.said[-1], bytes) else wr.said[-1]), "scores with an accented name: %r" % wr.said[-1])
    wr2 = World(real); wr2.t = wr.t
    boxr2, _ = start(wr2, store=os.path.join(tmp, "sr"))
    check(any(t["name"] == u"Troda\u00ed" for t in boxr2.teams) and len(boxr2.teams) == 14, "accented name not kept across a restart")

    # ---- helpers
    rows = ns["parse_csv"](u"﻿name,x\r\n\"a \"\"b\"\", c\",1\r\n# c\r\n\r\nd,2")
    check(rows == [{"name": u'a "b", c', "x": u"1"}, {"name": u"d", "x": u"2"}], "csv parser: %r" % rows)
    check(ns["clean_text"](u"a\nb\x00^c\\d", 99) == u"a b c d", "clean_text")
    check(ns["malta_hhmm"](utc(2026, 11, 28, 23, 30)) == "00:30", "Malta clock")
    shutil.rmtree(tmp)

if __name__ == "__main__":
    run()
    print("%s: %s" % (sys.version.split()[0], "CONTROLLER OK" if not FAILS else "%d FAILURES" % len(FAILS)))
    rc = 1 if FAILS else 0
    if sys.version_info[0] == 3 and os.path.exists(PY27) and "--no27" not in sys.argv:
        rc = rc or subprocess.call([PY27, os.path.abspath(__file__), "--no27"])
    sys.exit(rc)
