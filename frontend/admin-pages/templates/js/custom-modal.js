/**
 * Кастомное модальное окно
 * Заменяет стандартные alert() и confirm()
 *
 * Скрипт может подключаться дважды (base_static_page + страница) — повторный запуск пропускается.
 */
(function () {
    if (window.__learnSiteCustomModalLoaded) {
        return;
    }
    window.__learnSiteCustomModalLoaded = true;

    // Создаем overlay и модальное окно при загрузке страницы
    let customModalOverlay = null;
    let customModal = null;

    // Инициализация модального окна
    function initCustomModal() {
        const existing = document.getElementById("custom-modal-overlay");
        if (existing) {
            customModalOverlay = existing;
            customModal = document.getElementById("custom-modal");
            return;
        }
        if (customModalOverlay) return; // Уже инициализировано

        // Создаем overlay
        customModalOverlay = document.createElement("div");
        customModalOverlay.className = "custom-modal-overlay";
        customModalOverlay.id = "custom-modal-overlay";

        // Создаем модальное окно
        customModal = document.createElement("div");
        customModal.className = "custom-modal";
        customModal.id = "custom-modal";

        // Структура модального окна
        customModal.innerHTML = `
        <div class="custom-modal-header">
            <h2 class="custom-modal-title" id="custom-modal-title">заголовок</h2>
        </div>
        <div class="custom-modal-body">
            <p class="custom-modal-message" id="custom-modal-message">текст</p>
        </div>
        <div class="custom-modal-footer" id="custom-modal-footer">
            <!-- Кнопки добавляются динамически -->
        </div>
    `;

        customModalOverlay.appendChild(customModal);
        document.body.appendChild(customModalOverlay);

        // Закрытие при клике на overlay (не в режиме «только кнопки»)
        customModalOverlay.addEventListener("click", (e) => {
            if (
                e.target === customModalOverlay &&
                !customModalOverlay.classList.contains("custom-modal-overlay--blocking")
            ) {
                closeCustomModal();
            }
        });

        // Закрытие при Escape (не в режиме «только кнопки»)
        document.addEventListener("keydown", (e) => {
            if (
                e.key === "Escape" &&
                customModalOverlay.classList.contains("show") &&
                !customModalOverlay.classList.contains("custom-modal-overlay--blocking")
            ) {
                closeCustomModal();
            }
        });
    }

    // Показать модальное окно
    // options: { requireButtonsOnly?: boolean, messageClass?: string } — без закрытия по фону/Escape; доп. классы к тексту
    function showCustomModal(title, message, buttons, options) {
        options = options || {};
        if (!customModalOverlay) {
            initCustomModal();
        }

        // Устанавливаем заголовок и сообщение
        const titleEl = document.getElementById("custom-modal-title");
        const messageEl = document.getElementById("custom-modal-message");
        const footerEl = document.getElementById("custom-modal-footer");

        if (titleEl) titleEl.textContent = title || "заголовок";
        if (messageEl) {
            messageEl.textContent = message || "текст";
            messageEl.className = "custom-modal-message";
            if (options.messageClass) {
                String(options.messageClass)
                    .split(/\s+/)
                    .filter(Boolean)
                    .forEach((c) => messageEl.classList.add(c));
            }
        }

        // Очищаем и добавляем кнопки
        if (footerEl) {
            footerEl.innerHTML = "";
            if (buttons && buttons.length > 0) {
                buttons.forEach((button) => {
                    const btn = document.createElement("button");
                    btn.className = `custom-modal-btn ${button.className || ""}`;
                    btn.textContent = button.text || "текст";
                    btn.onclick = button.onclick || (() => closeCustomModal());
                    footerEl.appendChild(btn);
                });
            }
        }

        if (options.requireButtonsOnly) {
            customModalOverlay.classList.add("custom-modal-overlay--blocking");
        } else {
            customModalOverlay.classList.remove("custom-modal-overlay--blocking");
        }

        // Показываем модальное окно
        customModalOverlay.classList.add("show");
        document.body.style.overflow = "hidden"; // Блокируем скролл
    }

    // Закрыть модальное окно
    function closeCustomModal() {
        if (customModalOverlay) {
            customModalOverlay.classList.remove("show");
            customModalOverlay.classList.remove("custom-modal-overlay--blocking");
            document.body.style.overflow = ""; // Разблокируем скролл
        }
        const messageEl = document.getElementById("custom-modal-message");
        if (messageEl) {
            messageEl.className = "custom-modal-message";
        }
    }

    // Замена alert()
    function customAlert(message, title = "Уведомление") {
        return new Promise((resolve) => {
            showCustomModal(title, message, [
                {
                    text: "OK",
                    className: "custom-modal-btn-ok",
                    onclick: () => {
                        closeCustomModal();
                        resolve();
                    },
                },
            ]);
        });
    }

    // Замена confirm()
    function customConfirm(message, title = "Подтвердите действие") {
        return new Promise((resolve) => {
            showCustomModal(title, message, [
                {
                    text: "Отмена",
                    className: "custom-modal-btn-cancel",
                    onclick: () => {
                        closeCustomModal();
                        resolve(false);
                    },
                },
                {
                    text: "Подтвердить",
                    className: "custom-modal-btn-confirm",
                    onclick: () => {
                        closeCustomModal();
                        resolve(true);
                    },
                },
            ]);
        });
    }

    // Инициализация при загрузке DOM
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initCustomModal);
    } else {
        initCustomModal();
    }

    // Экспорт функций глобально
    window.customAlert = customAlert;
    window.customConfirm = customConfirm;
    window.showCustomModal = showCustomModal;
    window.closeCustomModal = closeCustomModal;
})();
