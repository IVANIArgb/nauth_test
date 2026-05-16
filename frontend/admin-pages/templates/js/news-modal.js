// Кнопка «Новости» в шапке и модалка (чтение всем, писать только super_admin).
(function () {
  const API_BASE = '/api';
  const btn = document.getElementById('news-open-btn');
  const dot = document.getElementById('news-unread-badge');
  if (!btn) return;

  const role = (document.body && document.body.getAttribute('data-role')) || 'user';
  const isSuper = role === 'super_admin';
  const STORAGE_KEY = 'ls_news_last_seen_id';

  function esc(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  async function fetchJson(url, opts) {
    const r = await fetch(url, opts || {});
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
    return data;
  }

  function openModal(title, contentEl) {
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.45);display:flex;align-items:center;justify-content:center;z-index:9999;padding:16px;';
    const modal = document.createElement('div');
    modal.style.cssText = 'width:min(980px,100%);max-height:90vh;background:#fff;border-radius:14px;box-shadow:0 14px 48px rgba(0,0,0,0.28);display:flex;flex-direction:column;overflow:hidden;';
    const head = document.createElement('div');
    head.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:14px 16px;border-bottom:1px solid #eee;';
    head.innerHTML = `<div style="font-weight:700;">${esc(title || '')}</div>`;
    const closeBtn = document.createElement('button');
    closeBtn.textContent = '✕';
    closeBtn.style.cssText = 'border:none;background:transparent;font-size:18px;cursor:pointer;padding:6px 10px;border-radius:10px;';
    closeBtn.addEventListener('click', () => overlay.remove());
    head.appendChild(closeBtn);
    const body = document.createElement('div');
    body.style.cssText = 'padding:16px;overflow:auto;';
    body.appendChild(contentEl);
    modal.appendChild(head);
    modal.appendChild(body);
    overlay.appendChild(modal);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    document.body.appendChild(overlay);
    return overlay;
  }

  function formatDate(iso) {
    if (!iso) return '';
    try { return new Date(iso).toLocaleString('ru-RU'); } catch (e) { return String(iso); }
  }

  function setLastSeen(id) {
    try { localStorage.setItem(STORAGE_KEY, String(id || 0)); } catch (e) {}
  }
  function getLastSeen() {
    try { return parseInt(localStorage.getItem(STORAGE_KEY) || '0', 10) || 0; } catch (e) { return 0; }
  }

  async function refreshDot() {
    if (!dot) return;
    try {
      const data = await fetchJson(`${API_BASE}/news?limit=1`);
      const events = Array.isArray(data.events) ? data.events : [];
      const latestId = events[0] && events[0].id ? parseInt(events[0].id, 10) : 0;
      const lastSeen = getLastSeen();
      dot.style.display = latestId > lastSeen ? '' : 'none';
    } catch (e) {
      dot.style.display = 'none';
    }
  }

  async function openNewsModal() {
    const container = document.createElement('div');
    container.innerHTML = `
      ${isSuper ? `
        <div style="border:1px solid #eee;border-radius:12px;padding:12px;margin-bottom:12px;background:#fafafa;">
          <div style="font-weight:700;margin-bottom:8px;">Добавить новость (super_admin)</div>
          <div style="display:grid;gap:8px;">
            <input id="news-title" type="text" placeholder="Заголовок" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:10px;">
            <textarea id="news-body" rows="3" placeholder="Текст" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:10px;"></textarea>
            <div style="display:flex;gap:10px;justify-content:flex-end;">
              <button class="refresh-button" id="news-post-btn">Опубликовать</button>
            </div>
            <div id="news-post-msg"></div>
          </div>
        </div>
      ` : ''}
      <div id="news-list">Загрузка...</div>
    `;

    const listEl = container.querySelector('#news-list');
    const overlay = openModal('Новости', container);

    async function loadList() {
      try {
        listEl.textContent = 'Загрузка...';
        const data = await fetchJson(`${API_BASE}/news?limit=100`);
        const events = Array.isArray(data.events) ? data.events : [];
        if (!events.length) {
          listEl.innerHTML = '<div style="color:#666;">Пока нет новостей.</div>';
          return;
        }
        const maxId = events[0] && events[0].id ? parseInt(events[0].id, 10) : 0;
        setLastSeen(maxId);
        if (dot) dot.style.display = 'none';

        listEl.innerHTML = events.map((ev) => {
          const who = ev.author_full_name || ev.author_username || '—';
          const when = formatDate(ev.created_at);
          return `
            <div style="border:1px solid #eee;border-radius:12px;padding:12px;margin:10px 0;background:#fff;">
              <div style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start;">
                <div style="font-weight:700;">${esc(ev.title || '')}</div>
                <div style="color:#888;font-size:12px;white-space:nowrap;">${esc(when)}</div>
              </div>
              <div style="color:#666;font-size:12px;margin-top:4px;">${esc(who)} · ${esc(ev.event_type || '')}</div>
              ${ev.body ? `<div style="margin-top:8px;white-space:pre-wrap;">${esc(ev.body)}</div>` : ''}
            </div>
          `;
        }).join('');
      } catch (e) {
        listEl.innerHTML = `<div style="color:#d32f2f;">${esc(e.message || 'Ошибка загрузки')}</div>`;
      }
    }

    if (isSuper) {
      container.querySelector('#news-post-btn')?.addEventListener('click', async () => {
        const msg = container.querySelector('#news-post-msg');
        try {
          msg.textContent = 'Публикация...';
          const title = (container.querySelector('#news-title').value || '').trim();
          const body = (container.querySelector('#news-body').value || '').trim();
          await fetchJson(`${API_BASE}/news`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, body, event_type: 'manual' })
          });
          msg.innerHTML = '<span style="color:#2e7d32;">Опубликовано</span>';
          container.querySelector('#news-title').value = '';
          container.querySelector('#news-body').value = '';
          await loadList();
        } catch (e) {
          msg.innerHTML = `<span style="color:#d32f2f;">${esc(e.message || 'Ошибка')}</span>`;
        }
      });
    }

    overlay.addEventListener('remove', refreshDot);
    await loadList();
  }

  btn.addEventListener('click', function (e) {
    e.preventDefault();
    openNewsModal();
  });

  refreshDot();
  window.setInterval(refreshDot, 60000);
})();

