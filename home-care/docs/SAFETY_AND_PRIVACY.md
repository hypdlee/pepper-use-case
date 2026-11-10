# Safety and privacy notes

This is a research prototype for supervised use by care professionals. It is not a medical device.

## Privacy

- By default nothing leaves the robot. There is no cloud service, no account, and no network request from the tablet page.
- Optional exception (v4.1): if you type an address into the Care Controller parameter "Dashboard URL", the robot sends what the Staff view shows (first names, activity, alerts with reasons, records, the last words heard) to that one laptop on the local network, unencrypted and without a password. Use it only on a private network, with staff who are allowed to see that. The dashboard program keeps it in memory, logs no names, writes nothing to disk, and Clear all records clears it. Leave the parameter empty and nothing is sent.
- Names, session counts, quiz scores, the number of Snakes and Ladders games played and won, liked memory topics and chosen answers, alerts and reminders are held only in Pepper's memory while the behaviour runs. They are lost when it stops.
- There is no analysis of a resident's face. Pepper's people detection only counts how many people stand close, and nothing from it is stored.
- The last words Pepper heard are shown in the Staff view and kept only in Pepper's memory (the last phrase only, at most 60 characters), and is wiped with Clear all records. Nothing is sent anywhere. Calm mode turns face recognition off.
- Staff can wipe everything with Clear all records. It also removes typed names from the dialog and the tablet's own "How do I feel" answers.
- Relive Malta has no right or wrong answers and keeps only which topics were liked and which of the two offered answers was chosen (never what was said). Memories can bring up strong feelings, so a carer should sit with the resident and press Stop if they seem upset.

## Safety

- Exercises are gentle, seated-friendly movements of 40 seconds each. Joint angles in every timeline were checked against Pepper's limits. A staff member stays with the resident.
- "Stop" works at any time by voice or by the tablet button. It stops movement and music at once.
- Help stops all movement, then flashes Pepper's eyes and alerts the tablet. It does not page anyone, so a person must be watching the Staff view or the room.
- Safety phrases ("I have fallen", "I am in pain", "I feel dizzy", "I can not breathe") raise an urgent alert with the reason shown to staff and stop movement. They depend on speech recognition hearing the words, so they are an extra, never a replacement for the Help button, for supervision, or for a real nurse call system.
- Needs ("toilet", "drink", "food", "cold", "hot") raise a normal alert with the reason. They do not stop the activity.
- Jokes, facts, time and suggestions are fixed texts and the robot clock. Pepper does not give medical, dosing or diagnostic answers and does not make them up.
- If the robot becomes slow, a watchdog pauses tracking so that listening keeps working. It is not a safety function.
- Medicine features are prompts only. Pepper never says a dose and never decides what a person should take. The nurse's instructions always apply.
- Any exercise, music or show is stopped before the quiz, Snakes and Ladders or Relive Malta starts.
- Snakes and Ladders is a game of chance with no stakes and no score that is judged. The dice are fair and the controller rolls them, so the tablet and Pepper always agree. Pepper never speaks over its own commands: a spoken "roll" or "new game" counts only after Pepper has finished talking, and a game left alone for ten minutes closes silently. Pepper plays at the resident's pace; the resident can skip a turn or press Stop at any time.

## Before a real deployment

Test with staff and residents, set up a real nurse call link, review the wording with a clinician, and check local rules on consent and data.
