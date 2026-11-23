// Screenshots of the new Home and every intro scene, at 1280x800 (robot state faked). Usage: node tests/intro_shots.js OUTDIR
const { chromium } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const ROOT = path.join(__dirname, '..', 'ChampionshipHost', 'html'), OUT = process.argv[2] || '/tmp/intro';
fs.mkdirSync(OUT, { recursive: true });
const types = { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.json': 'application/json', '.csv': 'text/csv; charset=utf-8', '.mp4': 'video/mp4', '.jpg': 'image/jpeg', '.woff': 'font/woff' };
const srv = http.createServer((q, r) => { const p = path.join(ROOT, decodeURIComponent(q.url.split('?')[0])); if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'Content-Type': types[path.extname(p)] || 'application/octet-stream' }); fs.createReadStream(p).pipe(r); });
(async () => {
  await new Promise(r => srv.listen(0, r));
  const b = await chromium.launch(); const pg = await b.newPage({ viewport: { width: 1280, height: 800 } });
  await pg.goto(`http://127.0.0.1:${srv.address().port}/index.html`); await pg.waitForTimeout(3000);
  const teams = await pg.evaluate(() => HostState.teams.map((t, i) => Object.assign({}, t, { id: 't' + i })));
  const sched = await pg.evaluate(() => HostState.schedule);
  const base = { v: '1.1.0', now: Date.UTC(2026, 10, 28, 14, 26), voice: true, speaking: true, calls: true, teams, schedule: sched, scores: [], alerts: [], introAuto: true, introEvery: 10 };
  await pg.evaluate(s => HostUI.update(s), Object.assign({ seq: 1, intro: null, speaking: false }, base)); await pg.waitForTimeout(400);
  await pg.screenshot({ path: OUT + '/00-home.png' });
  const content = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/content.json'), 'utf8'));
  for (let i = 0; i < content.intro.length; i++) {
    const sc = content.intro[i];
    const na = teams.filter(t => t.cat === 'arena').length, nm = teams.length - na;   // from teams.csv, like Pepper
    const fill = t => String(t || '').replace('{n}', String(teams.length)).replace('{na}', String(na)).replace('{nm}', String(nm));
    const intro = { i, n: content.intro.length, id: sc.id, kind: sc.kind, clip: sc.clip || '', head: fill(sc.head), sub: sc.kind === 'next' ? 'Coming up next, at 15:20: Time of Fall in the Arena.' : fill(sc.sub) };
    await pg.evaluate(s => HostUI.update(s), Object.assign({ seq: 2 + i, intro }, base)); await pg.waitForTimeout(500);
    await pg.screenshot({ path: `${OUT}/${String(i + 1).padStart(2, '0')}-${sc.id}.png` });
  }
  await b.close(); srv.close();
})();
