"""Builds ChampionshipHost/html/data/schedule.csv from the organisers' workbook (sheet "Running order").

Usage:  python3 tools/import_running_order.py "Robot_Arm_AI_Challenge_-_Scoring_and_Leaderboard.xlsx"

Only the public competition programme is taken: the opening ceremony (as one item), the robot catwalk and team
spotlight, the AI for Humanity pitches, every Arena match and Robot Arm round with its teams, the Sunday knockout,
the finals and the awards ceremony (as one item). Speeches, crew notes, changeovers, lunch breaks and the names of
award nominees are left out. Run it again whenever the sheet changes.
"""
import csv, io, os, re, sys, datetime
import openpyxl

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ChampionshipHost", "html", "data", "schedule.csv")
HEADER = """# Programme for the Pepper host, imported from the organisers' running order. Lines starting with # are notes.
# day: sat or sun.  time: HH:MM (Malta time).  minutes: how long it lasts.
# category: arena, arm or stage.  game: tof, chaos, wil, hh, colour, shape, dynamic, pour, fold, tower (optional).
# side_a / side_b: Arena red and blue corner, or the Robot Arm teams on at the same time.  done: yes when finished.
# Re-create with: python3 tools/import_running_order.py <workbook.xlsx>
"""
ARM_ROUNDS = [("Colour Sort", "colour"), ("Shape Sort", "shape"), ("Dynamic Sort", "dynamic"), ("Pouring", "pour"), ("Folding", "fold")]


def hhmm(t):
    if isinstance(t, datetime.time):
        return "%02d:%02d" % (t.hour, t.minute)
    if isinstance(t, datetime.datetime):
        return "%02d:%02d" % (t.hour, t.minute)
    m = re.match(r"^(\d{1,2}):(\d{2})", str(t or ""))
    return "%02d:%s" % (int(m.group(1)), m.group(2)) if m else None


def minutes(a, b, fallback):
    try:
        ha, ma = map(int, a.split(":")); hb, mb = map(int, b.split(":"))
        d = (hb * 60 + mb) - (ha * 60 + ma)
        return d if d > 0 else fallback
    except Exception:
        return fallback


def rows(path):
    ws = openpyxl.load_workbook(path, data_only=True)["Running order"]
    for r in ws.iter_rows(min_row=1, values_only=True):
        if not r or not r[0] or not str(r[0]).startswith(("Sat", "Sun")):
            continue
        day = "sat" if str(r[0]).startswith("Sat") else "sun"
        start, end = hhmm(r[1]), hhmm(r[2])
        if not start:
            continue
        try:
            mins = int(float(r[3])) if r[3] not in (None, "") else None
        except ValueError:
            mins = None
        yield day, start, end, mins, str(r[4] or "").strip(), str(r[6] or "").strip()


def build(path):
    out, opening = [], None
    for day, start, end, mins, seg, act in rows(path):
        m = mins or minutes(start, end or start, 10)
        if day == "sat" and seg in ("Opening video",) and opening is None:
            opening = [day, start, 32, "Opening Ceremony", "stage", "", "", ""]
            out.append(opening)
        elif seg == "Arena robot catwalk":
            if not out or out[-1][3] != "Arena robot catwalk":
                out.append([day, start, 0, "Arena robot catwalk", "stage", "", "", ""])
            out[-1][2] += m
        elif seg == "Robot Arm team spotlight":
            if not out or out[-1][3] != "Robot Arm team spotlight":
                out.append([day, start, 0, "Robot Arm team spotlight", "stage", "", "", ""])
            out[-1][2] += m
        elif seg == "AI for Humanity Pitch":
            n = re.search(r"AI Pitch (\d+)", act)
            out.append([day, start, m, "AI for Humanity Pitch" + (" " + n.group(1) if n else ""), "stage", "", "", ""])
        elif act.startswith("Arena: Game 1: Time of Fall - "):
            a, _, b = act[len("Arena: Game 1: Time of Fall - "):].partition(" vs ")
            out.append([day, start, m, "Time of Fall", "arena", "tof", a.strip(), b.strip()])
        elif act.startswith("Arena: Game 2: Climate Chaos - "):
            out.append([day, start, m, "Climate CHAOS", "arena", "chaos", act.split(" - ", 1)[1].strip(), ""])
        elif seg.startswith("Arms Game"):
            for title, gid in ARM_ROUNDS:
                if title in act:
                    teams = [p.split(" - ", 1)[1].strip() for p in act[len("Arms: "):].split(";") if " - " in p]
                    out.append([day, start, m, title, "arm", gid, teams[0] if teams else "", teams[1] if len(teams) > 1 else ""])
                    break
        elif "Arena R1" in act:
            out.append([day, start, 60, "Arena round 1", "arena", "", "", ""])
        elif "semi-finals" in act:
            out.append([day, start, 30, "Arena semi-finals", "arena", "", "", ""])
            if "Wrap and Pack" in act:
                out.append([day, start, m, "Wrap and Pack (optional)", "arm", "", "", ""])
        elif seg == "Tower Duel":
            out.append([day, start, m, "Tower Construction Duel (final)", "arm", "tower", "", ""])
        elif seg == "Arena Game 4":
            out.append([day, start, m, "Hanging Hazard (final)", "arena", "hh", "", ""])
        elif seg == "Awards Ceremony" and m:
            out.append([day, start, m, "Awards Ceremony", "stage", "", "", ""])
    return out


if __name__ == "__main__":
    items = build(sys.argv[1])
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["day", "time", "minutes", "title", "category", "game", "side_a", "side_b", "done"])
    for it in items:
        w.writerow(it + [""])
    io.open(OUT, "w", encoding="utf-8").write(HEADER + buf.getvalue())
    print("schedule.csv: %d items" % len(items))
