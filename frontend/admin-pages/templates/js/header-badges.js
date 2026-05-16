// Инициализация бейджей в шапке.
(function () {
  const API_BASE = '/api';
  const badge = document.getElementById('questions-unanswered-badge');
  if (!badge) return;

  async function tick() {
    try {
      const resp = await fetch(`${API_BASE}/questions/unanswered-count`);
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`);
      const count = parseInt(data.count, 10) || 0;
      if (count > 0) {
        badge.textContent = String(count);
        badge.style.display = '';
      } else {
        badge.style.display = 'none';
      }
    } catch (e) {
      // тихо: чтобы не спамить консоль на страницах без доступа
      badge.style.display = 'none';
    }
  }

  tick();
  window.setInterval(tick, 30000);
})();

