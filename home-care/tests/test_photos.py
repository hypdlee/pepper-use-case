# The photo fetcher against a mock Commons: licence and type filters, file names, credits, pml registration, idempotence.
import http.server, json, os, re, shutil, subprocess, sys, tempfile, threading, urllib.parse
ROOT = "/home/claude/hack"
sys.path.insert(0, ROOT + "/tools")
import fetch_photos as fp
fails = []
def check(c, m):
    if not c: fails.append(m)

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 200 + b"\xff\xd9"
PORT = []
FILES = {   # title -> (mime, width, licence, artist html)
    "Malta Pastizzi.JPG": ("image/jpeg", 2000, "CC BY-SA 4.0", '<a href="x">Jane <b>Doe</b></a>'),
    "Pastizzi.jpg": ("image/jpeg", 2000, "CC BY-NC 2.0", "Somebody"),          # NC: rejected
    "Traditional Maltese pastry - pastizzi.jpg": ("image/jpeg", 2000, "Public domain", ""),
    "Pastizzi and Kinnie (cropped).JPG": ("image/png", 2000, "CC0", "Png Person"),   # not a JPEG: rejected
    "Cat Pastizz A.jpg": ("image/jpeg", 300, "CC BY 3.0", "Tiny"),               # too small: rejected
    "Cat Pastizz B.jpg": ("image/jpeg", 1600, "CC BY-ND 2.0", "NoDerivs"),      # ND: rejected
    "Cat Pastizz C.jpg": ("image/jpeg", 1600, "CC BY 4.0", "Cee"),
    "Cat Pastizz D.jpg": ("image/jpeg", 1600, "CC0", "Dee"),                    # a fourth good one: only three are kept
}
CATS = {"Pastizz": list(FILES)[4:]}

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        if u.path.startswith("/img/"):
            self.send_response(200); self.send_header("Content-Type", "image/jpeg"); self.end_headers(); self.wfile.write(JPEG); return
        out = {"query": {}}
        if q.get("list") == ["categorymembers"]:
            cat = q["cmtitle"][0].replace("Category:", "")
            out["query"]["categorymembers"] = [{"title": "File:" + t} for t in CATS.get(cat, [])]
        else:
            pages = {}
            for i, t in enumerate(q["titles"][0].split("|")):
                name = t.replace("File:", "")
                if name in FILES:
                    mime, w, lic, art = FILES[name]
                    pages[str(i)] = {"title": t, "imageinfo": [{"thumburl": "http://127.0.0.1:%d/img/%d" % (PORT[0], i), "url": "x", "width": w, "mime": mime,
                                     "descriptionurl": "http://example.invalid/" + name,
                                     "extmetadata": {"LicenseShortName": {"value": lic}, "Artist": {"value": art}}}]}
                else:
                    pages[str(-i - 1)] = {"title": t, "missing": ""}
            out["query"]["pages"] = pages
        body = json.dumps(out).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)

srv = http.server.HTTPServer(("127.0.0.1", 0), H)
PORT.append(srv.server_address[1])
threading.Thread(target=srv.serve_forever, daemon=True).start()

# licence rules on their own
for ok in ("CC BY-SA 4.0", "CC BY 2.0", "CC0", "Public domain", "PD-old"):
    check(fp.licence_ok(ok), "licence should be accepted: " + ok)
for bad in ("CC BY-NC 2.0", "CC BY-ND 2.0", "CC BY-NC-SA 3.0", "GFDL", "", "All rights reserved"):
    check(not fp.licence_ok(bad), "licence should be refused: %r" % bad)

tmp = tempfile.mkdtemp()
proj = os.path.join(tmp, "PepperCareCompanion")
shutil.copytree(ROOT + "/pkg", proj)
fp.MANIFEST = {"pastizzi": {"files": ["Malta Pastizzi.JPG", "Pastizzi.jpg", "Traditional Maltese pastry - pastizzi.jpg",
                                      "Pastizzi and Kinnie (cropped).JPG", "Not On Commons.jpg"], "categories": ["Pastizz"]},
               "luzzu": {"files": [], "categories": []}}
api = "http://127.0.0.1:%d/w/api.php" % PORT[0]
for run in (1, 2):                                             # twice: the second run must give the same result
    rc = fp.main(["--project", proj, "--api", api, "--pause", "0"])
    check(rc == 0, "exit code")
    pdir = proj + "/html/photos"
    names = sorted(os.listdir(pdir))
    check(names == ["CREDITS.txt", "credits.js", "pastizzi-1.jpg", "pastizzi-2.jpg", "pastizzi-3.jpg"], "files after run %d: %s" % (run, names))
    cr = json.loads(re.search(r"=\s*(\{.*\})\s*;", open(pdir + "/credits.js").read(), re.S).group(1))
    check(cr.get("pastizzi-1.jpg") == "Photo: Jane Doe, CC BY-SA 4.0, Wikimedia Commons", "credit text: %r" % cr.get("pastizzi-1.jpg"))
    check("unknown author" in cr.get("pastizzi-2.jpg", ""), "a missing author is said so")
    txt = open(pdir + "/CREDITS.txt").read()
    check("Pastizzi.jpg" not in txt.replace("Malta Pastizzi.JPG", ""), "the NC picture was kept")
    check("NoDerivs" not in txt and "Tiny" not in txt and "Png Person" not in txt, "a refused picture was kept")
    check(all(open(pdir + "/pastizzi-%d.jpg" % i, "rb").read()[:2] == b"\xff\xd8" for i in (1, 2, 3)), "not JPEG data")
    pml = open(proj + "/PepperCareCompanion.pml", encoding="utf-8").read()
    for f in names:
        check(pml.count('src="html/photos/%s"' % f) == 1, "pml entry count for " + f)
    check(len(re.findall(r'name="photo-', pml)) == 5, "pml photo entries: %d" % len(re.findall(r'name="photo-', pml)))
    ids = re.findall(r'<File name="([^"]+)"', pml)
    check(len(ids) == len(set(ids)), "duplicate pml names")
check(os.path.isfile(tmp + "/photo_preview.html"), "no preview page")
# register-only after the user removed one picture and added their own
os.remove(proj + "/html/photos/pastizzi-3.jpg")
open(proj + "/html/photos/luzzu-1.jpg", "wb").write(JPEG)
fp.main(["--project", proj, "--register-only"])
pml = open(proj + "/PepperCareCompanion.pml", encoding="utf-8").read()
check("pastizzi-3.jpg" not in pml and 'src="html/photos/luzzu-1.jpg"' in pml, "register-only did not follow the folder")
# the package test must be happy with the registered photos (every file under html/ listed)
res = subprocess.run(["python3", "-c", open(ROOT + "/tests/test_package.py").read().replace('PKG = "/home/claude/hack/pkg"', 'PKG = %r' % proj)],
                     capture_output=True, text=True)
check("PACKAGE OK" in res.stdout, "test_package on the project with photos: " + (res.stdout + res.stderr)[-300:])
shutil.rmtree(tmp)
if fails:
    print("PHOTOS FAIL"); [print(" -", f) for f in fails]; sys.exit(1)
print("photo fetcher checks passed"); print("PHOTOS OK")
