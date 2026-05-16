/**
 * JavaScript для страницы корзины
 */

const API_BASE = '/api';

// DOM элементы
let deletedObjectsContainer = null;
let binSortFilter = null;
let allDeletedObjects = [];
let currentSortType = 'all'; // 'all' | 'category' | 'course' | 'lesson'

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    deletedObjectsContainer = document.getElementById('deleted-objects-container');
    createBinSortFilter();
    
    // Проверяем роль пользователя
    checkUserRole();
    
    // Загружаем удаленные объекты
    loadDeletedObjects();
});

// Создание фильтра сортировки по типу
function createBinSortFilter() {
    const container = document.getElementById('bin-sort-filter');
    if (!container) return;
    
    binSortFilter = document.createElement('select');
    binSortFilter.id = 'bin-sort-select';
    binSortFilter.title = 'Сортировка по типу';
    binSortFilter.innerHTML = `
        <option value="all">Все объекты</option>
        <option value="category">Категории</option>
        <option value="course">Курсы</option>
        <option value="lesson">Уроки</option>
    `;
    
    binSortFilter.addEventListener('change', () => {
        currentSortType = binSortFilter.value;
        renderDeletedObjects(allDeletedObjects);
    });
    
    container.innerHTML = '';
    container.appendChild(binSortFilter);
}

// Проверка роли пользователя
async function checkUserRole() {
    try {
        const response = await fetch(`${API_BASE}/current-user`);
        const data = await response.json();
        const role = (data.effective_role || data.role || '').toLowerCase();
        if (response.ok && role !== 'admin' && role !== 'super_admin') {
            // Если не админ и не супер-админ, перенаправляем
            window.location.href = '/main-pg';
        }
    } catch (error) {
        console.error('Ошибка проверки роли:', error);
        window.location.href = '/main-pg';
    }
}

// Загрузка удаленных объектов
async function loadDeletedObjects() {
    try {
        const response = await fetch(`${API_BASE}/bin`);
        const data = await response.json();
        
        if (response.ok) {
            allDeletedObjects = data.deleted_objects || [];
            renderDeletedObjects(allDeletedObjects);
        } else {
            showError('Не удалось загрузить корзину');
        }
    } catch (error) {
        console.error('Ошибка загрузки корзины:', error);
        showError('Ошибка загрузки корзины');
    }
}

// Отображение удаленных объектов
function renderDeletedObjects(objects) {
    if (!deletedObjectsContainer) {
        console.error('Контейнер корзины не найден');
        return;
    }
    
    deletedObjectsContainer.innerHTML = '';
    
    if (objects.length === 0) {
        deletedObjectsContainer.innerHTML = '<p class="empty-message">Корзина пуста</p>';
        return;
    }
    
    // Фильтруем по выбранному типу
    let filtered = objects;
    if (currentSortType && currentSortType !== 'all') {
        filtered = objects.filter(obj => obj.object_type === currentSortType);
    }
    
    if (filtered.length === 0) {
        deletedObjectsContainer.innerHTML = '<p class="empty-message">Нет объектов выбранного типа</p>';
        return;
    }
    
    // Сортируем: категории → курсы → уроки, внутри типа по дате удаления
    const typeOrder = { 'category': 0, 'course': 1, 'lesson': 2 };
    const sorted = [...filtered].sort((a, b) => {
        const orderA = typeOrder[a.object_type] ?? 3;
        const orderB = typeOrder[b.object_type] ?? 3;
        if (orderA !== orderB) return orderA - orderB;
        return new Date(b.deleted_at) - new Date(a.deleted_at);
    });
    
    sorted.forEach(obj => {
        deletedObjectsContainer.appendChild(createDeletedObjectCard(obj));
    });
}

// Создание карточки удаленного объекта (использует единый модуль)
function createDeletedObjectCard(obj) {
    // Используем функцию из unified-card-builder.js
    if (typeof window.createDeletedObjectCardFromModule === 'function') {
        return window.createDeletedObjectCardFromModule(obj);
    }
    // Fallback на локальную реализацию
    return createDeletedObjectCardLocal(obj);
}

// Локальная реализация (fallback) - использует unified-card классы
function createDeletedObjectCardLocal(obj) {
    const card = document.createElement('article');
    card.className = 'unified-card deleted-object-card';
    card.dataset.deletedId = obj.id;
    
    const objectData = obj.object_data || {};
    const deletedDate = new Date(obj.deleted_at);
    const daysLeft = obj.days_until_permanent_delete || 0;
    
    card.innerHTML = `
        <div class="card-content">
            <div class="card-header">
                <h3 class="card-title">${escapeHtml(objectData.title || 'Без названия')}</h3>
            </div>
            <div class="card-main">
                <p class="card-description">${escapeHtml(objectData.description || '')}</p>
                <div class="card-stats">
                    <span class="object-type">${getObjectTypeLabel(obj.object_type)}</span>
                </div>
                <p class="deleted-info">
                    Удалено: ${deletedDate.toLocaleDateString('ru-RU')}
                </p>
                <p class="days-left ${daysLeft <= 7 ? 'warning' : ''}">
                    Осталось дней до полного удаления: ${daysLeft}
                </p>
            </div>
            <div class="status-panel not-started">
                <div class="status-left">
                    <span class="status-text">удалено</span>
                </div>
                <div class="status-right">
                    <button class="btn-action-icon btn-restore-icon" onclick="restoreObject(${obj.id})" title="Восстановить">↻</button>
                </div>
            </div>
        </div>
    `;
    
    return card;
}

// Получить метку типа объекта
function getObjectTypeLabel(type) {
    const labels = {
        'category': 'Категория',
        'course': 'Курс',
        'lesson': 'Урок'
    };
    return labels[type] || type;
}

// Восстановить объект
async function restoreObject(deletedId) {
    const confirmed = await customConfirm('Восстановить этот объект?');
    if (!confirmed) return;
    
    try {
        const response = await fetch(`${API_BASE}/bin/${deletedId}/restore`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showSuccess('Объект восстановлен');
            loadDeletedObjects();
        } else {
            showError(data.error || 'Ошибка при восстановлении');
        }
    } catch (error) {
        console.error('Ошибка:', error);
        showError('Не удалось восстановить объект');
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

// Экспорт функций
window.restoreObject = restoreObject;

