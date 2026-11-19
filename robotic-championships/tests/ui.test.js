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
  ok((await pg.evaluate(() => HostState.schedule.length)) === 56, 'the official running order (56 items) not read in preview');
  ok((await pg.evaluate(() => HostState.schedule.filter(x => x.title === 'Time of Fall').length)) === 16 && (await pg.evaluate(() => HostState.schedule[6].a === 'Troda\u00ed' && HostState.schedule[6].b === 'BRIS - SWERVY')), 'Time of Fall matches from the running order');
  ok((await pg.evaluate(() => HostState.teams.filter(t => t.cat === 'arena').length)) === 8 && (await pg.evaluate(() => HostState.teams.filter(t => t.cat === 'arm').length)) === 5, 'official teams from teams.csv (8 + 5)');
  ok((await pg.evaluate(() => HostState.teams.some(t => t.name === 'Troda\u00ed'))), 'accented team name read from teams.csv');
  ok((await txt('#footRules')).indexOf('v0.7') >= 0, 'rulebook version not shown');
  ok(await vis('#countBox'), 'countdown not shown before the event');
  ok((await pg.$$eval('.stat', e => e.length)) === 3, 'stats');
  await pg.click('[data-go="teams"]'); await pg.waitForTimeout(100);
  ok((await pg.$$eval('#teamSeg button', e => e.map(x => x.textContent))).join('|') === 'All teams \u00b7 13|Arena \u00b7 8|Robot Arm AI \u00b7 5', 'team counts on the filter buttons');
  ok((await pg.$$eval('.tgh', e => e.map(x => x.textContent))).join('|') === 'Arena: 4 Games8 teams|Robot Arm AI Challenge5 teams', 'team groups: ' + (await pg.$$eval('.tgh', e => e.map(x => x.textContent))).join('|'));
  ok((await pg.$$eval('#teamGrid .team', e => e.length)) === 13, 'all 13 team cards');
  ok((await pg.evaluate(() => { const g = document.getElementById('teamGrid'); return g.scrollHeight <= g.clientHeight + 1; })), 'all 13 teams visible without scrolling');
  ok((await pg.$$eval('#teamGrid .tn', e => e.every(x => x.scrollWidth <= x.clientWidth + 1))), 'a team name is cut off');
  ok((await pg.$$eval('#teamGrid .team', e => e.every(x => { const r = x.getBoundingClientRect(); return r.right <= 1280 && r.bottom <= 770; }))), 'a team card is off screen');
  ok((await pg.$$eval('.tcards', e => e.map(c => { const tops = {}; Array.prototype.forEach.call(c.children, k => { tops[Math.round(k.getBoundingClientRect().top)] = (tops[Math.round(k.getBoundingClientRect().top)] || 0) + 1; }); return Object.keys(tops).map(t => tops[t]).join(','); }).join('|'))) === '4,4|4,1', 'cards per row (expected 4 per row)');
  await pg.evaluate(() => HostUI.go('home')); await pg.waitForTimeout(100);
  ok((await txt('#tileTeams')) === '8 Arena \u00b7 5 Robot Arm', 'teams tile in preview: ' + await txt('#tileTeams'));
  ok((await pg.$$eval('.stat b', e => e.map(x => x.textContent))).join('|') === '40+|13|10+', 'home stats use the real team count');
  await pg.evaluate(() => HostUI.go('scores')); await pg.waitForTimeout(100);
  ok((await pg.$$eval('#boardArena li', e => e.length)) === 8 && (await pg.$$eval('#boardArm li', e => e.length)) === 5, 'every team listed on its board before any score');
  ok((await pg.$$eval('.board', e => e.every(b => b.scrollHeight <= b.clientHeight + 1 && b.getBoundingClientRect().right <= 1280))), 'a scoreboard needs scrolling or is off screen');
  ok((await pg.$$eval('#boardArena .pt', e => e.every(x => x.textContent === 'No score yet'))), 'no-score label');
  ok((await pg.$eval('#boardArena li .rk', e => getComputedStyle(e).backgroundColor)) !== 'rgb(255, 205, 87)', 'a team without a score shown as first place');
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
  ok((await txt('#tileTeams')) === '2 Arena \u00b7 2 Robot Arm', 'teams tile: ' + await txt('#tileTeams'));
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
  const ratio = await pg.$$eval('#gameCards .gcard img', e => e.map(i => (i.clientWidth / i.clientHeight) / (i.naturalWidth / i.naturalHeight)));
  ok(ratio.length === 4 && ratio.every(r => Math.abs(r - 1) < 0.01), 'arena card pictures are not 16:9 boxes: ' + ratio.join(','));
  ok((await pg.$$eval('#gameCards .gcard', e => e.every(x => x.getBoundingClientRect().right <= 1280 && x.getBoundingClientRect().bottom <= 770))), 'arena cards fit on screen');
  ok((await sent()).some(m => m.cmd === 'view' && m.view === 'games' && m.arg === 'arena'), 'view message');
  await pg.click('[data-cat="arm"]'); await pg.waitForTimeout(150);
  ok((await pg.$$eval('#gameCards .gcard', e => e.length)) === 6, 'six arm games');
  const ratio2 = await pg.$$eval('#gameCards .gcard img', e => e.map(i => (i.clientWidth / i.clientHeight) / (i.naturalWidth / i.naturalHeight)));
  ok(ratio2.length === 6 && ratio2.every(r => Math.abs(r - 1) < 0.01), 'arm card pictures are not 16:9 boxes: ' + ratio2.join(','));
  ok((await pg.$$eval('#gameCards .gcard', e => e.every(x => x.getBoundingClientRect().right <= 1280 && x.getBoundingClientRect().bottom <= 770))), 'arm cards fit on screen');
  await pg.click('[data-game="pour"]'); await pg.waitForTimeout(600);
  ok((await txt('#gtitle')) === 'Pouring', 'game detail title');
  ok((await pg.$eval('.vidwrap', v => Math.abs(v.clientWidth / v.clientHeight - 16 / 9) < 0.01)), 'video box is not 16:9');
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
  ok((await pg.$$eval('#boardArm .nm', e => e.map(x => x.textContent))).join('|') === 'ArmStrong|<img src=x onerror="window.__xss=1">', 'unscored teams listed after scored ones');
  ok((await pg.$$eval('#boardArm .rk', e => e.map(x => x.textContent))).join('|') === '1|-', 'unscored teams get no rank');
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
  await pg.click('[data-st="schedule"]');
  ok((await pg.$$eval('#sA option', e => e.map(x => x.textContent))).join('|') === '(none)|Team Falcon|Team Orion', 'arena match offers only arena teams');
  await pg.selectOption('#sCat', 'arm'); await pg.waitForTimeout(100);
  ok((await pg.$$eval('#sA option', e => e.map(x => x.textContent))).join('|') === '(none)|<img src=x onerror="window.__xss=1">|ArmStrong', 'arm match offers only arm teams: ' + (await pg.$$eval('#sA option', e => e.map(x => x.textContent))).join('|'));
  await pg.selectOption('#sCat', 'arena'); await pg.waitForTimeout(100);
  await pg.fill('#sTime', '9:30'); await pg.selectOption('#sGame', 'wil'); await pg.selectOption('#sA', 'Team Falcon');
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
  // ---- v1.1: Pepper's intro (driven by the robot)
  await pg.evaluate(() => HostUI.go('home')); await pg.waitForTimeout(100);
  const before = (await sent()).length;
  await pg.click('#introBtn');
  ok((await sent()).slice(before).some(m => m.cmd === 'intro'), 'intro button asks Pepper for the intro');
  const scenes = content.intro;
  ok(scenes.length === 12 && scenes.every(x => x.say && x.head), 'twelve intro scenes with speech and a title');
  for (let i = 0; i < scenes.length; i++) {
    const sc = scenes[i];
    await pg.evaluate(s => HostUI.update(s), state({ seq: 100 + i, intro: { i, n: scenes.length, id: sc.id, kind: sc.kind, clip: sc.clip || '', head: sc.head.replace('{n}', '4'), sub: 'Sub' } }));
    await pg.waitForTimeout(60);
    ok(await vis('#v-intro') && !(await vis('#nav')), 'intro screen with the navigation hidden, scene ' + sc.id);
    ok((await txt('#introHead')) === sc.head.replace('{n}', '4'), 'intro title, scene ' + sc.id);
    ok((await pg.$$eval('#introDots span', e => e.length)) === 12 && (await pg.$$eval('#introDots span.on', e => e.length)) === 1, 'progress dots, scene ' + sc.id);
    if (sc.clip) { ok((await pg.$eval('#ivid', v => v.getAttribute('data-src'))) === 'clips/' + sc.clip + '.mp4' && !(await vis('#introBig')), 'intro clip, scene ' + sc.id); }
    else { ok(await vis('#introBig'), 'intro panel, scene ' + sc.id); }
    ok((await pg.evaluate(() => { const b = document.getElementById('introBig'); return Array.prototype.every.call(b.querySelectorAll('*'), e => e.getBoundingClientRect().right <= b.getBoundingClientRect().right + 1 && e.getBoundingClientRect().bottom <= b.getBoundingClientRect().bottom + 1); })), 'intro panel content spills out, scene ' + sc.id);
    if (sc.kind === 'teams') { ok((await pg.$$eval('.ib-col div', e => e.length)) === 4, 'team names in the intro'); }
  }
  await pg.click('#introSkip');
  ok((await sent()).some(m => m.cmd === 'intro-stop'), 'skip asks Pepper to stop the intro');
  await pg.evaluate(s => HostUI.update(s), state({ seq: 200, intro: null })); await pg.waitForTimeout(80);
  ok(await vis('#v-home') && await vis('#nav'), 'back home with the navigation after the intro');
  await pg.evaluate(() => { HostState.lastTouch = Date.now() - 200000; });
  await pg.evaluate(s => HostUI.update(s), state({ seq: 201, intro: { i: 3, n: 12, id: 'chaos', kind: 'clip', clip: 'arena-climate-chaos', head: 'Climate CHAOS', sub: '' } }));
  await pg.waitForTimeout(1300);
  ok(await vis('#v-intro'), 'the idle timer must not end the intro');
  await pg.evaluate(s => HostUI.update(s), state({ seq: 202, intro: null })); await pg.waitForTimeout(80);

  // ---- v1.1: home reel shows the games in turn
  await pg.evaluate(() => HostUI.go('home')); await pg.waitForTimeout(80);
  const r1 = await txt('#reelTitle'); await pg.evaluate(() => HostState.nextReel()); const r2 = await txt('#reelTitle');
  ok(r1 && r2 && r1 !== r2 && content.games.some(g => g.title === r2), 'home reel moves to the next game: ' + r1 + ' -> ' + r2);
  ok((await pg.$eval('.reel', v => Math.abs(v.clientWidth / v.clientHeight - 16 / 9) < 0.01)), 'reel box is 16:9');

  // ---- v1.1: 100 questions, five per round, nothing repeats until all 100 were asked
  await pg.evaluate(() => { try { localStorage.removeItem('host.quizBag'); } catch (e) {} });
  await pg.reload(); await pg.waitForTimeout(3000);
  await pg.evaluate(() => { window.__sent = []; Bridge.canSend = () => true; Bridge.send = m => { window.__sent.push(m); return true; }; });
  const rounds = await pg.evaluate(() => { const out = []; for (let i = 0; i < 21; i++) { out.push(HostState.nextFive()); } return out; });
  const first20 = [].concat(...rounds.slice(0, 20).map(r => r.five));
  ok(first20.length === 100 && new Set(first20).size === 100, '20 rounds of five cover all 100 questions once');
  ok(rounds.every(r => r.five.length === 5), 'every round has five questions');
  ok(rounds[20].five.every(q => rounds[19].five.indexOf(q) < 0), 'a new pass does not start with the questions just asked');
  ok(rounds[20].round === 21 && rounds[19].left === 0, 'round counter');
  await pg.reload(); await pg.waitForTimeout(3000);
  await pg.evaluate(() => { window.__sent = []; Bridge.canSend = () => true; Bridge.send = m => { window.__sent.push(m); return true; }; });
  const after = await pg.evaluate(() => HostState.nextFive());
  ok(after.round === 22 && after.five.every(q => rounds[20].five.indexOf(q) < 0), 'the shuffle bag continues after a reload');
  await pg.evaluate(() => HostUI.go('quiz')); ok((await txt('.qq')).indexOf('100') >= 0, 'quiz start mentions the 100 questions');

  // ---- v1.1: staff can start the intro and switch the automatic intro off
  await pg.evaluate(s => HostUI.update(s), state({ seq: 300 }));
  await pg.evaluate(() => HostUI.staff({ ok: true, token: 'tok9' })); await pg.click('[data-st="announce"]');
  await pg.click('[data-act="intro-start"]'); ok((await sent()).some(m => m.cmd === 'intro-start' && m.token === 'tok9'), 'staff intro start');
  await pg.click('[data-act="intro-auto"]'); ok((await sent()).some(m => m.cmd === 'intro-auto' && m.on === false && m.token === 'tok9'), 'staff automatic intro off');
  await pg.evaluate(() => HostUI.staffClosed());

  // ---- v1.1: without a robot, the page plays the intro by itself
  await pg.evaluate(() => { Bridge.canSend = () => false; HostUI.go('home'); }); await pg.waitForTimeout(80);
  await pg.click('#introBtn'); await pg.waitForTimeout(100);
  ok(await vis('#v-intro') && (await txt('#introHead')) === 'Hello! I am Pepper', 'intro plays without a robot');
  await pg.waitForTimeout(5200); ok((await txt('#introHead')) === 'Two competitions', 'local intro moves on: ' + await txt('#introHead'));
  await pg.click('#introSkip'); ok(await vis('#v-home'), 'local intro skip');
  await pg.evaluate(() => { Bridge.canSend = () => true; });

  // CSV parser matches the controller's rules
  const rows = await pg.evaluate(() => HostState.parseCSV('﻿name,x\r\n"a ""b"", c",1\r\n# c\r\n\r\nd,2'));
  ok(JSON.stringify(rows) === JSON.stringify([{ name: 'a "b", c', x: '1' }, { name: 'd', x: '2' }]), 'csv parser ' + JSON.stringify(rows));
  ok(errs.length === 0, 'page errors: ' + errs.join(' | '));
  await b.close(); srv.close();
  console.log(`UI ${fail ? 'FAILED' : 'OK'}: ${pass} passed, ${fail} failed`);
  process.exit(fail ? 1 : 0);
})();
