/**
 * JavaScript для редактора урока (admin only)
 */

const API_BASE = '/api';

let isEditMode = false;
let currentLessonId = null;

// Переключение режима редактирования
function toggleEditMode() {
    isEditMode = !isEditMode;
    
    if (isEditMode) {
        enableEditMode();
    } else {
        disableEditMode();
    }
}

// Включить режим редактирования
function enableEditMode() {
    const blocksContainer = document.querySelector('.lesson-blocks');
    if (!blocksContainer) return;
    
    // Добавляем кнопки редактирования к каждому блоку
    const blocks = blocksContainer.querySelectorAll('.content-block');
    blocks.forEach(block => {
        addBlockControls(block);
    });
    
    // Добавляем кнопку добавления блока
    addAddBlockButton(blocksContainer);
    
    // Обновляем кнопку редактирования
    const editBtn = document.querySelector('.btn-edit-lesson');
    if (editBtn) {
        editBtn.textContent = 'Завершить редактирование';
        editBtn.onclick = () => toggleEditMode();
    }
}

// Отключить режим редактирования
function disableEditMode() {
    // Удаляем все элементы управления
    const blockControls = document.querySelectorAll('.block-controls');
    blockControls.forEach(control => control.remove());
    
    const addBlockBtn = document.querySelector('.add-block-button');
    if (addBlockBtn) addBlockBtn.remove();
    
    const dragDropZone = document.querySelector('.drag-drop-zone');
    if (dragDropZone) dragDropZone.remove();
    
    // Обновляем кнопку редактирования
    const editBtn = document.querySelector('.btn-edit-lesson');
    if (editBtn) {
        editBtn.textContent = 'Редактировать урок';
        editBtn.onclick = () => toggleEditMode();
    }
}

// Добавить элементы управления к блоку
function addBlockControls(block) {
    // Проверяем, не добавлены ли уже элементы управления
    if (block.querySelector('.block-controls')) return;
    
    const controls = document.createElement('div');
    controls.className = 'block-controls';
    controls.innerHTML = `
        <button class="btn-edit-block" onclick="editBlock(${block.dataset.blockId})">✏️</button>
        <button class="btn-delete-block" onclick="deleteBlock(${block.dataset.blockId})">🗑️</button>
        <button class="btn-move-up" onclick="moveBlockUp(${block.dataset.blockId})">↑</button>
        <button class="btn-move-down" onclick="moveBlockDown(${block.dataset.blockId})">↓</button>
    `;
    block.appendChild(controls);
}

// Добавить кнопку добавления блока
function addAddBlockButton(container) {
    if (document.querySelector('.add-block-button')) return;
    
    const addBtn = document.createElement('button');
    addBtn.className = 'add-block-button';
    addBtn.textContent = '+ Добавить блок';
    addBtn.onclick = () => showAddBlockModal();
    container.appendChild(addBtn);
    
    // Добавляем зону для drag-and-drop
    addDragDropZone(container);
}

// Добавить зону для drag-and-drop загрузки файлов
function addDragDropZone(container) {
    if (document.querySelector('.drag-drop-zone')) return;
    
    const dropZone = document.createElement('div');
    dropZone.className = 'drag-drop-zone';
    dropZone.innerHTML = `
        <div class="drag-drop-content">
            <p class="drag-drop-text">Перетащите файлы сюда или нажмите для выбора</p>
            <input type="file" id="drag-drop-input" multiple style="display: none;" />
        </div>
    `;
    
    const fileInput = dropZone.querySelector('#drag-drop-input');
    
    // Обработчики событий drag-and-drop
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });
    
    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('drag-over');
    });
    
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        
        const files = Array.from(e.dataTransfer.files);
        handleDroppedFiles(files);
    });
    
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });
    
    fileInput.addEventListener('change', (e) => {
        const files = Array.from(e.target.files);
        handleDroppedFiles(files);
    });
    
    container.appendChild(dropZone);
}

// Обработка перетащенных файлов
async function handleDroppedFiles(files) {
    if (!currentLessonId) {
        showError('ID урока не определен');
        return;
    }
    
    if (files.length === 0) return;
    
    // Определяем тип файла и создаем соответствующий блок
    for (const file of files) {
        const fileType = file.type.split('/')[0]; // 'image', 'video', etc.
        const blockType = fileType === 'image' ? 'image' : 
                         fileType === 'video' ? 'video' : 'file';
        
        try {
            await uploadFileAndCreateBlock(file, blockType);
        } catch (error) {
            console.error('Ошибка загрузки файла:', error);
            showError(`Не удалось загрузить файл: ${file.name}`);
        }
    }
    
    // Перезагружаем урок после загрузки всех файлов
    setTimeout(() => {
        location.reload();
    }, 1000);
}

// Показать модальное окно добавления блока
function showAddBlockModal() {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.id = 'add-block-modal';
    modal.innerHTML = `
        <div class="modal-content">
            <span class="close" onclick="closeAddBlockModal()">&times;</span>
            <h2>Добавить блок контента</h2>
            <select id="block-type-select">
                <option value="heading">Заголовок</option>
                <option value="text">Текст</option>
                <option value="video">Видео</option>
                <option value="file">Файл</option>
                <option value="image">Изображение</option>
            </select>
            <div id="block-editor"></div>
            <div class="form-actions">
                <button onclick="closeAddBlockModal()">Отмена</button>
                <button onclick="saveNewBlock()">Добавить</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    
    // Обработчик изменения типа блока
    const typeSelect = document.getElementById('block-type-select');
    typeSelect.addEventListener('change', () => {
        renderBlockEditor(typeSelect.value);
    });
    
    renderBlockEditor(typeSelect.value);
}

// Отобразить редактор блока в зависимости от типа
function renderBlockEditor(blockType) {
    const editor = document.getElementById('block-editor');
    if (!editor) return;
    
    switch (blockType) {
        case 'heading':
            editor.innerHTML = `
                <label>Уровень заголовка (1-6):</label>
                <input type="number" id="heading-level" min="1" max="6" value="2" />
                <label>Текст:</label>
                <input type="text" id="heading-text" />
            `;
            break;
        case 'text':
            editor.innerHTML = `
                <label>Текст (HTML):</label>
                <textarea id="text-html" rows="8"></textarea>
                <small>Можно использовать HTML разметку</small>
                <div class="text-format-options">
                    <fieldset>
                        <legend>Размер</legend>
                        <select id="text-size">
                            <option value="xs">Очень маленький</option>
                            <option value="sm">Маленький</option>
                            <option value="md" selected>Средний</option>
                            <option value="lg">Большой</option>
                            <option value="xl">Очень большой</option>
                        </select>
                    </fieldset>
                    <fieldset>
                        <legend>Выделение</legend>
                        <label><input type="checkbox" id="text-bold" /> Жирный</label>
                <label><input type="checkbox" id="text-italic" /> Курсив</label>
                <label>Цвет: <input type="color" id="text-color" value="#4f4f4f" title="Выбрать цвет" /></label>
                <label><input type="checkbox" id="text-as-link" /> Как ссылка</label>
                <input type="text" id="text-link-url" placeholder="URL ссылки (можно /страницу или полный адрес)" style="display:none; width:100%; margin-top:4px;" />
                    </fieldset>
                    <fieldset>
                        <legend>Позиционирование</legend>
                        <label><input type="radio" name="text-align" value="left" checked /> Слева</label>
                        <label><input type="radio" name="text-align" value="center" /> По центру</label>
                        <label><input type="radio" name="text-align" value="right" /> Справа</label>
                    </fieldset>
                </div>
            `;
            document.getElementById('text-as-link').addEventListener('change', function() {
                document.getElementById('text-link-url').style.display = this.checked ? 'block' : 'none';
            });
            break;
        case 'video':
            editor.innerHTML = `
                <label>URL iframe:</label>
                <input type="url" id="video-url" placeholder="https://rutube.ru/play/embed/..." />
                <label>Ширина:</label>
                <input type="number" id="video-width" value="900" />
                <label>Высота:</label>
                <input type="number" id="video-height" value="500" />
                <label>Название (опционально):</label>
                <input type="text" id="video-title" />
            `;
            break;
        case 'file':
            editor.innerHTML = `
                <label>Загрузить файл:</label>
                <input type="file" id="file-upload" />
                <small>Файл будет загружен и добавлен в урок</small>
            `;
            break;
        case 'image':
            editor.innerHTML = `
                <label>Загрузить изображение:</label>
                <input type="file" id="image-upload" accept="image/*" />
                <label>Описание (alt):</label>
                <input type="text" id="image-alt" />
            `;
            break;
    }
}

// Сохранить новый блок
async function saveNewBlock() {
    if (!currentLessonId) {
        showError('ID урока не определен');
        return;
    }
    
    const typeSelect = document.getElementById('block-type-select');
    const blockType = typeSelect.value;
    let content = {};
    
    try {
        switch (blockType) {
            case 'heading':
                content = {
                    level: parseInt(document.getElementById('heading-level').value, 10),
                    text: document.getElementById('heading-text').value
                };
                break;
            case 'text': {
                const textAlignEl = document.querySelector('input[name="text-align"]:checked');
                let linkUrl = '';
                if (document.getElementById('text-as-link').checked) {
                    const raw = (document.getElementById('text-link-url').value || '').trim();
                    if (raw) {
                        if (/^https?:\/\//i.test(raw) || raw.startsWith('/')) {
                            linkUrl = raw;
                        } else {
                            try {
                                const loc = window.location;
                                if (raw.toLowerCase().startsWith(loc.host.toLowerCase())) {
                                    linkUrl = `${loc.protocol}//${raw}`;
                                } else {
                                    linkUrl = '/' + raw.replace(/^\/+/, '');
                                }
                            } catch (e) {
                                linkUrl = raw;
                            }
                        }
                    }
                }
                const textAlignEl2 = textAlignEl;
                content = {
                    html: document.getElementById('text-html').value,
                    size: document.getElementById('text-size').value || 'md',
                    bold: document.getElementById('text-bold').checked,
                    italic: document.getElementById('text-italic').checked,
                    color: document.getElementById('text-color').value || '',
                    linkUrl,
                    align: textAlignEl2 ? textAlignEl2.value : 'left'
                };
                break;
            }
            case 'video':
                content = {
                    url: document.getElementById('video-url').value,
                    width: parseInt(document.getElementById('video-width').value, 10),
                    height: parseInt(document.getElementById('video-height').value, 10),
                    title: document.getElementById('video-title').value
                };
                break;
            case 'file':
            case 'image':
                // Для файлов и изображений нужно сначала загрузить файл
                const fileInput = document.getElementById(blockType === 'file' ? 'file-upload' : 'image-upload');
                if (!fileInput.files || fileInput.files.length === 0) {
                    showError('Выберите файл');
                    return;
                }
                await uploadFileAndCreateBlock(fileInput.files[0], blockType);
                closeAddBlockModal();
                return;
        }
        
        // Создаем блок через API
        const response = await fetch(`${API_BASE}/lessons/${currentLessonId}/blocks`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                block_type: blockType,
                content: content
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showSuccess('Блок добавлен');
            closeAddBlockModal();
            // Перезагружаем урок
            location.reload();
        } else {
            showError(data.error || 'Ошибка при добавлении блока');
        }
    } catch (error) {
        console.error('Ошибка:', error);
        showError('Не удалось добавить блок');
    }
}

// Загрузить файл и создать блок
async function uploadFileAndCreateBlock(file, blockType) {
    const formData = new FormData();
    formData.append('file', file);
    
    // Определяем тип папки для загрузки
    let folderType = 'files';
    if (blockType === 'image') {
        folderType = 'images';
    } else if (blockType === 'video') {
        folderType = 'videos';
    }
    
    formData.append('type', folderType);
    
    try {
        // Показываем индикатор загрузки
        showUploadProgress(file.name);
        
        // Сначала загружаем файл
        const uploadResponse = await fetch(`${API_BASE}/lessons/${currentLessonId}/files`, {
            method: 'POST',
            body: formData
        });
        
        const uploadData = await uploadResponse.json();
        
        if (!uploadResponse.ok) {
            throw new Error(uploadData.error || 'Ошибка загрузки файла');
        }
        
        // Затем создаем блок
        const content = blockType === 'file' ? {
            filename: uploadData.filename || file.name,
            url: uploadData.url,
            size: uploadData.size || file.size,
            type: uploadData.type || file.type
        } : blockType === 'video' ? {
            url: uploadData.url,
            width: 900,
            height: 500,
            title: file.name
        } : {
            url: uploadData.url,
            alt: file.name
        };
        
        const blockResponse = await fetch(`${API_BASE}/lessons/${currentLessonId}/blocks`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                block_type: blockType,
                content: content
            })
        });
        
        const blockData = await blockResponse.json();
        
        if (blockResponse.ok) {
            hideUploadProgress(file.name);
            return blockData;
        } else {
            throw new Error(blockData.error || 'Ошибка при создании блока');
        }
    } catch (error) {
        console.error('Ошибка:', error);
        hideUploadProgress(file.name);
        throw error;
    }
}

// Показать индикатор загрузки
function showUploadProgress(filename) {
    let progressContainer = document.querySelector('.upload-progress-container');
    if (!progressContainer) {
        progressContainer = document.createElement('div');
        progressContainer.className = 'upload-progress-container';
        document.body.appendChild(progressContainer);
    }
    
    const progressItem = document.createElement('div');
    progressItem.className = 'upload-progress-item';
    progressItem.dataset.filename = filename;
    progressItem.innerHTML = `
        <span class="upload-filename">${escapeHtml(filename)}</span>
        <span class="upload-status">Загрузка...</span>
    `;
    progressContainer.appendChild(progressItem);
}

// Скрыть индикатор загрузки
function hideUploadProgress(filename) {
    const progressItem = document.querySelector(`.upload-progress-item[data-filename="${filename}"]`);
    if (progressItem) {
        progressItem.querySelector('.upload-status').textContent = 'Загружено';
        setTimeout(() => {
            progressItem.remove();
        }, 2000);
    }
}

// Утилита для экранирования HTML
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Редактировать блок
function editBlock(blockId) {
    // TODO: Реализовать редактирование блока
    customAlert('Редактирование блока будет реализовано в следующей версии', 'Информация');
}

// Удалить блок
async function deleteBlock(blockId) {
    if (!currentLessonId) return;
    
    const confirmed = await customConfirm('Удалить этот блок?');
    if (!confirmed) return;
    
    try {
        const response = await fetch(`${API_BASE}/lessons/${currentLessonId}/blocks/${blockId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showSuccess('Блок удален');
            location.reload();
        } else {
            showError(data.error || 'Ошибка при удалении блока');
        }
    } catch (error) {
        console.error('Ошибка:', error);
        showError('Не удалось удалить блок');
    }
}

// Переместить блок вверх/вниз
async function moveBlockUp(blockId) {
    // TODO: Реализовать изменение порядка блоков
    customAlert('Изменение порядка блоков будет реализовано в следующей версии', 'Информация');
}

async function moveBlockDown(blockId) {
    // TODO: Реализовать изменение порядка блоков
    customAlert('Изменение порядка блоков будет реализовано в следующей версии', 'Информация');
}

// Закрыть модальное окно
function closeAddBlockModal() {
    const modal = document.getElementById('add-block-modal');
    if (modal) {
        modal.remove();
    }
}

// Утилиты
function showError(message) {
    customAlert(message, 'Ошибка');
}

function showSuccess(message) {
    customAlert(message, 'Успешно');
}

// Инициализация
document.addEventListener('DOMContentLoaded', () => {
    const urlParams = new URLSearchParams(window.location.search);
    currentLessonId = urlParams.get('lesson_id');
    
    // Проверяем режим редактирования из URL
    const editMode = urlParams.get('edit') === 'true';
    if (editMode && currentLessonId) {
        // Автоматически включаем режим редактирования
        setTimeout(() => {
            toggleEditMode();
        }, 500);
    }
    
    // Экспорт функций
    window.toggleEditMode = toggleEditMode;
    window.editBlock = editBlock;
    window.deleteBlock = deleteBlock;
    window.moveBlockUp = moveBlockUp;
    window.moveBlockDown = moveBlockDown;
    window.showAddBlockModal = showAddBlockModal;
    window.closeAddBlockModal = closeAddBlockModal;
    window.saveNewBlock = saveNewBlock;
});

