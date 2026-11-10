/* Draws Pepper from joint angles (degrees), using the same keyframes as the robot's exercise timelines (ES5).
   Robot frame: x forward, y to Pepper's left, z up. The camera stands in front of Pepper, turned a little,
   so the patient sees the movement the way they see the real robot. */
(function (w) {
  'use strict';
  var D = Math.PI / 180;
  // Pepper standing pose (used for any joint an exercise does not move)
  var REST = { HeadYaw: 0, HeadPitch: -8, HipRoll: 0, HipPitch: -2,
    LShoulderPitch: 88, LShoulderRoll: 7, LElbowYaw: -70, LElbowRoll: -30,
    RShoulderPitch: 88, RShoulderRoll: -7, RElbowYaw: 70, RElbowRoll: 30 };
  var UPPER = 0.18, FORE = 0.21, SHOULDER_Y = 0.15, SHOULDER_Z = 0.40, NECK_Z = 0.50, HEAD_Z = 0.62, HEAD_R = 0.10;

  function sample(keys, frame) {
    if (frame <= keys[0][0]) { return keys[0][1]; }
    for (var i = 1; i < keys.length; i++) {
      if (frame <= keys[i][0]) {
        var a = keys[i - 1], b = keys[i], t = (frame - a[0]) / (b[0] - a[0]);
        t = 0.5 - 0.5 * Math.cos(Math.PI * t);           // smooth like Choregraphe's curves
        return a[1] + (b[1] - a[1]) * t;
      }
    }
    return keys[keys.length - 1][1];
  }
  /* Pose at `seconds` into the timeline. Before a joint's first key the robot moves from where it was (`from`,
     standing by default, or the end of the previous repeat) to that key, as Choregraphe does. */
  function pose(ex, seconds, from) {
    var p = {}, k, frame = seconds * (ex ? ex.fps : 25);
    for (k in REST) { if (REST.hasOwnProperty(k)) { p[k] = REST[k]; } }
    if (ex) {
      for (k in ex.curves) {
        if (ex.curves.hasOwnProperty(k) && p.hasOwnProperty(k)) {
          var keys = ex.curves[k], start = from && from.hasOwnProperty(k) ? from[k] : REST[k];
          if (frame < keys[0][0]) {
            var t = keys[0][0] > 0 ? frame / keys[0][0] : 1;
            p[k] = start + (keys[0][1] - start) * (0.5 - 0.5 * Math.cos(Math.PI * Math.max(0, t)));
          } else {
            p[k] = sample(keys, frame);
          }
        }
      }
    }
    return p;
  }

  function add(a, b) { return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]; }
  function mul(a, s) { return [a[0] * s, a[1] * s, a[2] * s]; }
  function torso(v, p) {                                   // lean: HipRoll to Pepper's left (+), HipPitch forward (+)
    var r = p.HipRoll * D, q = p.HipPitch * D;
    var y = v[1] * Math.cos(r) + v[2] * Math.sin(r), z = -v[1] * Math.sin(r) + v[2] * Math.cos(r), x = v[0];
    return [x * Math.cos(q) + z * Math.sin(q), y, -x * Math.sin(q) + z * Math.cos(q)];
  }
  function arm(p, side) {                                  // returns [shoulder, elbow, hand] in robot frame
    var s = side === 'L' ? 1 : -1;
    var pi = p[side + 'ShoulderPitch'] * D, ro = p[side + 'ShoulderRoll'] * D;
    var ey = p[side + 'ElbowYaw'] * D, er = Math.abs(p[side + 'ElbowRoll'] * D);
    var a = [Math.cos(ro) * Math.cos(pi), Math.sin(ro), -Math.cos(ro) * Math.sin(pi)];   // upper arm direction
    var b = [-Math.sin(ro) * Math.cos(pi), Math.cos(ro), Math.sin(ro) * Math.sin(pi)];   // towards Pepper's left
    var c = [Math.sin(pi), 0, Math.cos(pi)];
    var inward = mul(b, -s), yaw = s > 0 ? -ey : ey;                                      // bend plane set by ElbowYaw
    var d = add(mul(inward, Math.cos(yaw)), mul(c, Math.sin(yaw)));
    var f = add(mul(a, Math.cos(er)), mul(d, Math.sin(er)));
    var sh = [0, s * SHOULDER_Y, SHOULDER_Z];
    var el = add(sh, mul(a, UPPER)), ha = add(el, mul(f, FORE));
    return [torso(sh, p), torso(el, p), torso(ha, p)];
  }

  function Figure(canvas) {
    this.c = canvas; this.ctx = canvas.getContext('2d');
    this.yaw = 22 * D; this.tilt = 8 * D;
  }
  Figure.prototype.project = function (v) {
    var W = this.c.width, H = this.c.height, s = H / 1.62;
    var sx = -v[0] * Math.sin(this.yaw) + v[1] * Math.cos(this.yaw);
    var depth = v[0] * Math.cos(this.yaw) + v[1] * Math.sin(this.yaw);
    var sy = v[2] * Math.cos(this.tilt) - depth * Math.sin(this.tilt);
    return { x: W / 2 + sx * s, y: H * 0.535 - sy * s, d: depth };
  };
  Figure.prototype.draw = function (p) {
    var g = this.ctx, W = this.c.width, H = this.c.height, self = this, s = H / 1.62;
    var P = function (v) { return self.project(v); };
    var BODY = '#FFFFFF', EDGE = '#9AAFC0', INK = '#10243A', ACCENT = '#0F766E';
    g.clearRect(0, 0, W, H);
    // floor shadow and base (the base never moves)
    var o = P([0, 0, -0.62]);
    g.save(); g.translate(o.x, o.y); g.scale(1, 0.23); g.fillStyle = 'rgba(16,36,58,0.10)'; g.beginPath(); g.arc(0, 0, 0.30 * s, 0, 2 * Math.PI); g.fill(); g.restore();
    var b1 = P([0, -0.11, 0]), b2 = P([0, 0.11, 0]), b3 = P([0, 0.22, -0.60]), b4 = P([0, -0.22, -0.60]);
    g.fillStyle = BODY; g.strokeStyle = EDGE; g.lineWidth = 3; g.lineJoin = 'round';
    g.beginPath(); g.moveTo(b1.x, b1.y); g.lineTo(b2.x, b2.y); g.lineTo(b3.x, b3.y); g.lineTo(b4.x, b4.y); g.closePath(); g.fill(); g.stroke();
    // arms are drawn back to front around the torso
    var L = arm(p, 'L'), R = arm(p, 'R');
    var armDepth = function (A) { return P(A[1]).d + P(A[2]).d; };
    var drawArm = function (A) {
      var q = [P(A[0]), P(A[1]), P(A[2])];
      g.lineCap = 'round'; g.lineJoin = 'round';
      g.strokeStyle = EDGE; g.lineWidth = 0.075 * s; g.beginPath(); g.moveTo(q[0].x, q[0].y); g.lineTo(q[1].x, q[1].y); g.lineTo(q[2].x, q[2].y); g.stroke();
      g.strokeStyle = BODY; g.lineWidth = 0.075 * s - 6; g.stroke();
      g.fillStyle = BODY; g.strokeStyle = EDGE; g.lineWidth = 3; g.beginPath(); g.arc(q[2].x, q[2].y, 0.035 * s, 0, 2 * Math.PI); g.fill(); g.stroke();
    };
    var torsoPts = [[0, -0.13, 0.02], [0, 0.13, 0.02], [0, 0.17, SHOULDER_Z + 0.03], [0, -0.17, SHOULDER_Z + 0.03]];
    var drawTorso = function () {
      var t = torsoPts.map(function (v) { return P(torso(v, p)); });
      g.fillStyle = BODY; g.strokeStyle = EDGE; g.lineWidth = 3;
      g.beginPath(); g.moveTo(t[0].x, t[0].y); for (var i = 1; i < 4; i++) { g.lineTo(t[i].x, t[i].y); } g.closePath(); g.fill(); g.stroke();
      var tab = [[0.02, -0.07, 0.17], [0.02, 0.07, 0.17], [0.02, 0.07, 0.30], [0.02, -0.07, 0.30]].map(function (v) { return P(torso(v, p)); });
      g.fillStyle = '#DCE6EE'; g.beginPath(); g.moveTo(tab[0].x, tab[0].y); for (var j = 1; j < 4; j++) { g.lineTo(tab[j].x, tab[j].y); } g.closePath(); g.fill();
      // head
      var n1 = P(torso([0, 0, SHOULDER_Z + 0.03], p)), n2 = P(torso([0, 0, NECK_Z + 0.04], p));
      g.strokeStyle = EDGE; g.lineWidth = 0.05 * s; g.lineCap = 'butt'; g.beginPath(); g.moveTo(n1.x, n1.y); g.lineTo(n2.x, n2.y); g.stroke();
      var hc = torso([0, 0, HEAD_Z], p), h = P(hc);
      g.fillStyle = BODY; g.strokeStyle = EDGE; g.lineWidth = 3; g.beginPath(); g.arc(h.x, h.y, HEAD_R * s, 0, 2 * Math.PI); g.fill(); g.stroke();
      var yaw = p.HeadYaw * D, pit = p.HeadPitch * D;
      var eyes = [-1, 1].map(function (side) {
        var a = yaw + side * 0.33, dir = [Math.cos(a) * Math.cos(pit), Math.sin(a) * Math.cos(pit), -Math.sin(pit) + 0.05];
        return P(add(hc, mul(dir, HEAD_R * 0.92)));
      });
      for (var e = 0; e < 2; e++) {
        if (eyes[e].d > P(hc).d - 0.02) { g.fillStyle = ACCENT; g.beginPath(); g.arc(eyes[e].x, eyes[e].y, 0.018 * s, 0, 2 * Math.PI); g.fill(); }
      }
      var m = P(add(hc, mul([Math.cos(yaw) * Math.cos(pit), Math.sin(yaw) * Math.cos(pit), -Math.sin(pit) - 0.42], HEAD_R * 0.9)));
      if (m.d > P(hc).d - 0.02) { g.fillStyle = INK; g.beginPath(); g.arc(m.x, m.y, 0.006 * s, 0, 2 * Math.PI); g.fill(); }
    };
    var torsoDepth = P(torso([0, 0, SHOULDER_Z], p)).d * 2;
    var arms = [L, R].sort(function (A, B) { return armDepth(A) - armDepth(B); });
    for (var i = 0; i < 2; i++) { if (armDepth(arms[i]) < torsoDepth) { drawArm(arms[i]); } }
    drawTorso();
    for (var k = 0; k < 2; k++) { if (armDepth(arms[k]) >= torsoDepth) { drawArm(arms[k]); } }
  };

  /* Plays one exercise: start(n, offset) plays its motion once; start(n, offset, total) repeats it for `total`
     seconds the way the robot does (a repeat only starts if more than MIN_REPEAT seconds are left), then stands. */
  var MIN_REPEAT = 4;
  function Player(canvas) { this.fig = new Figure(canvas); this.ex = null; this.t0 = 0; this.timer = null; this.tw = null; this.total = 0; this.cur = pose(null, 0); }
  Player.prototype.find = function (n) {
    var all = w.EXERCISE_MOTION || [];
    for (var i = 0; i < all.length; i++) { if (all[i].n === n) { return all[i]; } }
    return null;
  };
  Player.prototype.start = function (n, offsetSeconds, total) {
    var self = this;
    this.ex = this.find(n); this.tw = null; this.total = total || 0;
    this.t0 = (new Date()).getTime() - (offsetSeconds || 0) * 1000;
    if (this.timer) { w.clearInterval(this.timer); }
    this.tick();
    this.timer = w.setInterval(function () { self.tick(); }, 40);
  };
  /* the pose `t` seconds after the start, with repeats */
  Player.prototype.at = function (t) {
    var ex = this.ex, dur = ex ? Math.max(0.5, ex.duration) : 1;
    if (!ex || !this.total) { return pose(ex, t); }
    if (t >= this.total) { return pose(null, 0); }
    var k = Math.floor(t / dur), endPose = pose(ex, dur);
    if (k > 0 && this.total - k * dur <= MIN_REPEAT) { return endPose; }       /* too little time left: hold */
    return pose(ex, t - k * dur, k > 0 ? endPose : null);
  };
  Player.prototype.elapsed = function () { return ((new Date()).getTime() - this.t0) / 1000; };
  /* Live mode: move the given joints from where they are now to target angles over a few seconds
     (used for guided breathing, where the robot announces each phase as it starts). */
  Player.prototype.tweenTo = function (targets, seconds) {
    var self = this;
    this.ex = null;
    this.tw = { from: this.cur, to: targets, t0: (new Date()).getTime(), dur: Math.max(0.1, seconds) };
    if (this.timer) { w.clearInterval(this.timer); }
    this.tick();
    this.timer = w.setInterval(function () { self.tick(); }, 40);
  };
  Player.prototype.tick = function () {
    var t = this.elapsed();
    if (this.tw) {
      var k = Math.min(1, ((new Date()).getTime() - this.tw.t0) / 1000 / this.tw.dur), e = 0.5 - 0.5 * Math.cos(Math.PI * k), p = {}, j;
      for (j in this.tw.from) { if (this.tw.from.hasOwnProperty(j)) { p[j] = this.tw.from[j]; } }
      for (j in this.tw.to) { if (this.tw.to.hasOwnProperty(j)) { p[j] = this.tw.from[j] + (this.tw.to[j] - this.tw.from[j]) * e; } }
      this.cur = p; this.fig.draw(p);
      if (this.ontick) { this.ontick(k, 1); }
      if (k >= 1 && this.timer) { w.clearInterval(this.timer); this.timer = null; }
      return;
    }
    this.cur = this.at(t);
    this.fig.draw(this.cur);
    var span = this.total || (this.ex ? this.ex.duration : 0);
    if (this.ontick) { this.ontick(t, span); }
    if (this.ex && t > span + 1 && this.timer) { w.clearInterval(this.timer); this.timer = null; }
  };
  Player.prototype.stop = function () {
    if (this.timer) { w.clearInterval(this.timer); this.timer = null; }
    this.ex = null; this.tw = null; this.cur = pose(null, 0); this.fig.draw(this.cur);
  };
  w.PepperFigure = { Figure: Figure, Player: Player, pose: pose };
})(window);
