/**
 * JavaScript для страницы списка уроков
 */

const API_BASE = '/api';

// DOM элементы
let lessonsContainer = null;
let currentCourseId = null;
let currentUserRole = 'user';
let breadcrumbsContainer = null;
let currentCourse = null;
let currentCategory = null;
let isCreatingLesson = false; // Флаг для отслеживания процесса создания урока
let createLessonAbortController = null; // Контроллер для отмены запросов
let isUpdatingLesson = false; // Флаг для отслеживания процесса обновления урока
let updateLessonAbortController = null; // Контроллер для отмены запросов при обновлении

// Найти или создать контейнер для списка уроков
function ensureLessonsContainer() {
    if (lessonsContainer) return lessonsContainer;
    lessonsContainer = document.querySelector('.courses-grid') ||
        document.querySelector('main .courses-grid') ||
        document.querySelector('.main-content .courses-grid');
    if (!lessonsContainer) {
        const main = document.querySelector('main') || document.querySelector('.main-content');
        if (main) {
            const section = document.createElement('section');
            section.className = 'courses-grid';
            main.appendChild(section);
            lessonsContainer = section;
        }
    }
    return lessonsContainer;
}

// Инициализация страницы списка уроков
function initLessonsPage() {
    ensureLessonsContainer();
    if (lessonsContainer) {
        lessonsContainer.innerHTML = '<p class="loading-message">Загрузка уроков...</p>';
    }

    // Получаем course_id из URL
    const urlParams = new URLSearchParams(window.location.search);
    currentCourseId = urlParams.get('course_id');
    
    // Создаем breadcrumbs
    breadcrumbsContainer = document.querySelector('.breadcrumbs');
    if (!breadcrumbsContainer) {
        breadcrumbsContainer = document.createElement('nav');
        breadcrumbsContainer.className = 'breadcrumbs';
        const mainContent = document.querySelector('.main-content');
        if (mainContent) {
            const pageTitle = document.querySelector('.page-title');
            if (pageTitle && pageTitle.parentNode) {
                pageTitle.parentNode.insertBefore(breadcrumbsContainer, pageTitle);
            }
        }
    }
    
    // Сначала получаем роль, потом загружаем уроки (чтобы на карточках были кнопки админа)
    checkUserRole().then(() => {
        if (currentCourseId) {
            loadCourseForBreadcrumbs();
        } else {
            updatePageTitle();
        }
        loadLessons();
    });
    
    // Настраиваем обработчики событий
    setupEventListeners();
}

// Запускаем инициализацию независимо от того, когда подключён скрипт
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initLessonsPage);
} else {
    initLessonsPage();
}

// Загрузка курса для breadcrumbs
async function loadCourseForBreadcrumbs() {
    try {
        const response = await fetch(`${API_BASE}/courses/${currentCourseId}`);
        const data = await response.json();
        
        if (response.ok) {
            currentCourse = data;
            
            // Загружаем категорию
            if (data.category_id) {
                const catResponse = await fetch(`${API_BASE}/categories/${data.category_id}`);
                const catData = await catResponse.json();
                if (catResponse.ok) {
                    currentCategory = catData;
                }
            }
            
            updateBreadcrumbs();
        }
        updatePageTitle();
    } catch (error) {
        console.error('Ошибка загрузки курса:', error);
    }
}

// Обновление заголовка страницы
function updatePageTitle() {
    const pageTitle = document.querySelector('.page-title');
    if (!pageTitle) return;
    if (currentCourse) {
        pageTitle.textContent = `Уроки в «${currentCourse.title}»`;
    } else {
        pageTitle.textContent = 'Уроки';
    }
}

// Обновление breadcrumbs
function updateBreadcrumbs() {
    if (!breadcrumbsContainer) return;
    
    let breadcrumbs = '<a href="/main-pg">Главная</a>';
    breadcrumbs += ' > <a href="/all-categories-pg">База знаний</a>';
    
    if (currentCategory) {
        breadcrumbs += ` > <a href="/all-categories-pg">${escapeHtml(currentCategory.title)}</a>`;
    }
    
    if (currentCourse) {
        breadcrumbs += ` > <a href="/all-courses-pg?category_id=${currentCategory?.id || ''}">${escapeHtml(currentCourse.title)}</a>`;
    }
    
    breadcrumbs += ' > <span>Уроки</span>';
    
    breadcrumbsContainer.innerHTML = breadcrumbs;
}

// Проверка роли пользователя
async function checkUserRole() {
    try {
        const response = await fetch(`${API_BASE}/current-user`);
        const data = await response.json();
        if (response.ok && data.role) {
            currentUserRole = data.effective_role || data.role;
            if (currentUserRole === 'admin' || currentUserRole === 'super_admin') {
                showAdminControls();
            }
        }
    } catch (error) {
        console.error('Ошибка проверки роли:', error);
    }
}

// Показать элементы управления для админа
function showAdminControls() {
    // Показываем большую голубую кнопку "Добавить урок"
    const addSection = document.querySelector('.add-lesson-section');
    if (addSection) {
        addSection.style.display = 'flex';
    }
    
    // Показываем кнопку в секции добавления, если есть
    const createLessonBtn = document.getElementById('create-lesson-btn');
    if (createLessonBtn) {
        createLessonBtn.style.display = 'flex';
    }
}

// Загрузка уроков
async function loadLessons(courseId = null) {
    try {
        ensureLessonsContainer();
        const courseIdToUse = courseId || currentCourseId;
        const url = courseIdToUse 
            ? `${API_BASE}/lessons?course_id=${courseIdToUse}`
            : `${API_BASE}/lessons`;
        
        const response = await fetch(url);
        let data;
        try {
            data = await response.json();
        } catch (_) {
            data = { lessons: [] };
        }
        
        if (response.ok) {
            const lessons = Array.isArray(data)
                ? data
                : (Array.isArray(data.lessons) ? data.lessons : []);
            renderLessons(lessons);
        } else {
            if (lessonsContainer) {
                const errMsg = data.error || 'Не удалось загрузить уроки';
                const requiredLink = data.required_course_id
                    ? `<p><a href="/all-lessons-pg?course_id=${data.required_course_id}" class="btn-link">Перейти к необходимому курсу</a></p>`
                    : '';
                lessonsContainer.innerHTML = `<div class="lesson-locked-message"><p>${escapeHtml(errMsg)}</p>${requiredLink}</div>`;
            }
            showError(data.error || 'Не удалось загрузить уроки');
        }
    } catch (error) {
        console.error('Ошибка загрузки уроков:', error);
        if (lessonsContainer) {
            lessonsContainer.innerHTML = '<p class="empty-message">Ошибка загрузки уроков. Проверьте сеть и обновите страницу.</p>';
        }
        showError('Ошибка загрузки уроков');
    }
}

// Отображение уроков
function renderLessons(lessons) {
    if (!ensureLessonsContainer()) {
        const main = document.querySelector('main') || document.querySelector('.main-content');
        if (main) {
            main.innerHTML += '<p class="empty-message">Ошибка: контейнер списка не найден. Обновите страницу.</p>';
        }
        return;
    }
    
    lessonsContainer.innerHTML = '';
    
    if (lessons.length === 0) {
        lessonsContainer.innerHTML = '<p class="empty-message">Уроки не найдены</p>';
        return;
    }
    
    lessons.forEach(lesson => {
        const card = createLessonCard(lesson);
        lessonsContainer.appendChild(card);
    });
}

// Создание карточки урока
// Создание карточки урока (использует единый модуль)
function createLessonCard(lesson) {
    // Используем функцию из unified-card-builder.js
    if (typeof window.createLessonCardFromModule === 'function') {
        return window.createLessonCardFromModule(lesson, { currentUserRole });
    }
    // Fallback на локальную реализацию
    return createLessonCardLocal(lesson);
}

// Локальная реализация (fallback) - использует unified-card классы
function createLessonCardLocal(lesson) {
    const isAccessible = lesson.is_accessible !== false;
    const lockedReason = lesson.locked_reason || 'Материал недоступен. Пройдите предыдущие уроки в последовательности.';
    
    const card = document.createElement('article');
    card.className = 'unified-card lesson-card' + (!isAccessible ? ' card-locked' : '');
    card.dataset.lessonId = lesson.id;
    card.dataset.isAccessible = isAccessible ? '1' : '0';
    card.dataset.lockedReason = lockedReason.replace(/"/g, '&quot;');
    
    const lessonStatus = lesson.lesson_status;
    const statusClass = lessonStatus === 2
        ? 'completed'
        : (lessonStatus === 1 ? 'in-progress' : 'not-started');
    
    const statusText = lessonStatus === 2
        ? 'завершен'
        : (lessonStatus === 1 ? 'в процессе' : 'неначат');
    
    const adminButtons = (currentUserRole === 'admin' || currentUserRole === 'super_admin') ? `
        <button class="btn-action-icon btn-edit-icon" onclick="editLesson(${lesson.id}, event)" title="Изменить">✎</button>
        <button class="btn-action-icon btn-delete-icon" onclick="deleteLesson(${lesson.id}, event)" title="Удалить">×</button>
    ` : '';
    
    card.innerHTML = `
        <div class="card-content">
            <div class="card-header">
                <h3 class="card-title">${escapeHtml(lesson.title)}</h3>
            </div>
            <div class="card-main">
                <p class="card-description">${escapeHtml(lesson.description || '')}</p>
                ${!isAccessible ? `<p class="locked-reason">${escapeHtml(lockedReason)}</p>` : ''}
            </div>
            <div class="status-panel ${statusClass}">
                <div class="status-left">
                    <span class="status-text">${statusText}</span>
                    <button class="btn-action-icon btn-open-icon" onclick="typeof handleLessonOpenClick==='function'?handleLessonOpenClick(event):openLesson(${lesson.id})" title="Открыть урок">→</button>
                    <button class="btn-action-icon btn-question-icon" onclick="askQuestionAboutLesson(${lesson.id}, event)" title="Задать вопрос">?</button>
                </div>
                <div class="status-right">
                    ${adminButtons}
                </div>
            </div>
        </div>
    `;
    
    card.addEventListener('dblclick', (e) => {
        if (!e.target.closest('button')) {
            if (isAccessible) openLesson(lesson.id);
            else (typeof customAlert === 'function' ? customAlert : alert)(lockedReason, 'Материал недоступен');
        }
    });
    
    card.addEventListener('click', (e) => {
        if (!isAccessible && !e.target.closest('button')) {
            (typeof customAlert === 'function' ? customAlert : alert)(lockedReason, 'Материал недоступен');
        }
    });
    
    return card;
}

// Открыть урок
function openLesson(lessonId) {
    window.location.href = `/lessons-content-pg?lesson_id=${lessonId}`;
}

// Задать вопрос по уроку — переход на страницу вопросов с формой создания
function askQuestionAboutLesson(lessonId, event) {
    if (event) event.stopPropagation();
    window.location.href = `/questions-pg?tab=ask&lesson_id=${lessonId}`;
}

// Удалить урок (admin only - полное удаление)
async function deleteLesson(lessonId, event) {
    if (event) event.stopPropagation();
    
    if (currentUserRole !== 'admin' && currentUserRole !== 'super_admin') {
        showError('Требуются права администратора');
        return;
    }
    
    const confirmed = await customConfirm('Удалить этот урок? Он будет полностью удален из базы данных.');
    if (!confirmed) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/lessons/${lessonId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showSuccess('Урок удален');
            loadLessons();
        } else {
            showError(data.error || 'Ошибка при удалении урока');
        }
    } catch (error) {
        console.error('Ошибка:', error);
        showError('Не удалось удалить урок');
    }
}

// Редактировать урок (модальное окно с встроенным редактированием контента)
async function editLesson(lessonId, event) {
    if (event) event.stopPropagation();
    
    if (currentUserRole !== 'admin' && currentUserRole !== 'super_admin') {
        showError('Требуются права администратора');
        return;
    }
    
    try {
        const [lessonRes, blocksRes] = await Promise.all([
            fetch(`${API_BASE}/lessons/${lessonId}`),
            fetch(`${API_BASE}/lessons/${lessonId}/blocks`)
        ]);
        const lesson = await lessonRes.json();
        const blocksData = await blocksRes.json();
        
        if (!lessonRes.ok) throw new Error(lesson.error || 'Урок не найден');
        
        const apiBlocks = blocksData.blocks || [];
        lessonContentBlocks = apiBlocks.map(b => ({
            id: b.id,
            type: b.block_type,
            content: b.content || {},
            order: b.order
        }));
        originalBlockIds = new Set(apiBlocks.map(b => b.id));
        editingLessonId = lessonId;
        const createModal = document.getElementById('create-lesson-modal');
        if (createModal) createModal.style.display = 'none';
        openEditLessonModal(lesson);
    } catch (error) {
        console.error('Ошибка:', error);
        showError('Не удалось загрузить данные урока');
    }
}

// Открыть модальное окно редактирования урока (с конструктором контента)
function openEditLessonModal(lesson) {
    let editModal = document.getElementById('edit-lesson-modal');
    if (!editModal) {
        editModal = document.createElement('div');
        editModal.id = 'edit-lesson-modal';
        editModal.className = 'modal-overlay lesson-constructor-modal';
        document.body.appendChild(editModal);
    }
    
    editModal.innerHTML = `
        <div class="modal-container lesson-constructor-container">
            <div class="modal-header">
                <h2 class="modal-title">Изменить урок</h2>
                <button class="modal-close" onclick="closeEditLessonModal()" aria-label="Закрыть">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </button>
            </div>
            <div class="modal-body lesson-constructor-body">
                <form id="edit-lesson-form" onsubmit="event.preventDefault(); updateLesson(${lesson.id});">
                    <div class="form-group">
                        <label for="edit-lesson-title" class="form-label">Название <span class="required">*</span></label>
                        <input type="text" id="edit-lesson-title" class="form-input" value="${escapeHtml(lesson.title || '')}" required />
                    </div>
                    <div class="form-group">
                        <label for="edit-lesson-description" class="form-label">Описание</label>
                        <textarea id="edit-lesson-description" class="form-textarea" rows="2">${escapeHtml(lesson.description || '')}</textarea>
                    </div>
                    <div class="form-group">
                        <label for="edit-lesson-order" class="form-label">Порядок отображения</label>
                        <input type="number" id="edit-lesson-order" class="form-input" value="${lesson.lesson_number ?? lesson.order ?? 1}" min="1" />
                    </div>
                    <div class="content-constructor-section">
                        <div class="constructor-header">
                            <h3>Контент урока</h3>
                            <div class="add-content-dropdown">
                                <button type="button" class="btn-add-content" onclick="toggleContentMenu(event)">
                                    <span>+ Добавить контент</span>
                                    <span class="dropdown-arrow">▼</span>
                                </button>
                                <div class="content-menu edit-content-menu" id="edit-content-menu">
                                    <button type="button" class="content-menu-item" onclick="addContentBlock('heading')">
                                        <span class="menu-icon">📝</span> Заголовок
                                    </button>
                                    <button type="button" class="content-menu-item" onclick="addContentBlock('text')">
                                        <span class="menu-icon">📄</span> Текст
                                    </button>
                                    <button type="button" class="content-menu-item" onclick="addContentBlock('image')">
                                        <span class="menu-icon">🖼️</span> Изображение
                                    </button>
                                    <button type="button" class="content-menu-item" onclick="addContentBlock('video')">
                                        <span class="menu-icon">🎥</span> Видео
                                    </button>
                                    <button type="button" class="content-menu-item" onclick="addContentBlock('file')">
                                        <span class="menu-icon">📎</span> Файл
                                    </button>
                                    <button type="button" class="content-menu-item" onclick="addContentBlock('test')">
                                        <span class="menu-icon">🧪</span> Тест
                                    </button>
                                </div>
                            </div>
                        </div>
                        <div class="content-blocks-container" id="edit-content-blocks-container">
                            <p class="empty-blocks-message">Добавьте контент, используя меню выше</p>
                        </div>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn-cancel" onclick="closeEditLessonModal()">Отмена</button>
                <button type="submit" form="edit-lesson-form" class="btn-submit">Сохранить</button>
            </div>
        </div>
    `;
    editModal.style.display = 'flex';
    
    editModal.onclick = (e) => {
        if (e.target === editModal) closeEditLessonModal();
    };
    
    // toggleContentMenu ищет #content-menu, в режиме редактирования меню — #edit-content-menu
    const editMenu = document.getElementById('edit-content-menu');
    const addBtn = editModal.querySelector('.btn-add-content');
    if (addBtn && editMenu) {
        addBtn.onclick = (ev) => {
            ev.stopPropagation();
            editMenu.classList.toggle('show');
            document.addEventListener('click', function closeEditMenu(e) {
                if (!editMenu.contains(e.target) && !addBtn.contains(e.target)) {
                    editMenu.classList.remove('show');
                    document.removeEventListener('click', closeEditMenu);
                }
            });
        };
    }
    
    renderContentBlocks();
    initDragAndDrop();
}

// Закрыть модальное окно редактирования урока
function closeEditLessonModal() {
    const editModal = document.getElementById('edit-lesson-modal');
    if (editModal) editModal.style.display = 'none';
    editingLessonId = null;
    originalBlockIds = new Set();
}

// Обновить урок (метаданные + блоки контента)
async function updateLesson(lessonId) {
    const titleInput = document.getElementById('edit-lesson-title');
    const descriptionInput = document.getElementById('edit-lesson-description');
    const orderInput = document.getElementById('edit-lesson-order');
    
    const title = (titleInput?.value || '').trim();
    const description = (descriptionInput?.value || '').trim();
    const lessonNumber = parseInt(orderInput?.value || '1', 10);
    
    if (!title) {
        showError('Название урока обязательно');
        return;
    }

    // Предотвращаем двойной клик по "Сохранить"
    if (isUpdatingLesson) return;
    isUpdatingLesson = true;
    updateLessonAbortController = new AbortController();

    // Блокируем кнопку "Сохранить" в форме
    const submitBtn = document.querySelector('form#edit-lesson-form button[type="submit"]');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Сохранение...';
    }

    // Показываем модалку ожидания (как при создании)
    showLessonUpdateModal();

    try {
        const response = await fetch(`${API_BASE}/lessons/${lessonId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, description, lesson_number: lessonNumber }),
            signal: updateLessonAbortController.signal
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }
        
        // Синхронизация блоков контента
        const currentIds = new Set(lessonContentBlocks.map(b => typeof b.id === 'number' ? b.id : null).filter(Boolean));
        for (const origId of originalBlockIds) {
            if (!currentIds.has(origId)) {
                await fetch(`${API_BASE}/lessons/${lessonId}/blocks/${origId}`, { method: 'DELETE', signal: updateLessonAbortController.signal });
            }
        }
        for (let i = 0; i < lessonContentBlocks.length; i++) {
            const block = lessonContentBlocks[i];
            let content = block.content || {};
            if (block.file) {
                const formData = new FormData();
                formData.append('file', block.file);
                formData.append('type', block.type === 'image' ? 'images' : block.type === 'video' ? 'videos' : 'files');
                const uploadRes = await fetch(`${API_BASE}/lessons/${lessonId}/files`, { method: 'POST', body: formData, signal: updateLessonAbortController.signal });
                const uploadData = await uploadRes.json();
                if (uploadRes.ok) {
                    content = {
                        ...content,
                        url: uploadData.url,
                        filename: uploadData.filename,
                        stored_filename: uploadData.stored_filename
                    };
                    if (block.type === 'file') content.size = uploadData.size;
                    if (block.type === 'video') content.title = content.title || uploadData.filename;
                    if (block.type === 'image') content.alt = content.alt || uploadData.filename;
                    if (typeof content.url === 'string' && content.url.startsWith('blob:')) URL.revokeObjectURL(content.url);
                } else throw new Error(uploadData.error || 'Ошибка загрузки файла');
            }
            const payload = { block_type: block.type, content, order: i };
            const isExistingBlock = (typeof block.id === 'number') && originalBlockIds.has(block.id);
            if (isExistingBlock) {
                const res = await fetch(`${API_BASE}/lessons/${lessonId}/blocks/${block.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                    signal: updateLessonAbortController.signal
                });
                if (!res.ok) {
                    const err = await res.json().catch(() => ({}));
                    throw new Error(err.error || 'Не удалось обновить блок контента');
                }
            } else {
                const res = await fetch(`${API_BASE}/lessons/${lessonId}/blocks`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                    signal: updateLessonAbortController.signal
                });
                if (!res.ok) {
                    const err = await res.json().catch(() => ({}));
                    throw new Error(err.error || 'Не удалось создать блок контента');
                } else {
                    // Обновим id в памяти, чтобы дальнейшие сохранения работали корректно
                    const created = await res.json().catch(() => null);
                    if (created && typeof created.id === 'number') {
                        block.id = created.id;
                        originalBlockIds.add(created.id);
                    }
                }
            }
        }
        
        showSuccess('Урок обновлён');
        closeLessonUpdateModal();
        closeEditLessonModal();
        loadLessons();
    } catch (error) {
        console.error('Ошибка обновления урока:', error);
        if (error && (error.name === 'AbortError' || String(error).includes('AbortError'))) {
            // Уже показали сообщение в cancelLessonUpdate()
            return;
        }
        showError('Не удалось обновить урок');
        closeLessonUpdateModal();
    } finally {
        isUpdatingLesson = false;
        updateLessonAbortController = null;
        // Возвращаем кнопку "Сохранить", если модалка редактирования ещё открыта
        const btn = document.querySelector('form#edit-lesson-form button[type="submit"]');
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Сохранить';
        }
    }
}

// Утилиты
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showError(message) {
    const alertFn = typeof customAlert === 'function' ? customAlert : window.alert;
    alertFn(message, 'Ошибка');
}

function showSuccess(message) {
    const alertFn = typeof customAlert === 'function' ? customAlert : window.alert;
    alertFn(message, 'Успешно');
}

// Создание урока (admin)
async function createLesson() {
    if (currentUserRole !== 'admin' && currentUserRole !== 'super_admin') {
        showError('Требуются права администратора');
        return;
    }
    
    if (!currentCourseId) {
        showError('Выберите курс для создания урока');
        return;
    }
    
    const titleInput = document.getElementById('lesson-title');
    const descriptionInput = document.getElementById('lesson-description');
    const orderInput = document.getElementById('lesson-order');
    
    const title = (titleInput?.value || '').trim();
    const description = (descriptionInput?.value || '').trim();
    const order = parseInt(orderInput?.value || '0', 10);
    
    if (!title) {
        showError('Название урока обязательно');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/lessons`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                course_id: currentCourseId,
                title,
                description,
                order
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showSuccess('Урок создан');
            closeCreateLessonModal();
            loadLessons();
        } else {
            showError(data.error || 'Ошибка при создании урока');
        }
    } catch (error) {
        console.error('Ошибка создания урока:', error);
        showError('Не удалось создать урок');
    }
}

// Хранилище блоков контента для нового/редактируемого урока
let lessonContentBlocks = [];
let currentEditingBlockId = null;
// ID урока при редактировании (null при создании)
let editingLessonId = null;
// Исходные ID блоков при редактировании (для определения удалённых)
let originalBlockIds = new Set();

// Открыть модальное окно создания урока (конструктор)
function openCreateLessonModal() {
    if (!currentCourseId) {
        showError('Выберите курс для создания урока');
        return;
    }
    
    lessonContentBlocks = [];
    editingLessonId = null;
    originalBlockIds = new Set();
    
    let createModal = document.getElementById('create-lesson-modal');
    if (!createModal) {
        createModal = document.createElement('div');
        createModal.id = 'create-lesson-modal';
        createModal.className = 'modal-overlay lesson-constructor-modal';
        document.body.appendChild(createModal);
    }
    
    createModal.innerHTML = `
        <div class="modal-container lesson-constructor-container">
            <div class="modal-header">
                <h2 class="modal-title">Создать урок</h2>
                <button class="modal-close" onclick="closeCreateLessonModal()" aria-label="Закрыть">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </button>
            </div>
            <div class="modal-body lesson-constructor-body">
                    <form id="create-lesson-form" onsubmit="event.preventDefault(); event.stopPropagation(); createLessonWithContent(); return false;">
                    <div class="form-group">
                        <label for="lesson-title" class="form-label">Название <span class="required">*</span></label>
                        <input type="text" id="lesson-title" class="form-input" placeholder="Введите название урока" required />
                    </div>
                    <div class="form-group">
                        <label for="lesson-description" class="form-label">Описание</label>
                        <textarea id="lesson-description" class="form-textarea" rows="2" placeholder="Введите описание урока"></textarea>
                    </div>
                    
                    <div class="content-constructor-section">
                        <div class="constructor-header">
                            <h3>Контент урока</h3>
                            <div class="add-content-dropdown">
                                <button type="button" class="btn-add-content" onclick="toggleContentMenu(event)">
                                    <span>+ Добавить контент</span>
                                    <span class="dropdown-arrow">▼</span>
                                </button>
                                <div class="content-menu" id="content-menu">
                                    <button type="button" class="content-menu-item" onclick="addContentBlock('heading')">
                                        <span class="menu-icon">📝</span> Заголовок
                                    </button>
                                    <button type="button" class="content-menu-item" onclick="addContentBlock('text')">
                                        <span class="menu-icon">📄</span> Текст
                                    </button>
                                    <button type="button" class="content-menu-item" onclick="addContentBlock('image')">
                                        <span class="menu-icon">🖼️</span> Изображение
                                    </button>
                                    <button type="button" class="content-menu-item" onclick="addContentBlock('video')">
                                        <span class="menu-icon">🎥</span> Видео
                                    </button>
                                    <button type="button" class="content-menu-item" onclick="addContentBlock('file')">
                                        <span class="menu-icon">📎</span> Файл
                                    </button>
                                    <button type="button" class="content-menu-item" onclick="addContentBlock('test')">
                                        <span class="menu-icon">🧪</span> Тест
                                    </button>
                                </div>
                            </div>
                        </div>
                        <div class="content-blocks-container" id="content-blocks-container">
                            <p class="empty-blocks-message">Добавьте контент, используя меню выше</p>
                        </div>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn-cancel" onclick="closeCreateLessonModal()">Отмена</button>
                <button type="submit" form="create-lesson-form" class="btn-submit">Создать урок</button>
            </div>
        </div>
    `;
    createModal.style.display = 'flex';
    
    // Закрытие по клику на overlay
    createModal.addEventListener('click', (e) => {
        if (e.target === createModal) {
            closeCreateLessonModal();
        }
    });
    
    // Инициализация drag-and-drop
    initDragAndDrop();
}

// Закрыть модальное окно создания урока
function closeCreateLessonModal() {
    const createModal = document.getElementById('create-lesson-modal');
    if (createModal) {
        createModal.style.display = 'none';
        // Очищаем форму
        const titleInput = document.getElementById('lesson-title');
        const descriptionInput = document.getElementById('lesson-description');
        if (titleInput) titleInput.value = '';
        if (descriptionInput) descriptionInput.value = '';
        lessonContentBlocks = [];
        
        // Если урок не создается, разблокируем кнопку на странице
        if (!isCreatingLesson) {
            const createLessonBtn = document.getElementById('create-lesson-btn');
            if (createLessonBtn) {
                createLessonBtn.disabled = false;
                createLessonBtn.style.opacity = '1';
                createLessonBtn.style.cursor = 'pointer';
            }
        }
    }
}

// Переключить меню добавления контента
function toggleContentMenu(event) {
    event.stopPropagation();
    const menu = document.getElementById('content-menu');
    if (menu) {
        menu.classList.toggle('show');
    }
    
    // Закрытие при клике вне меню
    document.addEventListener('click', function closeMenu(e) {
        if (!menu.contains(e.target) && !e.target.closest('.btn-add-content')) {
            menu.classList.remove('show');
            document.removeEventListener('click', closeMenu);
        }
    });
}

// Добавить блок контента
function addContentBlock(type) {
    const blockId = Date.now();
    const block = {
        id: blockId,
        type: type,
        content: getDefaultContent(type),
        order: lessonContentBlocks.length
    };
    
    lessonContentBlocks.push(block);
    renderContentBlocks();
    
    // Закрываем меню (создание и редактирование)
    const menu = document.getElementById('content-menu');
    const editMenu = document.getElementById('edit-content-menu');
    if (menu) menu.classList.remove('show');
    if (editMenu) editMenu.classList.remove('show');
    
    // Если это файл/изображение/видео, открываем диалог загрузки
    if (type === 'image' || type === 'video' || type === 'file') {
        openFileUploadDialog(blockId, type);
    } else {
        // Для текста и заголовка сразу открываем редактирование
        editContentBlock(blockId);
    }
}

// Получить контент по умолчанию для типа блока (пустые поля при создании)
function getDefaultContent(type) {
    switch(type) {
        case 'heading':
            return { text: '' };
        case 'text':
            return { text: '' };
        case 'image':
            return { url: '', alt: '' };
        case 'video':
            return { url: '', title: '', attachments: [] };
        case 'file':
            return { filename: '', url: '' };
        case 'test':
            return { title: 'Тест', questions: [] };
        default:
            return {};
    }
}

function getBlocksContainer() {
    const id = editingLessonId ? 'edit-content-blocks-container' : 'content-blocks-container';
    return document.getElementById(id);
}

// Отобразить блоки контента
function renderContentBlocks() {
    const container = getBlocksContainer();
    if (!container) return;
    
    if (lessonContentBlocks.length === 0) {
        container.innerHTML = '<p class="empty-blocks-message">Добавьте контент, используя меню выше</p>';
        return;
    }
    
    container.innerHTML = '';
    
    lessonContentBlocks.forEach((block, index) => {
        const blockElement = createContentBlockElement(block, index);
        container.appendChild(blockElement);
    });
    
    // Инициализируем drag-and-drop после рендеринга
    initDragAndDrop();
}

// Создать элемент блока контента
function createContentBlockElement(block, index) {
    const div = document.createElement('div');
    div.className = 'content-block-item';
    div.dataset.blockId = block.id;
    div.draggable = true;
    
    let contentHtml = '';
    switch(block.type) {
        case 'heading':
            contentHtml = `<h4 class="block-preview-heading">${escapeHtml(block.content.text || 'Заголовок')}</h4>`;
            break;
        case 'text':
            contentHtml = `<p class="block-preview-text">${escapeHtml(block.content.html || block.content.text || 'Текст')}</p>`;
            break;
        case 'image':
            contentHtml = block.content.url 
                ? `<img src="${escapeHtml(block.content.url)}" alt="${escapeHtml(block.content.alt || '')}" class="block-preview-image" />`
                : `<div class="block-preview-placeholder">🖼️ Изображение</div>`;
            break;
        case 'video':
            const attachmentsCount = (block.content.attachments || []).length;
            const attachmentsBadge = attachmentsCount > 0 ? ` <span class="attachments-badge">(${attachmentsCount})</span>` : '';
            contentHtml = block.content.url
                ? `<div class="block-preview-video">🎥 ${escapeHtml(block.content.title || 'Видео')}${attachmentsBadge}</div>`
                : `<div class="block-preview-placeholder">🎥 Видео</div>`;
            break;
        case 'file':
            contentHtml = block.content.filename
                ? `<div class="block-preview-file">📎 ${escapeHtml(block.content.filename)}</div>`
                : `<div class="block-preview-placeholder">📎 Файл</div>`;
            break;
        case 'test':
            contentHtml = `<div class="block-preview-test">🧪 ${escapeHtml(block.content.title || 'Тест')}</div>`;
            break;
    }
    
    div.innerHTML = `
        <div class="block-handle">☰</div>
        <div class="block-content">${contentHtml}</div>
        <div class="block-actions">
            <button type="button" class="btn-edit-block-small" onclick="editContentBlock(${block.id})" title="Редактировать">✏</button>
            <button type="button" class="btn-delete-block-small" onclick="removeContentBlock(${block.id})" title="Удалить">🗑</button>
        </div>
    `;
    
    return div;
}

// Удалить блок контента
function removeContentBlock(blockId) {
    lessonContentBlocks = lessonContentBlocks.filter(b => b.id !== blockId);
    renderContentBlocks();
}

// Редактировать блок контента
function editContentBlock(blockId) {
    const block = lessonContentBlocks.find(b => b.id === blockId);
    if (!block) return;
    currentEditingBlockId = blockId;
    
    // Создаем модальное окно для редактирования
    let editModal = document.getElementById('edit-block-modal');
    if (!editModal) {
        editModal = document.createElement('div');
        editModal.id = 'edit-block-modal';
        editModal.className = 'modal-overlay';
        document.body.appendChild(editModal);
    }
    
    let modalContent = '';
    
    switch(block.type) {
        case 'heading':
            modalContent = `
                <div class="modal-container">
                    <div class="modal-header">
                        <h2 class="modal-title">Редактировать заголовок</h2>
                        <button class="modal-close" onclick="closeEditBlockModal()">×</button>
                    </div>
                    <div class="modal-body">
                        <div class="form-group">
                            <label for="block-heading-text" class="form-label">Заголовок <span class="required">*</span></label>
                            <input type="text" id="block-heading-text" class="form-input" placeholder="Введите заголовок" value="${escapeHtml(block.content.text || '')}" required />
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn-cancel" onclick="closeEditBlockModal()">Отмена</button>
                        <button type="button" class="btn-submit" onclick="saveBlockEdit(${blockId})">Сохранить</button>
                    </div>
                </div>
            `;
            break;
        case 'text': {
            const textSize = block.content.size || 'md';
            const textAlign = block.content.align || 'left';
            const textColor = block.content.color || '#4f4f4f';
            const textLinkUrl = block.content.linkUrl || '';
            modalContent = `
                <div class="modal-container">
                    <div class="modal-header">
                        <h2 class="modal-title">Редактировать текст</h2>
                        <button class="modal-close" onclick="closeEditBlockModal()">×</button>
                    </div>
                    <div class="modal-body">
                        <div class="form-group">
                            <label for="block-text-content" class="form-label">Текст <span class="required">*</span></label>
                            <textarea id="block-text-content" class="form-textarea" rows="6" placeholder="Введите текст..." required>${escapeHtml(block.content.html || block.content.text || '')}</textarea>
                        </div>
                        <div class="text-format-options form-group">
                            <fieldset>
                                <legend>Размер</legend>
                                <select id="block-text-size">
                                    <option value="xs" ${textSize === 'xs' ? 'selected' : ''}>Очень маленький</option>
                                    <option value="sm" ${textSize === 'sm' ? 'selected' : ''}>Маленький</option>
                                    <option value="md" ${textSize === 'md' ? 'selected' : ''}>Средний</option>
                                    <option value="lg" ${textSize === 'lg' ? 'selected' : ''}>Большой</option>
                                    <option value="xl" ${textSize === 'xl' ? 'selected' : ''}>Очень большой</option>
                                </select>
                            </fieldset>
                            <fieldset>
                                <legend>Выделение</legend>
                                <label><input type="checkbox" id="block-text-bold" ${block.content.bold ? 'checked' : ''} /> Жирный</label>
                                <label><input type="checkbox" id="block-text-italic" ${block.content.italic ? 'checked' : ''} /> Курсив</label>
                                <label>Цвет: <input type="color" id="block-text-color" value="${escapeHtml(textColor)}" title="Выбрать цвет" /></label>
                                <label><input type="checkbox" id="block-text-as-link" ${textLinkUrl ? 'checked' : ''} /> Как ссылка</label>
                                <input type="url" id="block-text-link-url" placeholder="URL ссылки" value="${escapeHtml(textLinkUrl)}" style="display:${textLinkUrl ? 'block' : 'none'}; width:100%; margin-top:4px;" />
                            </fieldset>
                            <fieldset>
                                <legend>Позиционирование</legend>
                                <label><input type="radio" name="block-text-align" value="left" ${textAlign === 'left' ? 'checked' : ''} /> Слева</label>
                                <label><input type="radio" name="block-text-align" value="center" ${textAlign === 'center' ? 'checked' : ''} /> По центру</label>
                                <label><input type="radio" name="block-text-align" value="right" ${textAlign === 'right' ? 'checked' : ''} /> Справа</label>
                            </fieldset>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn-cancel" onclick="closeEditBlockModal()">Отмена</button>
                        <button type="button" class="btn-submit" onclick="saveBlockEdit(${blockId})">Сохранить</button>
                    </div>
                </div>
            `;
            break;
        }
        case 'video':
            const attachmentsHtml = (block.content.attachments || []).map((att, idx) => 
                `<div class="attachment-item" data-index="${idx}">
                    <span>${escapeHtml(att.name || att.filename || 'Файл')}</span>
                    <button type="button" class="btn-remove-attachment" onclick="removeVideoAttachment(${blockId}, ${idx})">×</button>
                </div>`
            ).join('');
            
            modalContent = `
                <div class="modal-container">
                    <div class="modal-header">
                        <h2 class="modal-title">Редактировать видео</h2>
                        <button class="modal-close" onclick="closeEditBlockModal()">×</button>
                    </div>
                    <div class="modal-body">
                        <div class="form-group">
                            <label for="block-video-url" class="form-label">URL видео <span class="required">*</span></label>
                            <input type="url" id="block-video-url" class="form-input" value="${escapeHtml(block.content.url || '')}" placeholder="https://rutube.ru/play/embed/..." required />
                        </div>
                        <div class="form-group">
                            <label for="block-video-title" class="form-label">Название видео</label>
                            <input type="text" id="block-video-title" class="form-input" value="${escapeHtml(block.content.title || '')}" />
                        </div>
                        <div class="form-group">
                            <label class="form-label">Прикрепленные файлы</label>
                            <div class="attachments-container" id="attachments-container-${blockId}">
                                ${attachmentsHtml || '<p class="no-attachments">Файлы не прикреплены</p>'}
                            </div>
                            <button type="button" class="btn-add-attachment" onclick="addVideoAttachment(${blockId})">+ Добавить файл</button>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn-cancel" onclick="closeEditBlockModal()">Отмена</button>
                        <button type="button" class="btn-submit" onclick="saveBlockEdit(${blockId})">Сохранить</button>
                    </div>
                </div>
            `;
            break;
        case 'image':
            modalContent = `
                <div class="modal-container">
                    <div class="modal-header">
                        <h2 class="modal-title">Редактировать изображение</h2>
                        <button class="modal-close" onclick="closeEditBlockModal()">×</button>
                    </div>
                    <div class="modal-body">
                        <div class="form-group">
                            <label for="block-image-url" class="form-label">URL изображения</label>
                            <input type="url" id="block-image-url" class="form-input" value="${escapeHtml(block.content.url || '')}" />
                        </div>
                        <div class="form-group">
                            <label class="form-label">Или загрузите файл</label>
                            <input type="file" id="block-image-file" accept="image/*" class="form-input" />
                        </div>
                        <div class="form-group">
                            <label for="block-image-alt" class="form-label">Альтернативный текст</label>
                            <input type="text" id="block-image-alt" class="form-input" value="${escapeHtml(block.content.alt || '')}" />
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn-cancel" onclick="closeEditBlockModal()">Отмена</button>
                        <button type="button" class="btn-submit" onclick="saveBlockEdit(${blockId})">Сохранить</button>
                    </div>
                </div>
            `;
            break;
        case 'file':
            modalContent = `
                <div class="modal-container">
                    <div class="modal-header">
                        <h2 class="modal-title">Редактировать файл</h2>
                        <button class="modal-close" onclick="closeEditBlockModal()">×</button>
                    </div>
                    <div class="modal-body">
                        <div class="form-group">
                            <label for="block-file-url" class="form-label">URL файла</label>
                            <input type="url" id="block-file-url" class="form-input" value="${escapeHtml(block.content.url || '')}" />
                        </div>
                        <div class="form-group">
                            <label class="form-label">Или загрузите файл</label>
                            <input type="file" id="block-file-file" class="form-input" />
                        </div>
                        <div class="form-group">
                            <label for="block-file-name" class="form-label">Название файла</label>
                            <input type="text" id="block-file-name" class="form-input" value="${escapeHtml(block.content.filename || '')}" />
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn-cancel" onclick="closeEditBlockModal()">Отмена</button>
                        <button type="button" class="btn-submit" onclick="saveBlockEdit(${blockId})">Сохранить</button>
                    </div>
                </div>
            `;
            break;
        case 'test':
            modalContent = `
                <div class="modal-container modal-container--wide">
                    <div class="modal-header">
                        <h2 class="modal-title">Редактировать тест</h2>
                        <button class="modal-close" onclick="closeEditBlockModal()">×</button>
                    </div>
                    <div class="modal-body">
                        <div class="test-edit-tabs" role="tablist" aria-label="Редактирование теста">
                            <button type="button" class="test-edit-tab active" data-tab="settings" role="tab" aria-selected="true">Настройки</button>
                            <button type="button" class="test-edit-tab" data-tab="questions" role="tab" aria-selected="false">Вопросы</button>
                        </div>

                        <div class="test-edit-content">
                            <div class="test-edit-panel active" data-panel="settings" role="tabpanel">
                                <div class="form-group">
                                    <label class="form-label">Название теста</label>
                                    <input type="text" id="edit-test-title" class="form-input" value="${escapeHtml(block.content.title || 'Тест')}" />
                                </div>
                                <div class="form-group">
                                    <label class="form-label">Порог прохождения (%)</label>
                                    <input type="number" id="edit-test-pass-percent" class="form-input" min="1" max="100" value="70" />
                                </div>
                                <div class="form-group inline">
                                    <label class="form-check">
                                        <input type="checkbox" id="edit-test-limit-attempts" />
                                        <span>Ограничить количество попыток</span>
                                    </label>
                                    <div class="form-inline-field">
                                        <label class="form-label-inline" for="edit-test-max-attempts">Попыток</label>
                                        <input type="number" id="edit-test-max-attempts" class="form-input small" min="1" value="3" />
                                    </div>
                                </div>
                                <div class="form-group">
                                    <label class="form-label">Ограничение по времени (минуты, 0 — без ограничения)</label>
                                    <input type="number" id="edit-test-time-limit" class="form-input" min="0" value="0" />
                                </div>
                                <div class="form-group">
                                    <label class="form-label">Тип теста</label>
                                    <div class="test-type-row" role="radiogroup" aria-label="Тип теста">
                                        <label class="form-radio">
                                            <input type="radio" name="edit-test-type" id="edit-test-type-permanent" value="permanent" checked />
                                            <span>Постоянный</span>
                                        </label>
                                        <label class="form-radio">
                                            <input type="radio" name="edit-test-type" id="edit-test-type-temporary" value="temporary" />
                                            <span>Временный</span>
                                        </label>
                                    </div>
                                    <div class="test-availability" id="edit-test-availability-fields" style="display:none;">
                                        <div class="form-group">
                                            <label class="form-label">Доступен с</label>
                                            <input type="datetime-local" id="edit-test-available-from" class="form-input" />
                                        </div>
                                        <div class="form-group">
                                            <label class="form-label">Доступен до</label>
                                            <input type="datetime-local" id="edit-test-available-until" class="form-input" />
                                        </div>
                                    </div>
                                </div>
                                <div class="form-group inline">
                                    <label class="form-check">
                                        <input type="checkbox" id="edit-test-shuffle-questions" />
                                        <span>Перемешивать вопросы</span>
                                    </label>
                                    <label class="form-check">
                                        <input type="checkbox" id="edit-test-shuffle-options" />
                                        <span>Перемешивать ответы</span>
                                    </label>
                                </div>
                            </div>

                            <div class="test-edit-panel" data-panel="questions" role="tabpanel">
                                <div class="test-questions-header">
                                    <div class="test-questions-title">Вопросы теста</div>
                                    <button type="button" class="btn-add-question" id="edit-btn-add-question">+ Создать вопрос</button>
                                </div>
                                <div class="test-questions-layout">
                                    <div class="test-questions-list" id="edit-test-questions-list"></div>
                                    <div class="test-question-editor" id="edit-test-question-editor"></div>
                                </div>
                                <div class="form-error" id="edit-test-question-error" style="display:none;"></div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn-cancel" onclick="closeEditBlockModal()">Отмена</button>
                        <button type="button" class="btn-submit" onclick="saveBlockEdit(${blockId})">Сохранить</button>
                    </div>
                </div>
            `;
            break;
    }
    
    editModal.innerHTML = modalContent;
    editModal.style.display = 'flex';

    // Инициализация UI редактирования теста
    if (block.type === 'test') {
        initTestEditModal(block);
    }
    
    // Закрытие по клику на overlay
    editModal.addEventListener('click', (e) => {
        if (e.target === editModal) {
            closeEditBlockModal();
        }
    });
    
    // Обработка загрузки файлов
    if (block.type === 'image') {
        const fileInput = document.getElementById('block-image-file');
        if (fileInput) {
            fileInput.addEventListener('change', (e) => {
                const file = e.target.files[0];
                if (file) {
                    const urlInput = document.getElementById('block-image-url');
                    if (urlInput) {
                        urlInput.value = URL.createObjectURL(file);
                    }
                }
            });
        }
    } else if (block.type === 'file') {
        const fileInput = document.getElementById('block-file-file');
        if (fileInput) {
            fileInput.addEventListener('change', (e) => {
                const file = e.target.files[0];
                if (file) {
                    const urlInput = document.getElementById('block-file-url');
                    const nameInput = document.getElementById('block-file-name');
                    if (urlInput) urlInput.value = URL.createObjectURL(file);
                    if (nameInput) nameInput.value = file.name;
                }
            });
        }
    } else if (block.type === 'text') {
        const asLinkCheck = document.getElementById('block-text-as-link');
        const linkUrlInput = document.getElementById('block-text-link-url');
        if (asLinkCheck && linkUrlInput) {
            asLinkCheck.addEventListener('change', function() {
                linkUrlInput.style.display = this.checked ? 'block' : 'none';
            });
        }
    }
}

// Сохранить изменения блока
function saveBlockEdit(blockId) {
    const block = lessonContentBlocks.find(b => b.id === blockId);
    if (!block) return;
    
    switch(block.type) {
        case 'heading':
            const headingText = document.getElementById('block-heading-text');
            if (headingText && headingText.value.trim()) {
                block.content.text = headingText.value.trim();
            }
            break;
        case 'text': {
            const textContent = document.getElementById('block-text-content');
            const textAlignEl = document.querySelector('input[name="block-text-align"]:checked');
            if (textContent && textContent.value.trim()) {
                block.content.html = textContent.value.trim();
                block.content.text = textContent.value.trim();
                block.content.size = (document.getElementById('block-text-size') && document.getElementById('block-text-size').value) || 'md';
                block.content.bold = document.getElementById('block-text-bold') ? document.getElementById('block-text-bold').checked : false;
                block.content.italic = document.getElementById('block-text-italic') ? document.getElementById('block-text-italic').checked : false;
                block.content.color = document.getElementById('block-text-color') ? document.getElementById('block-text-color').value : '';
                const asLink = document.getElementById('block-text-as-link') && document.getElementById('block-text-as-link').checked;
                block.content.linkUrl = asLink && document.getElementById('block-text-link-url') ? document.getElementById('block-text-link-url').value.trim() : '';
                block.content.align = textAlignEl ? textAlignEl.value : 'left';
            }
            break;
        }
        case 'video':
            const videoUrl = document.getElementById('block-video-url');
            const videoTitle = document.getElementById('block-video-title');
            if (videoUrl && videoUrl.value.trim()) {
                block.content.url = videoUrl.value.trim();
            }
            if (videoTitle) {
                block.content.title = videoTitle.value.trim();
            }
            // Прикрепления уже обновлены через функции addVideoAttachment/removeVideoAttachment
            break;
        case 'image':
            const imageUrl = document.getElementById('block-image-url');
            const imageAlt = document.getElementById('block-image-alt');
            if (imageUrl && imageUrl.value.trim()) {
                block.content.url = imageUrl.value.trim();
            }
            if (imageAlt) {
                block.content.alt = imageAlt.value.trim();
            }
            break;
        case 'file':
            const fileUrl = document.getElementById('block-file-url');
            const fileName = document.getElementById('block-file-name');
            if (fileUrl && fileUrl.value.trim()) {
                block.content.url = fileUrl.value.trim();
            }
            if (fileName) {
                block.content.filename = fileName.value.trim();
            }
            break;
        case 'test': {
            // Модалка теста всегда использует id с префиксом edit-
            const prefix = 'edit-';
            const titleInput = document.getElementById(prefix + 'test-title');
            const passInput = document.getElementById(prefix + 'test-pass-percent');
            const limitAttempts = document.getElementById(prefix + 'test-limit-attempts');
            const maxAttempts = document.getElementById(prefix + 'test-max-attempts');
            const timeLimit = document.getElementById(prefix + 'test-time-limit');
            const availableFrom = document.getElementById(prefix + 'test-available-from');
            const availableUntil = document.getElementById(prefix + 'test-available-until');
            const shuffleQuestions = document.getElementById(prefix + 'test-shuffle-questions');
            const shuffleOptions = document.getElementById(prefix + 'test-shuffle-options');

            const newTitle = titleInput ? titleInput.value.trim() : '';
            const settings = {};
            if (passInput && passInput.value) settings.pass_percent = parseInt(passInput.value, 10);
            settings.limit_attempts = !!(limitAttempts && limitAttempts.checked);
            if (settings.limit_attempts && maxAttempts && maxAttempts.value) {
                const v = parseInt(maxAttempts.value, 10);
                if (!isNaN(v) && v > 0) settings.max_attempts = v;
            } else if (!settings.limit_attempts) {
                settings.max_attempts = null;
            }
            if (timeLimit && timeLimit.value) {
                const minutes = parseInt(timeLimit.value, 10);
                if (!isNaN(minutes) && minutes > 0) settings.time_limit_seconds = minutes * 60;
            } else {
                settings.time_limit_seconds = null;
            }
            if (availableFrom && availableFrom.value) settings.available_from = availableFrom.value;
            if (availableUntil && availableUntil.value) settings.available_until = availableUntil.value;
            if (shuffleQuestions) settings.shuffle_questions = shuffleQuestions.checked;
            if (shuffleOptions) settings.shuffle_options = shuffleOptions.checked;

            // Вопросы уже находятся в block.content.questions (мы изменяем их в редакторе).
            let questions = Array.isArray(block.content.questions) ? block.content.questions : [];
            questions = questions.filter(q => q && typeof q === 'object' && (q.text || '').trim());
            if (questions.length === 0) {
                showError('Добавьте хотя бы один вопрос в тест');
                return;
            }

            // Базовая валидация вопросов, чтобы не сохранять битый тест
            for (const q of questions) {
                const t = (q.answer_type || (q.multiple ? 'multiple' : 'single') || 'single').toLowerCase();
                const pts = parseInt(String(q.points || '1'), 10);
                if (isNaN(pts) || pts <= 0) {
                    showError('Баллы в вопросах должны быть положительным числом');
                    return;
                }
                if (t === 'input') {
                    const acc = Array.isArray(q.accepted_answers) ? q.accepted_answers.filter(Boolean) : [];
                    if (!acc.length) {
                        showError('Для вопроса с вводом текста укажите хотя бы один допустимый ответ');
                        return;
                    }
                } else {
                    const opts = Array.isArray(q.options) ? q.options.map((s) => (s || '').trim()).filter(Boolean) : [];
                    if (!opts.length) {
                        showError('У каждого вопроса с вариантами должен быть хотя бы один вариант ответа');
                        return;
                    }
                    if (t === 'multiple') {
                        const ca = Array.isArray(q.correct_answer) ? q.correct_answer : [];
                        if (!ca.length) {
                            showError('В вопросах с несколькими вариантами отметьте хотя бы один правильный вариант');
                            return;
                        }
                    } else {
                        const ca = q.correct_answer;
                        if (!Number.isFinite(Number(ca))) {
                            showError('В вопросах с одним вариантом должен быть выбран один правильный ответ');
                            return;
                        }
                    }
                }
            }

            block.content.title = newTitle || 'Тест';
            block.content.settings = settings;
            block.content.questions = questions;
            break;
        }
    }

    // Немедленно сохраняем блок в API, чтобы настройки (таймер, попытки и т.д.) применились
    if (editingLessonId && typeof block.id === 'number') {
        const payload = { block_type: block.type, content: block.content, order: block.order ?? 0 };
        fetch(`${API_BASE}/lessons/${editingLessonId}/blocks/${block.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
            .then(async (res) => {
                const data = await res.json().catch(() => ({}));
                if (!res.ok) {
                    showError(data.error || 'Не удалось сохранить блок');
                } else {
                    showSuccess('Изменения сохранены');
                }
            })
            .catch(() => showError('Ошибка сети при сохранении блока'));
    }
    
    closeEditBlockModal();
    renderContentBlocks();
}

// Закрыть модальное окно редактирования блока
function closeEditBlockModal() {
    const editModal = document.getElementById('edit-block-modal');
    if (editModal) {
        editModal.style.display = 'none';
    }
    currentEditingBlockId = null;
}

// ---------------- Редактор теста в модалке урока (all-lessons-pg) ----------------

function initTestEditModal(block) {
    const tabs = document.querySelectorAll('.test-edit-tab');
    const panels = document.querySelectorAll('.test-edit-panel');
    const addQuestionBtn = document.getElementById('edit-btn-add-question');
    const listEl = document.getElementById('edit-test-questions-list');
    const editorEl = document.getElementById('edit-test-question-editor');
    const errorEl = document.getElementById('edit-test-question-error');

    const targetBlock = lessonContentBlocks.find((b) => b.id === block.id) || block;
    if (!targetBlock.content) targetBlock.content = {};
    if (!Array.isArray(targetBlock.content.questions)) targetBlock.content.questions = [];

    // Инициализация полей настроек теста из модели
    const settings = (targetBlock.content.settings && typeof targetBlock.content.settings === 'object')
        ? targetBlock.content.settings
        : {};
    const titleEl = document.getElementById('edit-test-title');
    const passEl = document.getElementById('edit-test-pass-percent');
    const limitAttemptsEl = document.getElementById('edit-test-limit-attempts');
    const maxAttemptsEl = document.getElementById('edit-test-max-attempts');
    const timeLimitEl = document.getElementById('edit-test-time-limit');
    const availableFromEl = document.getElementById('edit-test-available-from');
    const availableUntilEl = document.getElementById('edit-test-available-until');
    const shuffleQuestionsEl = document.getElementById('edit-test-shuffle-questions');
    const shuffleOptionsEl = document.getElementById('edit-test-shuffle-options');
    const typePermanentEl = document.getElementById('edit-test-type-permanent');
    const typeTemporaryEl = document.getElementById('edit-test-type-temporary');
    const availabilityWrap = document.getElementById('edit-test-availability-fields');

    function toIntOr(value, fallback) {
        const n = parseInt(String(value ?? ''), 10);
        return Number.isFinite(n) ? n : fallback;
    }
    function toBool(value, fallback = false) {
        if (typeof value === 'boolean') return value;
        if (typeof value === 'string') return value.trim().toLowerCase() === 'true';
        if (typeof value === 'number') return value !== 0;
        return fallback;
    }
    function applyTestTypeUI() {
        const isTemporary = !!typeTemporaryEl?.checked;
        if (availabilityWrap) availabilityWrap.style.display = isTemporary ? 'block' : 'none';
        if (!isTemporary) {
            if (availableFromEl) availableFromEl.value = '';
            if (availableUntilEl) availableUntilEl.value = '';
        }
    }
    function applyAttemptsUI() {
        const enabled = !!limitAttemptsEl?.checked;
        if (maxAttemptsEl) {
            maxAttemptsEl.disabled = !enabled;
        }
    }

    if (titleEl && typeof targetBlock.content.title === 'string') titleEl.value = targetBlock.content.title || 'Тест';
    if (passEl) passEl.value = String(toIntOr(settings.pass_percent, 70));
    if (limitAttemptsEl) limitAttemptsEl.checked = toBool(settings.limit_attempts, false);
    if (maxAttemptsEl) maxAttemptsEl.value = settings.max_attempts != null ? String(toIntOr(settings.max_attempts, 3)) : '3';
    if (timeLimitEl) {
        const seconds = toIntOr(settings.time_limit_seconds, 0);
        const minutes = Math.max(0, Math.round(seconds / 60));
        timeLimitEl.value = String(minutes);
    }
    if (availableFromEl && typeof settings.available_from === 'string') availableFromEl.value = settings.available_from;
    if (availableUntilEl && typeof settings.available_until === 'string') availableUntilEl.value = settings.available_until;
    if (shuffleQuestionsEl) shuffleQuestionsEl.checked = toBool(settings.shuffle_questions, false);
    if (shuffleOptionsEl) shuffleOptionsEl.checked = toBool(settings.shuffle_options, false);

    // Тип теста: если есть любые даты доступности — считаем «временный»
    const isTemporaryFromModel = !!(settings.available_from || settings.available_until);
    if (typePermanentEl && typeTemporaryEl) {
        typeTemporaryEl.checked = isTemporaryFromModel;
        typePermanentEl.checked = !isTemporaryFromModel;
    }
    applyTestTypeUI();
    applyAttemptsUI();

    typePermanentEl?.addEventListener('change', applyTestTypeUI);
    typeTemporaryEl?.addEventListener('change', applyTestTypeUI);
    limitAttemptsEl?.addEventListener('change', applyAttemptsUI);

    let activeIndex = 0;

    function setError(msg) {
        if (!errorEl) return;
        if (!msg) {
            errorEl.style.display = 'none';
            errorEl.textContent = '';
        } else {
            errorEl.style.display = 'block';
            errorEl.textContent = msg;
        }
    }

    function activateTab(tabName) {
        tabs.forEach((btn) => {
            const isActive = btn.dataset.tab === tabName;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
        });
        panels.forEach((p) => p.classList.toggle('active', p.dataset.panel === tabName));
    }

    tabs.forEach((btn) => {
        btn.addEventListener('click', () => activateTab(btn.dataset.tab || 'settings'));
    });

    function renderQuestionsList() {
        if (!listEl) return;
        setError('');
        const questions = targetBlock.content.questions || [];
        if (!questions.length) {
            listEl.innerHTML = `<div class="test-questions-empty">Пока нет ни одного вопроса. Нажмите «Создать вопрос».</div>`;
            if (editorEl) editorEl.innerHTML = `<div class="test-question-empty">Выберите вопрос слева или создайте новый.</div>`;
            return;
        }

        listEl.innerHTML = '';
        questions.forEach((q, idx) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'test-question-item' + (idx === activeIndex ? ' active' : '');
            btn.dataset.index = String(idx);
            const title = (q && typeof q === 'object' ? (q.text || '') : '') || '';
            btn.innerHTML = `
                <div class="test-question-item__num">Вопрос ${idx + 1}</div>
                <div class="test-question-item__text">${escapeHtml(title.trim() || 'Без текста')}</div>
            `;
            btn.addEventListener('click', () => {
                activeIndex = idx;
                renderQuestionsList();
                renderActiveQuestion();
            });
            listEl.appendChild(btn);
        });
    }

    function ensureSingleCorrect(optionsListEl, changedCb) {
        if (!optionsListEl || !changedCb || !changedCb.checked) return;
        const all = optionsListEl.querySelectorAll('input[type="checkbox"].test-opt-correct');
        all.forEach((cb) => {
            if (cb !== changedCb) cb.checked = false;
        });
    }

    function renderActiveQuestion() {
        if (!editorEl) return;
        setError('');
        const questions = targetBlock.content.questions || [];
        const q = questions[activeIndex];
        if (!q) {
            editorEl.innerHTML = `<div class="test-question-empty">Выберите вопрос слева или создайте новый.</div>`;
            return;
        }

        const answerType = (q.answer_type || (q.multiple ? 'multiple' : 'single') || 'single').toLowerCase();
        const points = typeof q.points === 'number' && q.points > 0 ? q.points : parseInt(String(q.points || '1'), 10) || 1;

        editorEl.innerHTML = `
            <div class="test-question-editor__header">
                <div class="test-question-editor__title">Редактирование вопроса ${activeIndex + 1}</div>
                <button type="button" class="test-question-delete-btn" id="edit-test-delete-question">Удалить</button>
            </div>

            <div class="form-group">
                <label class="form-label">Текст вопроса <span class="required">*</span></label>
                <textarea id="edit-test-q-text" class="form-textarea" rows="3" placeholder="Введите формулировку вопроса">${escapeHtml(q.text || '')}</textarea>
            </div>

            <div class="form-group inline">
                <div>
                    <label class="form-label">Тип ответа</label>
                    <select id="edit-test-q-type" class="form-input">
                        <option value="single" ${answerType === 'single' ? 'selected' : ''}>Один вариант</option>
                        <option value="multiple" ${answerType === 'multiple' ? 'selected' : ''}>Несколько вариантов</option>
                        <option value="input" ${answerType === 'input' ? 'selected' : ''}>Ввод текста</option>
                    </select>
                </div>
                <div>
                    <label class="form-label">Баллы</label>
                    <input type="number" id="edit-test-q-points" class="form-input small" min="1" value="${points}" />
                </div>
            </div>

            <div class="test-q-answers" id="edit-test-q-answers"></div>
        `;

        const textEl = document.getElementById('edit-test-q-text');
        const typeEl = document.getElementById('edit-test-q-type');
        const pointsEl = document.getElementById('edit-test-q-points');
        const deleteBtn = document.getElementById('edit-test-delete-question');
        const answersWrap = document.getElementById('edit-test-q-answers');

        function updateModelFromInputs() {
            q.text = (textEl?.value || '').trim();
            const rawPoints = parseInt(pointsEl?.value || '1', 10);
            q.points = !isNaN(rawPoints) && rawPoints > 0 ? rawPoints : 1;
        }

        function renderAnswersUI() {
            const t = (typeEl?.value || 'single').toLowerCase();
            if (!answersWrap) return;

            if (t === 'input') {
                const accepted = Array.isArray(q.accepted_answers) ? q.accepted_answers : [];
                answersWrap.innerHTML = `
                    <div class="form-group">
                        <label class="form-label">Допустимые ответы (через запятую) <span class="required">*</span></label>
                        <input type="text" id="edit-test-q-accepted" class="form-input" placeholder="например: да, согласен, верно" value="${escapeHtml(accepted.join(', '))}" />
                    </div>
                `;
                const accEl = document.getElementById('edit-test-q-accepted');
                accEl?.addEventListener('input', () => {
                    const raw = (accEl.value || '').trim();
                    q.accepted_answers = raw ? raw.split(',').map((s) => s.trim()).filter(Boolean) : [];
                    q.answer_type = 'input';
                    delete q.options;
                    delete q.correct_answer;
                    q.multiple = false;
                });
                return;
            }

            const isMultiple = t === 'multiple';
            const options = Array.isArray(q.options) ? q.options : [];
            const correct = q.correct_answer;
            const correctSet = new Set(
                Array.isArray(correct) ? correct.map((n) => Number(n)).filter((n) => Number.isFinite(n)) :
                (Number.isFinite(Number(correct)) ? [Number(correct)] : [])
            );

            answersWrap.innerHTML = `
                <div class="test-q-options">
                    <div class="test-q-options__header">
                        <div class="test-q-options__title">Варианты ответа <span class="required">*</span></div>
                        <button type="button" class="btn-add-option" id="edit-test-add-option">+ Добавить вариант</button>
                    </div>
                    <div class="test-q-options__list" id="edit-test-options-list"></div>
                    <div class="test-q-options__hint">Отметьте правильные ответы (для одного варианта — один, для нескольких — несколько).</div>
                </div>
            `;

            const list = document.getElementById('edit-test-options-list');
            const addBtn = document.getElementById('edit-test-add-option');

            function syncCorrectFromDOM() {
                if (!list) return;
                const rows = list.querySelectorAll('.test-opt-row');
                const picked = [];
                rows.forEach((row, idx) => {
                    const cb = row.querySelector('input.test-opt-correct');
                    if (cb && cb.checked) picked.push(idx);
                });
                q.correct_answer = isMultiple ? picked : (picked[0] ?? 0);
            }

            function addRow(value, checked) {
                if (!list) return;
                const row = document.createElement('div');
                row.className = 'test-opt-row';
                row.innerHTML = `
                    <input type="text" class="form-input test-opt-text" placeholder="Текст варианта" value="${escapeHtml(value || '')}" />
                    <label class="test-opt-correct-label">
                        <input type="checkbox" class="test-opt-correct" ${checked ? 'checked' : ''} />
                        <span>верный</span>
                    </label>
                    <button type="button" class="btn-delete-option" aria-label="Удалить вариант">✕</button>
                `;
                const textInp = row.querySelector('input.test-opt-text');
                const cb = row.querySelector('input.test-opt-correct');
                const del = row.querySelector('button.btn-delete-option');

                textInp?.addEventListener('input', () => {
                    const idx = Array.from(list.querySelectorAll('.test-opt-row')).indexOf(row);
                    if (idx >= 0) {
                        const arr = Array.isArray(q.options) ? q.options : [];
                        arr[idx] = textInp.value;
                        q.options = arr;
                    }
                });

                cb?.addEventListener('change', () => {
                    if (!isMultiple) ensureSingleCorrect(list, cb);
                    syncCorrectFromDOM();
                });

                del?.addEventListener('click', () => {
                    const idx = Array.from(list.querySelectorAll('.test-opt-row')).indexOf(row);
                    row.remove();
                    const arr = Array.isArray(q.options) ? q.options : [];
                    if (idx >= 0) arr.splice(idx, 1);
                    q.options = arr;
                    syncCorrectFromDOM();
                });

                list.appendChild(row);
            }

            // Ensure model shape
            q.answer_type = isMultiple ? 'multiple' : 'single';
            q.multiple = isMultiple;
            q.options = options.length ? options : ['',''];

            // Render rows
            (q.options || []).forEach((opt, idx) => addRow(opt, correctSet.has(idx)));

            addBtn?.addEventListener('click', () => {
                const arr = Array.isArray(q.options) ? q.options : [];
                arr.push('');
                q.options = arr;
                addRow('', false);
            });

            // If single and nothing checked, default first correct
            if (!isMultiple) {
                const rows = list?.querySelectorAll('.test-opt-row') || [];
                const anyChecked = Array.from(rows).some((r) => r.querySelector('input.test-opt-correct')?.checked);
                if (!anyChecked && rows[0]) {
                    const firstCb = rows[0].querySelector('input.test-opt-correct');
                    if (firstCb) firstCb.checked = true;
                    syncCorrectFromDOM();
                }
            } else {
                syncCorrectFromDOM();
            }
        }

        typeEl?.addEventListener('change', () => {
            // Reset type-specific fields safely
            const t = (typeEl.value || 'single').toLowerCase();
            if (t === 'input') {
                q.answer_type = 'input';
                q.multiple = false;
                q.accepted_answers = Array.isArray(q.accepted_answers) ? q.accepted_answers : [];
                delete q.options;
                delete q.correct_answer;
            } else {
                const isMultiple = t === 'multiple';
                q.answer_type = isMultiple ? 'multiple' : 'single';
                q.multiple = isMultiple;
                q.options = Array.isArray(q.options) ? q.options : ['',''];
                q.correct_answer = isMultiple ? (Array.isArray(q.correct_answer) ? q.correct_answer : []) : (Number.isFinite(Number(q.correct_answer)) ? Number(q.correct_answer) : 0);
                delete q.accepted_answers;
            }
            renderAnswersUI();
        });

        textEl?.addEventListener('input', () => {
            updateModelFromInputs();
            renderQuestionsList();
        });
        pointsEl?.addEventListener('input', updateModelFromInputs);

        deleteBtn?.addEventListener('click', () => {
            targetBlock.content.questions.splice(activeIndex, 1);
            activeIndex = Math.max(0, Math.min(activeIndex, (targetBlock.content.questions.length || 1) - 1));
            renderQuestionsList();
            renderActiveQuestion();
        });

        renderAnswersUI();
    }

    if (addQuestionBtn) {
        addQuestionBtn.addEventListener('click', () => {
            // Используем уже существующую модалку добавления вопроса с валидацией
            openTestQuestionModal(targetBlock);
        });
    }

    // Дадим возможность обновлять список после добавления вопроса
    window.__refreshEditTestModal = () => {
        activeIndex = Math.max(0, (targetBlock.content.questions?.length || 1) - 1);
        renderQuestionsList();
        renderActiveQuestion();
    };

    // Инициализация: по умолчанию настройки
    activateTab('settings');
    renderQuestionsList();
    renderActiveQuestion();
}

function openTestQuestionModal(block) {
    // Ленивая инициализация массива вопросов
    if (!Array.isArray(block.content.questions)) {
        block.content.questions = [];
    }

    let modal = document.getElementById('test-question-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'test-question-modal';
        modal.className = 'modal-overlay';
        document.body.appendChild(modal);
    }

    modal.innerHTML = `
        <div class="modal-container">
            <div class="modal-header">
                <h2 class="modal-title">Добавить вопрос</h2>
                <button class="modal-close" onclick="closeTestQuestionModal()">×</button>
            </div>
            <div class="modal-body tq-body-single">
                <div class="form-group">
                    <label class="form-label">Текст вопроса <span class="required">*</span></label>
                    <textarea id="tq-text" class="form-textarea" rows="3" placeholder="Введите формулировку вопроса"></textarea>
                </div>
                <div class="form-group inline">
                    <div>
                        <label class="form-label">Тип ответа</label>
                        <select id="tq-answer-type" class="form-input">
                            <option value="single">Один вариант (radio)</option>
                            <option value="multiple">Несколько вариантов (checkbox)</option>
                            <option value="input">Ввод текста</option>
                        </select>
                    </div>
                    <div>
                        <label class="form-label">Баллы</label>
                        <input type="number" id="tq-points" class="form-input small" min="1" value="1" />
                    </div>
                </div>

                <div id="tq-options-block" class="tq-options-block">
                    <label class="form-label">Варианты ответа</label>
                    <p class="tq-options-hint">Отметьте правильный ответ (радио — один, чекбоксы — несколько).</p>
                    <div id="tq-options-list" class="tq-options-list"></div>
                    <button type="button" class="btn-add-option" id="tq-add-option-btn">+ Добавить вариант</button>
                </div>

                <div id="tq-input-block" class="tq-input-block" style="display:none;">
                    <label class="form-label">Допустимые ответы (через запятую)</label>
                    <input type="text" id="tq-accepted-answers" class="form-input" placeholder="например: да, согласен, верно" />
                </div>

                <div class="form-error" id="tq-error" style="display:none;"></div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn-cancel" onclick="closeTestQuestionModal()">Отмена</button>
                <button type="button" class="btn-submit" onclick="saveTestQuestion('${block.id}')">Добавить</button>
            </div>
        </div>
    `;

    // Инициализация UI внутри модалки (без табов)
    const answerTypeSelect = document.getElementById('tq-answer-type');
    const optionsBlock = document.getElementById('tq-options-block');
    const inputBlock = document.getElementById('tq-input-block');
    const optionsList = document.getElementById('tq-options-list');
    const addOptionBtn = document.getElementById('tq-add-option-btn');

    function updateAnswerTypeVisibility() {
        const val = (answerTypeSelect.value || 'single').toLowerCase();
        if (val === 'input') {
            optionsBlock.style.display = 'none';
            inputBlock.style.display = 'block';
        } else {
            optionsBlock.style.display = 'block';
            inputBlock.style.display = 'none';
            refreshOptionsCorrectInputs();
        }
    }

    function refreshOptionsCorrectInputs() {
        const val = (answerTypeSelect.value || 'single').toLowerCase();
        const isMultiple = val === 'multiple';
        const rows = optionsList.querySelectorAll('.tq-option-row');
        rows.forEach((row) => {
            const textInput = row.querySelector('.tq-option-text');
            const correctWrap = row.querySelector('.tq-option-correct-wrap');
            const oldCorrect = row.querySelector('.tq-option-correct, input[name="tq-correct-radio"]');
            const wasChecked = oldCorrect && oldCorrect.checked;
            if (!correctWrap) return;
            correctWrap.innerHTML = '';
            const label = document.createElement('label');
            label.className = 'tq-option-correct-label';
            if (isMultiple) {
                const cb = document.createElement('input');
                cb.type = 'checkbox';
                cb.className = 'tq-option-correct';
                cb.checked = wasChecked;
                label.appendChild(cb);
            } else {
                const radio = document.createElement('input');
                radio.type = 'radio';
                radio.name = 'tq-correct-radio';
                radio.className = 'tq-option-correct-radio';
                radio.checked = wasChecked;
                label.appendChild(radio);
            }
            const span = document.createElement('span');
            span.textContent = 'правильный';
            label.appendChild(span);
            correctWrap.appendChild(label);
        });
        if (!isMultiple && rows.length > 0) {
            const anyChecked = optionsList.querySelector('input[name="tq-correct-radio"]:checked');
            if (!anyChecked) {
                const first = optionsList.querySelector('input[name="tq-correct-radio"]');
                if (first) first.checked = true;
            }
        }
    }

    function addOptionRow() {
        const val = (answerTypeSelect.value || 'single').toLowerCase();
        const isMultiple = val === 'multiple';
        const row = document.createElement('div');
        row.className = 'tq-option-row';
        const correctInput = isMultiple
            ? '<label class="tq-option-correct-label"><input type="checkbox" class="tq-option-correct" /><span>правильный</span></label>'
            : '<label class="tq-option-correct-label"><input type="radio" name="tq-correct-radio" class="tq-option-correct-radio" /><span>правильный</span></label>';
        row.innerHTML = `
            <input type="text" class="tq-option-text form-input" placeholder="Текст варианта" />
            <div class="tq-option-correct-wrap">${correctInput}</div>
            <button type="button" class="btn-delete-option" aria-label="Удалить">✕</button>
        `;
        const deleteBtn = row.querySelector('.btn-delete-option');
        deleteBtn.addEventListener('click', () => row.remove());
        optionsList.appendChild(row);
    }

    answerTypeSelect.addEventListener('change', updateAnswerTypeVisibility);
    addOptionBtn.addEventListener('click', addOptionRow);

    // Два пустых варианта по умолчанию
    addOptionRow();
    addOptionRow();
    updateAnswerTypeVisibility();

    modal.style.display = 'flex';
}

function closeTestQuestionModal() {
    const modal = document.getElementById('test-question-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

function saveTestQuestion(blockId) {
    const modal = document.getElementById('test-question-modal');
    if (!modal) return;
    const block = lessonContentBlocks.find((b) => String(b.id) === String(blockId)) || lessonContentBlocks.find((b) => b.id === currentEditingBlockId);
    if (!block) return;
    if (!Array.isArray(block.content.questions)) {
        block.content.questions = [];
    }

    const textEl = document.getElementById('tq-text');
    const typeEl = document.getElementById('tq-answer-type');
    const pointsEl = document.getElementById('tq-points');
    const acceptedEl = document.getElementById('tq-accepted-answers');
    const errorEl = document.getElementById('tq-error');
    const optionsList = document.getElementById('tq-options-list');

    function setError(msg) {
        if (!errorEl) return;
        if (!msg) {
            errorEl.style.display = 'none';
            errorEl.textContent = '';
        } else {
            errorEl.style.display = 'block';
            errorEl.textContent = msg;
        }
    }

    setError('');

    const text = (textEl?.value || '').trim();
    if (!text) {
        setError('Введите текст вопроса');
        return;
    }

    const answerType = (typeEl?.value || 'single').toLowerCase();
    let points = parseInt(pointsEl?.value || '1', 10);
    if (isNaN(points) || points <= 0) points = 1;

    let question = { text, points };

    if (answerType === 'input') {
        const raw = (acceptedEl?.value || '').trim();
        const accepted = raw
            ? raw.split(',').map((s) => s.trim()).filter((s) => s.length > 0)
            : [];
        if (!accepted.length) {
            setError('Укажите хотя бы один допустимый ответ');
            return;
        }
        question.answer_type = 'input';
        question.accepted_answers = accepted;
    } else {
        const multiple = answerType === 'multiple';
        const optionRows = optionsList.querySelectorAll('.tq-option-row');
        const options = [];
        const correctIdx = [];
        optionRows.forEach((row) => {
            const textInput = row.querySelector('.tq-option-text');
            const cb = row.querySelector('.tq-option-correct, .tq-option-correct-radio');
            const optText = (textInput?.value || '').trim();
            if (!optText) return;
            options.push(optText);
            if (cb && cb.checked) {
                correctIdx.push(options.length - 1);
            }
        });

        if (!options.length) {
            setError('Добавьте хотя бы один вариант ответа');
            return;
        }
        if (!correctIdx.length) {
            setError('Отметьте хотя бы один правильный вариант');
            return;
        }
        if (!multiple && correctIdx.length !== 1) {
            setError('Для типа "Один вариант" можно выбрать только один правильный ответ');
            return;
        }

        question.options = options;
        question.multiple = multiple;
        question.answer_type = multiple ? 'multiple' : 'single';
        question.correct_answer = multiple ? correctIdx : correctIdx[0];
    }

    block.content.questions.push(question);
    closeTestQuestionModal();
    if (typeof window.__refreshEditTestModal === 'function') {
        window.__refreshEditTestModal();
    }
}

// Добавить прикрепление к видео
function addVideoAttachment(blockId) {
    const block = lessonContentBlocks.find(b => b.id === blockId);
    if (!block || block.type !== 'video') return;
    
    if (!block.content.attachments) {
        block.content.attachments = [];
    }
    
    const input = document.createElement('input');
    input.type = 'file';
    input.onchange = (e) => {
        const file = e.target.files[0];
        if (file) {
            block.content.attachments.push({
                filename: file.name,
                name: file.name,
                url: URL.createObjectURL(file),
                size: file.size,
                type: file.type
            });
            
            // Обновляем отображение прикреплений
            const container = document.getElementById(`attachments-container-${blockId}`);
            if (container) {
                const attachmentsHtml = block.content.attachments.map((att, idx) => 
                    `<div class="attachment-item" data-index="${idx}">
                        <span>${escapeHtml(att.name || att.filename || 'Файл')}</span>
                        <button type="button" class="btn-remove-attachment" onclick="removeVideoAttachment(${blockId}, ${idx})">×</button>
                    </div>`
                ).join('');
                container.innerHTML = attachmentsHtml || '<p class="no-attachments">Файлы не прикреплены</p>';
            }
        }
    };
    input.click();
}

// Удалить прикрепление видео
function removeVideoAttachment(blockId, index) {
    const block = lessonContentBlocks.find(b => b.id === blockId);
    if (!block || block.type !== 'video' || !block.content.attachments) return;
    
    block.content.attachments.splice(index, 1);
    
    // Обновляем отображение
    const container = document.getElementById(`attachments-container-${blockId}`);
    if (container) {
        const attachmentsHtml = block.content.attachments.map((att, idx) => 
            `<div class="attachment-item" data-index="${idx}">
                <span>${escapeHtml(att.name || att.filename || 'Файл')}</span>
                <button type="button" class="btn-remove-attachment" onclick="removeVideoAttachment(${blockId}, ${idx})">×</button>
            </div>`
        ).join('');
        container.innerHTML = attachmentsHtml || '<p class="no-attachments">Файлы не прикреплены</p>';
    }
}

// Открыть диалог загрузки файла
function openFileUploadDialog(blockId, type) {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = type === 'image' ? 'image/*' : type === 'video' ? 'video/*' : '*/*';
    input.onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        
        // Сохраняем файл в блоке контента для последующей загрузки
        const block = lessonContentBlocks.find(b => b.id === blockId);
        if (block) {
            // Сохраняем сам файл объект для последующей загрузки
            block.file = file; // Сохраняем файл для последующей загрузки
            block.fileType = type; // Сохраняем тип для определения папки
            
            if (type === 'image') {
                block.content.alt = file.name;
                block.content.filename = file.name;
                // Временно показываем превью
                block.content.url = URL.createObjectURL(file);
            } else if (type === 'video') {
                block.content.title = file.name;
                block.content.filename = file.name;
                // Временно показываем превью
                block.content.url = URL.createObjectURL(file);
            } else {
                block.content.filename = file.name;
                block.content.size = file.size;
                block.content.type = file.type;
                // Временно показываем превью
                block.content.url = URL.createObjectURL(file);
            }
            renderContentBlocks();
        }
    };
    input.click();
}

// Инициализация drag-and-drop
function initDragAndDrop() {
    const container = getBlocksContainer();
    if (!container) return;
    
    const blocks = container.querySelectorAll('.content-block-item');
    
    blocks.forEach(block => {
        block.addEventListener('dragstart', handleDragStart);
        block.addEventListener('dragover', handleDragOver);
        block.addEventListener('drop', handleDrop);
        block.addEventListener('dragend', handleDragEnd);
    });
}

let draggedElement = null;

function handleDragStart(e) {
    draggedElement = this;
    this.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    
    const afterElement = getDragAfterElement(this.parentNode, e.clientY);
    if (afterElement === null) {
        this.parentNode.appendChild(draggedElement);
    } else {
        this.parentNode.insertBefore(draggedElement, afterElement);
    }
}

function handleDrop(e) {
    e.preventDefault();
    updateBlockOrders();
}

function handleDragEnd() {
    this.classList.remove('dragging');
    draggedElement = null;
}

function getDragAfterElement(container, y) {
    const draggableElements = [...container.querySelectorAll('.content-block-item:not(.dragging)')];
    
    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        
        if (offset < 0 && offset > closest.offset) {
            return { offset: offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}

function updateBlockOrders() {
    const container = getBlocksContainer();
    if (!container) return;
    
    const blocks = container.querySelectorAll('.content-block-item');
    blocks.forEach((blockEl, index) => {
        const blockId = parseInt(blockEl.dataset.blockId);
        const block = lessonContentBlocks.find(b => b.id === blockId);
        if (block) {
            block.order = index;
        }
    });
    
    lessonContentBlocks.sort((a, b) => a.order - b.order);
}

// Показать модальное окно загрузки урока
function showLessonCreationModal() {
    // Блокируем кнопку создания урока на странице
    const createLessonBtn = document.getElementById('create-lesson-btn');
    if (createLessonBtn) {
        createLessonBtn.disabled = true;
        createLessonBtn.style.opacity = '0.6';
        createLessonBtn.style.cursor = 'not-allowed';
    }
    
    // Создаем модальное окно загрузки
    let loadingModal = document.getElementById('lesson-creation-loading-modal');
    if (!loadingModal) {
        loadingModal = document.createElement('div');
        loadingModal.id = 'lesson-creation-loading-modal';
        loadingModal.className = 'modal-overlay';
        document.body.appendChild(loadingModal);
    }
    
    loadingModal.innerHTML = `
        <div class="modal-container" style="max-width: 400px;">
            <div class="modal-header">
                <h2 class="modal-title">Создание урока</h2>
            </div>
            <div class="modal-body" style="text-align: center; padding: 2rem;">
                <div class="loading-spinner" style="width: 48px; height: 48px; border: 4px solid #f3f3f3; border-top: 4px solid #3259ac; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 1rem;"></div>
                <p style="font-size: 1rem; color: #4f4f4f; margin: 0;">Пожалуйста, подождите...</p>
                <p style="font-size: 0.875rem; color: #666; margin: 0.5rem 0 0;">Создание урока и загрузка файлов</p>
            </div>
            <div class="modal-footer" style="justify-content: center;">
                <button type="button" class="btn-cancel" onclick="cancelLessonCreation()">Отменить</button>
            </div>
        </div>
    `;
    
    // Добавляем стили для анимации спиннера
    if (!document.getElementById('loading-spinner-styles')) {
        const style = document.createElement('style');
        style.id = 'loading-spinner-styles';
        style.textContent = `
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        `;
        document.head.appendChild(style);
    }
    
    loadingModal.style.display = 'flex';
    
    // Блокируем закрытие по клику на overlay
    loadingModal.addEventListener('click', (e) => {
        if (e.target === loadingModal) {
            // Не закрываем при клике на overlay, только через кнопку "Отменить"
        }
    });
}

// Закрыть модальное окно загрузки урока
function closeLessonCreationModal() {
    const loadingModal = document.getElementById('lesson-creation-loading-modal');
    if (loadingModal) {
        loadingModal.style.display = 'none';
    }
    
    // Разблокируем кнопку создания урока на странице
    const createLessonBtn = document.getElementById('create-lesson-btn');
    if (createLessonBtn) {
        createLessonBtn.disabled = false;
        createLessonBtn.style.opacity = '1';
        createLessonBtn.style.cursor = 'pointer';
    }
}

// Показать модальное окно обновления урока (как при создании)
function showLessonUpdateModal() {
    let loadingModal = document.getElementById('lesson-update-loading-modal');
    if (!loadingModal) {
        loadingModal = document.createElement('div');
        loadingModal.id = 'lesson-update-loading-modal';
        loadingModal.className = 'modal-overlay';
        document.body.appendChild(loadingModal);
    }

    loadingModal.innerHTML = `
        <div class="modal-container" style="max-width: 400px;">
            <div class="modal-header">
                <h2 class="modal-title">Изменение урока</h2>
            </div>
            <div class="modal-body" style="text-align: center; padding: 2rem;">
                <div class="loading-spinner" style="width: 48px; height: 48px; border: 4px solid #f3f3f3; border-top: 4px solid #3259ac; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 1rem;"></div>
                <p style="font-size: 1rem; color: #4f4f4f; margin: 0;">Пожалуйста, подождите...</p>
                <p style="font-size: 0.875rem; color: #666; margin: 0.5rem 0 0;">Сохранение изменений и загрузка файлов</p>
            </div>
            <div class="modal-footer" style="justify-content: center;">
                <button type="button" class="btn-cancel" onclick="cancelLessonUpdate()">Отменить</button>
            </div>
        </div>
    `;

    // Добавляем стили для анимации спиннера (если ещё нет)
    if (!document.getElementById('loading-spinner-styles')) {
        const style = document.createElement('style');
        style.id = 'loading-spinner-styles';
        style.textContent = `
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        `;
        document.head.appendChild(style);
    }

    loadingModal.style.display = 'flex';

    // Блокируем закрытие по клику на overlay
    loadingModal.addEventListener('click', (e) => {
        if (e.target === loadingModal) {
            // Не закрываем при клике на overlay, только через кнопку "Отменить"
        }
    });
}

function closeLessonUpdateModal() {
    const loadingModal = document.getElementById('lesson-update-loading-modal');
    if (loadingModal) loadingModal.style.display = 'none';
}

function cancelLessonUpdate() {
    if (updateLessonAbortController) {
        updateLessonAbortController.abort();
        updateLessonAbortController = null;
    }
    isUpdatingLesson = false;
    closeLessonUpdateModal();

    // Разблокируем кнопку "Сохранить" в форме редактирования
    const submitBtn = document.querySelector('form#edit-lesson-form button[type="submit"]');
    if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Сохранить';
    }

    showError('Изменение урока отменено');
}

// Отменить создание урока
function cancelLessonCreation() {
    if (createLessonAbortController) {
        createLessonAbortController.abort();
        createLessonAbortController = null;
    }
    
    isCreatingLesson = false;
    closeLessonCreationModal();
    
    // Восстанавливаем кнопку в форме
    const submitBtn = document.querySelector('form#create-lesson-form button[type="submit"]');
    if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Создать урок';
    }
    
    showError('Создание урока отменено');
}

// Создать урок с контентом
async function createLessonWithContent() {
    if (currentUserRole !== 'admin' && currentUserRole !== 'super_admin') {
        showError('Требуются права администратора');
        return;
    }
    
    // Предотвращаем двойное создание
    if (isCreatingLesson) {
        return; // Уже создается
    }
    
    isCreatingLesson = true;
    createLessonAbortController = new AbortController();
    
    // Блокируем кнопку в форме
    const submitBtn = document.querySelector('form#create-lesson-form button[type="submit"]');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Создание...';
    }
    
    // Показываем модальное окно загрузки
    showLessonCreationModal();
    
    try {
        if (!currentCourseId) {
            showError('Выберите курс для создания урока');
            // Сбрасываем флаги и закрываем модальное окно загрузки
            isCreatingLesson = false;
            createLessonAbortController = null;
            closeLessonCreationModal();
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Создать урок';
            }
            return;
        }
        
        const titleInput = document.getElementById('lesson-title');
        const descriptionInput = document.getElementById('lesson-description');
        
        const title = (titleInput?.value || '').trim();
        const description = (descriptionInput?.value || '').trim();
        
        if (!title) {
            showError('Название урока обязательно');
            // Сбрасываем флаги и закрываем модальное окно загрузки
            isCreatingLesson = false;
            createLessonAbortController = null;
            closeLessonCreationModal();
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Создать урок';
            }
            return;
        }
        
        // Сначала создаем урок
        const response = await fetch(`${API_BASE}/lessons`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                course_id: currentCourseId,
                title,
                description
            }),
            signal: createLessonAbortController.signal
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Ошибка при создании урока');
        }
        
        const lessonId = data.id;
        
        // Затем создаем блоки контента
        for (const block of lessonContentBlocks) {
            // Если есть файл для загрузки, загружаем его на сервер
            if (block.file) {
                try {
                    const formData = new FormData();
                    formData.append('file', block.file);
                    
                    // Определяем тип папки для загрузки
                    let folderType = 'files';
                    if (block.fileType === 'image') {
                        folderType = 'images';
                    } else if (block.fileType === 'video') {
                        folderType = 'videos';
                    }
                    formData.append('type', folderType);
                    
                    // Загружаем файл на сервер
                    const uploadResponse = await fetch(`${API_BASE}/lessons/${lessonId}/files`, {
                        method: 'POST',
                        body: formData,
                        signal: createLessonAbortController.signal
                    });
                    
                    const uploadData = await uploadResponse.json();
                    
                    if (uploadResponse.ok) {
                        // Обновляем content с URL файла
                        if (block.fileType === 'file') {
                            block.content.url = uploadData.url;
                            block.content.filename = uploadData.filename;
                            block.content.stored_filename = uploadData.stored_filename;
                            block.content.size = uploadData.size;
                        } else if (block.fileType === 'video') {
                            block.content.url = uploadData.url;
                            block.content.filename = uploadData.filename;
                            block.content.stored_filename = uploadData.stored_filename;
                            block.content.title = block.content.title || uploadData.filename;
                        } else if (block.fileType === 'image') {
                            block.content.url = uploadData.url;
                            block.content.filename = uploadData.filename;
                            block.content.stored_filename = uploadData.stored_filename;
                            block.content.alt = block.content.alt || uploadData.filename;
                        }
                        
                        // Освобождаем временный URL
                        if (block.content.url && block.content.url.startsWith('blob:')) {
                            URL.revokeObjectURL(block.content.url);
                        }
                    } else {
                        console.error('Ошибка загрузки файла:', uploadData.error);
                        throw new Error(uploadData.error || 'Ошибка загрузки файла');
                    }
                } catch (error) {
                    console.error('Ошибка загрузки файла:', error);
                    // Продолжаем создание блока без файла
                }
            }
            
            // Создаем блок контента
            const blockResponse = await fetch(`${API_BASE}/lessons/${lessonId}/blocks`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    block_type: block.type,
                    content: block.content,
                    order: block.order
                }),
                signal: createLessonAbortController.signal
            });
            
            if (!blockResponse.ok) {
                const errorData = await blockResponse.json();
                console.error('Ошибка создания блока:', errorData.error);
            }
        }
        
        showSuccess('Урок создан');
        closeCreateLessonModal(); // Закрываем форму создания
        closeLessonCreationModal(); // Закрываем модальное окно загрузки
        loadLessons();
    } catch (error) {
        console.error('Ошибка создания урока:', error);
        
        // Проверяем, не была ли операция отменена
        if (error.name === 'AbortError') {
            // Операция была отменена пользователем
            return;
        }
        
        showError('Не удалось создать урок: ' + error.message);
        closeLessonCreationModal(); // Закрываем модальное окно загрузки при ошибке
    } finally {
        // Сбрасываем флаги
        isCreatingLesson = false;
        createLessonAbortController = null;
        
        // Восстанавливаем кнопку в форме
        const submitBtn = document.querySelector('form#create-lesson-form button[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Создать урок';
        }
    }
}

// Настройка обработчиков событий
function setupEventListeners() {
    // Обработчик для кнопки создания урока
    const createLessonBtn = document.getElementById('create-lesson-btn');
    if (createLessonBtn) {
        createLessonBtn.addEventListener('click', openCreateLessonModal);
    }
    
    // Закрытие модальных окон по Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const createModal = document.getElementById('create-lesson-modal');
            if (createModal && createModal.style.display === 'flex') {
                closeCreateLessonModal();
            }
            const editLessonModal = document.getElementById('edit-lesson-modal');
            if (editLessonModal && editLessonModal.style.display === 'flex') {
                closeEditLessonModal();
            }
        }
    });
}

// Экспорт функций
window.openLesson = openLesson;
window.deleteLesson = deleteLesson;
window.editLesson = editLesson;
window.askQuestionAboutLesson = askQuestionAboutLesson;
window.createLesson = createLesson;
window.createLessonWithContent = createLessonWithContent;
window.openCreateLessonModal = openCreateLessonModal;
window.closeCreateLessonModal = closeCreateLessonModal;
window.closeEditLessonModal = closeEditLessonModal;
window.cancelLessonCreation = cancelLessonCreation;
window.toggleContentMenu = toggleContentMenu;
window.addContentBlock = addContentBlock;
window.removeContentBlock = removeContentBlock;
window.editContentBlock = editContentBlock;
window.closeEditBlockModal = closeEditBlockModal;
window.saveBlockEdit = saveBlockEdit;
window.addVideoAttachment = addVideoAttachment;
window.removeVideoAttachment = removeVideoAttachment;
