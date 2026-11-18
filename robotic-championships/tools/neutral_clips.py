"""Cut neutral, per-game clips from the two simulator videos.

Crops away the header, the side panels and the captions (they name one team and show its robot design),
removes the small team-name labels that follow the two robots in the arena, and writes one short muted
H.264 clip per game for Pepper's tablet. Pepper narrates the rules itself, from the rulebook.
"""
import sys, os, subprocess, cv2, numpy as np

GAMES_SRC, ARMS_SRC, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)

# (name, source, start s, end s, crop x, y, w, h, remove labels)
CUTS = [
    ("arena-time-of-fall",     GAMES_SRC, 0.9, 7.25, 287, 201, 626, 627, True),
    ("arena-climate-chaos",    GAMES_SRC, 7.4, 15.3, 287, 201, 626, 627, True),
    ("arena-weight-in-line",   GAMES_SRC, 15.5, 23.35, 287, 201, 626, 627, True),
    ("arena-hanging-hazard",   GAMES_SRC, 23.5, 29.9, 287, 201, 626, 627, True),
    ("arm-colour-sort",        ARMS_SRC, 6.2, 12.15, 35, 212, 831, 586, False),
    ("arm-shape-sort",         ARMS_SRC, 12.3, 18.2, 35, 212, 831, 586, False),
    ("arm-dynamic-sort",       ARMS_SRC, 18.3, 25.3, 35, 212, 831, 586, False),
    ("arm-pouring",            ARMS_SRC, 25.4, 32.35, 35, 212, 831, 586, False),
    ("arm-folding",            ARMS_SRC, 32.5, 39.35, 35, 212, 831, 586, False),
    ("arm-tower-duel",         ARMS_SRC, 39.5, 47.5, 35, 212, 831, 586, False),
]

def hue_mask(hsv, lo, hi, smin=60, vmin=90):
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    return ((h >= lo) & (h <= hi) & (s >= smin) & (v >= vmin)).astype(np.uint8) * 255

def strip_labels(img):
    """Find short lines of coloured text (the robot name labels) and paint them out."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    col = hue_mask(hsv, 70, 100) | hue_mask(hsv, 8, 28)     # teal label and orange label (OpenCV hue is 0..180)
    body = cv2.dilate(cv2.morphologyEx(col, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8)), np.ones((5, 5), np.uint8))
    thin = cv2.bitwise_and(col, cv2.bitwise_not(body))
    joined = cv2.morphologyEx(thin, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (11, 3)))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(joined)
    mask = np.zeros(col.shape, np.uint8)
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if 6 <= h <= 16 and w >= 30 and w >= 3 * h:
            mask[max(0, y - 3):y + h + 3, max(0, x - 3):x + w + 3] = 255
    # The labels are drawn about 44 px below each robot's centre. Find the two robot bodies (the largest
    # teal and orange blobs) and also clear label-coloured pixels in a box under each one, which catches
    # labels that touch a ball or the other robot.
    for lo, hi in ((70, 100), (8, 28)):
        c = hue_mask(hsv, lo, hi)
        solid = cv2.morphologyEx(c, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
        n2, _, st2, cen = cv2.connectedComponentsWithStats(solid)
        if n2 < 2:
            continue
        k = 1 + int(np.argmax(st2[1:, cv2.CC_STAT_AREA]))
        if st2[k, cv2.CC_STAT_AREA] < 1500:
            continue
        cx, cy = int(cen[k][0]), int(cen[k][1])
        y0, y1, x0, x1 = max(0, cy + 30), min(c.shape[0], cy + 60), max(0, cx - 62), min(c.shape[1], cx + 62)
        box = np.zeros_like(c); box[y0:y1, x0:x1] = 255
        bodyk = cv2.dilate(solid, np.ones((5, 5), np.uint8))
        lab = cv2.bitwise_and(cv2.bitwise_and(c, box), cv2.bitwise_not(bodyk))
        mask |= cv2.dilate(lab, np.ones((5, 5), np.uint8))
    if mask.any():
        img = cv2.inpaint(img, mask, 4, cv2.INPAINT_TELEA)
    return img, int(mask.any())

def cut(name, src, t0, t1, x, y, w, h, labels):
    cap = cv2.VideoCapture(src); fps = cap.get(cv2.CAP_PROP_FPS)
    cap.set(cv2.CAP_PROP_POS_MSEC, t0 * 1000)
    raw = os.path.join(OUT, name + ".raw.mp4")
    W, H = 1280, 720
    vw = cv2.VideoWriter(raw, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    hits = frames = 0
    while cap.get(cv2.CAP_PROP_POS_MSEC) < t1 * 1000:
        ok, f = cap.read()
        if not ok:
            break
        c = f[y:y + h, x:x + w]
        if labels:
            c, hit = strip_labels(c); hits += hit
        # letterbox onto the tablet's 16:9 frame, on the light stage colour the tablet page uses
        s = min(W / float(w), H / float(h))
        c = cv2.resize(c, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
        canvas = np.full((H, W, 3), (247, 244, 241), np.uint8)
        oy, ox = (H - c.shape[0]) // 2, (W - c.shape[1]) // 2
        canvas[oy:oy + c.shape[0], ox:ox + c.shape[1]] = c
        vw.write(canvas); frames += 1
    vw.release()
    final = os.path.join(OUT, name + ".mp4")
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", raw, "-an", "-c:v", "libx264", "-profile:v", "baseline",
                           "-level", "3.1", "-pix_fmt", "yuv420p", "-crf", "26", "-preset", "veryfast",
                           "-movflags", "+faststart", final])
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-ss", "2", "-i", final, "-frames:v", "1",
                           "-vf", "scale=480:-1", os.path.join(OUT, name + ".jpg")])
    os.remove(raw)
    print("%-22s %5.1fs %4d frames, labels removed in %d, %d KB" % (name, frames / fps, frames, hits, os.path.getsize(final) // 1024))

for c in CUTS:
    cut(*c)
