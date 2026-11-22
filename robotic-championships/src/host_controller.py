# Host Controller: Pepper as the neutral host of the IEEE Robot Championships 2026 (Choregraphe 2.5, NAOqi 2.5, Python 2.7).
#
# What it does
#   - Speaks for Pepper (ALAnimatedSpeech, with gestures) and keeps the tablet up to date (ALTabletService.executeJS).
#   - Reads what the dialog heard ($hostCmd and friends, written by Host_enu.top) and what was touched on the tablet.
#   - Holds the teams, the programme, provisional scores and volunteer calls. Teams and programme start from
#     html/data/teams.csv and schedule.csv; staff changes on the tablet are kept on the robot (~/.local/share/championship-host).
#   - Calls the two teams 10 minutes before each scheduled match, and announces matches as they start (staff can turn this off).
#   - Every team is treated the same way. Pepper never comments on a team and never states an official result.
# Nothing here goes to the internet.
import json, os, io, re, time, random, threading, unicodedata, calendar

VERSION = "1.2.1"
TOKEN_KEY = "Host/ControllerToken"
KEYS = ["hostCmd", "hostTeam", "hostGame", "hostAns", "hostInfo", "Host/TabletCmd", TOKEN_KEY]
STATE_KEY, STATE_EVT = "Host/State", "Host/Session"
STORE_DIR = os.path.expanduser("~/.local/share/championship-host")
DIALOG_NAME = "host"            # the topic in Host/Host_enu.top, compared in lower case
DIALOG_SUB = "HostController"
PONG = "ok1"
CALL_BEFORE_S = 600             # match call 10 minutes before (rulebook 6.5: teams get 10 minutes' notice)
CALL_WINDOW_S = 120             # a call is only made in the first 2 minutes of that window (no late calls after a restart)
START_WINDOW_S = 90             # "starting now" only in the first 90 s
NU_GAP_S = 60.0
VIEW_GAP_S = 15.0
QUIZ_IDLE_S = 180.0           # a quiz with no answer for 3 minutes was left half way             # the same screen's line is not repeated within 15 s
INTRO_START_S = 8.0           # Pepper gives its intro this long after the app starts (the tablet has loaded by then)
GREET_GAP_S = 120.0           # v1.1: Pepper talks less on its own
BLOCK_GAP_S = 600             # matches less than 10 minutes apart form one block: one call per block
INTRO_MIN_S = 4.0             # each intro scene stays at least this long (clips at least INTRO_CLIP_S)
INTRO_CLIP_S = 6.0
INTRO_MAX_S = 40.0            # and at most this long, even if speech never reports that it ended
STAFF_TTL_S = 300.0
PIN_TRIES, PIN_WINDOW_S = 5, 60.0
PUSH_BEAT_S = 4.0
MALTA_UTC_OFFSET_S = 3600       # Malta is UTC+1 in November
EVENT_DAY_UTC = {"sat": 1795824000, "sun": 1795910400}   # 28 and 29 November 2026, 00:00 UTC

try:
    unicode
    def _s(x):
        if isinstance(x, unicode):
            return x.encode("utf-8")
        return str(x)
    def _u(x):
        if isinstance(x, unicode):
            return x
        return str(x).decode("utf-8", "replace")
except NameError:
    def _s(x):
        return x if isinstance(x, str) else str(x)
    def _u(x):
        return x.decode("utf-8", "replace") if isinstance(x, bytes) else str(x)


def clean_text(x, n):
    """Text from a person (staff, a CSV file) made safe to speak and to show: no control characters, no speech
    annotations (^ and backslash tags), at most n characters."""
    t = _u(x if x is not None else "")
    t = re.sub(u"[\\x00-\\x1f\\x7f]", u" ", t)
    t = t.replace(u"^", u" ").replace(u"\\", u" ")
    t = re.sub(u"\\s+", u" ", t).strip()
    return t[:n]


def parse_csv(text):
    """Header row, then one record per line. Lines starting with # are notes. Quotes allowed (same rules as the tablet)."""
    text = _u(text)
    if text[:1] == u"\ufeff":
        text = text[1:]
    rows, row, f, q, i = [], [], u"", False, 0
    while i < len(text):
        c = text[i]
        if q:
            if c == u'"':
                if text[i + 1:i + 2] == u'"':
                    f += u'"'; i += 1
                else:
                    q = False
            else:
                f += c
        elif c == u'"':
            q = True
        elif c == u",":
            row.append(f); f = u""
        elif c in (u"\n", u"\r"):
            if c == u"\r" and text[i + 1:i + 2] == u"\n":
                i += 1
            row.append(f); f = u""; rows.append(row); row = []
        else:
            f += c
        i += 1
    if f != u"" or row:
        row.append(f); rows.append(row)
    out, head = [], None
    for r in rows:
        first = (r[0] if r else u"").lstrip()
        if first.startswith(u"#") or (len(r) == 1 and first == u""):
            continue
        if head is None:
            head = [h.strip().lower() for h in r]
            continue
        out.append(dict((h, (r[k] if k < len(r) else u"").strip()) for k, h in enumerate(head)))
    return out


def spoken_key(x):
    """A team name as speech recognition hears it: no accents, no punctuation, no spaces, lower case.
    'Trodai' and 'Troda\u00ed' match, and so do 'Electro Nexus' and 'ElectroNexus'."""
    t = unicodedata.normalize("NFKD", _u(x))
    t = u"".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(u"[^a-z0-9]", u"", t)


def concept_word(x):
    """A team name as a word list for the dialog's ~teamnames concept: plain letters and spaces only."""
    t = unicodedata.normalize("NFKD", _u(x))
    t = u"".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(u"\\s+", u" ", re.sub(u"[^a-z0-9']", u" ", t)).strip()


def norm_cat(c):
    c = _u(c).lower()
    if u"arm" in c:
        return "arm"
    if u"arena" in c:
        return "arena"
    return "stage"


def teams_from_rows(rows):
    out = []
    for i, r in enumerate(rows):
        name = clean_text(r.get(u"name", u""), 60)
        if name:
            out.append({"id": "f%d" % i, "name": name, "country": clean_text(r.get(u"country", u""), 40),
                        "cat": norm_cat(r.get(u"category", u"")), "say": clean_text(r.get(u"say_as", u""), 60)})
    return out


TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def sched_item(r, i):
    day = _u(r.get(u"day", u"")).strip().lower()
    day = "sat" if day.startswith(u"sat") else ("sun" if day.startswith(u"sun") else "")
    m = TIME_RE.match(_u(r.get(u"time", u"")).strip())
    title = clean_text(r.get(u"title", u""), 60)
    if not day or not m or not title or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        return None
    try:
        mins = int(_u(r.get(u"minutes", u"15")).strip() or 15)
    except ValueError:
        mins = 15
    return {"id": "f%d" % i, "day": day, "time": "%02d:%s" % (int(m.group(1)), m.group(2)), "mins": max(1, min(240, mins)),
            "title": title, "cat": norm_cat(r.get(u"category", u"")), "game": clean_text(r.get(u"game", u""), 20).lower(),
            "a": clean_text(r.get(u"side_a", u""), 60), "b": clean_text(r.get(u"side_b", u""), 60),
            "done": _u(r.get(u"done", u"")).strip().lower() in (u"y", u"yes", u"1", u"true", u"done")}


def schedule_from_rows(rows):
    out = []
    for i, r in enumerate(rows):
        it = sched_item(r, i)
        if it:
            out.append(it)
    return out


def start_epoch(it):
    h, m = it["time"].split(":")
    return EVENT_DAY_UTC[it["day"]] + int(h) * 3600 + int(m) * 60 - MALTA_UTC_OFFSET_S


def malta_hhmm(t):
    g = time.gmtime(t + MALTA_UTC_OFFSET_S)
    return "%02d:%02d" % (g.tm_hour, g.tm_min)


class MyClass(GeneratedClass):

    def __init__(self):
        GeneratedClass.__init__(self)
        self.clock = time.time
        self.sleep = time.sleep
        self.clockOffset = 0.0        # staff can correct Pepper's clock (System tab); kept in state.json

    def onLoad(self):
        self.px = {}
        self.running = False
        self.worker = None
        self.sender = None
        self.lock = threading.Lock()
        self.seenLock = threading.Lock()
        self.jsq = []
        self.content = None
        self.teams, self.schedule, self.scores, self.alerts = [], [], [], []
        self.calls = True
        self.edited = {"teams": False, "schedule": False}
        self.announced = {}
        self.seq = 0
        self.lastSig = None
        self.lastPush = 0.0
        self.seen = []
        self.token = None
        self.staff = {}
        self.pinFails = []
        self.sayJob = None
        self.speaking = False
        self.lastSpeak = 0.0
        self.lastNu = 0.0
        self.jsLink = None
        self.viewSaid = {}
        self.introAtStart = False
        self.quizAt = 0.0
        self.lastGreet = 0.0
        self.lastHuman = -1
        self.quizOn = None
        self.intro = None             # v1.1: Pepper's intro show: {"i": scene, "t0": started}
        self.introAuto = True
        self.lastActivity = 0.0
        self.listen = None
        self.dlgTry = 0
        self.dlgAt = 0.0
        self.dlgSub = False
        self.topic = None
        self.startAt = None
        self.tuned = None
        self.appRoot = None
        self.lastCallCheck = 0.0
        self.lastSpeakCheck = 0.0

    def onUnload(self):
        self._halt()

    def onInput_onStart(self):
        if self.running:
            return
        self.running = True
        self.token = "%08x" % random.randint(0, 0x7fffffff)
        self._write(TOKEN_KEY, self.token)
        for k in KEYS[:-1]:
            self._write(k, "")
        self.startAt = self.clock()
        self.appRoot = self._appRoot()
        self.content = self._loadContent()
        if getattr(self, "_baseClock", None) is None:
            self._baseClock = self.clock
            self.clock = lambda: self._baseClock() + self.clockOffset
        self._loadData()
        self.startAt = self.clock()
        self.calls = self.calls and bool(self._param("Match calls", True))
        self.introAuto = self.introAuto and self._introEvery() > 0
        self.introAtStart = bool(self._param("Intro at start", True))
        self.viewSaid = {}
        self.lastActivity = self.clock()
        self._log("info", "[Host] v%s running. %d teams, %d programme items, content %s" % (
            VERSION, len(self.teams), len(self.schedule), "loaded" if self.content else "MISSING"))
        self._dialogOpen()
        self._setConcepts()
        self._tune()
        self._connectTablet()
        self.sender = threading.Thread(target=self._sendLoop)
        self.sender.daemon = True
        self.sender.start()
        self._push(True)
        self.worker = threading.Thread(target=self._loop)
        self.worker.daemon = True
        self.worker.start()

    def onInput_onStop(self):
        self._halt()
        self.onStopped()

    def _halt(self):
        if not getattr(self, "running", False):
            return
        self.running = False
        self.intro = None
        self.quizOn = None
        self._stopTalk()
        self._untune()
        self._dialogClose()
        self._disconnectTablet()

    def _disconnectTablet(self):
        """Without this, a stopped copy stays connected to the tablet and keeps answering every touch."""
        link, self.jsLink = getattr(self, "jsLink", None), None
        if not link:
            return
        try:
            link[0].onJSEvent.disconnect(link[1])
        except Exception as e:
            self._log("warning", "[Host] tablet link not removed (%s)" % e)

    def _owner(self):
        """True while this copy is the one running: stopped copies, and copies replaced by a newer start, stay silent."""
        if not getattr(self, "running", False):
            return False
        owner = self._read(TOKEN_KEY)
        return not (self.token and owner and owner != self.token)

    # ------------------------------------------------------------------ NAOqi access
    def _p(self, name):
        if name in self.px and self.px[name] is not None:
            return self.px[name]
        try:
            self.px[name] = self.session().service(name)
        except Exception:
            self.px[name] = None
        return self.px[name]

    def _call(self, name, method, *args):
        p = self._p(name)
        if p is None:
            return None
        try:
            return getattr(p, method)(*args)
        except Exception as e:
            self._log("warning", "[Host] %s.%s failed (%s)" % (name, method, e))
            return None

    def _read(self, key):
        m = self._p("ALMemory")
        if m is None:
            return ""
        try:
            v = m.getData(key)
            return "" if v is None else v
        except Exception:
            return ""

    def _write(self, key, value):
        m = self._p("ALMemory")
        if m is not None:
            try:
                m.insertData(key, _s(value))
            except Exception:
                pass

    def _log(self, level, msg):
        try:
            getattr(self.logger, level)(_s(msg))
        except Exception:
            pass

    def _param(self, name, default):
        try:
            v = self.getParameter(name)
            return default if v is None else v
        except Exception:
            return default

    # ------------------------------------------------------------------ files
    def _appRoot(self):
        try:
            fm = self._p("ALFrameManager")
            base = fm.getBehaviorPath(self.behaviorId) if fm is not None else None
            if base:
                return os.path.normpath(os.path.join(_u(base), u"..")).replace(u"\\", u"/")
        except Exception:
            pass
        return None

    def _file(self, rel):
        if not self.appRoot:
            return None
        p = os.path.join(self.appRoot, rel)
        try:
            with io.open(p, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            self._log("warning", "[Host] cannot read %s (%s)" % (rel, e))
            return None

    def _loadContent(self):
        t = self._file(u"html/data/content.json")
        if not t:
            return None
        try:
            return json.loads(t)
        except Exception as e:
            self._log("error", "[Host] content.json is not valid JSON (%s)" % e)
            return None

    def _storePath(self):
        return os.path.join(STORE_DIR, "state.json")

    def _loadData(self):
        st = {}
        try:
            with io.open(self._storePath(), "r", encoding="utf-8") as f:
                st = json.loads(f.read())
        except Exception:
            st = {}
        self.edited = st.get("edited") or {"teams": False, "schedule": False}
        if self.edited.get("teams") and isinstance(st.get("teams"), list):
            self.teams = st["teams"]
        else:
            self.teams = teams_from_rows(parse_csv(self._file(u"html/data/teams.csv") or u""))
        if self.edited.get("schedule") and isinstance(st.get("schedule"), list):
            self.schedule = st["schedule"]
        else:
            self.schedule = schedule_from_rows(parse_csv(self._file(u"html/data/schedule.csv") or u""))
        self.scores = st.get("scores") if isinstance(st.get("scores"), list) else []
        self.alerts = (st.get("alerts") if isinstance(st.get("alerts"), list) else [])[-50:]
        self.calls = bool(st.get("calls", True))
        self.introAuto = bool(st.get("introAuto", True))
        try:
            self.clockOffset = float(st.get("clockOffset", 0.0))
        except Exception:
            self.clockOffset = 0.0
        self.announced = st.get("announced") if isinstance(st.get("announced"), dict) else {}

    def _save(self):
        data = {"teams": self.teams, "schedule": self.schedule, "scores": self.scores, "alerts": self.alerts[-50:],
                "calls": self.calls, "introAuto": self.introAuto, "edited": self.edited, "announced": self.announced, "saved": self.clock(),
                "clockOffset": self.clockOffset}
        try:
            if not os.path.isdir(STORE_DIR):
                os.makedirs(STORE_DIR)
            tmp = self._storePath() + ".tmp"
            with io.open(tmp, "w", encoding="utf-8") as f:
                f.write(_u(json.dumps(data, ensure_ascii=True)))
            os.rename(tmp, self._storePath()) if not os.path.exists(self._storePath()) else self._replace(tmp)
        except Exception as e:
            self._log("warning", "[Host] could not save staff changes (%s)" % e)

    def _replace(self, tmp):
        try:
            os.replace(tmp, self._storePath())
        except AttributeError:      # Python 2.7 has no os.replace
            os.remove(self._storePath())
            os.rename(tmp, self._storePath())

    # ------------------------------------------------------------------ main loop
    def _loop(self):
        while self.running:
            try:
                self.tick()
            except Exception as e:
                self._log("error", "[Host] tick error (%s)" % e)
            self.sleep(0.1)

    def tick(self):
        vals = self._readKeys()
        owner = vals.get(TOKEN_KEY, "")
        if self.token and owner and owner != self.token:
            self._log("warning", "[Host] a newer Host Controller started: this one stops")
            self._halt()
            return
        cmd = vals.get("hostCmd", "")
        if cmd:
            self._write("hostCmd", "")
            self.lastActivity = self.clock()
            if self.listen is False:
                self.listen = True
            self._onDialog(_u(cmd).strip().lower(), vals)
        raw = vals.get("Host/TabletCmd", "")
        if raw:
            self._write("Host/TabletCmd", "")
            self.onTablet(raw)
        now = self.clock()
        self._dialogStep(now)
        if self.introAtStart and self.startAt is not None and now - self.startAt >= INTRO_START_S:
            self.introAtStart = False             # once per start
            if self.intro is None and self.quizOn is None:
                self.startIntro("start")
        self._introStep(now)
        if now - self.lastSpeakCheck >= 0.5:
            self.lastSpeakCheck = now
            self._checkSpeaking()
        if now - self.lastCallCheck >= 5.0:
            self.lastCallCheck = now
            self._matchCalls(now)
            self._expireStaff(now)
            if self.quizOn is not None and now - self.quizAt > QUIZ_IDLE_S:
                self.quizOn = None            # a quiz left half way: Pepper greets and gives the intro again
            self._introAutoCheck(now)         # first: after a quiet spell, someone arriving gets the intro, not a greeting
            self._greetCheck(now)
        self._push(False)

    def _readKeys(self):
        m = self._p("ALMemory")
        out = {}
        if m is None:
            return out
        try:
            vals = m.getListData(KEYS)
            for k, v in zip(KEYS, vals):
                out[k] = "" if v is None else v
        except Exception:
            for k in KEYS:
                out[k] = self._read(k)
        return out

    # ------------------------------------------------------------------ speech
    # Pepper's services, reached through self.session().service(), have no post helper. A call that must not block
    # uses _async=True and returns a future. If that is refused, the call runs in a small thread instead.
    def say(self, text, interrupt=True):
        text = clean_text(text, 400)
        if not text:
            return
        if interrupt:
            self._stopTalk()
        self.sayJob = self._speakAsync(_s(text))
        self.lastSpeak = self.clock()
        self.speaking = self.sayJob is not None
        self._log("info", "[Host] says: %s" % text)

    def _speakAsync(self, text):
        a = self._p("ALAnimatedSpeech")
        tts = self._p("ALTextToSpeech")
        conf = {"bodyLanguageMode": "contextual"}
        for proxy, args in ((a, (text, conf)), (tts, (text,))):
            if proxy is None:
                continue
            try:
                return ("future", proxy.say(*args, _async=True))
            except TypeError:
                pass                      # this NAOqi does not know _async: use a thread
            except Exception as e:
                self._log("warning", "[Host] speech failed (%s)" % e)
                continue
            box = {"done": False}
            def run(proxy=proxy, args=args, box=box):
                try:
                    proxy.say(*args)
                except Exception as e:
                    self._log("warning", "[Host] speech failed (%s)" % e)
                box["done"] = True
            th = threading.Thread(target=run)
            th.daemon = True
            th.start()
            return ("thread", box)
        return None

    def _stopTalk(self):
        tts = self._p("ALTextToSpeech")
        if tts is not None:
            try:
                tts.stopAll()
            except Exception:
                pass
        job = getattr(self, "sayJob", None)
        if job is not None and job[0] == "future":
            try:
                job[1].cancel()
            except Exception:
                pass
        self.sayJob = None
        self.speaking = False

    def _checkSpeaking(self):
        job = getattr(self, "sayJob", None)
        if job is None:
            self.speaking = False
            return
        try:
            running = (not job[1].isFinished()) if job[0] == "future" else (not job[1]["done"])
        except Exception:
            running = self.clock() - self.lastSpeak < 8.0
        if not running:
            self.sayJob = None
        self.speaking = running

    def _name(self, team_name):
        """How Pepper pronounces a team: its say-as text if staff gave one."""
        for t in self.teams:
            if t["name"] == team_name and t.get("say"):
                return t["say"]
        return team_name

    # ------------------------------------------------------------------ content helpers
    def _game(self, gid):
        for g in (self.content or {}).get("games", []):
            if g.get("id") == gid:
                return g
        return None

    def _sorted(self):
        return sorted(self.schedule, key=start_epoch)

    def _nowNext(self, t):
        cur, nxt = None, None
        for it in self._sorted():
            if it.get("done"):
                continue
            s = start_epoch(it)
            if cur is None and s <= t < s + it.get("mins", 15) * 60:
                cur = it
            if nxt is None and s > t:
                nxt = it
        return cur, nxt

    def _sides(self, it):
        a, b = it.get("a") or "", it.get("b") or ""
        if it.get("cat") == "arena" and (a or b):
            return "Red corner: %s. Blue corner: %s." % (self._name(a) if a else "to be confirmed", self._name(b) if b else "to be confirmed")
        names = [self._name(x) for x in (a, b) if x]
        return ("With %s." % " and ".join(names)) if names else ""

    def _itemLine(self, it):
        where = {"arena": " in the Arena", "arm": " at the Robot Arm AI Challenge"}.get(it.get("cat"), "")
        return ("At %s: %s%s. %s" % (it["time"], it["title"], where, self._sides(it))).strip()

    # ------------------------------------------------------------------ dialog commands
    def _onDialog(self, cmd, vals):
        self._log("info", "[Host] heard command %s" % cmd)
        now = self.clock()
        if cmd == "ping":
            return
        if cmd == "hello":
            self.say(random.choice(["Hello! Welcome to the IEEE Robot Championships. Touch my screen, or ask me what is on next.",
                                    "Hi! I am Pepper, your host. Would you like to see how the robot games work?"]))
        elif cmd in ("games", "arena", "arm"):
            cat = "arm" if cmd == "arm" else "arena"
            self._go("games", cat)
            self.say(((self.content or {}).get("categories", {}).get(cat, {}) or {}).get("say", "Here are the games."))
        elif cmd == "game":
            gid = _u(vals.get("hostGame", "")).strip().lower()
            self._write("hostGame", "")
            g = self._game(gid)
            if g:
                self._go("game", gid)
                self.say(g.get("say", g.get("tagline", "")))
        elif cmd == "teams":
            self._go("teams", "")
            self.say(self._teamsLine())
        elif cmd == "team":
            heard = _u(vals.get("hostTeam", "")).strip().lower()
            self._write("hostTeam", "")
            self._teamInfo(heard)
        elif cmd in ("schedule", "next", "now"):
            self._go("schedule", "")
            self.say(self._nextLine(now))
        elif cmd == "scores":
            self._go("scores", "")
            self.say(self._scoresLine())
        elif cmd == "quiz":
            self._js("HostUI.quizStart()")
        elif cmd == "ans":
            n = _u(vals.get("hostAns", "")).strip()
            self._write("hostAns", "")
            if n in ("1", "2", "3"):
                self._js("HostUI.answer(%s)" % n)
            elif n == "next":
                self._js("HostUI.answer(0)")
        elif cmd in ("help", "volunteer"):
            self._go("help", "")
            self._volunteer()
        elif cmd == "about":
            self._go("help", "")
            self.say((self.content or {}).get("event", {}).get("about", "This is the IEEE Robot Championships."))
        elif cmd == "info":
            self._infoLine(_u(vals.get("hostInfo", "")).strip())
        elif cmd == "time":
            self.say("It is %s." % malta_hhmm(now))
        elif cmd == "who":
            self.say("I am Pepper, a humanoid robot. Today I am the host of the IEEE Robot Championships. I am not in the games myself. I just love watching them!")
        elif cmd == "thanks":
            self.say("You are welcome!")
        elif cmd == "bye":
            self.say("Goodbye! Enjoy the championships!")
            self._go("home", "")
        elif cmd == "intro":
            self.startIntro("voice")
        elif cmd == "stop":
            if self.intro is not None:
                self.stopIntro()
            else:
                self._stopTalk()
        elif cmd == "nu":
            # In a noisy hall the dialog often hears noise as speech. Only answer someone who is standing at Pepper,
            # at most once a minute, and never during the intro or the quiz (the screen shows what to do there).
            if self.intro is not None or self.quizOn is not None:
                return
            try:
                near = int(self._read("ALBasicAwareness/HumanTracked")) >= 0
            except Exception:
                near = False
            if near and now - self.lastNu >= NU_GAP_S and not self.speaking:
                self.lastNu = now
                self.say("Sorry, I did not catch that. You can also touch my screen.")

    # ------------------------------------------------------------------ one short line when a screen opens
    def _viewLine(self, view, arg):
        if view == "home":
            return "Welcome! Touch Watch Pepper's intro, or pick a game."
        if view == "games":
            if arg == "arm":
                return "This is the Robot Arm AI Challenge. Touch a round, and I will explain it."
            return "These are the four Arena games. Touch one, and I will explain it."
        if view == "teams":
            return self._teamsLine()
        if view == "schedule":
            return "Here is the programme. " + self._comingUp(self.clock())
        if view == "scores":
            return "These are the provisional scores. The judges announce the official results."
        if view == "quiz":
            return "Let's play the robot quiz! Five questions. Touch Start."
        if view == "help":
            return "If you need help, touch the red button, and a volunteer will come to you."
        return ""

    def _viewTalk(self, view, arg):
        """Every tap gets an answer: a short line for the screen, not repeated within VIEW_GAP_S for the same screen."""
        if self.intro is not None:
            return
        line = self._viewLine(view, arg)
        if not line:
            return
        key, now = view + "/" + arg, self.clock()
        if now - self.viewSaid.get(key, -1e9) < VIEW_GAP_S:
            return
        self.viewSaid[key] = now
        self.say(line)

    # ------------------------------------------------------------------ Pepper's clock
    def _setClock(self, msg):
        """Staff correct Pepper's clock: {"date": "2026-11-28", "time": "13:52"} in Malta time, or {"reset": true}.
        Every timer is moved by the same amount, so nothing fires or expires because of the correction."""
        if msg.get("reset"):
            target = None
        else:
            try:
                y, mo, d = [int(x) for x in _u(msg.get("date", "")).split("-")]
                hh, mm = [int(x) for x in _u(msg.get("time", "")).split(":")]
                target = calendar.timegm((y, mo, d, hh, mm, 0, 0, 0, 0)) - MALTA_UTC_OFFSET_S
            except Exception:
                self._log("warning", "[Host] clock not set: date or time not understood")
                return False
            if not (2026 <= y <= 2030):
                return False
        old = self.clockOffset
        new = 0.0 if target is None else float(target - self._baseClock())
        delta = new - old
        self.clockOffset = new
        for name in ("startAt", "lastActivity", "lastSpeak", "lastGreet", "lastNu", "lastCallCheck", "quizAt"):
            v = getattr(self, name, None)
            if isinstance(v, (int, float)) and v:
                setattr(self, name, v + delta)
        for tok in list(self.staff.keys()):
            self.staff[tok] += delta
        for k in list(self.viewSaid.keys()):
            self.viewSaid[k] += delta
        if self.intro is not None and isinstance(self.intro.get("t0"), (int, float)):
            self.intro["t0"] += delta
        self._log("info", "[Host] clock corrected by %d minutes, Malta time is now %s" % (int(round(new / 60.0)), malta_hhmm(self.clock())))
        return True

    def _teamsLine(self):
        n = len(self.teams)
        if not n:
            return "The team list is coming soon. During the matches, the Arena teams play from the red corner and the blue corner."
        if n == 1:
            return "One team is on the list so far."
        na = len([t for t in self.teams if t["cat"] == "arena"])
        nm = n - na
        parts = []
        if na:
            parts.append("%d %s in the Arena" % (na, "team" if na == 1 else "teams"))
        if nm:
            parts.append("%d %s in the Robot Arm AI Challenge" % (nm, "team" if nm == 1 else "teams"))
        return "%d teams are taking part: %s." % (n, " and ".join(parts))

    def _findTeams(self, heard):
        """Every team whose name (or say-as text) sounds like what was heard. Two teams in different competitions can
        sound the same, for example 'Electro Nexus' in the Arena and 'ElectroNexus' in the Robot Arm AI Challenge."""
        k = spoken_key(heard)
        if not k:
            return []
        hits = [t for t in self.teams if k in (spoken_key(t["name"]), spoken_key(t.get("say") or ""))]
        if hits:
            return hits
        return [t for t in self.teams if len(k) >= 4 and k in spoken_key(t["name"])]

    def _teamInfo(self, heard):
        hits = self._findTeams(heard)
        if not hits:
            self._go("teams", "")
            self.say("I could not find that team. Here is the team list.")
            return
        if len(hits) > 1:
            self._go("teams", "")
            self.say("There are %d teams with that name: %s." % (len(hits), " and ".join(
                "%s in %s" % (self._name(t["name"]), "the Robot Arm AI Challenge" if t["cat"] == "arm" else "the Arena") for t in hits)))
            return
        t = hits[0]
        comp = "the Robot Arm AI Challenge" if t["cat"] == "arm" else "the Arena"
        line = "%s%s competes in %s." % (self._name(t["name"]), (" from " + t["country"]) if t.get("country") else "", comp)
        now = self.clock()
        for it in self._sorted():
            if not it.get("done") and start_epoch(it) > now and t["name"] in (it.get("a"), it.get("b")):
                line += " Their next match: %s, at %s." % (it["title"], it["time"])
                break
        self._go("teams", "")
        self.say(line)

    def _nextLine(self, now):
        cur, nxt = self._nowNext(now)
        parts = []
        if cur:
            parts.append("Now: %s." % cur["title"])
        if nxt:
            parts.append("Next. " + self._itemLine(nxt))
        if not parts:
            return "The match times will be on my screen as soon as they are ready. Please ask a volunteer for the latest times."
        return " ".join(parts)

    def _board(self, cat):
        return sorted([s for s in self.scores if s.get("cat") == cat], key=lambda s: -float(s.get("points", 0)))

    def _scoresLine(self):
        out = []
        for cat, label in (("arena", "Arena"), ("arm", "Robot Arm AI Challenge")):
            b = self._board(cat)[:3]
            if b:
                places = ["first", "second", "third"]
                out.append("%s: %s." % (label, ", ".join("%s, %s with %s points" % (places[i], self._name(s["team"]), self._num(s["points"])) for i, s in enumerate(b))))
        if not out:
            return "There are no scores yet. They will appear on my screen during the games."
        return "These are the provisional scores. " + " ".join(out) + " The judges announce the official results."

    @staticmethod
    def _num(p):
        try:
            f = float(p)
            return str(int(f)) if f == int(f) else ("%.1f" % f)
        except Exception:
            return str(p)

    def _infoLine(self, idx):
        info = (self.content or {}).get("event", {}).get("info", [])
        try:
            item = info[int(idx)]
        except Exception:
            item = None
        self._go("help", "")
        self.say(item["a"] if item else "Please ask a volunteer at the information desk.")

    # ------------------------------------------------------------------ tablet commands
    def onTablet(self, raw):
        if not self._owner():
            return
        try:
            msg = json.loads(_u(raw))
        except Exception:
            return
        if not isinstance(msg, dict):
            return
        mid = msg.get("id")
        if mid:
            # a tap arrives twice (tablet link and robot memory, on two threads): check and record in one step
            self.seenLock.acquire()
            try:
                if mid in self.seen:
                    return
                self.seen.append(mid)
                self.seen = self.seen[-60:]
            finally:
                self.seenLock.release()
        cmd = msg.get("cmd", "")
        now = self.clock()
        self.lastActivity = now
        if cmd == "game":
            g = self._game(_u(msg.get("game", "") or ""))
            if g is not None:
                self.say(g.get("say", ""))
        elif cmd == "view":
            if _u(msg.get("view", "")) != "quiz":
                self.quizOn = None            # the visitor left the quiz
            self._viewTalk(_u(msg.get("view", "")), _u(msg.get("arg", "")))
        elif cmd == "intro":
            self.startIntro("tablet")
        elif cmd == "intro-stop":
            self.stopIntro()
        elif cmd == "quizq":
            self._quizQuestion(msg)
        elif cmd == "quiza":
            self._quizAnswer(msg)
        elif cmd == "quizend":
            self._quizEnd(msg)
        elif cmd == "volunteer":
            self._volunteer()
        elif cmd == "stop":
            if self.intro is not None:
                self.stopIntro()
            else:
                self._stopTalk()
        elif cmd == "staff-login":
            self._staffLogin(_u(msg.get("pin", "")), now)
        elif cmd == "staff-logout":
            self.staff.pop(_u(msg.get("token", "")), None)
        elif cmd.startswith("team-") or cmd.startswith("sched-") or cmd.startswith("score-") or cmd in ("announce", "calls", "reload", "alert-seen", "intro-start", "intro-auto", "set-clock"):
            self._staffCmd(cmd, msg, now)

    def _quizQuestion(self, msg):
        quiz = (self.content or {}).get("quiz", [])
        try:
            q = quiz[int(msg.get("i"))]
            opts = [int(x) for x in msg.get("opts", [0, 1, 2])][:3]
        except Exception:
            return
        self.quizOn = int(msg.get("i"))
        self.quizAt = self.clock()
        self.say(q["q"])                  # v1.1: the answers are on the screen; Pepper reads only the question

    def _quizAnswer(self, msg):
        self.quizAt = self.clock()
        quiz = (self.content or {}).get("quiz", [])
        try:
            q = quiz[int(msg.get("i"))]
        except Exception:
            return
        if msg.get("ok") is True:
            self.say(random.choice(["Correct!", "Yes! Well done!", "That is right!"]))
        else:
            self.say("Not quite.")

    def _quizEnd(self, msg):
        try:
            s, n = int(msg.get("score")), int(msg.get("total"))
        except Exception:
            return
        self.quizOn = None
        tail = "Brilliant! You are a robot expert." if s >= n - 1 else ("Well done!" if s >= 2 else "Good try! Watch the games and try again.")
        self.say("You got %d out of %d. %s" % (s, n, tail))

    def _volunteer(self):
        now = self.clock()
        recent = [a for a in self.alerts if not a.get("seen") and now * 1000 - a.get("t", 0) < 120000]
        if recent:
            self.say("A volunteer is already on the way. Please wait here with me.")
            return
        self.alerts.append({"id": "a%d" % int(now * 1000), "t": int(now * 1000), "text": "A visitor at Pepper asked for a volunteer.", "seen": False})
        self.alerts = self.alerts[-50:]
        self._save()
        self._log("warning", "[Host] VOLUNTEER CALLED at Pepper")
        self.say("I have called a volunteer. Please wait here with me.")
        self._push(True)

    # ------------------------------------------------------------------ staff
    def _staffLogin(self, pin, now):
        self.pinFails = [t for t in self.pinFails if now - t < PIN_WINDOW_S]
        if len(self.pinFails) >= PIN_TRIES:
            self._js("HostUI.staff(%s)" % json.dumps({"ok": False, "wait": True}))
            return
        if pin and pin == _u(self._param("Staff PIN", "2026")).strip():
            tok = "%016x" % random.getrandbits(64)
            self.staff[tok] = now
            self._log("info", "[Host] staff mode opened")
            self._js("HostUI.staff(%s)" % json.dumps({"ok": True, "token": tok}))
        else:
            self.pinFails.append(now)
            self._js("HostUI.staff(%s)" % json.dumps({"ok": False}))

    def _expireStaff(self, now):
        for tok in list(self.staff.keys()):
            if now - self.staff[tok] > STAFF_TTL_S:
                del self.staff[tok]
                self._js("HostUI.staffClosed()")

    def _staffCmd(self, cmd, msg, now):
        tok = _u(msg.get("token", "") or "")
        if tok not in self.staff:
            self._js("HostUI.staffClosed()")
            return
        self.staff[tok] = now
        changed = True
        if cmd == "team-save":
            t = msg.get("team") or {}
            name = clean_text(t.get("name", ""), 60)
            if not name:
                return
            new = {"name": name, "country": clean_text(t.get("country", ""), 40), "cat": "arm" if t.get("cat") == "arm" else "arena",
                   "say": clean_text(t.get("say", ""), 60)}
            tid = _u(t.get("id", "") or "")
            old = [x for x in self.teams if x["id"] == tid]
            if old:
                prev = old[0]["name"]
                old[0].update(new)
                for it in self.schedule:
                    if it.get("a") == prev:
                        it["a"] = name
                    if it.get("b") == prev:
                        it["b"] = name
                for s in self.scores:
                    if s.get("teamId") == tid:
                        s["team"], s["cat"] = name, new["cat"]
                self.edited["schedule"] = True
            else:
                if any(_u(x["name"]).lower() == name.lower() and x["cat"] == new["cat"] for x in self.teams):
                    self._js("HostUI.toast(%s)" % json.dumps("This team is already on the list for that competition."))
                    return
                new["id"] = "t%d" % int(now * 1000)
                self.teams.append(new)
            self.edited["teams"] = True
            self._setConcepts()
        elif cmd == "team-del":
            tid = _u(msg.get("key", ""))
            self.teams = [x for x in self.teams if x["id"] != tid]
            self.scores = [s for s in self.scores if s.get("teamId") != tid]
            self.edited["teams"] = True
            self._setConcepts()
        elif cmd == "sched-save":
            it = msg.get("item") or {}
            row = {u"day": it.get("day", ""), u"time": it.get("time", ""), u"minutes": _u(it.get("mins", 15)), u"title": it.get("title", ""),
                   u"category": it.get("cat", ""), u"game": it.get("game", ""), u"side_a": it.get("a", ""), u"side_b": it.get("b", ""),
                   u"done": u"yes" if it.get("done") else u""}
            new = sched_item(row, 0)
            if new is None:
                self._js("HostUI.toast(%s)" % json.dumps("Check the day, the time (like 14:30) and the title."))
                return
            sid = _u(it.get("id", "") or "")
            old = [x for x in self.schedule if x["id"] == sid]
            if old:
                new["id"] = sid
                self.schedule[self.schedule.index(old[0])] = new
            else:
                new["id"] = "s%d" % int(now * 1000)
                self.schedule.append(new)
            self.edited["schedule"] = True
        elif cmd == "sched-del":
            sid = _u(msg.get("key", ""))
            self.schedule = [x for x in self.schedule if x["id"] != sid]
            self.edited["schedule"] = True
        elif cmd == "score-save":
            tid = _u(msg.get("teamId", ""))
            team = [x for x in self.teams if x["id"] == tid]
            try:
                pts = float(msg.get("points"))
            except Exception:
                return
            if not team or not (-10000 <= pts <= 100000):
                return
            pts = int(pts) if pts == int(pts) else round(pts, 1)
            ex = [s for s in self.scores if s.get("teamId") == tid]
            if ex:
                ex[0]["points"] = pts
            else:
                self.scores.append({"id": "c%d" % int(now * 1000), "teamId": tid, "team": team[0]["name"], "cat": team[0]["cat"], "points": pts})
        elif cmd == "score-del":
            sid = _u(msg.get("key", ""))
            self.scores = [s for s in self.scores if s.get("id") != sid]
        elif cmd == "alert-seen":
            aid = _u(msg.get("key", ""))
            for a in self.alerts:
                if a.get("id") == aid:
                    a["seen"] = True
        elif cmd == "calls":
            self.calls = bool(msg.get("on"))
        elif cmd == "intro-start":
            changed = False
            self.startIntro("staff")
        elif cmd == "intro-auto":
            self.introAuto = bool(msg.get("on"))
        elif cmd == "set-clock":
            if not self._setClock(msg):
                changed = False
        elif cmd == "announce":
            text = clean_text(msg.get("text", ""), 300)
            changed = False
            if text:
                self._log("info", "[Host] staff announcement")
                self.say(text)
        elif cmd == "reload":
            self.teams = teams_from_rows(parse_csv(self._file(u"html/data/teams.csv") or u""))
            self.schedule = schedule_from_rows(parse_csv(self._file(u"html/data/schedule.csv") or u""))
            self.edited = {"teams": False, "schedule": False}
            self._setConcepts()
            self._js("HostUI.toast(%s)" % json.dumps("Reloaded: %d teams, %d programme items." % (len(self.teams), len(self.schedule))))
        else:
            changed = False
        if changed:
            self._save()
            self._push(True)

    # ------------------------------------------------------------------ match calls
    def _blockStarts(self):
        """The first item of each block: matches of the same game less than 10 minutes apart are one block, so the
        teams get one call ten minutes before the block (sixteen Time of Fall matches 4 minutes apart: one call)."""
        out, prev = [], None
        for it in self._sorted():
            if it.get("done"):
                continue
            s = start_epoch(it)
            same = (prev is not None and prev.get("cat") == it.get("cat") and prev.get("title") == it.get("title")
                    and s - (start_epoch(prev) + prev.get("mins", 15) * 60) < BLOCK_GAP_S)
            if not same and (it.get("cat") != "stage" or it.get("mins", 0) >= 30):
                out.append(it)
            prev = it
        return out

    def _firstLine(self, it):
        a, b = it.get("a") or "", it.get("b") or ""
        if it.get("cat") == "arena" and a and b:
            return " First match: %s in the red corner, against %s in the blue corner." % (self._name(a), self._name(b))
        names = [self._name(x) for x in (a, b) if x]
        if not names:
            return ""
        return " First up: %s." % " and ".join(names)

    def _matchCalls(self, now):
        if not self.calls:
            return
        for it in self._blockStarts():
            s = start_epoch(it)
            key = it["id"] + "|" + it["day"] + it["time"]
            if s - CALL_BEFORE_S <= now < s - CALL_BEFORE_S + CALL_WINDOW_S and not self.announced.get(key + "|call"):
                self.announced[key + "|call"] = True
                self._save()
                if self.intro is not None:
                    self.stopIntro()
                if it.get("cat") == "stage":
                    self.say("Attention please. The %s starts in ten minutes." % it["title"])
                else:
                    first = self._firstLine(it)
                    self.say(("Attention teams. In ten minutes%s: %s.%s Please get ready." % (
                        {"arena": ", in the Arena", "arm": ", at the Robot Arm AI Challenge"}.get(it.get("cat"), ""), it["title"], first)).replace("  ", " "))
                return
        if not bool(self._param("Announce match starts", False)):
            return
        for it in self._sorted():
            if it.get("done") or it.get("cat") == "stage":
                continue
            s = start_epoch(it)
            key = it["id"] + "|" + it["day"] + it["time"]
            if s <= now < s + START_WINDOW_S and not self.announced.get(key + "|start"):
                self.announced[key + "|start"] = True
                self._save()
                if self.intro is not None:
                    self.stopIntro()
                self.say(("Starting now: %s! %s Good luck to both teams!" % (it["title"], self._sides(it))) if (it.get("a") and it.get("b"))
                         else ("Starting now: %s! %s Good luck!" % (it["title"], self._sides(it))).replace("  ", " "))
                return

    # ------------------------------------------------------------------ Pepper's intro show (v1.1)
    def _introEvery(self):
        try:
            return max(0, int(self._param("Intro when idle (minutes)", 10)))
        except Exception:
            return 0

    def _introScenes(self):
        return (self.content or {}).get("intro", [])

    def _introFill(self, text):
        arena = sorted([t for t in self.teams if t["cat"] == "arena"], key=lambda t: _u(t["name"]).lower())
        arms = sorted([t for t in self.teams if t["cat"] == "arm"], key=lambda t: _u(t["name"]).lower())
        def names(ts):
            ns = [self._name(t["name"]) for t in ts]
            return ", ".join(ns[:-1]) + " and " + ns[-1] if len(ns) > 1 else (ns[0] if ns else "")
        vals = {"n": len(self.teams), "na": len(arena), "nm": len(arms), "arena_teams": names(arena), "arm_teams": names(arms),
                "next": self._comingUp(self.clock())}
        out = _u(text)
        for k, v in vals.items():
            out = out.replace(u"{%s}" % k, _u(v))
        return out

    def _comingUp(self, now):
        open_at = EVENT_DAY_UTC["sat"] + 14 * 3600 - MALTA_UTC_OFFSET_S
        if now < open_at - 6 * 3600:
            return "The championships open on Saturday the 28th at two in the afternoon, and the Arena starts at twenty past three."
        cur, nxt = self._nowNext(now)
        if nxt is not None:
            where = {"arena": " in the Arena", "arm": " at the Robot Arm AI Challenge"}.get(nxt.get("cat"), "")
            return "Coming up next, at %s: %s%s." % (nxt["time"], nxt["title"], where)
        return "Thank you for being part of the IEEE Robot Championships 2026!"

    def _introSceneState(self):
        if self.intro is None:
            return None
        sc = self._introScenes()[self.intro["i"]]
        st = {"i": self.intro["i"], "n": len(self._introScenes()), "id": sc.get("id"), "kind": sc.get("kind", "title"),
              "clip": sc.get("clip", ""), "head": self._introFill(sc.get("head", "")), "sub": self._introFill(sc.get("sub", ""))}
        if st["kind"] == "next":
            st["sub"] = self._comingUp(self.clock())
        return st

    def startIntro(self, source):
        if not self._introScenes():
            return
        self._log("info", "[Host] intro started (%s)" % source)
        self.quizOn = None
        self.intro = {"i": 0, "t0": self.clock()}
        self._js("HostUI.go(\"intro\",\"\")")
        self._introScene()

    def _introScene(self):
        sc = self._introScenes()[self.intro["i"]]
        self.intro["t0"] = self.clock()
        self.say(self._introFill(sc.get("say", "")))
        self._push(True)

    def _introStep(self, now):
        if self.intro is None:
            return
        sc = self._introScenes()[self.intro["i"]]
        held = now - self.intro["t0"]
        least = INTRO_CLIP_S if sc.get("clip") else INTRO_MIN_S
        if held < least or (self.speaking and held < INTRO_MAX_S):
            return
        if self.intro["i"] + 1 >= len(self._introScenes()):
            self._log("info", "[Host] intro finished")
            self.intro = None
            self.lastActivity = now
            self._go("home", "")
            self._push(True)
            return
        self.intro["i"] += 1
        self._introScene()

    def stopIntro(self):
        if self.intro is None:
            return
        self.intro = None
        self._stopTalk()
        self.lastActivity = self.clock()
        self._go("home", "")
        self._push(True)

    def _introAutoCheck(self, now):
        every = self._introEvery()
        if not self.introAuto or every <= 0 or self.intro is not None or self.speaking or self.quizOn is not None:
            return
        if now - max(self.lastActivity, self.lastSpeak) < every * 60:
            return
        try:
            near = int(self._read("ALBasicAwareness/HumanTracked")) >= 0
        except Exception:
            near = False
        if near:
            self.startIntro("idle")

    # ------------------------------------------------------------------ greeting people who come close
    def _greetCheck(self, now):
        if not bool(self._param("Greet visitors", True)):
            return
        h = self._read("ALBasicAwareness/HumanTracked")
        try:
            h = int(h)
        except Exception:
            h = -1
        newly = h >= 0 and self.lastHuman < 0
        self.lastHuman = h
        if newly and not self.speaking and now - self.lastGreet >= GREET_GAP_S and now - self.lastSpeak >= 20.0 and self.quizOn is None and self.intro is None:
            self.lastGreet = now
            self.say(random.choice(["Hello! Touch my screen, or watch my intro.", "Welcome! Touch my screen to see the robot games."]))

    # ------------------------------------------------------------------ dialog check: does Pepper hear?
    def _dialogStep(self, now):
        if self.listen is not None or self.startAt is None:
            return
        if self.dlgTry == 0:
            if now - self.startAt >= 4.0:
                self._write("hostPong", "")
                self.dlgTry, self.dlgAt = 1, now
                self._call("ALDialog", "forceInput", _s("robotcmd ping"))
            return
        if _u(self._read("hostPong")) == PONG:
            self.listen = True
            self._log("info", "[Host] the dialog answers: Pepper is listening")
            return
        if now - self.dlgAt < 3.0:
            return
        if self.dlgTry >= 2:
            self.listen = False
            self._log("error", "[Host] the dialog does not answer: Pepper cannot listen. The tablet still works. Stop all behaviours and start the app once.")
            return
        self._dialogRepair()
        self._write("hostPong", "")
        self.dlgTry, self.dlgAt = 2, now
        self._call("ALDialog", "forceInput", _s("robotcmd ping"))

    def _topicNames(self, method):
        d = self._p("ALDialog")
        try:
            return [_u(x) for x in (getattr(d, method)() or [])]
        except Exception:
            return []

    @staticmethod
    def _topicKey(n):
        return re.sub(u"(_enu)?(\\.top)?$", u"", _u(n).replace(u"\\", u"/").split(u"/")[-1].lower()).lstrip(u"~")

    def _dialogOpen(self):
        """Load Host_enu.top, activate it and start listening. An old copy left loaded by an earlier run (the cause of
        'topic is already loaded') is unloaded first, so every start begins clean."""
        d = self._p("ALDialog")
        if d is None or not self.appRoot:
            self._log("warning", "[Host] no dialog engine or app folder: Pepper will not listen, the tablet still works")
            return False
        for n in self._topicNames("getAllLoadedTopics"):
            if self._topicKey(n) == DIALOG_NAME:
                for m in ("deactivateTopic", "unloadTopic"):
                    try:
                        getattr(d, m)(_s(n))
                    except Exception:
                        pass
                self._log("info", "[Host] removed an old copy of the dialog left by an earlier run")
        try:
            self.topic = _u(d.loadTopic(_s(os.path.join(self.appRoot, u"Host", u"Host_enu.top"))))
            d.activateTopic(_s(self.topic))
            d.subscribe(DIALOG_SUB)
            self.dlgSub = True
            self._log("info", "[Host] dialog loaded and listening")
            return True
        except Exception as e:
            self._log("warning", "[Host] could not start the dialog (%s)" % e)
            return False

    def _dialogClose(self):
        d = self.px.get("ALDialog")
        if d is None:
            return
        if self.dlgSub:
            self.dlgSub = False
            try:
                d.unsubscribe(DIALOG_SUB)
            except Exception:
                pass
        if self.topic:
            owner = self._read(TOKEN_KEY)
            if owner and self.token is not None and owner != self.token:
                return                       # a newer Host Controller runs and uses the topic: leave it
            for m in ("deactivateTopic", "unloadTopic"):
                try:
                    getattr(d, m)(_s(self.topic))
                except Exception:
                    pass
            self.topic = None

    def _dialogRepair(self):
        self._log("warning", "[Host] dialog did not answer. Loaded: %s. Active: %s" % (
            self._topicNames("getAllLoadedTopics"), self._topicNames("getActivatedTopics")))
        self._dialogClose()
        self._dialogOpen()
        self._setConcepts()

    def _setConcepts(self):
        words = []
        for t in self.teams:
            for s in (t["name"], t.get("say") or ""):
                w = concept_word(s)
                if w and w not in words:
                    words.append(w)
        d = self._p("ALDialog")
        if d is None:
            return
        try:
            d.setConcept(_s("teamnames"), _s("English"), [_s(w) for w in (words or ["no team yet"])])
        except Exception as e:
            self._log("warning", "[Host] team names not loaded into the dialog (%s)" % e)

    # ------------------------------------------------------------------ calm robot
    def _tune(self):
        ba = self._p("ALBasicAwareness")
        if ba is None:
            return
        try:
            self.tuned = (ba.getTrackingMode(), ba.getEngagementMode())
        except Exception:
            self.tuned = None
        try:
            ba.setTrackingMode(_s("Head"))
            ba.setEngagementMode(_s("SemiEngaged"))
        except Exception as e:
            self._log("warning", "[Host] basic awareness not tuned (%s)" % e)

    def _untune(self):
        ba = self.px.get("ALBasicAwareness")
        if ba is not None and self.tuned:
            try:
                ba.setTrackingMode(_s(self.tuned[0]))
                ba.setEngagementMode(_s(self.tuned[1]))
            except Exception:
                pass

    # ------------------------------------------------------------------ tablet
    def _connectTablet(self):
        try:
            ts = self.session().service("ALTabletService")
            self.jsLink = (ts, ts.onJSEvent.connect(self.onTablet))
        except Exception as e:
            self._log("warning", "[Host] onJSEvent not available (%s); the tablet uses ALMemory" % e)

    def _state(self):
        return {"v": VERSION, "teams": self.teams, "schedule": self.schedule, "scores": self.scores, "alerts": self.alerts[-20:],
                "calls": self.calls, "voice": self.listen, "speaking": self.speaking,
                "intro": self._introSceneState(), "introAuto": self.introAuto, "introEvery": self._introEvery(),
                "clockFix": int(round(self.clockOffset / 60.0))}

    def _push(self, force):
        st = self._state()
        sig = json.dumps(st, sort_keys=True)
        now = self.clock()
        if not force and sig == self.lastSig and now - self.lastPush < PUSH_BEAT_S:
            return
        self.lastSig, self.lastPush = sig, now
        self.seq += 1
        st["seq"] = self.seq
        st["now"] = int(now * 1000)
        body = json.dumps(st, ensure_ascii=True)
        self._write(STATE_KEY, body)
        m = self._p("ALMemory")
        if m is not None:
            try:
                m.raiseEvent(STATE_EVT, _s(body))
            except Exception:
                pass
        self._js("HostUI.update(%s)" % body, "update")

    def _go(self, view, arg):
        self._js("HostUI.go(%s,%s)" % (json.dumps(view), json.dumps(arg)))

    def _js(self, code, kind=None):
        self.lock.acquire()
        try:
            if kind == "update":
                self.jsq = [q for q in self.jsq if q[0] != "update"]
            self.jsq.append((kind, code))
            self.jsq = self.jsq[-50:]
        finally:
            self.lock.release()
        if self.sender is None:
            self._flushJs()

    def _flushJs(self):
        while True:
            self.lock.acquire()
            try:
                item = self.jsq.pop(0) if self.jsq else None
            finally:
                self.lock.release()
            if item is None:
                return
            ts = self._p("ALTabletService")
            if ts is not None:
                try:
                    ts.executeJS(_s("try{" + item[1] + "}catch(e){}"))
                except Exception:
                    pass

    def _sendLoop(self):
        while self.running:
            try:
                self._flushJs()
            except Exception as e:
                self._log("error", "[Host] tablet sender error (%s)" % e)
            self.sleep(0.05)
