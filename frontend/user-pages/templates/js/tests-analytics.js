// Каталог тестов: две таблицы (уроки + глобальные), сортировка, права админа.
(function () {
  const API_BASE = '/api';
  const lessonTbody = document.getElementById('lesson-tests-body');
  const globalTbody = document.getElementById('global-tests-body');
  const totalEl = document.getElementById('total-tests');
  const completedEl = document.getElementById('completed-tests');
  const fullEl = document.getElementById('full-complete-users') || document.getElementById('new-tests');
  const deptSelect = document.getElementById('department-filter');
  const searchInput = document.getElementById('search-input');
  const sortSelect = document.getElementById('sort-by');
  const refreshBtn = document.getElementById('refresh-btn');

  let isAdmin = false;
  let lastTests = [];

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
    closeBtn.textContent = '\u2715';
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

  function sortTests(arr, key) {
    const a = arr.slice();
    const t = (x) => String(x.title || '');
    if (key === 'title') {
      a.sort((x, y) => t(x).localeCompare(t(y)));
    } else if (key === 'category') {
      const c = (x) => (x.source && x.source.category_title) || '';
      a.sort((x, y) => c(x).localeCompare(c(y)) || t(x).localeCompare(t(y)));
    } else if (key === 'course') {
      const c = (x) => (x.source && x.source.course_title) || '';
      a.sort((x, y) => c(x).localeCompare(c(y)) || t(x).localeCompare(t(y)));
    } else if (key === 'date') {
      const d = (x) => x.updated_at || x.created_at || '';
      a.sort((x, y) => (d(y) || '').localeCompare(d(x) || '') || t(x).localeCompare(t(y)));
    }
    return a;
  }

  function applyFilterAndSort() {
    const q = (searchInput && (searchInput.value || '').trim().toLowerCase()) || '';
    const filtered = q ? lastTests.filter((t) => String(t.title || '').toLowerCase().includes(q)) : lastTests;
    const lessonTests = filtered.filter((t) => t.kind === 'lesson');
    const globalTests = filtered.filter((t) => t.kind === 'global');
    const sortKey = (sortSelect && sortSelect.value) || 'title';
    const sortedLesson = sortTests(lessonTests, sortKey);
    const sortedGlobal = sortTests(globalTests, sortKey);
    if (totalEl) totalEl.textContent = String(filtered.length);
    if (completedEl) completedEl.textContent = '-';
    if (fullEl) fullEl.textContent = '-';
    renderLessonRows(sortedLesson);
    renderGlobalRows(sortedGlobal);
  }

  function renderLessonRows(items) {
    if (!lessonTbody) return;
    if (!items.length) {
      lessonTbody.innerHTML = '<tr><td colspan="5" class="loading">Нет тестов в уроках.</td></tr>';
      return;
    }
    const frag = document.createDocumentFragment();
    for (let i = 0; i < items.length; i++) {
      const t = items[i];
      const tr = document.createElement('tr');
      const title = t.title || 'Тест';
      const s = t.source || {};
      const sourceText = [s.category_title, s.course_title, s.lesson_title].filter(Boolean).join(' / ') || '\u2014';
      const lastResult = t.last_result || null;
      let resultHtml = '\u2014';
      let ballsHtml = '\u2014';
      if (lastResult) {
        resultHtml = lastResult.passed ? '<span style="color:#2e7d32;font-weight:600;">Пройден</span>' : '<span style="color:#c62828;font-weight:600;">Провален</span>';
        ballsHtml = (lastResult.score != null && lastResult.total != null) ? (lastResult.score + ' из ' + lastResult.total) : '\u2014';
      }
      const actions = document.createElement('div');
      actions.className = 'tests-actions';
      const openBtn = document.createElement('button');
      openBtn.className = 'refresh-button';
      openBtn.textContent = 'Открыть';
      openBtn.addEventListener('click', () => openLessonTest(t));
      actions.appendChild(openBtn);
      if (isAdmin) {
        const editBtn = document.createElement('button');
        editBtn.className = 'refresh-button';
        editBtn.textContent = 'Редактировать';
        editBtn.addEventListener('click', () => {
          const lid = s.lesson_id;
          if (lid) window.location.href = '/lessons-content-pg?lesson_id=' + encodeURIComponent(String(lid));
        });
        actions.appendChild(editBtn);
      }
      tr.innerHTML = `<td><strong>${esc(title)}</strong></td><td>${esc(sourceText)}</td><td>${resultHtml}</td><td>${ballsHtml}</td><td></td>`;
      tr.children[4].appendChild(actions);
      frag.appendChild(tr);
    }
    lessonTbody.innerHTML = '';
    lessonTbody.appendChild(frag);
  }

  function renderGlobalRows(items) {
    if (!globalTbody) return;
    const frag = document.createDocumentFragment();
    if (isAdmin) {
      const ctrl = document.createElement('tr');
      ctrl.innerHTML = `
        <td colspan="5">
          <div style="display:flex;gap:10px;justify-content:flex-end;">
            <button class="refresh-button" id="gt-create-btn">+ Создать глобальный тест</button>
          </div>
        </td>
      `;
      ctrl.querySelector('#gt-create-btn')?.addEventListener('click', () => openEditor(null));
      frag.appendChild(ctrl);
    }

    if (!items.length) {
      const tr = document.createElement('tr');
      tr.innerHTML = '<td colspan="5" class="loading">Нет глобальных тестов.</td>';
      frag.appendChild(tr);
      globalTbody.innerHTML = '';
      globalTbody.appendChild(frag);
      return;
    }
    for (let i = 0; i < items.length; i++) {
      const t = items[i];
      const tr = document.createElement('tr');
      const title = t.title || 'Тест';
      const lastResult = t.last_result || null;
      const limitAttempts = !!t.limit_attempts;
      const maxAttempts = t.max_attempts != null ? Number(t.max_attempts) : null;
      const attemptsUsed = lastResult ? (lastResult.attempt_number || 0) : 0;
      const hasAttemptsLeft = !limitAttempts || maxAttempts == null || attemptsUsed < maxAttempts;
      const passed = lastResult && lastResult.passed === true;
      const failed = lastResult && !lastResult.passed;
      let resultHtml = t.is_active === false ? '<span style="color:#999">выключен</span>' : '\u2014';
      if (lastResult) {
        if (passed) resultHtml = '<span style="color:#2e7d32;font-weight:600;">Пройден</span>';
        else resultHtml = '<span style="color:#c62828;font-weight:600;">Провален</span>';
      }
      const ballsHtml = lastResult && lastResult.total != null ? (lastResult.score + ' из ' + lastResult.total) : '\u2014';
      const actions = document.createElement('div');
      actions.className = 'tests-actions';
      const showRunBtn = !passed && (!failed || hasAttemptsLeft);
      if (showRunBtn) {
        const runBtn = document.createElement('button');
        runBtn.className = 'refresh-button';
        runBtn.textContent = failed && hasAttemptsLeft ? 'Перепройти' : 'Пройти';
        runBtn.addEventListener('click', () => openRunModal(t.id));
        actions.appendChild(runBtn);
      }
      if (isAdmin) {
        const editBtn = document.createElement('button');
        editBtn.className = 'refresh-button';
        editBtn.textContent = 'Редактировать';
        editBtn.addEventListener('click', () => openEditor(t.id));
        actions.appendChild(editBtn);
        const delBtn = document.createElement('button');
        delBtn.className = 'refresh-button';
        delBtn.style.background = '#d32f2f';
        delBtn.textContent = 'Удалить';
        delBtn.addEventListener('click', () => deleteGlobalTest(t.id));
        actions.appendChild(delBtn);
      }
      tr.innerHTML = `<td><strong>${esc(title)}</strong></td><td>Глобальный тест</td><td>${resultHtml}</td><td>${ballsHtml}</td><td></td>`;
      tr.children[4].appendChild(actions);
      frag.appendChild(tr);
    }
    globalTbody.innerHTML = '';
    globalTbody.appendChild(frag);
  }

  function openLessonTest(t) {
    const s = t.source || {};
    if (s.lesson_id) {
      window.location.href = '/lessons-content-pg?lesson_id=' + encodeURIComponent(String(s.lesson_id));
      return;
    }
    if (typeof customAlert === 'function') customAlert('Не удалось определить урок', 'Ошибка');
    else alert('Не удалось определить урок');
  }

  async function openRunModal(testId) {
    try {
      const [data, lastResultRes] = await Promise.all([
        fetchJson(API_BASE + '/global-tests/' + encodeURIComponent(String(testId))),
        fetchJson(API_BASE + '/global-tests/' + encodeURIComponent(String(testId)) + '/submit/last').catch(() => ({}))
      ]);
      const test = data.test || {};
      const questions = Array.isArray(data.questions) ? data.questions : [];
      const settings = (test.settings && typeof test.settings === 'object') ? test.settings : {};
      const timeLimitSeconds = Number(settings.time_limit_seconds) || 0;
      const limitAttempts = !!settings.limit_attempts;
      const maxAttempts = settings.max_attempts != null ? Number(settings.max_attempts) : null;
      const lastResult = lastResultRes.result || null;

      if (limitAttempts && maxAttempts != null && lastResult && lastResult.attempt_number >= maxAttempts) {
        const container = document.createElement('div');
        container.style.cssText = 'max-width:480px;padding:8px 0;';
        const titleEl = document.createElement('div');
        titleEl.style.cssText = 'font-weight:700;font-size:1.05rem;margin-bottom:12px;';
        titleEl.textContent = test.title || 'Тест';
        container.appendChild(titleEl);
        const msg = document.createElement('div');
        msg.style.cssText = 'padding:16px;background:#e8eaf6;border-radius:12px;border:1px solid #9fa8da;';
        const used = lastResult.attempt_number || 0;
        const total = lastResult.total || 0;
        const score = lastResult.score ?? 0;
        const pct = lastResult.score_percent ?? (total ? Math.round((score / total) * 100) : 0);
        const passed = lastResult.passed === true;
        const dateStr = lastResult.created_at ? new Date(lastResult.created_at).toLocaleString('ru-RU') : '';
        msg.innerHTML = `
          <div style="font-weight:600;color:#283593;margin-bottom:8px;">Попытки исчерпаны (${used} из ${maxAttempts})</div>
          <div style="margin-bottom:6px;"><strong>Ваш результат:</strong> ${score} из ${total} (${pct}%) — ${passed ? 'тест пройден' : 'тест не пройден'}</div>
          ${dateStr ? '<div style="font-size:0.9rem;color:#555;">Дата: ' + dateStr + '</div>' : ''}
        `;
        container.appendChild(msg);
        if (typeof customModal === 'function') {
          try { customModal('Пройти тест: ' + (test.title || 'Тест'), container); return; } catch (e) {}
        }
        openModal('Пройти тест: ' + (test.title || 'Тест'), container);
        return;
      }

      const container = document.createElement('div');
      container.className = 'global-test-run-container';
      container.style.cssText = 'max-width:520px;max-height:75vh;overflow:auto;';

      const hasTimeLimit = timeLimitSeconds > 0;
      function fmt(s) {
        const m = Math.floor(Math.max(0, s) / 60);
        const r = Math.max(0, s) % 60;
        return m + ':' + String(r).padStart(2, '0');
      }
      let timeValueEl = null;
      let timerIntervalId = null;
      let remainingSeconds = timeLimitSeconds;

      const startScreen = document.createElement('div');
      startScreen.className = 'gt-run-start-screen';
      startScreen.style.cssText = 'padding:8px 0;';
      const titleEl = document.createElement('div');
      titleEl.style.cssText = 'font-weight:700;font-size:1.05rem;margin-bottom:6px;';
      titleEl.textContent = test.title || 'Тест';
      startScreen.appendChild(titleEl);
      const desc = (test.description || '').toString().trim();
      if (desc && !/^\d+$/.test(desc)) {
        const descEl = document.createElement('div');
        descEl.style.cssText = 'color:#666;font-size:0.9rem;margin-bottom:16px;';
        descEl.textContent = desc;
        startScreen.appendChild(descEl);
      }
      if (hasTimeLimit) {
        const noticeBox = document.createElement('div');
        noticeBox.style.cssText = 'margin-bottom:16px;padding:16px;background:linear-gradient(135deg,#e3f2fd 0%,#bbdefb 100%);border-radius:12px;border:1px solid #90caf9;box-shadow:0 1px 3px rgba(0,0,0,0.06);';
        const noticeText = document.createElement('div');
        noticeText.style.cssText = 'font-weight:500;color:#0d47a1;margin-bottom:10px;line-height:1.4;';
        const minutes = Math.ceil(timeLimitSeconds / 60);
        noticeText.textContent = 'На этот тест отведено время: ' + minutes + ' мин. Нажмите «Начать» — появятся вопросы и запустится таймер.';
        noticeBox.appendChild(noticeText);
        const timeHint = document.createElement('div');
        timeHint.style.cssText = 'font-size:0.9rem;color:#1565c0;';
        timeHint.textContent = 'Осталось времени: ' + fmt(timeLimitSeconds);
        noticeBox.appendChild(timeHint);
        startScreen.appendChild(noticeBox);
        const startBtn = document.createElement('button');
        startBtn.type = 'button';
        startBtn.className = 'refresh-button';
        startBtn.textContent = 'Начать';
        startBtn.style.cssText = 'margin-top:0;padding:12px 28px;font-size:1rem;font-weight:600;';
        startScreen.appendChild(startBtn);
      }
      const questionsBlock = document.createElement('div');
      questionsBlock.style.cssText = 'display:flex;flex-direction:column;gap:0;';
      if (hasTimeLimit) {
        questionsBlock.style.display = 'none';
        const timerBar = document.createElement('div');
        timerBar.style.cssText = 'margin-bottom:14px;padding:10px 14px;background:#263238;color:#fff;border-radius:10px;font-weight:600;font-size:1.05rem;';
        timerBar.appendChild(document.createTextNode('Осталось времени: '));
        timeValueEl = document.createElement('span');
        timeValueEl.textContent = fmt(remainingSeconds);
        timerBar.appendChild(timeValueEl);
        questionsBlock.appendChild(timerBar);
      }

      const form = document.createElement('form');
      form.style.cssText = 'display:flex;flex-direction:column;gap:14px;';
      const answers = [];

      questions.forEach((q, idx) => {
        const qContent = (q && q.content) ? q.content : (typeof q === 'object' ? q : {});
        const text = qContent.text || qContent.question || '';
        const answerType = (qContent.answer_type || (qContent.multiple ? 'multiple' : 'single') || 'single').toLowerCase();
        const options = Array.isArray(qContent.options) ? qContent.options : [];

        const wrap = document.createElement('div');
        wrap.style.cssText = 'padding:14px;border:1px solid #e0e0e0;border-radius:10px;background:#fafafa;';
        const label = document.createElement('div');
        label.style.cssText = 'font-weight:600;margin-bottom:10px;color:#333;';
        label.textContent = (idx + 1) + '. ' + (text || 'Вопрос без текста');
        wrap.appendChild(label);

        if (answerType === 'input') {
          const inp = document.createElement('input');
          inp.type = 'text';
          inp.name = 'q-' + idx;
          inp.placeholder = 'Введите ответ';
          inp.style.cssText = 'width:100%;padding:8px;box-sizing:border-box;';
          wrap.appendChild(inp);
          form.appendChild(wrap);
          answers[idx] = { type: 'input', el: inp };
          return;
        }
        const optsWrap = document.createElement('div');
        optsWrap.style.cssText = 'display:flex;flex-direction:column;gap:6px;';
        options.forEach((opt, oi) => {
          const lab = document.createElement('label');
          lab.style.cssText = 'display:flex;align-items:center;gap:8px;cursor:pointer;';
          const inp = document.createElement('input');
          inp.type = answerType === 'multiple' ? 'checkbox' : 'radio';
          inp.name = answerType === 'multiple' ? 'q-' + idx : 'q-' + idx;
          inp.value = String(oi);
          lab.appendChild(inp);
          lab.appendChild(document.createTextNode(opt));
          optsWrap.appendChild(lab);
        });
        wrap.appendChild(optsWrap);
        form.appendChild(wrap);
        answers[idx] = { type: answerType, options: options, name: 'q-' + idx, wrap };
      });

      const submitBtn = document.createElement('button');
      submitBtn.type = 'button';
      submitBtn.className = 'refresh-button';
      submitBtn.textContent = 'Отправить';
      submitBtn.style.marginTop = '12px';

      const resultDiv = document.createElement('div');
      resultDiv.style.cssText = 'margin-top:12px;padding:12px;border-radius:8px;display:none;';

      let started = false;
      questionsBlock.appendChild(form);
      questionsBlock.appendChild(submitBtn);
      questionsBlock.appendChild(resultDiv);

      if (hasTimeLimit) {
        const startBtn = startScreen.querySelector('button');
        startBtn.addEventListener('click', () => {
          started = true;
          startScreen.style.display = 'none';
          questionsBlock.style.display = '';
          if (timeValueEl) {
            remainingSeconds = timeLimitSeconds;
            timeValueEl.textContent = fmt(remainingSeconds);
            timerIntervalId = setInterval(() => {
              remainingSeconds--;
              if (timeValueEl) timeValueEl.textContent = fmt(Math.max(0, remainingSeconds));
              if (remainingSeconds <= 0) {
                clearInterval(timerIntervalId);
                submitBtn.click();
              }
            }, 1000);
          }
        });
      }

      container.appendChild(startScreen);
      container.appendChild(questionsBlock);

      submitBtn.addEventListener('click', async () => {
        if (timeLimitSeconds > 0 && !started) {
          resultDiv.style.display = 'block';
          resultDiv.style.background = '#fff3e0';
          resultDiv.style.color = '#e65100';
          resultDiv.textContent = 'Сначала нажмите «Начать», чтобы запустить тест и таймер.';
          return;
        }
        const payload = [];
        questions.forEach((q, idx) => {
          const a = answers[idx];
          if (!a) { payload.push([]); return; }
          if (a.type === 'input') {
            payload.push((a.el && a.el.value) ? a.el.value.trim() : '');
            return;
          }
          const name = a.name;
          const checked = form.querySelectorAll('input[name="' + name + '"]:checked');
          const vals = Array.from(checked).map((c) => parseInt(c.value, 10)).filter((n) => !isNaN(n));
          payload.push(a.type === 'single' ? (vals.length ? [vals[0]] : []) : vals);
        });

        submitBtn.disabled = true;
        try {
          const r = await fetch(API_BASE + '/global-tests/' + encodeURIComponent(String(testId)) + '/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ answers: payload })
          });
          const res = await r.json().catch(() => ({}));
          if (timerIntervalId) clearInterval(timerIntervalId);
          resultDiv.style.display = 'block';
          if (!r.ok) {
            resultDiv.style.background = '#ffebee';
            resultDiv.textContent = res.code === 'attempts_exhausted'
              ? ('Попытки исчерпаны. Использовано: ' + (res.attempts_used || '') + ' из ' + (res.max_attempts || ''))
              : (res.error || 'Ошибка отправки');
            if (res.code === 'attempts_exhausted') {
              form.querySelectorAll('input').forEach(function (inp) { inp.disabled = true; });
            } else {
              submitBtn.disabled = false;
            }
            return;
          }
          form.querySelectorAll('input').forEach(function (inp) { inp.disabled = true; });
          resultDiv.style.background = res.passed ? '#e8f5e9' : '#ffebee';
          resultDiv.style.color = '#333';
          resultDiv.innerHTML = `
            <strong>${res.passed ? 'Тест пройден' : 'Тест не пройден'}</strong><br>
            Баллы: ${res.score} из ${res.total} (${res.score_percent}%). Проходной балл: ${res.pass_percent}%.
            <br><span style="font-size:0.9rem;color:#666;">Повторная отправка недоступна.</span>
            ${res.feedback && res.feedback.length ? '<br>Обратная связь по вопросам отображается ниже.' : ''}
          `;
          load();
        } catch (err) {
          resultDiv.style.display = 'block';
          resultDiv.style.background = '#ffebee';
          resultDiv.textContent = err.message || 'Ошибка отправки';
          submitBtn.disabled = false;
        }
      });

      if (typeof customModal === 'function') {
        try { customModal('Пройти тест: ' + (test.title || 'Тест'), container); return; } catch (e) {}
      }
      openModal('Пройти тест: ' + (test.title || 'Тест'), container);
    } catch (e) {
      if (typeof customAlert === 'function') customAlert(e.message || 'Ошибка', 'Ошибка');
      else alert(e.message || 'Ошибка');
    }
  }

  // UI-редактор глобальных тестов (без JSON textarea)
  function buildGlobalTestEditorModal(state, overlayRef) {
    const st = state.settings || {};
    const passPct = st.pass_percent != null ? Number(st.pass_percent) : 70;
    const limitAttempts = !!st.limit_attempts;
    const maxAttempts = st.max_attempts != null ? Number(st.max_attempts) : 3;
    const timeLimitMin = st.time_limit_seconds != null ? Math.round(Number(st.time_limit_seconds) / 60) : 0;
    const hasTemporary = !!(st.available_from || st.available_until);
    const availFrom = (st.available_from || '').toString().substring(0, 16);
    const availUntil = (st.available_until || '').toString().substring(0, 16);
    const shuffleQ = !!st.shuffle_questions;
    const shuffleO = !!st.shuffle_options;

    const root = document.createElement('div');
    root.className = 'modal-container modal-container--wide';
    root.innerHTML = `
      <div class="modal-header">
        <h2 class="modal-title">${state.editId ? 'Редактировать тест' : 'Новый тест'}</h2>
        <button type="button" class="modal-close" id="gt-modal-close">×</button>
      </div>
      <div class="modal-body">
        <div class="test-edit-tabs" role="tablist" aria-label="Редактирование теста">
          <button type="button" class="test-edit-tab active" data-tab="settings" role="tab" aria-selected="true">Настройки</button>
          <button type="button" class="test-edit-tab" data-tab="questions" role="tab" aria-selected="false">Вопросы</button>
        </div>
        <div class="test-edit-content gt-test-edit-content">
          <div class="test-edit-panel active" data-panel="settings" role="tabpanel">
            <div class="form-group">
              <label class="form-label">Название теста</label>
              <input type="text" id="gt-edit-test-title" class="form-input" value="${esc(state.title || '')}" placeholder="Введите название теста" />
            </div>
            <div class="form-group">
              <label class="form-label">Описание</label>
              <textarea id="gt-edit-test-description" class="form-textarea" rows="3" placeholder="Краткое описание теста">${esc(state.description || '')}</textarea>
            </div>
            <div class="form-group inline">
              <label class="form-check">
                <input type="checkbox" id="gt-edit-test-active" ${state.is_active !== false ? 'checked' : ''} />
                <span>Активен</span>
              </label>
            </div>
            <div class="form-group">
              <label class="form-label">Порог прохождения (%)</label>
              <input type="number" id="gt-edit-test-pass-percent" class="form-input" min="1" max="100" value="${passPct}" style="max-width:6rem;" />
            </div>
            <div class="form-group inline">
              <label class="form-check">
                <input type="checkbox" id="gt-edit-test-limit-attempts" ${limitAttempts ? 'checked' : ''} />
                <span>Ограничить попытки</span>
              </label>
              <div class="form-inline-field">
                <label class="form-label-inline" for="gt-edit-test-max-attempts">Попыток</label>
                <input type="number" id="gt-edit-test-max-attempts" class="form-input small" min="1" value="${maxAttempts}" style="max-width:4rem;" ${limitAttempts ? '' : 'disabled'} />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Лимит времени (мин, 0 — без ограничения)</label>
              <input type="number" id="gt-edit-test-time-limit" class="form-input" min="0" value="${timeLimitMin}" style="max-width:6rem;" />
            </div>
            <div class="form-group">
              <label class="form-label">Тип теста</label>
              <div class="test-type-row" role="radiogroup" aria-label="Тип теста">
                <label class="form-radio">
                  <input type="radio" name="gt-edit-test-type" id="gt-edit-test-type-permanent" value="permanent" ${!hasTemporary ? 'checked' : ''} />
                  <span>Постоянный</span>
                </label>
                <label class="form-radio">
                  <input type="radio" name="gt-edit-test-type" id="gt-edit-test-type-temporary" value="temporary" ${hasTemporary ? 'checked' : ''} />
                  <span>Временный</span>
                </label>
              </div>
              <div class="test-availability" id="gt-edit-test-availability-fields" style="display:${hasTemporary ? 'block' : 'none'};">
                <div class="form-group">
                  <label class="form-label">Доступен с</label>
                  <input type="datetime-local" id="gt-edit-test-available-from" class="form-input" value="${esc(availFrom)}" />
                </div>
                <div class="form-group">
                  <label class="form-label">Доступен до</label>
                  <input type="datetime-local" id="gt-edit-test-available-until" class="form-input" value="${esc(availUntil)}" />
                </div>
              </div>
            </div>
            <div class="form-group inline">
              <label class="form-check">
                <input type="checkbox" id="gt-edit-test-shuffle-questions" ${shuffleQ ? 'checked' : ''} />
                <span>Перемешивать вопросы</span>
              </label>
              <label class="form-check">
                <input type="checkbox" id="gt-edit-test-shuffle-options" ${shuffleO ? 'checked' : ''} />
                <span>Перемешивать ответы</span>
              </label>
            </div>
          </div>
          <div class="test-edit-panel" data-panel="questions" role="tabpanel">
            <div class="test-questions-header">
              <div class="test-questions-title">Вопросы теста</div>
              <button type="button" class="btn-add-question" id="gt-edit-btn-add-question">+ Добавить вопрос</button>
            </div>
            <div class="test-questions-layout">
              <div class="test-questions-list" id="gt-edit-test-questions-list"></div>
              <div class="test-question-editor" id="gt-edit-test-question-editor"></div>
            </div>
            <div class="form-error" id="gt-edit-test-question-error" style="display:none;"></div>
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn-cancel" id="gt-btn-cancel">Отмена</button>
        <button type="button" class="btn-submit" id="gt-save-btn">Сохранить</button>
        <span id="gt-editor-msg" style="margin-left:8px;"></span>
      </div>
    `;

    const tabs = root.querySelectorAll('.test-edit-tab');
    const panels = root.querySelectorAll('.test-edit-panel');
    const listEl = root.querySelector('#gt-edit-test-questions-list');
    const editorEl = root.querySelector('#gt-edit-test-question-editor');
    const errorEl = root.querySelector('#gt-edit-test-question-error');
    const availabilityWrap = root.querySelector('#gt-edit-test-availability-fields');
    const typePermanentEl = root.querySelector('#gt-edit-test-type-permanent');
    const typeTemporaryEl = root.querySelector('#gt-edit-test-type-temporary');
    const limitAttemptsEl = root.querySelector('#gt-edit-test-limit-attempts');
    const maxAttemptsEl = root.querySelector('#gt-edit-test-max-attempts');
    let activeQuestionIndex = -1;

    function showError(msg) {
      if (!errorEl) return;
      errorEl.style.display = msg ? 'block' : 'none';
      errorEl.textContent = msg || '';
    }

    function applyTestTypeUI() {
      const isTemporary = !!typeTemporaryEl && typeTemporaryEl.checked;
      if (availabilityWrap) availabilityWrap.style.display = isTemporary ? 'block' : 'none';
    }
    function applyAttemptsUI() {
      const enabled = !!limitAttemptsEl && limitAttemptsEl.checked;
      if (maxAttemptsEl) maxAttemptsEl.disabled = !enabled;
    }
    typePermanentEl && typePermanentEl.addEventListener('change', applyTestTypeUI);
    typeTemporaryEl && typeTemporaryEl.addEventListener('change', applyTestTypeUI);
    limitAttemptsEl && limitAttemptsEl.addEventListener('change', applyAttemptsUI);

    function activateTab(tabName) {
      tabs.forEach((btn) => {
        const on = btn.dataset.tab === tabName;
        btn.classList.toggle('active', on);
        btn.setAttribute('aria-selected', on ? 'true' : 'false');
      });
      panels.forEach((p) => {
        p.classList.toggle('active', p.dataset.panel === tabName);
      });
    }

    tabs.forEach((btn) => {
      btn.addEventListener('click', () => activateTab(btn.dataset.tab || 'settings'));
    });

    function renderQuestionsList() {
      listEl.innerHTML = '';
      const qs = state.questions || [];
      if (!qs.length) {
        listEl.innerHTML = '<div class="test-questions-empty">Нет вопросов. Нажмите «+ Добавить вопрос».</div>';
        editorEl.innerHTML = '<div class="test-question-empty">Выберите вопрос слева или добавьте новый.</div>';
        return;
      }
      qs.forEach((q, idx) => {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'test-question-item' + (idx === activeQuestionIndex ? ' active' : '');
        item.dataset.index = String(idx);
        const text = (q && q.text) ? String(q.text).trim() : '';
        item.innerHTML = `<div class="test-question-item__num">Вопрос ${idx + 1}</div><div class="test-question-item__text">${esc(text || 'Без текста')}</div>`;
        item.addEventListener('click', () => {
          syncQuestionFromForm();
          activeQuestionIndex = idx;
          renderQuestionsList();
          renderQuestionEditor();
        });
        listEl.appendChild(item);
      });
      renderQuestionEditor();
    }

    function syncQuestionFromForm() {
      const q = state.questions[activeQuestionIndex];
      if (!q) return;
      const textInp = editorEl.querySelector('#gt-q-text');
      const typeSel = editorEl.querySelector('#gt-q-type');
      const pointsInp = editorEl.querySelector('#gt-q-points');
      if (textInp) q.text = textInp.value.trim();
      if (pointsInp) { const v = parseInt(pointsInp.value, 10); q.points = (!isNaN(v) && v > 0) ? v : 1; }
      if (typeSel) {
        const t = (typeSel.value || 'single').toLowerCase();
        q.answer_type = t;
        q.multiple = t === 'multiple';
        if (t === 'input') {
          const accInp = editorEl.querySelector('#gt-q-accepted');
          q.accepted_answers = accInp ? accInp.value.split(',').map((s) => s.trim()).filter(Boolean) : [];
          delete q.options;
          delete q.correct_answer;
        } else {
          const optsList = editorEl.querySelector('#gt-q-options-list');
          const opts = [];
          const correctIdx = [];
          if (optsList) {
            optsList.querySelectorAll('.gt-opt-row').forEach((row) => {
              const inp = row.querySelector('input[type="text"]');
              const cb = row.querySelector('input.test-opt-correct');
              const v = (inp && inp.value) ? inp.value.trim() : '';
              if (v) {
                if (cb && cb.checked) correctIdx.push(opts.length);
                opts.push(v);
              }
            });
          }
          q.options = opts;
          q.correct_answer = q.multiple ? correctIdx : (correctIdx[0] !== undefined ? correctIdx[0] : 0);
          delete q.accepted_answers;
        }
      }
    }

    function renderQuestionEditor() {
      editorEl.innerHTML = '';
      const q = state.questions[activeQuestionIndex];
      if (!q) {
        editorEl.innerHTML = '<div class="test-question-empty">Выберите вопрос слева или добавьте новый.</div>';
        return;
      }
      showError('');
      const type = (q.answer_type || (q.multiple ? 'multiple' : 'single') || 'single').toLowerCase();
      const points = typeof q.points === 'number' && q.points > 0 ? q.points : 1;
      const options = Array.isArray(q.options) ? q.options : ['', ''];
      const correct = q.correct_answer;
      const correctSet = new Set(Array.isArray(correct) ? correct : (Number.isFinite(Number(correct)) ? [Number(correct)] : []));
      const accepted = Array.isArray(q.accepted_answers) ? q.accepted_answers.join(', ') : '';

      editorEl.innerHTML = `
        <div class="test-question-editor__header">
          <div class="test-question-editor__title">Редактирование вопроса ${activeQuestionIndex + 1}</div>
          <button type="button" class="test-question-delete-btn" id="gt-q-delete">Удалить</button>
        </div>
        <div class="form-group">
          <label class="form-label">Текст вопроса <span class="required">*</span></label>
          <textarea id="gt-q-text" class="form-textarea" rows="3" placeholder="Введите формулировку вопроса">${esc(q.text || '')}</textarea>
        </div>
        <div class="form-group inline">
          <div>
            <label class="form-label">Тип ответа</label>
            <select id="gt-q-type" class="form-input">
              <option value="single" ${type === 'single' ? 'selected' : ''}>Один вариант</option>
              <option value="multiple" ${type === 'multiple' ? 'selected' : ''}>Несколько вариантов</option>
              <option value="input" ${type === 'input' ? 'selected' : ''}>Ввод текста</option>
            </select>
          </div>
          <div>
            <label class="form-label">Баллы</label>
            <input type="number" id="gt-q-points" class="form-input small" min="1" value="${points}" />
          </div>
        </div>
        <div id="gt-q-options-block" class="test-q-options">
          <div class="test-q-options__header">
            <div class="test-q-options__title">Варианты ответа <span class="required">*</span></div>
            <button type="button" class="btn-add-option" id="gt-q-add-opt">+ Добавить вариант</button>
          </div>
          <div class="test-q-options__list" id="gt-q-options-list"></div>
        </div>
        <div id="gt-q-input-block" class="tq-input-block" style="display:none;">
          <label class="form-label">Допустимые ответы (через запятую)</label>
          <input type="text" id="gt-q-accepted" class="form-input" placeholder="например: да, согласен, верно" value="${esc(accepted)}" />
        </div>
      `;

      const optionsList = editorEl.querySelector('#gt-q-options-list');
      const typeSel = editorEl.querySelector('#gt-q-type');
      const optionsBlock = editorEl.querySelector('#gt-q-options-block');
      const inputBlock = editorEl.querySelector('#gt-q-input-block');

      function toggleType() {
        const t = (typeSel.value || 'single').toLowerCase();
        optionsBlock.style.display = t === 'input' ? 'none' : 'block';
        inputBlock.style.display = t === 'input' ? 'block' : 'none';
      }

      const isMultiple = type === 'multiple';
      function addOptRow(val, checked) {
        const row = document.createElement('div');
        row.className = 'test-opt-row gt-opt-row';
        const correctInput = isMultiple
          ? '<label class="test-opt-correct-label"><input type="checkbox" class="test-opt-correct" /><span>правильный</span></label>'
          : '<label class="test-opt-correct-label"><input type="radio" name="gt-correct-radio" class="test-opt-correct" /><span>правильный</span></label>';
        row.innerHTML = `
          <input type="text" class="form-input test-opt-text" placeholder="Текст варианта" value="${esc(val || '')}" />
          ${correctInput}
          <button type="button" class="btn-delete-option" aria-label="Удалить">×</button>
        `;
        const delBtn = row.querySelector('.btn-delete-option');
        delBtn.addEventListener('click', () => row.remove());
        const cb = row.querySelector('input.test-opt-correct');
        if (cb) cb.checked = !!checked;
        optionsList.appendChild(row);
      }

      options.forEach((opt, i) => addOptRow(opt, correctSet.has(i)));
      typeSel.addEventListener('change', () => {
        toggleType();
        syncQuestionFromForm();
        renderQuestionEditor();
      });
      toggleType();

      editorEl.querySelector('#gt-q-add-opt')?.addEventListener('click', () => addOptRow('', false));

      const pointsEl = editorEl.querySelector('#gt-q-points');
      if (pointsEl) pointsEl.addEventListener('input', () => { const v = parseInt(pointsEl.value, 10); if (!isNaN(v) && v > 0) q.points = v; });

      editorEl.querySelector('#gt-q-delete')?.addEventListener('click', () => {
        state.questions.splice(activeQuestionIndex, 1);
        activeQuestionIndex = Math.max(0, Math.min(activeQuestionIndex, (state.questions.length || 1) - 1));
        renderQuestionsList();
      });
    }

    root.querySelector('#gt-edit-btn-add-question')?.addEventListener('click', () => {
      if (!state.questions) state.questions = [];
      state.questions.push({ text: '', answer_type: 'single', options: ['', ''], correct_answer: 0, points: 1 });
      activeQuestionIndex = state.questions.length - 1;
      renderQuestionsList();
    });

    root.querySelector('#gt-modal-close')?.addEventListener('click', () => overlayRef && overlayRef.remove());
    root.querySelector('#gt-btn-cancel')?.addEventListener('click', () => overlayRef && overlayRef.remove());

    root.querySelector('#gt-save-btn')?.addEventListener('click', async () => {
      syncQuestionFromForm();
      const title = (root.querySelector('#gt-edit-test-title')?.value || '').trim();
      if (!title) {
        if (typeof customAlert === 'function') customAlert('Введите название теста', 'Ошибка');
        else alert('Введите название теста');
        return;
      }
      const questions = (state.questions || []).filter((q) => q && (q.text || '').trim());
      if (!questions.length) {
        if (typeof customAlert === 'function') customAlert('Добавьте хотя бы один вопрос', 'Ошибка');
        else alert('Добавьте хотя бы один вопрос');
        return;
      }
      const msgEl = root.querySelector('#gt-editor-msg');
      msgEl.textContent = 'Сохранение...';
      try {
        const passPercent = parseInt(root.querySelector('#gt-edit-test-pass-percent')?.value || '70', 10) || 70;
        const limitAttempts = root.querySelector('#gt-edit-test-limit-attempts')?.checked || false;
        const maxAttempts = parseInt(root.querySelector('#gt-edit-test-max-attempts')?.value || '3', 10) || 3;
        const timeLimitMin = parseInt(root.querySelector('#gt-edit-test-time-limit')?.value || '0', 10) || 0;
        const availableFrom = (root.querySelector('#gt-edit-test-available-from')?.value || '').trim();
        const availableUntil = (root.querySelector('#gt-edit-test-available-until')?.value || '').trim();
        const isTemporary = root.querySelector('#gt-edit-test-type-temporary')?.checked || false;
        const settings = {
          pass_percent: passPercent,
          limit_attempts: limitAttempts,
          max_attempts: maxAttempts,
          time_limit_seconds: timeLimitMin > 0 ? timeLimitMin * 60 : 0,
          shuffle_questions: root.querySelector('#gt-edit-test-shuffle-questions')?.checked || false,
          shuffle_options: root.querySelector('#gt-edit-test-shuffle-options')?.checked || false
        };
        if (isTemporary) {
          if (availableFrom) settings.available_from = availableFrom;
          if (availableUntil) settings.available_until = availableUntil;
        }
        const payload = {
          title,
          description: (root.querySelector('#gt-edit-test-description')?.value || '').trim(),
          is_active: root.querySelector('#gt-edit-test-active')?.checked !== false,
          questions: questions.map((q) => {
            const out = { text: (q.text || '').trim(), answer_type: q.answer_type || 'single', points: (q.points != null ? Number(q.points) : 1) || 1 };
            if (out.answer_type === 'input') {
              out.accepted_answers = Array.isArray(q.accepted_answers) ? q.accepted_answers : [];
            } else {
              out.options = Array.isArray(q.options) ? q.options : [];
              out.correct_answer = q.correct_answer;
              out.multiple = out.answer_type === 'multiple';
            }
            return out;
          }),
          settings
        };
        if (state.editId) {
          await fetchJson(API_BASE + '/global-tests/' + encodeURIComponent(String(state.editId)), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
        } else {
          await fetchJson(API_BASE + '/global-tests', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
        }
        msgEl.innerHTML = '<span style="color:#2e7d32;">Сохранено</span>';
        if (overlayRef) overlayRef.remove();
        await load();
      } catch (e) {
        msgEl.innerHTML = '<span style="color:#c62828;">' + esc(e.message || 'Ошибка') + '</span>';
      }
    });

    renderQuestionsList();
    return root;
  }

  async function openEditor(id) {
    try {
      const state = {
        editId: id || null,
        title: '',
        description: '',
        is_active: true,
        settings: { pass_percent: 70, limit_attempts: false, max_attempts: 3, time_limit_seconds: 0 },
        questions: []
      };
      if (id) {
        const data = await fetchJson(API_BASE + '/global-tests/' + encodeURIComponent(String(id)));
        const t = data.test || {};
        state.title = t.title || '';
        state.description = t.description || '';
        state.is_active = t.is_active !== false;
        state.settings = (t.settings && typeof t.settings === 'object') ? t.settings : state.settings;
        const qs = Array.isArray(data.questions) ? data.questions : [];
        state.questions = qs.map((x) => {
          const c = (x && x.content) ? x.content : (typeof x === 'object' ? x : {});
          return {
            text: c.text || c.question || '',
            answer_type: c.answer_type || (c.multiple ? 'multiple' : 'single'),
            options: Array.isArray(c.options) ? c.options : [],
            correct_answer: c.correct_answer,
            accepted_answers: Array.isArray(c.accepted_answers) ? c.accepted_answers : [],
            multiple: !!c.multiple
          };
        });
        if (!state.questions.length) state.questions = [{ text: '', answer_type: 'single', options: ['', ''], correct_answer: 0 }];
      }

      const overlay = document.createElement('div');
      overlay.className = 'gt-modal-overlay';
      overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:9999;padding:1.5rem;overflow-x:hidden;overflow-y:auto;box-sizing:border-box;';
      const modal = document.createElement('div');
      modal.className = 'gt-modal-wrap';
      modal.style.cssText = 'width:100%;max-width:min(920px,100vw - 2rem);max-height:90vh;display:flex;flex-direction:column;flex-shrink:0;';
      const content = buildGlobalTestEditorModal(state, overlay);
      modal.appendChild(content);
      overlay.appendChild(modal);
      overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
      document.body.appendChild(overlay);
    } catch (e) {
      if (typeof customAlert === 'function') customAlert(e.message || 'Ошибка', 'Ошибка');
      else alert(e.message || 'Ошибка');
    }
  }

  async function deleteGlobalTest(id) {
    try {
      if (typeof customConfirm === 'function') {
        const ok = await customConfirm('Удалить этот тест? Это действие необратимо.');
        if (!ok) return;
      } else {
        if (!confirm('Удалить этот тест?')) return;
      }
      await fetchJson(API_BASE + '/global-tests/' + encodeURIComponent(String(id)), { method: 'DELETE' });
      await load();
    } catch (e) {
      if (typeof customAlert === 'function') customAlert(e.message || 'Ошибка', 'Ошибка');
      else alert(e.message || 'Ошибка');
    }
  }

  async function load() {
    if (lessonTbody) lessonTbody.innerHTML = '<tr><td colspan="5" class="loading">Загрузка...</td></tr>';
    if (globalTbody) globalTbody.innerHTML = '<tr><td colspan="5" class="loading">Загрузка...</td></tr>';
    try {
      const [userRes, depsRes, testsRes] = await Promise.all([
        fetchJson(API_BASE + '/current-user').catch(() => ({})),
        fetchJson(API_BASE + '/departments').catch(() => ({ departments: [] })),
        fetchJson(API_BASE + '/tests')
      ]);
      isAdmin = (userRes.effective_role === 'admin' || userRes.effective_role === 'super_admin');
      if (deptSelect && Array.isArray(depsRes.departments)) {
        deptSelect.innerHTML = '<option value="">Все отделы</option>';
        for (let i = 0; i < depsRes.departments.length; i++) {
          const opt = document.createElement('option');
          opt.value = depsRes.departments[i];
          opt.textContent = depsRes.departments[i];
          deptSelect.appendChild(opt);
        }
      }
      lastTests = Array.isArray(testsRes.tests) ? testsRes.tests : [];
      applyFilterAndSort();
    } catch (e) {
      const errMsg = esc(e.message || 'Ошибка загрузки');
      if (lessonTbody) lessonTbody.innerHTML = '<tr><td colspan="5" class="loading" style="color:#d32f2f;">' + errMsg + '</td></tr>';
      if (globalTbody) globalTbody.innerHTML = '<tr><td colspan="5" class="loading" style="color:#d32f2f;">' + errMsg + '</td></tr>';
    }
  }

  document.querySelectorAll('.tests-tab').forEach(function (tab) {
    tab.addEventListener('click', function () {
      const name = this.getAttribute('data-tab');
      document.querySelectorAll('.tests-tab').forEach(function (t) { t.classList.remove('active'); });
      document.querySelectorAll('.tests-panel').forEach(function (p) { p.classList.remove('active'); });
      this.classList.add('active');
      const panel = document.getElementById('panel-' + name);
      if (panel) panel.classList.add('active');
    });
  });

  if (refreshBtn) refreshBtn.addEventListener('click', load);
  if (searchInput) {
    searchInput.addEventListener('input', function () {
      clearTimeout(window.__testsSearchTimer);
      window.__testsSearchTimer = setTimeout(applyFilterAndSort, 120);
    });
  }
  if (sortSelect) sortSelect.addEventListener('change', applyFilterAndSort);

  // Грузим данные сразу, даже если DOMContentLoaded уже случился
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load);
  } else {
    load();
  }
})();
