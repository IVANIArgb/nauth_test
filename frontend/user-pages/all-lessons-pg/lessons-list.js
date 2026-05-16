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
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        if (data.role) {
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

// Редактировать урок
async function editLesson(lessonId, event) {
    if (event) event.stopPropagation();
    
    if (currentUserRole !== 'admin' && currentUserRole !== 'super_admin') {
        showError('Требуются права администратора');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/lessons/${lessonId}`);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Урок не найден');
        }
        
        // Переходим на страницу урока в режиме редактирования
        window.location.href = `/lessons-content-pg?lesson_id=${lessonId}&edit=true`;
    } catch (error) {
        console.error('Ошибка:', error);
        showError('Не удалось загрузить данные урока');
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
    
    const title = (titleInput?.value || '').trim();
    const description = (descriptionInput?.value || '').trim();
    
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
                description
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }
        await response.json();
        showSuccess('Урок создан');
        closeCreateLessonModal();
        loadLessons();
    } catch (error) {
        console.error('Ошибка создания урока:', error);
        showError('Не удалось создать урок');
    }
}

// Хранилище блоков контента для нового урока
let lessonContentBlocks = [];

// Открыть модальное окно создания урока (конструктор)
function openCreateLessonModal() {
    if (!currentCourseId) {
        showError('Выберите курс для создания урока');
        return;
    }
    
    lessonContentBlocks = []; // Сбрасываем блоки
    
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
                <form id="create-lesson-form" onsubmit="event.preventDefault(); createLessonWithContent();">
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
    
    // Закрываем меню
    const menu = document.getElementById('content-menu');
    if (menu) menu.classList.remove('show');
    
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
        default:
            return {};
    }
}

// Отобразить блоки контента
function renderContentBlocks() {
    const container = document.getElementById('content-blocks-container');
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
    }
    
    editModal.innerHTML = modalContent;
    editModal.style.display = 'flex';
    
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
        
        // Здесь должна быть загрузка файла на сервер
        // Пока используем временный URL
        const block = lessonContentBlocks.find(b => b.id === blockId);
        if (block) {
            if (type === 'image') {
                block.content.url = URL.createObjectURL(file);
                block.content.alt = file.name;
            } else if (type === 'video') {
                block.content.url = URL.createObjectURL(file);
                block.content.title = file.name;
            } else {
                block.content.url = URL.createObjectURL(file);
                block.content.filename = file.name;
            }
            renderContentBlocks();
        }
    };
    input.click();
}

// Инициализация drag-and-drop
function initDragAndDrop() {
    const container = document.getElementById('content-blocks-container');
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
    const container = document.getElementById('content-blocks-container');
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

// Создать урок с контентом
async function createLessonWithContent() {
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
    
    const title = (titleInput?.value || '').trim();
    const description = (descriptionInput?.value || '').trim();
    
    if (!title) {
        showError('Название урока обязательно');
        return;
    }
    
    try {
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
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Ошибка при создании урока');
        }
        
        const lessonId = data.id;
        
        // Затем создаем блоки контента
        for (const block of lessonContentBlocks) {
            await fetch(`${API_BASE}/lessons/${lessonId}/blocks`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    block_type: block.type,
                    content: block.content,
                    order: block.order
                })
            });
        }
        
        showSuccess('Урок создан');
        closeCreateLessonModal();
        loadLessons();
    } catch (error) {
        console.error('Ошибка создания урока:', error);
        showError('Не удалось создать урок: ' + error.message);
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
window.toggleContentMenu = toggleContentMenu;
window.addContentBlock = addContentBlock;
window.removeContentBlock = removeContentBlock;
window.editContentBlock = editContentBlock;
window.closeEditBlockModal = closeEditBlockModal;
window.saveBlockEdit = saveBlockEdit;
window.addVideoAttachment = addVideoAttachment;
window.removeVideoAttachment = removeVideoAttachment;
