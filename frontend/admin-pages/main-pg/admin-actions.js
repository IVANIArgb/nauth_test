;(function () {
  async function fetchCurrentUser() {
    try {
      const resp = await fetch('/api/current-user', { credentials: 'include' })
      if (!resp.ok) return null
      const data = await resp.json().catch(() => null)
      return data && typeof data === 'object' ? data : null
    } catch (e) {
      console.error('Не удалось получить текущего пользователя', e)
      return null
    }
  }

  async function fetchCurrentContentRootInfo() {
    try {
      const resp = await fetch('/api/admin/content-root', {
        method: 'GET',
        credentials: 'include',
      })
      if (!resp.ok) return null
      const data = await resp.json().catch(() => null)
      return data && typeof data === 'object' ? data : null
    } catch (e) {
      console.error('Не удалось получить информацию о папке контента', e)
      return null
    }
  }

  async function handleChangeContentRootClick() {
    const info = await fetchCurrentContentRootInfo()
    const current =
      info && info.current_root
        ? info.current_root
        : 'ещё не настроена (используется стандартная папка внутри проекта)'

    const hintLines = [
      'Укажите полный путь к НОВОЙ папке с контентом.',
      '',
      'Текущая папка:',
      current,
      '',
      'Можно выбрать существующую или новую директорию — она будет создана при необходимости.',
      '',
      'Пример (Windows):',
      'C:\\\\Users\\\\Имя\\\\Desktop\\\\learning-content',
      '',
      'ВНИМАНИЕ: после смены пути нужно перезапустить backend‑сервер,',
      'чтобы все страницы начали использовать новое хранилище.',
    ]

    const initialMessage = hintLines.join('\n')
    const path = window.prompt(initialMessage, info && info.current_root ? info.current_root : '')
    if (!path) {
      return
    }

    try {
      const resp = await fetch('/api/admin/content-root', {
        method: 'PUT',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ path }),
      })

      const data = await resp.json().catch(() => ({}))

      if (!resp.ok || !data || data.ok !== true) {
        const msg =
          (data && data.error) ||
          `Не удалось обновить папку контента (код ${resp.status}). Проверьте путь и права доступа.`
        if (window.customAlert) {
          await window.customAlert(msg, 'Ошибка смены папки контента')
        } else {
          alert(msg)
        }
        return
      }

      const finalMsgLines = [
        'Папка контента успешно обновлена.',
        '',
        `Новый путь:`,
        data.new_root || path,
        '',
        'Файл .env тоже обновлён.',
        'Перезапустите backend‑сервер (перезапуск приложения),',
        'чтобы новые настройки CONTENT_ROOT_DIR вступили в силу.',
      ]

      const finalMsg = finalMsgLines.join('\n')
      if (window.customAlert) {
        await window.customAlert(finalMsg, 'Готово')
      } else {
        alert(finalMsg)
      }
    } catch (e) {
      const msg = `Ошибка сети при смене папки контента: ${e}`
      if (window.customAlert) {
        await window.customAlert(msg, 'Ошибка сети')
      } else {
        alert(msg)
      }
    }
  }

  function initChangeContentRootButton(user) {
    if (!user || (user.effective_role || user.role || '').toLowerCase() !== 'super_admin') {
      return
    }

    const menuList = document.querySelector('.menu ul')
    if (!menuList) return

    const li = document.createElement('li')
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.className = 'menu-change-content-btn'
    btn.textContent = 'Сменить папку контента'
    btn.addEventListener('click', handleChangeContentRootClick)

    li.appendChild(btn)
    menuList.appendChild(li)
  }

  async function init() {
    const user = await fetchCurrentUser()
    initChangeContentRootButton(user)
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init)
  } else {
    init()
  }
})()

