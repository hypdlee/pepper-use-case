# Care Controller v4 (Pepper Care Companion). Python 2.7 and 3 compatible.
#
# The dialog only writes plain ALMemory variables, never Dialog-box outputs:
#     $pepperCmd=<command>     $pepperName=<name>     $medMin / $medHour / $medPart (reminder details)
# This box polls those keys, clears them, and does the work: fires its own outputs (exercises, music,
# shows), stops everything, runs guided breathing, keeps patients / queue / medication reminders,
# and pushes the state to the tablet with ALTabletService.executeJS.
#
# v4.0: (1) SESSION GUARD. A greeting, "next person" or a group phrase no longer restarts the name question or an activity: the dialog only
#  reports it (hello, group, autostart) and this box decides. Nothing starts a new session while a person is being served or an
#  activity runs, a welcome that the dialog repeats by itself is swallowed, and the dialog is put back on the running quiz,
#  card or game. (2) CALM ROBOT. Face tracking is head only and stays with one person (FullyEngaged), movement and sound
#  distractions, face recognition and background movement are off, people perception runs once a second and only when the
#  crowd warning is on; a lag watchdog pauses tracking if the main loop slows down, and gives it back later.
#  (3) SMARTER, ALL ON THE ROBOT: needs and safety phrases alert the carer with the reason (fell, pain, toilet, drink...), help that
#  depends on what is happening, a suggestion that learns what was already done, the time and the day, jokes and Malta facts that
#  never repeat, and a "did you mean ...?" fallback that matches what was heard against the tiles. No cloud, nothing is sent out.
# v3.9: (1) Relive Malta has two answers per card ("Something else" is gone; the questions name both answers). (2) When Pepper asks
#  "Which one?" (music) or "Dance, a quiz, ...?" (activities) the dialog sends pickmusic / pickact and the tablet opens that list by
#  itself (state field pick); it closes when something is chosen, on stop or no, or after 3 minutes.
# v3.8: (1) the guitar is gone from Music (two boxes, their links, one output, the tile and the sound file). (2) Snakes and
#  Ladders, from the supplied game, is a new choice under Activities (tile token tileq, tablet command "snl"). The
#  controller owns the game: fair dice, exact roll to reach 100, Pepper moves straight after the resident, one spoken line per
#  round ($snlText, forced token snlsay or snlend). The tablet only shows it. The same safeguards as the quiz and the memory
#  cards: the tablet shows the round first, Pepper speaks when the dice have settled, a tap carries the game and the round it was
#  made on, a double tap does nothing, a spoken roll counts only after Pepper has finished, nothing speaks on a timer.
#  (3) Before a name is given, a topic word (activities, music, quiz, games...) starts that topic instead of being taken as a name.
# v3.7: every Relive Malta card now has ONE question with two answers (v3.9 removed "Something else") (touch, or by voice: one, two or
#  the answer word). Pepper gives ONE short reply to the answer and then waits quietly; only the first answer on a card counts, and
#  an answer made on another card or session, or during the reading, is ignored. What a resident chose is kept for the carer
#  ("Said: Pastizzi and tea: Ricotta"). The tablet shows 2 to 3 real photos per card when they were added (tools/fetch_photos.py).
#  Pepper's welcome menu now names all eight tiles of the home screen.
# v3.6 (fourth round): "My mood" (a camera reading of the face) is gone. In its place, tile "Relive Malta": ten reminiscence cards
#  (a picture, one warm sentence, two gentle prompts). The tablet shows a card first and Pepper reads it only when the tablet says
#  it is on screen; then Pepper is quiet and the resident (with a carer) talks. Next, Back, "I like this" and Stop, by touch;
#  next, back, repeat and stop by voice, and a spoken command only counts after Pepper has finished reading. "I like this" is kept
#  in the record for the carer. No question is a memory test, there are no timeouts that speak, and the cards come in a shuffled order.
#  Sections about mood were removed (Get Expression, the mood result inputs, the onMood output, moodWait, moodChecks).
#
# v3.5 (third round, after the first on-robot test of the quiz):
#  * The dialog sometimes sends the same command twice, seconds apart (every command appeared twice in the robot log), and
#    only the first 1.5 s were ignored. Now: an exercise that just started is not restarted by its own repeat, a second
#    "quiz" does not deal a new quiz, a second "alert" within a few seconds is the same one.
#  * Quiz: Pepper starts reading a question only after the tablet reported it is showing it (or QUIZ_ACK_S passed); taps carry
#    the question they were made on, so a tap on an old question is ignored instead of answering the new one; a spoken answer
#    only counts after Pepper has had time to read the options (an echo of "option one" or a repeated command cannot answer);
#    the state is sent before Pepper speaks. The spoken answer words (dynamic concepts) were removed: one, two, three only.
#  * The state carries "run" so a tablet page that stayed open across a restart does not ignore the new, lower sequence numbers.
#
# v3.4 (IEEE Malta Digital Health Hackathon 2026, second round):
#  * Quiz instead of football (see below). The Saxophone box no longer locks Speakers (map fix, see the map notes).
#
# v3.3 (IEEE Malta Digital Health Hackathon 2026):
#  * (removed in v3.6) a camera mood result was kept in the patient record and shown to staff.
#  * Carer alerts: each alert has an id and a Seen state; the tablet Staff view lists them and sends "ack".
#    An alert also stops any exercise, music or show at once, and raises the onAlert output (eye LEDs).
#  * Eight new tablet tiles: quiz, saxophone and one tile for each of the three songs (mood and guitar were removed later).
#  * clearData: staff can wipe every record held in memory (history, queue, reminders, alerts, typed names).
#  * (v3.4) Quiz (Activities, next to Dance): QUIZ_LEN questions drawn from QUIZ_BANK, never repeating until the whole bank was
#    used, answers shuffled every time. Pepper asks through the dialog (it speaks $quizText and listens for one, two or
#    three); the tablet shows the question and three big answer buttons. Either way the answer lands here (qa1..qa3 or
#    the tablet's quizAnswer) and the same code scores it.
#
# v3 (second on-robot test):
#  * ONE worker thread does all NAOqi work. Tablet events and the timelines' onStopped signals are only queued
#    by their callbacks (calling the tablet service from inside its own onJSEvent callback can deadlock it,
#    which looked like "after stopping an exercise nothing responds").
#  * No ALMotion.killAll (it kills every module's motion tasks); only the joints the exercises use are stopped,
#    and the return to Stand is posted (non-blocking).
#  * Each exercise lasts EXERCISE_SECONDS: a short timeline repeats, a long one is cut, then the next one.
#  * Guided breathing is called "breathing" everywhere: the old name sounded like "medication" to the recogniser.
import json
import os
import random
import threading
import time

try:
    import urllib2 as _urlreq                    # Python 2.7 on the robot
except ImportError:
    import urllib.request as _urlreq             # Python 3 (tests)

try:
    _UNICODE = unicode          # Python 2.7 on the robot
except NameError:               # Python 3 (tests)
    _UNICODE = None


def _s(x):
    """Plain byte string for NAOqi. On the robot (Python 2.7) text from the tablet's JSON is `unicode`, and NAOqi's C++
    calls (forceInput, logger.warning, insertData...) refuse it: "argument 1 of type 'std::string const &'"."""
    if _UNICODE is not None and isinstance(x, _UNICODE):
        return x.encode("utf-8")
    if isinstance(x, str):
        return x
    try:
        return str(x)
    except Exception:
        try:
            return repr(x)
        except Exception:
            return "?"


def _fmt(fmt, *args):
    """fmt % args with every argument made a byte string first, so it can never raise a Unicode error."""
    try:
        return fmt % tuple(_s(a) for a in args)
    except Exception:
        return _s(fmt)

VERSION = "4.1.1"
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
         "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30}
NUMWORD = dict((v, k) for k, v in WORDS.items())
TABLET_SAY = ("exercise", "music", "chat", "medication", "dance", "breathing", "help",
              "stop", "next", "next patient", "hello", "reminder",
              "relive", "activities", "snl", "quiz", "sax", "song1", "song2", "song3")
EXERCISE_SECONDS = 40.0   # every exercise lasts this long
MIN_REPEAT_S = 4.0        # a timeline that ends with less than this left is not restarted; Pepper holds still
ECHO_S = 1.5              # an onStopped this soon after a (re)start is the echo of a stop, not the end
DONE_GAP_S = 25.0         # after "well done", if the dialog does not start the next exercise, go idle
POSTURE_SPEED = 0.35      # return to Stand gently
REPEAT_GUARD_S = 1.5      # the same dialog command twice within this time is done once (the robot log showed every command twice)
MOVING_JOINTS = ["HeadYaw", "HeadPitch", "LShoulderPitch", "LShoulderRoll", "LElbowYaw", "LElbowRoll", "LWristYaw",
                 "RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "RWristYaw", "LHand", "RHand",
                 "HipRoll", "HipPitch", "KneePitch"]
ABILITIES = ("BackgroundMovement", "ListeningMovement", "SpeakingMovement")
TOKEN_KEY = "Pepper/CareControllerToken"   # the controller that started last owns the robot; older ones step down
POLL_KEYS = ["pepperName", "pepperCmd", "Pepper/TabletCmd", TOKEN_KEY]   # read together: one ALMemory call per tick
# Guided breathing: the tablet animation is generated from these same numbers (tools/extract_motion.py)
BREATHS = 5
BREATH_IN_RAD = 0.85      # shoulders raised to about 49 degrees while breathing in
BREATH_OUT_RAD = 1.45     # back down to about 83 degrees while breathing out
BREATH_IN_S = 4.0         # arm movement time, breathing in
BREATH_OUT_S = 5.0        # arm movement time, breathing out
BREATH_CUE_S = 1.5        # length of the spoken cue ("Breathe in.")
BREATH_IN_HOLD = 3.2      # wait after the spoken cue, breathing in
BREATH_OUT_HOLD = 4.5     # wait after the spoken cue, breathing out
# Song lengths in seconds (the song boxes have no "finished" output, so the controller times them)
SONG_SECONDS = {"1": 30.8, "2": 48.0, "3": 34.8}
# a tablet tile sends an opaque token the dialog handles from any point in the conversation (a plain word like "music"
# would be taken as a name while Pepper asks for one)
TILE_TOKENS = {"exercise": "tilea", "music": "tileb", "chat": "tilec", "medication": "tiled", "dance": "tilee",
               "breathing": "tilef", "reminder": "tileg", "help": "tileh",
               "relive": "tilei", "activities": "tilep", "snl": "tileq", "quiz": "tilek", "sax": "tilel",
               "song1": "tilem", "song2": "tilen", "song3": "tileo"}
MEM_ACK_S = 2.5           # Pepper waits this long for the tablet to say it shows the card, then reads it anyway
MEM_THINK_S = 0.8         # a tap this soon after a card appeared is a double tap (or aimed at the previous card)
MEM_READ_BASE_S = 1.5     # a spoken command counts only after this plus MEM_READ_WORD_S per spoken word since reading began
MEM_READ_WORD_S = 0.3
MEM_READ_MAX_S = 14.0
MEM_START_DUP_S = 15.0    # a second "relive" this soon, still on the first card, is the dialog repeating itself
MEM_IDLE_S = 600.0        # nobody touched anything for ten minutes: back to the tiles, without speaking
MEM_END_S = 90.0          # the closing card stays this long
MEM_CMDS = ("relive", "mnext", "mback", "mrepeat", "ma1", "ma2")      # dialog commands that belong to a running Relive Malta
MEM_LIKES_KEPT = 6
MEM_ANSWERS_KEPT = 6
# Relive Malta: (picture key, title, one warm sentence, prompt Pepper asks, prompt shown on screen, tip for the carer).
# Plain ASCII (Pepper's dialog needs it). No question tests the memory; none has a right answer. The words next, back, again,
# repeat, stop, thanks and done are not used in Pepper's own words, so its voice cannot trigger the voice commands.
# Each card: id, title, one sentence, ONE question, then two answers: (label, voice keywords, Pepper's one reply).
# There are only the two answers (v3.9: "Something else" was removed). The question names both answers, because Pepper reads only the
# question. Keywords must be unique over all cards (test_dialog checks the dialog file lists exactly these words), and neither the
# question nor a reply may contain a voice command word.
MEM_CARDS = [
    ("festa", "The village festa", "Bands, church bells and fireworks on a summer evening.",
     "At the festa, did you enjoy the band or the fireworks?",
     (("The band", ("band", "bands"), "The brass bands are wonderful. Such a happy sound."),
      ("The fireworks", ("fireworks", "firework"), "Fireworks light up the whole sky. What a night!"))),
    ("luzzu", "Colourful fishing boats", "Painted luzzu boats rest in the harbour, each with a bright eye on the bow.",
     "Did you go out on a boat, or watch from the shore?",
     (("On a boat", ("on a boat", "aboard", "sailed"), "Out on the water must have been special."),
      ("From the shore", ("shore", "watched", "from the shore"), "The shore is a lovely place to watch the colours."))),
    ("ferry", "The Gozo ferry", "A short ride over the blue water to the quiet island of Gozo.",
     "On the ferry, did you sit inside or out on the deck?",
     (("Inside", ("inside", "indoors"), "Cosy inside, and out of the wind."),
      ("On the deck", ("deck", "outside", "outdoors"), "The sea air on the deck is the best."))),
    ("pastizzi", "Pastizzi and tea", "Warm, flaky pastizzi and a hot cup of tea.",
     "Which pastizzi do you like best, ricotta or peas?",
     (("Ricotta", ("ricotta", "irkotta"), "Ricotta pastizzi are a favourite for many people."),
      ("Peas", ("peas", "pizelli"), "Peas pastizzi are a true classic."))),
    ("harbour", "The Grand Harbour", "Golden stone walls, church domes and boats in a wide, calm harbour.",
     "What do you like most, the old walls or the boats?",
     (("The old walls", ("walls", "fortress", "stone"), "Those golden walls have seen so much history."),
      ("The boats", ("boats", "ships"), "So many boats, busy all day."))),
    ("baker", "The baker and fresh bread", "The smell of warm Maltese bread early in the morning.",
     "Do you like fresh bread with tomato and oil, or with butter?",
     (("With tomato and oil", ("tomato", "tomatoes", "olive oil"), "Bread with tomato and oil is the Maltese classic."),
      ("With butter", ("butter",), "Warm bread with butter is hard to beat."))),
    ("crib", "Christmas time", "A little crib, candles and a bright star at Christmas.",
     "At Christmas, did you like the crib or the food best?",
     (("The crib", ("crib", "nativity"), "The little crib figures always bring a smile."),
      ("The food", ("food", "sweets", "dinner"), "Christmas food brings everyone together."))),
    ("carnival", "Carnival", "Bright costumes, masks and music in the street.",
     "At Carnival, did you like the costumes or the floats?",
     (("The costumes", ("costumes", "costume"), "Costumes are so colourful. Every year something new."),
      ("The floats", ("floats", "float", "parade"), "The big floats are a sight to see."))),
    ("beach", "A summer day at the beach", "Warm sand, a cool sea and a sunny sky.",
     "At the beach, did you prefer swimming or a quiet walk?",
     (("Swimming", ("swimming", "swim"), "A cool swim on a hot day is perfect."),
      ("A quiet walk", ("walk", "strolling"), "A walk by the sea clears the mind."))),
    ("balconies", "The street with colourful balconies", "Narrow streets with painted wooden balconies high above the doors.",
     "Did you sit on a balcony, or play down in the street?",
     (("On a balcony", ("balcony", "balconies"), "A balcony is a good seat for watching the street."),
      ("In the street", ("street", "played"), "Playing out in the street was the best fun."))),
]
MEM_OPEN = "Let's remember Malta together. "
MEM_FIRST_TAIL = " Take your time."
MEM_END_TEXT = "That was lovely. It was good to share your memories. Would you like to look at more?"
ALERTS_KEPT = 20

# ---- Snakes and Ladders (the board of the supplied game; the controller owns the game, the tablet only shows it)
SNL_LADDERS = {2: 23, 8: 34, 20: 41, 32: 68, 36: 57, 48: 74, 71: 91, 80: 99}
SNL_SNAKES = {29: 9, 38: 15, 47: 26, 62: 43, 77: 56, 86: 54, 94: 73, 97: 78}
SNL_EXACT = True          # an exact number is needed to reach 100 (a bigger number leaves the piece where it is)
SNL_ACK_S = 2.5           # Pepper waits this long for the tablet to say it shows the move, then speaks anyway
SNL_DICE_DELAY_S = 1.3    # after a move is on screen Pepper waits for the dice to settle before it says the result
SNL_THINK_S = 0.8         # a tap this soon after the board changed is a double tap
SNL_TAP_SLACK_S = 0.5     # a tap may come this much before the animation has finished (clocks of tablet and robot differ)
SNL_READ_BASE_S = 1.5     # a spoken command counts only after this plus SNL_READ_WORD_S per spoken word
SNL_READ_WORD_S = 0.3
SNL_READ_MAX_S = 16.0
SNL_START_DUP_S = 15.0    # a second "start" this soon, before anybody rolled, is the dialog repeating itself
SNL_IDLE_S = 600.0        # nobody did anything for ten minutes: back to the tiles, without speaking
SNL_END_S = 120.0         # the closing screen stays this long
SNL_MOVE_MS = 900         # a move on the tablet: the dice rolling ...
SNL_STEP_MS = 140         # ... plus this per square walked ...
SNL_SPECIAL_MS = 1100     # ... plus this for a ladder or a snake ...
SNL_GAP_MS = 450          # ... plus a pause before the next move
SNL_CMDS = ("snl", "sroll", "sskip", "snew", "srepeat")      # dialog commands that belong to a running game
PICK_CMDS = ("pickmusic", "pickact")      # the dialog asks "Which one?" (music) or "Dance, a quiz, ...?" (activities): the tablet opens that list
PICK_IDLE_S = 180.0                   # a list nobody used closes by itself (silently)
SNL_NUM = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
# Pepper's words: plain ASCII, and none of them is a voice command of the game (roll, skip, new game, repeat, stop, yes, no, thanks).
SNL_OPEN = "Let's play Snakes and Ladders! You go first. Say roll, or touch the dice."
SNL_YOU = ["You got a %s.", "A %s for you."]
SNL_ME = ["Now me. I got a %s.", "My go. I got a %s."]
SNL_YOUR_GO = "Your go!"
SNL_SKIPPED = "That is fine, I will go."
SNL_WIN_YOU = "You got a %s and reached 100! You win! Well played! Would you like another game?"
SNL_WIN_ME = "I got a %s and reached 100! That was fun. Would you like another game?"
SHOW_MAX_S = 45.0         # the longest routine is under 20 s: a show still "running" after this has lost its end signal
SHOWS = {"dance": "onDance", "sax": "onSax"}

# ---- v4.0: session guard, calm robot, smarter listening --------------------------------------------------------------
DASH_TIMEOUT_S = 2.0      # v4.1: the optional laptop dashboard. One post never waits longer than this, and never on the robot's main loop
DASH_MIN_GAP_S = 0.5      # at most two posts a second; the newest state wins
DASH_BEAT_S = 4.0         # an unchanged state is posted again this often, so the dashboard can tell the robot is alive
DASH_MAX_BACKOFF_S = 10.0
DIALOG_NAME = "activity"   # v4.1.1: the dialog topic (Activity_enu.top), compared in lower case without path and language
DIALOG_SUB = "CareControllerDialog"   # the name the controller subscribes to the dialog engine with when it has to start it itself
DIALOG_PONG = "ok4"        # what the dialog writes to dlgPong when it is forced "robotcmd ping" (the old v3.9 dialog has no such rule)
DIALOG_FIRST_S = 3.0       # the first voice check, this long after the controller started
DIALOG_WAIT_S = 3.0        # an answer may take this long
DIALOG_GAP_S = 1.0         # between a repair and the next check
DIALOG_TRIES = 3           # check, repair, check, harder repair, check, then give up and tell the staff
STARTUP_GREET_S = 6.0      # v4.0: if the dialog's own start message never arrived, the controller starts the welcome itself this long after it started
AUTOSTART_DUP_S = 30.0    # a topic restart this soon after a welcome is not a new person
GREET_DUP_S = 8.0         # a second greeting this soon is Pepper hearing its own voice or a repeat: nothing happens
LAG_SLOW_S = 0.8          # a main loop tick that took longer than this (it normally takes about 0.1 s) counts as slow
LAG_TICKS = 3             # this many slow ticks in a row: the robot is overloaded, tracking is paused
LAG_HOLD_S = 45.0         # tracking stays paused at least this long ...
LAG_OK_S = 0.4            # ... and comes back when the last LAG_OK_TICKS ticks were all faster than this
LAG_OK_TICKS = 10
CALM_OFF = ("BackgroundMovement", "ListeningMovement")      # autonomous abilities that stay off while the app runs in calm mode
PERCEPTION_MS = 1000      # people perception period (default 500): the crowd warning does not need more
NU_ESCALATE = 2           # the second "I did not understand" in a row points to the touch screen
HEARD_KEPT = 60
# Passive commands: they never end a running quiz, card session, game or list; the controller decides what (if anything) happens.
NEEDS = {"needfall": ("has fallen", True), "needpain": ("is in pain", True), "needdizzy": ("feels dizzy", True),
         "needbreath": ("has trouble breathing", True), "needtoilet": ("needs the toilet", False), "needdrink": ("would like a drink", False),
         "needfood": ("is hungry", False), "needcold": ("feels cold", False), "needhot": ("feels hot", False)}
PASSIVE_CMDS = ("hello", "group", "autostart", "helpme", "joke", "fact", "nu", "dmyes", "dmno", "moodlow") + tuple(sorted(NEEDS))
# What Pepper may suggest, in order of preference: (name of what was done, tile token, words for the suggestion, record key(s)).
SUGGEST = [("exercise", "tilea", "some gentle exercise", ("exercises",)),
           ("music", "tileb", "some music", ("music", "performances")),
           ("relive", "tilei", "memories of Malta", ("memCards",)),
           ("quiz", "tilek", "a little quiz", ("quizzes",)),
           ("snl", "tileq", "a game of snakes and ladders", ("snlGames",)),
           ("breathing", "tilef", "some calm breathing", ("breathing",)),
           ("dance", "tilee", "a dance", ("performances",)),
           ("chat", "tilec", "a chat", ())]
SUGGEST_CALM = ("breathing", "music", "relive", "chat")         # preferred when the person said they feel low
# What was heard, matched against the tiles when the dialog did not understand it: (name, tile token, spoken label, words).
INTENT_WORDS = [
    ("exercise", "tilea", "exercise", ("exercise", "exercises", "workout", "stretch", "stretching", "gym", "fitness", "move", "moving", "movement")),
    ("breathing", "tilef", "breathing", ("breathe", "breathing", "relax", "relaxing", "calm", "rest", "peaceful", "breath")),
    ("music", "tileb", "music", ("music", "song", "songs", "sing", "singing", "radio", "tune", "tunes", "melody", "listen")),
    ("activities", "tilep", "activities", ("activity", "activities", "game", "games", "fun", "entertain", "entertainment")),
    ("dance", "tilee", "a dance", ("dance", "dancing", "disco", "dances")),
    ("quiz", "tilek", "a quiz", ("quiz", "quizzes", "trivia", "questions", "puzzle", "puzzles")),
    ("snl", "tileq", "snakes and ladders", ("snakes", "ladders", "ladder", "dice", "board")),
    ("relive", "tilei", "memories of Malta", ("memories", "memory", "malta", "remember", "remembering", "reminisce", "photos", "pictures", "nostalgia")),
    ("chat", "tilec", "a chat", ("chat", "talk", "talking", "conversation", "story", "stories", "company", "lonely")),
    ("medication", "tiled", "your medicine", ("medicine", "medication", "medicines", "pills", "tablets", "tablet", "drugs")),
    ("reminder", "tileg", "a reminder", ("reminder", "reminders", "remind", "alarm")),
]
JOKES = ["Why did the robot go to the doctor? It had a screw loose!",
         "What do you call a robot that loves to dance? A disco bot!",
         "Why do bees have sticky hair? They use honeycombs!",
         "What did the ocean say to the shore? Nothing, it just waved!",
         "Why did the scarecrow win a prize? He was outstanding in his field!",
         "What is a robot's favourite snack? Computer chips!",
         "Why are fish so clever? They live in schools!",
         "What do you call a sleeping bull? A bulldozer!"]
FACTS = ["Valletta is the capital of Malta. It is one of the smallest capitals in Europe.",
         "Malta has three main islands: Malta, Gozo and Comino.",
         "Malta's old temples are older than the pyramids of Egypt.",
         "The colourful luzzu fishing boats have eyes painted on the bow, to watch over the fishermen.",
         "Mdina is called the Silent City, because its old streets are so quiet.",
         "A pastizz is a flaky pastry filled with ricotta or with peas. Many people eat one with tea.",
         "Every summer, villages in Malta hold a festa, with brass bands, church bells and fireworks.",
         "The Maltese language is the only Semitic language written in the Latin alphabet.",
         "Malta uses the euro, and English and Maltese are both official languages.",
         "The ferry from Cirkewwa to Gozo takes about twenty five minutes.",
         "Rabbit stew, called stuffat tal-fenek, is often called the national dish of Malta."]
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
ORDINALS = ("zero", "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth",
            "thirteenth", "fourteenth", "fifteenth", "sixteenth", "seventeenth", "eighteenth", "nineteenth", "twentieth",
            "twenty first", "twenty second", "twenty third", "twenty fourth", "twenty fifth", "twenty sixth", "twenty seventh",
            "twenty eighth", "twenty ninth", "thirtieth", "thirty first")
HOUR_WORDS = ("twelve", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven")


def dashboard_url(raw):
    """The box parameter "Dashboard URL" -> a clean base address, "" when it is empty (the dashboard link is off), or None when it is not a usable address."""
    t = _s(raw if raw is not None else "").strip()
    if not t:
        return ""
    if "://" not in t:
        t = "http://" + t
    if not (t.startswith("http://") or t.startswith("https://")):
        return None
    scheme, _, host = t.partition("://")
    host = host.rstrip("/")
    t = scheme + "://" + host
    if not host or host.startswith(":") or host.startswith("/") or any(c <= " " or c == "\\" or c == "?" or c == "#" for c in t):
        return None
    return t


def clock_words(hour, minute):
    """"about a quarter past ten in the morning": the time as Pepper says it (to the nearest five minutes)."""
    m5 = int(minute / 5.0 + 0.5) * 5
    h = hour
    if m5 == 60:
        m5, h = 0, (hour + 1) % 24
    nxt = HOUR_WORDS[(h + 1) % 12]
    cur = HOUR_WORDS[h % 12]
    core = {0: cur + " o'clock", 5: "five past " + cur, 10: "ten past " + cur, 15: "a quarter past " + cur, 20: "twenty past " + cur,
            25: "twenty five past " + cur, 30: "half past " + cur, 35: "twenty five to " + nxt, 40: "twenty to " + nxt,
            45: "a quarter to " + nxt, 50: "ten to " + nxt, 55: "five to " + nxt}[m5]
    if m5 == 0 and h == 0:
        return ("about " if m5 != minute else "") + "midnight"
    if m5 == 0 and h == 12:
        return ("about " if m5 != minute else "") + "twelve o'clock, midday"
    part = "in the morning" if 5 <= h < 12 else "in the afternoon" if 12 <= h < 18 else "in the evening" if 18 <= h < 23 else "at night"
    return ("about " if m5 != minute else "") + core + " " + part


def day_words(wday, mday, month):
    """"Sunday, the first of November" (wday 0 = Monday, month 1 = January, as in time.struct_time except the month)."""
    return "%s, the %s of %s" % (WEEKDAYS[wday % 7], ORDINALS[mday], MONTHS[month - 1])


def _similar(a, b):
    """True when two words are the same, or one is the other with another ending (exercise, exercising; music, musical), for words
    of four letters or more. A common beginning is not enough: lonely and lovely are different words."""
    if a == b:
        return True
    short = min(len(a), len(b))
    if short < 4:
        return False
    n = 0
    while n < short and a[n] == b[n]:
        n += 1
    return n >= max(4, short - 1)


def understand(text):
    """What did the person most likely mean? Matches the words heard against the tiles (exactly, or nearly). Returns
    (name, tile token, spoken label) of the one clear winner, or None when nothing matches or two things tie. Pure and offline."""
    words = []
    cur = ""
    for ch in _s(text).lower():
        if "a" <= ch <= "z" or ch == "'":
            cur += ch
        elif cur:
            words.append(cur)
            cur = ""
    if cur:
        words.append(cur)
    if not words:
        return None
    best, second, top = 0, 0, None
    for name, token, label, keys in INTENT_WORDS:
        score = 0
        for w in words:
            if any(_similar(w, k) for k in keys):
                score += 1
        if score > best:
            best, second, top = score, best, (name, token, label)
        elif score > second:
            second = score
    if top is None or best == second:
        return None
    return top

# ---- quiz
QUIZ_LEN = 5              # questions in one quiz
QUIZ_THINK_S = 1.0        # a tap this soon after a question appeared is a double tap (or aimed at the previous question)
QUIZ_ACK_S = 2.5          # Pepper waits this long for the tablet to say it shows the question, then reads it anyway
QUIZ_READ_BASE_S = 1.5    # a spoken answer counts only after this plus QUIZ_READ_WORD_S per spoken word since reading began
QUIZ_READ_WORD_S = 0.3
QUIZ_READ_MAX_S = 16.0
QUIZ_START_DUP_S = 15.0   # a second "quiz" this soon, still on the first question, is the dialog repeating itself
EXERCISE_DUP_S = 8.0      # the same exercise asked for again this soon after it started is a repeated command
ALERT_DUP_S = 8.0         # a second alert this soon is the same call for help
QUIZ_IDLE_S = 240.0       # nobody answered for this long: the quiz ends by itself
QUIZ_RESULT_S = 90.0      # the final score stays on the tablet this long
QUIZ_CMDS = ("quiz", "qa1", "qa2", "qa3", "qrepeat")     # dialog commands that belong to a running quiz
QUIZ_OK = ("Correct!", "Well done!", "That is right!", "Yes, that is right!", "Very good!")
QUIZ_NO = ("Not quite.", "Good try.", "Nearly.", "Not this time.")
QUIZ_END = ("Thank you for playing.", "Thank you for playing.", "Nice try!", "Good job!", "Very good!", "A perfect score! Wonderful!")
QUIZ_NUM = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
# Each row: question, the right answer, two wrong answers. ASCII only. Edit src/quiz_bank.py and run embed_bank.py.
# <<QUIZ_BANK
QUIZ_BANK = [
    ('What is the capital city of Malta?', 'Valletta', 'Mdina', 'Sliema'),
    ('Which island is the sister island of Malta?', 'Gozo', 'Crete', 'Sicily'),
    ('What money is used in Malta?', 'The euro', 'The pound', 'The dollar'),
    ('Which languages are official in Malta?', 'Maltese and English', 'Italian and French', 'Spanish and Greek'),
    ('Which sea is Malta in?', 'The Mediterranean', 'The North Sea', 'The Red Sea'),
    ('Malta is south of which country?', 'Italy', 'Spain', 'Norway'),
    ('Which Maltese island is famous for the Blue Lagoon?', 'Comino', 'Gozo', 'Filfla'),
    ('Which old Maltese town is called the Silent City?', 'Mdina', 'Marsaxlokk', 'Birgu'),
    ('What are the colourful Maltese fishing boats called?', 'Luzzu', 'Gondola', 'Kayak'),
    ('Which Maltese snack is a flaky pastry filled with ricotta or peas?', 'Pastizzi', 'Pizza', 'Lasagne'),
    ('Kinnie is a famous Maltese what?', 'Soft drink', 'Cheese', 'Bread'),
    ('Which Maltese sweet pastry is filled with dates?', 'Imqaret', 'Pastizzi', 'Ftira'),
    ("Malta's national dish is a stew made from which animal?", 'Rabbit', 'Goat', 'Duck'),
    ('Ftira is a type of what?', 'Bread', 'Soup', 'Cake'),
    ('What colours are on the Maltese flag?', 'White and red', 'Blue and yellow', 'Green and white'),
    ('Which cross is in the corner of the Maltese flag?', 'The George Cross', 'The Red Cross', 'The Iron Cross'),
    ('Which Maltese town has a famous church with a huge round dome?', 'Mosta', 'Marsa', 'Zurrieq'),
    ('Which knights ruled Malta for over 250 years?', 'The Knights of St John', 'The Knights of the Round Table', 'The Viking knights'),
    ('Which famous Maltese festival takes place before Lent, with colourful floats?', 'Carnival', 'Easter', 'Christmas'),
    ('What do Maltese villages light up in the sky during a festa?', 'Fireworks', 'Kites', 'Balloons'),
    ('What is the main town of Gozo called?', 'Victoria', 'Valletta', 'Birgu'),
    ('What does the Maltese word Bongu mean?', 'Good morning', 'Goodbye', 'Thank you'),
    ('What is the Maltese word for thank you?', 'Grazzi', 'Bongu', 'Skuzi'),
    ('A festa in Malta is a village what?', 'Feast', 'Market', 'School'),
    ('Marsaxlokk is a fishing village famous for its Sunday market selling what?', 'Fish', 'Shoes', 'Books'),
    ('Which island country lies just south of Sicily?', 'Malta', 'Cyprus', 'Iceland'),
    ('Which saint is said to have been shipwrecked on Malta?', 'Saint Paul', 'Saint Peter', 'Saint Francis'),
    ('Malta has ancient temples older than which famous monuments?', 'The Egyptian pyramids', 'The Eiffel Tower', 'Big Ben'),
    ('Which small white dog breed is named after Malta?', 'The Maltese', 'The Beagle', 'The Poodle'),
    ('What are the colourful closed wooden balconies of Malta called?', 'Gallarija', 'Luzzu', 'Ftira'),
    ('Which flower is a symbol of remembrance in November?', 'The poppy', 'The rose', 'The tulip'),
    ('Which animal is known as the king of the jungle?', 'The lion', 'The tiger', 'The elephant'),
    ('What do spiders spin to catch insects?', 'A web', 'A nest', 'A hive'),
    ('Which of these birds cannot fly?', 'The penguin', 'The eagle', 'The swan'),
    ('Which British queen reigned for seventy years?', 'Queen Elizabeth', 'Queen Victoria', 'Queen Anne'),
    ('Which is the largest animal on land?', 'The elephant', 'The giraffe', 'The horse'),
    ('Which city in Italy is famous for its canals and gondolas?', 'Venice', 'Florence', 'Naples'),
    ('Which animal is famous for its very long neck?', 'The giraffe', 'The hippo', 'The rhino'),
    ('What does a caterpillar turn into?', 'A butterfly', 'A beetle', 'A bird'),
    ('Which tree do acorns grow on?', 'The oak', 'The pine', 'The palm'),
    ('Which fruit is dried to make raisins?', 'Grapes', 'Plums', 'Apples'),
    ('Olive oil is made from what?', 'Olives', 'Lemons', 'Nuts'),
    ('In which season do the leaves fall from the trees?', 'Autumn', 'Spring', 'Summer'),
    ('Which is the largest ocean?', 'The Pacific', 'The Atlantic', 'The Indian'),
    ('Which animal gives us wool?', 'The sheep', 'The pig', 'The hen'),
    ('Which is the fastest land animal?', 'The cheetah', 'The lion', 'The horse'),
    ('What is a group of lions called?', 'A pride', 'A flock', 'A herd'),
    ('Which insect lives in a hive?', 'The bee', 'The ant', 'The ladybird'),
    ('Which animal has a trunk?', 'The elephant', 'The camel', 'The bear'),
    ('What do giant pandas mostly eat?', 'Bamboo', 'Fish', 'Honey'),
    ('Which sea creature walks sideways?', 'A crab', 'A frog', 'A snail'),
    ('Which bird is a symbol of peace?', 'The dove', 'The eagle', 'The owl'),
    ('Which meal do we eat in the morning?', 'Breakfast', 'Dinner', 'Supper'),
    ('What is bread mainly made from?', 'Flour', 'Sugar', 'Rice'),
    ('Coffee is made from what?', 'Beans', 'Leaves', 'Roots'),
    ('Which vegetable can make you cry when you cut it?', 'The onion', 'The carrot', 'The potato'),
    ('Which food is made from milk?', 'Cheese', 'Bread', 'Rice'),
    ('Dried plums are called what?', 'Prunes', 'Raisins', 'Dates'),
    ('What is chocolate made from?', 'Cocoa', 'Honey', 'Rice'),
    ('Pasta comes from which country?', 'Italy', 'Japan', 'Brazil'),
    ('Sushi comes from which country?', 'Japan', 'India', 'Spain'),
    ('Paella comes from which country?', 'Spain', 'Norway', 'Egypt'),
    ('Which fruit is said to keep the doctor away?', 'An apple', 'A banana', 'A melon'),
    ('Which fruit is yellow and sour?', 'A lemon', 'A plum', 'A grape'),
    ('What do we use to tell the time?', 'A clock', 'A ruler', 'A compass'),
    ('Who bakes bread?', 'A baker', 'A tailor', 'A plumber'),
    ('Where can you borrow books?', 'A library', 'A bakery', 'A pharmacy'),
    ('Who looks after your teeth?', 'A dentist', 'A baker', 'A pilot'),
    ('Who flies an aeroplane?', 'A pilot', 'A sailor', 'A driver'),
    ('In which month is Christmas?', 'December', 'October', 'August'),
    ('Which holiday is famous for eggs made of chocolate?', 'Easter', 'Halloween', 'New Year'),
    ('Who gives out medicine in a pharmacy?', 'A pharmacist', 'A baker', 'A pilot'),
    ('What is the capital of France?', 'Paris', 'Lyon', 'Rome'),
    ('What is the capital of Italy?', 'Rome', 'Milan', 'Venice'),
    ('What is the capital of Spain?', 'Madrid', 'Barcelona', 'Seville'),
    ('What is the capital of Germany?', 'Berlin', 'Munich', 'Hamburg'),
    ('What is the capital of Norway?', 'Oslo', 'Bergen', 'Stockholm'),
    ('What is the capital of the United Kingdom?', 'London', 'Dublin', 'Cardiff'),
    ('What is the capital of Greece?', 'Athens', 'Rome', 'Cairo'),
    ('What is the capital of Egypt?', 'Cairo', 'Lagos', 'Athens'),
    ('What is the highest mountain on Earth?', 'Mount Everest', 'Mont Blanc', 'Kilimanjaro'),
    ('On which continent is Egypt?', 'Africa', 'Asia', 'Europe'),
    ('Which is the largest country in the world by area?', 'Russia', 'Canada', 'China'),
    ('Which river runs through London?', 'The Thames', 'The Seine', 'The Danube'),
    ('Which river runs through Paris?', 'The Seine', 'The Thames', 'The Rhine'),
    ('Which country is famous for its pyramids?', 'Egypt', 'Norway', 'Italy'),
    ('Which country is famous for its tulips?', 'The Netherlands', 'Spain', 'Norway'),
    ('Which Italian city has a famous leaning tower?', 'Pisa', 'Rome', 'Venice'),
    ('Which famous tower is in Paris?', 'The Eiffel Tower', 'Big Ben', 'The Leaning Tower'),
    ('In which city is Big Ben?', 'London', 'Paris', 'Madrid'),
    ('Which ocean lies between Europe and America?', 'The Atlantic', 'The Pacific', 'The Arctic'),
    ('Which planet is known as the Red Planet?', 'Mars', 'Venus', 'Jupiter'),
    ('Which is the biggest planet in our solar system?', 'Jupiter', 'Saturn', 'Mars'),
    ('What is the name of our galaxy?', 'The Milky Way', 'Andromeda', 'The Sombrero'),
    ('Which language do people speak in Brazil?', 'Portuguese', 'Spanish', 'French'),
    ('Which language do people speak in Austria?', 'German', 'Italian', 'Dutch'),
    ('Who painted the Mona Lisa?', 'Leonardo da Vinci', 'Picasso', 'Van Gogh'),
    ('Who wrote Romeo and Juliet?', 'William Shakespeare', 'Charles Dickens', 'Jane Austen'),
    ('Which band sang Yesterday and Let It Be?', 'The Beatles', 'Queen', 'ABBA'),
    ('Which singer is called the King of Rock and Roll?', 'Elvis Presley', 'Frank Sinatra', 'Louis Armstrong'),
    ('Which instrument is played with a bow?', 'The violin', 'The trumpet', 'The piano'),
    ('Who composed the opera The Magic Flute?', 'Mozart', 'Verdi', 'Wagner'),
    ('Which instrument has black and white keys?', 'The piano', 'The flute', 'The drum'),
    ('Which family of instruments does the saxophone belong to?', 'Woodwind', 'Brass', 'Strings'),
    ('Which Italian composer wrote The Four Seasons?', 'Vivaldi', 'Mozart', 'Beethoven'),
    ('Who wrote the piano piece called Fur Elise?', 'Beethoven', 'Mozart', 'Chopin'),
    ('Who wrote the story Oliver Twist?', 'Charles Dickens', 'William Shakespeare', 'Leo Tolstoy'),
    ('Who painted the picture called Sunflowers?', 'Van Gogh', 'Monet', 'Picasso'),
    ('What did the Wright brothers invent?', 'The aeroplane', 'The telephone', 'The bicycle'),
    ('In which city is the Colosseum?', 'Rome', 'Athens', 'Paris'),
    ('Which famous ship sank in 1912?', 'The Titanic', 'The Mayflower', 'The Victory'),
    ('Which American astronaut said a giant leap for mankind on the Moon?', 'Neil Armstrong', 'Yuri Gagarin', 'John Glenn'),
    ('Who wrote the Harry Potter books?', 'J. K. Rowling', 'Roald Dahl', 'Enid Blyton'),
    ('What do you wear on your wrist to tell the time?', 'A watch', 'A ring', 'A belt'),
    ('Which meal is eaten in the middle of the day?', 'Lunch', 'Breakfast', 'Supper'),
    ('Which month comes right after June?', 'July', 'May', 'August'),
    ('Which month has the fewest days?', 'February', 'March', 'April'),
    ('Which day of the week comes after Friday?', 'Saturday', 'Thursday', 'Sunday'),
    ('Which day is often called the day of rest?', 'Sunday', 'Monday', 'Wednesday'),
    ('Which shape has four equal sides and four corners?', 'A square', 'A triangle', 'A circle'),
    ('Which animal is known for its black and white stripes?', 'The zebra', 'The leopard', 'The elephant'),
    ('What appears in the sky when the sun shines through the rain?', 'A rainbow', 'A shooting star', 'A tornado'),
    ('Which small insect is red with black spots?', 'The ladybird', 'The bee', 'The ant'),
    ('Which bird lays the eggs we eat most often?', 'The hen', 'The swan', 'The owl'),
    ('Which fruit has a thick orange skin and is full of juice?', 'An orange', 'A pear', 'A plum'),
    ('Which vegetable is orange and said to be good for your eyes?', 'The carrot', 'The potato', 'The onion'),
    ('Which fruit grows in bunches on a vine and is used to make wine?', 'Grapes', 'Bananas', 'Cherries'),
    ('What happens to water when it gets very cold?', 'It turns to ice', 'It turns to steam', 'It turns to sand'),
    ('What do we call the water that falls from clouds?', 'Rain', 'Dust', 'Smoke'),
    ('In which direction does the sun rise?', 'East', 'West', 'North'),
    ('Which star is closest to the Earth?', 'The Sun', 'Sirius', 'The North Star'),
    ('On which planet do we live?', 'Earth', 'Mars', 'Venus'),
    ('Which part of the body pumps blood around the body?', 'The heart', 'The lung', 'The liver'),
    ('Which sense do you use your nose for?', 'Smell', 'Taste', 'Hearing'),
    ('Which metal is liquid at room temperature?', 'Mercury', 'Iron', 'Gold'),
    ('What colour do you make by mixing blue and yellow?', 'Green', 'Purple', 'Orange'),
    ('What colour do you make by mixing red and white?', 'Pink', 'Brown', 'Grey'),
    ('In which sport do players kick a ball into a net, with a goalkeeper?', 'Football', 'Tennis', 'Golf'),
    ('In which sport do you hit a shuttlecock?', 'Badminton', 'Golf', 'Rugby'),
    ('Which sport is played at Wimbledon?', 'Tennis', 'Cricket', 'Golf'),
    ('Which sport is played on ice with sticks and a puck?', 'Ice hockey', 'Rugby', 'Cricket'),
    ('Which sport uses a bat, a ball and wickets?', 'Cricket', 'Golf', 'Boxing'),
    ('Which country has won the football World Cup the most times?', 'Brazil', 'Italy', 'France'),
    ('What colour card does a football referee show to send a player off?', 'Red', 'Blue', 'Green'),
    ('In which sport can you score a try?', 'Rugby', 'Tennis', 'Golf'),
    ('In which sport do players shoot at a hoop with a net?', 'Basketball', 'Football', 'Hockey'),
]
# QUIZ_BANK>>


class MyClass(GeneratedClass):
    def __init__(self):
        GeneratedClass.__init__(self)

    # ------------------------------------------------------------------ lifecycle
    def onLoad(self):
        self.running = False
        self.thread = None
        self.px = {}
        self.clock = time.time
        self.sleep = time.sleep
        self.inbox = []
        self.inboxLock = threading.Lock()
        self.current = None
        self.history = []
        self.queue = []
        self.reminders = []
        self.alerts = []
        self.alertId = 0
        self.quiz = None              # the quiz being played (or just finished), see _quizStart
        self.quizDeck = []            # question numbers not asked yet: a whole bank is dealt before any question comes back
        self.rnd = random.Random()
        self.lastAlertAt = -1000.0
        self.lastAlertReason = ""
        self.quizSerial = 0
        self.mem = None               # the Relive Malta session being shown, see _memStart
        self.introduced = False       # True once the first person has started a session (the welcome names every topic)
        self.memSerial = 0
        self.snl = None               # the Snakes and Ladders game being shown, see _snlStart
        self.snlSerial = 0
        self.pick = None              # the choice list the tablet shows because Pepper asked: {"k", "which", "at"}
        self.pickSerial = 0
        self.perf = time.time          # real elapsed time, for the lag watchdog (tests replace it)
        self.lastTickAt = None
        self.slowTicks = 0
        self.fastTicks = 0
        self.lagMode = False
        self.lagSince = 0.0
        self.calm = False
        self.undo = []                 # (proxy, setter, args) that put the robot's settings back when the app stops
        self.lastGreet = -1000.0
        self.startAt = None            # when this controller started (for the start-up welcome)
        self.dashUrl = ""              # v4.1: laptop dashboard base address ("" = off)
        self.dashBody = None           # the newest state as JSON text, waiting to be posted
        self.dashEvt = threading.Event()
        self.dashThread = None
        self.dashDown = False
        self.dashFails = 0
        self.dashLastSent = 0.0
        self.dashSent = 0
        self.startGreeted = False
        self.voiceOk = None            # v4.1.1: None = not checked yet, True = the dialog answered, False = it never did (staff are told)
        self.dlgTry = 0                # voice checks sent so far (see _dialogStep)
        self.dlgSettle = False
        self.dlgAt = 0.0
        self.dlgSub = False            # this controller subscribed the dialog engine
        self.dlgSubName = _fmt("%s%d", DIALOG_SUB, id(self) % 100000)    # one name per controller, so one stopping never ends the other's subscription
        self.dlgOwn = None             # name of a topic this controller loaded itself (it unloads it again when it stops)
        self.heard = ""                # the last thing the robot heard (staff view only)
        self.heardUsed = ""
        self.nuCount = 0
        self.dm = None                 # what "did you mean" asked about
        self.sugg = None               # what Pepper suggested: {"name", "token"}
        self.suggTried = []
        self.jokeDeck = []
        self.factDeck = []
        self.clockKey = ""
        self.mode = None
        self.exIndex = 0
        self.exStart = 0.0
        self.exEnds = 0.0
        self.exRunStart = 0.0
        self.exPhase = None
        self.exSeconds = EXERCISE_SECONDS
        self.breath = None
        self.breathCount = BREATHS
        self.bodyBusy = False
        self.musicEnds = 0.0
        self.showStart = 0.0
        self.current_item = ""        # the song or routine now playing ("song2", "dance"...)
        self.showRunning = False      # a song box was started and not stopped since: the original box keeps its own
                                      # "running" flag until it is stopped, and stopping it then reports an end (an echo)
        self.expectEcho = 0           # ends still to come from boxes we stopped (not the end of the new one)
        self.echoUntil = 0.0
        self.dueId = None
        self.lastCmd = ""
        self.lastRaw = ""
        self.lastRawAt = 0.0
        self.seenTablet = []
        self.extraNames = []
        self.seq = 0
        self.lastPush = 0.0
        self.lastFull = 0.0
        self.lastKey = ""
        self.lastCrowdCheck = 0.0
        self.crowdSince = None
        self.crowdLast = None
        self.nextRid = 1
        self.calling = None
        self.token = None             # set on start; see TOKEN_KEY
        self.jsq = []                 # tablet calls waiting for the sender thread (in order)
        self.jsLock = threading.Lock()
        self.jsThread = None

    def onUnload(self):
        self._halt()

    def onInput_onStart(self):
        # nothing may raise out of a box input: on the robot an error there ends the whole behaviour
        try:
            if self.running:
                return
            self.running = True
            # a controller left running by an earlier (crashed) run sees this token and steps down: two controllers
            # polling the same keys would run every command twice and double the tablet traffic (lag)
            self.token = _fmt("%s-%s", repr(time.time()), id(self))
            self._write(TOKEN_KEY, self.token)
            self._write("pepperCmd", "")              # cleared BEFORE the slow tablet and robot-settings work below, so the dialog's first
            self._write("pepperName", "")             # message (autostart) cannot arrive early and then be wiped
            self._write("Pepper/TabletCmd", "")       # every polled key exists, so one getListData call always works
            self._write("medNext", "not set")
            self.startAt = self.clock()
            self.startGreeted = False
            self.voiceOk = None
            self.dlgTry = 0
            self._logRunning()
            self._connectTablet()
            self._tune()
            self._log("info", _fmt("[Care Controller] v%s running", VERSION))
            # tablet calls go through their own thread: a slow tablet never delays what Pepper does
            self.jsThread = threading.Thread(target=self._jsLoop)
            self.jsThread.daemon = True
            self.jsThread.start()
            self._dashStart()
            self._push(force=True)
            self.thread = threading.Thread(target=self._loop)
            self.thread.daemon = True
            self.thread.start()
        except Exception as e:
            self._log("error", _fmt("[Care Controller] start failed (%s)", e))

    def onInput_onStop(self):
        try:
            self._halt()
        except Exception as e:
            self._log("error", _fmt("[Care Controller] stop failed (%s)", e))
        try:
            self.onStopped()
        except Exception:
            pass

    def _halt(self):
        self.running = False
        self.dashEvt.set()                           # lets the dashboard sender end at once
        pp = self.px.get("ALPeoplePerception")
        if pp is not None:
            try:
                pp.unsubscribe("CareController")
            except Exception:
                pass
        self._dialogRelease()
        self._untune()

    # ------------------------------------------------------------------ the voice engine (v4.1.1)
    # The robot log showed the dialog box failing to start ("topic ... is already loaded", left over from an earlier run) while the
    # controller and the tablet worked: Pepper stayed silent. The controller now asks the dialog "robotcmd ping" a few seconds after it
    # started. A dialog that is running answers by writing dlgPong. If it does not, the controller looks at the engine, starts or reloads
    # the topic itself, asks again, and as a last resort tells the staff on the tablet (and out loud) that the voice is not ready.
    @staticmethod
    def _topicKey(name):
        t = str(name).strip().replace("\\", "/").split("/")[-1].lower()
        if t.endswith(".top"):
            t = t[:-4]
        if t.endswith("_enu"):
            t = t[:-4]
        return t.lstrip("~")

    def _topicList(self, method):
        """Names the dialog engine reports (all loaded or all activated topics); None when it cannot be asked."""
        d = self._p("ALDialog")
        if d is None:
            return None
        try:
            r = getattr(d, method)()
        except Exception as e:
            self._log("warning", _fmt("[Care Controller] ALDialog.%s failed (%s)", method, e))
            return None
        try:
            return [str(x) for x in (r or [])]
        except Exception:
            return None

    def _ourTopics(self, names):
        return [n for n in (names or []) if self._topicKey(n) == DIALOG_NAME]

    def _topicPath(self):
        """Where Activity_enu.top lives on the robot (next to the behaviour folder), or None."""
        try:
            fm = self._p("ALFrameManager")
            base = fm.getBehaviorPath(self.behaviorId) if fm is not None else None
            if not base:
                return None
            return os.path.normpath(os.path.join(str(base), "..", "Activity", "Activity_enu.top"))
        except Exception:
            return None

    def _logRunning(self):
        """One log line naming the behaviours that run right now: two copies of this app at once was one cause of the silence."""
        names = self._call("ALBehaviorManager", "getRunningBehaviors")
        try:
            names = sorted([str(n) for n in (names or [])])
        except Exception:
            return
        self._log("info", _fmt("[Care Controller] running behaviours: %s", ", ".join(names) if names else "none listed"))
        mine = [n for n in names if self._topicKey(n).startswith("behavior_1") or "care" in n.lower() or "choregraphe" in n.lower()]
        if len(mine) > 1:
            self._log("warning", _fmt("[Care Controller] more than one copy of the app seems to be running (%s): stop all behaviours and start one", ", ".join(mine)))

    def _dialogStep(self):
        """Called every tick until the voice check is finished."""
        if self.voiceOk is not None or self.startAt is None:
            return
        now = self.clock()
        if self.dlgTry == 0:
            if now - self.startAt >= DIALOG_FIRST_S:
                self._dialogProbe(now)
            return
        if self.dlgSettle:                           # a repair was just done: a moment later, ask again
            if now - self.dlgAt >= DIALOG_GAP_S:
                self._dialogProbe(now)
            return
        if self._read("dlgPong") == DIALOG_PONG:
            self._dialogAnswered("repaired" if self.dlgTry > 1 else "first check")
            return
        if now - self.dlgAt < DIALOG_WAIT_S:
            return
        if self.dlgTry >= DIALOG_TRIES:
            self._dialogFailed()
            return
        self._dialogRepair(self.dlgTry)
        self.dlgSettle = True
        self.dlgAt = now

    def _dialogProbe(self, now):
        self._write("dlgPong", "")
        self.dlgTry += 1
        self.dlgAt = now
        self.dlgSettle = False
        self._force("robotcmd ping")

    def _dialogAnswered(self, how):
        self.voiceOk = True
        self._log("info", _fmt("[Care Controller] the dialog answers (%s): the voice is ready", how))

    def _dialogRepair(self, n):
        """The dialog did not answer. Look at the engine first (and write what it says to the log), then put it right:
        first try: a topic that is loaded but not active is activated and the engine is started;
        second try: the topic is unloaded and loaded again from the file (an old copy of it may be what is running)."""
        d = self._p("ALDialog")
        if d is None:
            return
        loaded, active = self._topicList("getAllLoadedTopics"), self._topicList("getActivatedTopics")
        self._log("warning", _fmt("[Care Controller] the dialog did not answer (try %d). Loaded topics: %s. Active topics: %s",
                                  n, ", ".join(loaded) if loaded else "none", ", ".join(active) if active else "none"))
        ours = self._ourTopics(loaded)
        act = self._ourTopics(active)
        if n >= 2:
            path = self._topicPath()
            if path is not None:
                for nm in ours:
                    self._dlgDo("deactivateTopic", nm)
                    self._dlgDo("unloadTopic", nm)
                got = self._dlgDo("loadTopic", _s(path))
                nm = str(got) if got else None
                if nm:
                    self.dlgOwn = nm
                    self._log("info", _fmt("[Care Controller] the dialog topic was loaded again from %s", path))
                    ours, act = [nm], []
            else:
                self._log("warning", "[Care Controller] the dialog topic cannot be reloaded: the app folder is not known")
                for nm in act:
                    self._dlgDo("deactivateTopic", nm)
                act = []
        if ours and not act:
            self._dlgDo("activateTopic", ours[0])
        if ours:
            if self._dlgDo("subscribe", self.dlgSubName) is not False:
                self.dlgSub = True

    def _dlgDo(self, method, arg):
        """One call to the dialog engine. Returns what it returned, or False when it failed (never raises)."""
        d = self._p("ALDialog")
        if d is None:
            return False
        try:
            r = getattr(d, method)(arg)
            return True if r is None else r
        except Exception as e:
            self._log("warning", _fmt("[Care Controller] ALDialog.%s(%s) failed (%s)", method, arg, e))
            return False

    def _dialogFailed(self):
        self.voiceOk = False
        self._log("error", "[Care Controller] the dialog never answered: Pepper cannot speak. Stop all behaviours on Pepper, then start the app once")
        self._post("ALTextToSpeech", "say", "My voice is not ready. Please ask a helper to restart me.")

    def _dialogRelease(self):
        """What this controller started in the dialog engine, it ends again, so the next start finds it clean."""
        d = self.px.get("ALDialog")
        if d is None:
            return
        if self.dlgSub:
            self.dlgSub = False
            try:
                d.unsubscribe(self.dlgSubName)
            except Exception:
                pass
        if self.dlgOwn:
            nm, self.dlgOwn = self.dlgOwn, None
            owner = self._read(TOKEN_KEY)
            if owner and self.token is not None and owner != self.token:
                return                       # a newer controller runs now and may be using this topic: leave it loaded
            for m in ("deactivateTopic", "unloadTopic"):
                try:
                    getattr(d, m)(nm)
                except Exception:
                    pass

    # ------------------------------------------------------------------ NAOqi access (all failures are soft)
    def _log(self, level, msg):
        """Logging can never raise (NAOqi's logger only takes a plain byte string)."""
        try:
            getattr(self.logger, level)(_s(msg))
        except Exception:
            pass

    def _p(self, name):
        if name not in self.px:
            try:
                self.px[name] = ALProxy(name)
            except Exception as e:
                self.px[name] = None
                self._log("warning", _fmt("[Care Controller] no %s (%s)", name, e))
        return self.px[name]

    def _read(self, key):
        m = self._p("ALMemory")
        if m is None:
            return ""
        try:
            v = m.getData(key)
        except Exception:
            return ""
        if v is None:
            return ""
        return v if isinstance(v, str) else (str(v) if not hasattr(v, "encode") else v.encode("utf-8"))

    def _write(self, key, value):
        m = self._p("ALMemory")
        if m is not None:
            try:
                m.insertData(_s(key), _s(value) if isinstance(value, str) or (_UNICODE is not None and isinstance(value, _UNICODE)) else value)
            except Exception as e:
                self._log("warning", _fmt("[Care Controller] insertData %s failed (%s)", key, e))

    def _force(self, text):
        d = self._p("ALDialog")
        if d is None:
            return False
        try:
            d.forceInput(_s(text))
            return True
        except Exception as e:
            self._log("warning", _fmt("[Care Controller] forceInput '%s' failed (%s)", text, e))
            return False

    def _call(self, proxy, method, *args):
        p = self._p(proxy)
        if p is None:
            return None
        try:
            return getattr(p, method)(*args)
        except Exception as e:
            self._log("warning", _fmt("[Care Controller] %s.%s failed (%s)", proxy, method, e))
            return None

    def _post(self, proxy, method, *args):
        """Non-blocking NAOqi call (proxy.post.method): the worker never waits for a movement to finish."""
        p = self._p(proxy)
        if p is None:
            return None
        try:
            return getattr(p.post, method)(*args)
        except Exception as e:
            self._log("warning", _fmt("[Care Controller] %s.post.%s failed (%s)", proxy, method, e))
            return None

    def _fire(self, output):
        try:
            getattr(self, output)()
        except Exception as e:
            self._log("warning", _fmt("[Care Controller] output %s failed (%s)", output, e))

    # ------------------------------------------------------------------ events from other threads: queue only
    def _enqueue(self, kind, data=None):
        """Called from box inputs and NAOqi callbacks: it can never raise (an error there ends the whole behaviour)."""
        try:
            t = self.clock()
        except Exception:
            t = 0.0
        try:
            self.inboxLock.acquire()
            try:
                self.inbox.append((kind, data, t))
                self.inbox = self.inbox[-200:]
            finally:
                self.inboxLock.release()
        except Exception:
            pass

    def onInput_onMotionDone(self):
        """Wired to onStopped of the nine exercise timelines. Queued; handled by the worker."""
        self._enqueue("motionDone")

    def onInput_onShowDone(self):
        """Wired to onStopped of the dance and saxophone routines and of the songs. Queued."""
        self._enqueue("showDone")

    def onTablet(self, raw):
        """ALTabletService.onJSEvent callback. Queued: no NAOqi call may happen on this thread."""
        self._enqueue("tablet", raw)

    def _drain(self):
        self.inboxLock.acquire()
        try:
            items, self.inbox = self.inbox, []
        finally:
            self.inboxLock.release()
        for kind, data, t in items:
            try:
                if kind == "tablet":
                    self._tablet(data)
                elif kind == "motionDone":
                    self._motionDone(t)
                elif kind == "showDone":
                    self._showDone(t)
            except Exception as e:
                self._log("error", _fmt("[Care Controller] %s event failed (%s)", kind, e))

    # ------------------------------------------------------------------ main loop (the only thread that calls NAOqi)
    def _loop(self):
        while self.running:
            try:
                self.tick()
            except Exception as e:
                self._log("error", _fmt("[Care Controller] tick error (%s)", e))
            self.sleep(0.1)

    def _readKeys(self, keys):
        """Several ALMemory keys in ONE call (getListData) instead of one call each; falls back if unavailable."""
        m = self._p("ALMemory")
        if m is None:
            return [""] * len(keys)
        try:
            vals = list(m.getListData(keys))
            if len(vals) != len(keys):
                raise ValueError("size")
        except Exception:
            return [self._read(k) for k in keys]
        return ["" if v is None else _s(v) for v in vals]

    def _param(self, name, default):
        try:
            v = self.getParameter(name)
            return default if v is None else v
        except Exception:
            return default

    # ------------------------------------------------------------------ calm robot and lag watchdog (v4.0)
    def _tweak(self, proxy, getter, setter, *args):
        """Sets one robot setting and remembers how to put it back. Every failure is soft."""
        p = self._p(proxy)
        if p is None:
            return
        old = None
        if getter:
            try:
                old = getattr(p, getter[0])(*getter[1:])
            except Exception:
                old = None
        try:
            getattr(p, setter)(*args)
        except Exception as e:
            self._log("warning", _fmt("[Care Controller] %s.%s failed (%s)", proxy, setter, e))
            return
        if old is not None:
            self.undo.append((proxy, setter, tuple(args[:-1]) + (old,)))

    def _tune(self):
        """Calm mode: the robot stays with the person it is talking to, tracks with the head only, ignores movement and noise as
        a reason to turn away, does not try to recognise faces, and looks for people once a second. That is much less work for
        the robot (less lag, better listening) and nothing in it looks at faces beyond finding that somebody is there."""
        self.calm = bool(self._param("Calm mode", 1))
        if not self.calm:
            self._perceive(True)             # the robot's own behaviour, as before; only the crowd warning needs the people list
            return
        self._tweak("ALBasicAwareness", ("getEngagementMode",), "setEngagementMode", "FullyEngaged")
        self._tweak("ALBasicAwareness", ("getTrackingMode",), "setTrackingMode", "Head")
        for stim in ("Movement", "Sound", "NavigationMotion"):
            self._tweak("ALBasicAwareness", ("isStimulusDetectionEnabled", stim), "setStimulusDetectionEnabled", stim, False)
        self._tweak("ALFaceDetection", ("isRecognitionEnabled",), "setRecognitionEnabled", False)
        self._tweak("ALPeoplePerception", ("isMovementDetectionEnabled",), "setMovementDetectionEnabled", False)
        self._tweak("ALPeoplePerception", ("isFastModeEnabled",), "setFastModeEnabled", True)
        for ability in CALM_OFF:
            self._tweak("ALAutonomousLife", ("getAutonomousAbilityEnabled", ability), "setAutonomousAbilityEnabled", ability, False)
        self._perceive(True)

    def _untune(self):
        undo, self.undo = self.undo, []
        for proxy, setter, args in reversed(undo):
            self._call(proxy, setter, *args)
        self.calm = False

    def _perceive(self, on):
        """People perception is only needed for the crowd warning; with the warning off it is not subscribed at all."""
        pp = self._p("ALPeoplePerception")
        if pp is None:
            return
        try:
            if on:
                try:
                    allowed = int(self._param("People allowed", 2))
                except (TypeError, ValueError):
                    allowed = 2
                if allowed <= 0:
                    return
                try:
                    pp.subscribe("CareController", PERCEPTION_MS, 0.0)
                except Exception:
                    pp.subscribe("CareController")
            else:
                pp.unsubscribe("CareController")
        except Exception:
            pass

    def _lagCheck(self):
        """The main loop should tick about every 0.1 s. When the robot is overloaded (face tracking, sound, the tablet) it falls
        behind and the speech recogniser starves. After LAG_TICKS slow ticks in a row the tracking is paused and the people
        perception stopped, which is what loads the robot most; after LAG_HOLD_S of fast ticks they come back."""
        now = self.perf()
        last, self.lastTickAt = self.lastTickAt, now
        if last is None:
            return
        gap = now - last
        if gap > LAG_SLOW_S:
            self.slowTicks += 1
            self.fastTicks = 0
        else:
            self.slowTicks = 0
            self.fastTicks = self.fastTicks + 1 if gap < LAG_OK_S else 0
        if not self.lagMode and self.slowTicks >= LAG_TICKS:
            self.lagMode = True
            self.lagSince = now
            self._log("warning", "[Care Controller] the robot is slow: tracking paused")
            self._call("ALBasicAwareness", "pauseAwareness")
            self._perceive(False)
            self._push()
        elif self.lagMode and now - self.lagSince >= LAG_HOLD_S and self.fastTicks >= LAG_OK_TICKS:
            self.lagMode = False
            self._log("info", "[Care Controller] the robot is fast again: tracking resumed")
            if not self.bodyBusy:
                self._call("ALBasicAwareness", "resumeAwareness")
            self._perceive(True)
            self._push()

    def _writeClock(self):
        """The time and the day for "what time is it": written about every 20 s, only when they changed."""
        t = time.localtime(self.clock())
        key = "%d:%d:%d" % (t.tm_yday, t.tm_hour, t.tm_min)
        if key == self.clockKey:
            return
        self.clockKey = key
        self._write("clockText", clock_words(t.tm_hour, t.tm_min))
        self._write("dayText", day_words(t.tm_wday, t.tm_mday, t.tm_mon))

    def tick(self):
        self._lagCheck()
        if not self.startGreeted and self.startAt is not None and self.clock() - self.startAt >= STARTUP_GREET_S:
            self.startGreeted = True
            if self.lastGreet < 0 and self.current is None and self.calling is None and not self._busy():
                self._log("info", "[Care Controller] the dialog's start message did not arrive: starting the welcome")
                self._greet()
        self._dialogStep()
        name, cmd, raw, owner = self._readKeys(POLL_KEYS)
        if self.token is not None and owner and owner != self.token:
            self.running = False                        # a newer controller took over: leave its commands alone
            self._log("warning", "[Care Controller] a newer Care Controller started; this older one steps down")
            return
        self._drain()
        if name:
            self._write("pepperName", "")
            self.startSession(name)
        if cmd:
            self._write("pepperCmd", "")
            if self.voiceOk is False:
                self.voiceOk = True            # the dialog sent a command after all: it is running
                self._log("info", "[Care Controller] the dialog is running after all")
            now = self.clock()
            if cmd == self.lastRaw and now - self.lastRawAt < REPEAT_GUARD_S:
                self._log("info", _fmt("[Care Controller] repeated command %s ignored", cmd))
            else:
                self.lastRaw, self.lastRawAt = cmd, now
                self.handle(cmd)
        if raw:
            self._write("Pepper/TabletCmd", "")
            self._tablet(raw)
        now = self.clock()
        if self.mode == "music" and now >= self.musicEnds:             # the box may still report its end later
            self.mode = None
            self._push()
        if self.mode == "show" and now - self.showStart > SHOW_MAX_S:     # fallback if a routine's end is lost:
            self._stopAll()                                                # stop it, so nothing is left moving
            self._push()
        if self.mode == "exercise":
            self._exerciseTimer(now)
        if self.mode == "breathing" and self.breath is not None and now >= self.breath["next"]:
            self._breathStep(now)
        self._quizTimers(now)
        self._memTimers(now)
        self._snlTimers(now)
        if self.pick is not None and now - self.pick["at"] > PICK_IDLE_S:
            self.pick = None                  # nobody chose: the list goes away quietly
            self._push()
        self._checkReminders(now)
        if now - self.lastCrowdCheck >= 1.0:          # people walking up: once a second is plenty
            self.lastCrowdCheck = now
            self._checkCrowd(now)
            self._writeClock()
        if now - self.lastPush >= 5.0:
            self._push()

    # ------------------------------------------------------------------ commands from the dialog
    def handle(self, cmd):
        cmd = str(cmd).strip().lower()
        self.lastCmd = cmd
        self._log("info", _fmt("[Care Controller] command %s", cmd))
        self._noteHeard(cmd)
        passive = cmd in PASSIVE_CMDS
        if cmd != "nu":
            self.nuCount = 0
        if not passive:
            if self.quiz is not None and cmd not in QUIZ_CMDS:
                self._quizClear()                    # the dialog moved on to something else: no stale quiz on the tablet
            if self.mem is not None and cmd not in MEM_CMDS:
                self._memClear()                     # likewise for the memory cards
            if self.snl is not None and cmd not in SNL_CMDS:
                self._snlClear()                     # and for the game
            if self.pick is not None and cmd not in PICK_CMDS:
                self.pick = None                     # something was chosen or the dialog moved on: the list closes
        if cmd == "hello":
            self._greet()
        elif cmd == "group":
            self._group()
        elif cmd == "autostart":
            self._autoStart()
        elif cmd == "helpme":
            self._helpMe()
        elif cmd in ("joke", "fact"):
            self._tellSomething(cmd)
        elif cmd in NEEDS:
            self._need(cmd)
        elif cmd == "suggest":
            self._suggest(fresh=True)
        elif cmd == "suggestyes":
            self._suggestYes()
        elif cmd == "suggestno":
            self._suggest(fresh=False)
        elif cmd == "nu":
            self._notUnderstood()
        elif cmd == "dmyes":
            self._didMeanYes()
        elif cmd == "dmno":
            self.dm = None
        elif cmd == "pickmusic":
            self._pickOpen("music")
        elif cmd == "pickact":
            self._pickOpen("activities")
        elif cmd == "pickoff":
            pass                                 # the dialog dropped the question (stop, no): the list was closed above
        elif cmd == "snl":
            self._snlStart()
        elif cmd == "snew":
            if self._snlVoiceFree():
                self._snlStart(force=True)
        elif cmd == "sroll":
            self._snlRoll()
        elif cmd == "sskip":
            self._snlSkip()
        elif cmd == "srepeat":
            self._snlRepeat()
        elif cmd == "relive":
            self._memStart()
        elif cmd == "mnext":
            self._memMove(1)
        elif cmd == "mback":
            self._memMove(-1)
        elif cmd == "mrepeat":
            self._memShow("", fresh=False)
        elif cmd in ("ma1", "ma2"):
            self._memAnswer(int(cmd[2]))                 # spoken
        elif cmd == "quiz":
            self._quizStart()
        elif cmd in ("qa1", "qa2", "qa3"):
            self._quizAnswer(int(cmd[2]))                # spoken
        elif cmd == "qrepeat":
            self._quizAsk("", fresh=False)
        elif cmd.startswith("exercise") and cmd[8:].isdigit():
            n = int(cmd[8:])
            if 1 <= n <= 9:
                self._startExercise(n)
        elif cmd == "exercisesdone":
            if self.mode == "exercise" and self.exPhase in ("moving", "holding"):
                self._stopAll()              # "next" during the last exercise: stop its movement, stand up
            else:
                self._idle()
        elif cmd.startswith("song") and cmd[4:] in ("1", "2", "3") and self.mode == "music" and self.current_item == cmd:
            pass                                    # already playing this song: never stop and restart it
        elif cmd in SHOWS and self.mode == "show" and self.current_item == cmd:
            pass                                    # already performing this routine (e.g. "repeat"): keep it going
        elif cmd.startswith("song") and cmd[4:] in ("1", "2", "3"):
            self._stopAll()
            self.current_item = cmd
            self.musicEnds = self.clock() + SONG_SECONDS.get(cmd[4:], 60.0)   # fallback if the end signal is lost
            self.showStart = self.clock()
            self.mode = "music"
            self.showRunning = True
            self._fire("onSong" + cmd[4:])
            self._bump("music")
        elif cmd in SHOWS:
            self._stopAll()
            self.current_item = cmd
            self.showStart = self.clock()
            self.mode = "show"
            self._fire(SHOWS[cmd])
            self._bump("performances")
        elif cmd == "stop":
            self._stopAll()
        elif cmd == "breathe":
            self._startBreathing()
        elif cmd == "alert":
            self._alert()
        elif cmd == "confirmname":
            self.startSession(self._read("name"))
        elif cmd in ("medtaken", "mednot", "medunsure"):
            self._set("med", {"medtaken": "taken", "mednot": "not taken", "medunsure": "not sure"}[cmd])
        elif cmd == "moodlow":
            self._set("moodLow", True)
        elif cmd == "remindmin":
            self._remindIn(WORDS.get(self._read("medMin").lower(), 0))
        elif cmd == "remindat":
            self._remindAt(WORDS.get(self._read("medHour").lower(), 0), self._read("medPart").lower())
        elif cmd in ("duetaken", "duenot"):
            self._dueAnswer("taken" if cmd == "duetaken" else "not taken")
        elif cmd == "end":
            self._closeSession()
            self._callNext()
        elif cmd == "next":
            self._closeSession()
            self.calling = None
            if not self._callNext():
                self._force("robotcmd askname")
        elif cmd == "nexthere":
            self.startSession(self.calling or self._read("nextName"))
        elif cmd == "nextabsent":
            self.calling = None
            self._callNext()
        else:
            self._log("warning", _fmt("[Care Controller] unknown command %s", cmd))
        self._push()


    # ------------------------------------------------------------------ v4.0: the session guard
    def _busy(self):
        """True while something that needs the resident's attention runs (an activity, a quiz, cards or a game)."""
        return self.mode is not None or self.quiz is not None or self.mem is not None or self.snl is not None

    def _greet(self):
        """The dialog heard a greeting. Only a robot with nobody to serve starts a welcome; with a person being served nothing restarts."""
        now = self.clock()
        if now - self.lastGreet < GREET_DUP_S:
            return                                   # Pepper's own "hello", or a repeat of the same greeting
        if self._busy():
            self._log("info", "[Care Controller] greeting ignored: an activity is running")
            return
        self.lastGreet = now
        if self.current is None and self.calling is None:
            self._force("robotcmd welcome")
        elif self.current is not None:
            self._force("robotcmd hellosame")

    def _group(self):
        if self._busy() or self.current is not None or self.calling is not None:
            return
        self._force("robotcmd grouphere")

    def _autoStart(self):
        """The dialog's first proposal was said (a new engagement, a restart of the topic). With nobody being served this is the welcome;
        with a person being served it is ignored, and the dialog is put back where the running activity needs it."""
        if self.current is None and self.calling is None and not self._busy():
            if self.lastGreet > 0 and self.clock() - self.lastGreet < AUTOSTART_DUP_S:
                return                                   # the welcome was just given (the start-up fallback came first)
            self._greet()
        else:
            self._log("info", "[Care Controller] topic restart ignored: a session is running")
            self._dialogRestore()

    def _dialogRestore(self):
        """After the dialog jumped away, give a running quiz, card session or game its listening rules back (the question is read again)."""
        if self.quiz is not None and self.quiz["phase"] == "ask":
            self._quizAsk("", fresh=False)
        elif self.mem is not None and self.mem["phase"] == "show":
            self._memShow("", fresh=False)
        elif self.snl is not None:
            self._snlRepeat()

    # ------------------------------------------------------------------ v4.0: needs and safety
    def _need(self, cmd):
        label, urgent = NEEDS[cmd]
        self._alert(label, urgent)          # the same need said twice within ALERT_DUP_S is one call (see _alert)

    # ------------------------------------------------------------------ v4.0: help that depends on what is happening
    def _helpMe(self):
        if self.quiz is not None:
            tok = "hintquiz"
        elif self.mem is not None:
            tok = "hintmem"
        elif self.snl is not None:
            tok = "hintsnl"
        elif self.mode == "exercise":
            tok = "hintex"
        elif self.mode == "breathing":
            tok = "hintbreath"
        elif self.mode in ("music", "show"):
            tok = "hintmusic"
        else:
            tok = "hintidle"
        self._force("robotcmd " + tok)

    # ------------------------------------------------------------------ v4.0: jokes and facts, never repeated until all were told
    def _tellSomething(self, kind):
        if self._busy():
            self._force("robotcmd later")
            return
        bank, deckName = (JOKES, "jokeDeck") if kind == "joke" else (FACTS, "factDeck")
        deck = getattr(self, deckName)
        if not deck:
            deck = list(range(len(bank)))
            self.rnd.shuffle(deck)
        i = deck.pop()
        setattr(self, deckName, deck)
        self._write("sayText", bank[i])
        self._force("robotcmd saytext")

    # ------------------------------------------------------------------ v4.0: a suggestion that knows what was already done
    def _done(self, name, keys):
        rec = self.current
        if rec is None:
            return 0
        return sum(int(rec.get(k, 0) or 0) for k in keys)

    def _suggest(self, fresh):
        if self._busy():
            self._force("robotcmd later")
            return
        if fresh:
            self.suggTried = []
        low = self.current is not None and self.current.get("moodLow")
        ranked = []
        for order, (name, token, label, keys) in enumerate(SUGGEST):
            if name in self.suggTried:
                continue
            score = 0
            if self._done(name, keys) == 0:
                score += 3
            if low and name in SUGGEST_CALM:
                score += 2 + 0.1 * (len(SUGGEST_CALM) - SUGGEST_CALM.index(name))      # breathing first, then music, memories, a chat
            ranked.append((-score, order, name, token, label))
        if not ranked:
            self.sugg = None
            self._force("robotcmd suggestnone")
            return
        ranked.sort()
        _, _, name, token, label = ranked[0]
        self.suggTried.append(name)
        self.sugg = {"name": name, "token": token}
        self._write("suggestText", _fmt("How about %s? Would you like that?", label))
        self._force("robotcmd suggestask")

    def _suggestYes(self):
        sg, self.sugg = self.sugg, None
        if sg is not None:
            self._force("robotcmd " + sg["token"])

    # ------------------------------------------------------------------ v4.0: "did you mean ...?" when nothing was understood
    def _noteHeard(self, cmd):
        """Keeps the last thing the robot heard (the staff view shows it). Pepper's own forced tokens are not speech."""
        txt = _s(self._read("Dialog/LastInput")).strip()
        if not txt or txt.lower().startswith("robotcmd"):
            return
        txt = "".join(c for c in txt if " " <= c <= "~")[:HEARD_KEPT]
        if txt:
            self.heard = txt
            if cmd != "nu":
                self.heardUsed = txt

    def _notUnderstood(self):
        """The dialog did not understand. Match what was heard against the tiles; one clear match becomes a question, otherwise
        a short hint (the second time in a row points to the touch screen)."""
        self.nuCount += 1
        heard = self.heard if self.heard and self.heard != self.heardUsed else ""
        found = understand(heard) if heard else None
        if found is not None:
            self.dm = {"name": found[0], "token": found[1]}
            self._write("didMeanText", _fmt("Did you mean %s?", found[2]))
            self._force("robotcmd didmean")
        else:
            self.dm = None
            self._force("robotcmd nutouch" if self.nuCount >= NU_ESCALATE else "robotcmd nuplain")

    def _didMeanYes(self):
        dm, self.dm = self.dm, None
        if dm is not None:
            self._force("robotcmd " + dm["token"])

    # ------------------------------------------------------------------ sessions
    def _clean(self, raw):
        if not isinstance(raw, str):
            try:
                raw = raw.encode("utf-8")
            except Exception:
                raw = str(raw)
        words = [w for w in raw.replace(",", " ").split() if w][:3]
        out = []
        for w in words:
            out.append(w[0].upper() + w[1:] if "a" <= w[0] <= "z" else w)
        return " ".join(out)[:40]

    def _new(self, name):
        return {"name": name, "start": time.strftime("%H:%M", time.localtime(self.clock())), "exercises": 0,
                "music": 0, "performances": 0, "breathing": 0, "med": "",
                "moodLow": False, "alert": False, "quizzes": 0, "quizLast": "", "memCards": 0, "memLikes": [], "memAnswers": [], "snlGames": 0, "snlWins": 0}

    def startSession(self, raw):
        name = self._clean(raw)
        if not name:
            return
        if self.current is not None and self.current["name"].lower() == name.lower():
            return
        self._closeSession()
        self.calling = None
        self.current = self._new(name)
        self.introduced = True
        self.queue = [q for q in self.queue if q.lower() != name.lower()]
        self._write("name", name)
        self._updateMedNext()
        self._push()

    def _closeSession(self):
        if self.mode is not None:
            self._stopAll()          # a new person never inherits the previous person's movement or music
        if self.current is not None:
            self.current["end"] = time.strftime("%H:%M", time.localtime(self.clock()))
            self.history.append(self.current)
            self.history = self.history[-500:]
            self.current = None
        self._updateMedNext()

    def _ensure(self):
        if self.current is None:
            self.current = self._new("Unnamed patient")
        return self.current

    def _bump(self, key):
        self._ensure()[key] += 1

    def _set(self, key, value):
        self._ensure()[key] = value

    def _callNext(self):
        """Calls the next queued person, unless someone is being served or already being called."""
        if not self.queue or self.current is not None or self.calling is not None:
            return False
        nxt = self.queue.pop(0)
        self.calling = nxt
        self._write("nextName", nxt)
        self._write("name", nxt)
        self._force("robotcmd callnext")
        return True

    # ------------------------------------------------------------------ body: quiet while Pepper exercises
    def _body(self, busy):
        if busy == self.bodyBusy:
            return
        self.bodyBusy = busy
        self._call("ALMotion", "setBreathEnabled", "Body", not busy)
        al = self._p("ALAutonomousLife")
        done = False
        if al is not None:
            try:
                for ability in ABILITIES:
                    al.setAutonomousAbilityEnabled(ability, (not busy) and not (self.calm and ability in CALM_OFF))
                done = True
            except Exception:
                done = False
        if not done:
            self._call("ALSpeakingMovement", "setEnabled", not busy)
        aw = self._p("ALBasicAwareness")
        if aw is not None:
            try:
                if busy or self.lagMode:
                    aw.pauseAwareness()
                else:
                    aw.resumeAwareness()
            except Exception:
                pass

    def _stopMotion(self):
        """Stops the exercise timelines and anything still moving the exercise joints. Never blocks."""
        self._fire("onStopAll")
        self._call("ALMotion", "killTasksUsingResources", MOVING_JOINTS)

    def _posture(self):
        self._post("ALRobotPosture", "goToPosture", "Stand", POSTURE_SPEED)

    # ------------------------------------------------------------------ exercises: EXERCISE_SECONDS each
    def _startExercise(self, n):
        now = self.clock()
        if self.mode == "exercise" and self.exIndex == n and now - self.exStart < EXERCISE_DUP_S:
            self._log("info", _fmt("[Care Controller] exercise %s is just starting, repeated command ignored", n))
            return
        if self.mode == "exercise":
            self._stopMotion()            # skip / repeat: the previous timeline stops, no trip back to Stand
        elif self.mode is not None:
            self._stopAll()
        self.mode = "exercise"
        self.exIndex = n
        self.exStart = now
        self.exRunStart = now
        self.exEnds = now + self.exSeconds
        self.exPhase = "moving"
        self._body(True)
        self._fire("onExercise%d" % n)
        self._js("PepperUI.exercise && PepperUI.exercise(%d, 0, %d)" % (n, int(self.exSeconds)))
        self._bump("exercises")

    def _motionDone(self, t):
        """A timeline reached its end: repeat it until the exercise time is up. A start sent to a timeline that is
        still running is ignored by Choregraphe, so an echo of a stop can never leave Pepper standing still."""
        if self.mode != "exercise" or self.exPhase != "moving":
            return
        if self.exEnds - self.clock() > MIN_REPEAT_S:
            self.exRunStart = self.clock()
            self._fire("onExercise%d" % self.exIndex)
        else:
            self.exPhase = "holding"

    def _exerciseTimer(self, now):
        if self.exPhase in ("moving", "holding") and now >= self.exEnds:
            n = self.exIndex
            self.exPhase = "done"
            self.exEnds = now
            self._stopMotion()
            self._posture()
            self._js("PepperUI.exerciseDone && PepperUI.exerciseDone(%d)" % n)
            self._force("robotcmd exdone%d" % n)
            self._push()
        elif self.exPhase == "done" and now - self.exEnds > DONE_GAP_S:
            self._idle()                  # the dialog moved on without starting another exercise
            self._push()

    def _stopAll(self):
        was = self.mode
        self.quiz = None
        self.mem = None
        self.snl = None
        self.pick = None
        if self.showRunning:                 # a song box we stop still reports its end (its stop code calls onStopped): an echo
            self.expectEcho += 1
            self.echoUntil = self.clock() + 3.0
            self.showRunning = False
        self.mode = None
        self.exPhase = None
        self.breath = None
        self._fire("onStopAll")
        self._call("ALAudioPlayer", "stopAll")
        if was in ("exercise", "breathing", "show"):
            self._call("ALMotion", "killTasksUsingResources", MOVING_JOINTS)
            self._posture()
        if was == "exercise":
            self._js("PepperUI.exercise && PepperUI.exercise(0, 0)")
        if was == "breathing":
            self._js("PepperUI.breath && PepperUI.breath('end', 0, 0)")
        self._body(False)

    def _idle(self):
        self.mode = None
        self.exPhase = None
        self._body(False)
        self._js("PepperUI.exercise && PepperUI.exercise(0, 0)")

    def _showDone(self, t):
        """A routine or a song reported its end (its box onStopped). The end of a box we stopped ourselves (an echo)
        is expected and swallowed, but only for a few seconds, so a lost echo can never hide a real end for long."""
        if self.expectEcho > 0 and t <= self.echoUntil:
            self.expectEcho -= 1
            return
        self.expectEcho = 0
        if self.mode in ("show", "music"):
            self.mode = None
            self._push()

    # ------------------------------------------------------------------ quiz
    def _quizDeal(self):
        """QUIZ_LEN question numbers. The bank is shuffled once and dealt out five at a time, so a question never comes
        back before every other one was asked; when fewer than QUIZ_LEN are left they are used first and the rest of the
        bank is shuffled in behind them (still no repeat inside one quiz)."""
        good = self._quizRows()
        self.quizDeck = [i for i in self.quizDeck if i in good]      # the bank may have been edited by hand
        if len(self.quizDeck) < QUIZ_LEN:
            rest = [i for i in good if i not in self.quizDeck]
            self.rnd.shuffle(rest)
            self.quizDeck = self.quizDeck + rest
        picks, self.quizDeck = self.quizDeck[:QUIZ_LEN], self.quizDeck[QUIZ_LEN:]
        return picks

    def _quizRows(self):
        """Numbers of the usable rows: the bank can be edited in Choregraphe, and one bad row must not stop the quiz."""
        return [i for i, r in enumerate(QUIZ_BANK)
                if isinstance(r, (tuple, list)) and len(r) == 4 and all(isinstance(x, str) and x.strip() for x in r) and len(set(r[1:])) == 3]

    def _quizStart(self):
        qz0 = self.quiz
        if qz0 is not None and qz0["phase"] == "ask" and qz0["i"] == 0 and self.clock() - qz0["asked"] < QUIZ_START_DUP_S:
            self._log("info", "[Care Controller] a quiz is just starting, repeated command ignored")
            return
        if len(self._quizRows()) < QUIZ_LEN:
            self._log("warning", "[Care Controller] the quiz bank has fewer than five usable questions")
            self._force("robotcmd quizidle")
            return
        if self.mode is not None:
            self._stopAll()
        qs = []
        for i in self._quizDeal():
            q, right, w1, w2 = QUIZ_BANK[i]
            opts = [right, w1, w2]
            self.rnd.shuffle(opts)           # the right answer is not always the same number
            qs.append({"q": q, "opts": opts, "right": opts.index(right), "bank": i})
        now = self.clock()
        self.quizSerial += 1
        self.mode = "quiz"
        self.quiz = {"k": self.quizSerial, "qs": qs, "i": 0, "score": 0, "phase": "ask", "asked": now, "last": now, "fb": None,
                     "say": "", "wait": 0.0, "voiceFrom": 0.0}
        self._quizAsk("Quiz time! Five questions. Say the number of your answer, or touch the screen. ")

    def _quizAsk(self, lead, fresh=True):
        """Makes the current question current. The tablet gets it first; Pepper reads it when the tablet says it shows it
        (cmd quizShown) or after QUIZ_ACK_S, so Pepper never talks about a question nobody can see. A repeat reads at once."""
        qz = self.quiz
        if qz is None or qz["phase"] != "ask":
            return
        cur = qz["qs"][qz["i"]]
        o = cur["opts"]
        qz["say"] = _fmt("%sQuestion %s. %s Option one, %s. Option two, %s. Option three, %s.",
                         lead, QUIZ_NUM[qz["i"] + 1], cur["q"], o[0], o[1], o[2])
        now = self.clock()
        if fresh:
            qz["asked"] = qz["last"] = now
            qz["wait"] = now + QUIZ_ACK_S
            qz["voiceFrom"] = now + 1000.0          # no spoken answer until the question has been read
            self._push()
        else:
            qz["last"] = now
            self._quizSpeak()

    def _quizSpeak(self):
        """Writes what Pepper says into ALMemory ($quizText) and makes the dialog say it."""
        qz = self.quiz
        if qz is None or qz["phase"] != "ask":
            return
        now = self.clock()
        qz["wait"] = 0.0
        words = len(qz["say"].split())
        qz["voiceFrom"] = now + min(QUIZ_READ_MAX_S, QUIZ_READ_BASE_S + QUIZ_READ_WORD_S * words)
        self._write("quizText", qz["say"])
        self._force("robotcmd quizask")

    def _quizAnswer(self, n, tablet=None):
        """n is 1, 2 or 3. tablet is None for a spoken answer, or the (quiz, question) pair the tap was made on."""
        qz = self.quiz
        if qz is None or qz["phase"] != "ask" or n not in (1, 2, 3):
            return
        now = self.clock()
        if tablet is None:
            if qz["wait"] or now < qz["voiceFrom"]:
                self._log("info", "[Care Controller] spoken answer ignored: the question is still being read")
                return
        else:
            if (tablet[0] is not None and tablet[0] != qz["k"]) or (tablet[1] is not None and tablet[1] != qz["i"] + 1):
                self._log("info", "[Care Controller] tap ignored: it was made on another question")
                return
            if now - qz["asked"] < QUIZ_THINK_S:
                return
        cur = qz["qs"][qz["i"]]
        ok = (n - 1 == cur["right"])
        answer = cur["opts"][cur["right"]]
        if ok:
            qz["score"] += 1
            lead = QUIZ_OK[self.rnd.randrange(len(QUIZ_OK))] + " "
        else:
            lead = _fmt("%s The answer is %s. ", QUIZ_NO[self.rnd.randrange(len(QUIZ_NO))], answer)
        qz["fb"] = {"ok": ok, "answer": answer}
        qz["i"] += 1
        qz["last"] = now
        if tablet is not None:
            self._call("ALTextToSpeech", "stopAll")      # a tap while Pepper is still reading the options
        if qz["i"] < len(qz["qs"]):
            self._quizAsk(lead)
        else:
            total = len(qz["qs"])
            qz["phase"] = "done"
            qz["doneAt"] = now
            qz["wait"] = 0.0
            self.mode = None
            rec = self._ensure()
            rec["quizzes"] += 1
            rec["quizLast"] = "%d/%d" % (qz["score"], total)
            text = _fmt("%sThat was the last question. You got %s out of %s. %s", lead,
                        QUIZ_NUM[qz["score"]], QUIZ_NUM[total], QUIZ_END[min(qz["score"], len(QUIZ_END) - 1)])
            self._write("quizText", text)
            self._push()
            self._force("robotcmd quizend")
        self._push()

    def _quizShown(self, k, n):
        """The tablet reports that it is showing question n of quiz k: Pepper may read it now."""
        qz = self.quiz
        if qz is not None and qz["phase"] == "ask" and qz["wait"] and k == qz["k"] and n == qz["i"] + 1:
            self._quizSpeak()

    def _quizClear(self):
        self.quiz = None
        if self.mode == "quiz":
            self.mode = None

    def _quizTimers(self, now):
        qz = self.quiz
        if qz is None:
            return
        if qz["phase"] == "ask" and qz["wait"] and now >= qz["wait"]:
            self._quizSpeak()                # no tablet answer in time (no tablet, or it is slow): voice only
        if qz["phase"] == "ask" and now - qz["last"] > QUIZ_IDLE_S:
            self._quizClear()
            self._force("robotcmd quizidle")
            self._push()
        elif qz["phase"] == "done" and now - qz["doneAt"] > QUIZ_RESULT_S:
            self.quiz = None
            self._push()

    def _quizView(self):
        """What the tablet may see. The right answer of the question on screen is never in here (only of the last one)."""
        qz = self.quiz
        if qz is None:
            return None
        fb = qz["fb"]
        view = {"k": qz["k"], "phase": qz["phase"], "total": len(qz["qs"]), "score": qz["score"], "fb": fb}
        if qz["phase"] == "ask":
            cur = qz["qs"][qz["i"]]
            view.update({"n": qz["i"] + 1, "q": cur["q"], "opts": cur["opts"]})
        return view

    # ------------------------------------------------------------------ Relive Malta: reminiscence cards
    def _memStart(self):
        m0 = self.mem
        if m0 is not None and m0["phase"] == "show" and m0["i"] == 0 and self.clock() - m0["asked"] < MEM_START_DUP_S:
            self._log("info", "[Care Controller] Relive Malta is just starting, repeated command ignored")
            return
        if self.mode is not None:
            self._stopAll()
        order = list(range(len(MEM_CARDS)))
        self.rnd.shuffle(order)              # a different order each time
        now = self.clock()
        self.memSerial += 1
        self.mode = "memories"
        self.mem = {"k": self.memSerial, "order": order, "i": 0, "phase": "show", "asked": now, "last": now,
                    "say": "", "wait": 0.0, "voiceFrom": 0.0, "liked": [], "seen": [], "ans": None, "reply": ""}
        self._memShow(MEM_OPEN)

    def _memCard(self):
        return MEM_CARDS[self.mem["order"][self.mem["i"]]]

    def _memShow(self, lead, fresh=True):
        """Makes the current card current. The tablet gets it first; Pepper reads it when the tablet says it shows it
        (cmd memShown) or after MEM_ACK_S. A repeat reads at once. Pepper reads the title, the sentence and the first prompt."""
        m = self.mem
        if m is None or m["phase"] != "show":
            return
        card = self._memCard()
        if fresh:
            m["ans"], m["reply"] = None, ""
        if m["ans"] is not None:
            m["say"] = m["reply"]              # a repeat after the answer says the reply again
        else:
            m["say"] = _fmt("%s%s. %s %s%s", lead, card[1], card[2], card[3], MEM_FIRST_TAIL if lead else "")
        now = self.clock()
        if fresh:
            idx = m["order"][m["i"]]
            if idx not in m["seen"]:
                m["seen"].append(idx)
                rec = self._ensure()
                rec["memCards"] += 1
            m["asked"] = m["last"] = now
            m["wait"] = now + MEM_ACK_S
            m["voiceFrom"] = now + 1000.0         # no spoken command until the card has been read
            self._push()
        else:
            m["last"] = now
            self._memSpeak()

    def _memSpeak(self):
        m = self.mem
        if m is None or m["phase"] != "show":
            return
        now = self.clock()
        m["wait"] = 0.0
        words = len(m["say"].split())
        m["voiceFrom"] = now + min(MEM_READ_MAX_S, MEM_READ_BASE_S + MEM_READ_WORD_S * words)
        self._write("memText", m["say"])
        self._force("robotcmd memcard")

    def _memShown(self, k, n):
        """The tablet reports that it shows card n of session k: Pepper may read it now."""
        m = self.mem
        if m is not None and m["phase"] == "show" and m["wait"] and k == m["k"] and n == m["i"] + 1:
            self._memSpeak()

    def _memOk(self, tablet):
        """True when a command counts. A spoken one (tablet is None) only after Pepper has finished reading; a tap only when it
        was made on the card that is on screen now."""
        m = self.mem
        if m is None or m["phase"] != "show":
            return False
        now = self.clock()
        if tablet is None:
            if m["wait"] or now < m["voiceFrom"]:
                self._log("info", "[Care Controller] spoken command ignored: the card is still being read")
                return False
            return True
        if (tablet[0] is not None and tablet[0] != m["k"]) or (tablet[1] is not None and tablet[1] != m["i"] + 1):
            self._log("info", "[Care Controller] tap ignored: it was made on another card")
            return False
        return now - m["asked"] >= MEM_THINK_S

    def _memMove(self, delta, tablet=None):
        if not self._memOk(tablet):
            return
        m = self.mem
        now = self.clock()
        j = m["i"] + delta
        if j < 0:
            return                            # already on the first card
        if tablet is not None:
            self._call("ALTextToSpeech", "stopAll")       # a tap while Pepper is still reading
        m["last"] = now
        if j >= len(m["order"]):
            m["phase"] = "end"
            m["doneAt"] = now
            m["wait"] = 0.0
            self._write("memText", MEM_END_TEXT)
            self._push()
            self._force("robotcmd memend")
        else:
            m["i"] = j
            self._memShow("")
        self._push()

    def _memAnswer(self, j, tablet=None):
        """j is 1 or 2. One answer per card, one reply from Pepper. tablet is None for a spoken answer, or the (session, card)
        pair the tap was made on."""
        m = self.mem
        if m is None or m["phase"] != "show" or j not in (1, 2) or m["ans"] is not None:
            return
        if not self._memOk(tablet):
            return
        now = self.clock()
        card = self._memCard()
        label, _words, reply = card[4][j - 1]
        m["ans"], m["reply"] = j - 1, reply
        m["last"] = now
        if tablet is not None:
            self._call("ALTextToSpeech", "stopAll")      # a tap while Pepper is still reading the question
        rec = self._ensure()
        line = _fmt("%s: %s", card[1], label)
        if line not in rec["memAnswers"]:
            rec["memAnswers"] = (rec["memAnswers"] + [line])[-MEM_ANSWERS_KEPT:]
        m["say"] = reply
        self._memSpeak()
        self._push()

    def _memLike(self, k, n):
        m = self.mem
        if m is None or m["phase"] != "show":
            return
        if (k is not None and k != m["k"]) or (n is not None and n != m["i"] + 1):
            return
        idx = m["order"][m["i"]]
        m["last"] = self.clock()
        if idx not in m["liked"]:
            m["liked"].append(idx)
            rec = self._ensure()
            title = MEM_CARDS[idx][1]
            if title not in rec["memLikes"]:
                rec["memLikes"] = (rec["memLikes"] + [title])[-MEM_LIKES_KEPT:]
        self._push()

    def _memClear(self):
        self.mem = None
        if self.mode == "memories":
            self.mode = None

    def _memTimers(self, now):
        m = self.mem
        if m is None:
            return
        if m["phase"] == "show" and m["wait"] and now >= m["wait"]:
            self._memSpeak()                  # no tablet answer in time (no tablet, or it is slow): voice only
        if m["phase"] == "show" and now - m["last"] > MEM_IDLE_S:
            self._memClear()                  # quietly: somebody may be in the middle of a conversation
            self._push()
        elif m["phase"] == "end" and now - m["doneAt"] > MEM_END_S:
            self._memClear()
            self._push()

    def _memView(self):
        """What the tablet shows. Nothing secret in here."""
        m = self.mem
        if m is None:
            return None
        view = {"k": m["k"], "phase": m["phase"], "total": len(m["order"])}
        if m["phase"] == "show":
            idx = m["order"][m["i"]]
            c = MEM_CARDS[idx]
            view.update({"n": m["i"] + 1, "id": c[0], "title": c[1], "line": c[2], "q": c[3],
                         "opts": [c[4][0][0], c[4][1][0]],
                         "ans": -1 if m["ans"] is None else m["ans"], "reply": m["reply"] if m["ans"] is not None else "",
                         "liked": idx in m["liked"]})
        return view

    # ------------------------------------------------------------------ Snakes and Ladders
    # The controller owns the game: fair dice (self.rnd), every rule, and what Pepper says. A round is the resident's move and, straight
    # after it, Pepper's (one spoken line for both). The tablet gets the round first (cmd snlShown), Pepper speaks when the dice have
    # settled. A tap carries the game (k) and the round (n) it was made on; a stale or double tap does nothing. A spoken roll counts only
    # after Pepper has finished talking and the board has stopped moving. Nothing speaks on a timer: a quiet screen stays quiet.
    def _pickOpen(self, which):
        """Pepper has asked what to play: the tablet shows the same choices without a tap. Anything running stops first, because a
        resident who asks for the list wants to choose something else."""
        if self.mode is not None:
            self._stopAll()
        self._ensure()                       # as for every topic: said before a name, it still shows on the tablet
        self.pickSerial += 1
        self.pick = {"k": self.pickSerial, "which": which, "at": self.clock()}
        self._push()

    def _pickView(self):
        p = self.pick
        return None if p is None else {"k": p["k"], "which": p["which"]}

    def _snlStart(self, force=False):
        m0 = self.snl
        if (not force and m0 is not None and m0["phase"] == "play" and m0["rolls"] == 0
                and self.clock() - m0["asked"] < SNL_START_DUP_S):
            self._log("info", "[Care Controller] Snakes and Ladders is just starting, repeated command ignored")
            return
        if m0 is not None and force and m0["phase"] == "play" and m0["rolls"] == 0 and self.clock() - m0["asked"] < SNL_START_DUP_S:
            return                                   # "new game" on a board nobody has touched changes nothing
        if self.mode is not None:
            self._stopAll()
        now = self.clock()
        self.snlSerial += 1
        self.mode = "snl"
        self._ensure()["snlGames"] += 1
        self.snl = {"k": self.snlSerial, "n": 1, "phase": "play", "pos": [0, 0], "moves": [], "say": SNL_OPEN, "wait": now + SNL_ACK_S,
                    "speakAt": 0.0, "voiceFrom": now + 1000.0, "animEnd": now, "asked": now, "last": now, "rolls": 0, "ladders": 0,
                    "snakes": 0, "winner": None, "doneAt": 0.0}
        self._push()

    def _snlMove(self, who, die):
        """One move of one player. Returns what the tablet needs to animate it."""
        m = self.snl
        frm = m["pos"][who]
        land, kind = frm + die, ""
        if land > 100:
            if SNL_EXACT:
                land, kind = frm, "bounce"
            else:
                land = 100
        to = land
        if kind == "":
            if land in SNL_LADDERS:
                to, kind = SNL_LADDERS[land], "ladder"
                if who == 0:
                    m["ladders"] += 1
            elif land in SNL_SNAKES:
                to, kind = SNL_SNAKES[land], "snake"
                if who == 0:
                    m["snakes"] += 1
        m["pos"][who] = to
        steps = 0 if kind == "bounce" else land - frm
        ms = SNL_MOVE_MS + SNL_STEP_MS * steps + (SNL_SPECIAL_MS if kind in ("ladder", "snake") else 0) + SNL_GAP_MS
        return {"who": who, "die": die, "frm": frm, "land": land, "to": to, "kind": kind, "ms": ms, "roll": SNL_MOVE_MS, "step": SNL_STEP_MS,
                "hold": SNL_SPECIAL_MS if kind in ("ladder", "snake") else 0, "gap": SNL_GAP_MS}

    def _snlLine(self, mv, first):
        """What Pepper says about one move."""
        d = SNL_NUM[mv["die"]]
        if mv["who"] == 0:
            lead = SNL_YOU[self.rnd.randrange(len(SNL_YOU))]
        else:
            lead = SNL_ME[self.rnd.randrange(len(SNL_ME))] if first else SNL_ME[0]
        lead = _fmt(lead, d)
        if mv["to"] == 100:
            return _fmt(SNL_WIN_YOU if mv["who"] == 0 else SNL_WIN_ME, d)
        if mv["kind"] == "ladder":
            tail = _fmt("A ladder! Up to %s.", mv["to"]) if mv["who"] == 0 else _fmt("A ladder! Up I go to %s.", mv["to"])
        elif mv["kind"] == "snake":
            tail = _fmt("A snake! Down to %s.", mv["to"]) if mv["who"] == 0 else _fmt("A snake! Down I go to %s.", mv["to"])
        elif mv["kind"] == "bounce":
            tail = _fmt("That is too many for the end, so %s on %s.", "you stay" if mv["who"] == 0 else "I stay", mv["to"])
        else:
            tail = _fmt("%s on %s.", "You are" if mv["who"] == 0 else "I am", mv["to"])
        return lead + " " + tail

    def _snlRound(self, skip):
        """The resident rolls (or skips), then Pepper moves. Updates the game and what is said."""
        m = self.snl
        now = self.clock()
        moves, parts = [], []
        if skip:
            parts.append(SNL_SKIPPED)
        else:
            mv = self._snlMove(0, 1 + self.rnd.randrange(6))
            moves.append(mv)
            m["rolls"] += 1
            parts.append(self._snlLine(mv, True))
        over = bool(moves) and moves[0]["to"] == 100
        if not over:
            mv = self._snlMove(1, 1 + self.rnd.randrange(6))
            moves.append(mv)
            m["rolls"] += 1
            parts.append(self._snlLine(mv, not skip))
            over = mv["to"] == 100
        m["moves"] = moves
        m["n"] += 1
        m["last"] = now
        m["asked"] = now
        m["animEnd"] = now + sum(x["ms"] for x in moves) / 1000.0
        if over:
            m["phase"] = "over"
            m["winner"] = 0 if m["pos"][0] == 100 else 1
            m["doneAt"] = now
            if m["winner"] == 0:
                self._ensure()["snlWins"] += 1
        else:
            parts.append(SNL_YOUR_GO)
        m["say"] = " ".join(parts)
        m["wait"] = now + SNL_ACK_S + sum(x["ms"] for x in moves[:1]) / 1000.0
        m["speakAt"] = 0.0
        m["voiceFrom"] = now + 1000.0           # no spoken command until Pepper has said it
        self._push()

    def _snlOk(self, tablet):
        """True when a command counts. Spoken (tablet is None): only after Pepper has finished and the board is still. A tap: only on
        the round that is on screen now, and not before the board has nearly stopped."""
        m = self.snl
        if m is None or m["phase"] != "play":
            return False
        now = self.clock()
        if tablet is None:
            if m["wait"] or m["speakAt"] or now < m["voiceFrom"] or now < m["animEnd"]:
                self._log("info", "[Care Controller] spoken command ignored: the game is still talking or moving")
                return False
            return True
        if (tablet[0] is not None and tablet[0] != m["k"]) or (tablet[1] is not None and tablet[1] != m["n"]):
            self._log("info", "[Care Controller] tap ignored: it was made on another round")
            return False
        if now < m["animEnd"] - SNL_TAP_SLACK_S:
            return False
        return now - m["asked"] >= SNL_THINK_S

    def _snlRoll(self, tablet=None, skip=False):
        if not self._snlOk(tablet):
            return
        if tablet is not None:
            self._call("ALTextToSpeech", "stopAll")       # a tap while Pepper is still talking
        self._snlRound(skip)

    def _snlSkip(self, tablet=None):
        self._snlRoll(tablet, skip=True)

    def _snlVoiceFree(self):
        """True when nothing is being said or moved (so a spoken 'new game' cannot be Pepper's own voice or an old echo)."""
        m = self.snl
        if m is None:
            return True
        return not (m["wait"] or m["speakAt"] or self.clock() < m["voiceFrom"] or self.clock() < m["animEnd"])

    def _snlRepeat(self):
        """Says the last thing again, once Pepper has finished saying it (also on the closing screen)."""
        m = self.snl
        if m is None or m["wait"] or m["speakAt"] or self.clock() < m["voiceFrom"]:
            return
        m["last"] = self.clock()
        self._snlSpeak()

    def _snlSpeak(self):
        m = self.snl
        if m is None:
            return
        now = self.clock()
        m["wait"], m["speakAt"] = 0.0, 0.0
        words = len(m["say"].split())
        m["voiceFrom"] = now + min(SNL_READ_MAX_S, SNL_READ_BASE_S + SNL_READ_WORD_S * words)
        self._write("snlText", m["say"])
        self._force("robotcmd snlend" if m["phase"] == "over" else "robotcmd snlsay")

    def _snlShown(self, k, n):
        """The tablet reports that it shows round n of game k: Pepper speaks once the dice have settled."""
        m = self.snl
        if m is not None and m["wait"] and k == m["k"] and n == m["n"]:
            m["wait"] = 0.0
            m["speakAt"] = self.clock() + (SNL_DICE_DELAY_S if m["moves"] else 0.0)
            if m["speakAt"] <= self.clock():
                self._snlSpeak()

    def _snlClear(self):
        self.snl = None
        if self.mode == "snl":
            self.mode = None

    def _snlTimers(self, now):
        m = self.snl
        if m is None:
            return
        if m["speakAt"] and now >= m["speakAt"]:
            self._snlSpeak()
        elif m["wait"] and now >= m["wait"]:
            self._snlSpeak()                  # no tablet answer in time (no tablet, or it is slow): voice only
        if m["phase"] == "play" and now - m["last"] > SNL_IDLE_S:
            self._snlClear()                  # quietly: somebody may be in the middle of a conversation
            self._push()
        elif m["phase"] == "over" and now - m["doneAt"] > SNL_END_S:
            self._snlClear()
            self._push()

    def _snlView(self):
        """What the tablet shows. Nothing secret in here."""
        m = self.snl
        if m is None:
            return None
        return {"k": m["k"], "n": m["n"], "phase": m["phase"], "pos": list(m["pos"]), "moves": list(m["moves"]), "say": m["say"],
                "winner": m["winner"], "rolls": m["rolls"], "ladders": m["ladders"], "snakes": m["snakes"]}

    # ------------------------------------------------------------------ guided breathing (a timed sequence, no thread)
    def _startBreathing(self):
        if self.mode is not None:
            self._stopAll()
        self.mode = "breathing"
        self._bump("breathing")
        self._body(True)
        self.breath = {"i": 0, "phase": "", "next": self.clock()}
        self._breathStep(self.clock())

    def _breathStep(self, now):
        b = self.breath
        n = self.breathCount
        names = ["LShoulderPitch", "RShoulderPitch"]
        if b["phase"] in ("", "out"):
            if b["i"] >= n:
                self._endBreathing()
                return
            b["i"] += 1
            b["phase"] = "in"
            self._js("PepperUI.breath && PepperUI.breath('in', %d, %d)" % (b["i"], n))
            self._post("ALMotion", "angleInterpolation", names, [BREATH_IN_RAD, BREATH_IN_RAD], [BREATH_IN_S, BREATH_IN_S], True)
            self._post("ALTextToSpeech", "say", "Breathe in slowly." if b["i"] == 1 else "Breathe in.")
            b["next"] = now + BREATH_CUE_S + BREATH_IN_HOLD
        else:
            b["phase"] = "out"
            self._js("PepperUI.breath && PepperUI.breath('out', %d, %d)" % (b["i"], n))
            self._post("ALMotion", "angleInterpolation", names, [BREATH_OUT_RAD, BREATH_OUT_RAD], [BREATH_OUT_S, BREATH_OUT_S], True)
            self._post("ALTextToSpeech", "say", "And breathe out." if b["i"] == 1 else "And out.")
            b["next"] = now + BREATH_CUE_S + BREATH_OUT_HOLD
        self._push()

    def _endBreathing(self):
        self.mode = None
        self.breath = None
        self._js("PepperUI.breath && PepperUI.breath('end', 0, 0)")
        self._body(False)
        self._force("robotcmd breathdone")
        self._push()

    # ------------------------------------------------------------------ help
    def _alert(self, reason="", urgent=True):
        if self.clock() - self.lastAlertAt < ALERT_DUP_S and reason == self.lastAlertReason:
            return                           # the dialog said it twice: one call for help, one entry
        self.lastAlertAt = self.clock()
        self.lastAlertReason = reason
        who = self.current["name"] if self.current is not None else "A patient"
        if self.current is not None:
            self.current["alert"] = True
        if self.mode is not None and urgent:
            self._stopAll()                  # nobody keeps exercising or dancing while a carer is being called
        self.alertId += 1
        entry = {"id": self.alertId, "name": who, "time": time.strftime("%H:%M", time.localtime(self.clock())),
                 "seen": False, "reason": reason}
        self.alerts.append(entry)
        self.alerts = self.alerts[-ALERTS_KEPT:]
        self._fire("onAlert")
        m = self._p("ALMemory")
        if m is not None:
            try:
                m.raiseEvent("Pepper/CaregiverAlert", json.dumps(entry))
            except Exception:
                pass
        self._js("PepperUI.alert && PepperUI.alert(%s)" % json.dumps(entry))

    # ------------------------------------------------------------------ staff: alerts and records
    def _ack(self, aid):
        """Marks one alert (or, with no id, every alert) as seen by staff."""
        for a in self.alerts:
            if aid is None or a.get("id") == aid:
                a["seen"] = True

    def _clearData(self):
        """Staff wipe: nothing about any patient stays in the robot's memory afterwards."""
        if self.mode is not None:
            self._stopAll()
        self.current = None
        self.calling = None
        self.history = []
        self.queue = []
        self.reminders = []
        self.alerts = []
        self.dueId = None
        self.quiz = None
        self.mem = None
        self.snl = None
        self.pick = None
        self.extraNames = []
        self.heard = ""                  # v4.0: what the robot last heard may hold a name
        self.heardUsed = ""
        self.dm = None
        self.sugg = None
        self.suggTried = []
        self.nuCount = 0
        self._write("Dialog/LastInput", "")   # the robot keeps the last heard text itself
        self._write("name", "")
        self._write("nextName", "")
        self._write("medFor", "")
        self._updateMedNext()
        d = self._p("ALDialog")
        if d is not None:
            for lang in ("English", "enu"):
                try:
                    d.setConcept("extraNames", lang, [])
                    break
                except Exception:
                    pass

    # ------------------------------------------------------------------ medication reminders
    def _fmt(self, t):
        lt = time.localtime(t)
        h = lt.tm_hour % 12 or 12
        return "%d:%02d %s" % (h, lt.tm_min, "a m" if lt.tm_hour < 12 else "p m")

    def _addReminder(self, due, who=None):
        who = who or (self.current["name"] if self.current is not None else "")
        if not who or due <= 0:
            return None
        r = {"id": self.nextRid, "name": who, "due": due, "label": self._fmt(due), "status": "pending"}
        self.nextRid += 1
        self.reminders.append(r)
        self.reminders = sorted(self.reminders, key=lambda x: x["due"])[-100:]
        self._updateMedNext()
        return r

    def _remindIn(self, minutes, who=None):
        if minutes <= 0:
            return None
        return self._addReminder(self.clock() + 60 * minutes, who)

    def _remindAt(self, hour, part, who=None):
        if not 1 <= hour <= 12:
            return None
        now = self.clock()
        lt = time.localtime(now)
        base = now - (lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec)
        options = []
        if part in ("am", "morning"):
            hours = [hour % 12]
        elif part in ("pm", "afternoon", "evening", "night"):
            hours = [hour % 12 + 12]
        else:
            hours = [hour % 12, hour % 12 + 12]
        for day in (0, 1):
            for h in hours:
                t = base + day * 86400 + h * 3600
                if t > now + 30:
                    options.append(t)
        return self._addReminder(min(options), who) if options else None

    def _remindClock(self, hhmm, who=None):
        try:
            h, m = [int(x) for x in str(hhmm).split(":")[:2]]
        except Exception:
            return None
        now = self.clock()
        lt = time.localtime(now)
        t = now - (lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec) + h * 3600 + m * 60
        if t <= now:
            t += 86400
        return self._addReminder(t, who)

    def _updateMedNext(self):
        who = self.current["name"].lower() if self.current is not None else None
        mine = [r for r in self.reminders if r["status"] == "pending" and who and r["name"].lower() == who]
        self._write("medNext", mine[0]["label"] if mine else "not set")

    def _checkReminders(self, now):
        if self.dueId is not None or self.mode in ("exercise", "breathing"):
            return
        for r in self.reminders:
            if r["status"] == "pending" and r["due"] <= now:
                if self.quiz is not None:
                    self._quizClear()        # a medicine reminder matters more than a question
                if self.mem is not None:
                    self._memClear()
                if self.snl is not None:
                    self._snlClear()
                r["status"] = "due"
                self.dueId = r["id"]
                self._write("medFor", r["name"])
                self._js("PepperUI.reminder && PepperUI.reminder(%s)" % json.dumps(r))
                self._force("robotcmd meddue")
                self._push()
                return

    def _dueAnswer(self, status):
        for r in self.reminders:
            if r["id"] == self.dueId:
                r["status"] = status
                if self.current is not None and self.current["name"].lower() == r["name"].lower():
                    self.current["med"] = status
        self.dueId = None
        self._updateMedNext()

    # ------------------------------------------------------------------ crowd (any number of visitors)
    def _count(self, maxDist):
        mem = self._p("ALMemory")
        if mem is None:
            return 0
        try:
            ids = list(mem.getData("PeoplePerception/PeopleList") or [])
        except Exception:
            return 0
        if maxDist <= 0 or not ids:
            return len(ids)
        near = {}
        try:
            data = mem.getData("PeoplePerception/PeopleDetected")
            for p in (data[1] if data and len(data) > 1 else []):
                near[p[0]] = float(p[1])
        except Exception:
            pass
        return len([i for i in ids if near.get(i, 0.0) <= maxDist])

    def _checkCrowd(self, now):
        try:
            allowed = int(self.getParameter("People allowed"))
            maxDist = float(self.getParameter("Max distance (m)"))
            hold = float(self.getParameter("Hold time (s)"))
            cool = float(self.getParameter("Cooldown (s)"))
        except Exception:
            return
        if allowed <= 0 or self.lagMode or self.mode is not None or self.quiz is not None or self.mem is not None or self.snl is not None:
            self.crowdSince = None      # a warning spoken over an activity would break it (and a stray face must never do that)
            return
        if self._count(maxDist) > allowed:
            if self.crowdSince is None:
                self.crowdSince = now
            ready = self.crowdLast is None or now - self.crowdLast >= cool
            if now - self.crowdSince >= hold and ready:
                self._force("robotcmd crowd")
                self.crowdLast = now
                self.crowdSince = None
        else:
            self.crowdSince = None


    # ------------------------------------------------------------------ tablet
    def _connectTablet(self):
        try:
            ts = self.session().service("ALTabletService")
            ts.onJSEvent.connect(self.onTablet)
        except Exception as e:
            self._log("warning", _fmt("[Care Controller] onJSEvent not available (%s); tablet uses ALMemory", e))

    def _js(self, code, kind=None):
        """Queues a tablet call for the sender thread (direct call when no sender runs). A new full state update
        replaces one still waiting (only the newest state matters); other calls keep their order."""
        if self.jsThread is None:
            self._jsNow(code)
            return
        self.jsLock.acquire()
        try:
            if kind in ("update", "ping"):
                self.jsq = [q for q in self.jsq if q[0] != kind]
            self.jsq.append((kind, code))
            if len(self.jsq) > 100:
                self.jsq = self.jsq[-100:]
        finally:
            self.jsLock.release()

    def _jsNow(self, code):
        ts = self._p("ALTabletService")
        if ts is None:
            return
        try:
            ts.executeJS(_s("try{") + _s(code) + _s("}catch(e){}"))
        except Exception:
            pass

    def _jsLoop(self):
        while self.running:
            item = None
            try:
                self.jsLock.acquire()
                try:
                    if self.jsq:
                        item = self.jsq.pop(0)
                finally:
                    self.jsLock.release()
                if item is None:
                    self.sleep(0.03)
                else:
                    self._jsNow(item[1])
            except Exception as e:
                self._log("error", _fmt("[Care Controller] tablet sender error (%s)", e))
                self.sleep(0.1)

    # ------------------------------------------------------------------ v4.1: optional laptop dashboard (off unless an address is set)
    def _dashStart(self):
        """Reads the box parameter "Dashboard URL". Empty means no link at all. A bad address is logged and ignored."""
        raw = self._param("Dashboard URL", "")
        url = dashboard_url(raw)
        if url is None:
            self._log("warning", _fmt("[Care Controller] Dashboard URL %r is not a usable address (use http://LAPTOP_IP:8100); the dashboard link is off", _s(raw)))
            return
        if not url:
            return
        self.dashUrl = url
        self._log("info", _fmt("[Care Controller] dashboard link on: %s (state is sent to this laptop on the local network)", url))
        self.dashThread = threading.Thread(target=self._dashLoop)
        self.dashThread.daemon = True
        self.dashThread.start()

    def _dashPost(self, url, data):
        """One POST with a short timeout. Tests replace this."""
        req = _urlreq.Request(url, data, {"Content-Type": "application/json"})
        _urlreq.urlopen(req, timeout=DASH_TIMEOUT_S).read()

    def _dashOnce(self):
        """Posts the newest state once. Returns True when there was nothing to do or it worked, False when the laptop could not be reached."""
        body = self.dashBody
        if body is None:
            return True
        data = ('{"sentAt":%.3f,"state":%s}' % (time.time(), body)).encode("utf-8")
        try:
            self._dashPost(self.dashUrl + "/api/care/state", data)
        except Exception as e:
            self.dashFails += 1
            if not self.dashDown:
                self.dashDown = True
                self._log("warning", _fmt("[Care Controller] dashboard not reachable (%s): Pepper carries on; trying again", e))
            return False
        self.dashSent += 1
        self.dashFails = 0
        if self.dashDown:
            self.dashDown = False
            self._log("info", "[Care Controller] dashboard reachable again")
        return True

    def _dashLoop(self):
        while self.running:
            try:
                self.dashEvt.wait(DASH_BEAT_S)           # a new state wakes this up; otherwise it re-sends the last one as a heartbeat
                if not self.running:
                    break
                self.dashEvt.clear()
                gap = DASH_MIN_GAP_S - (time.time() - self.dashLastSent)
                if gap > 0:
                    time.sleep(gap)
                self.dashLastSent = time.time()
                if not self._dashOnce():
                    waited = 0.0
                    limit = min(DASH_MAX_BACKOFF_S, 1.0 + self.dashFails)
                    while self.running and waited < limit:
                        time.sleep(0.25)
                        waited += 0.25
            except Exception as e:                       # nothing here may ever stop or slow the robot
                self._log("error", _fmt("[Care Controller] dashboard sender error (%s)", e))
                time.sleep(1.0)

    def state(self):
        ex = None
        if self.mode == "exercise" and self.exPhase is not None:
            ex = {"n": self.exIndex, "elapsed": round(self.clock() - self.exStart, 1), "total": int(self.exSeconds),
                  "phase": self.exPhase}
        br = None
        if self.mode == "breathing" and self.breath is not None:
            br = {"i": self.breath["i"], "n": self.breathCount, "phase": self.breath["phase"]}
        return {"v": VERSION, "run": self.token, "seq": self.seq, "current": self.current, "calling": self.calling, "history": self.history[-60:],
                "seenTotal": len(self.history), "queue": self.queue, "alerts": self.alerts[-10:],
                "alertsOpen": len([a for a in self.alerts if not a.get("seen")]), "mode": self.mode,
                "item": self.current_item if self.mode in ("music", "show") else "",
                "quiz": self._quizView(), "mem": self._memView(), "snl": self._snlView(), "pick": self._pickView(), "lastCmd": self.lastCmd, "heard": self.heard, "lag": self.lagMode, "voice": self.voiceOk, "exercise": ex, "breathing": br,
                "reminders": [r for r in self.reminders if r["status"] in ("pending", "due")][:12]}

    def _push(self, force=False):
        """Sends the state to the tablet only when something a person can see has changed; otherwise a tiny "still
        here" ping every 5 s, and the full state every 30 s to resynchronise (less traffic, less tablet lag)."""
        now = self.clock()
        st = self.state()
        ex = st["exercise"] or {}
        key = json.dumps([st["current"], st["calling"], len(self.history), st["queue"], st["alerts"], st["mode"],
                          st["reminders"], st["breathing"], ex.get("n"), ex.get("phase"), st["item"], st["quiz"], st["mem"], st["snl"], st["pick"], st["heard"], st["lag"], st["voice"]])
        if not force and key == self.lastKey and now - self.lastFull < 30.0:
            if now - self.lastPush >= 5.0:
                self.lastPush = now
                self._js("window.PepperUI && PepperUI.ping && PepperUI.ping()", "ping")
            return
        self.lastKey, self.lastFull = key, now
        self.seq += 1
        st["seq"] = self.seq
        self.lastPush = now
        payload = json.dumps(st)
        self._js("window.PepperUI && PepperUI.update(%s)" % payload, "update")
        if self.dashUrl:
            self.dashBody = payload                  # the newest state replaces any older one that was not sent yet
            self.dashEvt.set()
        m = self._p("ALMemory")
        if m is not None:
            try:
                m.insertData("Pepper/SessionState", payload)
                m.raiseEvent("Pepper/Session", payload)
            except Exception:
                pass

    def _tablet(self, raw):
        try:
            msg = json.loads(raw) if not isinstance(raw, dict) else raw
        except Exception:
            return
        if not isinstance(msg, dict):
            return
        mid = msg.get("id")
        if mid is not None:
            if mid in self.seenTablet:
                return
            self.seenTablet = (self.seenTablet + [mid])[-50:]
        cmd = _s(msg.get("cmd"))
        if cmd == "say" and _s(msg.get("text")) in TABLET_SAY:
            text = _s(msg["text"])
            if text == "stop":
                self._stopAll()          # the movement stops at once, the dialog then answers
            if text == "next" and self.mode != "exercise":
                text = None              # Skip only means something during the exercises
            if text and text != "quiz" and self.quiz is not None:
                self._quizClear()        # another tile was touched: the quiz is over
            if text and text != "relive" and self.mem is not None:
                self._memClear()
            if text and text != "snl" and self.snl is not None:
                self._snlClear()
            if text and text not in ("music", "activities") and self.pick is not None:
                self.pick = None         # something was chosen on the tablet: the list is done
                self._push()
            if text in TILE_TOKENS:
                self._force("robotcmd " + TILE_TOKENS[text])
            elif text:
                self._force(text)
        elif cmd == "name":
            name = self._clean(msg.get("name", ""))
            if name:
                self._addExtraName(name)
                first = not self.introduced          # the first person since Pepper started hears what Pepper can do
                self.startSession(name)
                self._force("robotcmd registeredfirst" if first else "robotcmd registered")
        elif cmd == "queue":
            name = self._clean(msg.get("name", ""))
            taken = [q.lower() for q in self.queue] + [(self.calling or "").lower()]
            if self.current is not None:
                taken.append(self.current["name"].lower())
            if name and name.lower() not in taken:
                self._addExtraName(name)
                self.queue.append(name)
                if self.mode is None:
                    self._callNext()
        elif cmd == "unqueue":
            self.queue = [q for q in self.queue if q.lower() != _s(msg.get("name", "")).lower()]
        elif cmd == "remind":
            if msg.get("minutes"):
                try:
                    self._remindIn(int(msg["minutes"]))
                except (TypeError, ValueError):
                    pass
            elif msg.get("at"):
                self._remindClock(_s(msg["at"]))
        elif cmd == "hello":
            self._push(force=True)             # a (re)loaded tablet page gets the full state at once
            return
        elif cmd == "quizAnswer":
            try:
                self._quizAnswer(int(msg.get("n")), (self._intOrNone(msg.get("k")), self._intOrNone(msg.get("q"))))
            except (TypeError, ValueError):
                pass
        elif cmd == "quizShown":
            self._quizShown(self._intOrNone(msg.get("k")), self._intOrNone(msg.get("q")))
        elif cmd == "quizClose":
            if self.quiz is not None:
                self._quizClear()
                self._force("robotcmd quizidle")
        elif cmd in ("memNext", "memBack", "memLike", "memShown", "memAnswer"):
            k, n = self._intOrNone(msg.get("k")), self._intOrNone(msg.get("n"))
            if cmd == "memAnswer":
                try:
                    self._memAnswer(int(msg.get("a")), (k, n))
                except (TypeError, ValueError):
                    pass
            elif cmd == "memShown":
                self._memShown(k, n)
            elif cmd == "memLike":
                self._memLike(k, n)
            else:
                self._memMove(1 if cmd == "memNext" else -1, (k, n))
        elif cmd == "memClose":
            if self.mem is not None:
                self._memClear()
                self._force("robotcmd memidle")
        elif cmd in ("snlRoll", "snlSkip", "snlShown"):
            k, n = self._intOrNone(msg.get("k")), self._intOrNone(msg.get("n"))
            if cmd == "snlShown":
                self._snlShown(k, n)
            elif cmd == "snlRoll":
                self._snlRoll((k, n))
            else:
                self._snlSkip((k, n))
        elif cmd == "snlNew":
            m = self.snl
            if m is not None and m["phase"] == "over" and self._intOrNone(msg.get("k")) in (None, m["k"]):
                self._snlStart(force=True)
        elif cmd == "snlClose":
            if self.snl is not None:
                self._snlClear()
                self._force("robotcmd snlidle")
        elif cmd == "ack":
            aid = msg.get("alert")
            try:
                aid = None if aid is None else int(aid)
            except (TypeError, ValueError):
                aid = None
            self._ack(aid)
        elif cmd == "clearData":
            self._clearData()
        elif cmd == "endSession":
            self._closeSession()
            self._force("robotcmd closed")
            self._callNext()
        self._push()

    def _intOrNone(self, v):
        try:
            return None if v is None else int(v)
        except (TypeError, ValueError):
            return None

    def _addExtraName(self, name):
        first = name.split()[0].lower()
        if first in self.extraNames:
            return
        self.extraNames = (self.extraNames + [first])[-200:]
        d = self._p("ALDialog")
        if d is None:
            return
        for lang in ("English", "enu"):
            try:
                d.setConcept("extraNames", lang, [_s(n) for n in self.extraNames])
                return
            except Exception:
                pass
