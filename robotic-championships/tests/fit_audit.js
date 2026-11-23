// Fit audit with the real team list: every view at 1280x800, reports clipped text and content that needs scrolling.
// Usage: node tests/fit_audit.js OUTDIR   (exit code 1 if anything public is clipped or hidden)
const { chromium } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const ROOT = path.join(__dirname, '..', 'ChampionshipHost', 'html'), OUT = process.argv[2] || '/tmp/audit';
fs.mkdirSync(OUT, { recursive: true });
const types = { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.json': 'application/json', '.csv': 'text/csv; charset=utf-8', '.mp4': 'video/mp4', '.jpg': 'image/jpeg', '.woff': 'font/woff' };
const srv = http.createServer((q, r) => { const p = path.join(ROOT, decodeURIComponent(q.url.split('?')[0])); if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'Content-Type': types[path.extname(p)] || 'application/octet-stream' }); fs.createReadStream(p).pipe(r); });
(async () => {
  await new Promise(r => srv.listen(0, r));
  const b = await chromium.launch(); const pg = await b.newPage({ viewport: { width: 1280, height: 800 } });
  await pg.goto(`http://127.0.0.1:${srv.address().port}/index.html`); await pg.waitForTimeout(3500);
  const teams = await pg.evaluate(() => HostState.teams.map((t, i) => Object.assign({}, t, { id: 't' + i })));
  const T = Date.UTC(2026, 10, 28, 14, 20);
  const scores = teams.map((t, i) => ({ id: 'c' + i, team: t.name, cat: t.cat, points: 200 - i * 7 }));
  const sched = [];
  // a long day: 24 matches from 12:00, so the NOW match (15:15) is far down the list
  for (let i = 0; i < 24; i++) { const a = teams.filter(t => t.cat === 'arena'); sched.push({ id: 's' + i, day: 'sat', time: (12 + Math.floor(i / 4)) + ':' + ['00', '15', '30', '45'][i % 4], mins: 15, title: 'Time of Fall', cat: 'arena', game: 'tof', a: a[i % 8].name, b: a[(i + 3) % 8].name, done: false }); }
  await pg.evaluate(s => HostUI.update(s), { seq: 1, v: '1.0.1', now: T, voice: true, speaking: false, calls: true, teams, schedule: sched, scores, alerts: [] });
  const report = [];
  async function audit(name, publicView) {
    await pg.waitForTimeout(250);
    await pg.screenshot({ path: `${OUT}/${name}.png` });
    const r = await pg.evaluate(() => {
      const out = { clipped: [], scroll: [] };
      document.querySelectorAll('.view.on *, header *, nav *').forEach(e => {
        if (!e.offsetWidth) { return; }
        const cs = getComputedStyle(e);
        if (e.children.length === 0 && e.textContent.trim() && e.scrollWidth > e.clientWidth + 1 && cs.overflow !== 'visible') { out.clipped.push(e.className + ': ' + e.textContent.trim().slice(0, 40)); }
        const rr = e.getBoundingClientRect();
        const dock = document.getElementById('nav'), inDock = dock.contains(e), lim = inDock || !dock.offsetHeight ? 801 : dock.getBoundingClientRect().top + 1;
        if (e.children.length === 0 && e.textContent.trim() && (rr.right > 1281 || rr.bottom > lim)) {
          let p = e.parentElement, inScroll = false;
          while (p) { const s = getComputedStyle(p); if (s.overflowY === 'auto' || s.overflowY === 'scroll') { inScroll = true; break; } p = p.parentElement; }
          if (!inScroll) { out.clipped.push('off-screen ' + e.className + ': ' + e.textContent.trim().slice(0, 40)); }
        }
        if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll') && e.scrollHeight > e.clientHeight + 1) { out.scroll.push(e.id || e.className); }
      });
      return out;
    });
    report.push({ name, publicView, clipped: r.clipped, scroll: r.scroll });
  }
  await pg.evaluate(() => HostUI.go('home')); await audit('home', true);
  // Pepper's intro: every scene, with the real teams from teams.csv and the longest "next" line
  const scenes = await pg.evaluate(() => HostState.content.intro);
  const nAll = String(teams.length), nAr = String(teams.filter(t => t.cat === 'arena').length), nArm = String(teams.length - teams.filter(t => t.cat === 'arena').length);
  for (let i = 0; i < scenes.length; i++) {
    const sc = scenes[i];
    const sub = sc.kind === 'next' ? 'Next: Tower Construction Duel (final), Sunday 16:45, then Hanging Hazard (final)' : (sc.sub || '').replace(/\{n\}/g, nAll).replace(/\{na\}/g, nAr).replace(/\{nm\}/g, nArm);
    await pg.evaluate(s => HostUI.update(s), { seq: 10 + i, v: '1.1.0', now: T, voice: true, speaking: true, calls: true, teams, schedule: sched, scores, alerts: [],
      intro: { i, n: scenes.length, id: sc.id, kind: sc.kind, clip: sc.clip || '', head: sc.head.replace(/\{n\}/g, nAll), sub } });
    await audit('intro-' + (i + 1) + '-' + sc.id, true);
  }
  await pg.evaluate(s => HostUI.update(s), { seq: 40, v: '1.1.0', now: T, voice: true, speaking: false, calls: true, teams, schedule: sched, scores, alerts: [], intro: null });
  await pg.evaluate(() => HostUI.go('teams')); await audit('teams-all', true);
  await pg.click('[data-f="arena"]'); await audit('teams-arena', true);
  await pg.click('[data-f="arm"]'); await audit('teams-arm', true);
  await pg.evaluate(() => HostUI.go('scores')); await audit('scores', true);
  await pg.evaluate(() => HostUI.go('schedule')); await audit('schedule', true);
  const nowVisible = await pg.evaluate(() => { const r = document.querySelector('#schedList .srow.now'), box = document.getElementById('schedList'); if (!r) { return false; } const a = r.getBoundingClientRect(), b = box.getBoundingClientRect(); return a.top >= b.top && a.bottom <= b.bottom; });
  report.push({ name: 'schedule-now-row-in-view', publicView: true, clipped: nowVisible ? [] : ['the NOW match is scrolled out of view'], scroll: [] });
  await pg.evaluate(() => HostUI.go('games', 'arena')); await audit('games-arena', true);
  await pg.evaluate(() => HostUI.go('games', 'arm')); await audit('games-arm', true);
  await pg.evaluate(() => HostUI.go('game', 'tower')); await audit('game-tower', true);
  await pg.evaluate(() => HostUI.go('help')); await audit('help', true);
  await pg.evaluate(() => HostUI.quizStart()); await audit('quiz', true);
  await pg.evaluate(() => HostUI.staff({ ok: true, token: 'x' })); await pg.click('[data-st="teams"]'); await audit('staff-teams', false);
  await pg.click('[data-st="schedule"]'); await audit('staff-schedule', false);
  await pg.click('[data-st="scores"]'); await audit('staff-scores', false);
  let bad = 0;
  for (const r of report) {
    const hiddenPublic = r.publicView ? r.scroll.filter(s => s !== 'schedList') : [];
    console.log(`${r.name}: clipped=${JSON.stringify(r.clipped)} needs-scroll=${JSON.stringify(r.scroll)}`);
    bad += r.clipped.length + hiddenPublic.length;
  }
  await b.close(); srv.close();
  console.log(bad ? `FIT FAILED: ${bad}` : 'FIT OK');
  process.exit(bad ? 1 : 0);
})();
