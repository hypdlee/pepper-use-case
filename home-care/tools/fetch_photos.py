#!/usr/bin/env python3
"""Relive Malta photos: fetch 2 to 3 free-to-reuse pictures per memory card from Wikimedia Commons.

Run this on a computer with internet access (not on Pepper), then install the project to Pepper as usual.

    python fetch_photos.py --project PATH/TO/PepperCareCompanion

What it does
  * looks up each picture on Commons and reads its licence and author from Commons itself
  * keeps only JPEG pictures that are CC0, public domain, CC BY or CC BY-SA (no NC, no ND), at least 600 px wide
  * downloads each one at 800 px width (small files) to html/photos/<card>-<n>.jpg
  * writes html/photos/credits.js (the caption shown under the picture) and html/photos/CREDITS.txt (author, licence, link)
  * adds every file in html/photos to PepperCareCompanion.pml, because Choregraphe installs only what the .pml lists
  * writes photo_preview.html next to the project so you can LOOK at every picture before you install

Your own photos: save them as html/photos/<card>-1.jpg, -2.jpg, -3.jpg (cards: festa, luzzu, ferry, pastizzi, harbour, baker,
crib, carnival, beach, balconies; about 800 px wide) and run:   python fetch_photos.py --project ... --register-only

A card with no photos keeps its drawing. Re-running replaces the fetched files. Python 3, standard library only.
"""
import argparse, html, io, json, os, re, sys, time, urllib.parse, urllib.request

API = "https://commons.wikimedia.org/w/api.php"
AGENT = "PepperCareCompanion/3.7 (care home reminiscence demo; local use)"
WANT = 3
MIN_WIDTH = 600

# File titles that were found on Commons for each card (searched, not yet checked: the script checks licence and type),
# then categories used to top up to three pictures.
MANIFEST = {
    "festa": {"files": ["Bandist.jpg", "Mobile Band Tent.jpg", "Malta - St. Paul's Bay - Malta International Fireworks Festival 12 ies.jpg"],
              "categories": ["Village feasts in Malta"]},
    "luzzu": {"files": ["Maltese fishing boat (Luzzu).jpg", "Malta Luzzu Boat.jpg", "Eyes of luzzu. Details of traditional maltese fishing boat.jpg",
                        "Maltese luzzu.JPG", "Marsaxlokk bay.jpg"],
              "categories": ["Luzzu"]},
    "ferry": {"files": ["Gozo Channel Line Ferry GHAWDEX at Mġarr, 1996 (3341465720).jpg", "Gozo Mgarr Harbour.jpg", "Malta Bus Gozo Ferry.jpg"],
              "categories": ["Mġarr Harbour"]},
    "pastizzi": {"files": ["Traditional Maltese pastry - pastizzi.jpg", "Malta Pastizzi.JPG", "Pastizzi.jpg", "Pastizzi and Kinnie (cropped).JPG"],
                 "categories": ["Pastizz"]},
    "harbour": {"files": ["Valletta, Malta's Grand Harbor.jpg", "Malta 27 Valletta.jpg", "Malta 270915 Valletta 06.jpg", "Valletta, The Fortress City.jpg"],
                "categories": ["Grand Harbour"]},
    "baker": {"files": ["Malta ftira.JPG", "MALTESE BREAD (2977855466).jpg", "MALTESE BREAD ( HOBZ TAL-MALTI ) (4347814955).jpg"],
              "categories": ["Breads of Malta"]},
    "crib": {"files": ["Christmas crib decorations.jpg", "Tavern crib.JPG"],
             "categories": ["Nativity scenes"]},
    "carnival": {"files": ["A Traditional Carnival Float in Malta, showcasing the traditions of Mexico.jpg", "Carnival mallta valletta.jpg",
                           "Costumes of Maltese Carnival.jpg", "Maltese Costumes @ Carnival.jpg"],
                 "categories": []},
    "beach": {"files": ["Malta - Mellieha - Golden Bay (Triq Ghajn Tuffieha) 02 ies.jpg"],
              "categories": ["Golden Bay (Mellieħa)", "Beaches of Malta"]},
    "balconies": {"files": [], "categories": ["Balconies in Malta", "Gallarija"]},
}


def licence_ok(name):
    n = (name or "").strip().lower()
    if not n:
        return False
    if " nc" in n or "-nc" in n or " nd" in n or "-nd" in n:
        return False
    return n.startswith("cc0") or n.startswith("public domain") or n.startswith("pd") or n.startswith("cc by")


def clean(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", text or ""))).strip()


class Commons:
    def __init__(self, api, pause):
        self.api, self.pause = api, pause

    def get(self, url):
        time.sleep(self.pause)
        req = urllib.request.Request(url, headers={"User-Agent": AGENT})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()

    def query(self, **params):
        params.update({"action": "query", "format": "json"})
        return json.loads(self.get(self.api + "?" + urllib.parse.urlencode(params)).decode("utf-8"))

    def category_files(self, cat):
        d = self.query(list="categorymembers", cmtitle="Category:" + cat, cmtype="file", cmlimit="40")
        return [m["title"] for m in d.get("query", {}).get("categorymembers", [])]

    def info(self, titles):
        """title -> dict(thumb, width, mime, licence, artist, page) for the titles Commons knows."""
        out = {}
        for i in range(0, len(titles), 40):
            chunk = ["File:" + t if not t.startswith("File:") else t for t in titles[i:i + 40]]
            d = self.query(titles="|".join(chunk), prop="imageinfo", iiprop="url|extmetadata|mime|size", iiurlwidth="800",
                           iiextmetadatafilter="LicenseShortName|Artist|UsageTerms")
            for p in d.get("query", {}).get("pages", {}).values():
                ii = (p.get("imageinfo") or [None])[0]
                if not ii:
                    continue
                md = ii.get("extmetadata", {})
                out[p["title"]] = {"thumb": ii.get("thumburl") or ii.get("url"), "width": ii.get("width", 0), "mime": ii.get("mime", ""),
                                   "licence": clean(md.get("LicenseShortName", {}).get("value", "")),
                                   "artist": clean(md.get("Artist", {}).get("value", "")) or "unknown author",
                                   "page": ii.get("descriptionurl", "")}
        return out


def register(project):
    """List every file in html/photos in the .pml (Choregraphe installs only listed files)."""
    pml = os.path.join(project, "PepperCareCompanion.pml")
    text = io.open(pml, encoding="utf-8", newline="").read()
    text = re.sub(r'[ \t]*<File name="photo-[^"]*" src="html/photos/[^"]*" />\r?\n', "", text)
    pdir = os.path.join(project, "html", "photos")
    names = sorted(os.listdir(pdir)) if os.path.isdir(pdir) else []
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = "".join('        <File name="photo-%s" src="html/photos/%s" />%s' % (re.sub(r"[^A-Za-z0-9]+", "-", f).strip("-").lower(), f, nl) for f in names)
    anchor = re.search(r'[ \t]*<File name="panel" src="html/js/panel.js" />\r?\n', text)
    assert anchor, "panel.js is not listed in the .pml: is --project the PepperCareCompanion folder?"
    text = text[:anchor.end()] + lines + text[anchor.end():]
    io.open(pml, "w", encoding="utf-8", newline="").write(text)
    return len(names)


def preview(project, credits):
    pdir = os.path.join(project, "html", "photos")
    rows = []
    for cid in MANIFEST:
        imgs = "".join('<figure><img src="%s" width="300"><figcaption>%s</figcaption></figure>' % (
            urllib.parse.quote(os.path.basename(project) + "/html/photos/" + f),
            html.escape(credits.get(f, ""))) for f in sorted(os.listdir(pdir)) if f.startswith(cid + "-") and f.endswith(".jpg"))
        rows.append("<h2>%s</h2><div style='display:flex;flex-wrap:wrap'>%s</div>" % (cid, imgs or "<p>no photo: the drawing is used</p>"))
    out = os.path.join(os.path.dirname(os.path.abspath(project)), "photo_preview.html")
    io.open(out, "w", encoding="utf-8").write("<!doctype html><meta charset=utf-8><title>Relive Malta photos</title>"
                                               "<style>figure{margin:6px;width:300px;font:12px sans-serif}img{border-radius:8px}</style>"
                                               "<h1>Check every picture, delete any you do not want, then run with --register-only</h1>" + "".join(rows))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Fetch free-to-reuse Relive Malta photos from Wikimedia Commons")
    ap.add_argument("--project", required=True, help="the PepperCareCompanion folder (the one with the .pml)")
    ap.add_argument("--register-only", action="store_true", help="do not download: only list the files already in html/photos in the .pml")
    ap.add_argument("--api", default=API, help=argparse.SUPPRESS)
    ap.add_argument("--pause", type=float, default=0.6, help="seconds between requests (be polite to Commons)")
    a = ap.parse_args(argv)
    project = os.path.abspath(a.project)
    pdir = os.path.join(project, "html", "photos")
    os.makedirs(pdir, exist_ok=True)
    cpath = os.path.join(pdir, "credits.js")
    credits = {}
    if os.path.isfile(cpath):
        try:
            credits = json.loads(re.search(r"=\s*(\{.*\})\s*;", io.open(cpath, encoding="utf-8").read(), re.S).group(1))
        except Exception:
            credits = {}
    if not a.register_only:
        for f in os.listdir(pdir):
            if re.match(r"^[a-z]+-\d\.jpg$", f):
                os.remove(os.path.join(pdir, f))
        credits, lines = {}, []
        cm = Commons(a.api, a.pause)
        for cid, spec in MANIFEST.items():
            titles = list(spec["files"])
            for cat in spec["categories"]:
                if len(titles) < WANT + 4:
                    try:
                        titles += [t for t in cm.category_files(cat) if t not in titles and t.replace("File:", "") not in titles][:12]
                    except Exception as e:
                        print("  %s: category %s failed (%s)" % (cid, cat, e))
            try:
                info = cm.info(titles)
            except Exception as e:
                print("%s: lookup failed (%s)" % (cid, e))
                continue
            got = 0
            by_norm = {k.replace("File:", "").replace("_", " "): v for k, v in info.items()}
            for t in titles:
                if got >= WANT:
                    break
                meta = by_norm.get(t.replace("File:", "").replace("_", " "))
                if not meta:
                    print("  %s: not on Commons: %s" % (cid, t))
                    continue
                if meta["mime"] != "image/jpeg":
                    print("  %s: skipped (not a JPEG): %s" % (cid, t))
                    continue
                if meta["width"] < MIN_WIDTH:
                    print("  %s: skipped (too small): %s" % (cid, t))
                    continue
                if not licence_ok(meta["licence"]):
                    print("  %s: skipped (licence %r): %s" % (cid, meta["licence"], t))
                    continue
                try:
                    data = cm.get(meta["thumb"])
                except Exception as e:
                    print("  %s: download failed (%s): %s" % (cid, e, t))
                    continue
                if data[:2] != b"\xff\xd8":
                    print("  %s: skipped (not a JPEG file): %s" % (cid, t))
                    continue
                got += 1
                fname = "%s-%d.jpg" % (cid, got)
                io.open(os.path.join(pdir, fname), "wb").write(data)
                short = meta["artist"][:40].rstrip()
                credits[fname] = "Photo: %s, %s, Wikimedia Commons" % (short, meta["licence"])
                lines.append("%s | %s | %s | %s | %s" % (fname, t.replace("File:", ""), meta["artist"], meta["licence"], meta["page"]))
                print("  %s: kept %s (%s)" % (cid, t.replace("File:", ""), meta["licence"]))
            print("%s: %d photo(s)" % (cid, got))
        io.open(cpath, "w", encoding="utf-8").write("window.MemCredits = " + json.dumps(credits, indent=1, sort_keys=True) + ";\n")
        io.open(os.path.join(pdir, "CREDITS.txt"), "w", encoding="utf-8").write(
            "Relive Malta photos from Wikimedia Commons. File | original title | author | licence | page\n" + "\n".join(lines) + "\n")
    n = register(project)
    out = preview(project, credits)
    print("Listed %d file(s) in the .pml. Look at the pictures: %s" % (n, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
