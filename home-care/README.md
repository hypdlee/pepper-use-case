# Home care: Pepper Care Companion (v4.1.1)

An activity companion for care homes, built for the IEEE Malta Digital Health Hackathon 2026. Health care professionals interact with Pepper by voice or by touching the tablet. Everything runs on the robot, with no cloud service. The only optional network link is a read-only laptop dashboard, which is off by default.

What it does: greets and asks a first name, medicine check-in and reminders, guided exercise and breathing, music, dance, quiz, snakes and ladders, Relive Malta memory cards, chat, and alerts to the care staff.

## Folders

| Folder | What is inside |
|---|---|
| `PepperCareCompanion/` | The Choregraphe project. Open `PepperCareCompanion.pml` in Choregraphe 2.5, connect to Pepper, press Play once |
| `CareDashboard/` | Optional laptop dashboard that only watches the Care Companion (Python 3.8+, standard library only) |
| `docs/` | README with clean-start steps and troubleshooting, safety and privacy notes, demo script, quiz questions |
| `media/` | Animations of the tablet (exercise, breathing, snakes and ladders) and a short slide deck on the tablet and the local connection |
| `src/` | The Care Controller source (it is embedded in the behaviour box) |
| `tests/` | Test suites used while building (they need the original build set-up, so they are here for reference) |
| `tools/` | Optional script that fetches photos for the memory cards |

## Start here

Read `docs/README.md`: it has the clean-start steps and what to do if Pepper does not talk. Status: tested against a simulated robot; one run on a real Pepper is still needed (see `GATES.md`).
