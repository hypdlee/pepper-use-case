// Tablet tests for the Pepper host (Playwright Chromium at 1280x800). Usage: node tests/ui.test.js
const { chromium } = require('playwright');
const acorn = require('acorn');
const http = require('http'), fs = require('fs'), path = require('path');
const ROOT = path.join(__dirname, '..', 'ChampionshipHost', 'html');
let pass = 0, fail = 0;
function ok(c, m) { if (c) { pass++; } else { fail++; console.log('FAIL:', m); } }

for (const f of ['js/host.js', 'js/bridge.js']) {
  try { acorn.parse(fs.readFileSync(path.join(ROOT, f), 'utf8'), { ecmaVersion: 5 }); ok(true); } catch (e) { ok(false, 'ES5 parse ' + f + ': ' + e.message); }
}
const content = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/content.json'), 'utf8'));
for (const g of content.games) {
  ok(fs.existsSync(path.join(ROOT, 'clips', g.clip + '.mp4')) && fs.existsSync(path.join(ROOT, 'clips', g.clip + '.jpg')), 'clip missing for ' + g.id);
  ok(g.facts.length === 3 && g.say.length > 40 && g.say.length < 400, 'game text for ' + g.id);
}
for (const q of content.quiz) { ok(q.a.length === 3 && q.ok >= 0 && q.ok < 3 && q.why, 'quiz item ' + q.q); }

const types = { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.json': 'application/json', '.csv': 'text/csv', '.mp4': 'video/mp4', '.jpg': 'image/jpeg', '.woff': 'font/woff', '.png': 'image/png' };
const srv = http.createServer((q, r) => { const p = path.join(ROOT, decodeURIComponent(q.url.split('?')[0])); if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'Content-Type': types[path.extname(p)] || 'application/octet-stream' }); fs.createReadStream(p).pipe(r); });
const T = Date.UTC(2026, 10, 28, 14, 20);   // Sat 15:20 Malta
function state(extra) {
  return Object.assign({ seq: 1, v: '1.0.0', now: T, voice: true, speaking: false, calls: true,
    teams: [ { id: 't1', name: 'Team Falcon', country: 'Croatia', cat: 'arena', say: '' }, { id: 't2', name: 'Team Orion', country: 'Greece', cat: 'arena', say: '' },
             { id: 't4', name: 'ArmStrong', country: 'Portugal', cat: 'arm', say: '' }, { id: 'tx', name: '<img src=x onerror="window.__xss=1">', country: '<b>x</b>', cat: 'arm', say: '' } ],
    schedule: [ { id: 's1', day: 'sat', time: '14:00', mins: 30, title: 'Opening Ceremony', cat: 'stage', game: '', a: '', b: '', done: false },
                { id: 's2', day: 'sat', time: '15:10', mins: 15, title: 'Time of Fall', cat: 'arena', game: 'tof', a: 'Team Falcon', b: 'Team Orion', done: false },
                { id: 's3', day: 'sat', time: '15:30', mins: 15, title: 'Colour Sort', cat: 'arm', game: 'colour', a: 'ArmStrong', b: '', done: false },
                { id: 's4', day: 'sun', time: '18:00', mins: 45, title: 'Awards Ceremony', cat: 'stage', game: '', a: '', b: '', done: false } ],
    scores: [ { id: 'c1', team: 'Team Orion', cat: 'arena', points: 95 }, { id: 'c2', team: 'Team Falcon', cat: 'arena', points: 120 }, { id: 'c3', team: 'ArmStrong', cat: 'arm', points: 88 } ],
    alerts: [] }, extra || {});
}

(async () => {
  await new Promise(r => srv.listen(0, r));
  const url = `http://127.0.0.1:${srv.address().port}/index.html`;
  const b = await chromium.launch();
  const pg = await b.newPage({ viewport: { width: 1280, height: 800 } });
  const errs = []; pg.on('pageerror', e => errs.push(e.message));
  await pg.goto(url); await pg.waitForTimeout(3000);
  const txt = s => pg.$eval(s, e => e.textContent);
  const vis = s => pg.$eval(s, e => !!(e.offsetWidth || e.offsetHeight) && !e.hidden);

  // preview mode (no robot): content and the CSV files are read by the page itself
  ok((await txt('#status')) === 'Preview', 'status in preview: ' + await txt('#status'));
  ok((await pg.evaluate(() => HostState.schedule.length)) === 2, 'schedule.csv not read in preview');
  ok((await pg.evaluate(() => HostState.teams.length)) === 0, 'teams.csv template should be empty');
  ok((await txt('#footRules')).indexOf('v0.7') >= 0, 'rulebook version not shown');
  ok(await vis('#countBox'), 'countdown not shown before the event');
  ok((await pg.$$eval('.stat', e => e.length)) === 3, 'stats');
  await pg.click('[data-go="teams"]'); await pg.waitForTimeout(100);
  ok((await txt('#teamGrid')).indexOf('coming soon') >= 0, 'empty team list message');
  await pg.click('[data-go="schedule"]'); await pg.waitForTimeout(100);
  ok((await txt('#schedList')).indexOf('Opening Ceremony') >= 0, 'opening ceremony in schedule');
  // volunteer without robot
  await pg.click('[data-go="help"]'); await pg.click('#volBtn'); await pg.waitForTimeout(100);
  ok((await txt('#volDone')).indexOf('not connected') >= 0, 'volunteer without Pepper must say so');

  // connect a fake robot
  await pg.evaluate(() => { window.__sent = []; Bridge.canSend = () => true; Bridge.send = m => { window.__sent.push(m); return true; }; });
  const sent = () => pg.evaluate(() => window.__sent.slice());
  await pg.evaluate(s => HostUI.update(s), state()); await pg.evaluate(() => HostUI.go('home')); await pg.waitForTimeout(150);
  ok((await txt('#status')) === 'Pepper connected', 'status connected');
  ok((await txt('#clock')) === '15:20', 'Malta clock from the robot: ' + await txt('#clock'));
  ok(await vis('#liveBox') && !(await vis('#countBox')), 'live box during the event');
  ok((await txt('#liveNow')).indexOf('15:10  Time of Fall') >= 0 && (await txt('#liveNow')).indexOf('Red: Team Falcon') >= 0, 'now: ' + await txt('#liveNow'));
  ok((await txt('#liveNext')).indexOf('15:30  Colour Sort') >= 0, 'next: ' + await txt('#liveNext'));
  ok((await txt('#tileTeams')) === '4 teams', 'teams tile');
  await pg.evaluate(s => HostUI.update(s), state({ seq: 2, speaking: true }));
  ok(await vis('#speaking') && await vis('#stopTalk'), 'speaking indicator');
  await pg.click('#stopTalk'); ok((await sent()).some(m => m.cmd === 'stop'), 'stop button sends stop');
  await pg.evaluate(s => HostUI.update(s), state({ seq: 3, voice: false }));
  ok((await txt('#status')) === 'Voice not ready', 'listening problem shown');
  await pg.evaluate(s => HostUI.update(s), state({ seq: 2 }));
  ok((await txt('#status')) === 'Voice not ready', 'an older state was not ignored');

  // games
  await pg.click('[data-go="games"][data-arg="arena"]'); await pg.waitForTimeout(150);
  ok((await pg.$$eval('#gameCards .gcard', e => e.length)) === 4, 'four arena games');
  ok((await pg.$$eval('#gameCards .gcard', e => e.every(x => x.getBoundingClientRect().right <= 1280 && x.getBoundingClientRect().bottom <= 770))), 'arena cards fit on screen');
  ok((await sent()).some(m => m.cmd === 'view' && m.view === 'games' && m.arg === 'arena'), 'view message');
  await pg.click('[data-cat="arm"]'); await pg.waitForTimeout(150);
  ok((await pg.$$eval('#gameCards .gcard', e => e.length)) === 6, 'six arm games');
  ok((await pg.$$eval('#gameCards .gcard', e => e.every(x => x.getBoundingClientRect().right <= 1280 && x.getBoundingClientRect().bottom <= 770))), 'arm cards fit on screen');
  await pg.click('[data-game="pour"]'); await pg.waitForTimeout(600);
  ok((await txt('#gtitle')) === 'Pouring', 'game detail title');
  ok((await pg.$$eval('#gfacts li', e => e.length)) === 3, 'three facts');
  ok((await sent()).some(m => m.cmd === 'game' && m.game === 'pour' && m.id !== 'pour'), 'game message: game field kept apart from the message id');
  ok((await pg.$eval('#gvid', v => v.getAttribute('data-src'))) === 'clips/arm-pouring.mp4', 'clip chosen');
  ok((await pg.$eval('#gvid', v => v.muted)), 'clip muted');
  await pg.click('#gnext'); await pg.waitForTimeout(200); ok((await txt('#gtitle')) === 'Folding', 'next game');
  await pg.click('#gexplain'); ok((await sent()).filter(m => m.cmd === 'game' && m.game === 'fold').length === 2, 'explain again');
  await pg.click('#gback'); ok(await vis('#v-games'), 'back to games');
  await pg.evaluate(() => HostUI.go('game', 'hh')); await pg.waitForTimeout(200);
  ok((await txt('#gtitle')) === 'Hanging Hazard' && !(await sent()).some(m => m.game === 'hh'), 'voice navigation must not ask Pepper to speak twice');

  // teams: text only (no markup from staff input)
  await pg.click('[data-go="teams"]'); await pg.waitForTimeout(150);
  ok((await pg.$$eval('#teamGrid .team', e => e.length)) === 4, 'team cards');
  ok((await pg.evaluate(() => window.__xss)) === undefined && (await pg.$$eval('#teamGrid img', e => e.length)) === 0, 'team name rendered as markup');
  await pg.click('[data-f="arena"]'); ok((await pg.$$eval('#teamGrid .team', e => e.length)) === 2, 'arena filter');
  const names = await pg.$$eval('#teamGrid .tn', e => e.map(x => x.textContent)); ok(names[0] === 'Team Falcon' && names[1] === 'Team Orion', 'teams sorted');

  // schedule and scores
  await pg.click('[data-go="schedule"]'); await pg.waitForTimeout(150);
  ok((await pg.$$eval('#schedList .srow.now', e => e.map(x => x.textContent))).join().indexOf('Time of Fall') >= 0, 'NOW row');
  ok((await pg.$$eval('#schedList .srow.next', e => e.map(x => x.textContent))).join().indexOf('Colour Sort') >= 0, 'NEXT row');
  ok((await pg.$$eval('#schedList .srow.done', e => e.length)) === 1, 'finished row greyed');
  await pg.click('[data-day="sun"]'); ok((await txt('#schedList')).indexOf('Awards Ceremony') >= 0, 'sunday');
  await pg.click('[data-go="scores"]'); await pg.waitForTimeout(150);
  ok((await pg.$$eval('#boardArena .nm', e => e.map(x => x.textContent))).join('|') === 'Team Falcon|Team Orion', 'arena board ordered by points');
  ok((await txt('.provisional')).indexOf('Official results are announced by the judges') >= 0, 'provisional note');

  // quiz, by touch and by voice
  await pg.click('[data-go="quiz"]'); await pg.click('#quizStart'); await pg.waitForTimeout(150);
  let q = await pg.evaluate(() => HostState.quiz);
  ok(q.order.length === 5 && new Set(q.order).size === 5, 'five different questions');
  ok((await sent()).some(m => m.cmd === 'quizq' && m.i === q.order[0] && m.opts.length === 3), 'question sent to Pepper');
  for (let k = 0; k < 5; k++) {
    q = await pg.evaluate(() => HostState.quiz);
    const right = q.opts.indexOf(content.quiz[q.order[q.k]].ok);
    if (k % 2 === 0) { await pg.click(`[data-ans="${right}"]`); } else { await pg.evaluate(n => HostUI.answer(n), right + 1); }
    await pg.waitForTimeout(80);
    ok((await pg.$$eval('.qa.right', e => e.length)) === 1, 'right answer shown');
    if (k === 0) {
      const wrong = (right + 1) % 3, before = (await sent()).length;
      await pg.click(`[data-ans="${wrong}"]`);
      ok((await sent()).length === before && (await pg.evaluate(() => HostState.quiz.score)) === 1, 'a second answer to the same question counted');
    }
    if (k % 2 === 0) { await pg.click('#quizNext'); } else { await pg.evaluate(() => HostUI.answer(0)); }
    await pg.waitForTimeout(80);
  }
  ok((await txt('.qbig')) === '5 of 5', 'final score');
  ok((await sent()).some(m => m.cmd === 'quizend' && m.score === 5 && m.total === 5), 'quiz end sent');
  ok((await sent()).filter(m => m.cmd === 'quiza' && m.ok === true).length === 5, 'answers sent');

  // volunteer with robot
  await pg.click('[data-go="home"]'); await pg.click('[data-go="help"][data-arg="volunteer"]'); await pg.waitForTimeout(150);
  ok((await sent()).filter(m => m.cmd === 'volunteer').length === 1 && (await txt('#volDone')).indexOf('has been called') >= 0, 'volunteer tile');
  await pg.click('#volBtn'); ok((await sent()).filter(m => m.cmd === 'volunteer').length === 1, 'double volunteer call within a minute');

  // the quiz order changes between games
  const firsts = new Set();
  for (let r = 0; r < 12; r++) { await pg.evaluate(() => HostUI.quizStart()); firsts.add(await pg.evaluate(() => HostState.quiz.order.join(','))); }
  ok(firsts.size > 1, 'quiz questions are always in the same order');
  await pg.evaluate(() => HostUI.go('home'));
  // five slow taps do not open staff mode
  for (let i = 0; i < 4; i++) { await pg.click('.wm1'); }
  await pg.waitForTimeout(3200); await pg.click('.wm1');
  ok(!(await vis('#pin')), 'slow taps opened the PIN pad');
  await pg.waitForTimeout(3100);
  // staff mode: five taps on the title, PIN, then the robot answers
  for (let i = 0; i < 5; i++) { await pg.click('.wm1'); }
  ok(await vis('#pin'), 'PIN pad after five taps');
  for (const k of ['2', '4', '6', '8']) { await pg.click(`[data-pin="${k}"]`); }
  await pg.click('[data-pin="OK"]');
  ok((await sent()).some(m => m.cmd === 'staff-login' && m.pin === '2468'), 'PIN sent to Pepper');
  await pg.evaluate(() => HostUI.staff({ ok: false })); ok((await txt('#pinMsg')) === 'Wrong PIN.', 'wrong PIN message');
  await pg.evaluate(() => HostUI.staff({ ok: true, token: 'tok1' })); await pg.waitForTimeout(100);
  ok(await vis('#v-staff') && !(await vis('#pin')), 'staff screen open');
  await pg.evaluate(s => HostUI.update(s), state({ seq: 10, alerts: [{ id: 'a1', t: T, text: 'A visitor at Pepper asked for a volunteer.', seen: false }] }));
  await pg.waitForTimeout(100);
  ok((await txt('#toast')).indexOf('Volunteer needed') >= 0, 'staff alerted to a new volunteer call');
  await pg.click('[data-seen="a1"]'); ok((await sent()).some(m => m.cmd === 'alert-seen' && m.key === 'a1' && m.token === 'tok1'), 'alert seen');
  await pg.click('[data-st="teams"]'); await pg.fill('#tName', 'Team Nova'); await pg.fill('#tCountry', 'Malta'); await pg.selectOption('#tCat', 'arm');
  await pg.click('[data-act="team-save"]');
  ok((await sent()).some(m => m.cmd === 'team-save' && m.team.name === 'Team Nova' && m.team.cat === 'arm' && m.token === 'tok1'), 'team save');
  await pg.click('[data-edit-team="t1"]'); ok((await pg.$eval('#tName', e => e.value)) === 'Team Falcon', 'edit fills the form');
  await pg.click('[data-del-team="t2"]'); ok((await sent()).some(m => m.cmd === 'team-del' && m.key === 't2'), 'team delete');
  await pg.click('[data-st="schedule"]'); await pg.fill('#sTime', '9:30'); await pg.selectOption('#sGame', 'wil'); await pg.selectOption('#sA', 'Team Falcon');
  await pg.click('[data-act="sched-save"]');
  ok((await sent()).some(m => m.cmd === 'sched-save' && m.item.time === '09:30' && m.item.title === 'Weight in Line' && m.item.a === 'Team Falcon'), 'schedule save');
  await pg.fill('#sTime', 'soon'); await pg.click('[data-act="sched-save"]'); ok((await txt('#toast')).indexOf('14:30') >= 0, 'bad time refused on the tablet');
  await pg.click('[data-done="s2"]'); ok((await sent()).some(m => m.cmd === 'sched-save' && m.item.id === 's2' && m.item.done === true), 'mark done');
  await pg.click('[data-st="scores"]'); await pg.selectOption('#scTeam', 't1'); await pg.fill('#scPts', '140'); await pg.click('[data-act="score-save"]');
  ok((await sent()).some(m => m.cmd === 'score-save' && m.teamId === 't1' && m.points === 140), 'score save');
  await pg.click('[data-st="announce"]'); await pg.fill('#aText', 'Hello everyone'); await pg.click('[data-act="announce"]');
  ok((await sent()).some(m => m.cmd === 'announce' && m.text === 'Hello everyone'), 'announce');
  await pg.click('[data-act="calls"]'); ok((await sent()).some(m => m.cmd === 'calls' && m.on === false), 'calls toggle');
  await pg.click('[data-st="system"]'); ok((await txt('#staffBody')).indexOf('Version: 1.0.0') >= 0, 'system tab');
  await pg.evaluate(() => HostUI.staffClosed()); ok(await vis('#v-home'), 'staff closed by the robot');
  await pg.evaluate(() => HostUI.go('staff')); ok(await vis('#v-home'), 'staff screen without a token');

  // idle: back home after 90 s without a touch
  await pg.click('[data-go="scores"]'); await pg.evaluate(() => { HostState.lastTouch = Date.now() - 91000; }); await pg.waitForTimeout(1300);
  ok(await vis('#v-home'), 'idle return to home');
  // after the event
  await pg.evaluate(s => HostUI.update(s), state({ seq: 20, now: Date.UTC(2026, 10, 29, 20, 0) })); await pg.waitForTimeout(1200);
  ok((await txt('#countLbl')).indexOf('Thank you for coming') >= 0, 'after the event');
  // nothing wider than the screen, on every view
  for (const v of ['home', 'games', 'teams', 'schedule', 'scores', 'quiz', 'help']) {
    await pg.evaluate(v => HostUI.go(v), v); await pg.waitForTimeout(80);
    ok((await pg.evaluate(() => document.documentElement.scrollWidth)) <= 1280, 'horizontal overflow on ' + v);
  }
  // CSV parser matches the controller's rules
  const rows = await pg.evaluate(() => HostState.parseCSV('﻿name,x\r\n"a ""b"", c",1\r\n# c\r\n\r\nd,2'));
  ok(JSON.stringify(rows) === JSON.stringify([{ name: 'a "b", c', x: '1' }, { name: 'd', x: '2' }]), 'csv parser ' + JSON.stringify(rows));
  ok(errs.length === 0, 'page errors: ' + errs.join(' | '));
  await b.close(); srv.close();
  console.log(`UI ${fail ? 'FAILED' : 'OK'}: ${pass} passed, ${fail} failed`);
  process.exit(fail ? 1 : 0);
})();
