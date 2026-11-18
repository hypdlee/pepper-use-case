// Screenshots of the tablet at Pepper's 1280x800, with a fake robot state. Usage: node tests/shots.js OUTDIR
const { chromium } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const ROOT = path.join(__dirname, '..', 'ChampionshipHost', 'html'), OUT = process.argv[2] || '/tmp/shots';
fs.mkdirSync(OUT, { recursive: true });
const types = { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.json': 'application/json', '.csv': 'text/csv', '.mp4': 'video/mp4', '.jpg': 'image/jpeg', '.woff': 'font/woff', '.png': 'image/png', '.txt': 'text/plain' };
const srv = http.createServer((q, r) => { const p = path.join(ROOT, decodeURIComponent(q.url.split('?')[0])); if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'Content-Type': types[path.extname(p)] || 'application/octet-stream' }); fs.createReadStream(p).pipe(r); });
const T = Date.UTC(2026, 10, 28, 14, 20);   // Sat 15:20 Malta
// Real team list (read by the page from teams.csv), the two fixed ceremonies, and no invented scores or matches.
const state = { seq: 1, v: '1.0.1', now: T, voice: true, speaking: false, calls: true, teams: null,
  schedule: [ { id: 's1', day: 'sat', time: '14:00', mins: 30, title: 'Opening Ceremony', cat: 'stage', game: '', a: '', b: '', done: false },
              { id: 's4', day: 'sun', time: '18:00', mins: 45, title: 'Awards Ceremony', cat: 'stage', game: '', a: '', b: '', done: false } ],
  scores: [], alerts: [ { id: 'a1', t: T - 60000, text: 'A visitor at Pepper asked for a volunteer.', seen: false } ] };
(async () => {
  await new Promise(r => srv.listen(0, r)); const port = srv.address().port;
  const b = await chromium.launch(); const pg = await b.newPage({ viewport: { width: 1280, height: 800 } });
  const errs = []; pg.on('pageerror', e => errs.push(e.message)); pg.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await pg.goto(`http://127.0.0.1:${port}/index.html`); await pg.waitForTimeout(800);
  await pg.screenshot({ path: OUT + '/0-home-preview.png' });
  await pg.waitForTimeout(2600); state.teams = await pg.evaluate(() => HostState.teams.map((t, i) => Object.assign({}, t, { id: 't' + i }))); await pg.evaluate(s => HostUI.update(s), state); await pg.waitForTimeout(300);
  await pg.screenshot({ path: OUT + '/1-home-live.png' });
  const shots = [['games', null, '2-games-arena'], ['games', 'arm', '3-games-arm'], ['game', 'tof', '4-game-tof'], ['game', 'tower', '5-game-tower'], ['teams', null, '6-teams'], ['schedule', null, '7-schedule'], ['scores', null, '8-scores'], ['help', null, '9-help']];
  for (const [v, a, n] of shots) { await pg.evaluate(([v, a]) => HostUI.go(v, a), [v, a]); await pg.waitForTimeout(700); await pg.screenshot({ path: `${OUT}/${n}.png` }); }
  await pg.evaluate(() => HostUI.quizStart()); await pg.waitForTimeout(300); await pg.click('[data-ans="1"]'); await pg.waitForTimeout(200); await pg.screenshot({ path: OUT + '/10-quiz.png' });
  await pg.evaluate(() => HostUI.staff({ ok: true, token: 'x' })); await pg.waitForTimeout(200); await pg.screenshot({ path: OUT + '/11-staff-alerts.png' });
  await pg.click('[data-st="schedule"]'); await pg.waitForTimeout(200); await pg.screenshot({ path: OUT + '/12-staff-schedule.png' });
  console.log('errors:', JSON.stringify(errs)); await b.close(); srv.close();
})();
