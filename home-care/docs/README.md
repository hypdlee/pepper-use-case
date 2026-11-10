# Pepper Care Companion (v4.1.1)

A care home activity companion for Pepper, built for the IEEE Malta Digital Health Hackathon 2026. Pepper leads a resident through short exercises, guided breathing, music, a dance, a five question quiz, Snakes and Ladders, Relive Malta memory cards, medicine check-ins and reminders. A tablet screen for the resident and a separate Staff view for the care professional run alongside it. Everything runs on the robot and its tablet, with no cloud service and no internet. An optional laptop dashboard (below) can watch it over your local network, and is off unless you set an address.

## Laptop dashboard (optional, new in v4.1)

A second screen for the care professional: a web page on a laptop or phone that shows, live, who is with Pepper, what Pepper is doing (exercise, quiz question, game position, memory card), carer alerts with their reason in red, the queue, medicine reminders, the day's records and what Pepper last heard. It only watches. An alert is still marked as seen on Pepper's tablet.

1. On the laptop (Windows, Mac or Linux with Python 3.8 or newer, nothing else to install), open the `CareDashboard` folder and double click `start_dashboard.bat` (Mac or Linux: `./start_dashboard.sh`). The window prints two addresses: one for this laptop, one for a phone on the same Wi-Fi. On Windows, allow Python through the firewall for **private** networks when asked.
2. In Choregraphe, double click the **Care Controller** box and set the parameter **Dashboard URL** to the address the window printed for Pepper, for example `http://192.168.1.50:8100`. Leave it empty to keep the dashboard off (the default).
3. Press Play. The dashboard top bar changes to "Pepper connected" within a few seconds. In the log you should see `[Care Controller] dashboard link on: http://...`.
4. Press the "Alert sound" button on the dashboard page once (browsers only allow sound after a click) to hear a beep for each new alert.

What changes for privacy: with an address set, the robot sends the same information the Staff view shows (first names, the activity, alerts and their reasons, records, what it last heard) to that one laptop, over the local network, without a password. Use a private network you trust. The dashboard keeps it in memory only, writes nothing to disk, logs no names, and forgets everything when you close it. "Clear all records" on the tablet clears the dashboard too. With the parameter empty, nothing is sent anywhere.

If the laptop is off or the network drops, Pepper carries on as normal (each send gives up after 2 seconds, in its own thread), the dashboard says "Pepper is not sending", and it reconnects by itself when the laptop is back. Do not run another Pepper program that shows its own page on the tablet or speaks at the same time as the Care Companion.

Not yet done: the dashboard has not been run on a real network with a real robot (it is tested with the real controller code posting over real HTTP on one computer, and with a headless browser), it has no password, and it is a separate program on its own port (8100), not a tab inside any other dashboard.

## Start it, and what to do if Pepper does not talk

**Clean start (do this every time you put a new version on the robot).** A robot log showed the dialog box failing with `LoadTopic::ALDialog ... Activity_enu.top is already loaded`, and two copies of the app running at once. Then the tablet and the controller work, but the voice engine is dead or is running an old copy of the dialog, so Pepper is silent.

1. In Choregraphe press the red "Stop all behaviours" button (or stop every running behaviour in the Robot applications panel). Wait until nothing is running.
2. Remove every older copy of the project from the robot and from Choregraphe (the package id is `pepper-care-companion`; very old copies use `test-148bbb`), so that only one copy exists. Also close any extra Choregraphe project that has the same behaviour open.
3. If Pepper was silent before, clear the dialog engine. The simplest way that always works is to restart the robot (long press the chest button, or Choregraphe: Robot, "Restart"). Wait until Pepper is up. If you can open a shell on the robot, this works too (the first line shows the real topic name, which should be `Activity`): `qicli call ALDialog.getAllLoadedTopics`, then `qicli call ALDialog.deactivateTopic Activity` and `qicli call ALDialog.unloadTopic Activity`.
4. Unzip the new zip into a NEW folder, open `PepperCareCompanion/PepperCareCompanion.pml` in Choregraphe 2.5, connect to Pepper, and press Play ONCE. Do not press Play again while it runs.
5. In the Choregraphe log view you should see `[Care Controller] v4.1.1 running` within a few seconds, then `running behaviours: ...` (this line lists what runs; more than one entry for this app is a problem). On the tablet, "Waiting for Pepper" should change to "Pepper connected", and the Staff footer says v4.1.1.
6. Within about 6 seconds Pepper should speak the welcome and ask for the first name.

**New in v4.1.1: Pepper checks its own voice.** About 3 seconds after it starts, the controller asks the dialog "are you there?" (a silent test word). If the dialog answers, the log says `the dialog answers (first check): the voice is ready` and nothing else happens. If not, the controller looks at the dialog engine and writes what it finds (`the dialog did not answer (try 1). Loaded topics: ... Active topics: ...`), then repairs it: first it activates the topic and starts the engine, then, if still silent, it reloads the topic from the file (an old copy may have been the one running), and asks again. If after about 14 seconds there is still no answer, the tablet shows "Pepper voice not ready" with a note, the staff footer says what to do, and Pepper says "My voice is not ready. Please ask a helper to restart me." (if the speech engine works at all). This is tested against a model of the dialog engine; it has not yet been confirmed on a real Pepper, so please send me the Choregraphe log from the next run.

If Pepper stays silent:

| What you see | Likely cause | What to try |
|---|---|---|
| No `[Care Controller] ... running` line, or a red error from the Care Controller box | The controller did not start (v4.0 needs it for the greeting) | Send me the log lines from the moment you pressed Play |
| The tablet stays on "Waiting for Pepper" | Same: the controller is not running | As above |
| Red error `Activity ... is already loaded` at start | A topic from an earlier run is still loaded | Do the clean start above. v4.1.1 also tries to repair this by itself and tells you on the tablet if it cannot |
| `running behaviours:` lists this app twice | Two copies run at the same time | Stop all behaviours, press Play once |
| Tablet says "Pepper voice not ready" | The dialog never answered, even after the repair | Clean start above (restart the robot); check Pepper's volume and that it is awake and not in rest; send me the log |
| The controller line is there, the welcome line is there, the dialog answers, still no voice | Pepper's speech is off or too quiet | Check Pepper's volume and that the robot is awake and not in rest; say "hello" |
| Pepper talks only after you say "hello" | The start message and the fallback were both missed | Send me the log |
| Old behaviour (v3.x text, no "Calm mode" parameter on the Care Controller box) | An old copy is still the one running | Remove old copies, open the new `.pml` |


## What is new in v4.0

v4.0 answers three problems seen in use. None of it has been run on a real Pepper or in Choregraphe yet (see "Known limits").

| Problem | Cause found in the code | Now |
|---|---|---|
| Pepper started a new session, asked for the name again, or began a new activity in the middle of one | Nothing stopped the dialog's own opening (the welcome and the name question) from firing again while a person was being served, and a dialog restart took the running quiz, card or game out of its listening rules | "Hello" and "group" are now only reports to the controller. It refuses them while a person is served, an activity runs or a call is in progress (log line `greeting ignored`). A silent first proposal swallows a topic restart (log line `topic restart ignored`), and a running quiz, card or game gets its listening rules back after a restart |
| Locking onto a face made Pepper lag, and then it sometimes missed what was said | Awareness kept switching between people and sounds, background movement and face recognition ran all the time, and people were polled every tick | **Calm mode** (a box parameter, on by default): Pepper stays with one person, tracks with the head only, ignores movement and sound as distractions, has face recognition and listening movement off, and polls the crowd once a second and only when the crowd warning is on. A **lag watchdog** pauses tracking and crowd checks when three slow ticks come in a row (log line `the robot is slow: tracking paused`, and the Staff view says so) and brings them back after 45 seconds of normal speed. Every setting Pepper changed is put back when the behaviour stops |
| "Make it more like a language model" | Not a bug | An offline helper layer, described next. It is not a neural language model |

### The helper layer (no cloud, no network)

- **Needs and safety phrases.** "I have fallen", "I am in pain", "I feel dizzy" and "I can not breathe" (with a few variants each) raise an urgent carer alert and stop whatever is running. "I need the toilet", "I am thirsty", "I am hungry", "I am cold" and "I am hot" raise a normal alert and do not stop the activity. Every alert carries its reason, shown in the banner and the alert list of the Staff view ("has fallen", "is in pain", "needs the toilet", "would like a drink", and so on). Two different reasons are not merged; the same reason inside a short window is.
- **Help that knows the context.** "What can you do", "what can I say" or "I do not understand" tells the person what they can say right now (for example the options of the quiz that is running). The words "help" and "help me" still raise the carer alert.
- **Suggestions.** Saying "surprise me", "I am bored", "something fun", "you choose" or "what do you suggest" gets one suggestion that avoids what was already done in the session, with yes or no. After a low mood ("I feel low", "I am sad", "I am lonely") the suggestion favours breathing, music, memories or a chat.
- **Time and date.** "What time is it", "what day is it" are answered from the robot's own clock in plain words ("It is a quarter past ten in the morning", "Today is Sunday, the first of November").
- **Jokes and facts.** "Tell me a joke" and "tell me a fact" (or "did you know") give one of 8 jokes or 11 Malta and nature facts, with no repeat until all have been told. While an activity, quiz, card or game is running Pepper says "Let us finish this first" and does not interrupt it.
- **Did you mean.** When Pepper hears something it does not know, it compares it with its own words (same word or same stem, so "lonely" does not match "lovely"). If there is one clear winner, it asks "Did you mean music?" and does it on yes. Otherwise it asks the person to say it another way or to touch the tablet. This depends on the robot passing back the heard text (`Dialog/LastInput`), which may be empty on a real robot.
- **Last heard.** The Staff view footer shows the last thing Pepper heard, which helps in a noisy room.

Honest limits: this is rules and word matching, not a language model. Pepper's speech recognition only hears words that are in the dialog's word lists, so a free sentence is not understood. Please say this when you present it.

## Open and run

1. Open `PepperCareCompanion/PepperCareCompanion.pml` in Choregraphe 2.5.
2. Connect to Pepper (NAOqi 2.5 with the tablet) and press Play. The behaviour starts the dialog, the Care Controller, and loads the tablet page.
3. If an older copy of this project is installed on the robot under the old id (`test-148bbb`), remove it first, because the package id is now `pepper-care-companion`.

## What the resident and the staff can do

| Where | What |
|---|---|
| Tablet, resident screen | Eight tiles: Exercise, Breathe, Music, Activities, Chat, Relive Malta, Medicine, Reminder. Help and Stop are always at the bottom. |
| First opening | The first time someone says "hello" (or the first name is typed on the tablet after Pepper starts), Pepper says: "I am Pepper, your activity companion. I can help you exercise and breathe, play music and activities, chat, relive memories of Malta, and look after your medicine and reminders." and then asks for the first name. Later people get the short greeting. |
| Welcome menu | After the check-in Pepper names the eight topics of the home screen, and only those (not what is inside them): "What would you like? Exercise, breathing, music, activities, chat, memories of Malta, medicine, or a reminder?". Saying any of them, including "memories", works. |
| Music | Pepper asks "Which one?" and the same choices appear on the tablet by themselves, whether you tapped Music or just said "music": three songs and the Saxophone. Say it or tap it. |
| Activities | Pepper asks "Dance, a quiz, or snakes and ladders?" and the three appear on the tablet by themselves with icons (also when you only said "activities"); they close again when something is chosen, when you say "stop" or "no", or after 3 minutes. Saying "activity" or "activities" (or "game") works at any time, including straight after Pepper's welcome. |
| Snakes and Ladders | A board game against Pepper on the tablet: a 10 by 10 board, 8 ladders and 8 snakes, two pieces. The resident goes first, touches the dice (or says "roll"), and the pieces walk square by square. Pepper then rolls for itself and says both results in one short sentence, for example "You got a three. You are on 3. Now me. I got a four. I am on 4. Your go!". A resident who does not want to roll can touch Skip my turn. An exact number is needed to land on 100. When someone wins Pepper asks "Would you like another game?" (say yes, or touch Play again; Done or "stop" closes it). The number of games and wins is kept in the record for the carer. See "Snakes and Ladders in detail". |
| Quiz | Five questions, three answers each. Pepper reads the question and the options and listens for "one", "two" or "three" (or the answer itself). The tablet shows the same question with three big buttons, so either works. Pepper says "Correct" or gives the right answer, keeps the score, and says the result at the end. The result is also kept in the resident's record. |
| Relive Malta | Ten reminiscence cards (pictures, one warm sentence, and ONE question that names its two answers). The resident taps or says an answer, Pepper gives one short reply, then stays quiet. Next, Back, I like this and Stop on the tablet. The answers and likes are kept in the record for the carer. See "Relive Malta in detail" below. |
| Staff view (top right) | Who is with Pepper, queue, medicine reminders, carer alerts with a Seen button, the day's records, and Clear all records. |
| Voice (v4.0 additions) | Anytime phrases: needs and safety ("I have fallen", "I need the toilet", "I am thirsty"), "I feel low", "what can you do", "what time is it", "what day is it", "tell me a joke", "tell me a fact", "surprise me". The time, the day, needs and "what can you do" are answered during an activity without ending it; jokes and facts wait until it is over; the urgent safety phrases stop it |
| Voice | Pepper's questions can be answered by voice (see each question). Anytime words: "hello", "help", "stop", "reminder", "medicine". To start something, use the tablet or answer Pepper's menu question ("What would you like?"). Loose words like "dance" or "music" no longer switch what Pepper is doing, because noise and the music itself were triggering them. |

## What changed from the package you sent

The map was already wired for exercises, songs and shows. The gaps were elsewhere:

| Area | Gap found | Now |
|---|---|---|
| Map, mood | A camera reading of one face (Get Expression, SayExpression, FailExpression) | Removed in v3.6 and replaced by Relive Malta, which needs no map box. The face reading was a rough guess, and judging a resident's feelings from their face is the most sensitive thing the project did. Pepper still asks "How do you feel today?" by voice |
| Map, tablet | If Show App failed to open the page, nothing happened and a retry was ignored | New TabletFailed box says so once and retries up to five times. Show App can now be retried |
| Map, alerts | A help request only changed the tablet | New onAlert output and CaregiverAlert box flash the eyes amber. Help also stops any exercise, music or show |
| Map, stop | Stopping the behaviour did not stop the controller | Behaviour onStop is wired to the Care Controller |
| Map, layout | Boxes were scattered | One column per job: tablet and dialog, shows and songs, exercises |
| Tablet | Six tiles; Guitar, Football, Saxophone, Reminder and the three songs had no button | Eight tiles. Music and Activities each open a short choice list, and Pepper asks the same question by voice |
| Tablet | Carer alerts were not listed anywhere | Staff view lists them with Seen and a badge on the Staff button |
| Tablet | No way to remove stored names | Clear all records, with a confirmation |
| Branding | Old university logo | Plain text title and event name |
| Map, saxophone | The saxophone never played. The robot log shows the command arrived and was started, but nothing sounded | The Saxophone box was the only show box that locked the Speakers resource (the parent of Speech and Audio player). The dialog holds Speech while Pepper talks and the box's own sound needs Audio player, so Choregraphe did not start it. The lock is removed. Guitar and Dance never had it |
| Activities | Football was a show with a ball sound | Replaced by the quiz (below). The football box, its sound and its audio file are removed from the project |
| Dialog | Guitar and saxophone were hidden words; the menu did not mention them | Pepper's menu names the eight home tiles (see the Welcome menu row). Saying the bare words still works. Help now says "I am letting the care staff know", which matches what the alert really does |
| Dialog (v3.8) | After Pepper's opening, saying "activity" did nothing but touching the tile worked. Pepper was waiting for a first NAME, and the rule that catches any word as a name swallowed "activity" (and "music", "quiz" and so on) | The topic words are now heard before the name rule, in both name questions, and "activity" is a known word for Activities. A topic word said instead of a name starts that topic; the tablet then shows "Hello." until a name is given |
| Relive Malta (v3.9) | Every card offered three answers: two choices and "Something else" | "Something else" is removed. Each card has two answers. Pepper reads only the question, so the four questions that did not name both answers (festa, harbour, bread, Christmas) were reworded to name them, for example "At the festa, did you enjoy the band or the fireworks?" |
| Tablet (v3.9) | Saying "activities" or "music" made Pepper list the choices, but the list opened on the tablet only when it was tapped | Pepper's question now tells the controller, and the tablet opens the same list by itself. A list you close with Back stays closed for that question |
| Music (v3.8) | The guitar was a music choice | Removed with its box, its sound file, its tile and its dialog words. Music is now three songs and the saxophone |
| Activities (v3.8) | Three choices: dance, quiz, and no game | Snakes and Ladders added (below). The game was supplied as a separate project with its own dashboard, CSV export and demo carer button; here it is rebuilt inside this project so it shares one controller, one dialog and the same safeguards. The CSV, the dashboard and the demo carer button were left out, because the Staff view and the Help button already do those jobs |

## What is tested, and what is not

Tested here: all 31 boxes and 69 links in the map; the Care Controller script on Python 2.7 and 3 against a simulated robot; the dialog against the controller; the tablet in a real browser engine at 1280x800, 1024x600 and phone width; the package listing.

Not tested: a real Pepper and a real Choregraphe. The amber eye flash, speech recognition in your room, the tablet's own web view, and the timing of each exercise on the robot need one run on the robot before the demo.

| Check | What it proves |
|---|---|
| Map structure | Every link and port in the map is valid. Alert, tablet retry and stop wiring exist, and no mood box is left. No show or sound box locks Speakers or Speech (the saxophone cause). All 19 box scripts compile on Python 2.7 |
| Care Controller | Tiles, Relive Malta, alerts, acknowledge, clear records, exercise timing, songs, shows, and the whole quiz on Python 2.7 and 3 |
| Snakes and Ladders | The ladders and snakes are the same on the robot and the tablet, none starts where another ends, and 300 whole games with random dice always finish with nobody off the board. Exact finish, ladders, snakes, skips and both wins behave as the rules say. The tablet shows the board first, then Pepper speaks; a spoken command or a tap during Pepper's speech or the walk, a double tap, and a tap made on an old round are all ignored. The board fits above Help and Stop at 1280x800, with or without a note on screen, and at 1024x600 and phone width |
| Quiz | The bank has 146 questions, none repeated, each with one right and two wrong answers. A quiz is five different questions. Every question is asked once before any comes back. The right answer lands on all three positions. Voice and tablet answers are scored the same way, a double tap is ignored, and the tablet never receives the right answer before the question is answered |
| Relive Malta | Ten different cards in plain English, none of Pepper's words is a voice command, no question is a memory test. The tablet gets a card first and Pepper reads it only when the tablet says it shows it (or after 2.5 seconds). A tap made on another card is ignored, and so is a spoken command or answer while Pepper is still reading. Only the first answer on a card counts and it gets one reply; "Something else" is not kept. Every answer word is different across the cards, and the dialog's word lists are checked against the cards. A repeated start does not restart. Cards come in a shuffled order, likes and answers are kept (last six), an idle session ends quietly, and any other command ends it. The photo fetcher is tested against a simulated Commons (it refuses non-commercial, no-derivative and non-JPEG pictures, writes the credits and lists the files in the project) |
| Voice check (v4.1.1) | Against a model of the dialog engine: a healthy dialog is asked once and nothing is touched; an inactive or unsubscribed topic is started; a stale topic is unloaded and loaded again from the file (in that order); the controller ends only what it started and leaves a newer controller's topic alone; a dead dialog ends in one tablet notice and one spoken notice. The model is my reading of the engine, so this needs one run on the robot |
| Dialog against controller | Every command the controller sends has a dialog handler, and every command the dialog writes is handled |
| Tablet in a browser | Every button and view in headless Chromium, layout, ES5 syntax, no network requests |
| Package | Everything is listed in the project file, and the controller in the map is the tested one |

## The quiz in detail

- **Questions.** 146 multiple choice questions in seven groups: Malta and Gozo, animals and nature, food and everyday life, the world, music art and history, numbers and science, sport. They are easy general knowledge and Maltese topics, with no names of residents and no medical content.
- **Each time.** Five questions are dealt from a shuffled copy of the bank, so a question does not come back until all 146 have been asked (about 29 quizzes). The three answers are shuffled for every question.
- **Voice.** Say "one", "two" or "three". Say "repeat" to hear the question again and "stop" to end the quiz. A spoken answer only counts once Pepper has finished reading the options, so Pepper's own words cannot answer for you.
- **Screen first.** Pepper starts reading a question only after the tablet reports that it is showing it (or after 2.5 seconds if the tablet does not answer). Each tap carries the question it was made on; a tap on an old question is ignored instead of answering the new one. If a tap is ignored the buttons come back after 2.5 seconds.
- **Staff.** The record shows how many quizzes and the last score. Touching any other tile, Stop, Help or a medicine reminder ends the quiz. If nobody answers for four minutes it ends by itself.
- **Reading them.** `QUIZ_QUESTIONS.md` lists every question with its right answer, so you can check the content before the demo.
- **Changing them.** Double click the Care Controller box in Choregraphe and edit the `QUIZ_BANK` list near the top of its script. Each row is the question, the right answer and two wrong answers, in plain English letters. Keep every question different and keep at least 100 rows.

## Snakes and Ladders in detail

- **Rules.** Squares 1 to 100, the resident and Pepper both start off the board. Ladders: 2 to 23, 8 to 34, 20 to 41, 32 to 68, 36 to 57, 48 to 74, 71 to 91, 80 to 99. Snakes: 29 to 9, 38 to 15, 47 to 26, 62 to 43, 77 to 56, 86 to 54, 94 to 73, 97 to 78. Landing on 100 needs the exact number; a bigger number leaves the piece where it is ("That is too many for the end"). To change that, set `SNL_EXACT = False` in the controller (a bigger number then finishes the game).
- **Dice.** The controller rolls fair dice (Python's random generator). The tablet only animates the result, so what Pepper says always matches the board.
- **One round.** The resident rolls, then Pepper rolls straight away, and Pepper says both moves in one sentence and ends with "Your go!". The tablet shows the board first and Pepper speaks after the dice have settled (or after 2.5 seconds if the tablet does not answer). A spoken "roll" only counts after Pepper has finished speaking and the pieces have stopped; a tap counts only on the round on screen.
- **Ending.** "Stop", Help, any other tile, a medicine reminder, or 10 minutes without a move end the game. The idle end is silent. After a win the closing screen stays for 2 minutes, then goes quietly.
- **Staff.** The record shows how many games were played and won, for example "Snakes and Ladders: 3 played, won 1".
- **Changing it.** The board tables `SNL_LADDERS` and `SNL_SNAKES` are in the controller and again in `html/js/panel.js`; a test fails if they differ. Keep no square that is both the end of one and the start of another.

## Relive Malta in detail

- **Why.** Looking at familiar places, food and traditions is a standard care home activity. It starts conversations, and it is the carer who leads them. Nothing here is a test: every prompt is an invitation with no right or wrong answer.
- **Ten cards.** Village festa, colourful fishing boats, the Gozo ferry, pastizzi and tea, the Grand Harbour, the baker and fresh bread, Christmas time, Carnival, a summer day at the beach, and the street with colourful balconies. The order is shuffled each time.
- **How it runs.** The tablet shows the card; Pepper then reads the title, the sentence and the question, and goes quiet. The resident answers by touching a button, or by saying "one", "two" or the answer itself (for example "ricotta" or "peas"). Pepper gives ONE short reply to that answer, and the next thing that happens is up to the resident or the carer: Next, Back or Stop. There are no spoken hints and no timeouts that speak. By voice "next", "back", "repeat", "stop" and the answers are heard, and a spoken command or answer counts only after Pepper has finished reading. Touch works the same way, and a tap made on an old card is ignored. Only the first answer on a card counts.
- **Staff.** "I like this" and the answers are kept in the record (the last six of each) and shown in the Staff view, for example "Said: Pastizzi and tea: Ricotta". Like everything else it is held in Pepper's memory only and is lost when the behaviour stops.
- **Changing the cards.** Edit `MEM_CARDS` in `src/care_controller.py` (or in the Care Controller box in Choregraphe): key, title, one sentence, the question, and two answers, each with its label, its voice words and Pepper's one reply. Keep the text plain English letters, and avoid the words next, back, again, repeat, stop, thanks, done, one, two, three, first, second and third in Pepper's own words (they are voice commands). If you change an answer word, the matching `memW1` or `memW2` concept in `Activity/Activity_enu.top` must list the same words; `tests/test_dialog.py` checks this. Every answer word must be different from every other on all cards.
- **Pictures.** Each card has a drawing (`html/js/memories.js`, no text, people or logos) and 1 to 3 real photos (20 in all, in `html/photos`, supplied by the project owner; see "Photos" below for the credits you still need to fill in). To add or replace photos, use `tools/fetch_photos.py` or your own files. A card with photos shows them with small dots (a tap on the picture shows the next one, and they rotate slowly) and a credit line; a card without photos keeps its drawing.

## Photos

0. **Credits to complete.** The 20 photos in the zip came as a ready made set from Wikimedia Commons without the author or licence of each picture. The caption under each shows "Photo: Wikimedia Commons" and `html/photos/CREDITS.txt` says which details are missing. Before the project is published or shown outside the hackathon, look each file up on Commons and put the real author and licence in `credits.js` and `CREDITS.txt` (CC BY and CC BY-SA need the author's name). A few pictures show performers' faces (festa band, carnival float) or a little shop text (luzzu boat 2 has "Boat Trips", the baker counter a crate label); delete a file from `html/photos` and run the tool with `--register-only` if you prefer not to show it.
1. To fetch other pictures: unzip the project. On a computer with internet access run: `python tools/fetch_photos.py --project PepperCareCompanion` (Python 3, nothing to install).
2. The script reads each picture's licence and author from Wikimedia Commons, keeps only JPEGs that are CC0, public domain, CC BY or CC BY-SA (no NC, no ND) and at least 600 px wide, saves them at 800 px width in `html/photos`, writes the credit captions (`credits.js`, `CREDITS.txt`), and lists every file in the `.pml` file (Choregraphe installs only listed files).
3. Open `photo_preview.html` (created next to the project) and look at every picture. Delete any you do not like from `html/photos`, and run the command again with `--register-only`.
4. Your own photos work too: save them as `html/photos/<card>-1.jpg`, `-2.jpg`, `-3.jpg` (cards: festa, luzzu, ferry, pastizzi, harbour, baker, crib, carnival, beach, balconies; about 800 px wide) and run with `--register-only`.
5. Install the project to Pepper as usual. The credit line under each photo is the attribution the licences ask for; keep `CREDITS.txt`.

The fetcher has been tested against a simulated Commons only. It has not run against the real site, so the picture lists may need one fix after the first run (it prints every title it could not find, skipped or kept). Check the preview before a demo.

## Known limits

- **v4.0 (session guard, calm mode, lag watchdog, helper layer) has not been run on a robot or in Choregraphe.** It is tested against a simulated robot (Python 2.7 and 3), the dialog file, the map file and a headless browser. On the robot, check: the log lines `greeting ignored`, `topic restart ignored` and `the robot is slow: tracking paused`; whether the lag is gone with Calm mode on (and whether it comes back with the box parameter "Calm mode" set to 0); and the "last heard" line in the Staff view. The idea that the dialog restarts its first proposal is a hypothesis from the code and the log; if Pepper still restarts, please save the log from that moment.
- The helper layer is offline rules and word matching, not a language model, and speech recognition only hears the words in the dialog.

- The carer alert is local. It shows on the tablet, flashes Pepper's eyes, and raises the ALMemory event `Pepper/CaregiverAlert`. Nobody is paged. A nurse call system can subscribe to that event.
- Pepper helps one person at a time. A second person joins the queue on the tablet.
- Speech recognition works best at 1 to 1.5 metres in a quiet room. While music or the saxophone plays, Pepper can mishear the sound as speech; for that reason only "stop" ends a song or a show by voice.
- The saxophone fix follows from the Choregraphe resource rules and the log, but it has not been run on a robot.
- **v3.9 (two answers per card, the choice lists that open by themselves) has not been run on a robot either.** Check that the list opens on the tablet at the moment Pepper starts asking.
- **v3.8 (Snakes and Ladders, the guitar removed, topic words before the name) has not been run on a robot or in Choregraphe either.** Check on the robot: that Pepper hears "activity" and "roll" in your room, that the dice and the walk on the tablet look right on its screen, and how long Pepper's spoken sentence takes against the walk.
- **v3.6 and v3.7 (Relive Malta questions, welcome, photos) have not been run on a robot or in Choregraphe either.** Pepper's reading speed, whether it understands the answer words in a real room (the tap always works), the tablet's own web view, and the dialog with the quiet card screen need one run on the robot.
- **v3.5 has not been run on a robot or in Choregraphe either.** The fixes address causes found by reading the code and the earlier robot log (the dialog sent each command twice, quiz speech started before the tablet showed the question, taps could answer a different question than the one on screen, and loose words could restart or switch activities). They are tested against a simulated robot and a headless browser. If a problem still happens, please save the robot log from the Choregraphe log view right after it happens.
