# Checks the Choregraphe project as a whole: structure, dialog against controller, content, clips, wording rules.
import os, re, io, json, subprocess, sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "ChampionshipHost")
FAILS = []
def check(c, m):
    if not c:
        FAILS.append(m); print("FAIL:", m)

src = io.open(os.path.join(ROOT, "src", "host_controller.py"), encoding="utf-8").read()
version = re.search(r'^VERSION = "([0-9.]+)"', src, re.M).group(1)
check(all(ord(c) < 128 for c in src), "controller source must be plain ASCII (Python 2.7 on the robot)")
check(".post" not in src, "the controller must not use .post: services from session.service() do not have it (Pepper stays silent)")
check("_async=True" in src, "speech must be started with _async=True")

# behaviour file
xar_text = io.open(os.path.join(PKG, "behavior_1", "behavior.xar"), encoding="utf-8").read()
ns = {"c": "http://www.aldebaran-robotics.com/schema/choregraphe/project.xsd"}
root = ET.fromstring(xar_text.encode("utf-8"))
diagram = root.find(".//c:Diagram", ns)
boxes = {int(b.get("id")): b for b in diagram.findall("c:Box", ns)}
check(sorted(boxes) == [2, 4], "boxes: %r (no Dialog box: the controller owns the topic)" % sorted(boxes))
check(boxes[4].get("name") == "Host Controller" and boxes[2].get("name") == "Show App", "box names")
check("dialogFile" not in xar_text, "a Dialog box is back in the behaviour")
code = boxes[4].find("c:script/c:content", ns).text
check(code == src, "the controller inside behavior.xar is not src/host_controller.py: run build.py")
def ports(b):
    ins = {int(i.get("id")) for i in b.findall("c:Input", ns)}
    outs = {int(o.get("id")) for o in b.findall("c:Output", ns)}
    return ins, outs
rootIns = {int(i.get("id")) for i in root.find("c:Box", ns).findall("c:Input", ns)}
rootOuts = {int(o.get("id")) for o in root.find("c:Box", ns).findall("c:Output", ns)}
links = [(int(l.get("inputowner")), int(l.get("indexofinput")), int(l.get("outputowner")), int(l.get("indexofoutput"))) for l in diagram.findall("c:Link", ns)]
for io_, ii, oo, oi in links:
    okin = (oi in rootIns) if oo == 0 else (oi in ports(boxes[oo])[1])
    okout = (ii in rootOuts) if io_ == 0 else (ii in ports(boxes[io_])[0])
    check(okin and okout, "bad link %r" % ((io_, ii, oo, oi),))
for b in (2, 4):
    check((b, 2, 0, 2) in links, "box %d is not started with the behaviour" % b)
check((0, 4, 4, 4) in links and (4, 3, 0, 3) in links, "controller stop / stopped links")
params = {p.get("name"): p for p in boxes[4].findall("c:Parameter", ns)}
VER = re.search(r'^VERSION = "([0-9.]+)"', src, re.M).group(1)
show = boxes[2].find("c:script/c:content", ns).text or ""
check("tabletService.cleanWebview()" in show and show.index("cleanWebview") < show.index("loadApplication"), "Show App must clear the tablet cache before loading the app")
idx = io.open(os.path.join(PKG, "html", "index.html"), encoding="utf-8").read()
for f in ("js/bridge.js", "js/host.js", "css/host.css"):
    check(('%s?v=%s"' % (f, VER)) in idx, "index.html must request %s with the version, so the tablet cannot use an old copy" % f)
check(set(params) == {"Staff PIN", "Match calls", "Greet visitors", "Intro when idle (minutes)", "Announce match starts", "Intro at start"}, "parameters: %r" % sorted(params))
check(len({p.get("id") for p in params.values()} | {"1", "2", "3", "4"}) == 4 + len(params), "parameter ids clash with the box ports")
for name in params:
    check(('"%s"' % name) in src, "parameter %s is not read by the controller" % name)

# manifest and project file
man = ET.parse(os.path.join(PKG, "manifest.xml")).getroot()
teams = [l.split(",") for l in io.open(os.path.join(PKG, "html", "data", "teams.csv"), encoding="utf-8").read().splitlines() if l and not l.startswith("#")][1:]
check(len([r for r in teams if r[2] == "arena"]) == 8 and len([r for r in teams if r[2] == "arm"]) == 5, "teams.csv should hold the 8 Arena and 5 Robot Arm teams from the organisers' sheet")
check(man.find("contents/dialogContent") is None, "manifest must not declare the topic (the system would load it too: topic already loaded)")
check(man.get("version") == version and man.get("uuid") == "ieee-championship-host", "manifest version/uuid")
pml = ET.parse(os.path.join(PKG, "ChampionshipHost.pml")).getroot()
listed = [f.get("src") for f in pml.iter("File")]
check(len(listed) == len(set(listed)) and len({f.get("name") for f in pml.iter("File")}) == len(listed), "duplicate resources in the .pml")
on_disk = []
for r, _, names in os.walk(PKG):
    for n in names:
        rel = os.path.relpath(os.path.join(r, n), PKG).replace("\\", "/")
        if rel not in ("manifest.xml", "ChampionshipHost.pml", "behavior_1/behavior.xar"):
            on_disk.append(rel)
check(sorted(listed) == sorted(on_disk), "the .pml does not list exactly the files on disk: run build.py")
check(not any(n.endswith((".pyc", ".DS_Store")) or "__pycache__" in n for n in on_disk), "junk files in the package")

# dialog against controller and content
top = io.open(os.path.join(PKG, "Host", "Host_enu.top"), encoding="utf-8").read()
content = json.load(io.open(os.path.join(PKG, "html", "data", "content.json"), encoding="utf-8"))
check("Host/Host_enu.top" in listed and not os.path.exists(os.path.join(PKG, "Host", "Host.dlg")), "topic file listing")
check(top.startswith("topic: ~host()") and "language: enu" in top and "dynamic: teamnames" in top, "topic header")
cmds = set(re.findall(r"\$hostCmd=(\w+)", top))
handled = set(re.findall(r'cmd == "(\w+)"', src)) | set(w for t in re.findall(r'cmd in \(([^)]*)\)', src) for w in re.findall(r'"(\w+)"', t))
check(cmds and cmds <= handled, "dialog commands the controller ignores: %r" % sorted(cmds - handled))
games = {g["id"] for g in content["games"]}
check(set(re.findall(r"\$hostGame=(\w+)", top)) == games, "dialog games vs content.json: %r" % (set(re.findall(r"\$hostGame=(\w+)", top)) ^ games))
for i in re.findall(r"\$hostInfo=(\d+)", top):
    check(int(i) < len(content["event"]["info"]), "hostInfo %s has no answer" % i)
pong = re.search(r'^PONG = "(\w+)"', src, re.M).group(1)
check(('u:("robotcmd ping") $hostPong=%s' % pong) in top, "ping rule does not match the controller")
concepts = set(re.findall(r"^concept:\((\w+)\)", top, re.M))
used = set(re.findall(r"~(\w+)", top)) - {"host", "teamnames"}
check(used <= concepts, "concepts used but not defined: %r" % sorted(used - concepts))
for n, line in enumerate(top.splitlines(), 1):
    if line.startswith(("u:", "concept:")):
        check(line.count("[") == line.count("]") and line.count("{") == line.count("}") and line.count("(") == line.count(")") and line.count('"') % 2 == 0,
              "unbalanced brackets or quotes on line %d" % n)
check(len(re.findall(r"^u:", top, re.M)) == len(set(re.findall(r"^u:\(([^)]*)\)", top, re.M))), "duplicate rule triggers")

# this is a robot competition, not a care setting: no care or medical wording in what Pepper hears, says or shows
care = ["first aid", "hurt", "sick", "injur", "nurse", "medic", "doctor", "patient", "dizzy", "caregiver", "carer", "care home", "emergency"]
for rel in ("Host/Host_enu.top", "html/data/content.json", "html/js/host.js", "html/index.html"):
    t = io.open(os.path.join(PKG, rel), encoding="utf-8").read().lower()
    check(not [w for w in care if w in t], "care or medical wording in %s: %r" % (rel, [w for w in care if w in t]))
low = src.lower()
check(not [w for w in care if w in low] and "care companion" not in low, "care or medical wording in the controller: %r" % [w for w in care if w in low])

# clips
for g in content["games"]:
    mp4 = os.path.join(PKG, "html", "clips", g["clip"] + ".mp4")
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,profile,width,height", "-of", "json", mp4])
    streams = json.loads(out.decode())["streams"]
    check(len(streams) == 1 and streams[0]["codec_type"] == "video" and streams[0]["codec_name"] == "h264" and streams[0]["profile"] == "Constrained Baseline"
          and (streams[0]["width"], streams[0]["height"]) == (1280, 720), "clip format %s: %r" % (g["clip"], streams))
    check(os.path.getsize(mp4) < 600 * 1024, "clip too big: %s" % g["clip"])

# wording: neutral, no em-dashes, no restricted names
restricted = [("hea" + "rts"), ("focus" + " group")]
texts = []
for base in (PKG, os.path.join(ROOT, "docs"), os.path.join(ROOT, "src"), os.path.join(ROOT, "tools")):
    for r, _, names in os.walk(base):
        for n in names:
            if n.endswith((".html", ".js", ".css", ".json", ".csv", ".top", ".dlg", ".py", ".md", ".txt", ".xml", ".pml", ".xar")):
                texts.append(os.path.join(r, n))
for p in texts:
    t = io.open(p, encoding="utf-8").read()
    rel = os.path.relpath(p, ROOT)
    check(u"\u2014" not in t, "em-dash in %s" % rel)
    if rel.replace("\\", "/") == "ChampionshipHost/html/data/teams.csv":
        rows = [l for l in t.splitlines() if l and not l.startswith("#")]
        check(all(l.count(",") == 3 for l in rows), "teams.csv: every row needs 4 columns")
    elif all(r[0] in t for r in teams):
        pass        # a full, equal list of every team (the docs) is neutral
    else:
        check("genesis" not in t.lower(), "a team name appears in %s (the host must stay neutral: only teams.csv or a full list of every team)" % rel)
    for w in restricted:
        check(w not in t.lower(), "restricted word in %s" % rel)


# ---- Pepper's tablet browser is old (Android 5 WebView, about Chrome 37 to 44). Seen on the robot: CSS variables were
#      ignored, so the purple and yellow vanished. Refuse every feature that browser does not have.
css_text = io.open(os.path.join(PKG, "html", "css", "host.css"), encoding="utf-8").read()
css_code = re.sub(r"/\*.*?\*/", "", css_text, flags=re.S)
for bad, why in ((r"var\(", "CSS variables"), (r"(^|[;{\s])--[a-z]", "CSS custom properties"), (r"(^|[;{\s])(row-|column-)?gap\s*:", "flex/grid gap"),
                 (r"display\s*:\s*(inline-)?grid", "CSS grid"), (r"position\s*:\s*sticky", "sticky"), (r"(^|[;{\s])inset\s*:", "inset"),
                 (r"aspect-ratio", "aspect-ratio"), (r"\b(clamp|min|max)\(", "clamp/min/max"), (r":(is|where|has)\(", ":is/:where/:has"),
                 (r"@supports", "@supports"), (r"backdrop-filter", "backdrop-filter"), (r"\bfit-content\b", "fit-content")):
    check(not re.search(bad, css_code, re.M), "host.css uses %s, which Pepper's tablet browser does not have" % why)
check(css_code.count("@keyframes") == css_code.count("@-webkit-keyframes"), "every @keyframes needs a @-webkit-keyframes twin")
for prop in ("animation", "transform"):
    n = len(re.findall(r"(^|[;{\s])%s\s*:" % prop, css_code, re.M)); nw = len(re.findall(r"-webkit-%s\s*:" % prop, css_code))
    check(nw >= n, "every %s needs a -webkit-%s twin (%d vs %d)" % (prop, prop, n, nw))
for name in ("host.js", "bridge.js"):
    js = io.open(os.path.join(PKG, "html", "js", name), encoding="utf-8").read()
    js_code = re.sub(r"//[^\n]*|/\*.*?\*/", "", js, flags=re.S)
    for bad in (r"\.includes\(", r"\.startsWith\(", r"\.endsWith\(", r"Object\.assign", r"\bfetch\(", r"\.closest\(", r"Array\.from", r"\.append\(",
                r"\.prepend\(", r"padStart", r"padEnd", r"Object\.values", r"Object\.entries", r"\.find\(", r"findIndex", r"\.repeat\(", r"\.fill\(",
                r"=>", r"\blet\s", r"\bconst\s", r"`", r"\.replaceAll\(", r"\.flat\(", r"IntersectionObserver", r"\.dataset\b", r"\bclass\s+[A-Z]",
                r"\.catch\(", r"\.finally\(", r"async\s", r"\bawait\s", r"\.toggle\([^,)]*,"):
        check(not re.search(bad, js_code), "%s uses %s, which Pepper's tablet browser does not have" % (name, bad))

print("PACKAGE OK" if not FAILS else "%d FAILURES" % len(FAILS))
sys.exit(1 if FAILS else 0)
