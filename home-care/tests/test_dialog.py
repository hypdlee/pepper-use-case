import re, sys
top = open("/home/claude/hack/pkg/Activity/Activity_enu.top", encoding="utf-8").read()
ctl = open("/home/claude/hack/src/care_controller.py", encoding="utf-8").read()
fails = []
def check(c, m):
    if not c: fails.append(m)

props = set(re.findall(r"^proposal:\s*%(\w+)", top, flags=re.M))
refs = set(re.findall(r"\^gotoReactivate\((\w+)\)", top))
check(not (refs - props), "gotoReactivate to missing proposals: %s" % sorted(refs - props))
check(not (props - refs - {"autoStart"}), "proposals never reached: %s" % sorted(props - refs))
check(all(ord(c) < 128 for c in top), "non-ASCII in the dialog")
concepts = set(re.findall(r"^concept:\(([\w]+)\)", top, flags=re.M)) | set(re.findall(r"^dynamic:(\w+)", top, flags=re.M))
used = set(re.findall(r"~(\w+)", re.sub(r"^topic:.*$", "", top, flags=re.M)))
check(not (used - concepts), "undefined concepts: %s" % sorted(used - concepts))

# tokens the controller can force
tiles = dict(re.findall(r'"(\w+)": "(tile\w)"', ctl))
check(len(tiles) == 16, "expected 16 tile tokens in the controller, found %d" % len(tiles))
NEWTOK = {"welcome", "hellosame", "grouphere", "saytext", "later", "hintquiz", "hintmem", "hintsnl", "hintex", "hintbreath", "hintmusic", "hintidle", "suggestask", "suggestnone", "didmean", "nuplain", "nutouch"}
forced = NEWTOK | set(tiles.values()) | {"crowd", "registered", "registeredfirst", "askname", "callnext", "closed", "meddue", "breathdone", "quizask", "quizend", "quizidle", "memcard", "memend", "memidle", "snlsay", "snlend", "snlidle"} | {"exdone%d" % n for n in range(1, 10)}
handled_top = set(re.findall(r'^u:\("robotcmd (\w+)"\)', top, flags=re.M))
check(forced <= handled_top, "top-level rules missing for: %s" % sorted(forced - handled_top))
blocks = re.split(r"^proposal:", top, flags=re.M)[1:]
for b in blocks:
    nm = re.match(r"\s*%(\w+)", b).group(1)
    if "u1:(_*)" in b:
        have = set(re.findall(r'"robotcmd (\w+)"', b))
        check(forced <= have, "catch-all %s misses tokens %s" % (nm, sorted(forced - have)))
# v4.1.1: the voice check. The controller forces "robotcmd ping"; the dialog answers with a silent assignment the controller waits for
pong = re.search(r'^DIALOG_PONG = "(\w+)"', ctl, flags=re.M)
check(pong is not None, "controller has no DIALOG_PONG")
check(pong and re.search(r'^u:\("robotcmd ping"\) \$dlgPong=%s$' % pong.group(1), top, flags=re.M), "the dialog has no silent ping rule that writes dlgPong=%s" % (pong and pong.group(1)))
check('"robotcmd ping"' in ctl, "the controller never forces the ping")
# each tile reaches a sensible proposal
want = {"tilea": "exerciseIntro", "tileb": "chooseSong", "tilec": "chatQ1", "tiled": "medCheck", "tilee": "dancePlay", "tilef": "breatheIntro",
        "tileg": "reminderAsk", "tileh": "callHelp", "tilei": "memStart", "tileq": "snlStart", "tilek": "quizStart", "tilel": "saxPlay",
        "tilem": "song1Play", "tilen": "song2Play", "tileo": "song3Play", "tilep": "chooseActivity"}
for tok, tgt in want.items():
    check(re.search(r'^u:\("robotcmd %s"\) \^gotoReactivate\(%s\)' % (tok, tgt), top, flags=re.M), "%s should go to %s" % (tok, tgt))
    check(tiles.get([k for k, v in tiles.items() if v == tok][0]) == tok, "token table")
for blk in ("offerMenu", "offerMenuAgain", "anythingElse"):
    b = [x for x in blocks if x.lstrip().startswith("%" + blk + " ")][0]
    check("u1:(~activities) ^gotoReactivate(chooseActivity)" in b, blk + " does not offer activities")
    check("u1:(~music) ^gotoReactivate(chooseSong)" in b, blk + " does not offer music")
cs = [x for x in blocks if x.lstrip().startswith("%chooseSong ")][0]
check("saxPlay" in cs and "song1Play" in cs and "guitar" not in cs.lower(), "music choice must cover songs and the saxophone, and no guitar")
check("guitar" not in top.lower(), "the guitar is still in the dialog")
ca = [x for x in blocks if x.lstrip().startswith("%chooseActivity ")][0]
check("dancePlay" in ca and "quizStart" in ca, "activities choice must cover dance and the quiz")
check("football" not in ca.lower(), "football is still offered in Activities")
check("footballPlay" not in top, "the football proposal is still in the dialog")
# the quiz: Pepper says what the controller writes, listens for one, two, three or the answer itself, and every answer reaches the controller
qa = [x for x in blocks if x.lstrip().startswith("%quizAsk ")][0]
check(qa.split("\n")[0].strip().endswith("$quizText"), "quizAsk must say $quizText")
for n, w in ((1, "One"), (2, "Two"), (3, "Three")):
    check(re.search(r"u1:\(~ans%s\) \$pepperCmd=qa%d" % (w, n), qa), "quizAsk: answer %d not wired" % n)
check("quizOpt" not in top, "the per-question dynamic answer words must be gone (they made the quiz slow and unreliable)")
check("$pepperCmd=qrepeat" in qa and "~stop" in qa, "quizAsk must repeat and stop")
qe = [x for x in blocks if x.lstrip().startswith("%quizEnd ")][0]
check("$quizText" in qe.split("\n")[0] and "quizStart" in qe, "quizEnd must say the score and offer another quiz")
# v3.5: loose words (noise, music, Pepper's own voice) must not switch what is happening: no top-level activity words
tops = [l for l in top.splitlines() if l.startswith("u:(")]
for l in tops:
    check("gotoReactivate" not in l or '"robotcmd' in l or any(x in l for x in ("~help", "~reminder", "~medication")), "top-level word rule can switch activity: %s" % l)
for w in ("~exercise", "~music", "~dance", "~quiz", "~activities", "~breathe", "~chat", "saxophone"):
    check(not any(l.startswith("u:(%s)" % w) for l in tops), "top-level rule for %s still switches activity from anywhere" % w)
for nm in ("song1Play", "song2Play", "song3Play", "dancePlay", "saxPlay"):
    b = [x for x in blocks if x.lstrip().startswith("%" + nm + " ")][0]
    check("anythingElse" in b and "~next" not in b and "~thx" not in b and "~done" not in b, "%s can be ended by a loose word (only stop should)" % nm)
for n in range(1, 10):
    b = [x for x in blocks if x.lstrip().startswith("%%exercise%d " % n)][0]
    check("~repeat" not in b and "~done" not in b, "exercise%d can be restarted or ended by a loose word" % n)
check(re.search(r'^u:\("robotcmd quizask"\) \^gotoReactivate\(quizAsk\)', top, flags=re.M), "quizask not handled")
for blk in ("offerMenu", "offerMenuAgain", "anythingElse"):
    b = [x for x in blocks if x.lstrip().startswith("%" + blk + " ")][0]
    check("u1:(~quiz) ^gotoReactivate(quizStart)" in b, blk + " does not offer the quiz")
menu = re.search(r"proposal: %offerMenu [^\n]*", top).group(0).lower()
# the welcome names the eight topics of the home screen (not what is inside them)
for word in ("exercise", "breathing", "music", "activities", "chat", "memories", "medicine", "reminder"):
    check(word in menu, "the spoken menu must name '%s' (a tile of the home screen): %s" % (word, menu))
check(all(x not in menu for x in ("dance", "saxophone", "quiz", "song", "snakes")), "the welcome describes sub topics: " + menu)
check(len(menu.split()) <= 24, "the spoken menu is too long to listen to")
# the very first opening (hello, or the first name typed on the tablet) names all eight topics before anything else is asked
for blk in ("welcome", "nameFirst"):
    wl = [x for x in blocks if x.lstrip().startswith("%" + blk + " ")][0].split("\n")[0].lower()
    for word in ("exercise", "breathe", "music", "activities", "chat", "memories", "medicine", "reminders"):
        check(word in wl, "the first opening (%s) must name '%s': %s" % (blk, word, wl))
    check(all(x not in wl for x in ("dance", "saxophone", "quiz", "song", "snakes")), "the first opening describes sub topics: " + wl)
    check(len(wl.split()) <= 45, "the first opening is too long: " + blk)
# v4.0: a greeting never starts the welcome by itself: it tells the controller, which decides (nothing restarts while someone is served)
hl = re.search(r"^u:\(~hello\)[^\n]*", top, flags=re.M).group(0)
check("$pepperCmd=hello" in hl and "gotoReactivate" not in hl and "^stayInScope" in hl, "hello must only report to the controller: " + hl)
gl = re.search(r"^u:\(~group\)[^\n]*", top, flags=re.M).group(0)
check("$pepperCmd=group" in gl and "gotoReactivate" not in gl, "a group phrase must only report to the controller: " + gl)
check(re.search(r'^u:\("robotcmd welcome"\) \^start\(animations/Stand/Gestures/Hey_1\) Hello! \^wait\(animations/Stand/Gestures/Hey_1\) \^gotoReactivate\(welcome\)', top, flags=re.M), "the welcome token is not wired")
check(re.search(r"^proposal: %autoStart \$pepperCmd=autostart\n", top, flags=re.M) and top.index("proposal: %autoStart") < top.index("proposal: %welcome"), "the first proposal must be the silent autoStart")
for w_ in ("my turn", "everyone", "everybody"):
    check(w_ not in top.split("concept:(nextPatient)")[1].split("\n")[0].lower() and w_ not in top.split("concept:(group)")[1].split("\n")[0].lower(), "the concept still has the loose phrase: " + w_)
check("^gotoReactivate(askName)" in [x for x in blocks if x.lstrip().startswith("%welcome ")][0], "the welcome must go on to ask the name")
check("^gotoReactivate(medCheck)" in [x for x in blocks if x.lstrip().startswith("%nameFirst ")][0], "nameFirst must go on to the medicine check")
for blk in ("offerMenu", "offerMenuAgain", "anythingElse"):
    b = [x for x in blocks if x.lstrip().startswith("%" + blk + " ")][0]
    check("u1:(~relive) ^gotoReactivate(memStart)" in b, blk + " does not offer Relive Malta")
# Relive Malta: Pepper says what the controller writes, stays quiet, and only next, back, repeat and stop are heard
mc = [x for x in blocks if x.lstrip().startswith("%memCard ")][0]
check(mc.split("\n")[0].strip().endswith("$memText"), "memCard must say $memText")
for rule, cmdname in (("~next", "mnext"), ("~back", "mback"), ("~repeat", "mrepeat")):
    check(re.search(r"u1:\(%s\) \$pepperCmd=%s" % (re.escape(rule), cmdname), mc), "memCard: %s not wired to %s" % (rule, cmdname))
check("~stop" in mc and "$pepperCmd=stop" in mc, "memCard must stop")
check("NotUnderstood" not in mc and "NotSpeaking" not in mc, "memCard must stay quiet: no hints or timeouts that speak while people talk")
check(len(re.findall(r"u1:\(", mc)) == 6, "memCard has loose rules: %s" % re.findall(r"u1:\([^)]*\)", mc))
# v3.7: the answers. Words heard = the ordinal plus exactly the words each card lists for that slot; nothing speaks
_ns = {}
exec(ctl[ctl.index("MEM_CARDS = ["):ctl.index("MEM_OPEN = ")], _ns)
for slot, (ord_, cname) in enumerate((("~ansOne", "memW1"), ("~ansTwo", "memW2")), 1):
    check(("u1:([%s ~%s]) $pepperCmd=ma%d" % (ord_, cname, slot)) in mc, "memCard: answer %d not wired" % slot)
    m_ = re.search(r"^concept:\(%s\) \[([^\]]*)\]" % cname, top, flags=re.M)
    check(m_ is not None, "concept " + cname + " missing")
    got = re.findall(r'"([^"]+)"|(\S+)', m_.group(1)) if m_ else []
    got = sorted(a or b for a, b in got)
    want = sorted([w_ for c in _ns["MEM_CARDS"] for w_ in c[4][slot - 1][1]])
    check(got == want, "concept %s differs from the card words: %r" % (cname, sorted(set(got) ^ set(want))))
check("memW3" not in top and "ma3" not in top, "the removed third answer is still in the dialog")
check("^gotoReactivate(memStart)" in [x for x in blocks if x.lstrip().startswith("%offerMenu ")][0], "the menu cannot start Relive Malta by voice")
me = [x for x in blocks if x.lstrip().startswith("%memEnd ")][0]
check("$memText" in me.split("\n")[0] and "memStart" in me, "memEnd must say the closing text and offer to look again")
ms = [x for x in blocks if x.lstrip().startswith("%memStart ")][0]
check("$pepperCmd=relive" in ms.split("\n")[0], "memStart must send relive")
check("mood" not in " ".join(b for b in blocks).lower().replace("moodlow", ""), "mood is still in the dialog")
for tok, tgt in (("memcard", "memCard"), ("memend", "memEnd")):
    check(re.search(r'^u:\("robotcmd %s"\) \^gotoReactivate\(%s\)' % (tok, tgt), top, flags=re.M), "%s not handled" % tok)
# the dialog's pepperCmd values are all handled by handle()
cmds = set(re.findall(r"\$pepperCmd=(\w+)", top))
body = ctl[ctl.index("    def handle(self, cmd):"):ctl.index("    # ------------------------------------------------------------------ sessions")]
literal = set(re.findall(r'cmd == "(\w+)"', body)) | set(re.findall(r'"(\w+)"', " ".join(re.findall(r"cmd in \(([^)]*)\)", body))))
literal |= set(re.findall(r'"(need\w+)":', ctl))
for c in cmds:
    ok = c in literal or (c.startswith("exercise") and c[8:].isdigit()) or (c.startswith("song") and c[4:] in "123") or c in ("dance", "sax")
    check(ok, "pepperCmd %s is not handled by the controller" % c)

# ---- Snakes and Ladders (v3.8) -----------------------------------------------------------------------------------------------------
def conc(name):
    m = re.search(r"^concept:\(%s\) \[([^\]]*)\]" % name, top, flags=re.M)
    check(m is not None, "concept %s missing" % name)
    return m.group(1).lower() if m else ""
check("snakes and ladders" in conc("snl") and "game" in conc("snl"), "~snl must know the name of the game and 'game'")
check("roll" in conc("rollDice") and "dice" in conc("rollDice"), "~rollDice")
check("skip" in conc("skipTurn"), "~skipTurn")
check("new game" in conc("newGame") and "play again" in conc("newGame"), "~newGame")
check(re.search(r"(^|\s)activity(\s|$)", conc("activities")) and re.search(r"(^|\s)activities(\s|$)", conc("activities")), "~activities must accept 'activity' as well as 'activities'")
for blk in ("offerMenu", "offerMenuAgain", "anythingElse"):
    b = [x for x in blocks if x.lstrip().startswith("%" + blk + " ")][0]
    check("u1:(~snl) ^gotoReactivate(snlStart)" in b, blk + " does not offer Snakes and Ladders")
check("u1:(~snl) ^gotoReactivate(snlStart)" in ca and "snakes" in ca.split("\n")[0].lower(), "the activities choice must offer Snakes and Ladders")
ss = [x for x in blocks if x.lstrip().startswith("%snlStart ")][0]
check("$pepperCmd=snl" in ss.split("\n")[0], "snlStart must send snl")
sy = [x for x in blocks if x.lstrip().startswith("%snlSay ")][0]
check(sy.split("\n")[0].strip().endswith("$snlText"), "snlSay must say $snlText")
for rule, tok in (("~rollDice", "sroll"), ("~skipTurn", "sskip"), ("~newGame", "snew"), ("~repeat", "srepeat")):
    check(re.search(r"u1:\(%s\) \$pepperCmd=%s" % (re.escape(rule), tok), sy), "snlSay: %s not wired to %s" % (rule, tok))
check("~stop" in sy and "$pepperCmd=stop" in sy, "snlSay must stop")
se = [x for x in blocks if x.lstrip().startswith("%snlEnd ")][0]
check(se.split("\n")[0].strip().endswith("$snlText"), "snlEnd must say $snlText")
check("$pepperCmd=snew" in se and "$pepperCmd=stop" in se and "$pepperCmd=srepeat" in se, "snlEnd must offer another game, stop and repeat")
# the three words that a resident says to play must be heard at the top level too (right after Pepper's intro), not only inside the game
for tok in ("snlsay", "snlend", "snlidle", "tileq"):
    check(re.search(r'^u:\("robotcmd %s"\)' % tok, top, flags=re.M), "top-level rule for %s" % tok)
# a topic word said instead of a name starts that topic (the 'activity' bug: only a tap worked, because the name catch-all swallowed the word)
for nm in ("askName", "askNameAgain"):
    b = [x for x in blocks if x.lstrip().startswith("%" + nm + " ")][0]
    pos = b.index("u1:(_~names)") if "u1:(_~names)" in b else b.index("u1:(_*)")
    head = b[:pos]
    for rule, tgt in (("~activities", "chooseActivity"), ("~music", "chooseSong"), ("~exercise", "exerciseIntro"), ("~relive", "memStart"),
                      ("~snl", "snlStart"), ("~quiz", "quizStart"), ("~breathe", "breatheIntro"), ("~chat", "chatQ1"), ("~dance", "dancePlay")):
        check(re.search(r"u1:\(%s\)[^\n]*%s" % (re.escape(rule), tgt), head), "%s: topic %s must be heard before the name catch-all" % (nm, rule))
# Pepper's own fixed game lines contain none of the words that control the game (except the one sentence that tells how to start)
ctl_src = ctl
texts = []
for nm in ("SNL_YOU", "SNL_ME"):
    texts += re.search(r"^%s = \[(.*)\]" % nm, ctl_src, flags=re.M).group(1).split('", "')
for nm in ("SNL_YOUR_GO", "SNL_SKIPPED", "SNL_WIN_YOU", "SNL_WIN_ME"):
    texts.append(re.search(r'^%s = "(.*)"' % nm, ctl_src, flags=re.M).group(1))
check(len(texts) >= 8, "the game texts were not found")
for tx in texts:
    low = tx.lower()
    check(not any(x in low for x in ("roll", "dice", "skip", "stop", "new game", "repeat")) or "another game" in low, "Pepper's own game line has a control word: " + tx)

# v3.9: when Pepper asks what to play, the tablet opens the same list by itself (the dialog tells the controller)
for nm, tok in (("chooseSong", "pickmusic"), ("chooseActivity", "pickact")):
    b = [x for x in blocks if x.lstrip().startswith("%" + nm + " ")][0]
    check(b.split("\n")[0].lstrip().startswith("%" + nm + " $pepperCmd=" + tok + " "), nm + " must send " + tok + " as it asks")
    check("[~stop ~no]) Okay. $pepperCmd=pickoff" in b and "NotSpeaking15) $pepperCmd=pickoff" in b, nm + " must close the list when the question is dropped")


# ---- v4.0: needs and safety, help, time, jokes, suggestions, did you mean ---------------------------------------------------------
NEEDS_RULES = {"needfall": "i fell", "needpain": "it hurts", "needdizzy": "i feel dizzy", "needbreath": "i cannot breathe", "needtoilet": "i need the toilet",
               "needdrink": "i am thirsty", "needfood": "i am hungry", "needcold": "i am cold", "needhot": "i am hot"}
name_blocks = [x for x in blocks if x.lstrip().startswith(("%askName ", "%askNameAgain "))]
check(len(name_blocks) == 2, "the two name questions")
for tok, phrase in NEEDS_RULES.items():
    check(re.search(r'^u:\(\[[^\]]*"%s"[^\]]*\]\) [^\n]*\$pepperCmd=%s \^stayInScope' % (re.escape(phrase), tok), top, flags=re.M), "top level: '%s' must alert the carer (%s)" % (phrase, tok))
    for b in name_blocks:
        pos = b.index("u1:(_~names)")
        check(re.search(r'u1:\(\[[^\]]*"%s"[^\]]*\]\) [^\n]*\$pepperCmd=%s \^stayInScope' % (re.escape(phrase), tok), b[:pos]), "name question: '%s' must be heard before the name catch-all (%s)" % (phrase, tok))
for phrase, tok in (("what can i say", "helpme"), ("tell me a joke", "joke"), ("tell me a fact", "fact"), ("surprise me", "suggest"), ("i am lonely", "moodlow")):
    check(re.search(r'^u:\(\[[^\]]*"%s"[^\]]*\]\) [^\n]*\$pepperCmd=%s ' % (re.escape(phrase), tok), top, flags=re.M), "top level: %s -> %s" % (phrase, tok))
check(re.search(r'^u:\(\[[^\]]*"what time is it"[^\]]*\]\) It is \$clockText\. \^stayInScope', top, flags=re.M), "the time rule")
check(re.search(r'^u:\(\[[^\]]*"what day is it"[^\]]*\]\) Today is \$dayText\. \^stayInScope', top, flags=re.M), "the day rule")
# none of the global rules switches the dialog to another activity
for l in top.splitlines():
    if l.startswith("u:([") and "gotoReactivate" in l:
        fails.append("a global phrase rule switches the dialog: " + l.strip()[:90])
# the menus offer a suggestion and report what they did not understand to the controller (it matches it against the tiles)
for blk in ("offerMenu", "offerMenuAgain", "anythingElse"):
    b = [x for x in blocks if x.lstrip().startswith("%" + blk + " ")][0]
    check("u1:(~suggest) $pepperCmd=suggest ^stayInScope" in b, blk + " does not offer a suggestion")
    check("u1:(e:Dialog/NotUnderstood) $pepperCmd=nu ^stayInScope" in b, blk + " does not report what was not understood")
sg = [x for x in blocks if x.lstrip().startswith("%suggestAsk ")][0]
check(sg.split("\n")[0].strip().endswith("$suggestText") and "$pepperCmd=suggestyes" in sg and "$pepperCmd=suggestno" in sg, "suggestAsk")
dm = [x for x in blocks if x.lstrip().startswith("%didMean ")][0]
check(dm.split("\n")[0].strip().endswith("$didMeanText") and "$pepperCmd=dmyes" in dm and "$pepperCmd=dmno" in dm, "didMean")
for blkname, tok in (("suggestAsk", "suggestask"), ("didMean", "didmean")):
    check(re.search(r'^u:\("robotcmd %s"\) \^gotoReactivate\(%s\)' % (tok, blkname), top, flags=re.M), tok + " not handled")
# Pepper's own words in the menus and in the suggestion contain none of the words that start a suggestion (it would answer itself)
m_ = re.search(r"^concept:\(suggest\) \[([^\]]*)\]", top, flags=re.M)
sw = [(a or b).lower() for a, b in re.findall(r'"([^"]+)"|(\S+)', m_.group(1))]
for blk in ("offerMenu", "offerMenuAgain", "anythingElse", "suggestAsk", "didMean", "endSession"):
    line = " " + re.sub(r"[^a-z ]", " ", [x for x in blocks if x.lstrip().startswith("%" + blk + " ")][0].split("\n")[0].lower()) + " "
    check(not [x for x in sw if (" %s " % x) in line], "%s says a word that starts a suggestion: %r" % (blk, [x for x in sw if (" %s " % x) in line]))
# every new token Pepper says is plain, short and in the topic twice more (both name questions)
for tok in sorted(NEWTOK):
    check(len(re.findall(r'"robotcmd %s"' % tok, top)) == 3, "token %s must be in the top level and in both name questions" % tok)

# every sentence Pepper says stays short enough to listen to
for l in top.splitlines():
    m = re.search(r"\) ([A-Z][^$^]*)", l)
    if m and len(m.group(1).split()) > 32:
        fails.append("long line: " + l.strip()[:80])
if fails:
    print("DIALOG FAILED"); [print(" -", f) for f in fails]; sys.exit(1)
print("%d proposals, %d tile tokens, %d pepperCmd values checked" % (len(props), len(tiles), len(cmds)))
print("DIALOG OK")
