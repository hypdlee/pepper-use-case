"""Builds the Choregraphe project in ChampionshipHost/: behavior_1/behavior.xar (with src/host_controller.py inside the
Host Controller box), manifest.xml and ChampionshipHost.pml (every file listed as a resource)."""
import os, io, re, sys
from xml.sax.saxutils import escape, quoteattr

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(HERE, "ChampionshipHost")
SRC = os.path.join(HERE, "src", "host_controller.py")
UUID, NAME = "ieee-championship-host", "IEEE Championship Host"

def version():
    m = re.search(r'^VERSION = "([0-9.]+)"', io.open(SRC, encoding="utf-8").read(), re.M)
    return m.group(1)

IO_STD = ('<Input name="onLoad" type="1" type_size="1" nature="0" inner="1" tooltip="Signal sent when diagram is loaded." id="1" />'
          '<Input name="onStart" type="1" type_size="1" nature="2" inner="0" tooltip="Box behavior starts when a signal is received on this input." id="2" />'
          '<Input name="onStop" type="1" type_size="1" nature="3" inner="0" tooltip="Box behavior stops when a signal is received on this input." id="3" />'
          '<Output name="onStopped" type="1" type_size="1" nature="1" inner="0" tooltip="Signal sent when box behavior is finished." id="4" />')

SHOW_APP = r'''<Box name="Show App" id="2" localization="8" tooltip="Loads this application on the tablet and shows its web page." x="40" y="40"><bitmap>media/images/box/root.png</bitmap><script language="4"><content><![CDATA[

class MyClass(GeneratedClass):

    def __init__(self):
        GeneratedClass.__init__(self)

    def onLoad(self):
        self.isRunning = False

    def onUnload(self):
        self.isRunning = False

    def _getTabletService(self):
        tabletService = None
        try:
            tabletService = self.session().service("ALTabletService")
        except Exception as e:
            self.logger.error(e)
        return tabletService

    def onInput_onStart(self):
        if self.isRunning:
            return
        self.isRunning = True
        tabletService = self._getTabletService()
        appName = self.packageUid()
        state = False
        if appName and tabletService:
            if tabletService.loadApplication(appName):
                self.logger.info("Successfully set application: %s" % appName)
                tabletService.showWebview()
                state = True
            else:
                self.logger.warning("Got tablet service, but failed to set application: %s" % appName)
        else:
            self.logger.warning("Couldn't find tablet service or app name, so can't set application")
        if state:
            self.onSuccess()
        else:
            self.isRunning = False
            self.onFailure()]]></content></script><Input name="onLoad" type="1" type_size="1" nature="0" inner="1" tooltip="Signal sent when diagram is loaded." id="1" /><Input name="onStart" type="1" type_size="1" nature="2" inner="0" tooltip="Box behavior starts when a signal is received on this input." id="2" /><Output name="onSuccess" type="1" type_size="1" nature="1" inner="0" tooltip="Signal sent when box behavior is finished successfully." id="3" /><Output name="onFailure" type="1" type_size="1" nature="1" inner="0" tooltip="Signal sent when box behavior is finished unsuccessfully." id="4" /></Box>'''

PARAMS = [
    ("Staff PIN", 3, "2026", "PIN for staff mode on the tablet (tap the title five times). Change it before the event."),
    ("Match calls", 0, "1", "On: ten minutes before each block of matches (and before the opening and the awards), Pepper calls the teams. Staff can also switch this on the tablet."),
    ("Greet visitors", 0, "1", "On: Pepper says hello when someone comes close (at most every 2 minutes)."),
    ("Intro when idle (minutes)", 1, "10", "Pepper gives its intro by itself after this many quiet minutes, if someone is near. 0 = only when asked. Staff can also switch this off on the tablet."),
    ("Announce match starts", 0, "0", "On: Pepper also announces every match as it starts. Off: only one call ten minutes before each block of matches."),
]

def controller_box(code):
    assert "]]>" not in code, "the controller source must not contain ]]>"
    ps = "".join('<Parameter name=%s inherits_from_parent="0" content_type="%d" value=%s default_value=%s tooltip=%s id="%d" />' % (
        quoteattr(n), t, quoteattr(v), quoteattr(v), quoteattr(tip), 5 + i) for i, (n, t, v, tip) in enumerate(PARAMS))
    tip = ("Host Controller v%s. Pepper's voice and memory as the neutral host of the IEEE Robot Championships 2026: answers what the "
           "dialog heard, keeps the tablet up to date, holds teams, programme, provisional scores and volunteer calls, and calls teams "
           "10 minutes before their match. Nothing goes to the internet." % version())
    return ('<Box name="Host Controller" id="4" localization="8" tooltip=%s x="300" y="120"><bitmap>media/images/box/box-python-script.png</bitmap>'
            '<script language="4"><content><![CDATA[%s]]></content></script>%s%s</Box>') % (quoteattr(tip), code, IO_STD, ps)

# No Dialog box: the Host Controller loads Host/Host_enu.top itself, clearing any copy an earlier run left loaded.
# (A Dialog box fails with "topic is already loaded" when that happens, and the box turns red.)
LINKS = [(2, 2, 0, 2), (4, 2, 0, 2), (4, 3, 0, 3), (0, 4, 4, 4)]

def xar():
    code = io.open(SRC, encoding="utf-8").read()
    head = ('<?xml version="1.0" encoding="UTF-8" ?><ChoregrapheProject xmlns="http://www.aldebaran-robotics.com/schema/choregraphe/project.xsd" xar_version="3">'
            '<Box name="root" id="-1" localization="8" tooltip="Root box of Choregraphe&apos;s behavior. Highest level possible." x="0" y="0">'
            '<bitmap>media/images/box/root.png</bitmap><script language="4"><content><![CDATA[]]></content></script>' + IO_STD +
            '<Timeline enable="0"><BehaviorLayer name="behavior_layer1"><BehaviorKeyframe name="keyframe1" index="1"><Diagram>')
    links = "".join('<Link inputowner="%d" indexofinput="%d" outputowner="%d" indexofoutput="%d" />' % l for l in LINKS)
    tail = '</Diagram></BehaviorKeyframe></BehaviorLayer></Timeline></Box></ChoregrapheProject>'
    return head + SHOW_APP + controller_box(code) + links + tail

def manifest():
    return ('<?xml version=\'1.0\' encoding=\'UTF-8\'?>\n<package uuid="%s" version="%s">\n <names>\n  <name lang="en_US">%s</name>\n </names>\n'
            ' <supportedLanguages>\n  <language>en_US</language>\n </supportedLanguages>\n <descriptionLanguages>\n  <language>en_US</language>\n </descriptionLanguages>\n'
            ' <contents>\n  <behaviorContent path="behavior_1">\n   <userRequestable/>\n   <nature>interactive</nature>\n   <permissions/>\n  </behaviorContent>\n'
            ' </contents>\n</package>\n') % (UUID, version(), NAME)

def pml():
    files = []
    for root, _, names in os.walk(PKG):
        for n in sorted(names):
            rel = os.path.relpath(os.path.join(root, n), PKG).replace("\\", "/")
            if rel in ("manifest.xml", "ChampionshipHost.pml", "behavior_1/behavior.xar"):
                continue
            files.append(rel)
    files.sort()
    seen, res = set(), []
    for rel in files:
        base = re.sub(r"[^A-Za-z0-9]+", "-", rel.rsplit(".", 1)[0]).strip("-").lower()
        k, i = base, 2
        while k in seen:
            k, i = "%s-%d" % (base, i), i + 1
        seen.add(k)
        res.append('        <File name=%s src=%s />' % (quoteattr(k), quoteattr(rel)))
    return ('<?xml version="1.0" encoding="UTF-8" ?>\n<Package name="%s" format_version="4">\n    <Manifest src="manifest.xml" />\n'
            '    <BehaviorDescriptions>\n        <BehaviorDescription name="behavior" src="behavior_1" xar="behavior.xar" />\n    </BehaviorDescriptions>\n'
            '    <Resources>\n%s\n    </Resources>\n'
            '    <IgnoredPaths />\n</Package>\n') % (NAME, "\n".join(res))

if __name__ == "__main__":
    os.makedirs(os.path.join(PKG, "behavior_1"), exist_ok=True)
    io.open(os.path.join(PKG, "behavior_1", "behavior.xar"), "w", encoding="utf-8").write(xar())
    io.open(os.path.join(PKG, "manifest.xml"), "w", encoding="utf-8").write(manifest())
    io.open(os.path.join(PKG, "ChampionshipHost.pml"), "w", encoding="utf-8").write(pml())
    print("built v%s: xar %d bytes, %d resources" % (version(), os.path.getsize(os.path.join(PKG, "behavior_1", "behavior.xar")), pml().count("<File ")))
