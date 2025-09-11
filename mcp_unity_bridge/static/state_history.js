(() => {
  const file = document.getElementById('file');
  const timeline = document.getElementById('timeline');
  const details = document.getElementById('details');

  file.addEventListener('change', async () => {
    const f = file.files[0]; if (!f) return;
    const text = await f.text();
    const items = JSON.parse(text);
    renderTimeline(items);
  });

  function renderTimeline(items) {
    timeline.innerHTML = '';
    items.forEach((it, idx) => {
      const a = document.createElement('div'); a.className = 'item'; a.textContent = `${idx} • ${it.meta.action_type || 'action'} @ ${new Date(it.meta.timestamp).toLocaleString()}`;
      const btn = document.createElement('button'); btn.textContent = 'Details';
      btn.addEventListener('click', () => details.textContent = JSON.stringify(it.meta, null, 2));
      const size = document.createElement('div'); size.textContent = `${Math.round((it.meta.size_bytes||0)/1024)} KB`;
      timeline.appendChild(a); timeline.appendChild(size); timeline.appendChild(btn);
    });
  }
})();

