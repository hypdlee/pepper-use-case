# The 100 quiz questions. Run this file to write them into ChampionshipHost/html/data/content.json.
# Each entry: question, correct answer, two wrong answers, short reason. The tablet shuffles the answers.
# Sources: Rulebook v0.7 (final draft), the organisers' running order and team sheet, ieeemalta.org, general robotics.
import io, json, os, sys

Q = [
    # ---- Arena games (Rulebook v0.7)
    ("In Time of Fall, what do the robots try to do?", "Pull the other robot into the pit", "Build a tower", "Sort coloured shapes", "It is a tug of war over the pit."),
    ("How long can a Time of Fall game last?", "60 seconds", "10 minutes", "One hour", "Sixty seconds at most."),
    ("In Time of Fall, what joins the two robots?", "A chain", "A rope bridge", "A magnet", "The robots are joined by a chain."),
    ("Which game is Arena Game 1?", "Time of Fall", "Hanging Hazard", "Weight in Line", "The Arena starts with Time of Fall."),
    ("In Climate CHAOS, where are the survivors?", "Under three towers", "On a boat", "Up a tree", "One survivor under each of three towers, worth 50, 100 and 150 points."),
    ("Where must a rescued survivor end up in Climate CHAOS?", "In the safe zone", "On top of a tower", "In the flood", "A survivor counts once it is fully inside the safe zone."),
    ("Which of these is a hazard in Climate CHAOS?", "A fire", "A volcano", "A snowstorm", "Sinkholes, floods and a fire."),
    ("How many points is the best Climate CHAOS tower worth?", "150", "15", "1500", "The towers are worth 50, 100 and 150 points."),
    ("What happens if a tower collapses in Climate CHAOS?", "The team loses points", "The team wins", "Nothing at all", "A collapsed tower costs points."),
    ("How long is a Climate CHAOS run?", "5 minutes", "30 seconds", "2 hours", "Five minutes."),
    ("In Weight in Line, where do the weights go?", "Into the team's rings", "Into a basket", "Onto a shelf", "Each robot places weights in its own rings."),
    ("How many weights are there in Weight in Line?", "Six", "Two", "Twenty", "Six weights, worth 5 to 30 points."),
    ("What is the most a single weight is worth in Weight in Line?", "30 points", "3 points", "300 points", "From 5 up to 30 points."),
    ("When does a weight score full points?", "When it sits perfectly in its ring", "When it is thrown high", "When it is painted", "A perfectly placed weight scores full points."),
    ("What ends a Weight in Line game early?", "A robot falling into a pit", "A robot singing", "The lights going off", "Five minutes, or until a robot falls into a pit."),
    ("Which ball is used in Hanging Hazard?", "A rugby ball", "A tennis ball", "A golf ball", "Robots score rugby balls."),
    ("Where do robots score in Hanging Hazard?", "In the other team's pocket", "In their own pocket", "On the ceiling", "Rugby balls go into the opponent's pocket."),
    ("How long is a Hanging Hazard game?", "8 minutes", "8 seconds", "8 hours", "Eight minutes."),
    ("Which game decides the Arena champion?", "Hanging Hazard", "Time of Fall", "Climate CHAOS", "Hanging Hazard is used for the final and third place."),
    ("How big is the Arena?", "6 by 6 metres", "1 by 1 metre", "100 by 100 metres", "6 by 6 metres."),
    ("How heavy can an Arena robot be?", "20 kilograms", "200 kilograms", "2 kilograms", "Up to 20 kilograms."),
    ("How wide can an Arena robot be?", "80 by 80 centimetres", "8 by 8 metres", "8 by 8 centimetres", "Up to 80 by 80 centimetres."),
    ("What must every Arena robot have, for safety?", "A kill switch", "A horn", "A flag", "A clearly marked kill switch turns the robot off."),
    ("How many people can be in an Arena team?", "Up to three", "Up to thirty", "Only one", "Teams of up to three."),
    ("How are Arena robots driven?", "By the team, with a remote control", "By the audience", "By Pepper", "Teams drive their robots by remote control."),
    ("How many games are in the Arena?", "Four", "One", "Ten", "Time of Fall, Climate CHAOS, Weight in Line, Hanging Hazard."),
    # ---- Robot Arm AI Challenge
    ("What is new at the championships in 2026?", "The Robot Arm AI Challenge", "A swimming race", "A cooking contest", "The Robot Arm AI Challenge is new for 2026."),
    ("How many people are in a Robot Arm team?", "Two", "Ten", "Fifty", "Teams of two."),
    ("How many robot arms does each team use?", "Two", "One", "Eight", "Two arms that work together."),
    ("Who controls the robot arms during a scored run?", "Nobody: they work on their own", "A joystick", "A phone app", "The arms see and decide by themselves."),
    ("What is Game 1 of the Robot Arm AI Challenge called?", "Pick-and-Place", "Hide and Seek", "Tug of War", "Game 1 is Pick-and-Place."),
    ("In Colour Sort, where does each shape go?", "In the bin of the same colour", "In the biggest bin", "Back in the box", "Each shape goes in the bin of its colour."),
    ("In Shape Sort, which bin does a cube go into?", "The red bin", "The blue bin", "No bin", "Cubes go in the red bin."),
    ("In Shape Sort, which bin does a cylinder go into?", "The blue bin", "The red bin", "The yellow bin", "Cylinders go in the blue bin."),
    ("What makes Dynamic Sort tricky?", "Judges move bins and objects during the run", "It is played in the dark", "The arms are upside down", "The arms must notice changes and plan again."),
    ("How long is a sorting round?", "5 minutes", "5 seconds", "5 hours", "Five minutes per round."),
    ("What happens when a shape goes in the wrong bin?", "The team loses points", "The team gets a bonus", "The round restarts", "A wrong bin costs points."),
    ("What is Game 2 of the Robot Arm AI Challenge?", "Two-Arm Coordination", "Arm Wrestling", "Robot Dancing", "Game 2 tests two arms working together."),
    ("In Pouring, what do the arms pour?", "Rice", "Water", "Sand", "125 grams of rice."),
    ("How much rice is in the cup in Pouring?", "125 grams", "125 kilograms", "1 gram", "125 grams."),
    ("In Pouring, what does the second arm hold?", "The bowl", "A spoon", "A flag", "One arm holds the cup, the other the bowl."),
    ("How many Pouring runs does a team get?", "Three, and the best counts", "One only", "Twenty", "Three runs; the best one counts."),
    ("In Folding, what do the arms fold?", "Square cloths", "Paper planes", "Metal sheets", "Four soft square cloths."),
    ("How many cloths are folded in Folding?", "Four", "Forty", "One", "Four cloths."),
    ("How many times is each cloth folded?", "Twice", "Ten times", "Never", "Twice, to about 15 centimetres."),
    ("Why is folding hard for a robot?", "Cloth is soft and floppy", "Cloth is too heavy", "Cloth is invisible", "Floppy things are hard to grab and predict."),
    ("Which teams play the Tower Construction Duel?", "The two best teams", "Every team at once", "Only the youngest team", "The top two teams meet in the final."),
    ("How many points is each block in a stable tower worth?", "5 points", "50 points", "500 points", "5 points per block."),
    ("In the Tower Duel, which blocks may be thrown?", "Red blocks", "Blue blocks", "No blocks", "Only red ones, once your tower is 6 blocks high."),
    ("How high must your tower be before you may throw?", "6 blocks", "60 blocks", "1 block", "Six blocks high."),
    ("How long is the Tower Construction Duel?", "15 minutes", "15 seconds", "15 hours", "Fifteen minutes."),
    ("When may a team speak to its arms in the Tower Duel?", "When the judge blows the whistle", "Whenever they like", "Never, not even once", "One short idea in each 30-second whistle window."),
    ("What happens if a Climate CHAOS robot drives into a flood?", "The run ends", "It gets extra points", "Nothing at all", "Driving into a flood is a washout: the run ends."),
    # ---- the event
    ("What is the name of the championship mascot?", "3-e", "R2", "Bolt", "Meet 3-e!"),
    ("When are the IEEE Robot Championships 2026?", "28 and 29 November", "1 and 2 January", "In the summer", "Saturday 28 and Sunday 29 November 2026."),
    ("Where are the championships held?", "Montekristo Estate, Malta", "On the Moon", "In a submarine", "Montekristo Estate, Malta."),
    ("How many teams compete in the Arena?", "Eight", "Eighty", "Two", "Eight Arena teams."),
    ("How many teams compete in the Robot Arm AI Challenge?", "Five", "Fifty", "One", "Five Robot Arm teams."),
    ("How many games are there in total?", "Seven", "Seventy", "Three", "Four Arena games and three Robot Arm games."),
    ("Who organises the championships?", "IEEE Malta Section", "A football club", "A pizza shop", "The IEEE Malta Section and the IEEE Computer Society Malta Chapter."),
    ("What does every team also present?", "An AI for Humanity pitch", "A cooking show", "A magic trick", "Every team presents an AI pitch."),
    ("What is IEEE's mission?", "Advancing Technology for Humanity", "Faster cars for everyone", "Robots instead of people", "Advancing Technology for Humanity."),
    ("What does IEEE stand for?", "Institute of Electrical and Electronics Engineers", "International Energy and Engine Experts", "Institute of Easy Electronic Experiments", "IEEE is the Institute of Electrical and Electronics Engineers."),
    ("What can visitors explore besides the games?", "A STEM area with hands-on activities", "A water park", "A zoo", "A large interactive STEM area."),
    ("What material are the game objects 3D printed in?", "PLA plastic", "Gold", "Glass", "They are printed in PLA."),
    ("What is the capital city of Malta?", "Valletta", "Rome", "Madrid", "Valletta is Malta's capital."),
    # ---- Pepper
    ("What kind of robot is Pepper?", "A humanoid robot", "A drone", "A robot vacuum", "Pepper is human-shaped: a humanoid."),
    ("How does Pepper move around?", "On wheels", "On two legs", "By flying", "Pepper rolls on wheels."),
    ("Where is Pepper's tablet?", "On its chest", "On its back", "On its head", "The tablet is on Pepper's chest."),
    ("About how tall is Pepper?", "1.2 metres", "12 metres", "12 centimetres", "About 1.2 metres."),
    ("Which company first made Pepper?", "Aldebaran", "LEGO", "NASA", "Pepper was made by Aldebaran, with SoftBank."),
    ("In which year was Pepper first shown?", "2014", "1914", "2064", "Pepper was introduced in 2014."),
    ("Is Pepper taking part in the games today?", "No, Pepper is the host", "Yes, in the Arena", "Yes, in Pouring", "Pepper is the host, not a competitor."),
    ("What does Pepper use to hear you?", "Microphones", "A periscope", "A thermometer", "Pepper has microphones in its head."),
    # ---- robots, sensors and AI
    ("Where does the word 'robot' come from?", "A Czech play from 1920", "An ancient Roman book", "A video game", "Karel Capek's play R.U.R. used the word robot."),
    ("What did the Czech word 'robota' mean?", "Hard work", "Metal man", "Fast car", "Robota means forced or hard work."),
    ("What was the first robot used in a factory called?", "Unimate", "Robby", "Wall-E", "Unimate started work in a car factory in 1961."),
    ("What is a humanoid robot?", "A robot shaped like a person", "A robot that only swims", "A robot made of wood", "Humanoid means human-shaped."),
    ("What does a sensor do?", "It measures something", "It makes the robot heavier", "It paints the robot", "Sensors measure light, distance, sound and more."),
    ("What does a motor do in a robot?", "It makes parts move", "It stores pictures", "It cools the room", "Motors turn energy into movement."),
    ("What is the 'brain' of most robots?", "A computer processor", "A battery", "A wheel", "A processor runs the robot's program."),
    ("What does a LiDAR sensor use to measure distance?", "Laser light", "Smell", "Taste", "LiDAR times laser light bouncing back."),
    ("What does an ultrasonic sensor use?", "Sound echoes", "Magnets", "Smoke", "It listens for echoes, like a bat."),
    ("What does a gyroscope sense?", "Turning", "Colour", "Temperature", "A gyroscope measures rotation."),
    ("What does a camera give a robot?", "Vision", "Hearing", "Smell", "Cameras let robots see."),
    ("What is the part that grabs things on a robot arm called?", "A gripper", "A propeller", "A wheel", "The gripper grabs objects."),
    ("What are the bending points of a robot arm called?", "Joints", "Tracks", "Wheels", "Motors turn the joints, like your elbow and wrist."),
    ("What is a robot that works without a remote control called?", "Autonomous", "Rusty", "Manual", "Autonomous robots decide by themselves."),
    ("What does AI stand for?", "Artificial Intelligence", "Automatic Ink", "Advanced Iron", "AI is Artificial Intelligence."),
    ("How does machine learning learn?", "From lots of examples", "From sleeping", "From eating", "Machine learning finds patterns in examples."),
    ("Which robot made the first powered flight on another planet?", "Ingenuity, on Mars", "Pepper, on the Moon", "A drone on Venus", "NASA's Ingenuity helicopter flew on Mars in 2021."),
    ("Which planet do the rovers Curiosity and Perseverance explore?", "Mars", "Jupiter", "The Sun", "Both rovers explore Mars."),
    ("Which famous author wrote the Three Laws of Robotics?", "Isaac Asimov", "William Shakespeare", "J. K. Rowling", "Isaac Asimov wrote them in his stories."),
    ("What does a 3D printer do?", "Builds objects layer by layer", "Prints only on paper", "Takes photos", "It builds objects one thin layer at a time."),
    ("Which wheels let a robot drive sideways?", "Mecanum wheels", "Square wheels", "Wooden wheels", "Mecanum wheels have angled rollers."),
    ("What does a robot use to store energy?", "A battery", "A sponge", "A mirror", "Batteries power most mobile robots."),
    ("What is a drone?", "A flying robot", "A robot fish", "A robot dog", "Drones are flying robots."),
    ("Which language of 0s and 1s do computers use?", "Binary", "Latin", "Morse code only", "Computers work in binary."),
    ("What do we call many small robots working together?", "A swarm", "A herd", "A forest", "Swarm robots cooperate like bees."),
    ("What does the big red stop button on a robot do?", "Stops the robot at once", "Makes it go faster", "Turns on music", "It cuts the robot's power straight away."),
]

def build():
    seen = set()
    out = []
    for q, ok, w1, w2, why in Q:
        assert q not in seen, "duplicate question: " + q
        seen.add(q)
        assert len({ok, w1, w2}) == 3, q
        assert u"\u2014" not in (q + ok + w1 + w2 + why)
        out.append({"q": q, "a": [ok, w1, w2], "ok": 0, "why": why})
    return out

if __name__ == "__main__":
    bank = build()
    assert len(bank) == 100, "the quiz needs exactly 100 questions, found %d" % len(bank)
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ChampionshipHost", "html", "data", "content.json")
    c = json.load(io.open(p, encoding="utf-8"))
    c["quiz"] = bank
    io.open(p, "w", encoding="utf-8").write(json.dumps(c, indent=2, ensure_ascii=True) + "\n")
    print("quiz: %d questions written" % len(bank))
