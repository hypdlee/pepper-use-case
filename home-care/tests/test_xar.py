import re, sys, subprocess, tempfile, os
import xml.etree.ElementTree as ET
PKG = "/home/claude/hack/pkg"
PY27 = "/tmp/claude-0/-home-claude/b05a1f0c-dd7e-5d57-999d-12aa7eb13b58/scratchpad/py27/bin/python2.7"
txt = open(PKG + "/behavior_1/behavior.xar", encoding="utf-8").read()
root = ET.fromstring(re.sub(r'\sxmlns="[^"]+"', '', txt, count=1)).find("Box")
fails = []
def check(cond, msg):
    if not cond: fails.append(msg)

def diagram(b):
    return b.find("./Timeline/BehaviorLayer/BehaviorKeyframe/Diagram")

def ports(b):
    ins = dict((p.get("id"), p) for p in b.findall("Input"))
    outs = dict((p.get("id"), p) for p in b.findall("Output"))
    return ins, outs

n_links = n_boxes = 0
def walk(b, path):
    global n_links, n_boxes
    d = diagram(b)
    if d is None: return
    kids = d.findall("Box")
    ids = [k.get("id") for k in kids]
    check(len(ids) == len(set(ids)), "duplicate box ids in " + path)
    byid = dict((k.get("id"), k) for k in kids)
    byid["0"] = b
    for k in kids:
        n_boxes += 1
        i, o = ports(k)
        pids = list(i) + list(o) + [p.get("id") for p in k.findall("Parameter")]
        check(len(pids) == len(set(pids)), "port/param id clash in %s/%s" % (path, k.get("name")))
        walk(k, path + "/" + k.get("name"))
    for l in d.findall("Link"):
        n_links += 1
        io_, ii, oo, oi = l.get("inputowner"), l.get("indexofinput"), l.get("outputowner"), l.get("indexofoutput")
        ok = io_ in byid and oo in byid
        check(ok, "link to missing box %s in %s" % (l.attrib, path))
        if not ok: continue
        # owner 0 is the enclosing box: its INPUTS act as sources and its OUTPUTS as sinks
        src_ports = ports(byid[oo])[0 if oo == "0" else 1]
        dst_ports = ports(byid[io_])[1 if io_ == "0" else 0]
        check(oi in src_ports, "link source port %s missing on %s (%s)" % (oi, byid[oo].get("name"), path))
        check(ii in dst_ports, "link target port %s missing on %s (%s)" % (ii, byid[io_].get("name"), path))
walk(root, "root")
check(n_links == 69 and n_boxes == 31, "unexpected map size (the mood and guitar boxes are gone: 31 boxes, 69 links): %d boxes %d links" % (n_boxes, n_links))

kids = dict((k.get("name"), k) for k in diagram(root).findall("Box"))
byid = dict((k.get("id"), k) for k in diagram(root).findall("Box"))
L = [(l.get("outputowner"), l.get("indexofoutput"), l.get("inputowner"), l.get("indexofinput")) for l in diagram(root).findall("Link")]
def has(src, so, dst, di): return (str(src), str(so), str(dst), str(di)) in L
ctl = kids["Care Controller"]
outs = dict((o.get("name"), o.get("id")) for o in ctl.findall("Output"))
ins = dict((o.get("name"), o.get("id")) for o in ctl.findall("Input"))

# every controller output that is a pulse to another box has at least one link, onStopped goes to the behaviour
for name, pid in outs.items():
    if name == "onStopped": check(has(30, pid, 0, 4), "controller onStopped not wired to behaviour onStopped")
    else: check(any(x[0] == "30" and x[1] == pid for x in L), "controller output %s is not wired" % name)
# every controller input except lifecycle ones has a source
for name, pid in ins.items():
    if name in ("onLoad",): continue
    check(any(x[2] == "30" and x[3] == pid for x in L), "controller input %s has no source" % name)
# nine exercises -> nine distinct timelines, each timeline reports back and is stopped by onStopAll
tl = []
for n in range(1, 10):
    tgt = [x[2] for x in L if x[0] == "30" and x[1] == outs["onExercise%d" % n] and x[3] == "2"]
    check(len(tgt) == 1, "onExercise%d should start exactly one timeline, got %s" % (n, tgt))
    if tgt:
        tl.append(tgt[0])
        check(has(tgt[0], 4, 30, ins["onMotionDone"]), "timeline %s does not report onMotionDone" % tgt[0])
        check(has(30, outs["onStopAll"], tgt[0], 3), "onStopAll does not stop timeline %s" % tgt[0])
check(len(set(tl)) == 9, "exercise timelines are not 9 distinct boxes")
# shows and songs
for out, boxes in (("onDance", ["Disco", "Play Sound"]), ("onSax", ["Saxophone"]), ("onSong1", ["Play Sound (1)"]), ("onSong2", ["Play Sound (2)"]), ("onSong3", ["Play Sound (3)"])):
    for bn in boxes:
        bid = kids[bn].get("id")
        check(has(30, outs[out], bid, 2), "%s does not start %s" % (out, bn))
        check(has(30, outs["onStopAll"], bid, 3), "onStopAll does not stop %s" % bn)
for bn in ("Disco", "Saxophone"):
    check(any(x[0] == kids[bn].get("id") and x[1] == "4" and x[2] == "30" and x[3] == ins["onShowDone"] for x in L), "%s does not report onShowDone" % bn)
# The guitar was removed from Music (v3.8): no box, no output, no link, no sound, nothing in the map
check("Guitar" not in kids and "Guitar Sound" not in kids, "the guitar boxes are still in the map")
check("onGuitar" not in outs and "onGuitar" not in txt and '"guitar"' not in txt and "tilej" not in txt, "the map still refers to the guitar")
check("acoustic-guitar" not in txt, "the map still plays the guitar sound")
# Football was replaced by the quiz: nothing of it may be left in the map
check("football-game" not in txt and "onFootball" not in txt, "the map still refers to the football show")
check("Football" not in kids and "Play Football Sound" not in kids, "Football boxes are still in the map")
check("onFootball" not in outs, "controller still has an onFootball output")
# Saxophone never played because it was the only show box that locked "Speakers" (the parent of Speech and Audio player):
# the dialog holds Speech while Pepper talks and the box's own sound needs Audio player, so Choregraphe did not start it.
# No box at any depth may lock Speakers or Speech; only the sound boxes lock Audio player.
def locks(b):
    for r in b.findall("Resource"):
        yield r.get("name"), r.get("timeout")
    d = diagram(b)
    if d is not None:
        for k in d.findall("Box"):
            for x in locks(k): yield x
for bn in ("Disco", "Play Sound", "Saxophone", "Play Sound (1)", "Play Sound (2)", "Play Sound (3)"):
    mine = [x for x in locks(kids[bn]) if x[0] in ("Speakers", "Speech", "Speech recognition")]
    check(not mine, "%s (or a box inside it) locks %s" % (bn, mine))
check(any(x[0] == "Audio player" for x in locks(kids["Saxophone"])), "the Saxophone sound lost its Audio player lock (test is broken)")
for bn in ("Disco", "Saxophone"):
    mine = sorted(r.get("name") for r in kids[bn].findall("Resource"))
    check(mine == ["All motors", "Standing"], "%s should lock only Standing and All motors, it locks %s" % (bn, mine))
# the saxophone sound itself must still be there, in the same place the other sounds are (Audio player lock, a file that exists)
check("epicsax.ogg" in ET.tostring(kids["Saxophone"], encoding="unicode"), "Saxophone box does not play epicsax.ogg")
check(os.path.exists(PKG + "/behavior_1/epicsax.ogg"), "epicsax.ogg is missing from the package")
# "My mood" (a camera reading of the face) is gone: no Get Expression or SayExpression or FailExpression box, no mood port, no link to them
check(not any(n in kids for n in ("Get Expression", "SayExpression", "FailExpression")), "a mood box is still in the map")
check("onMood" not in outs and "onMoodResult" not in ins and "onMoodFail" not in ins, "the controller still has a mood port")
check("ALFaceCharacteristics" not in txt and "Face analysis" not in txt, "the map still refers to face analysis")
# Relive Malta needs no box: it is the controller, the dialog and the tablet
# alert + tablet
check(has(30, outs["onAlert"], kids["CaregiverAlert"].get("id"), 2), "onAlert not wired to CaregiverAlert")
sa, tf = kids["Show App"].get("id"), kids["TabletFailed"].get("id")
check(has(0, 2, sa, 2), "behaviour does not start Show App")
check(has(sa, 4, tf, 2), "Show App failure not wired to TabletFailed")
check(has(tf, 5, sa, 2), "TabletFailed retry not wired back to Show App")
check(has(0, 2, kids["Activity"].get("id"), 2) or has(0, 1, kids["Activity"].get("id"), 2), "Activity (dialog) is not started")
check(has(0, 2, 30, 2), "behaviour does not start the Care Controller")
check(has(0, 3, 30, 3), "behaviour onStop does not stop the Care Controller")
# fixes present
check("self.isRunning = False   # Care Companion" in kids["Show App"].find("script/content").text, "Show App retry fix missing")
check("VERSION = \"4.1.1\"" in ctl.find("script/content").text, "controller is not v4.1.1")
calm = [p for p in ctl.findall("Parameter") if p.get("name") == "Calm mode"]
check(len(calm) == 1 and calm[0].get("content_type") == "0" and calm[0].get("value") == "1" and calm[0].get("default_value") == "1", "the Calm mode parameter (boolean, on by default) is missing")
check('_param("Calm mode", 1)' in ctl.find("script/content").text, "the controller does not read the Calm mode parameter")
dash = [p for p in ctl.findall("Parameter") if p.get("name") == "Dashboard URL"]
check(len(dash) == 1 and dash[0].get("content_type") == "3" and dash[0].get("value") == "" and dash[0].get("default_value") == "", "the Dashboard URL parameter (text, empty = off) is missing")
check('_param("Dashboard URL", "")' in ctl.find("script/content").text, "the controller does not read the Dashboard URL parameter")
_ids = [p.get("id") for p in ctl.findall("Parameter")]
check(len(_ids) == len(set(_ids)), "two parameters of the Care Controller share an id: %r" % _ids)

# layout: no two root boxes at the same spot (same column and less than 60px apart)
pos = [(int(k.get("x")), int(k.get("y")), k.get("name")) for k in diagram(root).findall("Box")]
for i, a in enumerate(pos):
    for b in pos[i + 1:]:
        if abs(a[0] - b[0]) < 100 and abs(a[1] - b[1]) < 60:
            fails.append("boxes overlap: %s and %s" % (a[2], b[2]))
check("uni-malta" not in txt.lower(), "uni-malta still referenced in the map")

# every python box script compiles under Python 2.7 (the robot) and the controller under 3 as well
def scripts(b):
    d = diagram(b)
    if d is None: return
    for k in d.findall("Box"):
        sc = k.find("script/content")
        if sc is not None and sc.text and k.find("script").get("language") == "4" and sc.text.strip():
            yield k.get("name"), sc.text
        for x in scripts(k): yield x
count = 0
for name, code in scripts(root):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
    r = subprocess.run([PY27, "-c", "import sys; compile(open(sys.argv[1]).read(), sys.argv[1], 'exec')", f.name], capture_output=True, text=True)
    os.unlink(f.name)
    check(r.returncode == 0, "python 2.7 cannot compile box %s: %s" % (name, r.stderr.strip()[-200:]))
    count += 1
check(count >= 19, "only %d python boxes found" % count)

if fails:
    print("XAR FAILED"); [print(" -", f) for f in fails]; sys.exit(1)
print("%d boxes, %d links, %d python scripts compiled on 2.7" % (n_boxes, n_links, count))
print("XAR OK")
