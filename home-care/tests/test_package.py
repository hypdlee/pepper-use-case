import os, re, sys
import xml.etree.ElementTree as ET
PKG = "/home/claude/hack/pkg"
fails = []
def check(c, m):
    if not c: fails.append(m)
pml = ET.parse(PKG + "/PepperCareCompanion.pml").getroot()
check(pml.get("name") == "Pepper Care Companion", "pml name")
files = [(f.get("name"), f.get("src")) for f in pml.find("Resources")]
names = [n for n, _ in files]
check(len(names) == len(set(names)), "duplicate resource names in the pml")
for n, src in files:
    check(os.path.isfile(os.path.join(PKG, src)), "pml lists a missing file: " + src)
listed = set(src for _, src in files)
for top in ("html", "music", "behavior_1"):
    for dp, dn, fn in os.walk(os.path.join(PKG, top)):
        for f in fn:
            rel = os.path.relpath(os.path.join(dp, f), PKG)
            if rel == "behavior_1/behavior.xar": continue
            check(rel in listed, "file not listed in the pml: " + rel)
for bd in pml.find("BehaviorDescriptions"):
    check(os.path.isfile(os.path.join(PKG, bd.get("src"), bd.get("xar"))), "behaviour file missing")
for d in pml.find("Dialogs"): check(os.path.isfile(os.path.join(PKG, d.get("src"))), "dialog file missing")
for t in pml.find("Topics"): check(os.path.isfile(os.path.join(PKG, t.get("src"))), "topic file missing")
man = open(PKG + "/manifest.xml").read()
check('uuid="pepper-care-companion"' in man and 'version="4.1.1"' in man, "manifest uuid/version")
ET.fromstring(man)
# html pages only reference local files that exist
for f in os.listdir(PKG + "/html"):
    if f.endswith(".html"):
        t = open(os.path.join(PKG, "html", f), encoding="utf-8").read()
        for ref in re.findall(r'(?:src|href)="([^"#?]+)', t):
            if re.match(r"^(https?:|/|mailto:|data:)", ref): check(False, "%s uses a non-local reference %s" % (f, ref)); continue
            check(os.path.isfile(os.path.join(PKG, "html", ref)), "%s references missing %s" % (f, ref))
css = open(PKG + "/html/css/main.css").read()
check("url(" not in css, "css references a file")
# every sound the map plays exists
xar = open(PKG + "/behavior_1/behavior.xar", encoding="utf-8").read()
for ref in set(re.findall(r'value="(/\.\./music/[^"]+|/[\w.-]+\.(?:ogg|pmt))"', xar)):
    p = os.path.normpath(os.path.join(PKG, "behavior_1", ref.lstrip("/")))
    check(os.path.isfile(p) or os.path.isfile(os.path.join(PKG, "behavior_1", ref.lstrip("/"))), "map references a missing file: " + ref)
for stale in ("uni-malta", "University of Malta", "test-148bbb", "FYPPepper"):
    for dp, dn, fn in os.walk(PKG):
        for f in fn:
            if f.endswith((".png", ".mp3", ".ogg", ".pmt")): continue
            t = open(os.path.join(dp, f), encoding="utf-8", errors="ignore").read()
            check(stale.lower() not in t.lower(), "%s still appears in %s" % (stale, f))
# the football show is gone: no audio file, no resource entry
check(not os.path.exists(PKG + "/music/football-game.mp3") and "football-game" not in open(PKG + "/PepperCareCompanion.pml", encoding="utf-8").read(), "football audio is still packaged")
# the controller inside the map equals the file we tested
src = open("/home/claude/hack/src/care_controller.py", encoding="utf-8").read()
check(src in xar, "the Care Controller in behavior.xar differs from src/care_controller.py")
# the shipped Relive Malta photos: known card, numbered 1 to 3 without gaps, real JPEG, small, and every one has a caption
import json
pdir = PKG + "/html/photos"
if os.path.isdir(pdir):
    cards = ("festa", "luzzu", "ferry", "pastizzi", "harbour", "baker", "crib", "carnival", "beach", "balconies")
    cap = json.loads(re.search(r"=\s*(\{.*\})\s*;", open(pdir + "/credits.js", encoding="utf-8").read(), re.S).group(1))
    jp = sorted(f for f in os.listdir(pdir) if f.endswith(".jpg"))
    if PKG == "/home/claude/hack/pkg":           # the shipped project: every photo has its caption (own photos added later may have none)
        check(jp and set(cap) == set(jp), "credits.js must have a caption for every shipped photo")
    for f in jp:
        m = re.match(r"^([a-z]+)-([123])\.jpg$", f)
        check(m is not None and m.group(1) in cards, "bad photo name " + f)
        data = open(os.path.join(pdir, f), "rb").read()
        check(data[:2] == b"\xff\xd8" and len(data) < 300 * 1024, "photo is not a small JPEG: " + f)
    for c in cards:
        ns = sorted(int(f.split("-")[1][0]) for f in jp if f.startswith(c + "-"))
        check(ns == list(range(1, len(ns) + 1)), "photo numbers for %s have a gap: %s" % (c, ns))
    check(os.path.isfile(pdir + "/CREDITS.txt"), "CREDITS.txt missing")
if fails:
    print("PACKAGE FAILED"); [print(" -", f) for f in fails]; sys.exit(1)
print("%d resources listed, all present" % len(files)); print("PACKAGE OK")
