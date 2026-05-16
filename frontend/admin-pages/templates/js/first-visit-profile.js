// Модалка первого входа: подтверждение данных пользователя.
(function () {
  const STORAGE_KEY = "ls_profile_confirmed_v1";

  const FIRST_VISIT_MODAL_OPTS = {
    requireButtonsOnly: true,
    messageClass: "custom-modal-message--profile",
  };

  function safe(v) {
    return String(v || "").trim();
  }

  function val(v) {
    return safe(v) || "—";
  }

  function formatProfileConfirmationBody(u, extraTailLines) {
    const lines = [
      "Проверьте, пожалуйста, ваши данные.",
      "",
      "Логин",
      val(u.username),
      "",
      "ФИО",
      val(u.full_name),
      "",
      "Отдел",
      val(u.department),
      "",
      "Должность",
      val(u.position),
      "",
      "Email",
      val(u.email),
    ];
    if (extraTailLines && extraTailLines.length) {
      lines.push("", ...extraTailLines);
    }
    return lines.join("\n");
  }

  function isTruthy(v) {
    return String(v || "").trim().toLowerCase() === "true";
  }

  async function fetchJson(url) {
    const r = await fetch(url, { credentials: "include" });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error((data && data.error) || `HTTP ${r.status}`);
    return data;
  }

  function alreadyConfirmed() {
    try {
      return localStorage.getItem(STORAGE_KEY) === "1";
    } catch (e) {
      return false;
    }
  }

  function markConfirmed() {
    try {
      localStorage.setItem(STORAGE_KEY, "1");
    } catch (e) {}
  }

  function goReport(u, isGuest) {
    // Перекидываем на страницу "Вопросы" с предзаполнением (там модалка "создать вопрос" откроется сама).
    const title = "Ошибка в данных профиля (первый вход)";
    const bodyLines = [
      isGuest
        ? "Здравствуйте! Система не смогла определить меня (зашёл как guest) или данные профиля неверные."
        : "Здравствуйте! При первом входе система показала неверные данные профиля.",
      "",
      "Показано у меня:",
      `- Логин: ${safe(u.username) || "—"}`,
      `- ФИО: ${safe(u.full_name) || "—"}`,
      `- Отдел: ${safe(u.department) || "—"}`,
      `- Должность: ${safe(u.position) || "—"}`,
      `- Email: ${safe(u.email) || "—"}`,
      "",
      "Пожалуйста, исправьте данные в AD/настройках. Верные данные должны быть:",
      "- (напишите здесь)",
      "",
      "Техническая информация:",
      `- auth_method: ${safe(u.auth_method) || "—"}`,
      `- realm: ${safe(u.realm) || safe(u.domain) || "—"}`,
    ];
    const body = bodyLines.join("\n");
    const tags = "Проблема: Профиль, Тип: Ошибка данных";

    const qs = new URLSearchParams();
    qs.set("tab", "ask");
    qs.set("new", "1");
    qs.set("title", title);
    qs.set("body", body);
    qs.set("tags", tags);
    window.location.href = `/questions-pg?${qs.toString()}`;
  }

  async function run() {
    // Ждём custom-modal, иначе некуда показывать.
    if (typeof window.showCustomModal !== "function") return;
    if (alreadyConfirmed()) return;

    let u;
    try {
      u = await fetchJson("/api/current-user");
    } catch (e) {
      return;
    }

    const username = safe(u && u.username);
    const authMethod = safe(u && u.auth_method);
    const isGuest = (!username) || username === "guest" || authMethod === "none";
    if (isGuest) {
      const msgLines = [
        "Не удалось определить пользователя (вы вошли как guest).",
        "",
        "Такое бывает, если Kerberos/AD недоступны или неправильно настроены.",
        "",
        "Нажмите «Сообщить об ошибке» — откроется создание вопроса с готовым описанием.",
      ];
      window.showCustomModal("Проблема входа", msgLines.join("\n"), [
        {
          text: "Перейти в вопросы",
          className: "custom-modal-btn-confirm",
          onclick: () => {
            markConfirmed();
            window.closeCustomModal();
            window.location.href = "/questions-pg";
          },
        },
        {
          text: "Сообщить об ошибке",
          className: "custom-modal-btn-cancel",
          onclick: () => {
            markConfirmed();
            window.closeCustomModal();
            goReport(u || {}, true);
          },
        },
      ],
        FIRST_VISIT_MODAL_OPTS);
      return;
    }

    // В тестовом режиме (контейнер/демо) пользователь часто "фейковый" — но модалку всё равно полезно показать.
    const testMode = isTruthy(u && u.test_mode) || isTruthy((u && u.TEST_MODE) || "");

    const body = formatProfileConfirmationBody(
      u,
      testMode
        ? [
            "Примечание: сейчас включён TEST_MODE (демо/контейнер), данные могут быть тестовыми.",
          ]
        : null
    );

    window.showCustomModal("Подтверждение профиля", body, [
      {
        text: "Всё верно",
        className: "custom-modal-btn-confirm",
        onclick: () => {
          markConfirmed();
          window.closeCustomModal();
        },
      },
      {
        text: "Сообщить об ошибке",
        className: "custom-modal-btn-cancel",
        onclick: () => {
          markConfirmed();
          window.closeCustomModal();
          goReport(u || {}, false);
        },
      },
    ],
      FIRST_VISIT_MODAL_OPTS);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    queueMicrotask(run);
  }
})();

