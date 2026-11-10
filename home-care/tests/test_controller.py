# Runs the Care Controller v4.0 script (as stored inside behavior.xar) against a fake NAOqi, on Python 3 and on Python 2.7.
from __future__ import print_function
import json, sys, re, subprocess, os, io
PY27 = "/tmp/claude-0/-home-claude/b05a1f0c-dd7e-5d57-999d-12aa7eb13b58/scratchpad/py27/bin/python2.7"
HERE = os.path.dirname(os.path.abspath(__file__))

def load_script():
    txt = open("/home/claude/hack/pkg/behavior_1/behavior.xar").read()
    a = txt.index('<Box name="Care Controller"')
    c0 = txt.index("<![CDATA[", a) + 9
    c1 = txt.index("]]></content>", c0)
    return txt[c0:c1]

class Rec(object):
    """Fake NAOqi proxy: remembers every call; .post is itself."""
    def __init__(self, name, world):
        self._name, self._w = name, world
    @property
    def post(self): return self
    def __getattr__(self, m):
        if m.startswith("__"): raise AttributeError(m)
        def f(*a):
            self._w.calls.append((self._name, m, a))
            return None
        return f

class Mem(Rec):
    def __init__(self, w):
        Rec.__init__(self, "ALMemory", w); self.d = {}
    def getData(self, k):
        if k not in self.d: raise KeyError(k)
        return self.d[k]
    def getListData(self, ks): return [self.d.get(k) for k in ks]
    def insertData(self, k, v):
        assert isinstance(k, str), "key must be a byte string: %r" % (k,)
        if isinstance(v, str) or v is None or isinstance(v, (int, float, list)): pass
        else: raise TypeError("insertData value %r" % (v,))
        self.d[k] = v
    def raiseEvent(self, k, v): self.w_ev(k, v)
    def w_ev(self, k, v): self._w.events.append((k, v))
    def removeData(self, k): self.d.pop(k, None)

class Dlg(Rec):
    """A model of the robot's dialog engine: a topic that is loaded, active and subscribed answers "robotcmd ping" (unless it is a stale
    old copy); loading a topic that is already loaded fails the way the robot's log showed."""
    def __init__(self, w):
        Rec.__init__(self, "ALDialog", w)
        self.loaded, self.active, self.subs, self.stale, self.log = ["Activity"], ["Activity"], ["box"], False, []
        self.nolist = False
    def forceInput(self, t):
        assert isinstance(t, str), "forceInput needs a byte string, got %r" % (t,)
        if t == "robotcmd ping":
            self._w.pings.append(t)
            if "Activity" in self.loaded and "Activity" in self.active and self.subs and not self.stale:
                self._w.mem.d["dlgPong"] = "ok4"
            return
        self._w.forced.append(t)
    def getAllLoadedTopics(self):
        if self.nolist: raise RuntimeError("engine not ready")
        return list(self.loaded)
    def getActivatedTopics(self): return list(self.active)
    def loadTopic(self, path):
        self.log.append(("loadTopic", path))
        if "Activity" in self.loaded: raise RuntimeError("A topic named %s is already loaded" % path)
        self.loaded.append("Activity"); self.stale = False
        return "Activity"
    def unloadTopic(self, n):
        self.log.append(("unloadTopic", n)); self.loaded = [x for x in self.loaded if x != n]
    def activateTopic(self, n):
        self.log.append(("activateTopic", n))
        if n not in self.loaded: raise RuntimeError("no such topic")
        if n not in self.active: self.active.append(n)
    def deactivateTopic(self, n):
        self.log.append(("deactivateTopic", n)); self.active = [x for x in self.active if x != n]
    def subscribe(self, n):
        self.log.append(("subscribe", n)); self.subs.append(n)
    def unsubscribe(self, n):
        self.log.append(("unsubscribe", n)); self.subs = [x for x in self.subs if x != n]
    def setConcept(self, name, lang, words): self._w.concepts.append((name, lang, list(words)))

class FrameMgr(Rec):
    def __init__(self, w): Rec.__init__(self, "ALFrameManager", w)
    def getBehaviorPath(self, bid):
        assert bid == "fake-behavior-id"
        return "/home/nao/.local/share/PackageManager/apps/.lastUploadedChoregrapheBehavior/behavior_1"

class Tablet(Rec):
    def __init__(self, w):
        Rec.__init__(self, "ALTabletService", w)
        class S(object):
            def connect(s, cb): w.tabcb = cb
        self.onJSEvent = S()
    def executeJS(self, code): self._w.js.append(code)

class World(object):
    def __init__(self):
        self.calls, self.events, self.forced, self.js, self.concepts, self.tabcb = [], [], [], [], [], None
        self.pings = []
        self.mem = Mem(self)
        self.proxies = {"ALMemory": self.mem, "ALDialog": Dlg(self), "ALTabletService": Tablet(self), "ALFrameManager": FrameMgr(self)}
        self.outputs = []
    def proxy(self, name):
        if name not in self.proxies: self.proxies[name] = Rec(name, self)
        return self.proxies[name]

def make_box(world):
    ns = {}
    class GeneratedClass(object):
        def __init__(self, *a):
            class L(object):
                def __getattr__(s, n): return lambda m: None
            self.logger = L()
            self._params = {"Max distance (m)": 1.5, "People allowed": 2, "Hold time (s)": 3, "Cooldown (s)": 90, "Calm mode": 1, "Dashboard URL": ""}
        behaviorId = "fake-behavior-id"
        def getParameter(self, n): return self._params[n]
        def session(self):
            w = world
            class Sess(object):
                def service(s, n): return w.proxy(n)
            return Sess()
        def __getattr__(self, n):
            if n.startswith("on") and not n.startswith("onInput"):
                return lambda *a: world.outputs.append(n)
            raise AttributeError(n)
    ns["GeneratedClass"] = GeneratedClass
    ns["ALProxy"] = lambda name, *a: world.proxy(name)
    code = load_script()
    exec(compile(code, "care_controller", "exec"), ns)
    import threading
    class FakeThread(object):
        def __init__(self, target=None): self.daemon = False
        def start(self): pass
    class FT(object):
        Thread = FakeThread
        Lock = staticmethod(threading.Lock)
        Event = staticmethod(threading.Event)
    ns["threading"] = FT
    box = ns["MyClass"]()
    box.onLoad()
    t = [1000.0]
    box.clock = lambda: t[0]
    box.sleep = lambda s: None
    box.jsThread = None       # tablet calls run inline
    return box, ns, t

def start(world=None):
    w = world or World()
    box, ns, t = make_box(w)
    box.onInput_onStart()
    box.jsThread = None
    box.thread = None
    for kind, code in box.jsq: box._jsNow(code)      # what the sender thread would have sent
    box.jsq = []
    return w, box, ns, t

def start_with(name, value):
    """Like start(), but with one box parameter set before the box starts."""
    w = World()
    box, ns, t = make_box(w)
    box._params[name] = value
    box.onInput_onStart()
    box.jsThread = None
    box.thread = None
    for kind, code in box.jsq: box._jsNow(code)
    box.jsq = []
    return w, box, ns, t

def tick(box, t, dt=0.1):
    t[0] += dt
    box.tick()

fails = []
def check(c, msg):
    if not c: fails.append(msg)

def last_state(w):
    for code in reversed(w.js):
        if "PepperUI.update(" in code:
            j = code[code.index("PepperUI.update(") + 16:]
            return json.loads(j[:j.rindex(")}catch(e){}")])
    return None

def say(w, box, t, text, **kw):
    msg = {"cmd": "say", "text": text}; msg.update(kw)
    w.mem.d["Pepper/TabletCmd"] = json.dumps(msg)
    tick(box, t)

def cmd(w, box, t, c):
    t[0] += 3.0                     # more than the repeat guard
    w.mem.d["pepperCmd"] = c
    tick(box, t)

def spoken(w):
    return w.mem.d.get("quizText", "")

def qshow(w, box, t, k=None, q=None):
    """The tablet reports that it shows the current question (what panel.js does once the question is on screen)."""
    qz = box.quiz
    QTAP[0] += 1
    w.mem.d["Pepper/TabletCmd"] = json.dumps({"cmd": "quizShown", "id": "qs%d" % QTAP[0], "k": qz["k"] if k is None else k, "q": qz["i"] + 1 if q is None else q})
    tick(box, t)

QTAP = [0]
def qtap(w, box, t, n, k="auto", q="auto", ident=None):
    qz = box.quiz
    QTAP[0] += 1
    msg = {"cmd": "quizAnswer", "n": n, "id": ident or ("qt%d" % QTAP[0])}
    if k == "auto": k = qz["k"]
    if q == "auto": q = qz["i"] + 1
    if k is not None: msg["k"] = k
    if q is not None: msg["q"] = q
    w.mem.d["Pepper/TabletCmd"] = json.dumps(msg)
    tick(box, t)

def quiz_tests(w, box, ns, t):
    bank = ns["QUIZ_BANK"]
    # --- the bank itself ---------------------------------------------------------------------------------------------
    check(len(bank) >= 100, "quiz bank has only %d questions" % len(bank))
    check(len(set(r[0] for r in bank)) == len(bank), "duplicate questions in the bank")
    check(all(len(r) == 4 and len(set(r[1:])) == 3 and all(isinstance(x, str) and x.strip() for x in r) for r in bank), "bad row in the bank")
    check(all(r[0].rstrip().endswith("?") for r in bank), "a question does not end with a question mark")
    # --- one quiz: five questions, each asked through the dialog -------------------------------------------------------
    cmd(w, box, t, "stop"); w.forced[:] = []; w.mem.d["quizText"] = ""
    cmd(w, box, t, "quiz")
    check(box.mode == "quiz" and box.quiz is not None, "quiz command did not start a quiz")
    st = last_state(w)
    check(st["quiz"]["n"] == 1 and st["quiz"]["k"] == box.quiz["k"] and st["run"] == box.token, "the tablet was not given the first question: %r" % st.get("quiz"))
    check(w.forced == [] and spoken(w) == "", "Pepper started reading before the tablet showed the question: %r %r" % (w.forced, spoken(w)))
    qshow(w, box, t)
    check(w.forced[-1:] == ["robotcmd quizask"], "the dialog was not asked to read the first question: %r" % w.forced)
    txt = spoken(w)
    check(txt.startswith("Quiz time! Five questions.") and "Question one." in txt and "Option one," in txt and "Option three," in txt, "first question text: %r" % txt)
    qs = box.quiz["qs"]
    check(len(qs) == 5 and len(set(q["bank"] for q in qs)) == 5, "a quiz must have five different questions")
    for q in qs:
        r = bank[q["bank"]]
        check(sorted(q["opts"]) == sorted(r[1:]) and q["opts"][q["right"]] == r[1], "options or right answer wrong for %r" % r[0])
    st = last_state(w)
    check(st["quiz"]["phase"] == "ask" and st["quiz"]["n"] == 1 and len(st["quiz"]["opts"]) == 3 and st["mode"] == "quiz", "quiz state for the tablet: %r" % st.get("quiz"))
    check(not ({"right", "bank", "answer"} & set(st["quiz"])) and st["quiz"]["fb"] is None, "the tablet state leaks the answer")
    check(st["quiz"]["q"] == qs[0]["q"] and st["quiz"]["opts"] == qs[0]["opts"], "tablet shows another question than Pepper reads")
    check(not w.concepts or all(c[0] == "extraNames" for c in w.concepts), "the quiz must not churn dialog concepts: %r" % [c[0] for c in w.concepts])
    # an answer in the first second is a double tap and does not count
    w.mem.d["Pepper/TabletCmd"] = json.dumps({"cmd": "quizAnswer", "n": 1, "k": box.quiz["k"], "q": 1}); tick(box, t, 0.2)
    check(box.quiz["i"] == 0, "an instant answer was accepted")
    # a spoken answer while Pepper is still reading the options is its own echo or noise, not an answer
    cmd(w, box, t, "qa1"); check(box.quiz["i"] == 0, "a spoken answer during the reading was accepted")
    # answer all five: question 1 right (by tablet), 2 wrong (by voice), 3 right (voice), 4 wrong (tablet), 5 right (tablet)
    plan = [(True, "tablet"), (False, "voice"), (True, "voice"), (False, "tablet"), (True, "tablet")]
    score = 0
    for i, (good, how) in enumerate(plan):
        t[0] += 20.0                                       # Pepper has finished reading; the tablet has long shown it
        q = box.quiz["qs"][i]
        pick = q["right"] if good else (q["right"] + 1) % 3
        n = pick + 1
        w.forced[:] = []
        if how == "tablet":
            qtap(w, box, t, n, ident="a%d" % i)
        else:
            cmd(w, box, t, "qa%d" % n)
        score += 1 if good else 0
        if i < 4:
            check(w.forced == [] and box.quiz["i"] == i + 1, "Pepper must wait for the tablet before reading question %d: %r" % (i + 2, w.forced))
            st = last_state(w)
            check(st["quiz"]["n"] == i + 2 and st["quiz"]["k"] == box.quiz["k"], "the tablet was not given question %d first" % (i + 2))
            qshow(w, box, t)
            txt = spoken(w)
            check(w.forced == ["robotcmd quizask"], "next question not asked after answer %d: %r" % (i + 1, w.forced))
            check(("Question %s." % ns["QUIZ_NUM"][i + 2]) in txt, "wrong question number after answer %d: %r" % (i + 1, txt))
            if good:
                check(any(txt.startswith(x) for x in ns["QUIZ_OK"]), "no praise after a right answer: %r" % txt)
            else:
                check("The answer is " + q["opts"][q["right"]] + "." in txt, "wrong answer must say the right one: %r" % txt)
            st = last_state(w)
            check(st["quiz"]["fb"]["ok"] is good and st["quiz"]["fb"]["answer"] == q["opts"][q["right"]], "feedback for the tablet wrong")
            check(st["quiz"]["n"] == i + 2, "tablet is not on question %d" % (i + 2))
    check(w.forced == ["robotcmd quizend"], "end of quiz not announced: %r" % w.forced)
    txt = spoken(w)
    check("You got three out of five." in txt, "score not spoken: %r" % txt)
    st = last_state(w)
    check(st["quiz"]["phase"] == "done" and st["quiz"]["score"] == 3 and st["quiz"]["total"] == 5 and st["mode"] is None, "result state wrong: %r" % st["quiz"])
    check(box.current["quizzes"] == 1 and box.current["quizLast"] == "3/5", "quiz result not in the patient record")
    # answers after the end do nothing
    cmd(w, box, t, "qa1"); check(box.quiz is None or box.quiz["phase"] == "done", "late answer changed the quiz")
    # the result goes away by itself
    for _ in range(100): tick(box, t, 1.0)
    check(last_state(w)["quiz"] is None, "the result stayed on the tablet")

    # --- another quiz, then leaving it by touching another tile / by the dialog ----------------------------------------------
    cmd(w, box, t, "quiz"); first = [q["bank"] for q in box.quiz["qs"]]
    w.forced[:] = []; say(w, box, t, "music")
    check(box.quiz is None and last_state(w)["quiz"] is None and box.mode is None, "touching another tile must end the quiz")
    cmd(w, box, t, "quiz"); cmd(w, box, t, "exercise1")
    check(box.quiz is None and box.mode == "exercise", "a command for something else must end the quiz")
    cmd(w, box, t, "quiz"); check(box.mode == "quiz" and box.quiz is not None, "quiz after an exercise")
    check(len(box.quiz["qs"]) == 5, "second quiz length")
    cmd(w, box, t, "stop"); check(box.quiz is None and box.mode is None, "stop must end the quiz")
    cmd(w, box, t, "quiz"); cmd(w, box, t, "alert"); check(box.quiz is None, "an alert must end the quiz")
    cmd(w, box, t, "quiz"); w.mem.d["Pepper/TabletCmd"] = json.dumps({"cmd": "say", "text": "quiz", "id": "q-again"}); tick(box, t)
    check(w.forced[-1] == "robotcmd tilek", "the quiz tile must send tilek: %r" % w.forced[-2:])
    # repeat re-reads the same question without a lead-in
    q0 = box.quiz["qs"][0]["q"]; cmd(w, box, t, "qrepeat")
    check(spoken(w).startswith("Question one. " + q0), "repeat did not re-read the question: %r" % spoken(w))
    # nobody answers: the quiz ends by itself and the dialog is told
    w.forced[:] = []
    for _ in range(300): tick(box, t, 1.0)
    check(box.quiz is None and box.mode is None and "robotcmd quizidle" in w.forced, "an unanswered quiz must end: %r" % w.forced)
    # a tablet "close" while the result is showing
    cmd(w, box, t, "quiz")
    for i in range(5):
        t[0] += 2.0; qtap(w, box, t, 1, ident="c%d" % i)
    check(box.quiz and box.quiz["phase"] == "done", "five answers should finish the quiz")
    w.forced[:] = []; w.mem.d["Pepper/TabletCmd"] = json.dumps({"cmd": "quizClose"}); tick(box, t)
    check(box.quiz is None and w.forced == ["robotcmd quizidle"], "quizClose: %r" % w.forced)
    # a finished quiz (result still on the tablet) goes away when the dialog moves on to something that has no show to stop
    cmd(w, box, t, "quiz")
    for i in range(5):
        t[0] += 2.0; qtap(w, box, t, 2, ident="d%d" % i)
    check(box.quiz and box.quiz["phase"] == "done" and box.mode is None, "quiz should be finished here")
    cmd(w, box, t, "medunsure")
    check(box.quiz is None and last_state(w)["quiz"] is None, "a command for something else must clear a finished quiz from the tablet")
    # a medicine reminder interrupts a quiz
    cmd(w, box, t, "quiz"); box._remindIn(1); t[0] += 90
    box.reminders[-1]["due"] = t[0] - 1; tick(box, t)
    check(box.quiz is None and "robotcmd meddue" in w.forced, "a due reminder must end the quiz and be announced")
    cmd(w, box, t, "duetaken")

    # --- dealing: every question once before any repeats; shuffled between quizzes ---------------------------------------------
    box.quizDeck = []; seen = []; orders = set()
    n = len(bank)
    for k in range(n // 5):
        cmd(w, box, t, "quiz"); picks = [q["bank"] for q in box.quiz["qs"]]
        seen += picks; orders.add(tuple(picks)); cmd(w, box, t, "stop")
    check(len(set(seen)) == len(seen) == (n // 5) * 5, "a question came back before the whole bank was used")
    check(len(orders) == n // 5, "two quizzes were identical")
    for k in range(40):                               # keeps working past the end of the bank: still five different questions each time
        cmd(w, box, t, "quiz"); picks = [q["bank"] for q in box.quiz["qs"]]
        check(len(set(picks)) == 5, "quiz %d has a repeated question: %r" % (k, picks)); cmd(w, box, t, "stop")
    # the right answer is not always option one
    pos = {0: 0, 1: 0, 2: 0}
    for k in range(60):
        cmd(w, box, t, "quiz")
        for q in box.quiz["qs"]: pos[q["right"]] += 1
        cmd(w, box, t, "stop")
    check(min(pos.values()) > 60, "right answers are not spread over the three positions: %r" % pos)
    # a bank edited by hand: bad rows are skipped, and too few good rows means no quiz (and no crash)
    good = list(bank)
    bad = [("only three items", "a", "b"), ("same", "x", "x", "y"), 5, ("", "a", "b", "c")]
    ns["QUIZ_BANK"][:] = bad + good[:7]
    box.quizDeck = []
    for k in range(10):
        cmd(w, box, t, "quiz"); check(box.quiz is not None and all(q["bank"] >= 4 for q in box.quiz["qs"]), "a bad row was dealt: %r" % [q["bank"] for q in box.quiz["qs"]]); cmd(w, box, t, "stop")
    ns["QUIZ_BANK"][:] = bad + good[:3]
    w.forced[:] = []; cmd(w, box, t, "quiz")
    check(box.quiz is None and w.forced == ["robotcmd quizidle"], "a bank with fewer than five good rows must not start a quiz: %r" % w.forced)
    ns["QUIZ_BANK"][:] = good; box.quizDeck = []
    # --- v3.5: what the first on-robot test showed ---------------------------------------------------------------------------
    box.quizDeck = []
    cmd(w, box, t, "stop"); w.forced[:] = []; w.mem.d["quizText"] = ""
    cmd(w, box, t, "quiz"); qz1 = box.quiz; ks = qz1["k"]
    cmd(w, box, t, "quiz")
    check(box.quiz is qz1 and box.quiz["i"] == 0, "a repeated quiz command dealt a new quiz")
    # the tablet never answers: Pepper reads anyway after a few seconds (voice only), not never
    for _ in range(40): tick(box, t, 0.1)
    check(w.forced == ["robotcmd quizask"] and spoken(w).startswith("Quiz time!"), "Pepper never read the question when the tablet did not answer: %r" % w.forced)
    # a tablet answer about another question (an old tap, or an old quiz) is ignored and does not move the new question on
    t[0] += 20.0; w.forced[:] = []
    qtap(w, box, t, 1, q=2); check(box.quiz["i"] == 0, "a tap made on question 2 answered question 1")
    qtap(w, box, t, 1, k=ks + 50); check(box.quiz["i"] == 0, "a tap made on another quiz answered this one")
    qtap(w, box, t, 1, k=None, q=None); check(box.quiz["i"] == 1, "a tap without ids (older tablet page) must still count")
    # the tablet says it shows a question that is not the current one: Pepper does not read yet
    w.forced[:] = []
    qshow(w, box, t, q=5); qshow(w, box, t, k=ks + 50)
    check(w.forced == [], "Pepper read a question because the tablet showed another one: %r" % w.forced)
    qshow(w, box, t); check(w.forced == ["robotcmd quizask"], "the matching tablet report did not start the reading")
    qshow(w, box, t); check(w.forced == ["robotcmd quizask"], "a second report from the tablet read the question twice")
    # the same exercise and alert said twice by the dialog are done once
    cmd(w, box, t, "stop")
    cmd(w, box, t, "exercise3"); st0 = box.exStart; n0 = box.current["exercises"] if box.current else 0
    cmd(w, box, t, "exercise3")
    check(box.exStart == st0 and (not box.current or box.current["exercises"] == n0), "the same exercise restarted from the beginning")
    t[0] += 20.0; cmd(w, box, t, "exercise3")
    check(box.exStart != st0, "asking for the same exercise later must still start it")
    cmd(w, box, t, "stop")
    a0 = len(box.alerts); cmd(w, box, t, "alert"); cmd(w, box, t, "alert")
    check(len(box.alerts) == a0 + 1, "one call for help made two alerts")
    t[0] += 30.0; cmd(w, box, t, "alert"); check(len(box.alerts) == a0 + 2, "a later call for help was ignored")
    t[0] += 60.0; tick(box, t); cmd(w, box, t, "stop")

def mtap(w, box, t, c, k="auto", n="auto"):
    m = box.mem
    QTAP[0] += 1
    msg = {"cmd": c, "id": "mt%d" % QTAP[0]}
    if k == "auto": k = m["k"]
    if n == "auto": n = m["i"] + 1
    if k is not None: msg["k"] = k
    if n is not None: msg["n"] = n
    w.mem.d["Pepper/TabletCmd"] = json.dumps(msg)
    tick(box, t)

def mem_tests(w, box, ns, t):
    cards = ns["MEM_CARDS"]
    # --- the cards themselves -------------------------------------------------------------------------------------------
    check(len(cards) == 10 and len(set(c[0] for c in cards)) == 10 and len(set(c[1] for c in cards)) == 10, "ten different cards expected")
    check(all(len(c) == 5 and all(isinstance(x, str) and x.strip() for x in c[:4]) and len(c[4]) == 2 for c in cards), "bad card")
    check(all(len(o) == 3 and o[0].strip() and o[2].strip() and len(o[1]) >= 1 for c in cards for o in c[4]), "bad answer")
    flat = lambda c: [c[0], c[1], c[2], c[3]] + [x for o in c[4] for x in (o[0], o[2]) + tuple(o[1])]
    check(all(all(ord(ch) < 128 for ch in "".join(flat(c))) for c in cards), "a card is not plain ASCII")
    check(all(c[3].endswith("?") for c in cards), "the question must be a question")
    check("MEM_ELSE" not in ns, "the third answer 'Something else' is back")
    check(all(len(c[4]) == 2 for c in cards), "every card has exactly two answers")
    # Pepper reads only the question, so the question must name both answers (one of each answer's voice words)
    for c in cards:
        ql = c[3].lower()
        check(all(any(w_ in ql for w_ in o[1]) for o in c[4]), "card %s: the question does not name both answers: %r" % (c[0], c[3]))
    # the voice words must be different on every card and slot (a word heard must mean one answer), and never a command word
    allw = [w_ for c in cards for o in c[4] for w_ in o[1]] 
    check(len(allw) == len(set(allw)), "an answer word is used twice: %r" % sorted(set(x for x in allw if allw.count(x) > 1)))
    check(not (set(allw) & set("next skip back previous repeat again pardon stop enough halt thanks thank done finished yes no one two three first second third".split())), "an answer word is a command word")
    # Pepper's own words must not contain a word the dialog listens for in this view (its voice could trigger it)
    bad = set("next skip back previous repeat again pardon stop enough halt thanks thank done finished yes one two three first second third".split())
    for c in cards:
        words = set(re.findall(r"[a-z]+", " ".join([c[1], c[2], c[3]] + [o[2] for o in c[4]]).lower()))
        check(not (words & bad), "card %s says a voice command word: %r" % (c[0], sorted(words & bad)))
    check(not (set(re.findall(r"[a-z]+", (ns["MEM_OPEN"] + ns["MEM_FIRST_TAIL"] + ns["MEM_END_TEXT"]).lower())) & bad), "the opening or closing words contain a command word")
    check("memory test" not in " ".join(c[3] for c in cards).lower() and not any(c[3].lower().startswith(("do you remember", "can you remember")) for c in cards), "a prompt tests the memory")
    # --- start: the tablet first, Pepper reads only when the card is on screen -------------------------------------------------
    cmd(w, box, t, "stop"); w.forced[:] = []; w.mem.d["memText"] = ""
    rec = box.current; rec["memCards"] = 0; rec["memLikes"] = []
    cmd(w, box, t, "relive")
    check(box.mode == "memories" and box.mem is not None, "relive did not start")
    st = last_state(w)
    mv = st["mem"]
    check(mv["phase"] == "show" and mv["n"] == 1 and mv["total"] == 10 and mv["k"] == box.mem["k"] and mv["id"] and mv["title"] and mv["line"] and mv["q"] and len(mv["opts"]) == 2 and mv["ans"] == -1 and mv["reply"] == "" and mv["liked"] is False, "state for the tablet: %r" % mv)
    check(not any(k in mv for k in ("q1", "q2", "tip")), "old fields are still sent")
    check(w.forced == [] and w.mem.d.get("memText", "") == "", "Pepper started reading before the tablet showed the card: %r" % w.forced)
    check(sorted(box.mem["order"]) == list(range(10)), "the session does not contain each card once")
    check(box.current["memCards"] == 1, "viewed cards not counted")
    mshow(w, box, t)
    check(w.forced == ["robotcmd memcard"], "the dialog was not asked to read the card: %r" % w.forced)
    card = cards[box.mem["order"][0]]
    txt = w.mem.d["memText"]
    check(txt == "Let's remember Malta together. %s. %s %s Take your time." % (card[1], card[2], card[3]), "spoken text: %r" % txt)
    # a spoken command during the reading, and a tap in the first moments, do nothing
    cmd(w, box, t, "mnext"); check(box.mem["i"] == 0, "a spoken next during the reading counted")
    box.mem["asked"] = t[0]; mtap(w, box, t, "memNext"); check(box.mem["i"] == 0, "an instant tap counted")
    t[0] += 20.0
    # stale taps (another card, another session) do nothing
    mtap(w, box, t, "memNext", n=2); check(box.mem["i"] == 0, "a tap made on card 2 moved card 1")
    mtap(w, box, t, "memNext", k=box.mem["k"] + 40); check(box.mem["i"] == 0, "a tap from another session moved the card")
    # next: the tablet gets the next card first
    w.forced[:] = []
    mtap(w, box, t, "memNext")
    check(box.mem["i"] == 1 and w.forced == [], "next: Pepper must wait for the tablet: i=%s %r" % (box.mem["i"], w.forced))
    check(last_state(w)["mem"]["n"] == 2 and box.current["memCards"] == 2, "the tablet was not given card 2")
    mtap(w, box, t, "memNext", n=1)
    check(box.mem["i"] == 1, "a second tap on the old card moved on again")
    mshow(w, box, t, n=7); mshow(w, box, t, k=box.mem["k"] + 9)
    check(w.forced == [], "Pepper read a card because the tablet showed another one")
    mshow(w, box, t)
    card2 = cards[box.mem["order"][1]]
    check(w.forced == ["robotcmd memcard"] and w.mem.d["memText"] == "%s. %s %s" % (card2[1], card2[2], card2[3]), "card 2 text: %r" % w.mem.d["memText"])
    mshow(w, box, t); check(w.forced == ["robotcmd memcard"], "a second report read the card twice")
    # I like this: kept for the carer, once
    mtap(w, box, t, "memLike", n=5); check(box.current["memLikes"] == [], "a like for another card was counted")
    mtap(w, box, t, "memLike"); mtap(w, box, t, "memLike")
    check(box.current["memLikes"] == [card2[1]] and last_state(w)["mem"]["liked"] is True, "like not kept: %r" % box.current["memLikes"])
    # voice: back, repeat, next work after the reading
    t[0] += 20.0; cmd(w, box, t, "mback"); check(box.mem["i"] == 0, "spoken back did not work")
    cmd(w, box, t, "mback"); check(box.mem["i"] == 0, "back on the first card must do nothing")
    w.forced[:] = []; cmd(w, box, t, "mrepeat")
    check(w.forced == ["robotcmd memcard"] and w.mem.d["memText"] == "%s. %s %s" % (card[1], card[2], card[3]), "repeat: %r" % w.mem.d["memText"])
    t[0] += 20.0; cmd(w, box, t, "mnext"); check(box.mem["i"] == 1, "spoken next did not work")
    # no tablet answer: Pepper reads anyway after a few seconds
    w.forced[:] = []
    for _ in range(40): tick(box, t, 0.1)
    check(w.forced == ["robotcmd memcard"], "Pepper never read the card when the tablet did not answer: %r" % w.forced)
    # a duplicate start does not restart; an old tablet page (no ids) still works
    cmd(w, box, t, "relive")
    # --- through all ten cards to the end ------------------------------------------------------------------------------------------
    cmd(w, box, t, "stop"); w.forced[:] = []
    cmd(w, box, t, "relive"); first = box.mem
    cmd(w, box, t, "relive"); check(box.mem is first, "a repeated relive command started a new session")
    for i in range(10):
        mshow(w, box, t); t[0] += 20.0
        check(box.mem["phase"] == "show" and box.mem["i"] == i, "card %d expected, on %r" % (i, box.mem["i"]))
        w.forced[:] = []
        mtap(w, box, t, "memNext", k=None, n=None) if i % 2 else mtap(w, box, t, "memNext")
    check(box.mem["phase"] == "end" and w.forced == ["robotcmd memend"] and w.mem.d["memText"] == ns["MEM_END_TEXT"], "end: %r %r" % (box.mem and box.mem["phase"], w.forced))
    check(last_state(w)["mem"] == {"k": box.mem["k"], "phase": "end", "total": 10}, "end state: %r" % last_state(w)["mem"])
    check(box.current["memCards"] == 10 or box.current["memCards"] >= 10, "cards seen")
    mtap(w, box, t, "memNext", n=None); check(box.mem["phase"] == "end", "a tap at the end changed the phase")
    w.forced[:] = []; w.mem.d["Pepper/TabletCmd"] = json.dumps({"cmd": "memClose"}); tick(box, t)
    check(box.mem is None and box.mode is None and w.forced == ["robotcmd memidle"] and last_state(w)["mem"] is None, "memClose: %r" % w.forced)
    # the closing card goes away by itself
    cmd(w, box, t, "relive"); box.mem["phase"] = "end"; box.mem["doneAt"] = t[0]
    for _ in range(100): tick(box, t, 1.0)
    check(box.mem is None and last_state(w)["mem"] is None, "the closing card stayed")
    # --- shuffled order; likes capped ----------------------------------------------------------------------------------------------
    orders = set()
    for k in range(12):
        cmd(w, box, t, "stop"); cmd(w, box, t, "relive"); orders.add(tuple(box.mem["order"]))
    check(len(orders) > 6, "the order is not shuffled: %d different orders in 12 sessions" % len(orders))
    cmd(w, box, t, "stop"); box.current["memLikes"] = []
    cmd(w, box, t, "relive")
    for i in range(10):
        t[0] += 20.0; mshow(w, box, t); mtap(w, box, t, "memLike"); mtap(w, box, t, "memNext")
    check(len(box.current["memLikes"]) == 6 and len(set(box.current["memLikes"])) == 6, "likes not capped at six: %r" % box.current["memLikes"])
    # --- silent idle: no speech, back to the tiles ---------------------------------------------------------------------------------
    cmd(w, box, t, "stop"); cmd(w, box, t, "relive"); mshow(w, box, t); w.forced[:] = []
    for _ in range(700): tick(box, t, 1.0)
    check(box.mem is None and box.mode is None and w.forced == [] and last_state(w)["mem"] is None, "idle must end quietly: %r" % w.forced)
    # --- anything else ends it -----------------------------------------------------------------------------------------------------
    for other in ("stop", "quiz", "alert", "exercise1", "song1", "dance", "breathe", "medunsure"):
        cmd(w, box, t, "relive"); check(box.mem is not None, "start before %s" % other)
        t[0] += 20.0; cmd(w, box, t, other)
        check(box.mem is None and last_state(w)["mem"] is None, "%s did not end Relive Malta" % other)
        cmd(w, box, t, "stop")
    cmd(w, box, t, "relive"); say(w, box, t, "music")
    check(box.mem is None, "another tile did not end Relive Malta")
    cmd(w, box, t, "relive"); w.forced[:] = []; say(w, box, t, "relive")
    check(box.mem is not None and w.forced == ["robotcmd tilei"], "the Relive Malta tile must forward its token and keep the session: %r" % w.forced)
    cmd(w, box, t, "relive"); box._remindIn(1); t[0] += 90; box.reminders[-1]["due"] = t[0] - 1; tick(box, t)
    check(box.mem is None and "robotcmd meddue" in w.forced, "a due reminder must end Relive Malta and be announced")
    cmd(w, box, t, "duetaken"); cmd(w, box, t, "stop")

def matap(w, box, t, a, k="auto", n="auto"):
    m = box.mem
    QTAP[0] += 1
    msg = {"cmd": "memAnswer", "id": "ma%d" % QTAP[0], "a": a}
    if k == "auto": k = m["k"]
    if n == "auto": n = m["i"] + 1
    if k is not None: msg["k"] = k
    if n is not None: msg["n"] = n
    w.mem.d["Pepper/TabletCmd"] = json.dumps(msg)
    tick(box, t)

def mem_answer_tests(w, box, ns, t):
    """v3.7: one question per card, one answer, one reply."""
    cards = ns["MEM_CARDS"]
    cmd(w, box, t, "stop"); w.forced[:] = []; w.mem.d["memText"] = ""
    rec = box.current; rec["memAnswers"] = []
    cmd(w, box, t, "relive")
    cmd(w, box, t, "ma1"); check(box.mem["ans"] is None, "a spoken answer before the card was shown counted")
    mshow(w, box, t)
    card = cards[box.mem["order"][0]]
    cmd(w, box, t, "ma1"); check(box.mem["ans"] is None, "a spoken answer while Pepper reads the question counted")
    box.mem["asked"] = t[0]; matap(w, box, t, 1); check(box.mem["ans"] is None, "an instant tap answered")
    t[0] += 20.0
    matap(w, box, t, 1, n=2); matap(w, box, t, 1, k=box.mem["k"] + 40)
    check(box.mem["ans"] is None, "a tap made on another card or session answered this one")
    for bad in (0, 3, 4, -1, "x", None):
        matap(w, box, t, bad)
    check(box.mem["ans"] is None and w.forced == ["robotcmd memcard"], "an invalid answer was accepted: %r %r" % (box.mem["ans"], w.forced))
    # a tap on option 1
    w.forced[:] = []
    matap(w, box, t, 1)
    reply = card[4][0][2]
    check(box.mem["ans"] == 0 and w.forced == ["robotcmd memcard"] and w.mem.d["memText"] == reply, "answer 1: %r %r" % (box.mem["ans"], w.mem.d["memText"]))
    mv = last_state(w)["mem"]
    check(mv["ans"] == 0 and mv["reply"] == reply and mv["n"] == 1, "the tablet was not told the answer: %r" % mv)
    check(rec["memAnswers"] == ["%s: %s" % (card[1], card[4][0][0])], "the answer was not kept: %r" % rec["memAnswers"])
    # one answer only: a second tap, or a spoken one, changes nothing and says nothing
    w.forced[:] = []
    matap(w, box, t, 2); t[0] += 20.0; cmd(w, box, t, "ma2"); cmd(w, box, t, "ma1")
    check(box.mem["ans"] == 0 and w.forced == [] and w.mem.d["memText"] == reply and len(rec["memAnswers"]) == 1, "a second answer counted")
    # Pepper is quiet after the reply; a repeat says the reply again, not the question
    w.forced[:] = []; cmd(w, box, t, "mrepeat")
    check(w.forced == ["robotcmd memcard"] and w.mem.d["memText"] == reply, "repeat after the answer: %r" % w.mem.d["memText"])
    # a spoken next straight after the answer waits for the reply to be read
    w.forced[:] = []; cmd(w, box, t, "mnext"); check(box.mem["i"] == 0, "a spoken next during the reply counted")
    t[0] += 20.0
    # a tap on Next moves on at once; the next card starts without an answer
    mtap(w, box, t, "memNext")
    mv = last_state(w)["mem"]
    check(box.mem["i"] == 1 and mv["ans"] == -1 and mv["reply"] == "" and w.forced == [], "next card not clean: %r %r" % (mv, w.forced))
    matap(w, box, t, 1, n=1); check(box.mem["ans"] is None, "an old tap answered the new card")
    # card 2: the state shows two answers
    mshow(w, box, t); t[0] += 20.0
    w.forced[:] = []
    check("ma3" not in ns["MEM_CMDS"], "the third answer command is still part of the cards")
    check(last_state(w)["mem"]["opts"] == [cards[box.mem["order"][1]][4][0][0], cards[box.mem["order"][1]][4][1][0]], "state shows the two answers")
    cmd(w, box, t, "ma1")
    check(box.mem["ans"] == 0 and len(rec["memAnswers"]) == 2, "answer 1 by voice on card 2")
    # card 3 by voice, option 2
    t[0] += 20.0; cmd(w, box, t, "mnext"); mshow(w, box, t); t[0] += 20.0
    card3 = cards[box.mem["order"][2]]
    cmd(w, box, t, "ma2")
    check(box.mem["ans"] == 1 and w.mem.d["memText"] == card3[4][1][2] and rec["memAnswers"][-1] == "%s: %s" % (card3[1], card3[4][1][0]), "voice answer 2: %r" % rec["memAnswers"])
    # the record keeps the last six, once each
    for i in range(3, 10):
        t[0] += 20.0; cmd(w, box, t, "mnext"); mshow(w, box, t); t[0] += 20.0; cmd(w, box, t, "ma1")
    check(len(rec["memAnswers"]) == 6 and len(set(rec["memAnswers"])) == 6, "answers not capped at six: %r" % rec["memAnswers"])
    # at the end nothing can be answered; closing resets
    t[0] += 20.0; cmd(w, box, t, "mnext")
    check(box.mem["phase"] == "end", "end expected")
    cmd(w, box, t, "ma1"); matap(w, box, t, 1, n=None)
    check(box.mem["phase"] == "end" and w.forced[-1:] == ["robotcmd memend"], "an answer at the end changed something: %r" % w.forced)
    cmd(w, box, t, "stop")
    # another command ends the cards: no answer lingers
    cmd(w, box, t, "relive"); mshow(w, box, t); t[0] += 20.0; cmd(w, box, t, "ma1"); cmd(w, box, t, "quiz")
    check(box.mem is None and last_state(w)["mem"] is None, "a command for something else left the cards")
    cmd(w, box, t, "stop")

def mshow(w, box, t, k=None, n=None):
    """The tablet reports that it shows the current card (what panel.js does once the card is on screen)."""
    m = box.mem
    QTAP[0] += 1
    w.mem.d["Pepper/TabletCmd"] = json.dumps({"cmd": "memShown", "id": "ms%d" % QTAP[0], "k": m["k"] if k is None else k, "n": m["i"] + 1 if n is None else n})
    tick(box, t)


class Dice(object):
    """A scripted source of dice: each die value is returned in turn (the game asks randrange(6) for a die, other sizes get 0)."""
    def __init__(self, dice): self.dice = list(dice)
    def randrange(self, n):
        if n == 6 and self.dice: return self.dice.pop(0) - 1
        return 0
    def shuffle(self, x): pass

def cmdq(w, box, t, c, dt=1.6):
    t[0] += dt
    w.mem.d["pepperCmd"] = c
    tick(box, t)

def stap(w, box, t, c, k="auto", n="auto"):
    m = box.snl
    QTAP[0] += 1
    msg = {"cmd": c, "id": "st%d" % QTAP[0]}
    if k == "auto": k = m["k"]
    if n == "auto": n = m["n"]
    if k is not None: msg["k"] = k
    if n is not None: msg["n"] = n
    w.mem.d["Pepper/TabletCmd"] = json.dumps(msg)
    tick(box, t)

def settle(box, t):
    """Time for the board to stop and the dice to be thought about (a tap or a spoken command is then allowed)."""
    tick(box, t, 5.0)           # Pepper speaks (the fallback)
    tick(box, t, 17.0)          # and her words are over

def snl_tests(w, box, ns, t):
    L, S = ns["SNL_LADDERS"], ns["SNL_SNAKES"]
    # the board itself
    check(len(L) == 8 and len(S) == 8, "board: expected 8 ladders and 8 snakes")
    check(all(a < b for a, b in L.items()) and all(a > b for a, b in S.items()), "ladders must go up and snakes down")
    ends = list(L.keys()) + list(L.values()) + list(S.keys()) + list(S.values())
    starts = list(L.keys()) + list(S.keys())
    check(all(1 < x < 100 for x in ends), "board: nothing may start or end on 1 or 100")
    check(len(set(starts)) == 16 and not (set(starts) & (set(L.values()) | set(S.values()))), "board: a square is both an end and a start (chains)")
    check(len(set(ends)) == len(ends), "board: two ladders or snakes share a square")
    check(ns["SNL_EXACT"] is True, "the exact finish rule changed")
    # the tablet draws the same board that the controller plays on
    import re as _re, io as _io
    js = _io.open("/home/claude/hack/pkg/html/js/panel.js", encoding="utf-8").read()
    for nm, tab in (("SNL_LADDERS", L), ("SNL_SNAKES", S)):
        mm = _re.search(r"var %s = \{([^}]*)\};" % nm, js)
        jt = dict((int(a), int(b)) for a, b in _re.findall(r"(\d+)\s*:\s*(\d+)", mm.group(1))) if mm else {}
        check(jt == dict(tab), "%s differs between the controller and the tablet: %r vs %r" % (nm, tab, jt))
    # the controller's timings that the tablet animation must match
    check(ns["SNL_MOVE_MS"] == 900 and ns["SNL_STEP_MS"] == 140 and ns["SNL_SPECIAL_MS"] == 1100 and ns["SNL_GAP_MS"] == 450, "the animation timings changed")

    # --- starting: tablet first, then Pepper -------------------------------------------------------------------------------
    box.rnd = Dice([3, 4])
    w.forced[:] = []; w.mem.d["snlText"] = ""
    cmd(w, box, t, "snl")
    st = last_state(w)
    check(box.mode == "snl" and st["snl"] and st["snl"]["phase"] == "play" and st["snl"]["pos"] == [0, 0] and st["snl"]["n"] == 1, "game did not start: %r" % (st and st.get("snl")))
    check(w.mem.d.get("snlText") == "" and w.forced == [], "Pepper spoke before the tablet showed the board")
    k, n = st["snl"]["k"], st["snl"]["n"]
    stap(w, box, t, "snlShown", k, n)
    check(w.mem.d["snlText"] == ns["SNL_OPEN"] and w.forced == ["robotcmd snlsay"], "no opening after the tablet answered: %r %r" % (w.mem.d.get("snlText"), w.forced))
    check("roll" in ns["SNL_OPEN"].lower() and last_state(w)["snl"]["say"] == ns["SNL_OPEN"], "opening text")
    # a repeated start (the dialog saying it twice) changes nothing
    g = box.snlSerial; cmdq(w, box, t, "snl"); check(box.snlSerial == g, "a repeated start began a second game")
    # an early spoken 'roll' (Pepper still talking) is ignored
    w.forced[:] = []
    cmdq(w, box, t, "sroll"); check(box.snl["n"] == 1 and box.snl["rolls"] == 0, "'roll' counted while Pepper was still speaking")
    # a stale / wrong-round tap is ignored
    settle(box, t)
    stap(w, box, t, "snlRoll", k + 9, n); check(box.snl["rolls"] == 0, "tap from another game counted")
    stap(w, box, t, "snlRoll", k, n + 4); check(box.snl["rolls"] == 0, "tap from another round counted")

    # --- a plain round: resident 3, Pepper 4 -------------------------------------------------------------------------------
    w.forced[:] = []; w.mem.d["snlText"] = ""
    cmd(w, box, t, "sroll")
    m = box.snl; st = last_state(w)["snl"]
    check(m["pos"] == [3, 4] and st["pos"] == [3, 4] and m["n"] == 2 and m["rolls"] == 2, "round 1 positions: %r" % (m["pos"],))
    check([x["who"] for x in st["moves"]] == [0, 1] and [x["die"] for x in st["moves"]] == [3, 4] and all(x["kind"] == "" for x in st["moves"]), "moves: %r" % st["moves"])
    check(w.mem.d.get("snlText") == "" and w.forced == [], "Pepper spoke the result before the tablet showed it")
    sa = m["say"]
    check("three" in sa and "four" in sa and sa.endswith("Your go!"), "the spoken line: " + sa)
    check("%" not in sa, "an unfilled format in the spoken line: " + sa)
    stap(w, box, t, "snlShown", m["k"], m["n"] - 1)             # an acknowledgement of an older round: nothing
    check(w.mem.d.get("snlText") == "", "an old acknowledgement made Pepper speak")
    stap(w, box, t, "snlShown", m["k"], m["n"])
    check(w.mem.d.get("snlText") == "" and m["speakAt"] > 0, "Pepper must wait for the dice to settle before speaking")
    tick(box, t, 2.0)
    check(w.mem.d.get("snlText") == sa and w.forced == ["robotcmd snlsay"], "round not spoken after the dice settled: %r" % w.mem.d.get("snlText"))

    # --- no tablet answer at all: Pepper speaks anyway after the fallback --------------------------------------------------------
    box.rnd = Dice([1, 1]); settle(box, t)
    w.forced[:] = []; w.mem.d["snlText"] = ""
    cmd(w, box, t, "sroll")
    check(box.snl["n"] == 3 and w.mem.d.get("snlText") == "", "second round")
    tick(box, t, 6.0)
    check(w.mem.d.get("snlText") == box.snl["say"] and w.forced == ["robotcmd snlsay"], "no fallback speech without a tablet answer: %r" % w.forced)

    # --- spoken command only after the reading time -------------------------------------------------------------------------------
    box.rnd = Dice([1, 1]); n0 = box.snl["n"]
    cmd(w, box, t, "sroll"); check(box.snl["n"] == n0, "'roll' counted straight after Pepper spoke")
    settle(box, t)
    box.rnd = Dice([1, 1]); cmd(w, box, t, "sroll"); check(box.snl["n"] == n0 + 1, "'roll' not counted after the reading time")

    # --- double tap: one round -----------------------------------------------------------------------------------------------------
    settle(box, t); box.rnd = Dice([1, 1]); n0 = box.snl["n"]
    stap(w, box, t, "snlRoll"); stap(w, box, t, "snlRoll")
    check(box.snl["n"] == n0 + 1, "double tap played two rounds")
    stap(w, box, t, "snlRoll")
    check(box.snl["n"] == n0 + 1, "a tap during the animation played another round")

    # --- skip: Pepper alone ------------------------------------------------------------------------------------------------------------
    settle(box, t); box.rnd = Dice([2]); p0 = list(box.snl["pos"]); n0 = box.snl["n"]
    stap(w, box, t, "snlSkip")
    m = box.snl
    check(m["n"] == n0 + 1 and m["pos"][0] == p0[0] and m["pos"][1] != p0[1] and len(m["moves"]) == 1 and m["moves"][0]["who"] == 1, "skip: %r" % (m["moves"],))
    check(m["say"].startswith(ns["SNL_SKIPPED"]) and "Your go!" in m["say"], "skip line: " + m["say"])

    # --- ladder, snake, exact finish, wins -----------------------------------------------------------------------------------------------------
    def fresh():
        settle(box, t); cmd(w, box, t, "snew"); settle(box, t)
        check(box.snl["pos"] == [0, 0] and box.snl["n"] == 1, "new game did not start clean")
    g0 = box.snlSerial
    fresh(); check(box.snlSerial == g0 + 1 or box.snlSerial == g0, "")

    def put(a, b):
        box.snl["pos"] = [a, b]
    # ladder for the resident (square 2 -> 23)
    box.snl["pos"] = [0, 0]; box.rnd = Dice([2, 6]); stap(w, box, t, "snlRoll")
    mv = box.snl["moves"][0]
    check(mv["kind"] == "ladder" and mv["land"] == 2 and mv["to"] == 23 and box.snl["pos"][0] == 23 and box.snl["ladders"] == 1 and "ladder" in box.snl["say"].lower(), "ladder: %r" % mv)
    check("Up to 23." in box.snl["say"] and "%" not in box.snl["say"], "ladder line: " + box.snl["say"])
    # snake for the resident (29 -> 9): from 23 a 6 lands on 29
    settle(box, t); box.rnd = Dice([6, 3]); stap(w, box, t, "snlRoll")
    mv = box.snl["moves"][0]
    check(mv["kind"] == "snake" and mv["to"] == 9 and box.snl["pos"][0] == 9 and box.snl["snakes"] == 1 and "snake" in box.snl["say"].lower(), "snake: %r" % mv)
    check("Down to 9." in box.snl["say"], "snake line: " + box.snl["say"])
    # too many for the end: stays
    settle(box, t); put(98, 10); box.rnd = Dice([5, 1]); stap(w, box, t, "snlRoll")
    mv = box.snl["moves"][0]
    check(mv["kind"] == "bounce" and box.snl["pos"][0] == 98 and mv["to"] == 98 and "stay" in box.snl["say"], "exact finish: %r %s" % (mv, box.snl["say"]))
    check("you stay on 98." in box.snl["say"] and "I am on 11." in box.snl["say"] and "%" not in box.snl["say"], "exact finish line: " + box.snl["say"])
    # exact roll wins; Pepper does not move after it
    settle(box, t); put(98, 10); box.rnd = Dice([2, 3]); wins0 = box.current["snlWins"]; stap(w, box, t, "snlRoll")
    m = box.snl
    check(m["phase"] == "over" and m["winner"] == 0 and m["pos"] == [100, 10] and len(m["moves"]) == 1 and box.current["snlWins"] == wins0 + 1, "resident win: %r" % (m,))
    check("You win" in m["say"] and last_state(w)["snl"]["phase"] == "over", "win line: " + m["say"])
    w.forced[:] = []; stap(w, box, t, "snlShown", m["k"], m["n"]); tick(box, t, 2.0)
    check(w.forced == ["robotcmd snlend"] and w.mem.d["snlText"] == m["say"], "the win must go out through snlend: %r" % w.forced)
    # a spoken "new game" straight after Pepper's closing words (her own voice) is ignored, a later one starts a game
    g = box.snlSerial; cmdq(w, box, t, "snew"); check(box.snlSerial == g and box.snl["phase"] == "over", "a spoken 'new game' counted while Pepper was still talking")
    # nothing more to roll on the closing screen
    settle(box, t); n0 = m["n"]; stap(w, box, t, "snlRoll"); cmd(w, box, t, "sroll"); check(box.snl["n"] == n0, "rolled after the game was over")
    # the closing line can be repeated
    w.forced[:] = []; cmd(w, box, t, "srepeat"); check(w.forced == ["robotcmd snlend"], "repeat on the closing screen: %r" % w.forced)
    # Pepper wins
    settle(box, t); cmdq(w, box, t, "snew"); settle(box, t)
    check(box.snl["phase"] == "play" and box.snl["pos"] == [0, 0], "a spoken new game after the reading time")
    put(98, 10); box.rnd = Dice([2, 3]); stap(w, box, t, "snlRoll"); settle(box, t)
    check(box.snl["phase"] == "over", "setup for the tablet new game")
    stap(w, box, t, "snlNew"); settle(box, t)
    check(box.snl["phase"] == "play" and box.snl["pos"] == [0, 0], "new game from the tablet")
    wins1 = box.current["snlWins"]; put(10, 96); box.rnd = Dice([1, 4]); stap(w, box, t, "snlRoll")
    m = box.snl
    check(m["phase"] == "over" and m["winner"] == 1 and m["pos"][1] == 100 and box.current["snlWins"] == wins1 and "I got a four" in m["say"], "Pepper win: %r %s" % (m["pos"], m["say"]))
    # a ladder to the top square is not possible (nothing ends on 100), so 'to == 100' only by a roll
    # snlNew only when the game is over
    settle(box, t); stap(w, box, t, "snlNew"); settle(box, t)
    g = box.snlSerial; stap(w, box, t, "snlNew"); check(box.snlSerial == g, "snlNew started a game while one was running")

    # --- many whole games with real dice: they always end, nobody leaves the board, every move is consistent --------------------------------
    import random as _random
    cmd(w, box, t, "stop"); box.rnd = _random.Random(12345); lens = []; wins = [0, 0]
    for g_ in range(300):
        box._snlStart(force=True)
        m = box.snl; rounds = 0
        while m["phase"] == "play" and rounds < 2000:
            old = list(m["pos"])
            box._snlRound(rounds % 7 == 6)           # now and then the resident skips
            rounds += 1
            check(all(0 <= x <= 100 for x in m["pos"]), "a piece left the board: %r" % m["pos"])
            for mv in m["moves"]:
                check(1 <= mv["die"] <= 6 and (mv["kind"] != "ladder" or mv["to"] > mv["land"]) and (mv["kind"] != "snake" or mv["to"] < mv["land"]), "bad move %r" % mv)
                check(mv["to"] == m["pos"][mv["who"]] or any(x["who"] == mv["who"] and x is not mv for x in m["moves"]), "move end does not match the board %r" % mv)
            if len(m["moves"]) == 2:
                check(m["moves"][0]["who"] == 0 and m["moves"][1]["who"] == 1, "order of moves")
        check(m["phase"] == "over" and m["winner"] in (0, 1) and m["pos"][m["winner"]] == 100 and m["pos"][1 - m["winner"]] < 100, "game %d did not end properly: %r" % (g_, m["pos"]))
        wins[m["winner"]] += 1; lens.append(rounds)
        if g_ % 50 == 0: box._snlClear(); box.mode = None
    check(max(lens) < 400 and wins[0] > 60 and wins[1] > 60, "games are too long or one side almost always wins: %r %r" % (max(lens), wins))
    box.rnd = _random.Random(); box._snlClear(); box.mode = None

    # --- the games are counted --------------------------------------------------------------------------------------------------------------
    check(box.current["snlGames"] >= 3, "games not counted: %r" % box.current["snlGames"])

    # --- the dialog moving on, tiles, stop, idle -------------------------------------------------------------------------------------------
    for how in ("exercise1", "stop", "song1", "dance", "sax", "quizstart", "relive", "alert"):
        settle(box, t); cmd(w, box, t, "snew"); settle(box, t)
        if box.snl is None: cmd(w, box, t, "snl")
        check(box.snl is not None, "could not start for " + how)
        cmd(w, box, t, how)
        check(box.snl is None and last_state(w)["snl"] is None, "%s did not end the game" % how)
        cmd(w, box, t, "stop")
    settle(box, t); cmd(w, box, t, "snl"); check(box.snl is not None, "start after others")
    say(w, box, t, "exercise"); check(box.snl is None and box.mode != "snl", "a tile touch did not end the game")
    cmd(w, box, t, "stop")
    cmd(w, box, t, "snl"); say(w, box, t, "snl"); check(box.snl is not None, "tapping the Snakes and Ladders pick closed the game")
    stap(w, box, t, "snlClose", None, None)
    check(box.snl is None and "robotcmd snlidle" in w.forced, "Done button")
    # idle: back to the tiles, silently
    cmd(w, box, t, "snl"); tick(box, t, 4.0); w.forced[:] = []; w.mem.d["snlText"] = ""
    for _ in range(61): tick(box, t, 10.0)
    check(box.snl is None and box.mode is None and last_state(w)["snl"] is None, "an idle game did not end")
    check(w.forced == [] and w.mem.d.get("snlText") == "", "an idle end must be silent: %r" % w.forced)
    # the closing screen goes by itself, silently
    cmd(w, box, t, "snl"); settle(box, t); box.snl["pos"] = [98, 0]; box.rnd = Dice([2]); stap(w, box, t, "snlRoll"); w.forced[:] = []
    for _ in range(14): tick(box, t, 10.0)
    check(box.snl is None and "robotcmd snlidle" not in w.forced, "the closing screen did not end after two minutes")
    # a game never leaks into the next patient
    cmd(w, box, t, "snl"); w.mem.d["pepperName"] = "someone new"; tick(box, t)
    cmd(w, box, t, "stop")
    check(box.snl is None, "game left after stop")

def pick_tests(w, box, ns, t):
    """v3.9: Pepper asks what to play, the tablet opens that list by itself."""
    cmd(w, box, t, "stop")
    check(last_state(w)["pick"] is None, "a list is open with nothing asked")
    cmd(w, box, t, "pickact")
    pk = last_state(w)["pick"]
    check(pk and pk["which"] == "activities" and pk["k"] >= 1, "the activities list was not asked for: %r" % pk)
    cmd(w, box, t, "pickmusic")
    pk2 = last_state(w)["pick"]
    check(pk2 and pk2["which"] == "music" and pk2["k"] == pk["k"] + 1, "the music list: %r" % pk2)
    for how in ("dance", "song1", "snl", "quizstart", "relive", "stop", "pickoff", "exercise1", "alert", "help"):
        cmd(w, box, t, "pickact")
        check(last_state(w)["pick"] is not None, "list not open before " + how)
        cmd(w, box, t, how)
        check(last_state(w)["pick"] is None, "%s did not close the list" % how)
        cmd(w, box, t, "stop")
    # asking for the list while something runs stops it first
    cmd(w, box, t, "exercise2"); check(box.mode == "exercise", "setup")
    cmd(w, box, t, "pickmusic")
    check(box.mode is None and last_state(w)["pick"]["which"] == "music", "the list did not replace the running exercise")
    # a tablet tile touch (any other word) closes it; the same two words keep it
    say(w, box, t, "chat"); check(last_state(w)["pick"] is None, "a tile touch left the list open")
    cmd(w, box, t, "stop")
    # nobody chooses: it closes by itself, silently
    cmd(w, box, t, "pickact"); w.forced[:] = []
    for _ in range(20): tick(box, t, 10.0)
    check(last_state(w)["pick"] is None and w.forced == [], "an unused list did not close quietly: %r" % w.forced)
    # wiping the records closes it
    cmd(w, box, t, "pickact")
    w.mem.d["Pepper/TabletCmd"] = json.dumps({"cmd": "clearData"}); tick(box, t)
    check(last_state(w)["pick"] is None, "clearData left the list open")
    w.mem.d["pepperName"] = "quizzer"; tick(box, t)
    # said before any name (the name question): the list must still show
    wz, bz, nz, tz = start()
    cmd(wz, bz, tz, "pickmusic")
    stz = last_state(wz)
    check(stz["pick"] and stz["pick"]["which"] == "music" and stz["current"] is not None, "a list asked for before a name did not show: %r" % (stz["pick"], ))


def named(calls, proxy, method):
    return [c[2] for c in calls if c[0] == proxy and c[1] == method]

class Settings(Rec):
    """A proxy whose getters answer like a real robot (so the controller can put the settings back)."""
    VALUES = {"getEngagementMode": "SemiEngaged", "getTrackingMode": "BodyRotation", "isStimulusDetectionEnabled": True,
              "isRecognitionEnabled": True, "isMovementDetectionEnabled": True, "isFastModeEnabled": False,
              "getAutonomousAbilityEnabled": True}
    def __getattr__(self, m):
        if m.startswith("__"): raise AttributeError(m)
        def f(*a):
            self._w.calls.append((self._name, m, a))
            return self.VALUES.get(m)
        return f

def v41_dashboard_tests():
    """v4.1: the optional laptop dashboard. Off by default, never blocks the robot, sends the same state the tablet gets."""
    w, box, ns, t = start()
    du = ns["dashboard_url"]
    for raw, want in (("", ""), (None, ""), ("   ", ""), ("192.168.1.50:8100", "http://192.168.1.50:8100"), ("http://a.local:8100/", "http://a.local:8100"),
                      ("  http://10.0.0.5:8100  ", "http://10.0.0.5:8100"), ("https://x.example", "https://x.example"), ("ftp://x", None), ("http://", None),
                      ("http://a b", None), ("http://a/?x=1", None), (":8100", None), ("http://a#frag", None), ("file:///etc/passwd", None)):
        check(du(raw) == want, "dashboard_url(%r) = %r, wanted %r" % (raw, du(raw), want))
    # off by default: nothing is queued and nothing is posted
    posts = []
    box._dashPost = lambda url, data: posts.append((url, data))
    cmd(w, box, t, "exercise1"); tick(box, t, 3.0)
    check(box.dashUrl == "" and box.dashBody is None and box.dashThread is None and posts == [], "the dashboard link is not off by default: %r" % (box.dashUrl,))
    check(box._dashOnce() is True and posts == [], "a post was made with the link off")
    # a bad address leaves it off
    w2, box2, ns2, t2 = start_with("Dashboard URL", "ftp://laptop")
    check(box2.dashUrl == "" and box2.dashThread is None, "a bad address switched the link on: %r" % (box2.dashUrl,))
    # a good address starts the sender, and the newest state is what gets posted
    w3, box3, ns3, t3 = start_with("Dashboard URL", "192.168.1.50:8100")
    check(box3.dashUrl == "http://192.168.1.50:8100" and box3.dashThread is not None, "a good address did not start the sender: %r" % (box3.dashUrl,))
    sent = []
    box3._dashPost = lambda url, data: sent.append((url, data))
    check(box3._dashOnce() is True and len(sent) == 1, "first post: %r" % (sent,))
    url, data = sent[0]
    body = json.loads(data.decode("utf-8"))
    check(url == "http://192.168.1.50:8100/api/care/state", "post address: %r" % url)
    check("sentAt" in body and body["state"]["v"] == "4.1.1" and body["state"]["current"] is None and body["state"]["alerts"] == [], "first state: %r" % (body.get("state", {}).get("v"),))
    w3.mem.d["pepperName"] = "maria"; tick(box3, t3)
    cmd(w3, box3, t3, "alert"); tick(box3, t3, 1.0)
    check(box3._dashOnce() is True and len(sent) == 2, "second post")
    st = json.loads(sent[1][1].decode("utf-8"))["state"]
    check(st["current"]["name"] == "Maria" and len(st["alerts"]) == 1 and st["alerts"][0]["name"] == "Maria", "the alert did not reach the dashboard state: %r" % (st["alerts"],))
    check(all(ord(c) < 128 for c in sent[1][1].decode("utf-8")), "the post is not plain ASCII")
    # an unreachable laptop never raises, is counted once, and recovers
    def boom(url, data): raise IOError("no route to host")
    box3._dashPost = boom
    check(box3._dashOnce() is False and box3.dashDown is True and box3.dashFails == 1, "a failed post: %r %r" % (box3.dashDown, box3.dashFails))
    check(box3._dashOnce() is False and box3.dashFails == 2, "the second failed post")
    box3._dashPost = lambda url, data: sent.append((url, data))
    n = len(sent)
    check(box3._dashOnce() is True and box3.dashDown is False and box3.dashFails == 0 and len(sent) == n + 1, "the dashboard did not recover")
    # Clear all records reaches the dashboard too, and stopping releases the sender
    w3.mem.d["Pepper/TabletCmd"] = json.dumps({"cmd": "clearData"}); tick(box3, t3); tick(box3, t3, 1.0)
    box3._dashOnce(); st = json.loads(sent[-1][1].decode("utf-8"))["state"]
    check(st["current"] is None and st["alerts"] == [] and st["history"] == [], "the dashboard kept records after Clear all records: %r" % (st["current"],))
    box3.dashEvt.clear(); box3._halt()
    check(box3.dashEvt.is_set() and box3.running is False, "stop did not release the dashboard sender")

def v40_startup_tests():
    """v4.0: the first welcome never depends on the dialog's start message arriving: the controller gives it after 6 s if it did not."""
    # nothing arrives: the welcome comes once, not before 6 s
    w, box, ns, t = start(); w.forced[:] = []
    for _ in range(59): tick(box, t)
    check(w.forced == [], "the start-up welcome came before 6 s: %r" % w.forced)
    for _ in range(5): tick(box, t)
    check(w.forced == ["robotcmd welcome"], "no start message: the controller did not start the welcome: %r" % w.forced)
    for _ in range(200): tick(box, t)
    check(w.forced == ["robotcmd welcome"], "the start-up welcome was repeated: %r" % w.forced)
    # the dialog's start message arrives first: one welcome only
    w, box, ns, t = start(); w.forced[:] = []
    for _ in range(20): tick(box, t)
    cmd(w, box, t, "autostart")
    for _ in range(200): tick(box, t)
    check(w.forced == ["robotcmd welcome"], "start message then fallback: %r" % w.forced)
    # the start message comes late, after the fallback: not a second welcome
    w, box, ns, t = start(); w.forced[:] = []
    for _ in range(160): tick(box, t)                     # the fallback came at 6 s; the late message arrives at about 16 s (past the 8 s greeting guard)
    cmd(w, box, t, "autostart"); tick(box, t, 3.0)
    check(w.forced == ["robotcmd welcome"], "a late start message repeated the welcome: %r" % w.forced)
    # somebody typed a name on the tablet within 6 s: no start-up welcome
    w, box, ns, t = start(); w.forced[:] = []
    for _ in range(20): tick(box, t)
    w.mem.d["pepperName"] = "maria"
    for _ in range(100): tick(box, t)
    check("robotcmd welcome" not in w.forced and box.current is not None, "a start-up welcome over a typed name: %r" % w.forced)
    w.mem.d["Pepper/TabletCmd"] = json.dumps({"cmd": "endSession"}); tick(box, t)
    for _ in range(100): tick(box, t)
    check(box.current is None and "robotcmd welcome" not in w.forced, "the start-up welcome came later, after the person had gone: %r" % w.forced)

def v411_voice_tests():
    """v4.1.1: the controller checks that the dialog answers; it repairs a dead or stale dialog and tells the staff when it cannot."""
    PATH = "/home/nao/.local/share/PackageManager/apps/.lastUploadedChoregrapheBehavior/Activity/Activity_enu.top"
    def run(box, t, secs):
        for _ in range(int(secs * 10)): tick(box, t)
    # healthy engine: asked once at 3 s, answered, nothing touched
    w, box, ns, t = start(); d = w.proxies["ALDialog"]
    run(box, t, 2.5); check(w.pings == [] and box.voiceOk is None, "the voice check came before 3 s: %r" % w.pings)
    run(box, t, 1.0); check(len(w.pings) == 1, "no voice check at about 3 s: %r" % w.pings)
    run(box, t, 20)
    check(box.voiceOk is True and len(w.pings) == 1 and d.log == [], "healthy dialog: %r %r %r" % (box.voiceOk, w.pings, d.log))
    check(last_state(w)["voice"] is True, "the state does not say the voice is ready")
    # the check never writes anything the people see or hear: only the welcome fallback was forced
    check(w.forced == ["robotcmd welcome"], "the voice check forced something else: %r" % w.forced)
    # loaded but not active, nobody subscribed (the box failed to start): activated and started by the controller on the first repair
    w, box, ns, t = start(); d = w.proxies["ALDialog"]; d.active, d.subs = [], []
    run(box, t, 20)
    check(box.voiceOk is True and ("activateTopic", "Activity") in d.log and any(c[0] == "subscribe" for c in d.log), "inactive topic not repaired: %r %r" % (box.voiceOk, d.log))
    check(not any(c[0] in ("unloadTopic", "loadTopic") for c in d.log), "a light repair reloaded the topic: %r" % d.log)
    check(len(w.pings) == 2, "a repaired dialog should have been asked exactly twice: %r" % w.pings)
    check(w.pings != [] and not any(x.startswith("CareControllerDialog") for x in (box.onInput_onStop() or d.subs)) and d.subs == [], "the controller's own subscription was not ended at stop: %r" % d.subs)
    # loaded, active, but nobody subscribed: only the engine is started, the topic is not activated again
    w, box, ns, t = start(); d = w.proxies["ALDialog"]; d.subs = []
    run(box, t, 20)
    check(box.voiceOk is True and not any(c[0] == "activateTopic" for c in d.log) and any(c[0] == "subscribe" for c in d.log), "an active topic was activated again: %r" % d.log)
    # a pong left over from an earlier run does not count as an answer
    w, box, ns, t = start(); d = w.proxies["ALDialog"]; d.loaded, d.active, d.subs = [], [], []; w.proxies["ALFrameManager"].getBehaviorPath = lambda b: None
    w.mem.d["dlgPong"] = "ok4"; run(box, t, 40)
    check(box.voiceOk is False, "an old dlgPong counted as an answer: %r" % box.voiceOk)
    # a slow answer (2 s) is waited for: no repair
    w, box, ns, t = start(); d = w.proxies["ALDialog"]; d.stale = True
    run(box, t, 3.3); check(len(w.pings) == 1, "setup: %r" % w.pings)
    run(box, t, 2.0); w.mem.d["dlgPong"] = "ok4"; run(box, t, 5)
    check(box.voiceOk is True and d.log == [] and len(w.pings) == 1, "a slow answer was not waited for: %r %r" % (box.voiceOk, d.log))
    # timing of the checks: 3 s after the start, then 3 s of waiting and 1 s after each repair
    w, box, ns, t = start(); d = w.proxies["ALDialog"]; d.stale = True; d.nolist = False
    seen, at = 0, []
    for _ in range(200):
        tick(box, t)
        if len(w.pings) > seen: seen = len(w.pings); at.append(round(t[0] - 1000.0, 1))
    check(len(at) == 3 and 2.9 <= at[0] <= 3.3 and 6.9 <= at[1] <= 7.4 and 10.9 <= at[2] <= 11.5, "check times: %r" % at)
    # names the engine may report: with a path, a tilde or the language ending
    check([box._topicKey(x) for x in ("Activity", "~Activity", "/a/b/Activity_enu.top", "Activity_enu", "ACTIVITY")] == ["activity"] * 5 and box._topicKey("Other") != "activity", "topic names are not recognised")
    w, box, ns, t = start(); d = w.proxies["ALDialog"]; d.loaded, d.active = ["Activity_enu", "Other"], ["Activity_enu"]
    check(box._ourTopics(d.loaded) == ["Activity_enu"], "the topic list is not filtered: %r" % box._ourTopics(d.loaded))
    # a stale old copy is loaded and running but has no ping rule: reloaded from the file on the second repair
    w, box, ns, t = start(); d = w.proxies["ALDialog"]; d.stale = True
    run(box, t, 30)
    check(box.voiceOk is True, "stale topic was not replaced: %r %r" % (box.voiceOk, d.log))
    check(("unloadTopic", "Activity") in d.log and ("loadTopic", PATH) in d.log, "stale topic: wrong reload: %r" % d.log)
    check(d.log.index(("unloadTopic", "Activity")) < d.log.index(("loadTopic", PATH)), "loaded before it was unloaded: %r" % d.log)
    check(len(w.pings) == 3, "stale: asked %d times, expected 3" % len(w.pings))
    # the reloaded topic is unloaded again when the controller stops, so the next start finds the engine clean
    box.onInput_onStop()
    check("Activity" not in d.loaded and not any(x.startswith("CareControllerDialog") for x in d.subs), "the controller left its topic or subscription behind: %r %r" % (d.loaded, d.subs))
    # a topic that the controller did not load is never unloaded by it
    w, box, ns, t = start(); d = w.proxies["ALDialog"]; run(box, t, 10); box.onInput_onStop()
    check("Activity" in d.loaded and d.subs == ["box"], "a healthy dialog's topic was touched at stop: %r %r" % (d.loaded, d.subs))
    # a newer controller owns the robot: an older one that reloaded the topic leaves it for the newer one
    w, box, ns, t = start(); d = w.proxies["ALDialog"]; d.stale = True; run(box, t, 30)
    w.mem.d["Pepper/CareControllerToken"] = "newer-controller"; box.onInput_onStop()
    check("Activity" in d.loaded, "an older controller unloaded the topic that the newer one uses")
    # nothing works: three asks, then the staff are told, on the tablet and out loud, once
    w, box, ns, t = start(); d = w.proxies["ALDialog"]; d.loaded, d.active, d.subs = [], [], []; w.proxies["ALFrameManager"].getBehaviorPath = lambda b: None
    run(box, t, 40)
    check(box.voiceOk is False and len(w.pings) == 3, "dead dialog: %r %d" % (box.voiceOk, len(w.pings)))
    check(last_state(w)["voice"] is False, "the tablet is not told that the voice is not ready")
    said = [c for c in w.calls if c[0] == "ALTextToSpeech" and c[1] == "say"]
    check(len(said) == 1 and "voice is not ready" in said[0][2][0], "the spoken notice came %d times: %r" % (len(said), said))
    run(box, t, 60); said = [c for c in w.calls if c[0] == "ALTextToSpeech" and c[1] == "say"]
    check(len(said) == 1 and len(w.pings) == 3, "the dead-dialog notice repeated")
    # the dialog sends a command after all: the notice goes away
    cmd(w, box, t, "hello"); tick(box, t)
    check(box.voiceOk is True and last_state(w)["voice"] is True, "the notice stayed after the dialog spoke")
    # the engine itself cannot be asked: no crash, still ends with a verdict
    w, box, ns, t = start(); d = w.proxies["ALDialog"]; d.nolist = True; d.stale = True; run(box, t, 40)
    check(box.voiceOk in (True, False), "no verdict when the engine cannot list topics")
    # a person was already being served: the voice check never changes the session
    w, box, ns, t = start(); w.mem.d["pepperName"] = "maria"; run(box, t, 20)
    check(box.current is not None and box.current["name"] == "Maria", "the voice check disturbed a session")

def v40_session_tests():
    """v4.0: a greeting, a group phrase or a restart of the dialog never restarts the name question or an activity."""
    # a fresh robot with nobody to serve: hello starts the welcome, once
    w, box, ns, t = start()
    w.forced[:] = []; cmd(w, box, t, "hello")
    check(w.forced == ["robotcmd welcome"], "hello with nobody to serve must start the welcome: %r" % w.forced)
    cmd(w, box, t, "hello"); check(w.forced == ["robotcmd welcome"], "a second hello 3 s later (Pepper's own voice) started another welcome: %r" % w.forced)
    t[0] += 20; w.forced[:] = []; cmd(w, box, t, "hello"); check(w.forced == ["robotcmd welcome"], "hello after a pause must be welcomed again")
    w.forced[:] = []; t[0] += 20; cmd(w, box, t, "group"); check(w.forced == ["robotcmd grouphere"], "a group with nobody served: %r" % w.forced)
    # a person is being served and nothing runs: hello is answered, the name is not asked again
    w.mem.d["pepperName"] = "maria"; tick(box, t); w.forced[:] = []; t[0] += 20
    cmd(w, box, t, "hello")
    check(w.forced == ["robotcmd hellosame"] and box.current["name"] == "Maria", "hello during a session: %r" % w.forced)
    w.forced[:] = []; t[0] += 20; cmd(w, box, t, "group"); check(w.forced == [], "a group phrase during a session asked for a new name: %r" % w.forced)
    w.forced[:] = []; cmd(w, box, t, "autostart")
    check("robotcmd welcome" not in w.forced and "robotcmd askname" not in w.forced and box.current["name"] == "Maria", "a topic restart during a session welcomed again: %r" % w.forced)
    # every kind of activity: hello, group and autostart change nothing
    for what, start_cmd in (("exercise", "exercise1"), ("dance", "dance"), ("music", "song1"), ("breathing", "breathe"), ("sax", "sax")):
        t[0] += 20; cmd(w, box, t, start_cmd); mode = box.mode; w.forced[:] = []
        for c in ("hello", "group", "autostart"):
            cmd(w, box, t, c)
        check(box.mode == mode and mode is not None and box.current["name"] == "Maria", "%s: hello / group / autostart changed what runs (mode %r -> %r)" % (what, mode, box.mode))
        check(not [f for f in w.forced if f in ("robotcmd welcome", "robotcmd askname", "robotcmd grouphere", "robotcmd hellosame")], "%s: a greeting restarted the session: %r" % (what, w.forced))
        cmd(w, box, t, "stop")
    # the quiz, the cards and the game: autostart gives the dialog its listening rules back, and nothing ends
    t[0] += 20; w.forced[:] = []; cmd(w, box, t, "quiz"); tick(box, t, 3.0); tick(box, t, 3.0)
    check(box.quiz is not None and "robotcmd quizask" in w.forced, "the quiz did not start: %r" % w.forced)
    w.forced[:] = []; t[0] += 20; cmd(w, box, t, "hello"); cmd(w, box, t, "group")
    check(box.quiz is not None and w.forced == [], "hello or group ended or interrupted the quiz: %r" % w.forced)
    t[0] += 20; cmd(w, box, t, "autostart")
    check(box.quiz is not None and "robotcmd quizask" in w.forced and "robotcmd welcome" not in w.forced, "autostart in a quiz must put the dialog back on the question: %r" % w.forced)
    cmd(w, box, t, "stop")
    t[0] += 20; w.forced[:] = []; cmd(w, box, t, "relive"); tick(box, t, 3.0); tick(box, t, 3.0)
    check(box.mem is not None and "robotcmd memcard" in w.forced, "the cards did not start: %r" % w.forced)
    w.forced[:] = []; t[0] += 20; cmd(w, box, t, "autostart")
    check(box.mem is not None and "robotcmd memcard" in w.forced and "robotcmd welcome" not in w.forced, "autostart in the cards: %r" % w.forced)
    cmd(w, box, t, "stop")
    t[0] += 20; w.forced[:] = []; cmd(w, box, t, "snl"); tick(box, t, 3.0); tick(box, t, 3.0); tick(box, t, 20.0)
    check(box.snl is not None and "robotcmd snlsay" in w.forced, "the game did not start: %r" % w.forced)
    w.forced[:] = []; t[0] += 20; cmd(w, box, t, "autostart")
    check(box.snl is not None and "robotcmd snlsay" in w.forced and "robotcmd welcome" not in w.forced, "autostart in the game: %r" % w.forced)
    for c in ("hello", "group"):
        t[0] += 20; cmd(w, box, t, c)
    check(box.snl is not None, "hello or group ended the game")
    cmd(w, box, t, "stop")
    # with a person being called, a greeting does not start anything either
    w4, b4, ns4, t4 = start(); b4.calling = "Anna"; w4.forced[:] = []; cmd(w4, b4, t4, "hello"); cmd(w4, b4, t4, "group")
    check(w4.forced == [], "a greeting while a person is being called: %r" % w4.forced)

def v40_needs_tests():
    w, box, ns, t = start()
    w.mem.d["pepperName"] = "joseph"; tick(box, t)
    NEEDS = ns["NEEDS"]
    check(set(NEEDS) == {"needfall", "needpain", "needdizzy", "needbreath", "needtoilet", "needdrink", "needfood", "needcold", "needhot"}, "the list of needs changed")
    for c, (label, urgent) in sorted(NEEDS.items()):
        t[0] += 20; n0 = len(box.alerts); cmd(w, box, t, c)
        check(len(box.alerts) == n0 + 1 and box.alerts[-1]["reason"] == label and box.alerts[-1]["name"] == "Joseph", "%s: no alert with the reason %r: %r" % (c, label, box.alerts[-n0 - 1:]))
        check("PepperUI.alert" in "".join(w.js[-6:]) or last_state(w)["alertsOpen"] >= 1, "%s: the tablet was not told" % c)
    check(last_state(w)["alerts"][-1].get("reason"), "the state has no alert reason")
    check("onAlert" in w.outputs, "the eyes did not flash")
    # an urgent need stops an exercise; a small need (toilet, a drink) does not
    t[0] += 20; cmd(w, box, t, "exercise3"); check(box.mode == "exercise", "exercise did not start")
    t[0] += 20; cmd(w, box, t, "needtoilet"); check(box.mode == "exercise", "a need for the toilet stopped the exercise")
    t[0] += 20; cmd(w, box, t, "needpain"); check(box.mode is None, "pain did not stop the exercise")
    # the same need said twice is one call; two different needs close together are two
    n0 = len(box.alerts); t[0] += 20; cmd(w, box, t, "needcold"); t[0] += 2; w.mem.d["pepperCmd"] = "needcold"; tick(box, t)
    check(len(box.alerts) == n0 + 1, "the same need twice made two alerts")
    t[0] += 2; cmd_fast = "needhot"; w.mem.d["pepperCmd"] = cmd_fast; tick(box, t)
    check(len(box.alerts) == n0 + 2, "two different needs close together must both reach the carer")
    # an alert during a quiz does not end the quiz unless it is urgent
    t[0] += 20; cmd(w, box, t, "quiz"); tick(box, t, 3.0)
    t[0] += 20; cmd(w, box, t, "needdrink"); check(box.quiz is not None, "a request for a drink ended the quiz")
    t[0] += 20; cmd(w, box, t, "needfall"); check(box.quiz is None, "a fall must stop the quiz")
    # the Help tile still works and still stops everything
    t[0] += 20; cmd(w, box, t, "exercise2"); t[0] += 20; cmd(w, box, t, "alert"); check(box.mode is None and box.alerts[-1]["reason"] == "", "the Help alert changed")

def v40_help_tests():
    w, box, ns, t = start()
    w.mem.d["pepperName"] = "eva"; tick(box, t)
    def ask(expect, label):
        t[0] += 20; w.forced[:] = []; cmd(w, box, t, "helpme"); check(w.forced == ["robotcmd " + expect], "help %s: %r" % (label, w.forced))
    ask("hintidle", "when idle")
    t[0] += 20; cmd(w, box, t, "exercise1"); ask("hintex", "in an exercise"); cmd(w, box, t, "stop")
    t[0] += 20; cmd(w, box, t, "breathe"); ask("hintbreath", "in breathing"); cmd(w, box, t, "stop")
    t[0] += 20; cmd(w, box, t, "song1"); ask("hintmusic", "in a song"); cmd(w, box, t, "stop")
    t[0] += 20; cmd(w, box, t, "quiz"); tick(box, t, 3.0); ask("hintquiz", "in the quiz"); check(box.quiz is not None, "help ended the quiz"); cmd(w, box, t, "stop")
    t[0] += 20; cmd(w, box, t, "relive"); tick(box, t, 3.0); ask("hintmem", "in the cards"); check(box.mem is not None, "help ended the cards"); cmd(w, box, t, "stop")
    t[0] += 20; cmd(w, box, t, "snl"); tick(box, t, 3.0); ask("hintsnl", "in the game"); check(box.snl is not None, "help ended the game"); cmd(w, box, t, "stop")

def v40_talk_tests():
    w, box, ns, t = start()
    w.mem.d["pepperName"] = "rita"; tick(box, t)
    J, F = ns["JOKES"], ns["FACTS"]
    for kind, bank, nm in (("joke", J, "joke"), ("fact", F, "fact")):
        told = []
        for _ in range(len(bank)):
            t[0] += 20; w.forced[:] = []; cmd(w, box, t, kind)
            check(w.forced == ["robotcmd saytext"], "%s: %r" % (kind, w.forced))
            told.append(w.mem.d.get("sayText"))
        check(sorted(told) == sorted(bank), "%ss repeat before all were told: %r" % (nm, told))
        t[0] += 20; cmd(w, box, t, kind); check(w.mem.d.get("sayText") in bank, "the next round of %ss" % nm)
    # nothing is told over an activity
    t[0] += 20; cmd(w, box, t, "exercise1"); w.forced[:] = []; t[0] += 20; cmd(w, box, t, "joke")
    check(w.forced == ["robotcmd later"] and box.mode == "exercise", "a joke over an exercise: %r" % w.forced)
    cmd(w, box, t, "stop")
    # the time and the day
    import time as _t
    box.clock = lambda: _t.mktime((2026, 11, 1, 10, 15, 0, 6, 305, -1))
    box.clockKey = ""; box._writeClock()
    check(w.mem.d.get("clockText") == "a quarter past ten in the morning", "clockText: %r" % w.mem.d.get("clockText"))
    check(w.mem.d.get("dayText") == "Sunday, the first of November", "dayText: %r" % w.mem.d.get("dayText"))
    cw, dw = ns["clock_words"], ns["day_words"]
    table = [((10, 0), "ten o'clock in the morning"), ((10, 30), "half past ten in the morning"), ((10, 45), "a quarter to eleven in the morning"),
             ((11, 40), "twenty to twelve in the morning"), ((12, 0), "twelve o'clock, midday"), ((0, 0), "midnight"), ((15, 3), "about five past three in the afternoon"),
             ((11, 58), "about twelve o'clock, midday"), ((17, 50), "ten to six in the afternoon"), ((20, 35), "twenty five to nine in the evening"),
             ((23, 50), "ten to twelve at night"), ((7, 20), "twenty past seven in the morning"), ((13, 5), "five past one in the afternoon"),
             ((3, 10), "ten past three at night")]
    for (h, m), want in table:
        check(cw(h, m) == want, "clock_words(%d, %d) = %r, wanted %r" % (h, m, cw(h, m), want))
    for h in range(24):
        for m in range(60):
            x = cw(h, m); check(x and all(ord(c) < 128 for c in x) and not any(c.isdigit() for c in x), "clock_words(%d,%d) = %r" % (h, m, x))
    check(dw(0, 2, 11) == "Monday, the second of November" and dw(2, 31, 12) == "Wednesday, the thirty first of December", "day_words")
    # texts the robot says are plain ASCII and free of the words that control it
    import re as _re
    top = io.open("/home/claude/hack/pkg/Activity/Activity_enu.top", encoding="utf-8").read()
    ctrl = []
    for nm in ("stop", "next", "back", "done", "repeat", "yes", "no", "help", "hello", "rollDice", "skipTurn", "newGame"):
        m = _re.search(r"^concept:\(%s\) \[([^\]]*)\]" % nm, top, flags=_re.M)
        ctrl += [(a or b).lower() for a, b in _re.findall(r'"([^"]+)"|(\S+)', m.group(1))]
    ctrl = [c for c in ctrl if c not in ("i need help", "please", "sure", "okay", "ok", "of course", "go ahead")]
    for tx in J + F:
        low = " " + " ".join(_re.sub(r"[^a-z ]", " ", tx.lower()).split()) + " "
        check(all(ord(c) < 128 for c in tx), "non-ASCII in a joke or fact: " + tx)
        bad = [x for x in ctrl if (" %s " % x) in low]
        check(not bad, "a joke or fact contains voice command words %r: %s" % (bad, tx))
        check(len(tx.split()) <= 26, "a joke or fact is too long to listen to: " + tx)

def v40_suggest_tests():
    w, box, ns, t = start()
    w.mem.d["pepperName"] = "lina"; tick(box, t)
    t[0] += 20; w.forced[:] = []; cmd(w, box, t, "suggest")
    check(w.forced == ["robotcmd suggestask"] and w.mem.d["suggestText"] == "How about some gentle exercise? Would you like that?", "first suggestion: %r %r" % (w.forced, w.mem.d.get("suggestText")))
    t[0] += 20; w.forced[:] = []; cmd(w, box, t, "suggestyes"); check(w.forced == ["robotcmd tilea"], "yes must start the suggested activity: %r" % w.forced)
    # what was done already is not suggested first
    box.current["exercises"] = 2
    t[0] += 20; cmd(w, box, t, "suggest"); check("some music" in w.mem.d["suggestText"], "exercise was done: %r" % w.mem.d["suggestText"])
    seen = [w.mem.d["suggestText"]]
    for _ in range(12):
        t[0] += 20; w.forced[:] = []; cmd(w, box, t, "suggestno")
        if w.forced == ["robotcmd suggestnone"]: break
        seen.append(w.mem.d["suggestText"])
    check(w.forced == ["robotcmd suggestnone"], "the suggestions never ran out: %r" % seen)
    check(len(seen) == len(set(seen)) == 8, "a suggestion was repeated or lost: %r" % seen)
    # a person who feels low gets the calm ones first
    box.current["moodLow"] = True; box.current["exercises"] = 0
    t[0] += 20; cmd(w, box, t, "suggest"); check("calm breathing" in w.mem.d["suggestText"], "low mood: %r" % w.mem.d["suggestText"])
    # not over an activity
    t[0] += 20; cmd(w, box, t, "exercise1"); w.forced[:] = []; t[0] += 20; cmd(w, box, t, "suggest")
    check(w.forced == ["robotcmd later"], "suggestion over an exercise: %r" % w.forced)
    cmd(w, box, t, "stop")
    # a new suggestion round starts from the top again
    t[0] += 20; cmd(w, box, t, "suggest"); check(w.mem.d["suggestText"], "fresh suggestion")

def v40_understand_tests():
    ns = {}
    code = load_script()
    w, box, ns, t = start()
    u = ns["understand"]
    cases = [("I would like to listen to some songs", "music"), ("can we do some stretching", "exercise"), ("some musical afternoon please", "music"), ("tell me about the pictures of malta", "relive"),
             ("i want my tablets", "medication"), ("lets dance", "dance"), ("a quiz please", "quiz"), ("snakes and ladders", "snl"), ("some deep breathing to relax", "breathing"),
             ("set a reminder", "reminder"), ("i want to chat", "chat")]
    for text, want in cases:
        r = u(text); check(r is not None and r[0] == want, "understand(%r) = %r, wanted %s" % (text, r, want))
    for text in ("", "hello there", "the weather is lovely", "yes", "on in at", "play some music and dance", "one"):
        r = u(text); check(r is None, "understand(%r) must be None, got %r" % (text, r))
    # the three-word rule: very short words never match a longer word by accident
    check(u("mus") is None and u("fun") is not None, "short words")
    # the dialog did not understand: a clear match becomes a question, otherwise a hint, the second in a row points to the screen
    w, box, ns, t = start(); w.mem.d["pepperName"] = "sam"; tick(box, t)
    w.mem.d["Dialog/LastInput"] = "i would like to listen to some songs"
    t[0] += 20; w.forced[:] = []; cmd(w, box, t, "nu")
    check(w.forced == ["robotcmd didmean"] and w.mem.d["didMeanText"] == "Did you mean music?", "did you mean: %r %r" % (w.forced, w.mem.d.get("didMeanText")))
    t[0] += 20; w.forced[:] = []; cmd(w, box, t, "dmyes"); check(w.forced == ["robotcmd tileb"], "yes must start what was asked: %r" % w.forced)
    t[0] += 20; w.forced[:] = []; cmd(w, box, t, "dmyes"); check(w.forced == [], "a second yes started it again")
    w.mem.d["Dialog/LastInput"] = "the weather is lovely"
    t[0] += 20; w.forced[:] = []; cmd(w, box, t, "nu"); check(w.forced == ["robotcmd nuplain"], "first miss: %r" % w.forced)
    t[0] += 20; w.forced[:] = []; cmd(w, box, t, "nu"); check(w.forced == ["robotcmd nutouch"], "second miss in a row: %r" % w.forced)
    t[0] += 20; cmd(w, box, t, "stop"); t[0] += 20; w.forced[:] = []; cmd(w, box, t, "nu"); check(w.forced == ["robotcmd nuplain"], "a command in between resets the count: %r" % w.forced)
    # what was heard is shown to the staff; Pepper's own forced words are not speech; only plain text is kept
    w.mem.d["Dialog/LastInput"] = "robotcmd tilea"; w.mem.d["pepperCmd"] = "stop"; t[0] += 20; tick(box, t)
    check(box.heard != "robotcmd tilea", "a forced token was shown as heard")
    w.mem.d["Dialog/LastInput"] = "play me a song \xe9\n"; t[0] += 20; cmd(w, box, t, "stop")
    check(box.heard == "play me a song" or box.heard.startswith("play me a song"), "heard: %r" % box.heard)
    check(last_state(w)["heard"] == box.heard, "the staff view is not told what was heard")
    check(len(box.heard) <= 60 and all(ord(c) < 128 for c in box.heard), "heard is not bounded or not plain text")
    # a stale phrase (already used as a command) is not matched again when something else is not understood
    w.mem.d["Dialog/LastInput"] = "music"; t[0] += 20; cmd(w, box, t, "song1"); cmd(w, box, t, "stop")
    t[0] += 20; w.forced[:] = []; cmd(w, box, t, "nu"); check(w.forced == ["robotcmd nuplain"], "a phrase that was already used came back as a guess: %r" % w.forced)

def v40_calm_tests():
    # calm mode on: what the robot is told, and that it is put back
    w = World()
    for nm in ("ALBasicAwareness", "ALFaceDetection", "ALPeoplePerception", "ALAutonomousLife"):
        w.proxies[nm] = Settings(nm, w)
    w, box, ns, t = start(w)
    C = w.calls
    check(("FullyEngaged",) in named(C, "ALBasicAwareness", "setEngagementMode"), "the robot must stay with one person (FullyEngaged)")
    check(("Head",) in named(C, "ALBasicAwareness", "setTrackingMode"), "tracking must be head only")
    check(all(("%s" % s_, False) in named(C, "ALBasicAwareness", "setStimulusDetectionEnabled") for s_ in ("Movement", "Sound", "NavigationMotion")), "movement and noise must not distract the robot")
    check((False,) in named(C, "ALFaceDetection", "setRecognitionEnabled"), "face recognition must be off")
    check((False,) in named(C, "ALPeoplePerception", "setMovementDetectionEnabled"), "movement detection must be off")
    check(all((a, False) in named(C, "ALAutonomousLife", "setAutonomousAbilityEnabled") for a in ("BackgroundMovement", "ListeningMovement")), "background and listening movement must be off")
    subs = named(C, "ALPeoplePerception", "subscribe")
    check(subs and subs[-1][1] == 1000, "people perception must run once a second: %r" % subs)
    # exercising switches speaking movement off and back on, background and listening stay off
    w.mem.d["pepperName"] = "tim"; tick(box, t); C[:] = []
    t[0] += 20; cmd(w, box, t, "exercise1"); cmd(w, box, t, "stop")
    ab = named(C, "ALAutonomousLife", "setAutonomousAbilityEnabled")
    check(("SpeakingMovement", False) in ab and ("SpeakingMovement", True) in ab, "speaking movement is not paused during an exercise")
    check(("BackgroundMovement", True) not in ab and ("ListeningMovement", True) not in ab, "calm mode gave background or listening movement back after an exercise: %r" % ab)
    # stopping puts the robot's own settings back
    C[:] = []; box.onInput_onStop()
    check(("SemiEngaged",) in named(C, "ALBasicAwareness", "setEngagementMode") and ("BodyRotation",) in named(C, "ALBasicAwareness", "setTrackingMode"), "the awareness settings were not put back")
    check((True,) in named(C, "ALFaceDetection", "setRecognitionEnabled") and ("BackgroundMovement", True) in named(C, "ALAutonomousLife", "setAutonomousAbilityEnabled"), "face recognition / abilities not put back")
    check(named(C, "ALPeoplePerception", "unsubscribe"), "people perception not unsubscribed")
    # calm mode off: the robot's own behaviour, the crowd warning still has its people list
    w2 = World(); w2.proxies["ALBasicAwareness"] = Settings("ALBasicAwareness", w2)
    box2, ns2, t2 = make_box(w2)
    box2._params["Calm mode"] = 0 if hasattr(box2, "_params") else None
    box2.onInput_onStart()
    check(not named(w2.calls, "ALBasicAwareness", "setEngagementMode") and not named(w2.calls, "ALBasicAwareness", "setTrackingMode"), "calm mode off must not touch the awareness settings")
    check(named(w2.calls, "ALPeoplePerception", "subscribe"), "calm mode off must still subscribe to people perception for the crowd warning")
    # the crowd warning off: no perception at all
    w3 = World(); box3, ns3, t3 = make_box(w3); box3._params["People allowed"] = 0; box3.onInput_onStart()
    check(not named(w3.calls, "ALPeoplePerception", "subscribe"), "no crowd warning: people perception must not run")
    # a robot without these services starts fine
    w4 = World()
    class Boom(Rec):
        def __getattr__(self, m):
            if m.startswith("__"): raise AttributeError(m)
            def f(*a): raise RuntimeError("no such method")
            return f
    for nm in ("ALBasicAwareness", "ALFaceDetection", "ALPeoplePerception", "ALAutonomousLife"): w4.proxies[nm] = Boom(nm, w4)
    w4, b4, n4, t4 = start(w4); w4.mem.d["pepperName"] = "x"; tick(b4, t4); check(b4.current and b4.running, "a robot whose services fail must still run")

def v40_lag_tests():
    w = World(); w.proxies["ALBasicAwareness"] = Settings("ALBasicAwareness", w)
    w, box, ns, t = start(w)
    clock = [5000.0]; box.perf = lambda: clock[0]; box.lastTickAt = None
    def step(gap):
        clock[0] += gap; t[0] += 0.1; box.tick()
    C = w.calls; C[:] = []
    for _ in range(20): step(0.12)
    check(not box.lagMode, "a healthy robot was put into lag mode")
    for _ in range(2): step(1.2)
    check(not box.lagMode, "two slow ticks are not yet lag")
    step(0.12); step(1.2); step(1.2)
    check(not box.lagMode, "slow ticks must be in a row")
    step(1.2)
    check(box.lagMode and named(C, "ALBasicAwareness", "pauseAwareness") and named(C, "ALPeoplePerception", "unsubscribe"), "three slow ticks in a row must pause tracking: %r" % [c[1] for c in C])
    check(last_state(w)["lag"] is True, "the staff view is not told")
    # while lagging the crowd warning is silent, and a busy robot is not made to resume
    w.mem.d["PeoplePerception/PeopleList"] = [1, 2, 3, 4]; w.forced[:] = []
    for _ in range(40): step(0.12)
    check("robotcmd crowd" not in w.forced, "the crowd warning spoke while the robot lagged")
    check(box.lagMode, "tracking came back before LAG_HOLD_S")
    C[:] = []
    for _ in range(int(ns["LAG_HOLD_S"] / 0.12) + 5): step(0.12)
    check(not box.lagMode and named(C, "ALBasicAwareness", "resumeAwareness") and named(C, "ALPeoplePerception", "subscribe"), "tracking did not come back after the hold: %r" % [c[1] for c in C])
    check(last_state(w)["lag"] is False, "the staff view still says lag")
    # slow, but not recovering: it stays paused
    for _ in range(3): step(1.2)
    check(box.lagMode, "lag mode again")
    for _ in range(int(ns["LAG_HOLD_S"] / 0.5) + 40): step(0.5)
    check(box.lagMode, "tracking came back although the loop was still slow (0.5 s per tick)")
    # an exercise running: tracking is never resumed under it
    w.mem.d["pepperName"] = "uma"; box.tick()
    t[0] += 20; cmd(w, box, t, "exercise1"); C[:] = []
    for _ in range(int(ns["LAG_HOLD_S"] / 0.12) + 20): step(0.12)
    check(not named(C, "ALBasicAwareness", "resumeAwareness"), "tracking resumed under a running exercise")

def v40_crowd_tests():
    w, box, ns, t = start()
    w.mem.d["PeoplePerception/PeopleList"] = [1, 2, 3, 4]
    box.lastCrowdCheck = 0.0
    def run_for(sec):
        for _ in range(int(sec * 5)): tick(box, t, 0.2)
    w.forced[:] = []; run_for(6)
    check("robotcmd crowd" in w.forced, "a real crowd with nobody served gets the warning: %r" % w.forced)
    for what, c in (("music", "song1"), ("exercise", "exercise1"), ("dance", "dance"), ("breathing", "breathe"), ("quiz", "quiz"), ("cards", "relive"), ("game", "snl")):
        t[0] += 200; cmd(w, box, t, c); box.crowdLast = None; box.crowdSince = None; w.forced[:] = []; run_for(6)
        check("robotcmd crowd" not in w.forced or any(f.startswith("robotcmd") for f in []), "%s: the crowd warning spoke over the activity: %r" % (what, [f for f in w.forced if f == "robotcmd crowd"]))
        t[0] += 20; cmd(w, box, t, "stop")

def run():
    # --- start, session -----------------------------------------------------------------------------------
    w, box, ns, t = start()
    check(w.mem.d.get("Pepper/SessionState"), "no SessionState after start")
    st = last_state(w); check(st and st["v"] == "4.1.1", "state version is not 4.1.1: %r" % (st and st.get("v")))
    w.mem.d["pepperName"] = "maria"; tick(box, t)
    check(box.current and box.current["name"] == "Maria", "name not capitalised/started")
    check("mood" not in box.current and "moodChecks" not in box.current and box.current["memCards"] == 0 and box.current["memLikes"] == [], "record fields: %r" % sorted(box.current))

    # --- every tile sends its own token --------------------------------------------------------------------
    tiles = {"exercise": "tilea", "music": "tileb", "chat": "tilec", "medication": "tiled", "dance": "tilee", "breathing": "tilef",
             "reminder": "tileg", "help": "tileh", "relive": "tilei", "activities": "tilep", "snl": "tileq", "quiz": "tilek", "sax": "tilel",
             "song1": "tilem", "song2": "tilen", "song3": "tileo"}
    for text, tok in tiles.items():
        w.forced[:] = []
        say(w, box, t, text)
        check(w.forced == ["robotcmd " + tok], "tile %s forced %r, expected %s" % (text, w.forced, tok))
    w.forced[:] = []; say(w, box, t, "frobnicate"); check(w.forced == [], "unknown tile text was forwarded")
    w.forced[:] = []; say(w, box, t, "next"); check(w.forced == [], "'next' outside an exercise was forwarded")

    # --- the mood feature (a camera reading of the face) is gone ---------------------------------------------------------------
    w.outputs[:] = []; w.forced[:] = []
    cmd(w, box, t, "mood")
    check(not any(o in w.outputs for o in ("onMood", "onStopAll")), "the old mood command still does something: %r" % w.outputs)
    say(w, box, t, "mood"); check(w.forced == [], "the old mood tile text was forwarded: %r" % w.forced)
    check(not hasattr(box, "onInput_onMoodResult") and "moodWait" not in last_state(w) and "MOODS" not in ns, "mood code is still in the controller")

    # --- exercises still run 40 s and report ------------------------------------------------------------------------
    w.forced[:] = []; w.outputs[:] = []
    cmd(w, box, t, "exercise3"); check("onExercise3" in w.outputs, "exercise3 output")
    for _ in range(60):
        tick(box, t, 1.0)
    check("robotcmd exdone3" in w.forced, "exercise end not announced: %r" % w.forced)

    # --- songs and shows report the item ------------------------------------------------------------------------------
    w.outputs[:] = []; cmd(w, box, t, "song2")
    check("onSong2" in w.outputs and box.mode == "music" and last_state(w)["item"] == "song2", "song2 / item")
    for _ in range(60): tick(box, t, 1.0)
    check(box.mode is None and last_state(w)["item"] == "", "song did not end by timer")
    for c, o in (("sax", "onSax"), ("dance", "onDance")):
        w.outputs[:] = []; cmd(w, box, t, c); check(o in w.outputs and last_state(w)["item"] == c, c + " show")
        cmd(w, box, t, "stop")

    w.outputs[:] = []; cmd(w, box, t, "football")
    check(not w.outputs or w.outputs == ["onStopAll"] or "onFootball" not in w.outputs, "football must no longer be a command")
    check("onFootball" not in ns["SHOWS"].values() and "football" not in ns["TILE_TOKENS"], "football is still wired in the controller")

    # --- alerts ---------------------------------------------------------------------------------------------------------
    cmd(w, box, t, "exercise1")
    w.outputs[:] = []; w.events[:] = []
    cmd(w, box, t, "alert")
    check(box.mode is None and "onStopAll" in w.outputs, "alert did not stop the exercise")
    check("onAlert" in w.outputs, "alert did not fire onAlert")
    check(any(k == "Pepper/CaregiverAlert" for k, v in w.events), "no Pepper/CaregiverAlert event")
    st = last_state(w)
    check(st["alertsOpen"] == 1 and st["alerts"][0]["id"] == 1 and st["alerts"][0]["seen"] is False, "alert state wrong: %r" % st["alerts"])
    cmd(w, box, t, "alert")
    check(last_state(w)["alertsOpen"] == 1, "a second alert 3 s later is the same call for help")
    t[0] += 20.0; cmd(w, box, t, "alert")
    check(last_state(w)["alertsOpen"] == 2 and last_state(w)["alerts"][1]["id"] == 2, "second alert")
    w.mem.d["Pepper/TabletCmd"] = json.dumps({"cmd": "ack", "alert": 1}); tick(box, t)
    st = last_state(w); check(st["alertsOpen"] == 1 and st["alerts"][0]["seen"] and not st["alerts"][1]["seen"], "ack one alert")
    w.mem.d["Pepper/TabletCmd"] = json.dumps({"cmd": "ack"}); tick(box, t)
    check(last_state(w)["alertsOpen"] == 0, "ack all")
    for _ in range(30): cmd(w, box, t, "alert")
    check(len(last_state(w)["alerts"]) <= 10 and len(box.alerts) <= 20, "alert list not bounded")

    # --- tablet: name, queue, reminder, history ---------------------------------------------------------------------------
    w.mem.d["Pepper/TabletCmd"] = json.dumps({"cmd": "name", "name": "Joseph Borg", "id": 1}); tick(box, t)
    check(box.current["name"] == "Joseph Borg", "typed name")
    check(w.forced[-1:] == ["robotcmd registered"], "a later person typed on the tablet must get the short greeting: %r" % w.forced[-2:])
    # the very first person since Pepper started, typed on the tablet, hears what Pepper can do
    w2, box2, ns2, t2 = start()
    check(box2.introduced is False, "a fresh controller has not introduced itself yet")
    w2.forced[:] = []
    w2.mem.d["Pepper/TabletCmd"] = json.dumps({"cmd": "name", "name": "Anna", "id": 1}); tick(box2, t2)
    check(w2.forced[-1:] == ["robotcmd registeredfirst"] and box2.introduced is True, "the first typed name must get the full welcome: %r" % w2.forced)
    w2.mem.d["Pepper/TabletCmd"] = json.dumps({"cmd": "name", "name": "Ben", "id": 2}); tick(box2, t2)
    check(w2.forced[-1:] == ["robotcmd registered"], "the second typed name must get the short greeting: %r" % w2.forced)
    # a first person who gave the name by voice (the dialog already said the welcome) is not welcomed twice
    w3, box3, ns3, t3 = start()
    w3.mem.d["pepperName"] = "carl"; tick(box3, t3); w3.forced[:] = []
    w3.mem.d["Pepper/TabletCmd"] = json.dumps({"cmd": "name", "name": "Dora", "id": 1}); tick(box3, t3)
    check(w3.forced[-1:] == ["robotcmd registered"], "after a spoken first name the welcome must not be repeated: %r" % w3.forced)
    w.mem.d["Pepper/TabletCmd"] = json.dumps({"cmd": "queue", "name": "Carmen"}); tick(box, t)
    w.mem.d["Pepper/TabletCmd"] = json.dumps({"cmd": "remind", "minutes": 5}); tick(box, t)
    check(len(last_state(w)["reminders"]) == 1 and last_state(w)["queue"] == ["Carmen"], "queue / reminder")
    check(len(box.history) >= 1, "history empty after switching patient")

    # --- clearData -----------------------------------------------------------------------------------------------------------
    cmd(w, box, t, "exercise2"); w.concepts[:] = []
    w.mem.d["Dialog/LastInput"] = "my name is anna"; box.heard = "my name is anna"; box.heardUsed = "my name is anna"; box.suggTried = ["music"]; box.dm = {"name": "music", "token": "tileb"}
    w.mem.d["Pepper/TabletCmd"] = json.dumps({"cmd": "clearData"}); tick(box, t)
    st = last_state(w)
    check(st["heard"] == "" and box.heardUsed == "" and box.suggTried == [] and box.dm is None, "clearData kept what was heard: %r" % st.get("heard"))
    check(w.mem.d.get("Dialog/LastInput") == "", "clearData left the heard text in ALMemory")
    check(box.mode is None and st["current"] is None and st["history"] == [] and st["queue"] == [] and st["reminders"] == [] and st["alerts"] == [] and st["alertsOpen"] == 0, "clearData left something behind: %r" % {k: st[k] for k in ("current", "history", "queue", "reminders", "alerts")})
    check(w.mem.d.get("name") == "" and w.mem.d.get("medNext") == "not set", "clearData memory keys")
    check(any(c[0] == "extraNames" and c[2] == [] for c in w.concepts), "typed names not cleared from the dialog")
    check(box.extraNames == [], "extraNames kept")

    # --- the quiz (own patient record, after the alert and wipe tests so their counts stay simple) ------------------------------
    w.mem.d["pepperName"] = "quizzer"; tick(box, t)
    quiz_tests(w, box, ns, t)
    mem_tests(w, box, ns, t)
    mem_answer_tests(w, box, ns, t)
    snl_tests(w, box, ns, t)
    pick_tests(w, box, ns, t)
    v41_dashboard_tests(); v40_startup_tests(); v411_voice_tests(); v40_session_tests(); v40_needs_tests(); v40_help_tests(); v40_talk_tests(); v40_suggest_tests(); v40_understand_tests()
    v40_calm_tests(); v40_lag_tests(); v40_crowd_tests()

    # --- unicode from the tablet (Python 2) and duplicates --------------------------------------------------------------------
    w.forced[:] = []
    w.mem.d["Pepper/TabletCmd"] = json.dumps({"cmd": "say", "text": u"relive", "id": 77}); tick(box, t)
    w.mem.d["Pepper/TabletCmd"] = json.dumps({"cmd": "say", "text": u"relive", "id": 77}); tick(box, t)
    check(w.forced == ["robotcmd tilei"], "duplicate tablet id should be ignored once: %r" % w.forced)
    # --- stop ------------------------------------------------------------------------------------------------------------------------
    w.outputs[:] = []; box.onInput_onStop(); check("onStopped" in w.outputs and not box.running, "onStop")

    # --- an older controller steps down -----------------------------------------------------------------------------------------------
    w2, b2, ns2, t2 = start()
    w2.mem.d["Pepper/CareControllerToken"] = "someone-else"; tick(b2, t2)
    check(not b2.running, "a controller should step down when a newer one owns the token")

if __name__ == "__main__":
    if "--run" in sys.argv:
        try:
            run()
        except Exception:
            import traceback; traceback.print_exc(); fails.append("exception")
        if fails:
            print("FAIL (%s):" % sys.version.split()[0]); [print(" -", f) for f in fails]; sys.exit(1)
        print("controller checks passed on Python %s" % sys.version.split()[0])
    else:
        ok = True
        for py in ("python3", PY27):
            r = subprocess.run([py, os.path.abspath(__file__), "--run"], capture_output=True, text=True)
            print(r.stdout.strip(), r.stderr.strip()[-1500:])
            ok = ok and r.returncode == 0
        print("CONTROLLER OK" if ok else "CONTROLLER FAILED"); sys.exit(0 if ok else 1)
