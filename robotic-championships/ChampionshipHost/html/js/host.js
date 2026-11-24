/* Pepper host for the IEEE Robot Championships 2026: tablet app (ES5, no library).
   Content (games, quiz, event facts) comes from data/content.json, the same file Pepper's voice reads.
   Teams, schedule, scores and alerts come from the Host Controller on the robot (HostUI.update). Without a robot
   (a laptop preview, or the controller not running) the page reads data/teams.csv and data/schedule.csv itself. */
(function (w, d) {
  'use strict';
  var EVENT_UTC = { sat: Date.UTC(2026, 10, 28), sun: Date.UTC(2026, 10, 29) };
  var MALTA_OFFSET = 60 * 60 * 1000;                 /* Malta is UTC+1 in November */
  var IDLE_HOME_MS = 90 * 1000, STAFF_IDLE_MS = 5 * 60 * 1000;
  var H = {
    content: null, teams: [], schedule: [], scores: [], alerts: [], calls: true,
    voice: null, speaking: false, linked: false, robot: false, version: '',
    clockSkew: 0, view: 'home', cat: 'arena', game: null, teamFilter: 'all', day: 'sat',
    quiz: null, intro: null, introAuto: true, introEvery: 10, reelI: 0, staffToken: null, staffTab: 'alerts', staffEdit: null, lastTouch: 0, volunteerAt: 0
  };
  w.HostState = H;

  /* ---------- small helpers ---------- */
  function $(id) { return d.getElementById(id); }
  function el(tag, cls, text) { var e = d.createElement(tag); if (cls) { e.className = cls; } if (text !== undefined && text !== null) { e.textContent = String(text); } return e; }
  function clear(e) { while (e.firstChild) { e.removeChild(e.firstChild); } return e; }
  function each(list, fn) { for (var i = 0; i < list.length; i += 1) { fn(list[i], i); } }
  function now() { return (new Date()).getTime() + H.clockSkew; }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  // The page is laid out for 1280 x 800. If a tablet reports another size, scale the whole page to fit instead of cutting it.
  function fitScreen() {
    var app = $('app'); if (!app) { return; }
    var k = Math.min((w.innerWidth || 1280) / 1280, (w.innerHeight || 800) / 800), tr = Math.abs(k - 1) > 0.01 ? 'scale(' + k + ')' : '';
    app.style.webkitTransformOrigin = '0 0'; app.style.transformOrigin = '0 0';
    app.style.webkitTransform = tr; app.style.transform = tr;
  }
  H.fitScreen = fitScreen;
  function maltaDate(t) { var m = new Date(t + MALTA_OFFSET); return m.getUTCFullYear() + '-' + pad(m.getUTCMonth() + 1) + '-' + pad(m.getUTCDate()); }
  function maltaClock(t) { var m = new Date(t + MALTA_OFFSET); return pad(m.getUTCHours()) + ':' + pad(m.getUTCMinutes()); }
  function send(msg) { if (w.Bridge && w.Bridge.canSend()) { return w.Bridge.send(msg); } return false; }
  function staffSend(msg) { msg.token = H.staffToken; return send(msg); }
  function getJSON(url, ok, fail) {
    try {
      var x = new XMLHttpRequest();
      x.open('GET', url + '?t=' + (new Date()).getTime(), true);
      x.onreadystatechange = function () {
        if (x.readyState !== 4) { return; }
        if ((x.status === 200 || x.status === 0) && x.responseText) { try { ok(x.responseText); } catch (e) { if (fail) { fail(e); } } } else if (fail) { fail(x.status); }
      };
      x.send(null);
    } catch (e) { if (fail) { fail(e); } }
  }

  /* CSV with a header row; lines starting with # are notes; quotes allowed. Same rules as the controller. */
  function parseCSV(text) {
    var rows = [], row = [], f = '', q = false, i, c;
    text = String(text).replace(/^\uFEFF/, '');
    for (i = 0; i < text.length; i += 1) {
      c = text.charAt(i);
      if (q) {
        if (c === '"') { if (text.charAt(i + 1) === '"') { f += '"'; i += 1; } else { q = false; } } else { f += c; }
      } else if (c === '"') { q = true; } else if (c === ',') { row.push(f); f = ''; } else if (c === '\n' || c === '\r') {
        if (c === '\r' && text.charAt(i + 1) === '\n') { i += 1; }
        row.push(f); f = ''; rows.push(row); row = [];
      } else { f += c; }
    }
    if (f !== '' || row.length) { row.push(f); rows.push(row); }
    var out = [], head = null;
    each(rows, function (r) {
      var first = (r[0] || '').replace(/^\s+/, '');
      if (first.charAt(0) === '#' || (r.length === 1 && first === '')) { return; }
      if (!head) { head = []; each(r, function (h) { head.push(h.replace(/^\s+|\s+$/g, '').toLowerCase()); }); return; }
      var o = {};
      each(head, function (h, k) { o[h] = (r[k] || '').replace(/^\s+|\s+$/g, ''); });
      out.push(o);
    });
    return out;
  }
  H.parseCSV = parseCSV;

  function normCat(c) { c = String(c || '').toLowerCase(); if (c.indexOf('arm') >= 0) { return 'arm'; } if (c.indexOf('arena') >= 0) { return 'arena'; } return 'stage'; }
  function teamsFromCSV(rows) {
    var out = [];
    each(rows, function (r, i) { if (r.name) { out.push({ id: 'f' + i, name: r.name, country: r.country || '', cat: normCat(r.category), say: r.say_as || '' }); } });
    return out;
  }
  function scheduleFromCSV(rows) {
    var out = [];
    each(rows, function (r, i) {
      var day = String(r.day || '').toLowerCase().indexOf('sun') === 0 ? 'sun' : (String(r.day || '').toLowerCase().indexOf('sat') === 0 ? 'sat' : '');
      if (!day || !/^\d{1,2}:\d{2}$/.test(r.time || '') || !r.title) { return; }
      out.push({ id: 'f' + i, day: day, time: r.time.length === 4 ? '0' + r.time : r.time, mins: parseInt(r.minutes, 10) || 15, title: r.title,
        cat: normCat(r.category), game: r.game || '', a: r.side_a || '', b: r.side_b || '', done: /^(y|yes|1|true|done)$/i.test(r.done || '') });
    });
    return out;
  }

  /* ---------- time and the programme ---------- */
  function startOf(item) {
    var p = item.time.split(':');
    return EVENT_UTC[item.day] + (parseInt(p[0], 10) * 60 + parseInt(p[1], 10)) * 60000 - MALTA_OFFSET;
  }
  function sortedSchedule() {
    var s = H.schedule.slice(0);
    s.sort(function (a, b) { return startOf(a) - startOf(b); });
    return s;
  }
  // Both arenas play at the same time, so "now" can be more than one item: all of them are returned in .all
  function nowNext(t) {
    var all = [], nxt = null;
    each(sortedSchedule(), function (it) {
      var s = startOf(it), e = s + (it.mins || 15) * 60000;
      if (it.done) { return; }
      if (s <= t && t < e) { all.push(it); }
      if (!nxt && s > t) { nxt = it; }
    });
    return { now: all[0] || null, all: all, next: nxt };
  }
  function isNow(nn, it) { for (var i = 0; i < nn.all.length; i++) { if (nn.all[i].id === it.id) { return true; } } return false; }
  H.nowNext = nowNext;
  function teamsOf(cat) {
    var out = [];
    each(H.teams, function (t) { if (t.cat === cat) { out.push(t); } });
    out.sort(function (a, b) { var x = a.name.toLowerCase(), y = b.name.toLowerCase(); return x < y ? -1 : (x > y ? 1 : 0); });
    return out;
  }
  function plural(n, one, many) { return n + ' ' + (n === 1 ? one : many); }
  function sideText(it) {
    if (!it.a && !it.b) { return ''; }
    if (it.cat === 'arena') { return (it.a ? 'Red: ' + it.a : 'Red corner') + '  vs  ' + (it.b ? 'Blue: ' + it.b : 'Blue corner'); }
    return [it.a, it.b].filter(function (x) { return !!x; }).join('  ,  ');
  }
  function gameTitle(id) {
    var g = null;
    if (H.content) { each(H.content.games, function (x) { if (x.id === id) { g = x; } }); }
    return g ? g.title : '';
  }

  /* ---------- header ---------- */
  function renderHeader() {
    var st = $('status');
    if (!H.robot) { st.className = 'chip'; st.textContent = 'Preview'; }
    else if (!H.linked) { st.className = 'chip warn'; st.textContent = 'Waiting for Pepper'; }
    else if (H.voice === false) { st.className = 'chip warn'; st.textContent = 'Voice not ready'; }
    else { st.className = 'chip ok'; st.textContent = 'Pepper connected'; }
    $('speaking').hidden = !H.speaking;
    $('stopTalk').hidden = !H.speaking;
    $('clock').textContent = maltaClock(now());
  }

  /* ---------- views ---------- */
  function go(view, arg) {
    if (view === 'games' && arg) { H.cat = arg; }
    if (view === 'game') { H.game = arg; }
    if (view === 'map') { H.mapSel = arg || ''; if (arg) { H.mapMode = 'plan'; } }   // only the plan can light an area up
    if (H.view === 'game' && view !== 'game') { stopVideo(); }
    if (H.view === 'quiz' && view !== 'quiz') { H.quiz = null; }
    if (view === 'staff' && !H.staffToken) { view = 'home'; }
    if (view === 'intro' && !H.intro) { view = 'home'; }
    if (H.view === 'home' && view !== 'home') { pauseReel(); }
    if (H.view === 'intro' && view !== 'intro') { try { $('ivid').pause(); } catch (e) { /* ignore */ } }
    H.view = view;
    $('app').className = view === 'intro' ? 'introing' : '';
    each(d.querySelectorAll('.view'), function (v) { v.className = 'view' + (v.id === 'v-' + view ? ' on' : ''); });
    each(d.querySelectorAll('#nav button'), function (b) {
      var g = b.getAttribute('data-go');
      b.className = (g === view || (view === 'game' && g === 'games')) ? 'on' : '';
    });
    render();
    if (view === 'help' && arg === 'volunteer') { callVolunteer(); }
  }
  H.go = go;

  function render() {
    renderHeader();
    if (!H.content) { return; }
    if (H.view === 'home') { renderHome(); playReel(); }
    if (H.view === 'intro') { renderIntro(); }
    if (H.view === 'games') { renderGames(); }
    if (H.view === 'game') { renderGame(); }
    if (H.view === 'teams') { renderTeams(); }
    if (H.view === 'schedule') { renderSchedule(); }
    if (H.view === 'scores') { renderScores(); }
    if (H.view === 'quiz') { renderQuiz(); }
    if (H.view === 'help') { renderHelp(); }
    if (H.view === 'map') { renderMap(); }
    if (H.view === 'staff') { renderStaff(); }
  }

  function renderHome() {
    var t = now(), ev = H.content.event, open = Date.parse(ev.opening), end = Date.parse(ev.awards) + 60 * 60000;
    var nn = nowNext(t);
    var stats = clear($('stats'));
    var nA = teamsOf('arena').length, nM = teamsOf('arm').length;
    each(ev.stats, function (s) {
      var v = (s.label === 'Teams' && H.teams.length) ? String(H.teams.length) : s.value;
      var b = el('div', 'stat'); b.appendChild(el('b', null, v)); b.appendChild(el('span', null, s.label)); stats.appendChild(b);
    });
    $('tileTeams').textContent = H.teams.length ? nA + ' Arena \u00b7 ' + nM + ' Robot Arm' : 'Who is competing';
    if (t < open) {
      $('countBox').hidden = false; $('liveBox').hidden = true;
      $('countLbl').textContent = 'The championships start in';
      var left = Math.max(0, open - t), row = clear($('countRow'));
      var parts = [[Math.floor(left / 86400000), 'days'], [Math.floor(left / 3600000) % 24, 'hours'], [Math.floor(left / 60000) % 60, 'minutes']];
      each(parts, function (p) { var c = el('div', 'cnum'); c.appendChild(el('b', null, p[0])); c.appendChild(el('span', null, p[1])); row.appendChild(c); });
    } else if (t < end) {
      $('countBox').hidden = true; $('liveBox').hidden = false;
      fillLive($('liveNow'), 'NOW', nn.now, 'Between matches. Look around the STEM area!');
      if (nn.all.length > 1) { fillLive($('liveNext'), 'NOW', nn.all[1], ''); }      // both arenas at once
      else { fillLive($('liveNext'), 'NEXT', nn.next, 'More soon. Check the schedule.'); }
    } else {
      $('countBox').hidden = false; $('liveBox').hidden = true;
      $('countLbl').textContent = 'Thank you for coming to the IEEE Robot Championships 2026!';
      clear($('countRow'));
    }
  }
  /* the reel: every game clip in turn, muted, with its name */
  function reelGames() { return H.content ? H.content.games : []; }
  function playReel() {
    var v = $('reel'), list = reelGames();
    if (!list.length) { return; }
    var g = list[H.reelI % list.length], src = 'clips/' + g.clip + '.mp4';
    $('reelKind').textContent = g.cat === 'arm' ? 'Robot Arm AI' : 'Arena';
    $('reelTitle').textContent = g.title;
    if (v.getAttribute('data-src') !== src) { v.setAttribute('data-src', src); v.poster = 'clips/' + g.clip + '.jpg'; v.src = src; }
    try { var p = v.play(); if (p && p.then) { p.then(null, function () { /* autoplay refused: the poster stays */ }); } } catch (e) { /* ignore */ }
  }
  function pauseReel() { try { $('reel').pause(); } catch (e) { /* ignore */ } }
  function nextReel() { H.reelI += 1; if (H.view === 'home') { playReel(); } }
  H.nextReel = nextReel;

  /* Pepper's intro: the robot sends the scene; without a robot the page plays it by itself, silently */
  function renderIntro() {
    var sc = H.intro; if (!sc) { return; }
    $('introHead').textContent = sc.head || '';
    $('introSub').textContent = sc.kind === 'next' ? 'Programme' : (sc.sub || '');
    var dots = clear($('introDots')), i;
    for (i = 0; i < sc.n; i += 1) { dots.appendChild(el('span', i === sc.i ? 'on' : (i < sc.i ? 'past' : null))); }
    var v = $('ivid'), big = clear($('introBig'));
    if (sc.clip) {
      big.style.display = 'none'; v.style.display = 'block';
      var src = 'clips/' + sc.clip + '.mp4';
      if (v.getAttribute('data-src') !== src) { v.setAttribute('data-src', src); v.poster = 'clips/' + sc.clip + '.jpg'; v.src = src; try { var p = v.play(); if (p && p.then) { p.then(null, function () {}); } } catch (e) { /* ignore */ } }
      return;
    }
    // Android's tablet browser can draw a video above the page: a scene without a clip hides the video completely
    try { v.pause(); } catch (e) { /* ignore */ }
    v.style.display = 'none';
    big.style.display = '';
    if (sc.kind === 'title') {
      var img = el('img', 'ib-mascot'); img.src = 'brand/mascot.png'; img.alt = ''; img.onerror = function () { img.style.display = 'none'; }; big.appendChild(img);
      var t = el('div', 'ib-title'); t.appendChild(d.createTextNode('IEEE Robot Championships ')); t.appendChild(el('em', null, '2026')); big.appendChild(t);
      big.appendChild(el('div', 'ib-line', 'Montekristo Estate, Malta \u00b7 28 and 29 November'));
    } else if (sc.kind === 'stats') {
      var st = el('div', 'ib-stats');
      each([[String(H.teams.length || '13'), 'teams'], ['7', 'games'], ['2', 'days']], function (x) { var b = el('div'); b.appendChild(el('b', null, x[0])); b.appendChild(el('span', null, x[1])); st.appendChild(b); });
      big.appendChild(st); big.appendChild(el('div', 'ib-line', 'From IEEE Student Branches across Region 8'));
    } else if (sc.kind === 'teams') {
      var cols = el('div', 'ib-cols');
      each([['arena', 'Arena'], ['arm', 'Robot Arm AI']], function (g) {
        var c = el('div', 'ib-col'), list = teamsOf(g[0]);
        c.appendChild(el('h4', null, g[1] + ' \u00b7 ' + list.length));
        each(list, function (tm) { c.appendChild(el('div', null, tm.name)); });
        cols.appendChild(c);
      });
      big.appendChild(cols);
    } else if (sc.kind === 'next') {
      big.appendChild(el('div', 'ib-next', sc.sub || ''));
    } else if (sc.kind === 'map') {
      var pl = $('plan').cloneNode(true);                       // the same plan as the Map screen, without duplicate ids
      pl.removeAttribute('id'); pl.setAttribute('class', 'plan ib-plan');
      each(pl.querySelectorAll('[id]'), function (z) { z.removeAttribute('id'); });
      each(pl.querySelectorAll('.zone'), function (z) { z.setAttribute('class', (z.getAttribute('class') || '').replace(/\s*\bhi\b/g, '')); });
      big.appendChild(pl);
    } else {
      big.appendChild(el('div', 'ib-title', 'Explore the championships'));
      big.appendChild(el('div', 'ib-line', 'Games \u00b7 Teams \u00b7 Schedule \u00b7 Map \u00b7 Robot quiz'));
    }
  }
  var localIntro = null;
  function fillLocal(text) {
    var nA = teamsOf('arena').length, nM = teamsOf('arm').length;
    return String(text || '').replace(/\{n\}/g, H.teams.length).replace(/\{na\}/g, nA).replace(/\{nm\}/g, nM);
  }
  function localScene(i) {
    var list = H.content.intro, sc = list[i], nn = nowNext(now());
    H.intro = { i: i, n: list.length, id: sc.id, kind: sc.kind, clip: sc.clip || '', head: fillLocal(sc.head), sub: sc.kind === 'next' ? (nn.next ? 'Coming up next, at ' + nn.next.time + ': ' + nn.next.title + '.' : 'Enjoy the championships!') : fillLocal(sc.sub) };
  }
  function startIntro() {
    if (send({ cmd: 'intro' })) { return; }
    if (!H.content || !H.content.intro) { return; }
    var i = 0; localScene(0); go('intro');
    if (localIntro) { w.clearInterval(localIntro); }
    localIntro = w.setInterval(function () {
      i += 1;
      if (i >= H.content.intro.length || !H.intro) { stopLocalIntro(); return; }
      localScene(i); renderIntro();
    }, 5000);
  }
  function stopLocalIntro() { if (localIntro) { w.clearInterval(localIntro); localIntro = null; } H.intro = null; go('home'); }
  function skipIntro() { if (localIntro) { stopLocalIntro(); return; } if (!send({ cmd: 'intro-stop' })) { H.intro = null; go('home'); } }

  function fillLive(box, tag, it, empty) {
    clear(box); box.className = 'liveitem' + (tag === 'NEXT' ? ' next' : '');   // NOW is yellow, NEXT is white
    box.appendChild(el('span', 'tag', tag));
    if (!it) { box.appendChild(d.createTextNode(empty)); return; }
    box.appendChild(d.createTextNode(it.time + '  ' + it.title));
    var sub = sideText(it) || ({ arena: 'Arena A', arm: 'Arena B: Robot Arm' })[it.cat] || ''; if (sub) { box.appendChild(el('span', 'sub', sub)); }
  }

  function gamesOf(cat) { var out = []; each(H.content.games, function (g) { if (g.cat === cat) { out.push(g); } }); return out; }
  function renderGames() {
    each(d.querySelectorAll('#catSeg button'), function (b) { b.className = b.getAttribute('data-cat') === H.cat ? 'on' : ''; });
    var c = H.content.categories[H.cat];
    $('catIntro').textContent = c.intro;
    $('catStructure').textContent = c.structure;
    var box = clear($('gameCards')); box.className = 'cards ' + H.cat;
    each(gamesOf(H.cat), function (g) {
      var b = el('button', 'gcard'); b.setAttribute('data-game', g.id);
      var img = el('img'); img.src = 'clips/' + g.clip + '.jpg'; img.alt = ''; b.appendChild(img);
      var tx = el('div', 'gtx'); tx.appendChild(el('div', 'gn', g.n)); tx.appendChild(el('div', 'gt', g.title)); tx.appendChild(el('div', 'gs', g.tagline)); b.appendChild(tx);
      box.appendChild(b);
    });
  }

  function findGame(id) { var g = null; each(H.content.games, function (x) { if (x.id === id) { g = x; } }); return g; }
  function renderGame() {
    var g = findGame(H.game); if (!g) { go('games'); return; }
    $('gnum').textContent = H.content.categories[g.cat].short + ' \u00b7 ' + g.n;
    $('gtitle').textContent = g.title; $('gtag').textContent = g.tagline;
    var f = clear($('gfacts')); each(g.facts, function (x) { f.appendChild(el('li', null, x)); });
    var v = $('gvid'), src = 'clips/' + g.clip + '.mp4';
    if (v.getAttribute('data-src') !== src) {
      v.setAttribute('data-src', src); v.poster = 'clips/' + g.clip + '.jpg'; v.src = src;
      playVideo();
    }
  }
  function playVideo() {
    var v = $('gvid'), p;
    $('gplay').hidden = true;
    try { p = v.play(); } catch (e) { $('gplay').hidden = false; return; }
    if (p && p.then) { p.then(function () { $('gplay').hidden = true; }, function () { $('gplay').hidden = false; }); }
  }
  function stopVideo() { var v = $('gvid'); try { v.pause(); } catch (e) { /* ignore */ } }
  function openGame(id, fromVoice) {
    go('game', id);
    if (!fromVoice) { send({ cmd: 'game', game: id }); }
  }
  function nextGame() {
    var g = findGame(H.game), list = gamesOf(g.cat), i;
    for (i = 0; i < list.length; i += 1) { if (list[i].id === g.id) { break; } }
    openGame(list[(i + 1) % list.length].id, false);
  }

  // Team photos from the organisers: img/teams/<slug>.jpg or .png, named like the official site's files
  // (lower case, accented and other letters dropped, spaces as '-': 'Trodai' with its accent -> troda, 'Thumbi Arm' -> thumbi-arm).
  function teamSlug(name) {
    return String(name).toLowerCase().replace(/[^a-z0-9 \-]/g, '').replace(/[\s\-]+/g, '-').replace(/^-|-$/g, '');
  }
  function teamPhoto(card, name) {
    var im = d.createElement('img'), tries = ['jpg', 'png'], k = 0;
    im.className = 'tph'; im.alt = '';
    im.onerror = function () { k += 1; if (k < tries.length) { im.src = 'img/teams/' + teamSlug(name) + '.' + tries[k]; } else if (im.parentNode) { im.parentNode.className = 'team'; im.parentNode.removeChild(im); } };
    im.src = 'img/teams/' + teamSlug(name) + '.' + tries[0];
    card.className = 'team withph'; card.appendChild(im);
  }
  H.teamSlug = teamSlug;

  /* ---------- venue map ---------- */
  // The drawn plan follows the official map's layout. When the organisers' map image is in the app (img/venue-map.jpg),
  // an "Official map" button shows it; the drawn plan stays, because it can highlight each area.
  function officialMap() {
    if (H.officialTried || !H.content || !H.content.venue) { return; }
    H.officialTried = true;
    var im = new Image();
    im.onload = function () { H.hasOfficial = true; $('mapimg').src = im.src; if (H.view === 'map') { renderMap(); } };
    im.src = H.content.venue.official_map + '?v=' + (H.content.version || '');
  }
  function renderMap() {
    var v = H.content.venue, plan = $('plan'), sel = null;
    if (!v) { return; }
    officialMap();
    var official = H.hasOfficial && H.mapMode === 'official';
    $('mapOfficialBtn').hidden = !H.hasOfficial; $('mapSeg').style.display = H.hasOfficial ? '' : 'none';   // nothing to switch to without the official image
    each(d.querySelectorAll('#mapSeg button'), function (b) { b.className = b.getAttribute('data-m') === (official ? 'official' : 'plan') ? 'on' : ''; });
    $('mapimg').hidden = !official; plan.style.display = official ? 'none' : 'block';
    $('mapNote').textContent = official ? 'Official venue map from the organisers.' : 'Simplified plan based on the official venue map. Positions are approximate.';
    var hi = {};
    each(v.areas, function (a) {
      if (a.id === H.mapSel) { sel = a; each(a.zones, function (z) { hi[z] = true; }); }
      each(a.zones, function (z) { var g = $(z); if (g) { g.setAttribute('data-place', a.id); } });
    });
    each(plan.querySelectorAll('.zone'), function (g) {      // SVG: setAttribute, not className (old browsers)
      var c = (g.getAttribute('class') || '').replace(/\s*\bhi\b/g, '');
      g.setAttribute('class', hi[g.id] ? c + ' hi' : c);
    });
    plan.setAttribute('class', sel ? 'plan hl' : 'plan');
    var list = clear($('mapList'));
    each(v.areas, function (a) {
      var b = el('button', 'mapbtn' + (a.id === H.mapSel ? ' on' : ''), a.name); b.setAttribute('data-place', a.id); list.appendChild(b);
    });
    var desc = clear($('mapDesc'));
    if (sel) { desc.appendChild(el('b', null, sel.name)); desc.appendChild(d.createTextNode(sel.text)); }
    else { desc.appendChild(el('b', null, 'Find your way')); desc.appendChild(d.createTextNode('Touch a place on the map or in the list, and Pepper will show you where it is.')); }
  }
  H.renderMap = renderMap;

  function renderTeams() {
    var nA = teamsOf('arena').length, nM = teamsOf('arm').length;
    each(d.querySelectorAll('#teamSeg button'), function (b) {
      var f = b.getAttribute('data-f');
      b.className = f === H.teamFilter ? 'on' : '';
      b.textContent = f === 'all' ? 'All teams \u00b7 ' + (nA + nM) : (f === 'arena' ? 'Arena \u00b7 ' + nA : 'Robot Arm AI \u00b7 ' + nM);
    });
    var box = clear($('teamGrid')), shown = 0;
    each([['arena', 'Arena: 4 Games'], ['arm', 'Robot Arm AI Challenge']], function (g) {
      if (H.teamFilter !== 'all' && H.teamFilter !== g[0]) { return; }
      var list = teamsOf(g[0]);
      if (!list.length) { return; }
      var sec = el('div', 'tgroup'), h = el('div', 'tgh', g[1]);
      h.appendChild(el('span', null, plural(list.length, 'team', 'teams'))); sec.appendChild(h);
      var cards = el('div', 'tcards');
      each(list, function (t) {
        var c = el('div', 'team'); teamPhoto(c, t.name); c.appendChild(el('div', 'tn', t.name));
        var row = el('div', 'trow'); row.appendChild(el('span', 'tk ' + t.cat, t.cat === 'arm' ? 'Robot Arm AI' : 'Arena'));
        if (t.country) { row.appendChild(el('span', 'tc', t.country)); }
        c.appendChild(row); cards.appendChild(c); shown += 1;
      });
      sec.appendChild(cards); box.appendChild(sec);
    });
    if (!shown) {
      var e = el('div', 'empty'); e.appendChild(el('b', null, 'The team list is coming soon.'));
      e.appendChild(d.createTextNode('Teams from IEEE Student Branches across Region 8 are taking part. During matches, the Arena teams play from the red corner and the blue corner.'));
      box.appendChild(e);
    }
  }

  function renderSchedule() {
    each(d.querySelectorAll('#daySeg button'), function (b) { b.className = b.getAttribute('data-day') === H.day ? 'on' : ''; });
    var box = clear($('schedList')), t = now(), nn = nowNext(t), any = false;
    each(sortedSchedule(), function (it) {
      if (it.day !== H.day) { return; }
      any = true;
      var cls = 'srow', badge = null;
      if (isNow(nn, it)) { cls += ' now'; badge = 'NOW'; }
      else if (nn.next && nn.next.id === it.id) { cls += ' next'; badge = 'NEXT'; }
      else if (it.done || startOf(it) + (it.mins || 15) * 60000 <= t) { cls += ' done'; }
      var r = el('div', cls); r.appendChild(el('div', 'st', it.time));
      var b = el('div', 'sb'); b.appendChild(el('div', 'sti', it.title));
      var sub = el('div', 'ssub');
      if (it.cat !== 'stage') { sub.appendChild(el('span', 'catk ' + it.cat, it.cat === 'arm' ? 'Robot Arm AI' : 'Arena')); }
      if (it.cat === 'arena' && (it.a || it.b)) {
        sub.appendChild(el('span', 'side red', it.a || 'Red corner')); sub.appendChild(d.createTextNode('  vs  '));
        sub.appendChild(el('span', 'side blue', it.b || 'Blue corner'));
      } else if (sideText(it)) { sub.appendChild(d.createTextNode(sideText(it))); }
      if (sub.firstChild) { b.appendChild(sub); }
      r.appendChild(b);
      if (badge) { r.appendChild(el('span', 'badge', badge)); }
      box.appendChild(r);
    });
    var focus = box.querySelector('.srow.now') || box.querySelector('.srow.next');
    box.scrollTop = focus ? Math.max(0, focus.offsetTop - 8) : 0;
    if (!any) {
      var e = el('div', 'empty'); e.appendChild(el('b', null, 'The match times will appear here.'));
      e.appendChild(d.createTextNode('Saturday: Official Opening Ceremony at 14:00, games from 15:30. Sunday: games from 10:30, Awards Night at 18:00. Ask a volunteer for the latest times.'));
      box.appendChild(e);
    }
  }

  function boardFor(cat) {
    var list = [], has = {};
    each(H.scores, function (x) { if (x.cat === cat) { list.push(x); has[x.team] = true; } });
    list.sort(function (a, b) { return b.points - a.points; });
    each(teamsOf(cat), function (t) { if (!has[t.name]) { list.push({ team: t.name, cat: cat, points: null }); } });
    return list;
  }
  function renderScores() {
    each([['arena', 'boardArena', 'Arena'], ['arm', 'boardArm', 'Robot Arm AI Challenge']], function (p) {
      var ol = clear($(p[1])), list = boardFor(p[0]), n = teamsOf(p[0]).length;
      var h = ol.parentNode.querySelector('h3'); clear(h).appendChild(d.createTextNode(p[2]));
      if (n) { h.appendChild(el('span', null, plural(n, 'team', 'teams'))); }
      if (!list.length) { ol.appendChild(el('div', 'none', 'Scores appear here once the first results are in.')); return; }
      var rank = 0;
      each(list, function (s) {
        var none = s.points === null || s.points === undefined, li = el('li', none ? 'nos' : null);
        if (!none) { rank += 1; }
        li.appendChild(el('span', 'rk', none ? '-' : rank)); li.appendChild(el('span', 'nm', s.team)); li.appendChild(el('span', 'pt', none ? 'No score yet' : s.points));
        ol.appendChild(li);
      });
    });
  }

  /* ---------- quiz ---------- */
  function shuffle(a) { var i, j, t; for (i = a.length - 1; i > 0; i -= 1) { j = Math.floor(Math.random() * (i + 1)); t = a[i]; a[i] = a[j]; a[j] = t; } return a; }
  var BAG_KEY = 'host.quizBag', memBag = null;
  function loadBag() { try { var b = JSON.parse(w.localStorage.getItem(BAG_KEY) || 'null'); if (b && b.order && b.order.length === H.content.quiz.length) { return b; } } catch (e) { /* storage off */ } return memBag; }
  function saveBag(b) { memBag = b; try { w.localStorage.setItem(BAG_KEY, JSON.stringify(b)); } catch (e) { /* storage off: kept in memory */ } }
  function nextFive() {
    var total = H.content.quiz.length, b = loadBag(), last = [], i, idx;
    if (!b || b.pos + 5 > b.order.length) {
      last = b ? b.order.slice(Math.max(0, b.pos - 5), b.pos) : [];
      idx = []; for (i = 0; i < total; i += 1) { idx.push(i); }
      idx = shuffle(idx);
      /* the first round of a new pass never repeats the questions just asked */
      var head = [], tail = [];
      each(idx, function (x) { if (head.length < 5 && last.indexOf(x) < 0) { head.push(x); } else { tail.push(x); } });
      idx = head.concat(tail);
      b = { order: idx, pos: 0, round: b ? b.round : 0 };
    }
    var five = b.order.slice(b.pos, b.pos + 5);
    b.pos += 5; b.round = (b.round || 0) + 1; saveBag(b);
    return { five: five, round: b.round, left: b.order.length - b.pos };
  }
  H.nextFive = nextFive;
  function startQuiz() {
    var r = nextFive();
    H.quiz = { order: r.five, k: 0, score: 0, picked: -1, opts: null, round: r.round };
    askQuestion();
  }
  function askQuestion() {
    var q = H.content.quiz[H.quiz.order[H.quiz.k]];
    H.quiz.opts = shuffle([0, 1, 2]); H.quiz.picked = -1;
    renderQuiz();
    send({ cmd: 'quizq', i: H.quiz.order[H.quiz.k], opts: H.quiz.opts });
  }
  function answer(pos) {
    var Q = H.quiz; if (!Q || Q.picked >= 0 || pos < 0 || pos > 2) { return; }
    var qi = Q.order[Q.k], q = H.content.quiz[qi], right = Q.opts[pos] === q.ok;
    Q.picked = pos; if (right) { Q.score += 1; }
    renderQuiz();
    send({ cmd: 'quiza', i: qi, ok: right });
  }
  H.answer = answer;
  function nextQuestion() {
    var Q = H.quiz; Q.k += 1;
    if (Q.k >= Q.order.length) { Q.done = true; renderQuiz(); send({ cmd: 'quizend', score: Q.score, total: Q.order.length }); return; }
    askQuestion();
  }
  function renderQuiz() {
    var box = clear($('quiz')), Q = H.quiz;
    if (!Q) {
      box.appendChild(el('div', 'qprog', 'Robot quiz'));
      box.appendChild(el('div', 'qq', 'How much do you know about robots? Five questions at a time, from a bank of ' + H.content.quiz.length + '.'));
      var s = el('button', 'pill primary', 'Start the quiz'); s.id = 'quizStart'; box.appendChild(s);
      return;
    }
    if (Q.done) {
      box.appendChild(el('div', 'qprog', 'Your score'));
      box.appendChild(el('div', 'qbig', Q.score + ' of ' + Q.order.length));
      box.appendChild(el('div', 'qwhy', Q.score >= 4 ? 'Brilliant! You are a robot expert.' : (Q.score >= 2 ? 'Well done! Watch a match to learn even more.' : 'Good try! Watch the games and try again.')));
      var a = el('button', 'pill primary', 'Play again'); a.id = 'quizStart'; box.appendChild(a);
      var h = el('button', 'pill ghost', 'Back home'); h.setAttribute('data-go', 'home'); box.appendChild(h);
      return;
    }
    var q = H.content.quiz[Q.order[Q.k]];
    box.appendChild(el('div', 'qprog', 'Question ' + (Q.k + 1) + ' of ' + Q.order.length));
    box.appendChild(el('div', 'qq', q.q));
    each(Q.opts, function (oi, pos) {
      var cls = 'qa';
      if (Q.picked >= 0) { if (oi === q.ok) { cls += ' right'; } else if (pos === Q.picked) { cls += ' wrong'; } }
      var b = el('button', cls, (pos + 1) + '.  ' + q.a[oi]); b.setAttribute('data-ans', pos); box.appendChild(b);
    });
    box.appendChild(el('div', 'qwhy', Q.picked >= 0 ? ((Q.opts[Q.picked] === q.ok ? 'Correct! ' : 'Not quite. ') + q.why) : 'Touch an answer, or say one, two or three.'));
    if (Q.picked >= 0) { var n = el('button', 'pill primary', Q.k + 1 < Q.order.length ? 'Next question' : 'See my score'); n.id = 'quizNext'; box.appendChild(n); }
  }

  /* ---------- help ---------- */
  function renderHelp() {
    var ev = H.content.event, dl = clear($('infoList'));
    each(ev.info, function (x) { if (x.screen === false) { return; } dl.appendChild(el('dt', null, x.q)); dl.appendChild(el('dd', null, x.a)); });   // toilets and food: on the Map
    $('aboutText').textContent = ev.about;
    $('missionText').textContent = 'IEEE: ' + ev.mission;
    var th = clear($('themes')); each(ev.themes, function (x) { th.appendChild(el('li', null, x)); });
    $('travelText').textContent = ev.travel || '';
    $('shuttleText').textContent = ev.shuttle || '';
    var qr = clear($('qrRow'));
    each(ev.qr || [], function (x) { var f = el('div', 'qr'); var im = el('img'); im.src = x.img; im.alt = ''; f.appendChild(im); f.appendChild(el('span', null, x.label)); qr.appendChild(f); });
    $('volDone').hidden = !(H.volunteerAt && now() - H.volunteerAt < 10 * 60000);
  }
  function callVolunteer() {
    if (H.volunteerAt && now() - H.volunteerAt < 60000) { renderHelp(); return; }
    var sent = send({ cmd: 'volunteer' });
    if (sent) { H.volunteerAt = now(); $('volDone').textContent = 'A volunteer has been called. Please wait here with Pepper.'; }
    else { $('volDone').textContent = 'Pepper is not connected. Please find a volunteer at the information desk.'; H.volunteerAt = now(); }
    renderHelp();
  }

  /* ---------- staff mode ---------- */
  var taps = [], pinVal = '';
  function brandTap() {
    var t = (new Date()).getTime();
    taps.push(t); taps = taps.filter(function (x) { return t - x < 3000; });
    if (taps.length >= 5) { taps = []; openPin(); }
  }
  function openPin() {
    pinVal = ''; $('pinMsg').textContent = ''; drawPin(); $('pin').hidden = false;
  }
  function drawPin() {
    var dots = ''; var i; for (i = 0; i < pinVal.length; i += 1) { dots += '\u2022'; } $('pinDots').textContent = dots || ' ';
    var pad2 = clear($('pinPad'));
    each(['1', '2', '3', '4', '5', '6', '7', '8', '9', 'Cancel', '0', 'OK'], function (k) { var b = el('button', null, k); b.setAttribute('data-pin', k); pad2.appendChild(b); });
  }
  function pinKey(k) {
    if (k === 'Cancel') { $('pin').hidden = true; return; }
    if (k === 'OK') {
      if (!send({ cmd: 'staff-login', pin: pinVal })) { $('pinMsg').textContent = 'Staff mode needs Pepper to be connected.'; return; }
      $('pinMsg').textContent = 'Checking...'; return;
    }
    if (pinVal.length < 8) { pinVal += k; } drawPin();
  }
  function staffResult(r) {
    if (r && r.ok && r.token) { H.staffToken = r.token; $('pin').hidden = true; H.staffTab = 'alerts'; go('staff'); }
    else { pinVal = ''; drawPin(); $('pinMsg').textContent = (r && r.wait) ? 'Too many tries. Wait a minute.' : 'Wrong PIN.'; }
  }

  function input(label, id, value, width, type) {
    var l = el('label', null, label), i = el('input'); i.id = id; i.value = value || ''; i.type = type || 'text';
    i.style.width = (width || 220) + 'px'; l.appendChild(i); return l;
  }
  function select(label, id, options, value, width) {
    var l = el('label', null, label), s = el('select'); s.id = id; s.style.width = (width || 200) + 'px';
    each(options, function (o) { var op = el('option', null, o[1]); op.value = o[0]; if (o[0] === value) { op.selected = true; } s.appendChild(op); });
    l.appendChild(s); return l;
  }
  function val(id) { var e = $(id); return e ? String(e.value).replace(/^\s+|\s+$/g, '') : ''; }
  function button(text, cls, attr, v) { var b = el('button', cls || 'pill', text); if (attr) { b.setAttribute(attr, v); } return b; }
  function teamOptions(cat, blank) {
    var o = [['', blank]];
    if (cat === 'stage') { return o; }
    each(cat ? teamsOf(cat) : H.teams, function (t) { o.push([t.name, t.name]); });
    return o;
  }
  d.addEventListener('change', function (ev) {
    if (!ev.target || ev.target.id !== 'sCat') { return; }
    var E = H.staffEdit || {};
    H.staffEdit = { id: E.id || '', day: val('sDay'), time: val('sTime'), mins: val('sMins'), title: val('sTitle'), cat: val('sCat'), game: val('sGame'), a: '', b: '', done: !!E.done };
    renderStaff();
  }, false);

  function renderStaff() {
    each(d.querySelectorAll('#staffSeg button'), function (b) {
      var k = b.getAttribute('data-st'), open = 0;
      if (k === 'alerts') { each(H.alerts, function (a) { if (!a.seen) { open += 1; } }); b.textContent = open ? 'Alerts (' + open + ')' : 'Alerts'; }
      b.className = k === H.staffTab ? 'on' : '';
    });
    var box = clear($('staffBody')), E = H.staffEdit || {}, f, tb, tr;
    if (H.staffTab === 'alerts') {
      if (!H.alerts.length) { box.appendChild(el('p', 'note', 'No alerts. When a visitor touches "Call a volunteer", it appears here and on this screen in red.')); }
      each(H.alerts.slice(0).reverse(), function (a) {
        var r = el('div', 'alertrow' + (a.seen ? ' seen' : ''));
        r.appendChild(el('span', null, maltaClock(a.t) + '  ' + a.text));
        if (!a.seen) { r.appendChild(button('On my way', 'pill primary', 'data-seen', a.id)); }
        box.appendChild(r);
      });
    } else if (H.staffTab === 'teams') {
      f = el('div', 'form');
      f.appendChild(input('Team name', 'tName', E.name, 260));
      f.appendChild(input('Country', 'tCountry', E.country, 180));
      f.appendChild(select('Competition', 'tCat', [['arena', 'Arena'], ['arm', 'Robot Arm AI']], E.cat || 'arena', 180));
      f.appendChild(input('Say it as (optional)', 'tSay', E.say, 220));
      f.appendChild(button(E.id ? 'Save changes' : 'Add team', 'pill primary', 'data-act', 'team-save'));
      if (E.id) { f.appendChild(button('Cancel', 'pill ghost', 'data-act', 'edit-cancel')); }
      box.appendChild(f);
      box.appendChild(el('p', 'note', '"Say it as" is how Pepper should pronounce the name, if it gets it wrong. Names come from data/teams.csv when Pepper starts; changes made here are kept on the robot.'));
      tb = el('table', 'tbl'); tr = el('tr'); each(['Team', 'Country', 'Competition', ''], function (h) { tr.appendChild(el('th', null, h)); }); tb.appendChild(tr);
      each(H.teams, function (t) {
        tr = el('tr'); tr.appendChild(el('td', null, t.name)); tr.appendChild(el('td', null, t.country)); tr.appendChild(el('td', null, t.cat === 'arm' ? 'Robot Arm AI' : 'Arena'));
        var td = el('td'); td.appendChild(button('Edit', null, 'data-edit-team', t.id)); td.appendChild(button('Remove', null, 'data-del-team', t.id)); tr.appendChild(td); tb.appendChild(tr);
      });
      box.appendChild(tb);
    } else if (H.staffTab === 'schedule') {
      f = el('div', 'form');
      f.appendChild(select('Day', 'sDay', [['sat', 'Sat 28'], ['sun', 'Sun 29']], E.day || H.day, 110));
      f.appendChild(input('Time (HH:MM)', 'sTime', E.time, 110));
      f.appendChild(input('Minutes', 'sMins', E.mins || 15, 90, 'number'));
      f.appendChild(input('Title', 'sTitle', E.title, 240));
      f.appendChild(select('Competition', 'sCat', [['arena', 'Arena'], ['arm', 'Robot Arm AI'], ['stage', 'Other']], E.cat || 'arena', 150));
      var gopts = [['', '(none)']]; each(H.content.games, function (g) { gopts.push([g.id, g.title]); });
      f.appendChild(select('Game', 'sGame', gopts, E.game || '', 190));
      var sc = E.cat || 'arena';
      f.appendChild(select(sc === 'arm' ? 'Team A' : 'Red corner', 'sA', teamOptions(sc, '(none)'), E.a || '', 210));
      f.appendChild(select(sc === 'arm' ? 'Team B' : 'Blue corner', 'sB', teamOptions(sc, '(none)'), E.b || '', 210));
      f.appendChild(button(E.id ? 'Save changes' : 'Add to schedule', 'pill primary', 'data-act', 'sched-save'));
      if (E.id) { f.appendChild(button('Cancel', 'pill ghost', 'data-act', 'edit-cancel')); }
      box.appendChild(f);
      tb = el('table', 'tbl'); tr = el('tr'); each(['Day', 'Time', 'Title', 'Teams', ''], function (h) { tr.appendChild(el('th', null, h)); }); tb.appendChild(tr);
      each(sortedSchedule(), function (it) {
        tr = el('tr'); tr.appendChild(el('td', null, it.day === 'sat' ? 'Sat' : 'Sun')); tr.appendChild(el('td', null, it.time));
        tr.appendChild(el('td', null, it.title + (it.done ? ' (done)' : ''))); tr.appendChild(el('td', null, sideText(it)));
        var td = el('td'); td.appendChild(button(it.done ? 'Undo done' : 'Done', null, 'data-done', it.id)); td.appendChild(button('Edit', null, 'data-edit-sched', it.id)); td.appendChild(button('Remove', null, 'data-del-sched', it.id));
        tr.appendChild(td); tb.appendChild(tr);
      });
      box.appendChild(tb);
    } else if (H.staffTab === 'scores') {
      f = el('div', 'form');
      var opts = [['', '(choose a team)']]; each(H.teams, function (t) { opts.push([t.id, t.name + (t.cat === 'arm' ? ' (Arm)' : ' (Arena)')]); });
      f.appendChild(select('Team', 'scTeam', opts, E.teamId || '', 320));
      f.appendChild(input('Points', 'scPts', E.points === undefined ? '' : E.points, 120, 'number'));
      f.appendChild(button('Save score', 'pill primary', 'data-act', 'score-save'));
      box.appendChild(f);
      box.appendChild(el('p', 'note', 'Enter the running total for each team. The public screen says these are provisional, and that official results come from the judges.'));
      tb = el('table', 'tbl'); tr = el('tr'); each(['Team', 'Competition', 'Points', ''], function (h) { tr.appendChild(el('th', null, h)); }); tb.appendChild(tr);
      each(H.scores, function (s) {
        tr = el('tr'); tr.appendChild(el('td', null, s.team)); tr.appendChild(el('td', null, s.cat === 'arm' ? 'Robot Arm AI' : 'Arena')); tr.appendChild(el('td', null, s.points));
        var td = el('td'); td.appendChild(button('Remove', null, 'data-del-score', s.id)); tr.appendChild(td); tb.appendChild(tr);
      });
      box.appendChild(tb);
    } else if (H.staffTab === 'announce') {
      f = el('div', 'form'); f.appendChild(input('Pepper says (max 300 characters)', 'aText', '', 820));
      f.appendChild(button('Pepper, say this', 'pill primary', 'data-act', 'announce'));
      box.appendChild(f);
      var quick = ['The opening ceremony starts in 10 minutes. Please take your seats.', 'Please do not touch the robots or step into the arena.', 'The next match starts in 5 minutes.', 'The awards ceremony starts in 10 minutes.', 'Thank you for coming! Please take all your belongings with you.'];
      each(quick, function (q) { var b = button(q, 'pill', 'data-quick', q); b.style.height = 'auto'; b.style.padding = '12px 20px'; b.style.textAlign = 'left'; box.appendChild(b); });
      var ic = el('div', 'form'); ic.appendChild(el('span', null, "Pepper's intro (about 2 minutes). By itself after " + H.introEvery + ' quiet minutes when someone is near: ' + (H.introAuto && H.introEvery > 0 ? 'ON' : 'OFF') + '  '));
      ic.appendChild(button('Start the intro now', 'pill primary', 'data-act', 'intro-start'));
      ic.appendChild(button('Say every team name', 'pill', 'data-act', 'say-teams'));
      ic.appendChild(button(H.introAuto ? 'Stop the automatic intro' : 'Allow the automatic intro', 'pill', 'data-act', 'intro-auto')); box.appendChild(ic);
      var c = el('div', 'form'); c.appendChild(el('span', null, 'Match calls: one call ten minutes before each block of matches, and before the opening and the awards. Now: ' + (H.calls ? 'ON' : 'OFF') + '  '));
      c.appendChild(button(H.calls ? 'Turn off' : 'Turn on', 'pill', 'data-act', 'calls')); box.appendChild(c);
    } else if (H.staffTab === 'system') {
      var lines = ['Version: ' + (H.version || 'unknown'), 'Link: ' + (w.Bridge ? w.Bridge.channel : 'none') + (H.linked ? ', Pepper connected' : ', no link'),
        'Voice: ' + (H.voice === true ? 'ready' : (H.voice === false ? 'NOT READY (stop all behaviours on Pepper, start the app once)' : 'being checked')),
        'Teams: ' + H.teams.length + '. Schedule items: ' + H.schedule.length + '. Scores: ' + H.scores.length + '.'];
      each(lines, function (x) { box.appendChild(el('p', 'note', x)); });
      // Pepper's clock drives the programme, now and next, and the match calls: check it when you set up
      var ck = el('div', 'form clockbox');
      ck.appendChild(el('p', 'clocknow', "Pepper's clock: " + maltaDate(now()) + '  ' + maltaClock(now()) + (H.clockFix ? '  (corrected by ' + H.clockFix + ' min)' : '')));
      var tab = (new Date()).getTime();
      ck.appendChild(button("Use the tablet's time: " + maltaClock(tab), 'pill primary', 'data-act', 'clock-tablet'));
      ck.appendChild(input('Date', 'cDate', maltaDate(now()), 170)); ck.appendChild(input('Time', 'cTime', maltaClock(now()), 110));
      ck.appendChild(button('Set the clock', 'pill', 'data-act', 'clock-set'));
      if (H.clockFix) { ck.appendChild(button('Undo the correction', 'pill ghost', 'data-act', 'clock-reset')); }
      box.appendChild(ck);
      box.appendChild(button('Reload teams.csv and schedule.csv', 'pill', 'data-act', 'reload'));
      box.appendChild(el('p', 'note', 'Reload replaces the teams and the schedule with the files, and keeps scores and alerts. Staff mode closes by itself after 5 minutes without a touch.'));
    }
  }

  function staffAct(a) {
    var E = H.staffEdit || {};
    if (a === 'edit-cancel') { H.staffEdit = null; renderStaff(); return; }
    if (a === 'team-save') {
      var t = { id: E.id || '', name: val('tName'), country: val('tCountry'), cat: val('tCat'), say: val('tSay') };
      if (!t.name) { toast('Type a team name first.'); return; }
      staffSend({ cmd: 'team-save', team: t }); H.staffEdit = null; return;
    }
    if (a === 'sched-save') {
      var it = { id: E.id || '', day: val('sDay'), time: val('sTime'), mins: parseInt(val('sMins'), 10) || 15, title: val('sTitle'), cat: val('sCat'), game: val('sGame'), a: val('sA'), b: val('sB') };
      if (!/^\d{1,2}:\d{2}$/.test(it.time)) { toast('Time must look like 14:30.'); return; }
      if (it.time.length === 4) { it.time = '0' + it.time; }
      if (!it.title) { it.title = gameTitle(it.game) || 'Match'; }
      staffSend({ cmd: 'sched-save', item: it }); H.staffEdit = null; return;
    }
    if (a === 'score-save') {
      var id = val('scTeam'), p = parseFloat(val('scPts'));
      if (!id || isNaN(p)) { toast('Choose a team and type the points.'); return; }
      staffSend({ cmd: 'score-save', teamId: id, points: p }); return;
    }
    if (a === 'announce') { var x = val('aText'); if (x) { staffSend({ cmd: 'announce', text: x.slice(0, 300) }); $('aText').value = ''; } return; }
    if (a === 'calls') { staffSend({ cmd: 'calls', on: !H.calls }); return; }
    if (a === 'intro-start') { staffSend({ cmd: 'intro-start' }); return; }
    if (a === 'say-teams') { staffSend({ cmd: 'say-teams' }); toast('Listen: if a name sounds wrong, set its "Say it as" in the Teams tab.'); return; }
    if (a === 'clock-tablet') { var tt = (new Date()).getTime(); staffSend({ cmd: 'set-clock', date: maltaDate(tt), time: maltaClock(tt) }); toast('Clock set to ' + maltaClock(tt)); return; }
    if (a === 'clock-reset') { staffSend({ cmd: 'set-clock', reset: true }); return; }
    if (a === 'clock-set') {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(val('cDate')) || !/^\d{1,2}:\d{2}$/.test(val('cTime'))) { toast('Date like 2026-11-28, time like 13:45.'); return; }
      staffSend({ cmd: 'set-clock', date: val('cDate'), time: val('cTime') }); toast('Clock set to ' + val('cTime')); return;
    }
    if (a === 'intro-auto') { staffSend({ cmd: 'intro-auto', on: !H.introAuto }); return; }
    if (a === 'reload') { staffSend({ cmd: 'reload' }); }
  }

  /* ---------- toast ---------- */
  var toastTimer = null;
  function toast(text, kind) {
    var t = $('toast'); t.textContent = text; t.className = 'toast' + (kind === 'alert' ? ' alert' : ''); t.hidden = false;
    if (toastTimer) { w.clearTimeout(toastTimer); }
    toastTimer = w.setTimeout(function () { t.hidden = true; }, kind === 'alert' ? 8000 : 4000);
  }
  H.toast = toast;

  /* ---------- touch handling (one listener) ---------- */
  function attr(e, name) { while (e && e !== d) { if (e.getAttribute && e.getAttribute(name) !== null) { return { el: e, v: e.getAttribute(name) }; } e = e.parentNode; } return null; }
  d.addEventListener('click', function (ev) {
    var t = ev.target, a;
    H.lastTouch = (new Date()).getTime();
    if ((a = attr(t, 'data-pin'))) { pinKey(a.v); return; }
    if ((a = attr(t, 'data-go'))) { var g = a.v, arg = a.el.getAttribute('data-arg'); go(g, arg); if (!arg || g !== 'help') { send({ cmd: 'view', view: g, arg: arg || '' }); } return; }
    if ((a = attr(t, 'data-cat'))) { H.cat = a.v; renderGames(); send({ cmd: 'view', view: 'games', arg: a.v }); return; }
    if ((a = attr(t, 'data-game'))) { openGame(a.v, false); return; }
    if ((a = attr(t, 'data-f'))) { H.teamFilter = a.v; renderTeams(); return; }
    if ((a = attr(t, 'data-place'))) { H.mapSel = a.v; H.mapMode = 'plan'; renderMap(); send({ cmd: 'place', place: a.v }); return; }
    if ((a = attr(t, 'data-m'))) { H.mapMode = a.v; renderMap(); return; }
    if ((a = attr(t, 'data-day'))) { H.day = a.v; renderSchedule(); return; }
    if ((a = attr(t, 'data-ans'))) { answer(parseInt(a.v, 10)); return; }
    if ((a = attr(t, 'data-st'))) { H.staffTab = a.v; H.staffEdit = null; renderStaff(); return; }
    if ((a = attr(t, 'data-act'))) { staffAct(a.v); return; }
    if ((a = attr(t, 'data-seen'))) { staffSend({ cmd: 'alert-seen', key: a.v }); return; }
    if ((a = attr(t, 'data-quick'))) { staffSend({ cmd: 'announce', text: a.v }); return; }
    if ((a = attr(t, 'data-edit-team'))) { each(H.teams, function (x) { if (x.id === a.v) { H.staffEdit = { id: x.id, name: x.name, country: x.country, cat: x.cat, say: x.say }; } }); renderStaff(); return; }
    if ((a = attr(t, 'data-del-team'))) { staffSend({ cmd: 'team-del', key: a.v }); return; }
    if ((a = attr(t, 'data-edit-sched'))) { each(H.schedule, function (x) { if (x.id === a.v) { H.staffEdit = JSON.parse(JSON.stringify(x)); } }); renderStaff(); return; }
    if ((a = attr(t, 'data-del-sched'))) { staffSend({ cmd: 'sched-del', key: a.v }); return; }
    if ((a = attr(t, 'data-done'))) { each(H.schedule, function (x) { if (x.id === a.v) { var y = JSON.parse(JSON.stringify(x)); y.done = !x.done; staffSend({ cmd: 'sched-save', item: y }); } }); return; }
    if ((a = attr(t, 'data-del-score'))) { staffSend({ cmd: 'score-del', key: a.v }); return; }
    var id = t.id || (t.parentNode && t.parentNode.id) || '';
    if (id === 'quizStart') { startQuiz(); return; }
    if (id === 'quizNext') { nextQuestion(); return; }
    if (id === 'gexplain') { send({ cmd: 'game', game: H.game, again: true }); return; }
    if (id === 'gnext') { nextGame(); return; }
    if (id === 'gback') { go('games'); return; }
    if (id === 'gplay') { playVideo(); return; }
    if (id === 'volBtn') { callVolunteer(); return; }
    if (id === 'stopTalk') { if (H.intro) { skipIntro(); } else { send({ cmd: 'stop' }); } return; }
    if (id === 'introBtn' || (t.parentNode && t.parentNode.id === 'introBtn')) { startIntro(); return; }
    if (id === 'introSkip') { skipIntro(); return; }
    if (id === 'staffExit') { send({ cmd: 'staff-logout', token: H.staffToken }); H.staffToken = null; go('home'); return; }
    var b = t; while (b && b !== d) { if (b.id === 'brand') { brandTap(); return; } b = b.parentNode; }
  }, false);

  /* ---------- robot -> tablet ---------- */
  var lastSeq = -1;
  w.HostUI = {
    update: function (s) {
      if (!s || typeof s !== 'object') { return; }
      if (typeof s.seq === 'number') { if (s.seq <= lastSeq && s.seq > 0) { return; } lastSeq = s.seq; }
      if (w.Bridge) { w.Bridge.lastUpdate = (new Date()).getTime(); }
      H.robot = true; H.linked = true;
      if (typeof s.now === 'number') { H.clockSkew = s.now - (new Date()).getTime(); }
      if (s.teams) { H.teams = s.teams; } if (s.schedule) { H.schedule = s.schedule; } if (s.scores) { H.scores = s.scores; }
      var before = 0; each(H.alerts, function (a) { if (!a.seen) { before += 1; } });
      if (s.alerts) { H.alerts = s.alerts; }
      var after = 0; each(H.alerts, function (a) { if (!a.seen) { after += 1; } });
      if (after > before && H.staffToken) { toast('Volunteer needed at Pepper.', 'alert'); }
      if (typeof s.calls === 'boolean') { H.calls = s.calls; }
      H.voice = s.voice === true ? true : (s.voice === false ? false : null);
      H.speaking = !!s.speaking; H.version = s.v || H.version;
      if (typeof s.introAuto === 'boolean') { H.introAuto = s.introAuto; } if (typeof s.introEvery === 'number') { H.introEvery = s.introEvery; } if (typeof s.clockFix === 'number') { H.clockFix = s.clockFix; }
      if (s.intro) { if (localIntro) { w.clearInterval(localIntro); localIntro = null; } H.intro = s.intro; if (H.view !== 'intro') { go('intro'); return; } renderIntro(); renderHeader(); return; }
      if (!s.intro && H.intro && !localIntro) { H.intro = null; if (H.view === 'intro') { go('home'); return; } }
      if (H.view === 'game' || H.view === 'quiz') { renderHeader(); } else { render(); }
    },
    go: function (view, arg) { H.lastTouch = (new Date()).getTime(); if (view === 'game') { openGame(arg, true); } else { go(view, arg); } },
    toast: function (text, kind) { toast(text, kind); },
    staff: function (r) { staffResult(r); },
    staffClosed: function () { H.staffToken = null; if (H.view === 'staff') { go('home'); } },
    answer: function (n) { if (H.view === 'quiz' && H.quiz && !H.quiz.done) { if (H.quiz.picked >= 0 && n === 0) { nextQuestion(); } else { answer(n - 1); } } },
    quizStart: function () { go('quiz'); startQuiz(); },
    state: function () { return H; }
  };

  /* ---------- start ---------- */
  function loadLocalData() {
    if (H.robot) { return; }
    getJSON('data/teams.csv', function (t) { if (!H.robot) { H.teams = teamsFromCSV(parseCSV(t)); render(); } });
    getJSON('data/schedule.csv', function (t) { if (!H.robot) { H.schedule = scheduleFromCSV(parseCSV(t)); render(); } });
  }
  H.teamsFromCSV = teamsFromCSV; H.scheduleFromCSV = scheduleFromCSV;
  function tick() {
    var t = (new Date()).getTime();
    if (H.robot && w.Bridge && !w.Bridge.linked()) { H.linked = false; }
    renderHeader();
    if (H.view === 'home') { renderHome(); }
    if (H.view !== 'home' && H.view !== 'staff' && H.view !== 'intro' && H.lastTouch && t - H.lastTouch > IDLE_HOME_MS) { go('home'); }
    if (H.view === 'staff' && t - H.lastTouch > STAFF_IDLE_MS) { send({ cmd: 'staff-logout', token: H.staffToken }); H.staffToken = null; go('home'); }
  }
  getJSON('data/content.json', function (t) {
    H.content = JSON.parse(t);
    $('footRules').textContent = 'Game facts from the ' + H.content.rulebook;
    render();
  }, function () { toast('Could not load the content file.', 'alert'); });
  w.setTimeout(loadLocalData, 2500);
  w.setInterval(tick, 1000);
  H.lastTouch = (new Date()).getTime();
  try { $('reel').addEventListener('ended', nextReel, false); $('reel').addEventListener('error', function () { w.setTimeout(nextReel, 4000); }, false); } catch (e) { /* ignore */ }
  fitScreen(); try { w.addEventListener('resize', fitScreen, false); } catch (e) { /* ignore */ }
  if (w.Bridge) { w.Bridge.onchange = renderHeader; w.Bridge.connect(); }
  render();
})(window, document);
