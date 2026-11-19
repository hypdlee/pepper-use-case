# Gates: Pepper Championship Host v1.0.0

- [x] G1 Neutral clips: 10 per-game clips, team branding, panels and captions removed, muted, H.264 baseline 1280x720
  EVIDENCE: test_package clip checks; visual check of frames (labels gone); scan finds no team name in the package
- [x] G2 IEEE Malta look: white, #FFCD57, #772583, Open Sans (bundled, OFL), pill buttons, 1280x800
  EVIDENCE: docs/media screenshots; UI test: no horizontal overflow on any view, cards fit
- [x] G3 Works without team names: corner colours, empty-state messages, CSV templates, staff entry on the tablet
  EVIDENCE: UI preview-mode checks; controller teams line with 0 teams
- [x] G4 Controller on Python 2.7 and 3 against a simulated robot (dialog commands, tablet, staff, persistence, match calls, voice check, greeting)
  EVIDENCE: CONTROLLER OK on 3.13.18 and 2.7.15; source is plain ASCII
- [x] G5 Tablet flows (games, teams, schedule, scores, quiz by touch and voice, volunteer, staff, idle, XSS)
  EVIDENCE: UI OK 119 checks
- [x] G6 Package: xar boxes and links valid, controller in xar equals source, .pml lists every file, dialog commands all handled
  EVIDENCE: PACKAGE OK
- [x] G7 Tests catch real bugs: 18 controller mutants and 10 tablet mutants, all caught (after adding 5 tests and fixing a harness thread race)
  EVIDENCE: mutation runs, survivors []
- [ ] G8 Run on a real Pepper (speech in a loud arena, clip playback on the tablet, dynamic team concept)
  ABANDON: G8 needs the robot; checklist in docs/README.md "Before the event"

# Round 2 (v1.0.1): official team list, fit on Pepper's tablet
- [x] G9 Teams from the organisers' sheet: 8 Arena, 5 Robot Arm, names exactly as in "Teams & Settings"
  EVIDENCE: test_package counts 8 + 5; controller reads them on Python 2.7 and 3, including the accented name
- [x] G10 Different team counts handled: grouped team view with counts, every team listed on its scoreboard, staff match form offers only that competition's teams, look-alike names answered with both
  EVIDENCE: CONTROLLER OK (real-list scenario), UI OK 139 checks
- [x] G11 Fits 1280 x 800 with nothing cut off or stretched: all 13 team cards and both full scoreboards without scrolling, NOW match scrolled into view, every picture box exactly 16:9
  EVIDENCE: tests/fit_audit.js FIT OK on every view; ratio checks in the UI test
- [x] G12 New code is tested: 10 deliberate bugs in the new team code, 9 caught, 1 equivalent (removes nothing)
  EVIDENCE: mutation run, survivors [] after lengthening the audit schedule
- [ ] G13 Same check on Pepper's own tablet browser
  ABANDON: G13 needs the robot; the layout is fixed at 1280 x 800 and avoids newer CSS, but it has not been seen on the tablet itself

# Round 3 (v1.0.2): robot log showed silence and a red Host box
- [x] G14 Speech works on the robot: no .post (not available on session services); _async=True futures, thread fallback
  EVIDENCE: strict simulator (no .post, like the robot) CONTROLLER OK on 2.7 and 3; test_package forbids .post
- [x] G15 No "topic already loaded": no Dialog box, no topic in the manifest; the controller unloads an old copy, loads, listens, and unloads at stop
  EVIDENCE: simulator starts with an old copy loaded and refuses a second load; start, repair, stop and newer-controller cases pass
- [ ] G16 Confirmed on the robot
  ABANDON: G16 needs the next Choregraphe log

# Round 4 (v1.1.0): Pepper gives the intro, talks less, 100-question quiz
- [x] G17 Pepper's intro: 12 scenes (who Pepper is, both competitions, every game with its clip, all 13 teams, what's next, invitation), each waits for Pepper to finish speaking; starts from the tablet, by voice, by staff, or by itself after a quiet spell with someone near; Skip / "stop" end it; a match call ends it first
  EVIDENCE: test_controller intro block (order of 12 scenes, long sentence holds the scene, auto intro needs someone near, parameter 0 + staff override, no restart after finishing) OK on 2.7.15 and 3.13.18
- [x] G18 Less talking: screens are silent, greeting at most every 2 minutes, one call per block of matches (16 Time of Fall matches: one call), start announcements off by default, quiz speech is the question plus "Correct!" / "Not quite"
  EVIDENCE: test_controller block-call and quiet-view checks OK
- [x] G19 Quiz has 100 questions; five per round from a shuffled bag; no repeat until all 100 were asked; new pass never starts with the five just asked; bag survives a reload
  EVIDENCE: content.json quiz length 100; ui.test.js 21 rounds, 100 unique, reload continues at round 22; UI OK 309 checks
- [x] G20 Official running order imported (56 items) with match sides; no award nominee names; no care or medical wording
  EVIDENCE: ui.test.js schedule checks; test_package care-word and neutrality checks
- [x] G21 Fits 1280 x 800: new Home and all 12 intro scenes, nothing clipped or off screen
  EVIDENCE: fit_audit.js intro-1 ... intro-12 clipped=[] needs-scroll=[]; FIT OK
- [x] G22 New code is tested: 11 bugs planted (3 quiz shuffle, 8 intro and match calls); 10 caught, 1 equivalent (end-of-intro time is already covered by the last sentence's time)
  EVIDENCE: mutation run after tightening three tests
- [ ] G23 Confirmed on the robot
  ABANDON: G23 needs a run on Pepper and the Choregraphe log

# Round 5 (v1.1.0): the tablet redesigned as a kiosk
- [x] G24 Bottom dock of seven big buttons replaces the small top tabs and the footer; every button at least 150 x 70
  EVIDENCE: ui.test.js dock check; UI OK 310 checks
- [x] G25 Every public screen fills the tablet and nothing sits under the dock: Home, Games (both), game detail, Teams (all 13 without scrolling), Scores (all 8 Arena teams without scrolling), Quiz, Help, all 12 intro scenes
  EVIDENCE: fit_audit.js measures against the top of the dock; FIT OK. Cards checked to end above 700 px in ui.test.js
- [x] G26 Larger type throughout (body 17 to 23 px, titles 25 to 50 px, quiz answers 31 px) and a full-screen purple intro
  EVIDENCE: screenshots in docs/media and the repo tour GIF, reviewed at full size
