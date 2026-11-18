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
