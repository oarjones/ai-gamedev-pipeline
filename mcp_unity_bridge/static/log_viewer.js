(() => {
  const logEl = document.getElementById('log');
  const levelEl = document.getElementById('level');
  const compEl = document.getElementById('component');
  const kwEl = document.getElementById('keyword');
  const pauseBtn = document.getElementById('pause');
  const clearBtn = document.getElementById('clear');
  let paused = false;

  const loc = window.location;
  const wsProto = loc.protocol === 'https:' ? 'wss' : 'ws';
  const wsUrl = `${wsProto}://${loc.host}/ws/logs`;
  const ws = new WebSocket(wsUrl);

  function fmt(ts) {
    const d = new Date(ts * 1000);
    return d.toISOString();
  }

  function matchesFilters(e) {
    const lvl = levelEl.value;
    const comp = compEl.value.trim();
    const kw = kwEl.value.trim().toLowerCase();
    if (lvl && e.level !== lvl) return false;
    if (comp && e.component.indexOf(comp) === -1) return false;
    if (kw && JSON.stringify(e).toLowerCase().indexOf(kw) === -1) return false;
    return true;
  }

  function render(e) {
    if (!matchesFilters(e)) return;
    const line = `${fmt(e.timestamp)} ${e.component} ${e.level} ${e.module} ${e.message}`;
    const span = document.createElement('div');
    span.className = e.level;
    span.textContent = line;
    logEl.appendChild(span);
    if (!paused) {
      logEl.scrollTop = logEl.scrollHeight;
    }
  }

  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === 'log') {
        render(msg.payload);
      }
    } catch (e) {}
  };

  pauseBtn.onclick = () => { paused = !paused; pauseBtn.textContent = paused ? 'Resume' : 'Pause'; };
  clearBtn.onclick = () => { logEl.textContent = ''; };
})();

