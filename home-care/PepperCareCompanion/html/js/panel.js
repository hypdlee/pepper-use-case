/* Tablet UI (ES5). Patient screen: greeting, six activities, Help, Stop; exercise and breathing views.
   Staff view: session details, queue, reminders, history. Every button sends one short command to Pepper. */
(function (w, d) {
  'use strict';
  var $ = function (id) { return d.getElementById(id); };
  var S = { current: null, history: [], queue: [], reminders: [], alerts: [], alertsOpen: 0, item: '', mem: null, quiz: null, snl: null, calling: null, mode: null, lastCmd: '', v: '', seenTotal: 0, heard: '', lag: false, voice: null };
  var pick = null;      // 'music' or 'activities' while a choice list is open
  var pickSeen = 0;     // the number of the last list the controller asked for (Pepper asked "Which one?"), so a closed list stays closed
  var ITEM = { song1: 'My World Is Not My Home', song2: 'Mama Liked the Roses', song3: 'Falling in Love', dance: 'a dance', sax: 'the saxophone' };
  var MODE = { exercise: 'Exercise in progress. Say next to skip, or stop to finish.', breathing: 'Breathing together.',
               music: 'Music is playing. Say stop to end it.', show: 'Pepper is performing. Say stop to end it.',
               quiz: 'Quiz in progress. Say one, two or three, or touch an answer.' };

  function esc(s) { return String(s === undefined || s === null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function clean(raw) {
    var t = String(raw || '').replace(/[^A-Za-z\u00C0-\u024F\s-]/g, ' ').replace(/\s+/g, ' ').replace(/^[\s-]+|[\s-]+$/g, '');
    return t.split(' ').slice(0, 3).join(' ').slice(0, 40);
  }
  function feel() { try { return JSON.parse(w.localStorage.getItem('pepper.feel') || '{}'); } catch (e) { return {}; } }
  function tags(p) {
    var o = '', f = feel()[(p.name || '').toLowerCase()];
    if (p.exercises) { o += '<span class="tag">Exercises: ' + p.exercises + '</span>'; }
    if (p.breathing) { o += '<span class="tag">Breathing: ' + p.breathing + '</span>'; }
    if (p.music) { o += '<span class="tag">Music: ' + p.music + '</span>'; }
    if (p.performances) { o += '<span class="tag">Shows: ' + p.performances + '</span>'; }
    if (p.quizzes) { o += '<span class="tag">Quiz: ' + p.quizzes + (p.quizLast ? ' (last ' + esc(p.quizLast) + ')' : '') + '</span>'; }
    if (p.snlGames) { o += '<span class="tag">Snakes and Ladders: ' + p.snlGames + ' played' + (p.snlWins ? ', won ' + p.snlWins : '') + '</span>'; }
    if (p.med) { o += '<span class="tag' + (p.med === 'taken' ? '' : ' bad') + '">Medicine: ' + esc(p.med) + '</span>'; }
    if (p.memCards) { o += '<span class="tag">Memories: ' + p.memCards + (p.memLikes && p.memLikes.length ? ' (liked: ' + esc(p.memLikes.join(', ')) + ')' : '') + '</span>'; }
    if (p.memAnswers && p.memAnswers.length) { o += '<span class="tag">Said: ' + esc(p.memAnswers.join('; ')) + '</span>'; }
    if (p.moodLow) { o += '<span class="tag bad">Feels unwell</span>'; }
    if (p.alert) { o += '<span class="tag alert">Caregiver alerted</span>'; }
    if (f) { o += '<span class="tag">Feels: ' + esc(f) + '</span>'; }
    return o;
  }
  function when(ts) { var t = new Date(ts * 1000); var h = t.getHours(), m = t.getMinutes(); return (h < 10 ? '0' : '') + h + ':' + (m < 10 ? '0' : '') + m; }

  function render() {
    var c = S.current, i;
    if (!c || exShown > 0 || brShown || (S.mode && S.mode !== 'music') || (pick === 'music' && S.mode === 'music')) { pick = null; }   // a choice list only makes sense while nothing else runs
    // patient screen: one greeting, one line of guidance, then either the name box or the activities
    if (c) {
      $('patient-name').textContent = c.name === 'Unnamed patient' ? 'Hello.' : 'Hello, ' + c.name + '.';
      $('hint').textContent = pick ? 'Tap one, or tell Pepper which.' :
        ((S.mode === 'music' || S.mode === 'show') && ITEM[S.item] ? 'Now playing: ' + ITEM[S.item] + '. Say stop to end it.' :
        (MODE[S.mode] || 'Choose something to do, or just talk to Pepper.'));
    } else if (S.calling) {
      $('patient-name').textContent = S.calling + ', it is your turn.';
      $('hint').textContent = 'Please come closer and answer Pepper.';
    } else {
      $('patient-name').textContent = 'Hello.';
      $('hint').textContent = 'Say hello to Pepper, or type your first name.';
    }
    var ex = exShown > 0 || brShown || !!S.quiz || !!S.mem || !!S.snl;
    $('patient-name').className = 'hello' + (ex ? ' hidden' : '');
    $('hint').className = 'hint' + (ex ? ' hidden' : '');
    $('start-row').className = 'start-row' + (c || S.calling || ex ? ' hidden' : '');
    $('tiles').className = 'tiles' + (c && !ex && !pick ? '' : ' hidden');
    $('picker').className = 'picker' + (c && !ex && pick ? '' : ' hidden');
    $('pick-title').textContent = pick === 'music' ? 'Choose music' : 'Choose an activity';
    renderQuiz();
    renderMem();
    renderSnl();
    $('pick-music').className = 'pick-list' + (pick === 'music' ? '' : ' hidden');
    $('pick-activities').className = 'pick-list' + (pick === 'activities' ? '' : ' hidden');
    // staff view
    $('staff-current').textContent = c ? c.name : (S.calling ? 'Calling ' + S.calling : 'Nobody');
    $('patient-meta').innerHTML = (c ? '<p class="note">Since ' + esc(c.start) + '</p>' + tags(c) : '');
    var q = '';
    for (i = 0; i < S.queue.length; i++) { q += '<li><span>' + esc(S.queue[i]) + '</span><button type="button" class="x" data-name="' + esc(S.queue[i]) + '" aria-label="Remove ' + esc(S.queue[i]) + '">&times;</button></li>'; }
    $('queue').innerHTML = q || '<li class="empty">Nobody waiting.</li>';
    $('queue-count').textContent = S.queue.length ? '(' + S.queue.length + ')' : '';
    var r = '';
    for (i = 0; i < S.reminders.length; i++) { var x = S.reminders[i]; r += '<li' + (x.status === 'due' ? ' class="due"' : '') + '><span>' + when(x.due) + ' ' + esc(x.name) + (x.status === 'due' ? ', now' : '') + '</span></li>'; }
    $('reminders').innerHTML = r || '<li class="empty">No reminders yet.</li>';
    var al = '', open = 0;
    for (i = S.alerts.length - 1; i >= 0; i--) {
      var a = S.alerts[i];
      if (!a.seen) { open += 1; }
      al += '<li' + (a.seen ? '' : ' class="open"') + '><span>' + esc(a.time) + ' ' + esc(a.name) + (a.seen ? ', seen' : ', ' + (a.reason ? esc(a.reason) : 'needs help')) + '</span>' +
        (a.seen ? '' : '<button type="button" class="x seen" data-alert="' + esc(a.id) + '">Seen</button>') + '</li>';
    }
    $('alerts').innerHTML = al || '<li class="empty">No alerts.</li>';
    $('alert-count').textContent = open ? '(' + open + ' open)' : '';
    $('staff-badge').textContent = open;
    $('staff-badge').className = 'badge' + (open ? '' : ' hidden');
    var h = '';
    for (i = S.history.length - 1; i >= 0; i--) { var p = S.history[i]; h += '<li><span class="n">' + esc(p.name) + '</span>' + esc(p.start) + '&ndash;' + esc(p.end || '') + '<br>' + tags(p) + '</li>'; }
    $('history').innerHTML = h || '<li class="empty">Nobody yet.</li>';
    $('seen-count').textContent = S.seenTotal ? '(' + S.seenTotal + ')' : '';
    status();
  }
  // ---- quiz view: the question and three big answers; Pepper reads the same text and listens for one, two or three ----
  var qzLocked = 0;     // question number whose answer was just sent (the buttons wait for the next question)
  var qzLockAt = 0, qzKey = '', qzAcked = '';
  function qzUnlockSoon() {   // a tap that Pepper ignored must not leave the buttons dead: they come back after 2.5 s
    w.setTimeout(function () { if (qzLocked && (new Date()).getTime() - qzLockAt >= 2400) { qzLocked = 0; if (S.quiz) { renderQuiz(); } } }, 2500);
  }
  function feedback(el, fb) {
    if (!fb) { el.className = 'qz-fb hidden'; return; }
    el.className = 'qz-fb ' + (fb.ok ? 'good' : 'soft');
    el.textContent = fb.ok ? 'Correct!' : 'Not quite. The answer was ' + fb.answer + '.';
  }
  function renderQuiz() {
    var q = S.quiz, show = !!q;
    $('quizview').className = 'quiz' + (show ? '' : ' hidden');
    if (!show) { qzLocked = 0; qzKey = ''; return; }
    var qk = q.k + ':' + q.n + ':' + q.phase;
    if (qk !== qzKey) { qzKey = qk; qzLocked = 0; }          // a new question (or a new quiz): the buttons are live again
    var done = q.phase === 'done';
    $('qz-ask').className = done ? 'hidden' : '';
    $('qz-done').className = done ? '' : 'hidden';
    if (done) {
      $('qz-score').textContent = 'You got ' + q.score + ' out of ' + q.total + '.';
      $('qz-msg').textContent = q.score >= q.total ? 'A perfect score. Wonderful!' : q.score >= 3 ? 'Well done!' : 'Thank you for playing.';
      feedback($('qz-fb2'), q.fb);
      if (q.fb) { $('qz-fb2').textContent = 'Last question: ' + $('qz-fb2').textContent; }
      return;
    }
    if (qzLocked && qzLocked !== q.n) { qzLocked = 0; }
    $('qz-step').textContent = 'Question ' + q.n + ' of ' + q.total;
    feedback($('qz-fb'), q.fb);
    $('qz-q').textContent = q.q;
    var btns = $('qz-opts').getElementsByTagName('button');
    for (var i = 0; i < btns.length; i++) {
      btns[i].getElementsByTagName('span')[1].textContent = (q.opts && q.opts[i]) || '';
      btns[i].disabled = !!qzLocked;
    }
    $('qz-bar').style.width = Math.min(100, 100 * (q.n - 1) / q.total) + '%';
    // tell Pepper this question is on screen: it starts reading it only now, so it never talks about a question nobody can see
    var ak = q.k + ':' + q.n;
    if (q.phase === 'ask' && qzAcked !== ak) { qzAcked = ak; w.Bridge.send({ cmd: 'quizShown', k: q.k, q: q.n }); }
  }
  // ---- Relive Malta: a card with a picture. Pepper reads it once this page has said it shows it (cmd memShown) ----
  var memLocked = 0, memLockAt = 0, memKey = '', memAcked = '', memArt = '', memLikedLocal = '', memAnsLocal = '';
  var memPics = [], memPicIdx = 0, memPicId = '', memCredits = null, memTimer = null;
  function memUnlockSoon() {   // a tap that Pepper ignored must not leave the buttons dead: they come back after 2.5 s
    w.setTimeout(function () { if (memLocked && (new Date()).getTime() - memLockAt >= 2400) { memLocked = 0; if (S.mem) { renderMem(); } } }, 2500);
  }
  function renderMem() {
    var m = S.mem, show = !!m;
    $('memview').className = 'mem' + (show ? '' : ' hidden');
    if (!show) { memLocked = 0; memKey = ''; memLikedLocal = ''; memAnsLocal = ''; memPicId = ''; memArt = ''; memStopPics(); return; }
    var end = m.phase === 'end';
    $('mem-show').className = end ? 'hidden' : '';
    $('mem-end').className = end ? '' : 'hidden';
    if (end) { return; }
    var mk = m.k + ':' + m.n;
    if (mk !== memKey) { memKey = mk; memLocked = 0; memLikedLocal = ''; memAnsLocal = ''; }   // a new card: the buttons are live again
    $('mem-step').textContent = 'Memory ' + m.n + ' of ' + m.total;
    $('mem-title').textContent = m.title || '';
    $('mem-line').textContent = m.line || '';
    $('mem-q').textContent = m.q || '';
    var answered = typeof m.ans === 'number' && m.ans >= 0, o = m.opts || [], j;
    $('mem-reply').textContent = answered ? (m.reply || '') : '';
    $('mem-reply').className = 'mem-reply' + (answered && m.reply ? '' : ' hidden');
    for (j = 0; j < 2; j++) {
      var ob = $('b-mem-a' + (j + 1)), chosen = answered ? m.ans === j : memAnsLocal === mk + ':' + j;
      ob.textContent = o[j] || '';
      ob.className = 'mem-opt' + (chosen ? ' on' : '');
      ob.disabled = answered || !!memLocked || !!memAnsLocal;
    }
    if (memArt !== m.id) { memArt = m.id; $('mem-svg').innerHTML = (w.MemArt && w.MemArt[m.id]) || ''; memProbe(m.id); }
    var liked = !!m.liked || memLikedLocal === mk;
    $('b-mem-like').textContent = liked ? 'Liked' : 'I like this';
    $('b-mem-like').className = 'btn like' + (liked ? ' on' : '');
    $('b-mem-like').disabled = liked;
    $('b-mem-back').disabled = m.n <= 1 || !!memLocked;
    $('b-mem-next').disabled = !!memLocked;
    $('b-mem-next').textContent = m.n >= m.total ? 'Finish' : 'Next';
    if (memAcked !== mk) { memAcked = mk; w.Bridge.send({ cmd: 'memShown', k: m.k, n: m.n }); }
  }
  // photos: html/photos/<id>-1.jpg to -3.jpg and credits.js, if they were added (tools/fetch_photos.py). None: the drawing stays.
  function memStopPics() { if (memTimer) { w.clearInterval(memTimer); memTimer = null; } }
  function memCreditText(n) {
    var c = memCredits && memCredits[memPicId + '-' + n + '.jpg'];
    return c ? String(c) : '';
  }
  function memShowPic() {
    var has = memPics.length > 0, i, d = '';
    $('mem-photo').className = 'mem-photo' + (has ? '' : ' hidden');
    if (has) {
      if (memPicIdx >= memPics.length) { memPicIdx = 0; }
      $('mem-photo').style.backgroundImage = "url('photos/" + memPicId + '-' + memPics[memPicIdx] + ".jpg')";
      $('mem-credit').textContent = memCreditText(memPics[memPicIdx]);
      if (memPics.length > 1) { for (i = 0; i < memPics.length; i++) { d += '<span class="mem-dot' + (i === memPicIdx ? ' on' : '') + '"></span>'; } }
    } else { $('mem-credit').textContent = ''; }
    $('mem-dots').innerHTML = d;
  }
  function memNextPic() { if (memPics.length > 1) { memPicIdx = (memPicIdx + 1) % memPics.length; memShowPic(); } }
  function memProbe(id) {
    var n, found = [];
    memStopPics(); memPics = []; memPicIdx = 0; memPicId = id; memShowPic();
    if (memCredits === null) {      // photos/credits.js sets window.MemCredits = { 'festa-1.jpg': 'Photo: ...' }; a script tag works from any page address
      memCredits = {};
      try {
        var sc = w.document.createElement('script');
        sc.onload = function () { memCredits = w.MemCredits || {}; memShowPic(); };
        sc.onerror = function () {};
        sc.src = 'photos/credits.js';
        w.document.getElementsByTagName('head')[0].appendChild(sc);
      } catch (e) { memCredits = {}; }
    }
    function probe(k) {
      var im = new w.Image();
      im.onload = function () {
        if (memPicId !== id) { return; }
        memPics.push(k); memPics.sort(function (a, b) { return a - b; });
        memShowPic();
        if (memPics.length > 1 && !memTimer) { memTimer = w.setInterval(memNextPic, 7000); }
      };
      im.onerror = function () {};
      im.src = 'photos/' + id + '-' + k + '.jpg';
    }
    for (n = 1; n <= 3; n++) { probe(n); }
  }
  function memAnswer(j) {
    var m = S.mem, mk;
    if (!m || m.phase !== 'show' || memLocked || memAnsLocal || (typeof m.ans === 'number' && m.ans >= 0)) { return; }
    mk = m.k + ':' + m.n;
    if (tap('mem:' + mk + ':a' + j, $('b-mem-a' + j), { cmd: 'memAnswer', k: m.k, n: m.n, a: j })) {
      memAnsLocal = mk + ':' + (j - 1); memLockAt = (new Date()).getTime(); renderMem();
      w.setTimeout(function () { if (memAnsLocal && S.mem && !(typeof S.mem.ans === 'number' && S.mem.ans >= 0)) { memAnsLocal = ''; renderMem(); } }, 2500);   // Pepper ignored it: try again
    }
  }
  function memTap(cmd, el) {
    var m = S.mem;
    if (!m || m.phase !== 'show' || memLocked) { return; }
    if (tap('mem:' + m.k + ':' + m.n + ':' + cmd, el, { cmd: cmd, k: m.k, n: m.n })) {
      memLocked = m.n; memLockAt = (new Date()).getTime(); renderMem(); memUnlockSoon();
    }
  }
  // ---- Snakes and Ladders: this page draws the board and the dice; the Care Controller plays the game (fair dice, every rule) ----
  var SNL_LADDERS = { 2: 23, 8: 34, 20: 41, 32: 68, 36: 57, 48: 74, 71: 91, 80: 99 };
  var SNL_SNAKES = { 29: 9, 38: 15, 47: 26, 62: 43, 77: 56, 86: 54, 94: 73, 97: 78 };
  var SNL_PIPS = { 1: [[50, 50]], 2: [[28, 28], [72, 72]], 3: [[28, 28], [50, 50], [72, 72]], 4: [[28, 28], [72, 28], [28, 72], [72, 72]],
                   5: [[28, 28], [72, 28], [50, 50], [28, 72], [72, 72]], 6: [[28, 25], [72, 25], [28, 50], [72, 50], [28, 75], [72, 75]] };
  var snlBuilt = false, snlGameK = 0, snlKey = '', snlAcked = '', snlBusy = false, snlTimers = [], snlLocked = '', snlSaid = '', snlTight = false;
  function r1(v) { return Math.round(v * 10) / 10; }
  function snlXY(n) {    // centre of square n in board units (100 per square); 0 is the start spot below square 1
    if (n < 1) { return { x: 50, y: 1045 }; }
    var row = Math.floor((n - 1) / 10), off = (n - 1) % 10;
    return { x: ((row % 2 === 0 ? off : 9 - off) + 0.5) * 100, y: (9 - row + 0.5) * 100 };
  }
  function snlTokenXY(who, n) {
    var p = snlXY(n);
    return n < 1 ? { x: 60 + who * 90, y: 1040 } : { x: p.x + (who ? 18 : -18), y: p.y + (who ? -8 : 8) };
  }
  function snlLadder(a, b) {
    var p = snlXY(a), q = snlXY(b), dx = q.x - p.x, dy = q.y - p.y, len = Math.sqrt(dx * dx + dy * dy) || 1, ux = dx / len, uy = dy / len, nx = -uy * 13, ny = ux * 13, t, o = '';
    o += '<line x1="' + r1(p.x + nx) + '" y1="' + r1(p.y + ny) + '" x2="' + r1(q.x + nx) + '" y2="' + r1(q.y + ny) + '"/>';
    o += '<line x1="' + r1(p.x - nx) + '" y1="' + r1(p.y - ny) + '" x2="' + r1(q.x - nx) + '" y2="' + r1(q.y - ny) + '"/>';
    for (t = 28; t < len - 12; t += 34) {
      o += '<line x1="' + r1(p.x + ux * t + nx) + '" y1="' + r1(p.y + uy * t + ny) + '" x2="' + r1(p.x + ux * t - nx) + '" y2="' + r1(p.y + uy * t - ny) + '" stroke-width="6"/>';
    }
    return '<g stroke="#1F7A5E" stroke-width="8" stroke-linecap="round" opacity="0.92">' + o + '</g>';
  }
  function snlSnake(a, b) {    // the head is on square a, the tail on square b
    var p = snlXY(a), q = snlXY(b), dx = q.x - p.x, dy = q.y - p.y, len = Math.sqrt(dx * dx + dy * dy) || 1, k = (a % 2 ? 1 : -1) * len * 0.26;
    var cx = (p.x + q.x) / 2 - dy / len * k, cy = (p.y + q.y) / 2 + dx / len * k, ex = dx / len * 9, ey = dy / len * 9;
    return '<path d="M ' + r1(p.x) + ' ' + r1(p.y) + ' Q ' + r1(cx) + ' ' + r1(cy) + ' ' + r1(q.x) + ' ' + r1(q.y) + '" fill="none" stroke="#D9485F" stroke-width="16" stroke-linecap="round" opacity="0.88"/>' +
      '<circle cx="' + r1(q.x) + '" cy="' + r1(q.y) + '" r="8" fill="#D9485F"/>' +
      '<circle cx="' + r1(p.x) + '" cy="' + r1(p.y) + '" r="19" fill="#B0243B"/>' +
      '<circle cx="' + r1(p.x - 7) + '" cy="' + r1(p.y - 6) + '" r="5" fill="#fff"/><circle cx="' + r1(p.x + 7) + '" cy="' + r1(p.y - 6) + '" r="5" fill="#fff"/>' +
      '<circle cx="' + r1(p.x - 7) + '" cy="' + r1(p.y - 6) + '" r="2" fill="#10243A"/><circle cx="' + r1(p.x + 7) + '" cy="' + r1(p.y - 6) + '" r="2" fill="#10243A"/>';
  }
  function snlBoardSvg() {
    var o = '<svg viewBox="0 0 1000 1080" aria-hidden="true">', n, p, a, fill;
    for (n = 1; n <= 100; n++) {
      p = snlXY(n);
      fill = n === 100 ? '#F7D774' : SNL_LADDERS[n] ? '#DDF1EA' : SNL_SNAKES[n] ? '#FBE3E8' : (((Math.floor((n - 1) / 10) + (n - 1) % 10) % 2) ? '#EEF4F7' : '#FFFFFF');
      o += '<rect x="' + (p.x - 50) + '" y="' + (p.y - 50) + '" width="100" height="100" fill="' + fill + '" stroke="#C9D5E0" stroke-width="2"/>';
    }
    for (a in SNL_LADDERS) { if (SNL_LADDERS.hasOwnProperty(a)) { o += snlLadder(+a, SNL_LADDERS[a]); } }
    for (a in SNL_SNAKES) { if (SNL_SNAKES.hasOwnProperty(a)) { o += snlSnake(+a, SNL_SNAKES[a]); } }
    for (n = 1; n <= 100; n++) {      // the numbers last, so no ladder or snake hides one
      p = snlXY(n);
      o += '<text x="' + (p.x - 42) + '" y="' + (p.y - 20) + '" font-size="26" font-weight="bold" fill="#3A4B5D" font-family="Arial, sans-serif">' + n + '</text>';
    }
    o += '<text x="205" y="1052" font-size="30" fill="#4A5B6D" font-family="Arial, sans-serif">Start</text>';
    for (a = 0; a < 2; a++) {
      o += '<g id="snl-tok' + a + '" transform="translate(' + snlTokenXY(a, 0).x + ',' + snlTokenXY(a, 0).y + ')"><circle r="27" fill="' + (a ? '#B54708' : '#0F766E') + '" stroke="#fff" stroke-width="5"/>' +
        '<text y="10" text-anchor="middle" font-size="30" font-weight="bold" fill="#fff" font-family="Arial, sans-serif">' + (a ? 'P' : 'Y') + '</text></g>';
    }
    return o + '</svg>';
  }
  function snlDieSvg(v) {
    var o = '<svg viewBox="0 0 100 100" aria-hidden="true"><rect x="4" y="4" width="92" height="92" rx="18" fill="#fff" stroke="#0F766E" stroke-width="5"/>', i, pips = SNL_PIPS[v] || [];
    for (i = 0; i < pips.length; i++) { o += '<circle cx="' + pips[i][0] + '" cy="' + pips[i][1] + '" r="8.5" fill="#10243A"/>'; }
    return o + '</svg>';
  }
  function snlPlace(who, n) { var el = $('snl-tok' + who), p = snlTokenXY(who, n); $('snl-pos' + who).textContent = String(n); if (el) { el.setAttribute('transform', 'translate(' + r1(p.x) + ',' + r1(p.y) + ')'); } }
  function snlPlaceXY(who, x, y) { var el = $('snl-tok' + who); if (el) { el.setAttribute('transform', 'translate(' + r1(x) + ',' + r1(y) + ')'); } }
  function snlLater(fn, ms) { snlTimers.push(w.setTimeout(fn, ms)); }
  function snlStop() { for (var i = 0; i < snlTimers.length; i++) { w.clearTimeout(snlTimers[i]); } snlTimers = []; snlBusy = false; }
  function snlSay(g) {
    var t = g && g.say ? '“' + g.say + '”' : '';
    $('snl-say').textContent = t;
    snlSaid = g ? g.k + ':' + g.n : '';
  }
  // one move: the die rolls, the piece walks square by square, a ladder or a snake carries it, then a short pause
  function snlMove(mv, done) {
    var who = mv.who, i, steps = mv.kind === 'bounce' ? 0 : Math.max(0, mv.land - mv.frm), t;
    $('snl-banner').textContent = who === 0 ? 'You roll...' : 'Pepper rolls...';
    for (t = 0; t < mv.roll; t += 90) { (function (at) { snlLater(function () { $('snl-die').innerHTML = snlDieSvg(1 + Math.floor(Math.random() * 6)); }, at); })(t); }
    snlLater(function () {
      $('snl-die').innerHTML = snlDieSvg(mv.die);
      $('snl-banner').textContent = (who === 0 ? 'You rolled ' : 'Pepper rolled ') + mv.die + (mv.kind === 'bounce' ? '. Too many!' : '.');
    }, mv.roll);
    for (i = 1; i <= steps; i++) { (function (sq, at) { snlLater(function () { snlPlace(who, sq); }, at); })(mv.frm + i, mv.roll + i * mv.step); }
    var slideAt = mv.roll + steps * mv.step;
    if (mv.kind === 'ladder' || mv.kind === 'snake') {
      var a = snlTokenXY(who, mv.land), b = snlTokenXY(who, mv.to), f, frames = 10;
      snlLater(function () { $('snl-banner').textContent = mv.kind === 'ladder' ? 'A ladder! Up you go.' : 'A snake! Down we go.'; }, slideAt);
      for (f = 1; f <= frames; f++) { (function (fr) { snlLater(function () { snlPlaceXY(who, a.x + (b.x - a.x) * fr / frames, a.y + (b.y - a.y) * fr / frames); }, slideAt + mv.hold * fr / frames); })(f); }
      snlLater(function () { snlPlace(who, mv.to); }, slideAt + mv.hold);
    }
    snlLater(done, slideAt + mv.hold + mv.gap);
  }
  function snlPlay(moves, i) {
    if (i >= moves.length) { snlBusy = false; snlControls(); return; }
    snlMove(moves[i], function () { snlPlay(moves, i + 1); });
  }
  function snlControls() {
    var g = S.snl;
    if (!g) { return; }
    var play = g.phase === 'play', over = g.phase === 'over', key = g.k + ':' + g.n, locked = snlLocked === key, can = play && !snlBusy && !locked;
    if (!snlBusy) { $('snl-pos0').textContent = String(g.pos[0]); $('snl-pos1').textContent = String(g.pos[1]); }
    $('snl-tip').textContent = over ? 'Touch Play again, or say yes. Touch Done, or say stop.' : 'Touch the dice, or say roll. Say stop to end the game.';
    $('b-snl-roll').disabled = !can;
    $('b-snl-skip').disabled = !can || g.rolls === 0;
    $('b-snl-roll').className = 'snl-roll' + (over ? ' hidden' : '');
    $('b-snl-skip').className = 'btn quiet' + (over ? ' hidden' : '');
    $('b-snl-new').className = 'btn primary' + (over && !snlBusy ? '' : ' hidden');
    $('b-snl-done').className = 'btn quiet' + (over && !snlBusy ? '' : ' hidden');
    $('snl-rolltxt').textContent = snlBusy ? 'Playing...' : locked ? 'Rolling...' : 'Roll the dice';
    if (!snlBusy) {
      $('snl-banner').textContent = over ? (g.winner === 0 ? 'You win! Well played!' : 'Pepper wins! Well played!') : 'Your turn.';
      if (g.moves && g.moves.length) { $('snl-die').innerHTML = snlDieSvg(g.moves[g.moves.length - 1].die); }
      if (snlSaid !== key) { snlSay(g); }
    }
  }
  // the board takes the height that is free (it is a square-ish picture), the controls get compact when that is little
  function snlFit() {
    var v = $('snlview'), wrap = $('snl-boardwrap'), stage, avail, wd;
    if (!v || !wrap || !S.snl) { return; }
    if (w.innerWidth <= 760) { wrap.style.width = ''; snlTight = false; v.className = 'snl'; return; }
    stage = v.parentNode;
    avail = stage.getBoundingClientRect().bottom - wrap.getBoundingClientRect().top - 4;
    wd = Math.floor((avail - 4) * 1000 / 1080);
    wd = Math.max(260, Math.min(wd, 600, Math.floor(w.innerWidth * 0.5)));
    wrap.style.width = wd + 'px';
    snlTight = avail < 520;
    v.className = 'snl' + (snlTight ? ' snl-tight' : '');
  }
  function renderSnl() {
    var g = S.snl, show = !!g;
    $('snlview').className = 'snl' + (show && snlTight ? ' snl-tight' : '') + (show ? '' : ' hidden');
    if (!show) { snlStop(); snlKey = ''; snlAcked = ''; snlGameK = 0; snlLocked = ''; return; }
    if (!snlBuilt) { snlBuilt = true; $('snl-board').innerHTML = snlBoardSvg(); $('snl-die').innerHTML = snlDieSvg(5); }
    var key = g.k + ':' + g.n, who, mvs = g.moves || [], start = [g.pos[0], g.pos[1]], same = snlGameK === g.k, i;
    if (key !== snlKey) {
      snlKey = key; snlLocked = '';
      snlStop();
      if (same && mvs.length) {       // the next round of the game that is on screen: walk it
        for (i = 0; i < mvs.length; i++) { start[mvs[i].who] = mvs[i].frm; }
        for (who = 0; who < 2; who++) { snlPlace(who, start[who]); }
        snlBusy = true;
        snlSaid = '';
        $('snl-say').textContent = '';
        snlLater(function () { snlSay(S.snl); }, mvs[0].roll);       // what Pepper says appears when the first dice have settled
        snlPlay(mvs, 0);
      } else {                         // a new game, or a page that was just (re)loaded: show the board as it is
        for (who = 0; who < 2; who++) { snlPlace(who, g.pos[who]); }
        snlSay(g);
        $('snl-die').innerHTML = snlDieSvg(mvs.length ? mvs[mvs.length - 1].die : 5);
      }
      snlGameK = g.k;
    }
    snlControls();
    snlFit();
    $('snl-step').textContent = 'Snakes and Ladders';
    // tell Pepper this round is on screen: it speaks only now, so it never talks about a move nobody can see
    if (snlAcked !== key) { snlAcked = key; w.Bridge.send({ cmd: 'snlShown', k: g.k, n: g.n }); }
  }
  function snlTap(cmd, el) {
    var g = S.snl;
    if (!g || g.phase !== 'play' || snlBusy) { return; }
    var key = g.k + ':' + g.n;
    if (snlLocked === key) { return; }
    if (tap('snl:' + key + ':' + cmd, el, { cmd: cmd, k: g.k, n: g.n })) {
      snlLocked = key; renderSnl();
      w.setTimeout(function () { if (snlLocked === key && S.snl && S.snl.k + ':' + S.snl.n === key) { snlLocked = ''; renderSnl(); } }, 2500);   // Pepper ignored it (too early?): the button comes back
    }
  }
  // ---- exercise view: shown while Pepper does an exercise, in step with the robot (EXERCISE seconds each) ----
  var player = null, exShown = 0, exDone = false, brShown = false, brPlayer = null, total = 0;
  (w.EXERCISE_MOTION || []).forEach(function (e) { if (e.kind !== 'breathing') { total += 1; } });
  function exercise(n, offset, seconds) {
    if (!player && w.PepperFigure) {
      player = new w.PepperFigure.Player($('ex-canvas'));
      player.ontick = function (t, dur) {
        $('ex-bar').style.width = (dur ? Math.min(100, 100 * t / dur) : 0) + '%';
        if (!exDone) { var left = Math.max(0, Math.ceil(dur - t)); $('ex-left').textContent = left + (left === 1 ? ' second left' : ' seconds left'); }
      };
    }
    if (!n || !player) {
      exShown = 0; exDone = false; if (player) { player.stop(); }
      $('exview').className = 'exview hidden'; render(); return;
    }
    var ex = player.find(n);
    if (!ex) { return; }
    exShown = n; exDone = false;
    $('ex-step').textContent = 'Exercise ' + n + ' of ' + total;
    $('ex-title').textContent = ex.title;
    $('ex-text').textContent = ex.text;
    $('ex-img').src = ex.image;
    $('exview').className = 'exview';
    player.start(n, offset || 0, seconds || 40);
    render();
  }
  function exerciseDone(n) {
    if (n !== exShown) { return; }
    exDone = true;
    $('exview').className = 'exview done';
    $('ex-step').textContent = 'Exercise ' + n + ' of ' + total + ': well done!';
    $('ex-left').textContent = n < total ? 'Next one coming.' : 'All done.';
  }
  // ---- breathing view: Pepper announces each phase (in / out), the tablet moves with it ----
  function breathData() { var all = w.EXERCISE_MOTION || []; for (var i = 0; i < all.length; i++) { if (all[i].kind === 'breathing') { return all[i]; } } return null; }
  function breathing(phase, i, n) {
    var b = breathData();
    if (!brPlayer && w.PepperFigure) { brPlayer = new w.PepperFigure.Player($('br-canvas')); }
    if (phase === 'end' || !b || !brPlayer) {
      brShown = false; if (brPlayer) { brPlayer.stop(); }
      $('br-circle').className = 'bcircle'; $('breathview').className = 'exview hidden'; render(); return;
    }
    var inhale = phase === 'in', deg = inhale ? b.in_deg : b.out_deg;
    var first = !brShown;
    if (first) { brPlayer.stop(); }
    brShown = true;
    $('breathview').className = 'exview';
    if (first) { $('br-circle').className = 'bcircle'; void $('br-circle').offsetWidth; }   /* start small so the first breath grows too */
    $('br-step').textContent = 'Breath ' + i + ' of ' + n;
    $('br-title').textContent = inhale ? 'Breathe in' : 'Breathe out';
    $('br-circle').className = 'bcircle ' + (inhale ? 'in' : 'out');
    $('br-bar').style.width = Math.min(100, 100 * ((i - 1) + (inhale ? 0.5 : 1)) / n) + '%';
    brPlayer.tweenTo({ LShoulderPitch: deg, RShoulderPitch: deg }, inhale ? b.in_s : b.out_s);
    render();
  }
  function status() {
    var send = w.Bridge.canSend(), linked = w.Bridge.linked(), st = $('status');
    st.className = 'status ' + (linked ? 'ok' : 'warn');
    st.textContent = linked ? 'Pepper connected' : (send ? 'Waiting for Pepper' : 'Voice only');
    if (S.voice === false) { st.className = 'status warn'; st.textContent = 'Pepper voice not ready'; }
    // buttons are never greyed out because of the link: a tap always gives feedback (see tap())
    var has = !!S.current, ids = ['b-exercise', 'b-music', 'b-chat', 'b-activities', 'b-breathe', 'b-med', 'b-relive', 'b-remind', 'b-r1', 'b-r5', 'b-rset', 'b-end'];
    for (var i = 0; i < ids.length; i++) { $(ids[i]).disabled = !has; }
    $('b-help').disabled = $('b-stop').disabled = $('b-next').disabled = $('b-skip').disabled = false;
    $('b-start').disabled = !clean($('name-input').value);
    $('b-queue').disabled = !clean($('q-input').value);
    $('diag').textContent = 'Care Companion v' + (S.v || '?') + (S.lastCmd ? ', last command: ' + S.lastCmd : '') + (S.heard ? ', last heard: "' + S.heard + '"' : '') +
      (S.lag ? ', Pepper is busy: tracking paused' : '') + (S.voice === false ? ', the voice is not ready: stop all behaviours on Pepper and start the app once' : '') + ', link: ' + w.Bridge.channel + (send ? '' : '. The tablet cannot reach Pepper; voice still works.');
  }
  // every tap: a short flash, the same button twice within 0.8 s counts once, and a clear message if Pepper is unreachable
  var lastTap = {};
  function flash(el) { if (!el) { return; } el.className += ' tapped'; w.setTimeout(function () { el.className = el.className.replace(/ tapped/g, ''); }, 350); }
  function tap(key, el, msg) {
    var now = (new Date()).getTime();
    if (lastTap[key] && now - lastTap[key] < 800) { return true; }
    lastTap[key] = now; flash(el);
    var ok = w.Bridge.send(msg);
    status();
    if (!ok) { banner('Pepper did not get that. Please say it to Pepper.', 'info'); }
    return ok;
  }
  var lastSeq = 0, lastKey = '', lastRun = '';
  function say(t, el) { return tap('say:' + t, el, { cmd: 'say', text: t }); }
  var bannerTimer = null;
  function banner(text, cls) {
    $('alert').className = 'alert show ' + (cls || ''); $('alert-msg').textContent = text;
    if (bannerTimer) { w.clearTimeout(bannerTimer); bannerTimer = null; }
    // notes ("asking for help", "cleared") fade by themselves; a help request itself stays until someone taps OK
    if (cls === 'pending' || cls === 'info') { bannerTimer = w.setTimeout(function () { $('alert').className = 'alert'; snlFit(); }, 8000); }
    snlFit();       // a note takes some height: the game board makes room
  }
  function staff(open) { $('staff').className = 'staff' + (open ? ' open' : ''); }

  w.PepperUI = {
    ping: function () { w.Bridge.lastUpdate = (new Date()).getTime(); status(); },
    update: function (s) {
      if (!s) { return; }
      w.Bridge.lastUpdate = (new Date()).getTime();
      // the same state can arrive twice (executeJS and the ALMemory event): skip older or identical ones
      if (s.run && s.run !== lastRun) { lastRun = s.run; lastSeq = 0; lastKey = ''; qzAcked = ''; memAcked = ''; memAnsLocal = ''; snlAcked = ''; snlGameK = 0; snlLocked = ''; pickSeen = 0; }   // the controller restarted: its numbers start again
      if (s.seq && lastSeq && s.seq <= lastSeq && s.seq > 3) { return; }
      lastSeq = s.seq || 0;
      var key = JSON.stringify([s.current, s.history && s.history.length, s.seenTotal, s.queue, s.reminders, s.calling, s.mode, s.lastCmd, s.v, s.exercise && [s.exercise.n, s.exercise.phase], s.breathing, s.alerts, s.item, s.mem, s.quiz, s.snl, s.pick, s.heard, s.lag, s.voice]);
      if (key === lastKey && !(s.exercise && s.exercise.n !== exShown)) { status(); return; }
      lastKey = key;
      S.current = s.current || null; S.history = s.history || []; S.queue = s.queue || []; S.reminders = s.reminders || [];
      S.alerts = s.alerts || []; S.item = s.item || ''; S.mem = s.mem || null; S.quiz = s.quiz || null; S.snl = s.snl || null;
      // Pepper asked what to play (by voice or after a tile): the same list opens on the tablet by itself; it closes when the dialog moves on
      if (s.pick && s.pick.k !== pickSeen) { pickSeen = s.pick.k; pick = s.pick.which === 'music' ? 'music' : 'activities'; }
      else if (!s.pick && pickSeen) { pickSeen = 0; pick = null; }
      var openNow = 0; for (var k = 0; k < S.alerts.length; k++) { if (!S.alerts[k].seen) { openNow += 1; } }
      if (openNow > S.alertsOpen) { var la = null; for (var m = S.alerts.length - 1; m >= 0; m--) { if (!S.alerts[m].seen) { la = S.alerts[m]; break; } } banner('Help asked: ' + (la && la.name ? la.name : 'a patient') + (la && la.reason ? ' (' + la.reason + ')' : '') + ' at ' + (la && la.time ? la.time : '') + '.', ''); }
      S.alertsOpen = openNow;
      S.heard = s.heard || ''; S.lag = !!s.lag; var voiceWas = S.voice; S.voice = (s.voice === false) ? false : (s.voice === true ? true : null);
      if (S.voice === false && voiceWas !== false) { banner('Pepper cannot speak yet. Stop all behaviours on Pepper and start the app once. The tablet still works.', 'info'); } S.calling = s.calling || null; S.seenTotal = s.seenTotal || S.history.length; S.mode = s.mode || null; S.lastCmd = s.lastCmd || ''; S.v = s.v || '';
      // the robot's state decides which view is open, so a lost executeJS call can never leave a view stuck
      var e = s.exercise;
      if (S.mode === 'exercise' && e && e.n) {
        if (e.n !== exShown) { exercise(e.n, e.elapsed || 0, e.total || 40); }
        if (e.phase === 'done' && !exDone) { exerciseDone(e.n); }
      } else if (exShown) { exercise(0); }
      var b = s.breathing;
      if (S.mode === 'breathing' && b && b.phase && !brShown) { breathing(b.phase, b.i, b.n); }
      else if (S.mode !== 'breathing' && brShown) { breathing('end', 0, 0); }
      try { w.localStorage.setItem('pepper.current', S.current ? S.current.name : ''); } catch (e) { /* ignore */ }
      render();
    },
    alert: function (a) { banner('Help asked: ' + (a && a.name ? a.name : 'a patient') + (a && a.reason ? ' (' + a.reason + ')' : '') + ' at ' + (a && a.time ? a.time : '') + '.', ''); },
    reminder: function (r) { banner('Medicine time for ' + (r && r.name ? r.name : 'a patient') + '.', 'info'); },
    exercise: function (n, offset, seconds) { exercise(n, offset, seconds); },
    exerciseDone: function (n) { exerciseDone(n); },
    breath: function (phase, i, n) { breathing(phase, i, n); }
  };

  function wire() {
    var acts = { 'b-exercise': 'exercise', 'b-chat': 'chat', 'b-breathe': 'breathing', 'b-med': 'medication', 'b-relive': 'relive', 'b-remind': 'reminder', 'b-next': 'next patient' };
    for (var id in acts) { if (acts.hasOwnProperty(id)) { (function (i, t) { $(i).onclick = function () { say(t, $(i)); }; })(id, acts[id]); } }
    // Music: Pepper asks which one (so it can be answered by voice) and the choices are on screen too
    $('b-music').onclick = function () { pick = 'music'; say('music', $('b-music')); render(); };
    // Activities: Pepper asks "Dance, a quiz, or snakes and ladders?" and all three are on screen too
    $('b-activities').onclick = function () { pick = 'activities'; say('activities', $('b-activities')); render(); };
    $('b-pick-back').onclick = function () { pick = null; render(); };
    var qbtns = $('qz-opts').getElementsByTagName('button');
    for (var qi = 0; qi < qbtns.length; qi++) {
      (function (el) {
        el.onclick = function () {
          if (!S.quiz || S.quiz.phase !== 'ask' || qzLocked) { return; }
          var n = parseInt(el.getAttribute('data-n'), 10);
          if (tap('qa:' + S.quiz.k + ':' + S.quiz.n + ':' + n, el, { cmd: 'quizAnswer', n: n, k: S.quiz.k, q: S.quiz.n })) {
            qzLocked = S.quiz.n; qzLockAt = (new Date()).getTime(); renderQuiz(); qzUnlockSoon();
          }
        };
      })(qbtns[qi]);
    }
    $('b-mem-next').onclick = function () { memTap('memNext', $('b-mem-next')); };
    $('b-mem-back').onclick = function () { memTap('memBack', $('b-mem-back')); };
    $('b-mem-a1').onclick = function () { memAnswer(1); };
    $('b-mem-a2').onclick = function () { memAnswer(2); };
    $('mem-art').onclick = function () { memNextPic(); };
    $('b-mem-like').onclick = function () {
      var m = S.mem;
      if (!m || m.phase !== 'show') { return; }
      if (tap('mem:' + m.k + ':' + m.n + ':like', $('b-mem-like'), { cmd: 'memLike', k: m.k, n: m.n })) { memLikedLocal = m.k + ':' + m.n; renderMem(); }
    };
    $('b-snl-roll').onclick = function () { snlTap('snlRoll', $('b-snl-roll')); };
    $('b-snl-skip').onclick = function () { snlTap('snlSkip', $('b-snl-skip')); };
    $('b-snl-new').onclick = function () { var g = S.snl; if (g && g.phase === 'over') { tap('snl:' + g.k + ':new', $('b-snl-new'), { cmd: 'snlNew', k: g.k }); } };
    $('b-snl-done').onclick = function () { S.snl = null; tap('snlclose', $('b-snl-done'), { cmd: 'snlClose' }); render(); };
    $('b-mem-again').onclick = function () { say('relive', $('b-mem-again')); };
    $('b-mem-done').onclick = function () { S.mem = null; tap('memclose', $('b-mem-done'), { cmd: 'memClose' }); render(); };
    $('b-quiz-again').onclick = function () { say('quiz', $('b-quiz-again')); };
    $('b-quiz-done').onclick = function () { S.quiz = null; tap('quizclose', $('b-quiz-done'), { cmd: 'quizClose' }); render(); };
    var picks = d.getElementsByClassName('pick');
    for (var pi = 0; pi < picks.length; pi++) {
      (function (el) { el.onclick = function () { if (say(el.getAttribute('data-say'), el)) { pick = null; render(); } }; })(picks[pi]);
    }
    $('b-stop').onclick = function () { pick = null; breathing('end', 0, 0); exercise(0); say('stop', $('b-stop')); };
    $('b-skip').onclick = function () { say('next', $('b-skip')); };
    $('b-help').onclick = function () {
      if (say('help', $('b-help'))) { banner('Asking the care staff for help.', 'pending'); } else { banner('Pepper is not connected. Please call a carer directly.', ''); }
    };
    $('b-start').onclick = function () { var n = clean($('name-input').value); if (n) { tap('name:' + n, $('b-start'), { cmd: 'name', name: n }); $('name-input').value = ''; status(); } };
    $('b-queue').onclick = function () { var n = clean($('q-input').value); if (n) { tap('queue:' + n, $('b-queue'), { cmd: 'queue', name: n }); $('q-input').value = ''; status(); } };
    $('b-end').onclick = function () { tap('end', $('b-end'), { cmd: 'endSession' }); };
    $('b-r1').onclick = function () { tap('r1', $('b-r1'), { cmd: 'remind', minutes: 1 }); };
    $('b-r5').onclick = function () { tap('r5', $('b-r5'), { cmd: 'remind', minutes: 5 }); };
    $('b-rset').onclick = function () { var v = $('r-time').value; if (/^\d{1,2}:\d{2}$/.test(v)) { tap('at:' + v, $('b-rset'), { cmd: 'remind', at: v }); } };
    $('alerts').onclick = function (e) { var t = e.target; if (t && t.getAttribute && t.getAttribute('data-alert')) { tap('ack:' + t.getAttribute('data-alert'), t, { cmd: 'ack', alert: parseInt(t.getAttribute('data-alert'), 10) }); } };
    $('b-clear').onclick = function () { $('clear-row').className = 'hidden'; $('clear-confirm').className = 'confirm'; };
    $('b-clear-no').onclick = function () { $('clear-row').className = ''; $('clear-confirm').className = 'confirm hidden'; };
    $('b-clear-yes').onclick = function () {
      if (tap('clear', $('b-clear-yes'), { cmd: 'clearData' })) {
        try { w.localStorage.removeItem('pepper.feel'); w.localStorage.removeItem('pepper.current'); } catch (e) { /* ignore */ }
        S.current = null; S.history = []; S.queue = []; S.reminders = []; S.alerts = []; S.alertsOpen = 0; S.seenTotal = 0; render();
        banner('All records cleared.', 'info');
      }
      $('clear-row').className = ''; $('clear-confirm').className = 'confirm hidden';
    };
    $('queue').onclick = function (e) { var t = e.target; if (t && t.getAttribute && t.getAttribute('data-name')) { tap('unq:' + t.getAttribute('data-name'), t, { cmd: 'unqueue', name: t.getAttribute('data-name') }); } };
    $('name-input').oninput = $('q-input').oninput = status;
    $('name-input').onkeydown = function (e) { if ((e.keyCode || e.which) === 13 && !$('b-start').disabled) { $('b-start').onclick(); } };
    $('q-input').onkeydown = function (e) { if ((e.keyCode || e.which) === 13 && !$('b-queue').disabled) { $('b-queue').onclick(); } };
    $('b-staff').onclick = function () { staff(true); };
    $('b-staff-close').onclick = function () { staff(false); };
    $('alert-close').onclick = function () { $('alert').className = 'alert'; snlFit(); };
    w.Bridge.onchange = status;
    render();
    w.setInterval(status, 3000);
    w.Bridge.connect();
    w.Bridge.send({ cmd: 'hello' });
  }
  w.addEventListener('resize', function () { snlFit(); });
  if (d.readyState === 'loading') { d.addEventListener('DOMContentLoaded', wire); } else { wire(); }
})(window, document);
