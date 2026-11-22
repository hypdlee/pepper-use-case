"""Removes the maze walls from the Climate CHAOS clip (the arena has no maze; organisers' decision, Nov 2026).

Usage:  python3 tools/remove_maze.py <in.mp4> <out.mp4> [<debug.png>]

The camera does not move, so the walls are found once on the median frame: thin, straight, dark slate-grey bars.
Round things (sinkholes, tower columns), the text, the cars, the safe zone and the floods are kept. The walls are
painted out of a clean background; on every frame only wall pixels that the robot is not covering are replaced,
so nothing flickers and the robot stays exactly as it was.
"""
import sys, os, subprocess, cv2, numpy as np

src, dst = sys.argv[1], sys.argv[2]
dbg = sys.argv[3] if len(sys.argv) > 3 else None

cap = cv2.VideoCapture(src)
fps = cap.get(cv2.CAP_PROP_FPS) or 30
frames = []
while True:
    ok, f = cap.read()
    if not ok:
        break
    frames.append(f)
cap.release()
med = np.median(np.stack(frames[::3]), axis=0).astype(np.uint8)

def wall_mask(img):
    """Walls are long straight runs of slate grey. Letters are too short to be a run, and the round sinkholes and
    tower columns are thick blobs, so both are left alone. Returns (area to clean, pixels to keep as they are)."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    s, v = hsv[..., 1].astype(int), hsv[..., 2].astype(int)
    dark = ((v <= 135) & (s <= 100)).astype(np.uint8) * 255
    lines = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((1, 31), np.uint8)) | cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((31, 1), np.uint8))
    blobs = cv2.dilate(cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((17, 17), np.uint8)), np.ones((7, 7), np.uint8))
    lines[blobs > 0] = 0
    area = cv2.dilate(lines, np.ones((11, 11), np.uint8))                       # the wall and its soft shadow
    keep = ((dark > 0) & (cv2.dilate(lines, np.ones((3, 3), np.uint8)) == 0)) | (blobs > 0)   # letters, columns, sinkholes
    keep = cv2.dilate(keep.astype(np.uint8) * 255, np.ones((2, 2), np.uint8)) > 0
    return area, keep

walls, keep = wall_mask(med)
clean = cv2.inpaint(med, walls, 5, cv2.INPAINT_TELEA)
clean[keep] = med[keep]
walls[keep] = 0

# ---- redraw what sits next to the walls crisply, in its exact place: wiping the walls nicks these
from PIL import Image, ImageDraw, ImageFont
FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ChampionshipHost", "html", "fonts", "open-sans-latin-%d-normal.woff")
ARENA = (400, 120, 880, 600)                                 # the arena floor, x0, y0, x1, y1
SS = 4                                                       # draw 4x larger, then shrink: smooth edges

def find_text(text, size, weight, x0, y0, x1, y1):
    """Where the label really is in the median frame (template matching), so the redraw lands exactly on it."""
    f = ImageFont.truetype(FONT % weight, size)
    l, t, r, b = f.getbbox(text)
    tpl = Image.new("L", (r + 4, b + 4), 255); ImageDraw.Draw(tpl).text((2, 2), text, font=f, fill=0)
    tpl = np.array(tpl)
    reg = cv2.cvtColor(med[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    res = cv2.matchTemplate(reg, tpl, cv2.TM_CCOEFF_NORMED)
    _, score, _, (mx, my) = cv2.minMaxLoc(res)
    return x0 + mx + 2, y0 + my + 2, f, score

def paint(img_bgr):
    im = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    W, H = im.size
    big = im.resize((W * SS, H * SS), Image.NEAREST)
    d = ImageDraw.Draw(big)
    floor, ink = (229, 230, 220), (36, 40, 42)
    for cx, cy in ((856, 384), (806, 478), (712, 478)):                     # sinkholes: wipe the wall stubs, draw the disc
        d.rectangle([(cx - 30) * SS, (cy - 30) * SS, min(cx + 30, ARENA[2] - 1) * SS, (cy + 30) * SS], fill=floor)
        d.ellipse([(cx - 22) * SS, (cy - 22) * SS, (cx + 22) * SS, (cy + 22) * SS], fill=(16, 12, 2))
    d.rectangle([515 * SS, 157 * SS, 620 * SS, 164 * SS], fill=floor)                          # wall along Tower B's top edge
    d.rectangle([515 * SS, 165 * SS, 620 * SS, 170 * SS], fill=(200, 201, 191))
    sk = ImageFont.truetype(FONT % 700, 8 * SS)
    for xs, ys in (((513, 550, 587, 621), (164, 218)), ((753, 807, 861), (212, 266)), ((561, 588, 615, 642, 669), (308, 362))):
        for x in xs:                                                         # tower columns
            for y in ys:
                d.ellipse([(x - 4.5) * SS, (y - 4.5) * SS, (x + 4.5) * SS, (y + 4.5) * SS], fill=(34, 54, 74))
    d.rectangle([400 * SS, 504 * SS, 496 * SS, 600 * SS], fill=(184, 218, 192), outline=(81, 180, 118), width=2 * SS)   # safe zone
    for cx, cy in ((856, 384), (806, 478), (712, 478)):
        l, t, r, b = sk.getbbox("SINKHOLE"); d.text((cx * SS - (r - l) / 2.0 - l, cy * SS - (b - t) / 2.0 - t), "SINKHOLE", font=sk, fill=(176, 170, 162))
    im = big.resize((W, H), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    for text, size, weight, box, col in (("Tower B \u00b7 4 col \u00b7 +100", 13, 700, (490, 125, 660, 165), ink),
                                         ("Tower A \u00b7 5 col \u00b7 +50", 13, 700, (540, 270, 700, 310), ink),
                                         ("Tower C \u00b7 3 col \u00b7 +150", 13, 700, (730, 175, 900, 215), ink)):
        x, y, f, sc = find_text(text, size, weight, *box)
        l, t, r, b = f.getbbox(text)
        for xx in range(x + l - 2, x + r + 3):                                # clear behind the label: flood blue or floor
            for yy in range(y + t - 2, y + b + 3):
                im.putpixel((xx, yy), (126, 159, 194) if (496 <= xx <= 592 and yy <= 160) else floor)
        d.text((x, y), text, font=f, fill=col)
        print("label %-24s at %d,%d (match %.2f)" % (text, x, y, sc))
    f = ImageFont.truetype(FONT % 600, 11)
    d.text((408, 508), "SAFE ZONE", font=f, fill=(81, 180, 118))
    return cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)

def smooth_floor(img):
    """Bare floor inside the arena is replaced by a smooth version of itself: no ghost of a wall or its shadow is left.
    Towers, labels, sinkholes, cars, floods and the safe zone are not bare floor, so they stay sharp."""
    x0, y0, x1, y1 = ARENA
    reg = img[y0:y1, x0:x1].copy()
    hsv = cv2.cvtColor(reg, cv2.COLOR_BGR2HSV)
    bare = (hsv[..., 2] >= 205) & (hsv[..., 1] <= 40)
    bare = cv2.erode(bare.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0       # stay off the edges of things
    fill = reg.copy(); fill[~bare] = (220, 230, 229)                                # floor colour under the elements
    soft = cv2.blur(cv2.medianBlur(fill, 21), (41, 41))
    reg[bare] = soft[bare]
    out = img.copy(); out[y0:y1, x0:x1] = reg
    return out

clean = smooth_floor(paint(clean))
walls = ((cv2.absdiff(clean, med).max(axis=2) > 1) | (walls > 0)).astype(np.uint8) * 255   # everything that changed

if dbg:
    vis = med.copy(); vis[walls > 0] = (0, 0, 255)
    cv2.imwrite(dbg, np.hstack([vis, clean]))

h, w = med.shape[:2]
ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "%dx%d" % (w, h), "-r", str(fps), "-i", "-",
                       "-c:v", "libx264", "-preset", "slow", "-crf", "24", "-pix_fmt", "yuv420p", "-profile:v", "baseline", "-level", "3.1",
                       "-movflags", "+faststart", "-an", dst], stdin=subprocess.PIPE)
cleanf, medf = clean.astype(np.int16), med.astype(np.int16)
for f in frames:
    # the robot: its exact outline (largest teal shape, convex hull) keeps the original pixels
    hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
    teal = ((hsv[..., 0] >= 78) & (hsv[..., 0] <= 100) & (hsv[..., 1] >= 70) & (hsv[..., 2] >= 110)).astype(np.uint8)
    robot = np.zeros(teal.shape, np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(teal)
    if n > 1:
        k = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        if st[k, cv2.CC_STAT_AREA] > 400:
            pts = cv2.findNonZero((lab == k).astype(np.uint8))
            cv2.fillConvexPoly(robot, cv2.convexHull(pts), 1)
            robot = cv2.dilate(robot, np.ones((5, 5), np.uint8))
    # everywhere else in the cleaned area: clean background + what changed in this frame (pulse, fire glow, shadow);
    # the walls are in every frame, so they cancel out
    out = np.clip(cleanf + (f.astype(np.int16) - medf), 0, 255).astype(np.uint8)
    rep = (walls > 0) & (robot == 0)
    res = f.copy(); res[rep] = out[rep]
    ff.stdin.write(res.tobytes())
ff.stdin.close(); ff.wait()
print("walls removed: %d px of %d, %d frames" % (int((walls > 0).sum()), w * h, len(frames)))
