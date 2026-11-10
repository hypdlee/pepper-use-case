// Care Dashboard page: real server (Python), real browser (Chromium). Every kind of state, names as hostile text, stale robot, lost server, phone width.
const path = require("path"), fs = require("fs"), cp = require("child_process"), net = require("net");
const { chromium } = require("playwright");
const acorn = require("acorn");
const DIR = "/home/claude/hack/dashboard";
let pass = 0; const fails = [];
function ok(c, m) { if (c) { pass++; } else { fails.push(m); } }
const sleep = ms => new Promise(r => setTimeout(r, ms));
const html = fs.readFileSync(path.join(DIR, "dashboard.html"), "utf8");
const script = (html.match(/<script>([\s\S]*?)<\/script>/) || [])[1] || "";
try { acorn.parse(script, { ecmaVersion: 5 }); ok(true, ""); } catch (e) { ok(false, "ES5 parse: " + e.message); }

function freePort() { return new Promise(res => { const s = net.createServer(); s.listen(0, "127.0.0.1", () => { const p = s.address().port; s.close(() => res(p)); }); }); }
const state = (o) => Object.assign({ v: "4.1.1", run: "R1", seq: 1, current: null, calling: null, history: [], seenTotal: 0, queue: [], alerts: [], alertsOpen: 0, mode: null, item: "", quiz: null, mem: null, snl: null, pick: null, exercise: null, breathing: null, reminders: [], heard: "", lag: false }, o || {});
const person = (o) => Object.assign({ name: "Maria", start: "10:00", exercises: 2, music: 1, performances: 0, breathing: 1, quizzes: 1, quizLast: "4/5", med: "taken", moodLow: false, alert: false, memCards: 3, memLikes: ["The Gozo ferry"], memAnswers: ["Pastizzi and tea: Ricotta"], snlGames: 2, snlWins: 1 }, o || {});

(async () => {
  const port = await freePort();
  const srv = cp.spawn("python3", ["-c", "import sys; sys.path.insert(0, %j); import care_dashboard as cd; cd.STALE_S = 2.0; sys.exit(cd.main(['--port', '%d', '--host', '127.0.0.1']))".replace("%j", JSON.stringify(DIR)).replace("%d", String(port))], { stdio: "ignore" });
  const base = "http://127.0.0.1:" + port;
  for (let i = 0; i < 60; i++) { try { const r = await fetch(base + "/api/health"); if (r.ok) { break; } } catch (e) { await sleep(100); } }
  const post = (s) => fetch(base + "/api/care/state", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sentAt: Date.now() / 1000, state: s }) }).then(r => r.status);
  const b = await chromium.launch();
  async function open(w, h) {
    const ctx = await b.newContext({ viewport: { width: w, height: h } });
    const p = await ctx.newPage();
    p.errs = []; p.reqs = [];
    p.on("pageerror", e => p.errs.push(String(e))); p.on("console", m => { if (m.type() === "error") { p.errs.push(m.text()); } });
    p.on("request", r => p.reqs.push(r.url()));
    await p.addInitScript(() => { window.__osc = 0; window.AudioContext = function () { this.currentTime = 0; this.destination = {}; this.createOscillator = function () { window.__osc++; return { type: "", frequency: {}, connect: function () {}, start: function () {}, stop: function () {} }; }; this.createGain = function () { return { gain: { setValueAtTime: function () {}, exponentialRampToValueAtTime: function () {} }, connect: function () {} }; }; }; });
    await p.goto(base + "/");
    return p;
  }
  const txt = (p, sel) => p.$eval(sel, e => e.textContent);
  const vis = (p, sel) => p.$eval(sel, e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(e).display !== "none"; });
  const wait = async (p, fn, ms, arg) => { for (let i = 0; i < (ms || 3000) / 100; i++) { if (await p.evaluate(fn, arg)) { return true; } await sleep(100); } return false; };
  const connText = p => txt(p, "#conn-text");

  let p = await open(1280, 800);
  await sleep(1300);
  ok((await connText(p)).indexOf("Waiting for Pepper") === 0, "before the robot sends anything: " + await connText(p));
  ok((await p.title()) === "Care Dashboard", "title before any state");

  // a person with every record, an activity, a queue and a reminder
  await post(state({ current: person(), mode: "quiz", quiz: { k: 1, phase: "ask", n: 2, total: 5, score: 1, q: "?", opts: ["a", "b", "c"], fb: null }, queue: ["Joe", "Rita"], seenTotal: 1,
    history: [person({ name: "Old Man", start: "09:00", end: "09:30" })], reminders: [{ id: 1, name: "Maria", due: 1, label: "10:30 a m", status: "due" }, { id: 2, name: "Joe", due: 2, label: "2:00 p m", status: "pending" }], heard: "i like music" }));
  ok(await wait(p, () => document.getElementById("who").textContent === "Maria"), "the person is shown");
  ok((await connText(p)) === "Pepper connected", "connected: " + await connText(p));
  ok((await txt(p, "#since")) === "Since 10:00", "since");
  ok((await txt(p, "#doing-title")) === "Quiz" && (await txt(p, "#doing-detail")) === "Question 2 of 5, score so far 1", "quiz line: " + await txt(p, "#doing-detail"));
  const tg = await p.$$eval("#tags .tag", e => e.map(x => x.textContent));
  ok(tg.indexOf("Exercises: 2") >= 0 && tg.indexOf("Quiz: 1 (last 4/5)") >= 0 && tg.indexOf("Snakes and Ladders: 2 played, won 1") >= 0 && tg.indexOf("Medicine: taken") >= 0 && tg.indexOf("Memories: 3 (liked: The Gozo ferry)") >= 0 && tg.indexOf("Said: Pastizzi and tea: Ricotta") >= 0, "record tags: " + JSON.stringify(tg));
  ok(JSON.stringify(await p.$$eval("#queue li", e => e.map(x => x.textContent))) === '["Joe","Rita"]' && (await txt(p, "#queue-count")) === "(2)", "queue");
  ok(JSON.stringify(await p.$$eval("#reminders li", e => e.map(x => x.textContent))) === '["10:30 am Maria, now","2:00 pm Joe"]', "reminders: " + JSON.stringify(await p.$$eval("#reminders li", e => e.map(x => x.textContent))));
  ok((await p.$$eval("#reminders li.due", e => e.length)) === 1, "the due reminder is marked");
  ok((await txt(p, "#history")).indexOf("Old Man") >= 0 && (await txt(p, "#history")).indexOf("09:00 to 09:30") >= 0 && (await txt(p, "#seen-count")) === "(1)", "history");
  ok((await txt(p, "#heard")) === 'Pepper last heard: "i like music"', "last heard");
  ok((await txt(p, "#foot")).indexOf("Care Companion v4.1.1") === 0, "footer: " + await txt(p, "#foot"));
  ok(!(await vis(p, "#busy")), "no busy chip");

  // every activity has a plain line
  const lines = [
    [{ mode: "exercise", exercise: { n: 3, elapsed: 10, total: 40, phase: "run" } }, "Exercise", "Exercise 3 of 9: Arms up, 30 seconds left"],
    [{ mode: "breathing", breathing: { i: 2, n: 4, phase: "in" } }, "Breathing together", "Breath 2 of 4, in"],
    [{ mode: "music", item: "song2" }, "Music", "Mama Liked the Roses"],
    [{ mode: "show", item: "sax" }, "Performance", "the Saxophone"],
    [{ mode: "memories", mem: { phase: "show", n: 2, total: 10, title: "Colourful fishing boats", opts: ["Blue", "Yellow"], ans: 1 } }, "Relive Malta", "Memory 2 of 10: Colourful fishing boats. Chose: Yellow"],
    [{ mode: "snl", snl: { phase: "play", pos: [23, 4], winner: null } }, "Snakes and Ladders", "Resident on 23, Pepper on 4"],
    [{ mode: "snl", snl: { phase: "over", pos: [100, 4], winner: 0 } }, "Snakes and Ladders", "Finished: the resident won"],
    [{ mode: null, pick: { k: 1, which: "music" } }, "Choosing", "The resident is choosing a song"],
    [{ mode: null }, "Waiting", "Nothing is running. The resident can choose."],
    [{ mode: "quiz", quiz: { phase: "done", n: 5, total: 5, score: 4 } }, "Quiz", "Finished: 4 out of 5"] ];
  for (const [o, title, detail] of lines) {
    await post(state(Object.assign({ current: person() }, o)));
    const got = await wait(p, d => document.getElementById('doing-detail').textContent === d, 3000, detail);
    ok(got && (await txt(p, "#doing-title")) === title, "activity " + title + ": " + await txt(p, "#doing-title") + " / " + await txt(p, "#doing-detail"));
  }
  await post(state({ current: null, calling: "Ana" }));
  ok(await wait(p, () => document.getElementById("who").textContent === "Calling Ana"), "calling");
  await post(state({ lag: true, current: person() }));
  ok(await wait(p, () => !document.getElementById("busy").classList.contains("hidden")) && (await vis(p, "#busy")), "the busy chip shows when the robot is slow");

  // alerts: red cards with the reason, a count in the tab title, seen ones greyed
  const al = [{ id: 1, name: "Maria", time: "10:32", seen: false, reason: "would like a drink" }, { id: 2, name: "Joe", time: "10:40", seen: false, reason: "has fallen" }, { id: 3, name: "Old Man", time: "09:10", seen: true, reason: "" }];
  await post(state({ current: person(), alerts: al, alertsOpen: 2 }));
  ok(await wait(p, () => document.querySelectorAll("#alerts-open .alert").length === 2), "two open alerts");
  const cards = await p.$$eval("#alerts-open .alert", e => e.map(x => x.textContent));
  ok(cards[0] === "Joe" + "has fallen, 10:40" && cards[1] === "Mariawould like a drink, 10:32", "alert cards, newest first: " + JSON.stringify(cards));
  ok((await p.title()) === "(2) Care Dashboard" && (await txt(p, "#alert-count")) === "(2 open)", "tab title and count: " + await p.title());
  ok(!(await vis(p, "#alerts-none")) && (await txt(p, "#alerts-seen")) === "09:10 Old Man, needs help, seen", "seen list and empty text: " + await txt(p, "#alerts-seen"));
  await post(state({ current: person(), alerts: al.map(a => Object.assign({}, a, { seen: true })), alertsOpen: 0 }));
  ok(await wait(p, () => document.querySelectorAll("#alerts-open .alert").length === 0) && (await p.title()) === "Care Dashboard" && (await vis(p, "#alerts-none")), "all seen: cards gone, title reset");

  // hostile text is shown as text, never run
  const evil = "<img src=x onerror=window.__xss=1><b>x</b>";
  await post(state({ current: person({ name: evil, memLikes: [evil], memAnswers: [evil] }), queue: [evil], heard: evil, alerts: [{ id: 9, name: evil, time: "<i>", seen: false, reason: evil }], alertsOpen: 1, history: [person({ name: evil, end: evil })], reminders: [{ id: 1, name: evil, label: evil, status: "due" }] }));
  ok(await wait(p, () => document.getElementById("who").textContent.length > 0 && document.getElementById("who").textContent.charAt(0) === "<"), "the hostile name is shown as text");
  ok((await p.evaluate(() => window.__xss)) === undefined && (await p.$$eval("img, script[src], iframe", e => e.length)) === 0 && (await p.$$eval("#who b, #who i, #queue b, #queue i", e => e.length)) === 0 && (await p.$$eval("#alerts-open .alert i", e => e.length)) === 0, "markup in a name was run or inserted");

  // sound: off by default; the button needs a click; a NEW alert beeps, an old one does not
  ok((await p.evaluate(() => window.__osc)) === 0, "no sound before the button");
  await post(state({ current: person(), alerts: [], alertsOpen: 0 })); await sleep(1300);
  await p.click("#b-sound");
  ok((await p.getAttribute("#b-sound", "aria-pressed")) === "true" && (await txt(p, "#b-sound")) === "Alert sound: on" && (await p.evaluate(() => window.__osc)) === 3, "sound button: " + await p.evaluate(() => window.__osc));
  await post(state({ current: person(), alerts: [{ id: 21, name: "Maria", time: "11:00", seen: false, reason: "is in pain" }], alertsOpen: 1 }));
  ok(await wait(p, () => window.__osc >= 6, 3000), "a new alert did not beep");
  const oscNow = await p.evaluate(() => window.__osc);
  await post(state({ current: person(), alerts: [{ id: 21, name: "Maria", time: "11:00", seen: false, reason: "is in pain" }, { id: 22, name: "Maria", time: "11:01", seen: true, reason: "x" }], alertsOpen: 1 })); await sleep(1500);
  ok((await p.evaluate(() => window.__osc)) === oscNow, "the same open alert beeped again at once");
  await post(state({ current: person(), alerts: [{ id: 21, name: "Maria", time: "11:00", seen: false, reason: "is in pain" }, { id: 23, name: "Joe", time: "11:02", seen: false, reason: "has fallen" }], alertsOpen: 2 }));
  ok(await wait(p, n => window.__osc >= n + 3, 3000, oscNow), "a second new alert, soon after the first, did not beep");
  await p.click("#b-sound"); ok((await txt(p, "#b-sound")) === "Alert sound: off", "sound off again");

  // a robot that went quiet, then came back
  await sleep(2600);
  ok(await wait(p, () => document.getElementById("conn-text").textContent.indexOf("Pepper is not sending") === 0, 3000), "stale robot: " + await connText(p));
  ok((await p.$eval("#conn", e => e.className)) === "pill bad" && (await txt(p, "#who")).length > 0, "the last state stays visible and the pill is red");
  await post(state({ current: person() }));
  ok(await wait(p, () => document.getElementById("conn-text").textContent === "Pepper connected"), "the robot came back");

  ok(p.reqs.every(u => u.indexOf(base) === 0), "a request left the dashboard: " + p.reqs.filter(u => u.indexOf(base) !== 0).slice(0, 2));
  ok(p.errs.length === 0, "console errors: " + p.errs.slice(0, 2));
  // layout: two columns at desktop width, one column and no sideways scroll on a phone
  const cols = await p.evaluate(() => { const m = document.querySelector("main"); return getComputedStyle(m).gridTemplateColumns.split(" ").length; });
  ok(cols === 2, "desktop has two columns: " + cols);
  await p.close();
  p = await open(390, 800); await sleep(1300);
  const ph = await p.evaluate(() => ({ cols: getComputedStyle(document.querySelector("main")).gridTemplateColumns.split(" ").length, sw: document.documentElement.scrollWidth, w: window.innerWidth }));
  ok(ph.cols === 1 && ph.sw <= ph.w, "phone layout: " + JSON.stringify(ph));
  // the dashboard program stops: the page says so, and recovers when it is back
  srv.kill();
  ok(await wait(p, () => document.getElementById("conn-text").textContent === "The dashboard program is not reachable", 8000), "lost server: " + await connText(p));
  ok(p.errs.filter(e => !/ERR_CONNECTION|Failed to load resource/.test(e)).length === 0, "page errors after the server stopped: " + p.errs.slice(0, 2));
  await b.close();
  if (fails.length) { console.log("FAIL:\n - " + fails.join("\n - ")); console.log("DASHBOARD PAGE FAILED"); process.exit(1); }
  console.log(pass + " dashboard page checks passed"); console.log("DASHBOARD PAGE OK");
})().catch(e => { console.log("exception", e); process.exit(1); });
