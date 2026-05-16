// Инициализация бейджей в шапке.
(function () {
  const badge = document.getElementById('questions-unanswered-badge');
  if (!badge) return;
  // Для обычных пользователей бейджи по вопросам не показываем.
  badge.style.display = 'none';
})();

