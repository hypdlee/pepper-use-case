# GATES: Pepper Care Companion v3.4 (IEEE Malta Digital Health Hackathon 2026), saxophone fix and quiz
Audience: health care professionals using the tablet with residents.

- [x] H1 Map: links and ports valid, no show or sound box locks Speakers or Speech, Saxophone locks only Standing and All motors, football gone
  CHECK: python3 /home/claude/hack/tests/test_xar.py
  EXPECT: XAR OK
  EVIDENCE: 38 boxes, 84 links, 25 python scripts compiled on 2.7; XAR OK (Saxophone and Disco and Guitar lock only Standing and All motors; no Speakers/Speech lock in any show or sound box)
- [x] H2 Controller v3.4 on Python 2.7 and 3: tiles, mood, alerts, clearData and the whole quiz
  CHECK: python3 /home/claude/hack/tests/test_controller.py
  EXPECT: CONTROLLER OK
  EVIDENCE: controller checks passed on Python 3.13.18 and 2.7.15; CONTROLLER OK (quiz: 5 distinct questions, voice and tablet answers, double tap, idle end, bank dealt without repeats, hand-edited bank)
- [x] H3 Dialog lint clean, every token and command handled, quiz wired, football gone from Activities
  CHECK: python3 /home/claude/hack/tests/test_dialog.py
  EXPECT: DIALOG OK
  EVIDENCE: 53 proposals, 16 tile tokens, 38 pepperCmd values checked; DIALOG OK
- [x] H4 Tablet: every view and button in headless Chromium, including the quiz at 1280x800, 1024x600 and phone width
  CHECK: node /home/claude/hack/tests/tablet.test.js
  EXPECT: TABLET OK
  EVIDENCE: 99 tablet checks passed; TABLET OK (1280x800, 1024x600, 390x844; quiz question, feedback, result, locked buttons)
- [x] H5 Package consistent (pml lists every file, football audio gone, version 3.4.0)
  CHECK: python3 /home/claude/hack/tests/test_package.py
  EXPECT: PACKAGE OK
  EVIDENCE: 31 resources listed, all present; PACKAGE OK (football-game.mp3 removed; version 3.4.0)
- [x] H6 No em or en dashes and no restricted names in deliverable text files
  CHECK: python3 /home/claude/hack/tests/test_scan.py
  EXPECT: SCAN OK
  EVIDENCE: 19 text files scanned; SCAN OK
- [x] H7 The new tests fail when the work is broken (18 mutants: saxophone lock, repeats, shuffle, leak, double tap, dialog wiring, tablet)
  CHECK: python3 /home/claude/hack/tests/mutate.py
  EXPECT: 18 of 18 mutants caught
  EVIDENCE: 18 of 18 mutants caught (first run had 2 survivors; one equivalent mutant replaced, one test strengthened)
- [x] H8 Quiz bank: at least 100 questions, all different, one right and two different wrong answers each, ASCII
  CHECK: python3 -c "import sys; sys.path.insert(0,'/home/claude/hack/src'); import quiz_bank as q; b=q.QUIZ_BANK; assert len(b)>=100 and len(set(r[0] for r in b))==len(b) and all(len(set(r[1:]))==3 for r in b); print('bank', len(b))"
  EXPECT: bank 146
  EVIDENCE: bank 146; map bank == src bank (146 rows)
- [x] H9 Delivered zip equals the tested pkg and docs (unzip, diff -r) and was sent with SendUserFile
  EVIDENCE: PepperCareCompanion-hackathon.zip (5.1 MB, 51 entries) unzipped and diff -r identical to pkg and docs, also after the mutation run

# Round 3 (v3.5): activities restarting or switching, quiz not showing / not taking answers
- [x] R1 Controller guards (duplicate exercise/quiz/alert/mood, ack-before-speak, voice read gate, tap k/q) pass on py3 and py2.7
  CHECK: python3 /home/claude/hack/tests/test_controller.py
  EXPECT: CONTROLLER OK
  EVIDENCE: controller checks passed on Python 3.13.18 and 2.7.15; CONTROLLER OK
- [x] R2 Dialog: no global activity words, only stop ends shows, no exercise repeat, no dynamic quiz concepts
  EVIDENCE: DIALOG OK (52 proposals)
- [x] R3 Tablet: quizShown ack, k/q on taps, unlock after 2.5 s, run-aware seq, quiz shown without a name
  EVIDENCE: TABLET OK (106 checks)
- [x] R4 Tests fail when the fixes are broken
  EVIDENCE: 35 of 35 mutants caught
- [x] R5 Zip equals tested pkg and docs; no dashes or restricted names
  EVIDENCE: SCAN OK; diff -r IDENTICAL; zip 5119406 bytes, 51 files

# Round 4 (v3.6): Relive Malta replaces My mood
- [x] M1 All suites pass (XAR, controller py3 and py2.7, dialog, tablet 142, package 32 resources, scan 20 files)
  EVIDENCE: bash tests/run_all.sh: XAR OK, CONTROLLER OK, DIALOG OK, TABLET OK, PACKAGE OK, SCAN OK
- [x] M2 Tests fail when the v3.6 work is broken
  EVIDENCE: 53 of 53 mutants caught (52 in the full run; the last, a missing picture, had a wrong target file, was fixed and run by hand: tablet test failed as expected, file restored)
- [x] M3 Zip equals tested pkg and docs
  EVIDENCE: unzip + diff -r IDENTICAL, see above
- [ ] M4 Run on a real Pepper
  ABANDON: M4 cannot be done from this workspace; needs one test on the robot

# Round 5 (v3.7): welcome names the eight home tiles, one question and one reply per Relive Malta card, photo gallery
- [x] N1 All suites pass (XAR, controller py3 and py2.7, dialog, tablet 162, package, photos, scan)
  EVIDENCE: bash tests/run_all.sh: XAR OK, CONTROLLER OK, DIALOG OK, TABLET OK (162), PACKAGE OK, PHOTOS OK, SCAN OK
- [x] N2 Tests fail when the v3.7 work is broken
  EVIDENCE: 74 of 74 mutants caught
- [x] N3 Zip equals tested pkg, docs and tools/fetch_photos.py
  EVIDENCE: unzip + diff -r IDENTICAL
- [x] N4 Photos: the workspace cannot reach Wikimedia (proxy 403), so no photos are bundled; the fetcher and gallery are tested against a mock Commons and stand-in images
  EVIDENCE: curl to commons.wikimedia.org: CONNECT tunnel failed, response 403
- [ ] N5 Run on a real Pepper
  ABANDON: N5 needs one test on the robot

# Round 6 (v3.7 + supplied photos)
- [x] P1 The 20 supplied photos are installed as html/photos/<card>-<n>.jpg with captions, listed in the .pml, shown on the tablet
  EVIDENCE: PACKAGE OK (54 resources); TABLET OK (163 checks, shipped festa shows 3 dots and a credit, crib 1 photo and no dots); screenshots viewed
- [x] P2 Tests fail when the work is broken
  EVIDENCE: 74 of 74 mutants caught after the photo changes
- [x] P3 Zip equals tested pkg, docs and tools
  EVIDENCE: unzip + diff -r IDENTICAL
- [ ] P4 Author and licence of each photo
  ABANDON: P4 the supplied set had none; the user must look each file up on Commons (README, Photos step 0)

# Round 7 (v3.7 first opening names every topic)
- [x] W1 The first hello and the first tablet name get the full welcome naming all eight topics; later people get the short greeting
  EVIDENCE: DIALOG OK (56 proposals, welcome and nameFirst checked for all eight words); CONTROLLER OK on py3 and py2.7 (registeredfirst once, then registered)
- [x] W2 Tests fail when this is broken
  EVIDENCE: 79 of 79 mutants caught
- [x] W3 Zip equals tested pkg, docs, tools
  EVIDENCE: unzip + diff -r IDENTICAL

# Round 8 (v3.8 guitar removed, "activity" by voice, Snakes and Ladders)
- [x] G1 The guitar is gone (box, sound, tile, dialog, tablet, docs)
  EVIDENCE: XAR OK (31 boxes, 69 links, guitar-absent check); zip contains no "guitar" file; TABLET and DIALOG check the absence
- [x] G2 Topic words ("activity", "music", "quiz", "game"...) are heard at the name question
  EVIDENCE: DIALOG OK (topic rules before the name catch-all in askName and askNameAgain, "activity" token checked)
- [x] G3 Snakes and Ladders works end to end (rules, voice, tablet, locks)
  EVIDENCE: CONTROLLER OK py3.13 and py2.7 incl. 300 random games; TABLET OK 216 checks incl. walk, ladder, snake, win; screenshots viewed
- [x] G4 Bugs found by the tests were fixed
  EVIDENCE: raw %d in spoken lines; board clipped at 1280x800; spoken "new game" echo; wrong closing tip
- [x] G5 Tests fail when this is broken
  EVIDENCE: 117 of 117 mutants caught (2 survivors strengthened and re-killed)
- [x] G6 Zip equals tested pkg, docs, tools
  EVIDENCE: unzip + diff -r IDENTICAL, 7.0 MB
- [ ] G7 Run on a real Pepper
  ABANDON: G7 needs one test on the robot

# Round 9 (v3.9 two answers per card, choice lists open by themselves)
- [x] H1 Relive Malta cards have two answers, each question names both
  EVIDENCE: CONTROLLER OK py3+py2.7 (exactly two answers, question names both, ma3 gone); DIALOG OK; TABLET OK (two buttons, no "something else" anywhere)
- [x] H2 Saying "activities" or "music" opens the same list on the tablet by itself; closes on choice, stop, no, timeout
  EVIDENCE: DIALOG (pickmusic/pickact/pickoff wired); CONTROLLER (state pick, stop of running activity, 180 s quiet close, before-name case); TABLET (opens, Back stays closed, closes, restart numbers)
- [x] H3 Tests fail when this is broken
  EVIDENCE: 133 of 133 mutants caught (1 survivor strengthened and re-killed)
- [x] H4 Zip equals tested pkg, docs, tools
  EVIDENCE: unzip + diff -r IDENTICAL
- [ ] H5 Run on a real Pepper
  ABANDON: H5 needs one test on the robot

# Round 10 (v4.0 session guard, calm mode, lag watchdog, offline helper layer)
- [x] V1 Pepper no longer restarts the welcome or the name question, or starts a new activity, while a person is served or something runs
  EVIDENCE: CONTROLLER OK py3.13 + py2.7 (v40_session_tests: greeting and group refused while busy, dialog restore); DIALOG OK (hello/group only report, silent %autoStart first proposal)
- [x] V2 Lag and lost words addressed: calm mode, 1 Hz crowd polling only when needed, lag watchdog, settings restored on stop
  EVIDENCE: CONTROLLER OK (v40_calm_tests, v40_lag_tests, v40_crowd_tests); XAR OK (Calm mode parameter)
- [x] V3 Offline helper layer: needs and safety alerts with reasons, context help, suggestions, time and day, jokes and facts, did-you-mean, last heard
  EVIDENCE: CONTROLLER OK (v40_needs/help/talk/suggest/understand tests); DIALOG OK (61 proposals, 71 pepperCmd values); TABLET OK 241 checks
- [x] V4 Bug found by review: Clear all records left the last heard text in the controller and in ALMemory
  EVIDENCE: fixed in _clearData; test fails when either wipe is removed (2 of 2 manual mutants caught)
- [x] V5 Tests fail when this is broken
  EVIDENCE: 200 of 200 mutants caught (run before the V4 fix; V4 mutants checked separately)
- [x] V6 Docs say v4.0, no em-dashes, phrases match the dialog
  EVIDENCE: grep for the em-dash character gives 0 in all four docs; phrases checked against Activity_enu.top
- [x] V7 Zip equals tested pkg, docs, tools
  EVIDENCE: all 7 suites OK before zipping; unzip + diff -r IDENTICAL; behavior.xar cmp equal; VERSION 4.0; 64 files, 7.1 MB
- [ ] V8 Run on a real Pepper
  ABANDON: V8 needs one test on the robot

# Round 11 (v4.0.1 robot silent at start)
- [x] X1 The first welcome no longer depends on the dialog's start message: command keys are cleared before the slow start-up work, and the controller starts the welcome itself after 6 s if none came
  EVIDENCE: CONTROLLER OK py3.13 + py2.7 (v40_startup_tests: none arrives, arrives first, arrives late, name typed first, person gone); 4 manual mutants, 2 survivors strengthened and re-killed
- [x] X2 All suites pass on v4.0.1
  EVIDENCE: XAR, CONTROLLER, DIALOG, TABLET, PACKAGE, PHOTOS, SCAN all OK
- [ ] X3 Confirmed to speak on a real Pepper
  ABANDON: X3 the cause on the robot is a hypothesis; needs the Choregraphe log from the user's run

# Round 12 (v4.1.0 optional laptop dashboard that watches the Care Companion)
- [x] D1 Robot side: box parameter "Dashboard URL" (empty = off), non-blocking sender with 2 s timeout, newest state wins, fails soft, reconnects
  EVIDENCE: CONTROLLER OK py3.13 + py2.7 (v41_dashboard_tests); XAR OK (parameter, unique ids); 7 manual mutants, all caught except one equivalent (content type)
- [x] D2 Laptop side: stdlib-only server and page; read only; no names logged; nothing written to disk
  EVIDENCE: DASHBOARD OK (routes, bad input, stale, 13 parallel clients, busy port, no names in output); DASHBOARD PAGE OK 49 checks; 8 of 9 page mutants caught at first, the survivor strengthened and re-killed
- [x] D3 End to end: the real controller posts over real HTTP; alert with reason, seen, clear records, dead and restarted dashboard
  EVIDENCE: test_dashboard.py end-to-end block
- [x] D4 Hostile names are shown as text
  EVIDENCE: dashboard.test.js (markup in name, reason, queue, history, reminders)
- [x] D5 Naming and privacy scan includes the dashboard folder; docs state the privacy change
  EVIDENCE: SCAN OK (24 files); README and SAFETY_AND_PRIVACY updated
- [ ] D6 Run on a real Pepper and a real network
  ABANDON: D6 needs one run with the robot and the laptop on the same network

# Round 13 (v4.1.1 the log showed: dialog box "topic already loaded", two copies running, robot silent)
- [x] R1 The controller checks that the dialog answers (silent ping), repairs a dead or stale dialog, and tells the staff when it cannot
  EVIDENCE: CONTROLLER OK py3.13 + py2.7 (v411_voice_tests: healthy, inactive, unsubscribed, stale reload order, own-topic cleanup, newer controller, slow answer, old pong, check times, dead dialog notice once, recovery); 22 manual mutants, 22 caught after 7 survivors were strengthened
- [x] R2 The dialog has the silent ping rule, the tablet shows the notice, versions are 4.1.1 everywhere
  EVIDENCE: DIALOG OK, TABLET OK (voice null/true/false, note shown once), XAR OK, PACKAGE OK
- [x] R3 Clean-start steps and troubleshooting rows in the README; no em-dashes, no restricted names
  EVIDENCE: SCAN OK
- [ ] R4 Confirmed on a real Pepper (the cause is read from the log; the engine model is an assumption)
  ABANDON: R4 needs the Choregraphe log from the next run on the robot
