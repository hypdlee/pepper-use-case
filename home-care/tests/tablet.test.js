// Tablet tests: ES5 parse, every view and every button in headless Chromium, layout at tablet / short / phone sizes.
const path = require("path"), fs = require("fs");
const { chromium } = require("playwright");
const acorn = require("acorn");
const DIR = "/home/claude/hack/pkg/html";
const SHOTS = process.env.SHOTS || "";
let pass = 0; const fails = [];
function ok(c, m) { if (c) { pass++; } else { fails.push(m); } }

// 1. every script is ES5
["bridge.js", "figure.js", "motion-data.js", "memories.js", "panel.js"].forEach(f => {
  try { acorn.parse(fs.readFileSync(path.join(DIR, "js", f), "utf8"), { ecmaVersion: 5 }); ok(true, ""); }
  catch (e) { ok(false, "ES5 parse " + f + ": " + e.message); }
});
["index.html", "exercises.html", "feeling.html", "examples.html"].forEach(f => {
  const t = fs.readFileSync(path.join(DIR, f), "utf8");
  const scripts = t.match(/<script>([\s\S]*?)<\/script>/g) || [];
  scripts.forEach(s => { try { acorn.parse(s.replace(/<\/?script>/g, ""), { ecmaVersion: 5 }); ok(true, ""); } catch (e) { ok(false, "ES5 inline in " + f + ": " + e.message); } });
});

const state = (o) => Object.assign({ v: "4.1.1", seq: 10, current: { name: "Maria", start: "10:00", exercises: 2, music: 1, performances: 0, breathing: 0, med: "taken", moodLow: false, alert: false, mood: "" },
  calling: null, history: [], seenTotal: 0, queue: [], alerts: [], alertsOpen: 0, mode: null, item: "", mem: null, lastCmd: "", exercise: null, breathing: null, reminders: [] }, o || {});
let seq = 100;

(async () => {
  const b = await chromium.launch();
  async function open(w, h) {
    const ctx = await b.newContext({ viewport: { width: w, height: h } });
    const p = await ctx.newPage();
    const errs = []; p.on("pageerror", e => errs.push(String(e))); p.on("console", m => { if (m.type() === "error" && !/qimessaging|ERR_FILE|Failed to load resource/.test(m.text())) errs.push(m.text()); });
    await p.addInitScript(() => { window.__sent = []; window.ALTabletBinding = { raiseEvent: s => { window.__sent.push(JSON.parse(s)); } }; });
    await p.goto("file://" + path.join(DIR, "index.html"));
    await p.waitForTimeout(300);
    p.errs = errs;
    return p;
  }
  const upd = (p, o) => p.evaluate(s => window.PepperUI.update(s), Object.assign(state(o), { seq: ++seq }));
  const sent = p => p.evaluate(() => window.__sent.slice());
  const clearSent = p => p.evaluate(() => { window.__sent.length = 0; });
  const vis = (p, sel) => p.evaluate(s => { const e = document.querySelector(s); if (!e) return false; const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== "hidden" && !e.closest(".hidden"); }, sel);
  const txt = (p, sel) => p.evaluate(s => document.querySelector(s).textContent, sel);

  // ---------------- 1280x800 tablet ----------------
  let p = await open(1280, 800);
  ok((await txt(p, ".brand-name")) === "Pepper Care Companion", "brand name");
  ok((await txt(p, ".brand-sub")).indexOf("IEEE Malta Digital Health Hackathon 2026") === 0, "event named in plain text");
  ok(!(await p.$("img.logo")) && !(await p.$("header img")), "no logo image in the header");
  ok(await vis(p, "#start-row") && !(await vis(p, "#tiles")), "start screen: name box, no tiles");
  await p.fill("#name-input", "Maria"); await p.click("#b-start");
  ok((await sent(p)).some(m => m.cmd === "name" && m.name === "Maria"), "typed name is sent");
  await upd(p, {});
  ok(await vis(p, "#tiles"), "tiles shown after a session starts");
  const labels = await p.$$eval("#tiles .tile", els => els.map(e => e.textContent.trim()));
  ok(JSON.stringify(labels) === JSON.stringify(["Exercise", "Breathe", "Music", "Activities", "Chat", "Relive Malta", "Medicine", "Reminder"]), "eight tiles in order: " + labels);
  ok((await p.$$eval("#tiles .tile", els => els.every(e => !e.disabled))), "tiles enabled");
  const rows = await p.$$eval("#tiles .tile", els => { const t = {}; els.forEach(e => { t[Math.round(e.getBoundingClientRect().top)] = 1; }); return Object.keys(t).length; });
  ok(rows === 2, "tiles form two rows, got " + rows);
  const fit = await p.evaluate(() => { const r = document.getElementById("b-stop").getBoundingClientRect(), t = document.getElementById("tiles").getBoundingClientRect(); return { stopBottom: r.bottom, h: innerHeight, tilesBottom: t.bottom, helpTop: document.getElementById("b-help").getBoundingClientRect().top, sw: document.documentElement.scrollWidth }; });
  ok(fit.stopBottom <= fit.h + 1 && fit.tilesBottom <= fit.helpTop, "tiles and Help/Stop fit on 1280x800: " + JSON.stringify(fit));
  ok(fit.sw <= 1280, "no horizontal scroll at 1280");
  if (SHOTS) await p.screenshot({ path: SHOTS + "/tablet-home.png" });

  // every plain tile sends its word
  const plain = { "b-exercise": "exercise", "b-breathe": "breathing", "b-chat": "chat", "b-med": "medication", "b-relive": "relive", "b-remind": "reminder", "b-help": "help", "b-stop": "stop" };
  for (const id of Object.keys(plain)) {
    await clearSent(p); await p.click("#" + id); const m = await sent(p);
    ok(m.length === 1 && m[0].cmd === "say" && m[0].text === plain[id], id + " sends " + plain[id] + ": " + JSON.stringify(m));
    await p.waitForTimeout(850);
  }
  // music: Pepper asks, the three songs are on screen
  await clearSent(p); await p.click("#b-music");
  ok((await sent(p)).some(m => m.text === "music"), "music tile asks Pepper");
  ok(await vis(p, "#picker") && await vis(p, "#pick-music") && !(await vis(p, "#pick-activities")) && !(await vis(p, "#tiles")), "music list open");
  ok((await txt(p, "#pick-title")) === "Choose music", "music list title");
  ok((await p.$$eval("#pick-music .pick", e => e.length)) === 4, "four music choices (three songs and the saxophone)");
  const mfit = await p.evaluate(() => ({ back: document.getElementById("b-pick-back").getBoundingClientRect().bottom, help: document.getElementById("b-help").getBoundingClientRect().top, svgs: document.querySelectorAll("#pick-music .pick svg").length }));
  ok(mfit.back <= mfit.help && mfit.svgs === 4, "music list fits above Help and every choice has an icon: " + JSON.stringify(mfit));
  if (SHOTS) await p.screenshot({ path: SHOTS + "/tablet-songs.png" });
  for (const [i, s] of ["song1", "song2", "song3", "sax"].entries()) {
    await clearSent(p); await p.click("#pick-music .pick:nth-child(" + (i + 1) + ")");
    const m = await sent(p); ok(m.length === 1 && m[0].text === s, "music choice " + (i + 1) + " sends " + s + ": " + JSON.stringify(m));
    ok(await vis(p, "#tiles"), "list closes after a choice");
    await p.waitForTimeout(850);
    await p.click("#b-music"); await p.waitForTimeout(850);
  }
  await p.click("#b-pick-back"); ok(await vis(p, "#tiles") && !(await vis(p, "#picker")), "Back closes the music list");
  // activities: Pepper asks, dance and the quiz are on screen
  await p.waitForTimeout(850);
  await clearSent(p); await p.click("#b-activities");
  ok((await sent(p)).some(m => m.text === "activities"), "activities tile asks Pepper");
  ok(await vis(p, "#pick-activities") && !(await vis(p, "#pick-music")) && (await txt(p, "#pick-title")) === "Choose an activity", "activity list open");
  const acts = await p.$$eval("#pick-activities .pick", e => e.map(x => x.getAttribute("data-say")));
  ok(JSON.stringify(acts) === JSON.stringify(["dance", "quiz", "snl"]), "dance, quiz and snakes and ladders: " + acts);
  ok(!(await p.evaluate(() => /football/i.test(document.body.innerHTML))), "football is gone from the page");
  const afit = await p.evaluate(() => ({ back: document.getElementById("b-pick-back").getBoundingClientRect().bottom, help: document.getElementById("b-help").getBoundingClientRect().top, svgs: document.querySelectorAll("#pick-activities .pick svg").length }));
  ok(afit.back <= afit.help && afit.svgs === 3, "activity list fits and has icons: " + JSON.stringify(afit));
  if (SHOTS) await p.screenshot({ path: SHOTS + "/tablet-activities.png" });
  for (const s of acts) {
    if (!(await vis(p, "#pick-activities"))) { await p.click("#b-activities"); await p.waitForTimeout(850); }
    await clearSent(p); await p.click("#pick-activities .pick[data-say='" + s + "']");
    const m = await sent(p); ok(m.length === 1 && m[0].text === s, "activity " + s + " sent: " + JSON.stringify(m));
    await p.waitForTimeout(850);
  }

  // now-playing hints
  await upd(p, { mode: "music", item: "song2" });
  ok((await txt(p, "#hint")) === "Now playing: Mama Liked the Roses. Say stop to end it.", "now playing song: " + await txt(p, "#hint"));
  ok(!(await p.evaluate(() => /guitar/i.test(document.body.innerHTML))), "the guitar is gone from the page");
  await upd(p, { mode: "show", item: "sax" });
  ok((await txt(p, "#hint")).indexOf("Now playing: the saxophone") === 0, "now playing saxophone: " + await txt(p, "#hint"));
  await upd(p, { mode: null, item: "" });
  ok((await txt(p, "#hint")).indexOf("Choose something") === 0, "idle hint: " + await txt(p, "#hint"));

  // ---- quiz: question + three answers, feedback, result, and a calm screen (no tiles while it runs)
  const quizQ = (n, fb) => ({ k: 1, phase: "ask", n: n, total: 5, score: 0, q: "What is the capital city of Malta?", opts: ["Mdina", "Valletta", "Sliema"], fb: fb || null });
  await clearSent(p);
  await upd(p, { mode: "quiz", quiz: quizQ(1) });
  const shown1 = (await sent(p)).filter(m => m.cmd === "quizShown");
  ok(shown1.length === 1 && shown1[0].k === 1 && shown1[0].q === 1, "the page tells Pepper that question 1 is on screen: " + JSON.stringify(shown1));
  await upd(p, { mode: "quiz", quiz: quizQ(1), lastCmd: "x" }); await upd(p, { mode: "quiz", quiz: quizQ(1), lastCmd: "y" });
  ok((await sent(p)).filter(m => m.cmd === "quizShown").length === 1, "the same question was reported twice");
  ok(await vis(p, "#quizview") && await vis(p, "#qz-ask") && !(await vis(p, "#qz-done")), "quiz question shown");
  ok(!(await vis(p, "#tiles")) && !(await vis(p, "#picker")) && !(await vis(p, "#start-row")), "no tiles, no choice list, no name box during the quiz");
  ok((await txt(p, "#qz-step")) === "Question 1 of 5" && (await txt(p, "#qz-q")) === "What is the capital city of Malta?", "step and question: " + await txt(p, "#qz-step"));
  const qopts = await p.$$eval("#qz-opts .qz-opt", e => e.map(x => [x.getAttribute("data-n"), x.querySelector(".qz-num").textContent, x.querySelector(".qz-txt").textContent, x.disabled]));
  ok(JSON.stringify(qopts) === JSON.stringify([["1", "1", "Mdina", false], ["2", "2", "Valletta", false], ["3", "3", "Sliema", false]]), "three numbered answers: " + JSON.stringify(qopts));
  ok(!(await vis(p, "#qz-fb")), "no feedback before the first answer");
  const qfit = await p.evaluate(() => ({ tip: document.querySelector(".qz-tip").getBoundingClientRect().bottom, help: document.getElementById("b-help").getBoundingClientRect().top, sw: document.documentElement.scrollWidth, h: document.getElementById("qz-opts").getBoundingClientRect().height }));
  ok(qfit.tip <= qfit.help && qfit.sw <= 1280, "quiz fits above Help and Stop: " + JSON.stringify(qfit));
  if (SHOTS) await p.screenshot({ path: SHOTS + "/tablet-quiz.png" });
  await clearSent(p); await p.click("#qz-opts .qz-opt:nth-child(2)");
  const qa = await sent(p); ok(qa.length === 1 && qa[0].cmd === "quizAnswer" && qa[0].n === 2 && qa[0].k === 1 && qa[0].q === 1, "answer sends quizAnswer 2 with the quiz and question it was made on: " + JSON.stringify(qa));
  ok((await p.$$eval("#qz-opts .qz-opt", e => e.every(x => x.disabled))), "answers wait for the next question after a tap");
  await p.evaluate(() => document.querySelector("#qz-opts .qz-opt").click());
  ok((await sent(p)).length === 1, "a second tap on the same question sends nothing");
  await upd(p, { mode: "quiz", quiz: Object.assign(quizQ(2, { ok: true, answer: "Valletta" }), { q: "Which island is the sister island of Malta?", opts: ["Crete", "Sicily", "Gozo"], score: 1 }) });
  ok((await txt(p, "#qz-step")) === "Question 2 of 5" && (await p.$$eval("#qz-opts .qz-opt", e => e.every(x => !x.disabled))), "next question unlocks the answers");
  ok(await vis(p, "#qz-fb") && (await txt(p, "#qz-fb")) === "Correct!", "right answer feedback: " + await txt(p, "#qz-fb"));
  const shown2 = (await sent(p)).filter(m => m.cmd === "quizShown");
  ok(shown2.length === 1 && shown2[0].q === 2, "question 2 reported once it was on screen: " + JSON.stringify(shown2));
  await upd(p, { mode: "quiz", quiz: quizQ(3, { ok: false, answer: "Gozo" }) });
  ok((await txt(p, "#qz-fb")) === "Not quite. The answer was Gozo." && (await p.$eval("#qz-fb", e => e.className)).indexOf("soft") >= 0, "gentle wrong answer feedback: " + await txt(p, "#qz-fb"));
  ok((await p.$eval("#qz-bar", e => e.style.width)) === "40%", "progress bar at question 3: " + await p.$eval("#qz-bar", e => e.style.width));
  // a tap that Pepper ignored must not leave the buttons dead
  await p.click("#qz-opts .qz-opt:nth-child(1)");
  ok((await p.$$eval("#qz-opts .qz-opt", e => e.every(x => x.disabled))), "buttons wait after a tap");
  await p.waitForTimeout(2800);
  ok((await p.$$eval("#qz-opts .qz-opt", e => e.every(x => !x.disabled))), "buttons came back although the question did not change");
  // the question shows even when no name was entered (voice-started quiz), and a restarted controller (lower numbers) is not ignored
  await upd(p, { mode: "quiz", current: null, quiz: Object.assign(quizQ(4), { k: 2 }) });
  ok(await vis(p, "#quizview") && (await txt(p, "#qz-step")) === "Question 4 of 5", "quiz not shown without a current person");
  await p.evaluate(s => window.PepperUI.update(s), Object.assign(state({ run: "B", mode: "show", item: "sax", quiz: null }), { seq: 5 }));
  ok((await txt(p, "#hint")).indexOf("Now playing: the saxophone") === 0 && !(await vis(p, "#quizview")), "state from a restarted controller (lower seq, new run) was ignored: " + await txt(p, "#hint"));
  await upd(p, { mode: null, item: "", run: "B", quiz: { phase: "done", total: 5, score: 4, fb: { ok: true, answer: "x" } } });
  ok(await vis(p, "#qz-done") && !(await vis(p, "#qz-ask")), "result shown");
  ok((await txt(p, "#qz-score")) === "You got 4 out of 5." && (await txt(p, "#qz-msg")) === "Well done!", "score text: " + await txt(p, "#qz-score"));
  if (SHOTS) await p.screenshot({ path: SHOTS + "/tablet-quiz-result.png" });
  await upd(p, { mode: null, quiz: { phase: "done", total: 5, score: 5, fb: null } });
  ok((await txt(p, "#qz-msg")) === "A perfect score. Wonderful!", "perfect score message: " + await txt(p, "#qz-msg"));
  await upd(p, { mode: null, quiz: { phase: "done", total: 5, score: 1, fb: null } });
  ok((await txt(p, "#qz-msg")) === "Thank you for playing.", "low score is kind: " + await txt(p, "#qz-msg"));
  await clearSent(p); await p.click("#b-quiz-again");
  const again = await sent(p); ok(again.length === 1 && again[0].cmd === "say" && again[0].text === "quiz", "Another quiz asks Pepper for a quiz: " + JSON.stringify(again));
  await p.waitForTimeout(850);
  await clearSent(p); await p.click("#b-quiz-done");
  const dn = await sent(p); ok(dn.length === 1 && dn[0].cmd === "quizClose", "Done sends quizClose: " + JSON.stringify(dn));
  ok(await vis(p, "#tiles") && !(await vis(p, "#quizview")), "tiles are back after Done");
  await upd(p, { mode: "quiz", quiz: quizQ(1) });
  await clearSent(p); await p.click("#b-stop");
  ok((await sent(p)).some(m => m.text === "stop"), "Stop works during the quiz");
  await upd(p, { mode: null, quiz: null });
  ok(await vis(p, "#tiles") && !(await vis(p, "#quizview")), "quiz screen closes when the robot ends the quiz");
  await p.click("#b-staff");
  await upd(p, { current: Object.assign(state().current, { quizzes: 2, quizLast: "4/5" }) });
  ok((await txt(p, "#patient-meta")).indexOf("Quiz: 2 (last 4/5)") >= 0, "quiz result in the staff view: " + await txt(p, "#patient-meta"));
  await p.click("#b-staff-close");

  // ---- Relive Malta: a card, picture, two prompts; Pepper reads once the page reports the card is on screen ----
  const card = (n, o) => Object.assign({ k: 7, phase: "show", n: n, total: 10, id: "festa", title: "The village festa", line: "Bands, church bells and fireworks on a summer evening.", q: "At the festa, did you enjoy the band or the fireworks?", opts: ["The band", "The fireworks"], ans: -1, reply: "", liked: false }, o || {});
  await upd(p, { mode: "memories", mem: card(1) });
  ok(await vis(p, "#memview") && await vis(p, "#mem-show") && !(await vis(p, "#mem-end")), "memory card shown");
  ok(!(await vis(p, "#tiles")) && !(await vis(p, "#picker")) && !(await vis(p, "#start-row")) && !(await vis(p, "#quizview")), "calm screen during Relive Malta: no tiles");
  ok((await txt(p, "#mem-step")) === "Memory 1 of 10" && (await txt(p, "#mem-title")) === "The village festa" && (await txt(p, "#mem-q")) === "At the festa, did you enjoy the band or the fireworks?", "card text");
  ok(JSON.stringify(await p.$$eval(".mem-opt", els => els.map(e => e.textContent))) === JSON.stringify(["The band", "The fireworks"]) && !(await vis(p, "#mem-reply")), "two answers, no reply yet");
  ok(await vis(p, "#b-mem-a1") && await vis(p, "#b-mem-a2") && !(await p.$("#b-mem-a3")) && !(await p.evaluate(() => /something else/i.test(document.body.innerHTML))) && !(await p.$eval("#b-mem-a1", e => e.disabled)), "answer buttons are shown and live");
  ok(await p.$eval("#mem-art svg", e => e.getBoundingClientRect().width > 200), "the picture is drawn");
  ok((await p.$eval("#b-mem-back", e => e.disabled)) && !(await p.$eval("#b-mem-next", e => e.disabled)) && (await txt(p, "#b-mem-next")) === "Next", "back is off on the first card");
  const mfit2 = await p.evaluate(() => ({ actions: document.querySelector(".mem-actions").getBoundingClientRect().bottom, opts: document.getElementById("mem-opts").getBoundingClientRect().bottom, help: document.getElementById("b-help").getBoundingClientRect().top, sw: document.documentElement.scrollWidth }));
  ok(mfit2.actions <= mfit2.help && mfit2.sw <= 1280, "card and buttons fit above Help and Stop: " + JSON.stringify(mfit2));
  if (SHOTS) await p.screenshot({ path: SHOTS + "/tablet-relive.png" });
  await p.click("#b-staff"); ok((await txt(p, "#patient-meta")).indexOf("Relive Malta tip") < 0, "the old tip is gone"); await p.click("#b-staff-close");
  // ---- v3.7: one question, one answer, one reply ----
  await clearSent(p); await p.click("#b-mem-a2");
  const an = await sent(p); ok(an.length === 1 && an[0].cmd === "memAnswer" && an[0].k === 7 && an[0].n === 1 && an[0].a === 2, "answer carries k, n and a: " + JSON.stringify(an));
  ok((await p.$$eval(".mem-opt", els => els.every(e => e.disabled))) && (await p.$eval("#b-mem-a2", e => e.className)).indexOf("on") >= 0, "all answers lock and the chosen one is marked at once");
  await clearSent(p); await p.$eval("#b-mem-a1", e => e.click()); ok((await sent(p)).length === 0, "a second answer was sent");
  await upd(p, { mode: "memories", mem: card(1, { ans: 1, reply: "Fireworks light up the whole sky. What a night!" }) });
  ok((await txt(p, "#mem-reply")).indexOf("Fireworks light up") === 0 && await vis(p, "#mem-reply") && (await p.$eval("#b-mem-a2", e => e.className)).indexOf("on") >= 0, "Pepper's reply is shown with the chosen answer");
  ok((await p.$$eval(".mem-opt", els => els.every(e => e.disabled))) && !(await p.$eval("#b-mem-next", e => e.disabled)), "answers stay locked after the reply, Next stays live");
  const rfit = await p.evaluate(() => ({ actions: document.querySelector(".mem-actions").getBoundingClientRect().bottom, help: document.getElementById("b-help").getBoundingClientRect().top }));
  ok(rfit.actions <= rfit.help, "card, reply and buttons fit above Help and Stop: " + JSON.stringify(rfit));
  if (SHOTS) await p.screenshot({ path: SHOTS + "/tablet-relive-answer.png" });
  await p.click("#b-staff");
  await upd(p, { mode: "memories", mem: card(1, { ans: 1, reply: "x" }), current: Object.assign(state().current, { memCards: 3, memLikes: ["The Gozo ferry"], memAnswers: ["Pastizzi and tea: Ricotta", "The village festa: The fireworks"] }) });
  ok((await txt(p, "#patient-meta")).indexOf("Said: Pastizzi and tea: Ricotta; The village festa: The fireworks") >= 0, "answers in the staff view: " + await txt(p, "#patient-meta"));
  await p.click("#b-staff-close");
  // Pepper ignored a tap (no answer comes back): the answers come back after a moment
  await upd(p, { mode: "memories", mem: card(9, { id: "beach", title: "A summer day at the beach" }) });
  await clearSent(p); await p.click("#b-mem-a1"); await p.waitForTimeout(2800);
  ok(!(await p.$eval("#b-mem-a1", e => e.disabled)), "answers did not come back after an ignored tap");
  await upd(p, { mode: "memories", mem: card(1) });
  // the page tells Pepper the card is on screen, once
  await clearSent(p);
  await upd(p, { mode: "memories", mem: card(2, { id: "luzzu", title: "Colourful fishing boats" }) });
  await upd(p, { mode: "memories", mem: card(2, { id: "luzzu", title: "Colourful fishing boats" }), lastCmd: "x" });
  const ms = (await sent(p)).filter(m => m.cmd === "memShown");
  ok(ms.length === 1 && ms[0].k === 7 && ms[0].n === 2, "memShown sent once for card 2: " + JSON.stringify(ms));
  ok(!(await p.$eval("#b-mem-back", e => e.disabled)), "back is on from the second card");
  // taps carry their card; buttons wait; they come back
  await clearSent(p); await p.click("#b-mem-next");
  const mn = await sent(p); ok(mn.length === 1 && mn[0].cmd === "memNext" && mn[0].k === 7 && mn[0].n === 2, "next carries k and n: " + JSON.stringify(mn));
  ok((await p.$eval("#b-mem-next", e => e.disabled)) && (await p.$eval("#b-mem-back", e => e.disabled)), "buttons wait after a tap");
  await p.waitForTimeout(2800);
  ok(!(await p.$eval("#b-mem-next", e => e.disabled)), "buttons came back although the card did not change");
  await clearSent(p); await p.click("#b-mem-back");
  const mb = await sent(p); ok(mb.length === 1 && mb[0].cmd === "memBack" && mb[0].n === 2, "back carries n: " + JSON.stringify(mb));
  await upd(p, { mode: "memories", mem: card(3, { id: "ferry", title: "The Gozo ferry" }) });
  ok(!(await p.$eval("#b-mem-next", e => e.disabled)), "a new card unlocks the buttons");
  // I like this
  await clearSent(p); await p.click("#b-mem-like");
  const ml = await sent(p); ok(ml.length === 1 && ml[0].cmd === "memLike" && ml[0].n === 3, "like carries n: " + JSON.stringify(ml));
  ok((await txt(p, "#b-mem-like")) === "Liked" && (await p.$eval("#b-mem-like", e => e.disabled)), "like shows at once");
  await upd(p, { mode: "memories", mem: card(3, { id: "ferry", title: "The Gozo ferry", liked: true }) });
  ok((await txt(p, "#b-mem-like")) === "Liked", "like confirmed by the robot");
  await upd(p, { mode: "memories", mem: card(4, { id: "pastizzi", title: "Pastizzi and tea" }) });
  ok((await txt(p, "#b-mem-like")) === "I like this" && !(await p.$eval("#b-mem-like", e => e.disabled)), "like resets on the next card");
  await upd(p, { mode: "memories", mem: card(10, { id: "balconies", title: "The street with colourful balconies" }) });
  ok((await txt(p, "#b-mem-next")) === "Finish", "last card says Finish");
  // all ten pictures exist and show
  for (const key of ["festa", "luzzu", "ferry", "pastizzi", "harbour", "baker", "crib", "carnival", "beach", "balconies"]) {
    await upd(p, { mode: "memories", mem: card(5, { id: key, title: key }) });
    ok(await p.$eval("#mem-art svg", e => e.getBoundingClientRect().height > 100), "picture " + key);
  }
  // the end card
  await upd(p, { mode: "memories", mem: { k: 7, phase: "end", total: 10 } });
  ok(await vis(p, "#mem-end") && !(await vis(p, "#mem-show")), "end card shown");
  await clearSent(p); await p.click("#b-mem-again");
  const ma = await sent(p); ok(ma.length === 1 && ma[0].cmd === "say" && ma[0].text === "relive", "Look again asks Pepper: " + JSON.stringify(ma));
  await p.waitForTimeout(850);
  await clearSent(p); await p.click("#b-mem-done");
  const md = await sent(p); ok(md.length === 1 && md[0].cmd === "memClose", "Done sends memClose: " + JSON.stringify(md));
  ok(await vis(p, "#tiles") && !(await vis(p, "#memview")), "tiles are back after Done");
  // works without a name, and after a controller restart (new run, lower numbers)
  await upd(p, { mode: "memories", current: null, mem: card(1) });
  ok(await vis(p, "#memview"), "card shown without a current person");
  await p.evaluate(s => window.PepperUI.update(s), Object.assign(state({ run: "R2", mode: null, mem: null }), { seq: 4 }));
  ok(!(await vis(p, "#memview")), "a restarted controller (lower seq, new run) was ignored");
  await clearSent(p);
  await upd(p, { run: "R2", mode: "memories", mem: card(1) });
  ok((await sent(p)).filter(m => m.cmd === "memShown").length === 1, "the first card of the same numbers in a new run is reported again");
  await upd(p, { run: "R2", mode: null, mem: null });
  ok(await vis(p, "#tiles"), "tiles after the cards end");
  ok(!(await p.evaluate(() => /mood/i.test(document.getElementById("tiles").innerHTML))), "no mood tile");

  // ---- v3.7: photos (2 of 3 exist for festa; none for luzzu): a copy of the page with test photos ----
  const tmp = fs.mkdtempSync(path.join(require("os").tmpdir(), "relive-"));
  fs.cpSync(DIR, tmp, { recursive: true });
  fs.rmSync(path.join(tmp, "photos"), { recursive: true, force: true });       // the shipped photos stay out of this test
  fs.mkdirSync(path.join(tmp, "photos"));
  const JPG = Buffer.from("/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA=", "base64");
  fs.writeFileSync(path.join(tmp, "photos", "festa-1.jpg"), JPG); fs.writeFileSync(path.join(tmp, "photos", "festa-2.jpg"), JPG);
  fs.writeFileSync(path.join(tmp, "photos", "credits.js"), "window.MemCredits = " + JSON.stringify({ "festa-1.jpg": "Photo: Jane Doe, CC BY 4.0, Wikimedia Commons", "festa-2.jpg": "Photo: Joe Bloggs, CC0, Wikimedia Commons" }) + ";");
  const ctx2 = await b.newContext({ viewport: { width: 1280, height: 800 } }); const p2 = await ctx2.newPage(); const errs2 = [];
  p2.on("pageerror", e => errs2.push(String(e)));
  await p2.addInitScript(() => { window.__sent = []; window.ALTabletBinding = { raiseEvent: s => { window.__sent.push(JSON.parse(s)); } }; });
  await p2.goto("file://" + path.join(tmp, "index.html")); await p2.waitForTimeout(300);
  await upd(p2, { mode: "memories", mem: card(1) }); await p2.waitForTimeout(700);
  ok(await vis(p2, "#mem-photo") && (await p2.$eval("#mem-photo", e => e.style.backgroundImage)).indexOf("photos/festa-1.jpg") >= 0, "the first photo is shown");
  ok((await p2.$$eval(".mem-dot", e => e.length)) === 2 && (await p2.$$eval(".mem-dot.on", e => e.length)) === 1, "two dots for two photos");
  ok((await txt(p2, "#mem-credit")) === "Photo: Jane Doe, CC BY 4.0, Wikimedia Commons", "credit under the photo: " + await txt(p2, "#mem-credit"));
  await p2.click("#mem-art");
  ok((await p2.$eval("#mem-photo", e => e.style.backgroundImage)).indexOf("photos/festa-2.jpg") >= 0 && (await txt(p2, "#mem-credit")).indexOf("Joe Bloggs") >= 0, "a tap shows the next photo and its credit");
  await p2.click("#mem-art"); ok((await p2.$eval("#mem-photo", e => e.style.backgroundImage)).indexOf("festa-1.jpg") >= 0, "photos go round");
  if (SHOTS) await p2.screenshot({ path: SHOTS + "/tablet-relive-photo.png" });
  await upd(p2, { mode: "memories", mem: card(2, { id: "luzzu", title: "Colourful fishing boats" }) }); await p2.waitForTimeout(500);
  ok(!(await vis(p2, "#mem-photo")) && (await p2.$$eval(".mem-dot", e => e.length)) === 0 && (await txt(p2, "#mem-credit")) === "" && await p2.$eval("#mem-svg svg", e => e.getBoundingClientRect().width > 200), "no photos: the drawing stays, no dots, no credit");
  await upd(p2, { mode: "memories", mem: card(3) }); await p2.waitForTimeout(500);
  ok(await vis(p2, "#mem-photo"), "going back to a card with photos shows them again");
  await upd(p2, { mode: null, mem: null });
  ok(errs2.length === 0, "page errors with photos: " + errs2.join("; "));
  await ctx2.close(); fs.rmSync(tmp, { recursive: true, force: true });
  // the shipped project: festa has three photos (three dots, a credit), crib has one (no dots)
  await upd(p, { mode: "memories", mem: card(1) }); await p.waitForTimeout(1200);
  ok(await vis(p, "#mem-photo") && (await p.$$eval(".mem-dot", e => e.length)) === 3 && (await txt(p, "#mem-credit")).indexOf("Wikimedia Commons") >= 0, "the shipped festa photos are shown with a credit");
  await upd(p, { mode: "memories", mem: card(2, { id: "crib", title: "Christmas time" }) }); await p.waitForTimeout(1200);
  ok(await vis(p, "#mem-photo") && (await p.$$eval(".mem-dot", e => e.length)) === 0, "one photo: shown, no dots");
  await upd(p, { mode: null, mem: null });

  // carer alerts
  const al = [{ id: 1, name: "Maria", time: "10:32", seen: false }, { id: 2, name: "Joe", time: "10:40", seen: false }];
  await upd(p, { alerts: al, alertsOpen: 2 });
  ok(await vis(p, "#alert") && (await txt(p, "#alert-msg")).indexOf("Joe") >= 0, "banner names the patient: " + await txt(p, "#alert-msg"));
  ok(await vis(p, "#staff-badge") && (await txt(p, "#staff-badge")) === "2", "staff badge shows 2");
  await p.click("#b-staff");
  ok((await p.$$eval("#alerts li", e => e.length)) === 2 && (await txt(p, "#alert-count")).indexOf("2 open") >= 0, "two alerts listed");
  if (SHOTS) await p.screenshot({ path: SHOTS + "/tablet-staff.png" });
  await clearSent(p); await p.click("#alerts button[data-alert='2']");
  const ack = await sent(p); ok(ack.length === 1 && ack[0].cmd === "ack" && ack[0].alert === 2, "Seen sends ack for alert 2: " + JSON.stringify(ack));
  await upd(p, { alerts: [al[0], Object.assign({}, al[1], { seen: true })], alertsOpen: 1 });
  ok((await txt(p, "#staff-badge")) === "1" && (await p.$$eval("#alerts button", e => e.length)) === 1, "one alert left open");
  await upd(p, { alerts: [Object.assign({}, al[0], { seen: true }), Object.assign({}, al[1], { seen: true })], alertsOpen: 0 });
  ok(!(await vis(p, "#staff-badge")) && (await txt(p, "#alerts")).indexOf("seen") >= 0, "badge gone when all are seen");

  // clear records
  await p.evaluate(() => localStorage.setItem("pepper.feel", '{"maria":"happy"}'));
  await clearSent(p);
  await p.click("#b-clear"); ok(await vis(p, "#clear-confirm") && !(await vis(p, "#b-clear")), "confirmation asked");
  await p.click("#b-clear-no"); ok(!(await vis(p, "#clear-confirm")) && await vis(p, "#b-clear") && (await sent(p)).length === 0, "Cancel changes nothing");
  await p.click("#b-clear"); await p.click("#b-clear-yes");
  const cl = await sent(p); ok(cl.length === 1 && cl[0].cmd === "clearData", "clearData sent once: " + JSON.stringify(cl));
  ok((await p.evaluate(() => localStorage.getItem("pepper.feel"))) === null, "tablet-side feelings cleared");
  ok((await txt(p, "#staff-current")) === "Nobody", "staff view empties");
  await p.click("#b-staff-close");



  // ---- v3.9: Pepper asks what to play (by voice), the list opens by itself, and closes when the dialog moves on
  await upd(p, { mode: null, snl: null, mem: null, quiz: null });
  ok(await vis(p, "#tiles") && !(await vis(p, "#picker")), "tiles shown before Pepper asks");
  await upd(p, { pick: { k: 41, which: "activities" } });
  ok(await vis(p, "#picker") && await vis(p, "#pick-activities") && !(await vis(p, "#pick-music")) && !(await vis(p, "#tiles")) && (await txt(p, "#pick-title")) === "Choose an activity", "the activities list opened by itself when Pepper asked");
  ok((await txt(p, "#hint")).indexOf("Tap one") === 0, "the hint tells what to do: " + await txt(p, "#hint"));
  await upd(p, { pick: { k: 41, which: "activities" }, lastCmd: "q" });
  ok(await vis(p, "#picker"), "the same question twice keeps the list");
  await p.click("#b-pick-back");
  ok(await vis(p, "#tiles") && !(await vis(p, "#picker")), "Back closes the list");
  await upd(p, { pick: { k: 41, which: "activities" }, lastCmd: "r" });
  ok(!(await vis(p, "#picker")), "a list that was closed does not pop up again on the same question");
  await upd(p, { pick: { k: 42, which: "music" } });
  ok(await vis(p, "#pick-music") && !(await vis(p, "#pick-activities")) && (await txt(p, "#pick-title")) === "Choose music", "the next question opens the music list");
  await upd(p, { pick: null });
  ok(await vis(p, "#tiles") && !(await vis(p, "#picker")), "the list closes when the dialog moves on");
  // a list opened with a tap is not closed by an update that does not know about it yet
  await p.waitForTimeout(850);
  await p.click("#b-music");
  await upd(p, { pick: null, lastCmd: "t" });
  ok(await vis(p, "#picker") && await vis(p, "#pick-music"), "a tapped list stays open until Pepper's own question arrives");
  await upd(p, { pick: { k: 43, which: "music" } });
  ok(await vis(p, "#pick-music"), "the tapped list and Pepper's question agree");
  await upd(p, { pick: { k: 43, which: "music" }, mode: "quiz", quiz: quizQ(1) });
  ok(!(await vis(p, "#picker")) && await vis(p, "#quizview"), "a quiz replaces the list");
  await upd(p, { pick: null, mode: null, quiz: null });
  ok(await vis(p, "#tiles"), "tiles are back");
  // the controller restarts and numbers again from 1
  await upd(p, { run: "R1", pick: { k: 1, which: "activities" } });
  ok(await vis(p, "#pick-activities"), "list after a restart (first run)");
  await p.click("#b-pick-back");
  await p.evaluate(s => window.PepperUI.update(s), Object.assign(state({ run: "R2", pick: { k: 1, which: "music" } }), { seq: 2 }));
  ok(await vis(p, "#pick-music"), "list with the same number after a controller restart: " + await txt(p, "#pick-title"));
  await upd(p, { run: "R2", pick: null });
  // ---- Snakes and Ladders: the board, the dice, the walk, the locks, the end
  const SM = (who, die, frm, land, to, kind) => { const sp = kind === "ladder" || kind === "snake"; const steps = kind === "bounce" ? 0 : land - frm; return { who: who, die: die, frm: frm, land: land, to: to, kind: kind || "", roll: 900, step: 140, hold: sp ? 1100 : 0, gap: 450, ms: 900 + 140 * steps + (sp ? 1100 : 0) + 450 }; };
  const snlWait = (moves) => moves.reduce((a, m) => a + 900 + 140 * (m.kind === "bounce" ? 0 : m.land - m.frm) + m.hold + m.gap, 0) + 400;
  const SG = (o) => Object.assign({ k: 1, n: 1, phase: "play", pos: [0, 0], moves: [], say: "Let's play Snakes and Ladders! You go first. Say roll, or touch the dice.", winner: null, rolls: 0, ladders: 0, snakes: 0 }, o || {});
  const xy = (n) => { if (n < 1) return [50, 1045]; const row = Math.floor((n - 1) / 10), off = (n - 1) % 10; return [((row % 2 === 0 ? off : 9 - off) + 0.5) * 100, (9 - row + 0.5) * 100]; };
  const tokAt = (who, n) => { if (n < 1) return [60 + who * 90, 1040]; const q = xy(n); return [q[0] + (who ? 18 : -18), q[1] + (who ? -8 : 8)]; };
  const tokPos = (pg, who) => pg.$eval("#snl-tok" + who, e => (e.getAttribute("transform").match(/-?[\d.]+/g) || []).map(Number));
  const near = (a, b) => Math.abs(a[0] - b[0]) < 1 && Math.abs(a[1] - b[1]) < 1;
  await clearSent(p);
  await upd(p, { mode: "snl", snl: SG() });
  ok(await vis(p, "#snlview") && !(await vis(p, "#tiles")) && !(await vis(p, "#picker")) && !(await vis(p, "#quizview")) && !(await vis(p, "#exview")), "the game replaces the tiles");
  ok((await p.$$eval("#snl-board svg rect", e => e.length)) === 100, "the board has 100 squares");
  ok((await p.$$eval("#snl-board svg text", e => e.slice(0, 100).map(x => x.textContent).join(",") === Array.from({ length: 100 }, (_, i) => i + 1).join(","))), "squares numbered 1 to 100");
  ok((await p.$$eval("#snl-board svg path", e => e.length)) === 8, "eight snakes are drawn");
  ok((await p.$$eval("#snl-board svg g[stroke]", e => e.length)) === 8, "eight ladders are drawn");
  ok(near(await tokPos(p, 0), tokAt(0, 0)) && near(await tokPos(p, 1), tokAt(1, 0)), "both pieces wait at the start");
  const sh = (await sent(p)).filter(m => m.cmd === "snlShown");
  ok(sh.length === 1 && sh[0].k === 1 && sh[0].n === 1, "the page tells Pepper that round 1 is on screen: " + JSON.stringify(sh));
  await upd(p, { mode: "snl", snl: SG(), lastCmd: "z" });
  ok((await sent(p)).filter(m => m.cmd === "snlShown").length === 1, "the same round was reported twice");
  ok((await txt(p, "#snl-say")).indexOf("Let's play Snakes and Ladders") >= 0, "Pepper's opening words are shown: " + await txt(p, "#snl-say"));
  ok(!(await p.$eval("#b-snl-roll", e => e.disabled)) && (await p.$eval("#b-snl-skip", e => e.disabled)), "roll is ready, skip waits for the first round");
  ok((await txt(p, "#snl-pos0")) === "0" && (await txt(p, "#snl-pos1")) === "0" && (await txt(p, "#snl-banner")) === "Your turn.", "start chips and banner");
  const gfit = await p.evaluate(() => { const r = (id) => document.getElementById(id).getBoundingClientRect(); return { board: r("snl-board").bottom, boardR: r("snl-board").right, roll: r("b-snl-roll").bottom, help: r("b-help").top, stop: r("b-stop").bottom, h: innerHeight, sw: document.documentElement.scrollWidth, w: innerWidth, bw: r("snl-board").width, bh: r("snl-board").height }; });
  ok(gfit.board <= gfit.help + 1 && gfit.roll <= gfit.help + 1 && gfit.stop <= gfit.h + 1 && gfit.sw <= gfit.w, "the game fits above Help and Stop at 1280x800: " + JSON.stringify(gfit));
  ok(gfit.bw >= 380 && gfit.bh >= 380, "the board is big enough to read from a distance: " + JSON.stringify(gfit));
  ok((await vis(p, "#b-snl-skip")) && (await p.evaluate(() => document.getElementById("b-snl-skip").getBoundingClientRect().bottom <= document.getElementById("b-help").getBoundingClientRect().top + 1)), "Skip my turn is not hidden behind Help (note showing)");
  await p.click("#alert-close");
  const gfit2 = await p.evaluate(() => { const r = (id) => document.getElementById(id).getBoundingClientRect(); return { board: r("snl-board").bottom, bw: r("snl-board").width, help: r("b-help").top, skip: r("b-snl-skip").bottom }; });
  ok(gfit2.board <= gfit2.help + 1 && gfit2.skip <= gfit2.help + 1 && gfit2.bw > gfit.bw, "without the note the board grows and still fits: " + JSON.stringify(gfit2) + " vs " + gfit.bw);
  if (SHOTS) await p.screenshot({ path: SHOTS + "/tablet-snl-start.png" });
  // a tap: one command with the game and the round, and the second tap is ignored
  await clearSent(p); await p.click("#b-snl-roll");
  let rt = await sent(p); ok(rt.length === 1 && rt[0].cmd === "snlRoll" && rt[0].k === 1 && rt[0].n === 1, "roll sends snlRoll with game and round: " + JSON.stringify(rt));
  await p.evaluate(() => document.getElementById("b-snl-roll").click());
  await p.waitForTimeout(900);
  ok((await sent(p)).length === 1, "a second tap on the same round sent nothing");
  ok((await p.$eval("#b-snl-roll", e => e.disabled)), "the dice wait for the round after a tap");
  // round 1: you 3, Pepper 4. The walk takes a few seconds; afterwards the pieces stand on 3 and 4
  const r1 = [SM(0, 3, 0, 3, 3), SM(1, 4, 0, 4, 4)];
  await clearSent(p);
  await upd(p, { mode: "snl", snl: SG({ n: 2, pos: [3, 4], moves: r1, rolls: 2, say: "You got a three. You are on 3. Now me. I got a four. I am on 4. Your go!" }) });
  ok((await sent(p)).filter(m => m.cmd === "snlShown").length === 1 && (await sent(p)).filter(m => m.cmd === "snlShown")[0].n === 2, "round 2 reported at once");
  ok((await p.$eval("#b-snl-roll", e => e.disabled)) && (await txt(p, "#snl-rolltxt")) === "Playing...", "no rolling while the pieces move");
  await clearSent(p); await p.evaluate(() => document.getElementById("b-snl-roll").click());
  ok((await sent(p)).length === 0, "a tap while the pieces move sent nothing");
  ok((await txt(p, "#snl-say")) === "", "Pepper's words wait until the first dice have settled");
  await p.waitForTimeout(1100);
  ok((await txt(p, "#snl-say")).indexOf("You got a three") >= 0, "Pepper's words appear when the dice have settled: " + await txt(p, "#snl-say"));
  ok(!near(await tokPos(p, 1), tokAt(1, 4)), "Pepper's piece has not jumped ahead");
  await p.waitForTimeout(snlWait(r1));
  ok(near(await tokPos(p, 0), tokAt(0, 3)) && near(await tokPos(p, 1), tokAt(1, 4)), "the pieces stand on 3 and 4: " + JSON.stringify([await tokPos(p, 0), await tokPos(p, 1)]));
  ok((await txt(p, "#snl-pos0")) === "3" && (await txt(p, "#snl-pos1")) === "4", "chips show 3 and 4");
  ok(!(await p.$eval("#b-snl-roll", e => e.disabled)) && !(await p.$eval("#b-snl-skip", e => e.disabled)) && (await txt(p, "#snl-banner")) === "Your turn.", "the dice are ready again, skip is possible now");
  ok((await p.$eval("#snl-die", e => e.querySelectorAll("circle").length)) === 4, "the die shows Pepper's four");
  if (SHOTS) await p.screenshot({ path: SHOTS + "/tablet-snl-round1.png" });
  // skip sends its own command
  await clearSent(p); await p.click("#b-snl-skip");
  rt = await sent(p); ok(rt.length === 1 && rt[0].cmd === "snlSkip" && rt[0].k === 1 && rt[0].n === 2, "skip sends snlSkip: " + JSON.stringify(rt));
  // a ladder (2 to 23) and a snake (29 to 9)
  const r2 = [SM(0, 2, 0, 2, 23, "ladder"), SM(1, 1, 4, 5, 5)];
  await upd(p, { mode: "snl", snl: SG({ n: 3, pos: [23, 5], moves: r2, rolls: 4, ladders: 1, say: "A ladder!" }) });
  await p.waitForTimeout(900 + 280 + 700);         // the dice, the walk to square 2, and the slide is under way
  const mid = await tokPos(p, 0);
  ok(mid[1] < tokAt(0, 2)[1] - 20 && mid[1] > tokAt(0, 23)[1] + 20, "the piece is climbing the ladder (not jumping): " + JSON.stringify(mid));
  ok((await txt(p, "#snl-banner")).indexOf("ladder") >= 0, "ladder banner: " + await txt(p, "#snl-banner"));
  await p.waitForTimeout(snlWait(r2));
  ok(near(await tokPos(p, 0), tokAt(0, 23)) && (await txt(p, "#snl-pos0")) === "23", "the ladder ends on 23");
  const r3 = [SM(0, 6, 23, 29, 9, "snake"), SM(1, 2, 5, 7, 7)];
  await upd(p, { mode: "snl", snl: SG({ n: 4, pos: [9, 7], moves: r3, rolls: 6, ladders: 1, snakes: 1, say: "A snake!" }) });
  await p.waitForTimeout(snlWait(r3));
  ok(near(await tokPos(p, 0), tokAt(0, 9)) && (await txt(p, "#snl-pos0")) === "9", "the snake ends on 9");
  // too many for the end: the piece stays
  const r4 = [SM(0, 5, 98, 98, 98, "bounce"), SM(1, 1, 7, 8, 34, "ladder")];
  await upd(p, { mode: "snl", snl: SG({ n: 5, pos: [98, 34], moves: r4, rolls: 8, say: "Too many." }) });
  await p.waitForTimeout(snlWait(r4));
  ok(near(await tokPos(p, 0), tokAt(0, 98)) && near(await tokPos(p, 1), tokAt(1, 34)), "the bounce keeps the piece on 98, the ladder carries Pepper to 34");
  // the win
  const r5 = [SM(0, 2, 98, 100, 100)];
  await upd(p, { mode: "snl", snl: SG({ n: 6, phase: "over", winner: 0, pos: [100, 34], moves: r5, rolls: 9, say: "You got a two and reached 100! You win! Well played! Would you like another game?" }) });
  ok(!(await vis(p, "#b-snl-new")), "Play again waits until the walk is over");
  await p.waitForTimeout(snlWait(r5));
  ok((await txt(p, "#snl-banner")) === "You win! Well played!" && near(await tokPos(p, 0), tokAt(0, 100)), "the win is shown");
  ok(!(await vis(p, "#b-snl-roll")) && !(await vis(p, "#b-snl-skip")) && await vis(p, "#b-snl-new") && await vis(p, "#b-snl-done"), "the closing screen offers Play again and Done only");
  ok((await txt(p, "#snl-tip")).indexOf("Touch Play again") === 0 && (await txt(p, "#snl-tip")).indexOf("roll") < 0, "the closing screen tip fits the closing screen: " + await txt(p, "#snl-tip"));
  if (SHOTS) await p.screenshot({ path: SHOTS + "/tablet-snl-win.png" });
  await clearSent(p); await p.click("#b-snl-new");
  rt = await sent(p); ok(rt.length === 1 && rt[0].cmd === "snlNew" && rt[0].k === 1, "Play again sends snlNew: " + JSON.stringify(rt));
  // Pepper wins
  await upd(p, { mode: "snl", snl: SG({ n: 3, phase: "over", winner: 1, pos: [20, 100], moves: [SM(0, 1, 19, 20, 20), SM(1, 4, 96, 100, 100)], rolls: 9 }) });
  await p.waitForTimeout(snlWait([SM(0, 1, 19, 20, 20), SM(1, 4, 96, 100, 100)]));
  ok((await txt(p, "#snl-banner")) === "Pepper wins! Well played!", "Pepper's win: " + await txt(p, "#snl-banner"));
  // a new game starts from the start with no walk
  await upd(p, { mode: "snl", snl: SG({ k: 2 }) });
  ok(near(await tokPos(p, 0), tokAt(0, 0)) && (await txt(p, "#snl-pos0")) === "0" && !(await p.$eval("#b-snl-roll", e => e.disabled)) && !(await vis(p, "#b-snl-new")), "a new game starts clean");
  const sh2 = (await sent(p)).filter(m => m.cmd === "snlShown" && m.k === 2);
  ok(sh2.length === 1, "the new game is reported once: " + JSON.stringify(sh2));
  // a page that opens in the middle of a game shows the position at once
  const rp = await open(1280, 800);
  await upd(rp, {});
  await upd(rp, { mode: "snl", snl: SG({ k: 7, n: 9, pos: [26, 62], moves: [SM(0, 4, 43, 47, 26, "snake")], rolls: 20 }) });
  ok(near(await tokPos(rp, 0), tokAt(0, 26)) && near(await tokPos(rp, 1), tokAt(1, 62)) && (await txt(rp, "#snl-pos1")) === "62" && !(await rp.$eval("#b-snl-roll", e => e.disabled)), "a reloaded page shows the position without walking: " + JSON.stringify([await tokPos(rp, 0), tokAt(0, 26), await tokPos(rp, 1), tokAt(1, 62), await txt(rp, "#snl-pos1"), await rp.$eval("#b-snl-roll", e => e.disabled)]));
  ok(rp.errs.length === 0, "game page errors: " + rp.errs.join("|"));
  await rp.context().close();
  // Done closes the game and the tiles are back; the controller ending the game does the same
  await upd(p, { mode: "snl", snl: SG({ k: 3, phase: "over", winner: 0, pos: [100, 5], moves: [] }) });
  await clearSent(p); await p.click("#b-snl-done");
  rt = await sent(p); ok(rt.length === 1 && rt[0].cmd === "snlClose", "Done sends snlClose: " + JSON.stringify(rt));
  ok(await vis(p, "#tiles") && !(await vis(p, "#snlview")), "the tiles are back after Done");
  await upd(p, { mode: "snl", snl: SG({ k: 4 }) });
  await clearSent(p); await p.click("#b-stop");
  ok((await sent(p)).some(m => m.text === "stop"), "Stop works during the game");
  await upd(p, { mode: null, snl: null });
  ok(await vis(p, "#tiles") && !(await vis(p, "#snlview")), "the game screen closes when the robot ends the game");
  await p.click("#b-staff");
  await upd(p, { current: Object.assign(state().current, { snlGames: 3, snlWins: 1 }) });
  ok((await txt(p, "#patient-meta")).indexOf("Snakes and Ladders: 3 played, won 1") >= 0, "the game result in the staff view: " + await txt(p, "#patient-meta"));
  await p.click("#b-staff-close");

  // exercise and breathing views still work
  await upd(p, { current: state().current, mode: "exercise", exercise: { n: 3, elapsed: 5, total: 40, phase: "moving" } });
  await p.waitForTimeout(500);
  ok(await vis(p, "#exview") && (await txt(p, "#ex-title")).length > 2, "exercise view");
  await upd(p, { mode: null, exercise: null });
  await upd(p, { mode: "breathing", breathing: { i: 1, n: 5, phase: "in" } });
  await p.waitForTimeout(300);
  ok(await vis(p, "#breathview"), "breathing view");
  await upd(p, { mode: null, breathing: null });
  ok(p.errs.length === 0, "page errors: " + p.errs.join(" | "));
  await p.context().close();

  // ---------------- short laptop window and phone ----------------
  for (const [w, h] of [[1024, 600], [390, 844]]) {
    p = await open(w, h);
    await upd(p, {});
    const m = await p.evaluate(() => ({ sw: document.documentElement.scrollWidth, w: innerWidth, stop: document.getElementById("b-stop").getBoundingClientRect().bottom, h: innerHeight,
      tiles: document.getElementById("tiles").getBoundingClientRect().bottom, help: document.getElementById("b-help").getBoundingClientRect().top }));
    ok(m.sw <= m.w + 1, w + "x" + h + " no horizontal scroll " + JSON.stringify(m));
    if (w > 600) ok(m.stop <= m.h + 1 && m.tiles <= m.help + 1, w + "x" + h + " tiles and footer fit " + JSON.stringify(m));
    if (SHOTS) await p.screenshot({ path: SHOTS + "/tablet-" + w + ".png" });
    await upd(p, { mode: "quiz", quiz: { phase: "ask", n: 4, total: 5, score: 2, q: "Which family of instruments does the saxophone belong to?", opts: ["Woodwind", "Brass", "Strings"], fb: { ok: false, answer: "Gozo is the sister island" } } });
    const qm = await p.evaluate(() => ({ sw: document.documentElement.scrollWidth, w: innerWidth, last: document.querySelector("#qz-opts .qz-opt:nth-child(3)").getBoundingClientRect().bottom, help: document.getElementById("b-help").getBoundingClientRect().top, stopB: document.getElementById("b-stop").getBoundingClientRect().bottom, h: innerHeight }));
    ok(qm.sw <= qm.w + 1 && qm.last <= qm.help + 1 && qm.stopB <= qm.h + 1, w + "x" + h + " quiz fits: " + JSON.stringify(qm));
    if (SHOTS) await p.screenshot({ path: SHOTS + "/tablet-quiz-" + w + ".png" });
    await upd(p, { mode: "snl", snl: { k: 1, n: 1, phase: "play", pos: [47, 62], moves: [], say: "Let's play Snakes and Ladders! You go first. Say roll, or touch the dice.", winner: null, rolls: 4, ladders: 0, snakes: 0 } });
    const gm = await p.evaluate(() => { const r = (id) => document.getElementById(id).getBoundingClientRect(); return { sw: document.documentElement.scrollWidth, w: innerWidth, h: innerHeight, roll: r("b-snl-roll").bottom, rollT: r("b-snl-roll").top, help: r("b-help").top, stopB: r("b-stop").bottom, boardR: r("snl-board").right, bw: r("snl-board").width, sc: document.scrollingElement.scrollHeight }; });
    ok(gm.sw <= gm.w + 1 && gm.boardR <= gm.w + 1 && gm.bw >= 250, w + "x" + h + " game board fits across: " + JSON.stringify(gm));
    await p.evaluate(() => document.getElementById("b-snl-roll").scrollIntoView(false));
    const gm2 = await p.evaluate(() => ({ t: document.getElementById("b-snl-roll").getBoundingClientRect().top, b: document.getElementById("b-snl-roll").getBoundingClientRect().bottom, help: document.getElementById("b-help").getBoundingClientRect().top, h: innerHeight }));
    ok(gm2.t >= 0 && gm2.b <= gm2.help + 1, w + "x" + h + " the dice button can be reached (on screen or by scrolling the game): " + JSON.stringify(gm2));
    await p.evaluate(() => { document.getElementById("snlview").scrollTop = 0; });
    if (w > 600) ok(gm.roll <= gm.help + 1 && gm.stopB <= gm.h + 1, w + "x" + h + " game controls fit above Help and Stop: " + JSON.stringify(gm));
    if (SHOTS) await p.screenshot({ path: SHOTS + "/tablet-snl-" + w + ".png" });
    ok(p.errs.length === 0, w + " errors " + p.errs.join("|"));
    await p.context().close();
  }
  // ---- v4.0: the carer sees WHY help was asked, what Pepper last heard, and when the robot is busy
  {
    const q4 = await open(1280, 800);
    await upd(q4, { alerts: [{ id: 1, name: "Joe", time: "10:40", seen: false, reason: "needs the toilet" }, { id: 2, name: "Eva", time: "10:41", seen: false, reason: "" }, { id: 3, name: "Ann", time: "10:42", seen: true, reason: "is in pain" }], alertsOpen: 2 });
    const al = await q4.evaluate(() => Array.prototype.map.call(document.querySelectorAll("#alerts li"), li => li.textContent));
    ok(al.some(x => x.indexOf("10:40 Joe, needs the toilet") === 0), "the alert list shows the reason: " + JSON.stringify(al));
    ok(al.some(x => x.indexOf("10:41 Eva, needs help") === 0), "an alert without a reason still says needs help: " + JSON.stringify(al));
    ok(al.some(x => x.indexOf("10:42 Ann, seen") === 0), "a seen alert says seen: " + JSON.stringify(al));
    ok((await txt(q4, "#alert-msg")) === "Help asked: Eva at 10:41.", "the banner names the newest alert that is still open, not a seen one: " + await txt(q4, "#alert-msg"));
    await upd(q4, { alerts: [{ id: 1, name: "Joe", time: "10:40", seen: false, reason: "needs the toilet" }, { id: 2, name: "Eva", time: "10:41", seen: false, reason: "" }, { id: 3, name: "Ann", time: "10:42", seen: true, reason: "is in pain" }, { id: 4, name: "Rita", time: "11:00", seen: false, reason: "has fallen" }], alertsOpen: 3, lastCmd: "needfall" });
    ok((await txt(q4, "#alert-msg")) === "Help asked: Rita (has fallen) at 11:00.", "the banner names the reason: " + await txt(q4, "#alert-msg"));
    await q4.evaluate(() => window.PepperUI.alert({ id: 5, name: "Tom", time: "11:05", reason: "feels hot" }));
    ok((await txt(q4, "#alert-msg")) === "Help asked: Tom (feels hot) at 11:05.", "the live alert call names the reason: " + await txt(q4, "#alert-msg"));
    await upd(q4, { heard: 'play me a song "please"', lag: false });
    ok((await txt(q4, "#diag")).indexOf('last heard: "play me a song "please""') >= 0 && (await txt(q4, "#diag")).indexOf("busy") < 0, "the staff footer shows what Pepper heard: " + await txt(q4, "#diag"));
    await upd(q4, { heard: "music", lag: true });
    ok((await txt(q4, "#diag")).indexOf("Pepper is busy: tracking paused") >= 0, "the staff footer says when tracking is paused: " + await txt(q4, "#diag"));
    await upd(q4, { heard: "", lag: false });
    ok((await txt(q4, "#diag")).indexOf("last heard") < 0 && (await txt(q4, "#diag")).indexOf("busy") < 0, "nothing heard, nothing shown: " + await txt(q4, "#diag"));
    await upd(q4, { heard: "<b>x</b>", lag: false });
    ok(!(await q4.evaluate(() => !!document.querySelector("#diag b"))), "what was heard is shown as plain text");
    // v4.1.1: the voice check. Not checked yet or fine: nothing special. Dead: the status pill, the footer and one note tell the staff.
    await upd(q4, { voice: null });
    ok((await txt(q4, "#status")).indexOf("voice not ready") < 0 && (await txt(q4, "#diag")).indexOf("voice is not ready") < 0, "no voice warning before the check");
    await upd(q4, { voice: true });
    ok((await txt(q4, "#status")).indexOf("voice not ready") < 0, "no voice warning when the voice is ready");
    await upd(q4, { voice: false });
    ok((await txt(q4, "#status")) === "Pepper voice not ready", "the status pill says the voice is not ready: " + await txt(q4, "#status"));
    ok((await q4.evaluate(() => document.getElementById("status").className)).indexOf("warn") >= 0, "the pill is a warning");
    ok((await txt(q4, "#diag")).indexOf("stop all behaviours on Pepper and start the app once") >= 0, "the footer says what to do: " + await txt(q4, "#diag"));
    ok((await txt(q4, "#alert-msg")).indexOf("Pepper cannot speak yet") === 0, "a note says Pepper cannot speak: " + await txt(q4, "#alert-msg"));
    await q4.evaluate(() => { document.getElementById("alert").className = "alert"; });
    await upd(q4, { voice: false, heard: "again" });
    ok((await q4.evaluate(() => document.getElementById("alert").className)).indexOf("show") < 0, "the note is not shown again while the voice stays broken");
    await upd(q4, { voice: true, heard: "" });
    ok((await txt(q4, "#status")).indexOf("voice not ready") < 0 && (await txt(q4, "#diag")).indexOf("voice is not ready") < 0, "the warning goes when the voice works");
    ok(q4.errs.length === 0, "v4.0 tablet errors " + q4.errs.join("|"));
    await q4.context().close();
  }
  // no network requests leave the page
  const ctx = await b.newContext({ viewport: { width: 1280, height: 800 } }); const q = await ctx.newPage();
  const reqs = []; q.on("request", r => { if (!/^file:|^data:|^blob:/.test(r.url()) && !/qimessaging/.test(r.url())) reqs.push(r.url()); });
  await q.goto("file://" + path.join(DIR, "index.html")); await q.waitForTimeout(400);
  ok(reqs.length === 0, "external requests: " + reqs.join(","));
  await b.close();

  if (fails.length) { console.log("TABLET FAILED (" + pass + " passed)"); fails.forEach(f => console.log(" -", f)); process.exit(1); }
  console.log(pass + " tablet checks passed"); console.log("TABLET OK");
})().catch(e => { console.error(e); process.exit(1); });
