(() => {
  const templates = [
    { id: '2d_platformer', name: '2D Platformer', params: [
      { name: 'player_speed', type: 'float', default: 5.0 },
      { name: 'jump_height', type: 'float', default: 2.0 },
      { name: 'enemy_count', type: 'int', default: 3 },
    ] },
    { id: '3d_fps', name: '3D FPS', params: [
      { name: 'enemy_count', type: 'int', default: 5 },
    ] },
  ];

  const selContainer = document.getElementById('template-select');
  const form = document.getElementById('params-form');
  const output = document.getElementById('output');

  const select = document.createElement('select');
  templates.forEach(t => {
    const opt = document.createElement('option');
    opt.value = t.id; opt.textContent = t.name; select.appendChild(opt);
  });
  selContainer.appendChild(select);

  function renderParams(t) {
    form.innerHTML = '';
    t.params.forEach(p => {
      const label = document.createElement('label');
      label.textContent = `${p.name} (${p.type})`;
      const input = document.createElement('input');
      input.name = p.name; input.value = p.default;
      form.appendChild(label); form.appendChild(input);
    });
  }

  function getConfig() {
    const chosen = templates.find(t => t.id === select.value);
    const cfg = { template: chosen.id, parameters: {} };
    [...form.elements].forEach(el => { if (el.name) cfg.parameters[el.name] = el.value; });
    return cfg;
  }

  select.addEventListener('change', () => { renderParams(templates.find(t => t.id === select.value)); });
  document.getElementById('preview').addEventListener('click', (e) => {
    e.preventDefault(); output.textContent = JSON.stringify(getConfig(), null, 2);
  });
  document.getElementById('export').addEventListener('click', (e) => {
    e.preventDefault();
    const data = JSON.stringify(getConfig(), null, 2);
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([data], { type: 'application/json' }));
    a.download = 'template_config.json'; a.click();
  });

  renderParams(templates[0]);
})();

