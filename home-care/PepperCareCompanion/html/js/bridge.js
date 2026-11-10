/* Tablet <-> Pepper link (ES5, no library required).
   Robot -> tablet: the Care Controller calls ALTabletService.executeJS("PepperUI.update({...})"); with QiSession the
                    ALMemory event "Pepper/Session" carries the same state (older or repeated states are skipped).
   Tablet -> robot: EVERY tap goes through BOTH channels that are available, so one broken channel can never make the
                    tablet dead: ALTabletBinding.raiseEvent(json) (ALTabletService.onJSEvent) and QiSession + ALMemory
                    "Pepper/TabletCmd" (polled by the controller). Each message has an id; the controller ignores repeats.
                    The Qi connection is retried every 5 s until it works. */
(function (w) {
  'use strict';
  var B = { qi: null, mem: null, lastUpdate: 0, channel: 'none' };
  var n = 0, retry = null, tries = 0;
  function hasBinding() { return !!(w.ALTabletBinding && typeof w.ALTabletBinding.raiseEvent === 'function'); }
  B.canSend = function () { return hasBinding() || !!B.mem; };
  B.send = function (msg) {
    n += 1;
    msg.id = 't' + (new Date()).getTime() + '-' + n;
    var s = JSON.stringify(msg), ok = false, used = [];
    if (hasBinding()) {
      try { w.ALTabletBinding.raiseEvent(s); ok = true; used.push('binding'); } catch (e) { /* try the other channel */ }
    }
    if (B.mem) {
      try { B.mem.insertData('Pepper/TabletCmd', s); ok = true; used.push('memory'); } catch (e2) { /* nothing */ }
    }
    B.channel = used.join(' + ') || 'none';
    return ok;
  };
  B.linked = function () { return (new Date()).getTime() - B.lastUpdate < 12000; };
  function changed() { if (B.onchange) { try { B.onchange(); } catch (e) { /* ignore */ } } }
  function lost() {
    B.qi = null; B.mem = null; changed();
    if (!retry && tries < 120) { tries += 1; retry = w.setTimeout(function () { retry = null; B.connect(); }, 5000); }
  }
  function qiStart() {
    try {
      w.QiSession(function (session) {
        B.qi = session;
        session.service('ALMemory').then(function (m) {
          B.mem = m; changed();
          m.subscriber('Pepper/Session').then(function (sub) {
            sub.signal.connect(function (v) { try { w.PepperUI.update(JSON.parse(v)); } catch (e) { /* ignore */ } });
          }, function () { /* events optional */ });
          m.getData('Pepper/SessionState').then(function (v) { try { w.PepperUI.update(JSON.parse(v)); } catch (e) { /* ignore */ } }, function () { /* no state yet */ });
        }, lost);
        changed();
      }, lost);
    } catch (e) { lost(); }
  }
  B.connect = function () {
    if (typeof w.QiSession === 'function') { qiStart(); return; }
    var s = document.createElement('script');
    s.src = '/libs/qimessaging/2/qimessaging.js';
    s.onload = function () { if (typeof w.QiSession === 'function') { qiStart(); } else { lost(); } };
    s.onerror = lost;
    document.getElementsByTagName('head')[0].appendChild(s);
  };
  w.Bridge = B;
})(window);
