/**
 * JavaScript для страницы списка категорий
 */

const API_BASE = '/api';

// DOM элементы
let categoriesContainer = null;
let createCategoryBtn = null;
let createCategoryModal = null;
let currentUserRole = 'user';
let breadcrumbsContainer = null;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    categoriesContainer = document.querySelector('.categories-grid') || document.querySelector('.courses-grid');
    createCategoryBtn = document.getElementById('create-category-btn');
    createCategoryModal = document.getElementById('create-category-modal');
    breadcrumbsContainer = document.querySelector('.breadcrumbs');
    
    // Создаем breadcrumbs
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
    updateBreadcrumbs([]);
    
    // Проверяем роль пользователя
    checkUserRole();
    
    // Загружаем категории
    loadCategories();
    
    // Настраиваем обработчики событий
    setupEventListeners();
});

// Обновление breadcrumbs
function updateBreadcrumbs(path) {
    if (!breadcrumbsContainer) return;
    
    let breadcrumbs = '<a href="/main-pg">Главная</a>';
    breadcrumbs += ' > <a href="/all-categories-pg">База знаний</a>';
    
    if (path.length > 0) {
        path.forEach((item, index) => {
            if (index < path.length - 1) {
                breadcrumbs += ` > <a href="${item.url}">${escapeHtml(item.title)}</a>`;
            } else {
                breadcrumbs += ` > <span>${escapeHtml(item.title)}</span>`;
            }
        });
    }
    
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
    // Показываем большую голубую кнопку "Добавить категорию"
    const addSection = document.querySelector('.add-category-section');
    if (addSection) {
        addSection.style.display = 'flex';
    }
    
    // Показываем кнопку в секции добавления, если есть
    if (createCategoryBtn) {
        createCategoryBtn.style.display = 'flex';
    }
}

// Загрузка категорий
async function loadCategories() {
    try {
        const response = await fetch(`${API_BASE}/categories`);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        const categories = Array.isArray(data)
            ? data
            : (Array.isArray(data.categories) ? data.categories : []);
        renderCategories(categories);
    } catch (error) {
        console.error('Ошибка загрузки категорий:', error);
        showError('Ошибка загрузки категорий');
    }
}

// Отображение категорий
async function renderCategories(categories) {
    if (!categoriesContainer) {
        console.error('Контейнер категорий не найден');
        return;
    }
    
    categoriesContainer.innerHTML = '';
    
    if (categories.length === 0) {
        categoriesContainer.innerHTML = '<p class="empty-message">Категории не найдены</p>';
        return;
    }
    
    // Загружаем прогресс для каждой категории
    for (const category of categories) {
        const progress = await loadCategoryProgress(category.id);
        category.progress = progress;
        const card = createCategoryCard(category);
        categoriesContainer.appendChild(card);
    }
}

// Загрузка прогресса по категории
async function loadCategoryProgress(categoryId) {
    try {
        const response = await fetch(`${API_BASE}/categories/${categoryId}/progress`);
        if (!response.ok) {
            return { status: 'not_started', progress_percentage: 0 };
        }
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Ошибка загрузки прогресса:', error);
        return { status: 'not_started', progress_percentage: 0 };
    }
}

// Создание карточки категории (использует единый модуль)
function createCategoryCard(category) {
    // Используем функцию из unified-card-builder.js
    if (typeof window.createCategoryCardFromModule === 'function') {
        return window.createCategoryCardFromModule(category, { currentUserRole });
    }
    // Fallback на локальную реализацию
    return createCategoryCardLocal(category);
}

// Локальная реализация (fallback) - использует unified-card классы
function createCategoryCardLocal(category) {
    const card = document.createElement('article');
    card.className = 'unified-card category-card';
    card.dataset.categoryId = category.id;
    
    // Определяем статус прогресса
    const progress = category.progress || { status: 'not_started', progress_percentage: 0 };
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
        <button class="btn-action-icon btn-edit-icon" onclick="editCategory(${category.id}, event)" title="Изменить">✎</button>
        <button class="btn-action-icon btn-delete-icon" onclick="deleteCategory(${category.id}, event)" title="Удалить">×</button>
    ` : '';
    
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
                ${((progress.total_courses ?? category.courses_count ?? 0) > 0) ? `
                    <div class="progress-info"><span class="progress-text">${progress.courses_completed ?? 0} из ${progress.total_courses ?? category.courses_count ?? 0}</span></div>
                ` : ''}
            </div>
            <div class="status-panel ${statusClass}">
                <div class="status-left">
                    <span class="status-text">${statusText}</span>
                    <button class="btn-action-icon btn-open-icon" onclick="openCategory(${category.id})" title="Открыть категорию">→</button>
                    <button class="btn-action-icon btn-question-icon" onclick="askQuestionAboutCategory(${category.id}, event)" title="Задать вопрос">?</button>
                </div>
                <div class="status-right">
                    ${adminButtons}
                </div>
            </div>
        </div>
    `;
    
    // Двойной клик для открытия категории
    card.addEventListener('dblclick', () => openCategory(category.id));
    
    return card;
}

// Открыть категорию (переход к курсам)
function openCategory(categoryId) {
    window.location.href = `/all-courses-pg?category_id=${categoryId}`;
}

// Задать вопрос по категории — переход на страницу вопросов с формой создания
async function askQuestionAboutCategory(categoryId, event) {
    if (event) event.stopPropagation();
    try {
        const response = await fetch(`${API_BASE}/categories/${categoryId}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Категория не найдена');
        const title = `Вопрос по категории: ${data.title}`;
        const tags = `Категория: ${data.title}`;
        window.location.href = `/questions-pg?tab=ask&title=${encodeURIComponent(title)}&tags=${encodeURIComponent(tags)}`;
    } catch (error) {
        console.error('Ошибка:', error);
        showError(error.message || 'Не удалось перейти к форме вопроса');
    }
}

// Удалить категорию
async function deleteCategory(categoryId, event) {
    if (event) event.stopPropagation();
    
    const confirmed = await customConfirm('Удалить эту категорию? Она будет перемещена в корзину вместе со всеми курсами и уроками.');
    if (!confirmed) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/categories/${categoryId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        showSuccess('Категория перемещена в корзину');
        loadCategories();
    } catch (error) {
        console.error('Ошибка:', error);
        showError('Не удалось удалить категорию');
    }
}

// Редактировать категорию
async function editCategory(categoryId, event) {
    if (event) event.stopPropagation();
    
    try {
        const response = await fetch(`${API_BASE}/categories/${categoryId}`);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Категория не найдена');
        }
        
        openEditCategoryModal(data);
    } catch (error) {
        console.error('Ошибка:', error);
        showError('Не удалось загрузить данные категории');
    }
}

// Создание категории (admin)
async function createCategory() {
    if (currentUserRole !== 'admin' && currentUserRole !== 'super_admin') {
        showError('Требуются права администратора');
        return;
    }
    
    const titleInput = document.getElementById('category-title');
    const descriptionInput = document.getElementById('category-description');
    const typeSelect = document.getElementById('category-type');
    
    const title = (titleInput?.value || '').trim();
    const description = (descriptionInput?.value || '').trim();
    const sequentialProgression = (typeSelect?.value || 'free') === 'sequential';
    
    if (!title) {
        showError('Название категории обязательно');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/categories`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                title,
                description,
                sequential_progression: sequentialProgression
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        showSuccess('Категория создана');
        closeCreateCategoryModal();
        loadCategories();
    } catch (error) {
        console.error('Ошибка создания категории:', error);
        showError('Не удалось создать категорию');
    }
}

// Обновление категории
async function updateCategory(categoryId) {
    const titleInput = document.getElementById('edit-category-title');
    const descriptionInput = document.getElementById('edit-category-description');
    const orderInput = document.getElementById('edit-category-order');
    const typeSelect = document.getElementById('edit-category-type');
    
    const title = (titleInput?.value || '').trim();
    const description = (descriptionInput?.value || '').trim();
    const order = parseInt(orderInput?.value || '0', 10);
    const sequentialProgression = (typeSelect?.value || 'free') === 'sequential';
    
    if (!title) {
        showError('Название категории обязательно');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/categories/${categoryId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                title,
                description,
                order,
                sequential_progression: sequentialProgression
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        showSuccess('Категория обновлена');
        closeEditCategoryModal();
        loadCategories();
    } catch (error) {
        console.error('Ошибка обновления категории:', error);
        showError('Не удалось обновить категорию');
    }
}

// Открыть модальное окно создания категории
function openCreateCategoryModal() {
    if (createCategoryModal) {
        createCategoryModal.style.display = 'flex';
    } else {
        // Создаем модальное окно
        const modal = document.createElement('div');
        modal.id = 'create-category-modal';
        modal.className = 'modal-overlay';
        modal.style.display = 'flex';
        modal.innerHTML = `
            <div class="modal-container">
                <div class="modal-header">
                    <h2 class="modal-title">Создать категорию</h2>
                    <button class="modal-close" onclick="closeCreateCategoryModal()" aria-label="Закрыть">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                    </button>
                </div>
                <div class="modal-body">
                    <form id="create-category-form" onsubmit="event.preventDefault(); createCategory();">
                        <div class="form-group">
                            <label for="category-title" class="form-label">Название <span class="required">*</span></label>
                            <input type="text" id="category-title" class="form-input" placeholder="Введите название категории" required />
                        </div>
                        <div class="form-group">
                            <label for="category-description" class="form-label">Описание</label>
                            <textarea id="category-description" class="form-textarea" rows="4" placeholder="Введите описание категории"></textarea>
                        </div>
                        <div class="form-group">
                            <label for="category-type" class="form-label">Тип прохождения</label>
                            <select id="category-type" class="form-input">
                                <option value="free" selected>Свободный (курсы доступны сразу)</option>
                                <option value="sequential">Последовательный (следующий курс доступен после прохождения предыдущего)</option>
                            </select>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn-cancel" onclick="closeCreateCategoryModal()">Отмена</button>
                    <button type="submit" form="create-category-form" class="btn-submit">Создать</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        createCategoryModal = modal;
        
        // Закрытие по клику на overlay
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeCreateCategoryModal();
            }
        });
    }
}

// Открыть модальное окно редактирования категории
function openEditCategoryModal(category) {
    let editModal = document.getElementById('edit-category-modal');
    if (!editModal) {
        editModal = document.createElement('div');
        editModal.id = 'edit-category-modal';
        editModal.className = 'modal-overlay';
        document.body.appendChild(editModal);
    }
    
    editModal.innerHTML = `
        <div class="modal-container">
            <div class="modal-header">
                <h2 class="modal-title">Изменить категорию</h2>
                <button class="modal-close" onclick="closeEditCategoryModal()" aria-label="Закрыть">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </button>
            </div>
            <div class="modal-body">
                <form id="edit-category-form" onsubmit="event.preventDefault(); updateCategory(${category.id});">
                    <div class="form-group">
                        <label for="edit-category-title" class="form-label">Название <span class="required">*</span></label>
                        <input type="text" id="edit-category-title" class="form-input" value="${escapeHtml(category.title || '')}" required />
                    </div>
                    <div class="form-group">
                        <label for="edit-category-description" class="form-label">Описание</label>
                        <textarea id="edit-category-description" class="form-textarea" rows="4">${escapeHtml(category.description || '')}</textarea>
                    </div>
                    <div class="form-group">
                        <label for="edit-category-order" class="form-label">Порядок отображения</label>
                        <input type="number" id="edit-category-order" class="form-input" value="${category.order || 0}" min="0" />
                    </div>
                    <div class="form-group">
                        <label for="edit-category-type" class="form-label">Тип прохождения</label>
                        <select id="edit-category-type" class="form-input">
                            <option value="free" ${!category.sequential_progression ? 'selected' : ''}>Свободный (курсы доступны сразу)</option>
                            <option value="sequential" ${category.sequential_progression ? 'selected' : ''}>Последовательный (следующий курс доступен после прохождения предыдущего)</option>
                        </select>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn-cancel" onclick="closeEditCategoryModal()">Отмена</button>
                <button type="submit" form="edit-category-form" class="btn-submit">Сохранить</button>
            </div>
        </div>
    `;
    editModal.style.display = 'flex';
    
    // Закрытие по клику на overlay
    editModal.addEventListener('click', (e) => {
        if (e.target === editModal) {
            closeEditCategoryModal();
        }
    });
}

// Закрыть модальное окно создания категории
function closeCreateCategoryModal() {
    if (createCategoryModal) {
        createCategoryModal.style.display = 'none';
        // Очищаем форму
        const titleInput = document.getElementById('category-title');
        const descriptionInput = document.getElementById('category-description');
        if (titleInput) titleInput.value = '';
        if (descriptionInput) descriptionInput.value = '';
    }
}

// Закрыть модальное окно редактирования категории
function closeEditCategoryModal() {
    const editModal = document.getElementById('edit-category-modal');
    if (editModal) {
        editModal.style.display = 'none';
    }
}

// Настройка обработчиков событий
function setupEventListeners() {
    if (createCategoryBtn) {
        createCategoryBtn.addEventListener('click', openCreateCategoryModal);
    }
    
    // Закрытие модальных окон по Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (createCategoryModal && createCategoryModal.style.display === 'flex') {
                closeCreateCategoryModal();
            }
            const editModal = document.getElementById('edit-category-modal');
            if (editModal && editModal.style.display === 'flex') {
                closeEditCategoryModal();
            }
        }
    });
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

// Экспорт функций для использования в HTML
window.openCategory = openCategory;
window.createCategory = createCategory;
window.updateCategory = updateCategory;
window.deleteCategory = deleteCategory;
window.editCategory = editCategory;
window.askQuestionAboutCategory = askQuestionAboutCategory;
window.openCreateCategoryModal = openCreateCategoryModal;
window.closeCreateCategoryModal = closeCreateCategoryModal;
window.closeEditCategoryModal = closeEditCategoryModal;
