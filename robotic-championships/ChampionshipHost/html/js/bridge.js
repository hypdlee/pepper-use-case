/* Tablet <-> Pepper link (ES5, no library required).
   Robot -> tablet: the Host Controller calls ALTabletService.executeJS("HostUI.update({...})"); with QiSession the
                    ALMemory event "Host/Session" carries the same state (older or repeated states are skipped).
   Tablet -> robot: through QiSession + ALMemory "Host/TabletCmd" (polled by the Host Controller that is running now).
                    Only if that is not connected: ALTabletBinding.raiseEvent(json) (ALTabletService.onJSEvent).
                    Memory first, because copies of the app that were stopped earlier (or older versions) can stay
                    connected to onJSEvent until the robot restarts, and would answer every tap a second time.
                    Each message has an id; the controller ignores repeats.
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
    if (B.mem) {
      try { B.mem.insertData('Host/TabletCmd', s); ok = true; used.push('memory'); } catch (e2) { /* try the other channel */ }
    }
    if (!ok && hasBinding()) {
      try { w.ALTabletBinding.raiseEvent(s); ok = true; used.push('binding'); } catch (e) { /* nothing */ }
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
          m.subscriber('Host/Session').then(function (sub) {
            sub.signal.connect(function (v) { try { w.HostUI.update(JSON.parse(v)); } catch (e) { /* ignore */ } });
          }, function () { /* events optional */ });
          m.getData('Host/State').then(function (v) { try { w.HostUI.update(JSON.parse(v)); } catch (e) { /* ignore */ } }, function () { /* no state yet */ });
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
