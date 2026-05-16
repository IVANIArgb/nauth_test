/**
 * Страница /terminal: команды смены роли по кнопке «Выполнить» (без отправки по Enter).
 */
(function () {
  function el(id) {
    return document.getElementById(id);
  }

  function setStatus(text, isError) {
    var statusEl = el("terminal-status-msg");
    if (!statusEl) return;
    statusEl.textContent = text || "";
    statusEl.classList.remove("terminal-status--ok");
    statusEl.classList.toggle("terminal-status--error", !!isError);
    if (text && !isError) statusEl.classList.add("terminal-status--ok");
  }

  async function refreshEnabled() {
    var btn = el("terminal-run-btn");
    try {
      var r = await fetch("/api/me/terminal-commands-enabled", { credentials: "include" });
      var d = await r.json().catch(function () {
        return {};
      });
      if (r.status === 401) {
        setStatus("Войдите в систему, чтобы использовать терминал.", true);
        if (btn) btn.disabled = true;
        return;
      }
      if (!r.ok) {
        setStatus("Не удалось проверить настройки.", true);
        if (btn) btn.disabled = true;
        return;
      }
      if (!d.enabled) {
        setStatus(
          "Команды терминала отключены. Включите TERMINAL_ROLE_COMMANDS_ENABLED=true на сервере.",
          true
        );
        if (btn) btn.disabled = true;
        return;
      }
      setStatus(
        "Команды активны: роли, seed, просмотр настроек. Список — команда list-commands.",
        false
      );
      if (btn) btn.disabled = false;
    } catch (e) {
      setStatus("Ошибка сети при проверке настроек.", true);
      if (btn) btn.disabled = true;
    }
  }

  async function runCommand() {
    var input = el("terminal-input");
    var btn = el("terminal-run-btn");
    if (!input || !btn) return;

    var line = input.value.trim();
    if (!line) {
      if (typeof window.customAlert === "function") await window.customAlert("Введите команду.");
      return;
    }

    btn.disabled = true;
    try {
      var r = await fetch("/api/me/terminal-role-command", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: line }),
      });
      var d = await r.json().catch(function () {
        return {};
      });
      if (r.ok) {
        if (d.settings) {
          var txt = JSON.stringify(d.settings, null, 2);
          if (typeof window.customAlert === "function") await window.customAlert(txt);
          else window.alert(txt);
          return;
        }
        if (d.commands && Array.isArray(d.commands)) {
          var lines = d.commands.map(function (c) {
            return (c.command || "") + " — " + (c.description || "");
          });
          var block = lines.join("\n");
          if (typeof window.customAlert === "function") await window.customAlert(block);
          else window.alert(block);
          return;
        }
        if (d.role) {
          if (typeof window.customAlert === "function") {
            await window.customAlert(
              "Роль обновлена: " + (d.role || "") + ". Страница будет перезагружена."
            );
          }
          window.location.reload();
          return;
        }
        if (d.message) {
          if (typeof window.customAlert === "function") await window.customAlert(d.message);
          else window.alert(d.message);
          return;
        }
        if (typeof window.customAlert === "function") await window.customAlert("Готово.");
        return;
      }
      var msg = d.error || "Ошибка выполнения команды";
      if (typeof window.customAlert === "function") await window.customAlert(msg);
      else window.alert(msg);
    } finally {
      btn.disabled = false;
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    refreshEnabled();
    var btn = el("terminal-run-btn");
    if (btn) btn.addEventListener("click", runCommand);
  });
})();
