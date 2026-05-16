/**
 * JavaScript для страницы списка курсов
 */

const API_BASE = '/api';

// DOM элементы
let coursesContainer = null;
let categoryFilter = null;
let currentCategoryId = null;
let currentUserRole = 'user';
let breadcrumbsContainer = null;
let currentCategory = null;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    coursesContainer = document.querySelector('.courses-grid');
    
    // Получаем category_id из URL
    const urlParams = new URLSearchParams(window.location.search);
    const categoryIdParam = urlParams.get('category_id');
    currentCategoryId = categoryIdParam ? parseInt(categoryIdParam, 10) : null;
    
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
    
    // Проверяем роль пользователя
    checkUserRole();
    
    // Загружаем категорию для breadcrumbs и заголовка
    if (currentCategoryId) {
        loadCategoryForBreadcrumbs();
    } else {
        updatePageTitle();
    }
    
    // Загружаем категории для фильтра
    loadCategories();
    
    // Загружаем курсы
    loadCourses();
    
    setupEventListeners();
});

// Загрузка категории для breadcrumbs
async function loadCategoryForBreadcrumbs() {
    try {
        const response = await fetch(`${API_BASE}/categories/${currentCategoryId}`);
        const data = await response.json();
        
        if (response.ok) {
        currentCategory = data;
        updatePageTitle();
        updateBreadcrumbs([{
                type: 'category',
                id: data.id,
                title: data.title,
                url: `/all-categories-pg`
            }]);
        }
    } catch (error) {
        console.error('Ошибка загрузки категории:', error);
    }
}

// Обновление заголовка страницы
function updatePageTitle() {
    const pageTitle = document.querySelector('.page-title');
    if (!pageTitle) return;
    if (currentCategory) {
        pageTitle.textContent = `Курсы в «${currentCategory.title}»`;
    } else {
        pageTitle.textContent = 'Курсы';
    }
}

// Обновление breadcrumbs
function updateBreadcrumbs(path) {
    if (!breadcrumbsContainer) return;
    
    let breadcrumbs = '<a href="/main-pg">Главная</a>';
    breadcrumbs += ' > <a href="/all-categories-pg">База знаний</a>';
    
    if (currentCategory) {
        breadcrumbs += ` > <a href="/all-categories-pg">${escapeHtml(currentCategory.title)}</a>`;
    }
    
    breadcrumbs += ' > <span>Курсы</span>';
    
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
    // Показываем большую голубую кнопку "Добавить курс"
    const addSection = document.querySelector('.add-course-section');
    if (addSection) {
        addSection.style.display = 'flex';
    }
    
    // Показываем кнопку в секции добавления, если есть
    const createCourseBtn = document.getElementById('create-course-btn');
    if (createCourseBtn) {
        createCourseBtn.style.display = 'flex';
    }
}

// Загрузка категорий для фильтра
async function loadCategories() {
    try {
        const response = await fetch(`${API_BASE}/categories`);
        const data = await response.json();
        
        if (response.ok) {
            // Создаем фильтр категорий, если его нет
            createCategoryFilter(data.categories || []);
        }
    } catch (error) {
        console.error('Ошибка загрузки категорий:', error);
    }
}

// Создание фильтра категорий
function createCategoryFilter(categories) {
    // Ищем существующий фильтр или создаем новый
    let filterContainer = document.querySelector('.category-filter');
    if (!filterContainer) {
        filterContainer = document.createElement('div');
        filterContainer.className = 'category-filter';
        const pageTitle = document.querySelector('.page-title');
        if (pageTitle && pageTitle.parentNode) {
            pageTitle.parentNode.insertBefore(filterContainer, pageTitle.nextSibling);
        }
    }
    
    categoryFilter = document.createElement('select');
    categoryFilter.id = 'category-filter-select';
    
    // Опция "Все категории"
    const allOption = document.createElement('option');
    allOption.value = '';
    allOption.textContent = 'Все категории';
    if (!currentCategoryId) {
        allOption.selected = true;
    }
    categoryFilter.appendChild(allOption);
    
    categories.forEach(category => {
        const option = document.createElement('option');
        option.value = category.id.toString();
        option.textContent = category.title;
        if (currentCategoryId && category.id === currentCategoryId) {
            option.selected = true;
            allOption.selected = false;
        }
        categoryFilter.appendChild(option);
    });
    
    filterContainer.innerHTML = '';
    filterContainer.appendChild(categoryFilter);
    
    // Обработчик изменения фильтра
    categoryFilter.addEventListener('change', () => {
        const categoryId = categoryFilter.value;
        if (categoryId) {
            window.location.href = `/all-courses-pg?category_id=${categoryId}`;
        } else {
            window.location.href = '/all-courses-pg';
        }
    });
}

// Загрузка курсов
async function loadCourses(categoryId = null) {
    try {
        const categoryIdToUse = categoryId || currentCategoryId;
        let url = `${API_BASE}/courses`;
        if (categoryIdToUse) {
            url += `?category_id=${categoryIdToUse}`;
        }
        
        const response = await fetch(url);
        const data = await response.json();
        
        if (response.ok) {
            // Загружаем прогресс для каждого курса
            const coursesWithProgress = await Promise.all(
                (data.courses || []).map(async (course) => {
                    const progress = await loadCourseProgress(course.id);
                    course.progress = progress;
                    return course;
                })
            );
            renderCourses(coursesWithProgress);
        } else {
            showError('Не удалось загрузить курсы');
        }
    } catch (error) {
        console.error('Ошибка загрузки курсов:', error);
        showError('Ошибка загрузки курсов');
    }
}

// Загрузка прогресса по курсу
async function loadCourseProgress(courseId) {
    try {
        const response = await fetch(`${API_BASE}/courses/${courseId}/progress`);
        const data = await response.json();
        return response.ok ? data : { status: 'not_started', progress_percentage: 0 };
    } catch (error) {
        console.error('Ошибка загрузки прогресса:', error);
        return { status: 'not_started', progress_percentage: 0 };
    }
}

// Отображение курсов
function renderCourses(courses) {
    if (!coursesContainer) {
        console.error('Контейнер курсов не найден');
        return;
    }
    
    coursesContainer.innerHTML = '';
    
    if (courses.length === 0) {
        coursesContainer.innerHTML = '<p class="empty-message">Курсы не найдены</p>';
        return;
    }
    
    courses.forEach(course => {
        const card = createCourseCard(course);
        coursesContainer.appendChild(card);
    });
}

// Создание карточки курса (использует единый модуль)
function createCourseCard(course) {
    // Используем функцию из unified-card-builder.js
    if (typeof window.createCourseCardFromModule === 'function') {
        return window.createCourseCardFromModule(course, { currentUserRole });
    }
    // Fallback на локальную реализацию
    return createCourseCardLocal(course);
}

// Локальная реализация (fallback) - использует unified-card классы
function createCourseCardLocal(course) {
    const isAccessible = course.is_accessible !== false;
    const lockedReason = course.locked_reason || 'Материал недоступен. Пройдите предыдущие курсы в последовательности.';
    
    const card = document.createElement('article');
    card.className = 'unified-card course-card' + (!isAccessible ? ' card-locked' : '');
    card.dataset.courseId = course.id;
    card.dataset.isAccessible = isAccessible ? '1' : '0';
    card.dataset.lockedReason = lockedReason.replace(/"/g, '&quot;');
    
    // Индикатор последовательного прохождения
    const sequentialIndicator = course.sequential_progression 
        ? '<span class="sequential-badge" title="Последовательное прохождение уроков">🔒</span>' 
        : '';
    
    // Определяем статус прогресса
    const progress = course.progress || { status: 'not_started', progress_percentage: 0 };
    let statusClass = 'not-started';
    let statusText = 'неначат';
    
    if (progress.status === 'completed') {
        statusClass = 'completed';
        statusText = 'завершен';
    } else if (progress.status === 'in_progress') {
        statusClass = 'in-progress';
        statusText = 'в процессе';
    }
    
    // Кнопки для админа (в правой части статус-панели)
    const adminButtons = (currentUserRole === 'admin' || currentUserRole === 'super_admin') ? `
        <button class="btn-action-icon btn-edit-icon" onclick="editCourse(${course.id}, event)" title="Изменить">✎</button>
        <button class="btn-action-icon btn-settings-icon" onclick="openCourseSettings(${course.id}, event)" title="Настройки">⚙</button>
        <button class="btn-action-icon btn-delete-icon" onclick="deleteCourse(${course.id}, event)" title="Удалить">×</button>
    ` : '';
    
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
                ${!isAccessible ? `<p class="locked-reason">${escapeHtml(lockedReason)}</p>` : ''}
                ${((progress.total_lessons ?? course.total_lessons ?? 0) > 0) ? `
                    <div class="progress-info"><span class="progress-text">${progress.lessons_completed ?? 0} из ${progress.total_lessons ?? course.total_lessons ?? 0}</span></div>
                ` : ''}
            </div>
            <div class="status-panel ${statusClass}">
                <div class="status-left">
                    <span class="status-text">${statusText}</span>
                    <button class="btn-action-icon btn-open-icon" onclick="typeof handleCourseOpenClick==='function'?handleCourseOpenClick(event):openCourse(${course.id})" title="Открыть курс">→</button>
                    <button class="btn-action-icon btn-question-icon" onclick="askQuestionAboutCourse(${course.id}, event)" title="Задать вопрос">?</button>
                </div>
                <div class="status-right">
                    ${adminButtons}
                </div>
            </div>
        </div>
    `;
    
    card.addEventListener('dblclick', (e) => {
        if (!e.target.closest('button')) {
            if (isAccessible) openCourse(course.id);
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

// Открыть курс (переход к урокам)
function openCourse(courseId) {
    window.location.href = `/all-lessons-pg?course_id=${courseId}`;
}

// Задать вопрос по курсу — переход на страницу вопросов с формой создания
async function askQuestionAboutCourse(courseId, event) {
    if (event) event.stopPropagation();
    try {
        const response = await fetch(`${API_BASE}/courses/${courseId}`);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        const categoryResponse = await fetch(`${API_BASE}/categories/${data.category_id}`);
        if (!categoryResponse.ok) throw new Error(`HTTP error! status: ${categoryResponse.status}`);
        const categoryData = await categoryResponse.json();
        const title = `Вопрос по курсу: ${data.title}`;
        const tags = `Категория: ${categoryData.title || ''}, Курс: ${data.title}`;
        window.location.href = `/questions-pg?tab=ask&title=${encodeURIComponent(title)}&tags=${encodeURIComponent(tags)}`;
    } catch (error) {
        console.error('Ошибка:', error);
        showError(error.message || 'Не удалось перейти к форме вопроса');
    }
}

// Удалить курс
async function deleteCourse(courseId, event) {
    if (event) event.stopPropagation();
    
    const confirmed = await customConfirm('Удалить этот курс? Он будет перемещен в корзину вместе со всеми уроками.');
    if (!confirmed) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/courses/${courseId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        showSuccess('Курс перемещен в корзину');
        loadCourses();
    } catch (error) {
        console.error('Ошибка:', error);
        showError('Не удалось удалить курс');
    }
}

// Редактировать курс
async function editCourse(courseId, event) {
    if (event) event.stopPropagation();
    
    // Сразу показываем модалку (как при создании), чтобы не было ощущения "не нажалось"
    let editModal = document.getElementById('edit-course-modal');
    if (!editModal) {
        editModal = document.createElement('div');
        editModal.id = 'edit-course-modal';
        editModal.className = 'modal-overlay';
        document.body.appendChild(editModal);
    }
    editModal.innerHTML = `
        <div class="modal-container">
            <div class="modal-header">
                <h2 class="modal-title">Изменить курс</h2>
                <button class="modal-close" onclick="closeEditCourseModal()" aria-label="Закрыть">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </button>
            </div>
            <div class="modal-body">
                <div style="padding: 1rem 0; color:#666;">Загрузка…</div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn-cancel" onclick="closeEditCourseModal()">Отмена</button>
            </div>
        </div>
    `;
    editModal.style.display = 'flex';
    editModal.addEventListener('click', (e) => {
        if (e.target === editModal) closeEditCourseModal();
    });

    try {
        const response = await fetch(`${API_BASE}/courses/${courseId}`);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Курс не найден');
        }
        
        openEditCourseModal(data);
    } catch (error) {
        console.error('Ошибка:', error);
        closeEditCourseModal();
        showError('Не удалось загрузить данные курса');
    }
}

// Открыть настройки курса
async function openCourseSettings(courseId, event) {
    if (event) event.stopPropagation();
    
    try {
        // Загружаем данные курса
        const courseResponse = await fetch(`${API_BASE}/courses/${courseId}`);
        const courseData = await courseResponse.json();
        
        if (!courseResponse.ok) {
            throw new Error(courseData.error || 'Курс не найден');
        }
        
        // Загружаем отделы с доступом
        const deptResponse = await fetch(`${API_BASE}/courses/${courseId}/departments`);
        const deptData = await deptResponse.json();
        
        // Загружаем все отделы
        const allDeptResponse = await fetch(`${API_BASE}/departments`);
        const allDeptData = await allDeptResponse.json();
        
        showCourseSettingsModal(courseData, deptData.departments || [], allDeptData.departments || []);
    } catch (error) {
        console.error('Ошибка:', error);
        showError('Не удалось загрузить настройки курса');
    }
}

// Показать модальное окно настроек курса
function showCourseSettingsModal(course, currentDepartments, allDepartments) {
    let settingsModal = document.getElementById('course-settings-modal');
    if (!settingsModal) {
        settingsModal = document.createElement('div');
        settingsModal.id = 'course-settings-modal';
        settingsModal.className = 'modal-overlay';
        document.body.appendChild(settingsModal);
    }
    
    // Создаем список отделов с чекбоксами
    const departmentsList = allDepartments.map(dept => {
        const isChecked = currentDepartments.some(cd => cd === dept || (typeof cd === 'object' && cd.name === dept));
        const deptName = typeof dept === 'object' ? dept.name : dept;
        return `
            <label class="department-checkbox">
                <input type="checkbox" value="${escapeHtml(deptName)}" ${isChecked ? 'checked' : ''}>
                <span>${escapeHtml(deptName)}</span>
            </label>
        `;
    }).join('');
    
    settingsModal.innerHTML = `
        <div class="modal-container course-settings-container">
            <div class="modal-header">
                <h2 class="modal-title">Настройки курса</h2>
                <button class="modal-close" onclick="closeCourseSettingsModal()" aria-label="Закрыть">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </button>
            </div>
            <div class="modal-body">
                <form id="course-settings-form" onsubmit="event.preventDefault(); saveCourseSettings(${course.id});">
                    <div class="form-group">
                        <label for="course-title-display" class="form-label">Название курса</label>
                        <div class="form-readonly">${escapeHtml(course.title)}</div>
                    </div>
                <div class="form-group">
                        <label for="course-type-select" class="form-label">Тип курса <span class="required">*</span></label>
                        <select id="course-type-select" class="form-input" required>
                        <option value="free" ${!course.sequential_progression ? 'selected' : ''}>Свободный (уроки можно проходить в любом порядке)</option>
                        <option value="sequential" ${course.sequential_progression ? 'selected' : ''}>Последовательный (уроки проходятся по порядку)</option>
                    </select>
                </div>
                <div class="form-group">
                        <label class="form-label">Отделы с доступом к курсу</label>
                    <div class="departments-list">
                            ${departmentsList || '<p class="empty-message">Отделы не найдены</p>'}
                        </div>
                    </div>
                </form>
                </div>
            <div class="modal-footer">
                <button type="button" class="btn-cancel" onclick="closeCourseSettingsModal()">Отмена</button>
                <button type="submit" form="course-settings-form" class="btn-submit">Сохранить</button>
                </div>
        </div>
    `;
    settingsModal.style.display = 'flex';
    
    // Закрытие по клику на overlay
    settingsModal.addEventListener('click', (e) => {
        if (e.target === settingsModal) {
            closeCourseSettingsModal();
        }
    });
}

// Сохранить настройки курса
async function saveCourseSettings(courseId) {
    try {
        const courseType = document.getElementById('course-type-select').value;
        const sequentialProgression = courseType === 'sequential';
        
        // Получаем выбранные отделы
        const checkboxes = document.querySelectorAll('#course-settings-modal input[type="checkbox"]:checked');
        const departments = Array.from(checkboxes).map(cb => cb.value);
        
        // Обновляем тип курса
        const courseResponse = await fetch(`${API_BASE}/courses/${courseId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                sequential_progression: sequentialProgression
            })
        });
        
        if (!courseResponse.ok) {
            throw new Error('Ошибка обновления типа курса');
        }
        
        // Обновляем доступ по отделам
        const deptResponse = await fetch(`${API_BASE}/courses/${courseId}/departments`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                departments: departments
            })
        });
        
        if (!deptResponse.ok) {
            const errorData = await deptResponse.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP error! status: ${deptResponse.status}`);
        }
        const deptData = await deptResponse.json();
        showSuccess('Настройки курса сохранены');
        closeCourseSettingsModal();
        loadCourses();
    } catch (error) {
        console.error('Ошибка:', error);
        showError('Не удалось сохранить настройки');
    }
}

// Закрыть модальное окно настроек
function closeCourseSettingsModal() {
    const settingsModal = document.getElementById('course-settings-modal');
    if (settingsModal) {
        settingsModal.style.display = 'none';
    }
}

// Создание курса
async function createCourse() {
    if (currentUserRole !== 'admin' && currentUserRole !== 'super_admin') {
        showError('Требуются права администратора');
        return;
    }
    
    if (!currentCategoryId) {
        showError('Выберите категорию для курса');
        return;
    }
    
    const titleInput = document.getElementById('course-title');
    const descriptionInput = document.getElementById('course-description');
    const typeSelect = document.getElementById('course-type');
    
    const title = (titleInput?.value || '').trim();
    const description = (descriptionInput?.value || '').trim();
    const sequentialProgression = (typeSelect?.value || 'free') === 'sequential';
    
    if (!title) {
        showError('Название курса обязательно');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/courses`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                category_id: parseInt(currentCategoryId, 10),
                title,
                description,
                sequential_progression: sequentialProgression
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showSuccess('Курс создан');
            closeCreateCourseModal();
            loadCourses();
        } else {
            showError(data.error || 'Ошибка при создании курса');
        }
    } catch (error) {
        console.error('Ошибка создания курса:', error);
        showError('Не удалось создать курс');
    }
}

// Открыть модальное окно создания курса
function openCreateCourseModal() {
    if (!currentCategoryId) {
        showError('Выберите категорию для создания курса');
        return;
    }
    
    let createModal = document.getElementById('create-course-modal');
    if (!createModal) {
        createModal = document.createElement('div');
        createModal.id = 'create-course-modal';
        createModal.className = 'modal-overlay';
        document.body.appendChild(createModal);
    }
    
    createModal.innerHTML = `
        <div class="modal-container">
            <div class="modal-header">
                <h2 class="modal-title">Создать курс</h2>
                <button class="modal-close" onclick="closeCreateCourseModal()" aria-label="Закрыть">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </button>
            </div>
            <div class="modal-body">
                <form id="create-course-form" onsubmit="event.preventDefault(); createCourse();">
                    <div class="form-group">
                        <label for="course-title" class="form-label">Название <span class="required">*</span></label>
                        <input type="text" id="course-title" class="form-input" placeholder="Введите название курса" required />
                    </div>
                    <div class="form-group">
                        <label for="course-description" class="form-label">Описание</label>
                        <textarea id="course-description" class="form-textarea" rows="4" placeholder="Введите описание курса"></textarea>
                    </div>
                    <div class="form-group">
                        <label for="course-type" class="form-label">Тип прохождения</label>
                        <select id="course-type" class="form-input">
                            <option value="free" selected>Свободный (уроки можно проходить в любом порядке)</option>
                            <option value="sequential">Последовательный (следующий урок доступен только после прохождения предыдущего)</option>
                        </select>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn-cancel" onclick="closeCreateCourseModal()">Отмена</button>
                <button type="submit" form="create-course-form" class="btn-submit">Создать</button>
            </div>
        </div>
    `;
    createModal.style.display = 'flex';
    
    // Закрытие по клику на overlay
    createModal.addEventListener('click', (e) => {
        if (e.target === createModal) {
            closeCreateCourseModal();
        }
    });
}

// Закрыть модальное окно создания курса
function closeCreateCourseModal() {
    const createModal = document.getElementById('create-course-modal');
    if (createModal) {
        createModal.style.display = 'none';
        // Очищаем форму
        const titleInput = document.getElementById('course-title');
        const descriptionInput = document.getElementById('course-description');
        if (titleInput) titleInput.value = '';
        if (descriptionInput) descriptionInput.value = '';
    }
}

// Открыть модальное окно редактирования курса
function openEditCourseModal(course) {
    let editModal = document.getElementById('edit-course-modal');
    if (!editModal) {
        editModal = document.createElement('div');
        editModal.id = 'edit-course-modal';
        editModal.className = 'modal-overlay';
        document.body.appendChild(editModal);
    }
    
    editModal.innerHTML = `
        <div class="modal-container">
            <div class="modal-header">
                <h2 class="modal-title">Изменить курс</h2>
                <button class="modal-close" onclick="closeEditCourseModal()" aria-label="Закрыть">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </button>
            </div>
            <div class="modal-body">
                <form id="edit-course-form" onsubmit="event.preventDefault(); updateCourse(${course.id});">
                <div class="form-group">
                        <label for="edit-course-title" class="form-label">Название <span class="required">*</span></label>
                        <input type="text" id="edit-course-title" class="form-input" value="${escapeHtml(course.title || '')}" required />
                </div>
                <div class="form-group">
                        <label for="edit-course-description" class="form-label">Описание</label>
                        <textarea id="edit-course-description" class="form-textarea" rows="4">${escapeHtml(course.description || '')}</textarea>
                </div>
                <div class="form-group">
                        <label for="edit-course-order" class="form-label">Порядок</label>
                        <input type="number" id="edit-course-order" class="form-input" value="${course.order || 0}" min="0" />
                </div>
            </form>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn-cancel" onclick="closeEditCourseModal()">Отмена</button>
                <button type="submit" form="edit-course-form" class="btn-submit">Сохранить</button>
            </div>
        </div>
    `;
    editModal.style.display = 'flex';
    
    // Закрытие по клику на overlay
    editModal.addEventListener('click', (e) => {
        if (e.target === editModal) {
            closeEditCourseModal();
        }
    });
}

// Обновить курс
async function updateCourse(courseId) {
    const titleInput = document.getElementById('edit-course-title');
    const descriptionInput = document.getElementById('edit-course-description');
    const orderInput = document.getElementById('edit-course-order');
    
    const title = (titleInput?.value || '').trim();
    const description = (descriptionInput?.value || '').trim();
    const order = parseInt(orderInput?.value || '0', 10);
    
    if (!title) {
        showError('Название курса обязательно');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/courses/${courseId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                title,
                description,
                order
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        showSuccess('Курс обновлен');
        closeEditCourseModal();
        loadCourses();
    } catch (error) {
        console.error('Ошибка обновления курса:', error);
        showError('Не удалось обновить курс');
    }
}

// Закрыть модальное окно редактирования курса
function closeEditCourseModal() {
    const editModal = document.getElementById('edit-course-modal');
    if (editModal) {
        editModal.style.display = 'none';
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
    customAlert(message, 'Ошибка');
}

function showSuccess(message) {
    customAlert(message, 'Успешно');
}

// Настройка обработчиков событий
function setupEventListeners() {
    // Обработчик для кнопки создания курса
    const createCourseBtn = document.getElementById('create-course-btn');
    if (createCourseBtn) {
        createCourseBtn.addEventListener('click', openCreateCourseModal);
    }
    
    // Закрытие модальных окон по Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const createModal = document.getElementById('create-course-modal');
            if (createModal && createModal.style.display === 'flex') {
                closeCreateCourseModal();
            }
            const editModal = document.getElementById('edit-course-modal');
            if (editModal && editModal.style.display === 'flex') {
                closeEditCourseModal();
            }
        }
    });
}

// Экспорт функций
window.openCourse = openCourse;
window.createCourse = createCourse;
window.updateCourse = updateCourse;
window.deleteCourse = deleteCourse;
window.editCourse = editCourse;
window.askQuestionAboutCourse = askQuestionAboutCourse;
window.openCourseSettings = openCourseSettings;
window.saveCourseSettings = saveCourseSettings;
window.closeCourseSettingsModal = closeCourseSettingsModal;
window.openCreateCourseModal = openCreateCourseModal;
window.closeCreateCourseModal = closeCreateCourseModal;
window.closeEditCourseModal = closeEditCourseModal;
