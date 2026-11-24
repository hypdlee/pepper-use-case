"""Makes the QR codes shown on the Help screen (tickets, directions, the championship page) as PNG files in html/img/.
The tablet shows them as pictures, so they work without internet on the robot.

Usage:  pip install segno && python3 tools/make_qr.py
"""
import os, segno

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ChampionshipHost", "html", "img")
CODES = {
    "qr-tickets.png": "https://biljett.mt/events/global-robot-championships-2026/",
    "qr-directions.png": "https://www.google.com/maps/search/?api=1&query=Montekristo%20Estate%20Malta",
    "qr-site.png": "https://www.ieeemalta.org/ieee-robot-championship-2026/",
}

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, url in sorted(CODES.items()):
        segno.make(url, error="m").save(os.path.join(OUT, name), scale=5, border=2, dark="#1E293B", light="#FFFFFF")
        print("%s -> %s" % (name, url))
