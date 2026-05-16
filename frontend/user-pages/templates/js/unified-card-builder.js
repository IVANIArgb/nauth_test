/**
 * Единый модуль для создания карточек
 * Поддерживает: категории, курсы, уроки, корзина
 * Три статуса: завершен, в процессе, неначат
 */

// Константы для статусов
const CARD_STATUS = {
    COMPLETED: 'completed',
    IN_PROGRESS: 'in-progress',
    NOT_STARTED: 'not-started'
};

// Константы для текстов статусов
const STATUS_TEXT = {
    completed: 'завершен',
    'in-progress': 'в процессе',
    'not-started': 'неначат'
};

// Константы для иконок
const ICONS = {
    OPEN: '→',
    QUESTION: '?',
    EDIT: '✎',
    DELETE: '×',
    RESTORE: '↻'
};

/**
 * Определить статус карточки на основе данных
 */
function determineCardStatus(data) {
    // Для категорий и курсов
    if (data.progress) {
        if (data.progress.status === 'completed') {
            return CARD_STATUS.COMPLETED;
        } else if (data.progress.status === 'in_progress') {
            return CARD_STATUS.IN_PROGRESS;
        }
        return CARD_STATUS.NOT_STARTED;
    }
    
    // Для уроков (lesson_status: 0=незаходил, 1=недопрошел, 2=прошел)
    if (data.lesson_status !== undefined) {
        if (data.lesson_status === 2) return CARD_STATUS.COMPLETED;
        if (data.lesson_status === 1) return CARD_STATUS.IN_PROGRESS;
        return CARD_STATUS.NOT_STARTED;
    }
    if (data.is_completed !== undefined) {
        if (data.is_completed) return CARD_STATUS.COMPLETED;
        return CARD_STATUS.NOT_STARTED;
    }
    
    // Для корзины (всегда not-started)
    if (data.object_type) {
        return CARD_STATUS.NOT_STARTED;
    }
    
    return CARD_STATUS.NOT_STARTED;
}

/**
 * Получить текст статуса
 */
function getStatusText(statusClass) {
    return STATUS_TEXT[statusClass] || STATUS_TEXT['not-started'];
}

/**
 * Экранирование HTML
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Создать кнопку действия
 */
function createActionButton(icon, onClick, title, className = '', disabled = false) {
    const disabledAttr = disabled ? 'disabled style="opacity: 0.5; cursor: not-allowed;"' : '';
    return `<button class="btn-action-icon ${className}" ${disabledAttr} onclick="${onClick}" title="${escapeHtml(title)}">${icon}</button>`;
}

/**
 * Создать панель статуса
 */
function createStatusPanel(statusClass, statusText, leftButtons = '', rightButtons = '') {
    return `
        <div class="status-panel ${statusClass}">
            <div class="status-left">
                <span class="status-text">${statusText}</span>
                ${leftButtons}
            </div>
            <div class="status-right">
                ${rightButtons}
            </div>
        </div>
    `;
}

/**
 * Создать текст прогресса "X из Y" (сколько из скольки прошёл)
 */
function createProgressText(completed, total) {
    const c = completed != null ? completed : 0;
    const t = total != null ? total : 0;
    if (t <= 0) return '';
    return `<div class="progress-info"><span class="progress-text">${c} из ${t}</span></div>`;
}

/**
 * Создать прогресс бар (deprecated, используется createProgressText)
 */
function createProgressBar(percentage) {
    if (!percentage && percentage !== 0) return '';
    return `
        <div class="progress-info">
            <div class="progress-bar">
                <div class="progress-fill" style="width: ${percentage}%"></div>
            </div>
            <span class="progress-text">${percentage}%</span>
        </div>
    `;
}

/**
 * Создать карточку категории (глобальная функция из модуля)
 */
function createCategoryCardFromModule(category, options = {}) {
    const { currentUserRole = 'user', onOpen, onEdit, onDelete, onQuestion } = options;
    
    const statusClass = determineCardStatus(category);
    const statusText = getStatusText(statusClass);
    const progress = category.progress || { status: 'not_started', progress_percentage: 0 };
    
    // Кнопки слева (открыть, вопрос)
    const leftButtons = `
        ${createActionButton(ICONS.OPEN, `openCategory(${category.id})`, 'Открыть категорию', 'btn-open-icon')}
        ${createActionButton(ICONS.QUESTION, `askQuestionAboutCategory(${category.id}, event)`, 'Задать вопрос', 'btn-question-icon')}
    `;
    
    // Кнопки справа (только для админа)
    const rightButtons = (currentUserRole === 'admin' || currentUserRole === 'super_admin') ? `
        ${createActionButton(ICONS.EDIT, `editCategory(${category.id}, event)`, 'Изменить', 'btn-edit-icon')}
        ${createActionButton(ICONS.DELETE, `deleteCategory(${category.id}, event)`, 'Удалить', 'btn-delete-icon')}
    ` : '';
    
    const totalCourses = progress.total_courses ?? category.courses_count ?? 0;
    const progressText = createProgressText(progress.courses_completed, totalCourses);
    
    const card = document.createElement('article');
    card.className = 'unified-card category-card';
    card.dataset.categoryId = category.id;
    
    card.innerHTML = `
        <div class="card-content">
            <div class="card-header">
                <h3 class="card-title">${escapeHtml(category.title)}</h3>
            </div>
            <div class="card-main">
                <p class="card-description">${escapeHtml(category.description || '')}</p>
                <div class="card-stats">
                    <span class="courses-count">Курсов: ${category.courses_count || 0}</span>
                </div>
                ${progressText}
            </div>
            ${createStatusPanel(statusClass, statusText, leftButtons, rightButtons)}
        </div>
    `;
    
    // Двойной клик для открытия
    card.addEventListener('dblclick', () => {
        if (onOpen) onOpen(category.id);
        else openCategory(category.id);
    });
    
    return card;
}

/**
 * Обработка клика по кнопке «Открыть курс» — переход или уведомление о недоступности
 */
function handleCourseOpenClick(event) {
    if (event) event.stopPropagation();
    const card = event && event.target ? event.target.closest('.course-card') : null;
    if (!card) return;
    const isAccessible = card.dataset.isAccessible === '1';
    const courseId = card.dataset.courseId;
    const lockedReason = card.dataset.lockedReason || 'Материал недоступен. Пройдите предыдущие курсы в последовательности.';
    if (isAccessible && typeof openCourse === 'function') {
        openCourse(courseId);
    } else {
        (typeof customAlert === 'function' ? customAlert : alert)(lockedReason, 'Материал недоступен');
    }
}

/**
 * Создать карточку курса (глобальная функция из модуля)
 */
function createCourseCardFromModule(course, options = {}) {
    const { currentUserRole = 'user', onOpen, onEdit, onDelete, onQuestion } = options;
    
    const statusClass = determineCardStatus(course);
    const statusText = getStatusText(statusClass);
    const progress = course.progress || { status: 'not_started', progress_percentage: 0 };
    const isAccessible = course.is_accessible !== false;
    const lockedReason = (course.locked_reason || 'Материал недоступен. Пройдите предыдущие курсы в последовательности.').replace(/"/g, '&quot;');
    
    // Индикатор последовательного прохождения
    const sequentialIndicator = course.sequential_progression 
        ? `<span class="sequential-badge">🔒</span>` 
        : '';
    
    // Кнопки слева (открыть — через handleCourseOpenClick для уведомления при locked)
    const leftButtons = `
        ${createActionButton(ICONS.OPEN, `handleCourseOpenClick(event)`, 'Открыть курс', 'btn-open-icon', false)}
        ${createActionButton(ICONS.QUESTION, `askQuestionAboutCourse(${course.id}, event)`, 'Задать вопрос', 'btn-question-icon')}
    `;
    
    // Кнопки справа (только для админа)
    const rightButtons = (currentUserRole === 'admin' || currentUserRole === 'super_admin') ? `
        ${createActionButton(ICONS.EDIT, `editCourse(${course.id}, event)`, 'Изменить', 'btn-edit-icon')}
        ${createActionButton(ICONS.DELETE, `deleteCourse(${course.id}, event)`, 'Удалить', 'btn-delete-icon')}
    ` : '';
    
    const totalLessons = progress.total_lessons ?? course.total_lessons ?? 0;
    const progressText = createProgressText(progress.lessons_completed, totalLessons);
    
    const card = document.createElement('article');
    card.className = 'unified-card course-card' + (!isAccessible ? ' card-locked' : '');
    card.dataset.courseId = course.id;
    card.dataset.isAccessible = isAccessible ? '1' : '0';
    card.dataset.lockedReason = lockedReason;
    
    card.innerHTML = `
        <div class="card-content">
            <div class="card-header">
                <h3 class="card-title">
                    ${escapeHtml(course.title)}
                    ${sequentialIndicator}
                </h3>
            </div>
            <div class="card-main">
                <p class="card-description">${escapeHtml(course.description || '')}</p>
                ${!isAccessible ? `<p class="locked-reason">${escapeHtml(course.locked_reason || 'Материал недоступен. Пройдите предыдущие курсы в последовательности.')}</p>` : ''}
                ${progressText}
            </div>
            ${createStatusPanel(statusClass, statusText, leftButtons, rightButtons)}
        </div>
    `;
    
    // Двойной клик: переход или уведомление
    card.addEventListener('dblclick', (e) => {
        if (e.target.closest('button')) return;
        if (isAccessible) {
            if (onOpen) onOpen(course.id);
            else if (typeof openCourse === 'function') openCourse(course.id);
        } else {
            (typeof customAlert === 'function' ? customAlert : alert)(course.locked_reason || lockedReason, 'Материал недоступен');
        }
    });
    
    // Одиночный клик по заблокированной карточке — уведомление
    card.addEventListener('click', (e) => {
        if (!isAccessible && !e.target.closest('button')) {
            (typeof customAlert === 'function' ? customAlert : alert)(course.locked_reason || lockedReason, 'Материал недоступен');
        }
    });
    
    return card;
}

/**
 * Обработка клика по кнопке «Открыть урок» — переход или уведомление о недоступности
 */
function handleLessonOpenClick(event) {
    if (event) event.stopPropagation();
    const card = event && event.target ? event.target.closest('.lesson-card') : null;
    if (!card) return;
    const isAccessible = card.dataset.isAccessible === '1';
    const lessonId = card.dataset.lessonId;
    const lockedReason = card.dataset.lockedReason || 'Материал недоступен. Пройдите предыдущие уроки в последовательности.';
    if (isAccessible && typeof openLesson === 'function') {
        openLesson(lessonId);
    } else {
        (typeof customAlert === 'function' ? customAlert : alert)(lockedReason, 'Материал недоступен');
    }
}

/**
 * Создать карточку урока (глобальная функция из модуля)
 */
function createLessonCardFromModule(lesson, options = {}) {
    const { currentUserRole = 'user', onOpen, onEdit, onDelete, onQuestion } = options;
    
    const statusClass = determineCardStatus(lesson);
    const statusText = getStatusText(statusClass);
    const isAccessible = lesson.is_accessible !== false;
    const lockedReasonText = lesson.locked_reason || 'Материал недоступен. Пройдите предыдущие уроки в последовательности.';
    
    // Кнопки слева (открыть — через handleLessonOpenClick для уведомления при locked)
    const leftButtons = `
        ${createActionButton(ICONS.OPEN, `handleLessonOpenClick(event)`, 'Открыть урок', 'btn-open-icon', false)}
        ${createActionButton(ICONS.QUESTION, `askQuestionAboutLesson(${lesson.id}, event)`, 'Задать вопрос', 'btn-question-icon')}
    `;
    
    // Кнопки справа (только для админа)
    const rightButtons = (currentUserRole === 'admin' || currentUserRole === 'super_admin') ? `
        ${createActionButton(ICONS.EDIT, `editLesson(${lesson.id}, event)`, 'Изменить', 'btn-edit-icon')}
        ${createActionButton(ICONS.DELETE, `deleteLesson(${lesson.id}, event)`, 'Удалить', 'btn-delete-icon')}
    ` : '';
    
    const lockedReasonHtml = !isAccessible 
        ? `<p class="locked-reason">${escapeHtml(lockedReasonText)}</p>` 
        : '';
    
    const card = document.createElement('article');
    card.className = 'unified-card lesson-card' + (!isAccessible ? ' card-locked' : '');
    card.dataset.lessonId = lesson.id;
    card.dataset.isAccessible = isAccessible ? '1' : '0';
    card.dataset.lockedReason = lockedReasonText.replace(/"/g, '&quot;');
    
    card.innerHTML = `
        <div class="card-content">
            <div class="card-header">
                <h3 class="card-title">${escapeHtml(lesson.title)}</h3>
            </div>
            <div class="card-main">
                <p class="card-description">${escapeHtml(lesson.description || '')}</p>
                ${lockedReasonHtml}
            </div>
            ${createStatusPanel(statusClass, statusText, leftButtons, rightButtons)}
        </div>
    `;
    
    // Двойной клик: переход или уведомление
    card.addEventListener('dblclick', (e) => {
        if (e.target.closest('button')) return;
        if (isAccessible) {
            if (onOpen) onOpen(lesson.id);
            else if (typeof openLesson === 'function') openLesson(lesson.id);
        } else {
            (typeof customAlert === 'function' ? customAlert : alert)(lockedReasonText, 'Материал недоступен');
        }
    });
    
    // Одиночный клик по заблокированной карточке — уведомление
    card.addEventListener('click', (e) => {
        if (!isAccessible && !e.target.closest('button')) {
            (typeof customAlert === 'function' ? customAlert : alert)(lockedReasonText, 'Материал недоступен');
        }
    });
    
    return card;
}

/**
 * Создать карточку удаленного объекта (корзина) (глобальная функция из модуля)
 */
function createDeletedObjectCardFromModule(obj, options = {}) {
    const { onRestore } = options;
    
    const objectData = obj.object_data || {};
    const deletedDate = new Date(obj.deleted_at);
    const daysLeft = obj.days_until_permanent_delete || 0;
    
    const statusClass = CARD_STATUS.NOT_STARTED;
    const statusText = 'удалено';
    
    // Кнопки справа (восстановить)
    const rightButtons = `
        ${createActionButton(ICONS.RESTORE, `restoreObject(${obj.id})`, 'Восстановить', 'btn-restore-icon')}
    `;
    
    // Метка типа объекта
    const typeLabels = {
        'category': 'Категория',
        'course': 'Курс',
        'lesson': 'Урок'
    };
    const typeLabel = typeLabels[obj.object_type] || obj.object_type;
    
    const card = document.createElement('article');
    card.className = 'unified-card deleted-object-card';
    card.dataset.deletedId = obj.id;
    
    card.innerHTML = `
        <div class="card-content">
            <div class="card-header">
                <h3 class="card-title">${escapeHtml(objectData.title || 'Без названия')}</h3>
            </div>
            <div class="card-main">
                <p class="card-description">${escapeHtml(objectData.description || '')}</p>
                <div class="card-stats">
                    <span class="object-type">${typeLabel}</span>
                </div>
                <p class="deleted-info">
                    Удалено: ${deletedDate.toLocaleDateString('ru-RU')}
                </p>
                <p class="days-left ${daysLeft <= 7 ? 'warning' : ''}">
                    Осталось дней до полного удаления: ${daysLeft}
                </p>
            </div>
            ${createStatusPanel(statusClass, statusText, '', rightButtons)}
        </div>
    `;
    
    return card;
}

// Делаем функции доступными глобально
window.handleCourseOpenClick = handleCourseOpenClick;
window.handleLessonOpenClick = handleLessonOpenClick;
window.createCategoryCardFromModule = createCategoryCardFromModule;
window.createCourseCardFromModule = createCourseCardFromModule;
window.createLessonCardFromModule = createLessonCardFromModule;
window.createDeletedObjectCardFromModule = createDeletedObjectCardFromModule;
window.determineCardStatus = determineCardStatus;
window.getStatusText = getStatusText;
window.CARD_STATUS = CARD_STATUS;
window.STATUS_TEXT = STATUS_TEXT;
window.ICONS = ICONS;

// Экспорт функций (если используется модульная система)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        createCategoryCard: createCategoryCardFromModule,
        createCourseCard: createCourseCardFromModule,
        createLessonCard: createLessonCardFromModule,
        createDeletedObjectCard: createDeletedObjectCardFromModule,
        determineCardStatus,
        getStatusText,
        CARD_STATUS,
        STATUS_TEXT,
        ICONS
    };
}
