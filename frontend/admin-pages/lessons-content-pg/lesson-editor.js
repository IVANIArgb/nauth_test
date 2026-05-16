/**
 * JavaScript для редактора урока (admin only)
 */

const API_BASE = '/api';

let isEditMode = false;
let currentLessonId = null;

// Инициализация редактора урока
function initLessonEditor(lessonId) {
    currentLessonId = lessonId;
    
    // Проверяем URL параметры
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('edit') === 'true') {
        isEditMode = true;
        // Включаем режим редактирования после загрузки блоков
        setTimeout(() => {
            enableEditMode();
        }, 500);
    }
}

// Экспорт функции
window.initLessonEditor = initLessonEditor;

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
                <option value="test">Тест</option>
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
                <textarea id="text-html" rows="10"></textarea>
                <small>Можно использовать HTML разметку</small>
            `;
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
        case 'test':
            editor.innerHTML = `
                <div class="test-editor">
                    <div class="test-editor-tabs">
                        <button type="button" class="test-editor-tab-btn active" data-tab="settings">Настройки теста</button>
                        <button type="button" class="test-editor-tab-btn" data-tab="questions">Вопросы</button>
                    </div>

                    <div class="test-editor-tab-panels">
                        <div class="test-editor-tab-panel active" data-tab="settings">
                            <div class="test-editor-settings">
                                <label class="test-editor-field">
                                    <span>Название теста</span>
                                    <input type="text" id="test-title-input" placeholder="Например: Итоговый тест по уроку" />
                                </label>
                                <label class="test-editor-field">
                                    <span>Минимальный процент для зачёта</span>
                                    <input type="number" id="test-pass-percent" min="1" max="100" value="70" />
                                </label>
                                <label class="test-editor-field test-editor-inline">
                                    <input type="checkbox" id="test-limit-attempts" />
                                    <span>Ограничить количество попыток</span>
                                </label>
                                <label class="test-editor-field">
                                    <span>Максимум попыток</span>
                                    <input type="number" id="test-max-attempts" min="1" step="1" value="3" disabled />
                                </label>
                                <div class="test-editor-dates">
                                    <label class="test-editor-field">
                                        <span>Тест доступен с</span>
                                        <input type="datetime-local" id="test-available-from" />
                                    </label>
                                    <label class="test-editor-field">
                                        <span>Тест доступен до</span>
                                        <input type="datetime-local" id="test-available-until" />
                                    </label>
                                </div>
                                <label class="test-editor-field test-editor-inline">
                                    <input type="checkbox" id="test-time-limit-enabled" />
                                    <span>Ограничить время на прохождение</span>
                                </label>
                                <label class="test-editor-field">
                                    <span>Лимит времени (минуты)</span>
                                    <input type="number" id="test-time-limit-minutes" min="1" step="1" value="15" disabled />
                                </label>
                            </div>
                        </div>

                        <div class="test-editor-tab-panel" data-tab="questions">
                            <div class="test-editor-questions-header">
                                <span>Вопросы теста</span>
                                <button type="button" class="test-editor-add-question-btn" id="test-add-question-btn">
                                    + Создать вопрос
                                </button>
                            </div>
                            <div class="test-editor-questions-body">
                                <div class="test-editor-questions-tabs" id="test-questions-tabs"></div>
                                <div class="test-editor-questions-content" id="test-questions-container">
                                    <p class="test-editor-empty">Пока нет ни одного вопроса. Нажмите «Создать вопрос».</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="test-editor-hint">
                        <p>Поддерживаются три типа ответов:</p>
                        <ul>
                            <li><strong>Один вариант</strong> — радиокнопки (можно выбрать только один правильный ответ).</li>
                            <li><strong>Несколько вариантов</strong> — чекбоксы (можно отметить несколько правильных вариантов).</li>
                            <li><strong>Ввод текста</strong> — поле ввода, пользователь печатает ответ.</li>
                        </ul>
                    </div>
                    <div class="test-editor-error" id="test-editor-error"></div>
                </div>
            `;
            setupTestEditor();
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
            case 'text':
                content = {
                    html: document.getElementById('text-html').value
                };
                break;
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
            case 'test':
                const testData = collectTestEditorData();
                if (!testData) {
                    // Ошибка уже показана пользователю
                    return;
                }
                content = testData;
                break;
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

// ---------------- Тест: UI-конструктор ----------------

function setupTestEditor() {
    const container = document.querySelector('.test-editor');
    if (!container) return;

    const tabs = container.querySelectorAll('.test-editor-tab-btn');
    const panels = container.querySelectorAll('.test-editor-tab-panel');
    const errorBox = container.querySelector('#test-editor-error');
    const limitAttemptsCheckbox = container.querySelector('#test-limit-attempts');
    const maxAttemptsInput = container.querySelector('#test-max-attempts');
    const timeLimitCheckbox = container.querySelector('#test-time-limit-enabled');
    const timeLimitInput = container.querySelector('#test-time-limit-minutes');
    const addQuestionBtn = container.querySelector('#test-add-question-btn');
    const tabsHeader = container.querySelector('#test-questions-tabs');
    const questionsContainer = container.querySelector('#test-questions-container');

    function setError(message) {
        if (!errorBox) return;
        if (!message) {
            errorBox.textContent = '';
            errorBox.style.display = 'none';
        } else {
            errorBox.textContent = message;
            errorBox.style.display = 'block';
        }
    }

    // Переключение вкладок настроек/вопросов
    tabs.forEach((btn) => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            tabs.forEach((b) => b.classList.toggle('active', b === btn));
            panels.forEach((p) => p.classList.toggle('active', p.dataset.tab === tab));
        });
    });

    // Ограничение попыток
    if (limitAttemptsCheckbox && maxAttemptsInput) {
        const updateAttemptsState = () => {
            maxAttemptsInput.disabled = !limitAttemptsCheckbox.checked;
        };
        limitAttemptsCheckbox.addEventListener('change', updateAttemptsState);
        updateAttemptsState();
    }

    // Ограничение времени
    if (timeLimitCheckbox && timeLimitInput) {
        const updateTimeLimitState = () => {
            timeLimitInput.disabled = !timeLimitCheckbox.checked;
        };
        timeLimitCheckbox.addEventListener('change', updateTimeLimitState);
        updateTimeLimitState();
    }

    function createQuestionId() {
        const existing = questionsContainer.querySelectorAll('.test-editor-question');
        return existing.length ? Math.max(...Array.from(existing).map((q) => parseInt(q.dataset.qid || '0', 10))) + 1 : 1;
    }

    function activateQuestionTab(qid) {
        const allTabs = tabsHeader.querySelectorAll('.test-editor-question-tab');
        const allQuestions = questionsContainer.querySelectorAll('.test-editor-question');
        allTabs.forEach((t) => t.classList.toggle('active', t.dataset.qid === String(qid)));
        allQuestions.forEach((q) => q.classList.toggle('active', q.dataset.qid === String(qid)));
    }

    function rebuildQuestionTabs() {
        const questions = questionsContainer.querySelectorAll('.test-editor-question');
        tabsHeader.innerHTML = '';
        questions.forEach((q, index) => {
            const qid = q.dataset.qid;
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'test-editor-question-tab';
            if (index === 0) btn.classList.add('active');
            btn.dataset.qid = qid;
            btn.textContent = `Вопрос ${index + 1}`;
            btn.addEventListener('click', () => activateQuestionTab(qid));
            tabsHeader.appendChild(btn);
        });
        if (questions.length === 0) {
            questionsContainer.innerHTML = '<p class="test-editor-empty">Пока нет ни одного вопроса. Нажмите «Создать вопрос».</p>';
        } else {
            const empties = questionsContainer.querySelectorAll('.test-editor-empty');
            empties.forEach((e) => e.remove());
            activateQuestionTab(questions[0].dataset.qid);
        }
    }

    function addQuestion() {
        setError('');
        const qid = createQuestionId();
        const questionEl = document.createElement('div');
        questionEl.className = 'test-editor-question';
        questionEl.dataset.qid = String(qid);
        questionEl.innerHTML = `
            <div class="test-editor-question-header">
                <label class="test-editor-field">
                    <span>Текст вопроса</span>
                    <textarea class="test-editor-question-text" rows="3" placeholder="Введите формулировку вопроса"></textarea>
                </label>
                <label class="test-editor-field">
                    <span>Тип ответа</span>
                    <select class="test-editor-answer-type">
                        <option value="single">Один вариант (радиокнопки)</option>
                        <option value="multiple">Несколько вариантов (чекбоксы)</option>
                        <option value="input">Ввод текста</option>
                    </select>
                </label>
                <button type="button" class="test-editor-delete-question-btn">Удалить вопрос</button>
            </div>
            <div class="test-editor-question-body" data-answer-type="single">
                <div class="test-editor-options-wrapper">
                    <div class="test-editor-options-list"></div>
                    <button type="button" class="test-editor-add-option-btn">+ Добавить вариант</button>
                </div>
                <div class="test-editor-input-answers" style="display:none;">
                    <label class="test-editor-field">
                        <span>Допустимые ответы (через запятую)</span>
                        <input type="text" class="test-editor-accepted-answers" placeholder="Например: да, согласен, верно" />
                    </label>
                </div>
            </div>
        `;

        questionsContainer.appendChild(questionEl);

        const answerTypeSelect = questionEl.querySelector('.test-editor-answer-type');
        const body = questionEl.querySelector('.test-editor-question-body');
        const optionsWrapper = body.querySelector('.test-editor-options-wrapper');
        const inputAnswersWrapper = body.querySelector('.test-editor-input-answers');
        const addOptionBtn = body.querySelector('.test-editor-add-option-btn');
        const optionsList = body.querySelector('.test-editor-options-list');
        const deleteQuestionBtn = questionEl.querySelector('.test-editor-delete-question-btn');

        function updateAnswerType() {
            const val = (answerTypeSelect.value || 'single').toLowerCase();
            body.dataset.answerType = val;
            if (val === 'input') {
                optionsWrapper.style.display = 'none';
                inputAnswersWrapper.style.display = 'block';
            } else {
                optionsWrapper.style.display = 'block';
                inputAnswersWrapper.style.display = 'none';
            }

            // Если переключились в режим "один вариант", гарантируем только один отмеченный "верный"
            if (val === 'single') {
                const allCorrect = optionsList.querySelectorAll('.test-editor-option-correct');
                let firstCheckedFound = false;
                allCorrect.forEach((cb) => {
                    if (cb.checked) {
                        if (!firstCheckedFound) {
                            firstCheckedFound = true;
                        } else {
                            cb.checked = false;
                        }
                    }
                });
            }
        }

        function addOption() {
            const optionRow = document.createElement('div');
            optionRow.className = 'test-editor-option-row';
            optionRow.innerHTML = `
                <input type="text" class="test-editor-option-text" placeholder="Текст варианта ответа" />
                <label class="test-editor-option-correct-label">
                    <input type="checkbox" class="test-editor-option-correct" />
                    <span>верный</span>
                </label>
                <button type="button" class="test-editor-delete-option-btn">✕</button>
            `;
            const deleteBtn = optionRow.querySelector('.test-editor-delete-option-btn');
            deleteBtn.addEventListener('click', () => {
                optionRow.remove();
            });
            const correctCheckbox = optionRow.querySelector('.test-editor-option-correct');
            // В режиме "один вариант" имитируем поведение radio — только один "верный"
            correctCheckbox.addEventListener('change', () => {
                const currentType = (answerTypeSelect.value || 'single').toLowerCase();
                if (currentType === 'single' && correctCheckbox.checked) {
                    const allCorrect = optionsList.querySelectorAll('.test-editor-option-correct');
                    allCorrect.forEach((cb) => {
                        if (cb !== correctCheckbox) {
                            cb.checked = false;
                        }
                    });
                }
            });
            optionsList.appendChild(optionRow);
        }

        answerTypeSelect.addEventListener('change', updateAnswerType);
        addOptionBtn.addEventListener('click', addOption);
        deleteQuestionBtn.addEventListener('click', () => {
            questionEl.remove();
            rebuildQuestionTabs();
        });

        // Создаём два варианта по умолчанию
        addOption();
        addOption();
        updateAnswerType();

        rebuildQuestionTabs();
    }

    if (addQuestionBtn) {
        addQuestionBtn.addEventListener('click', addQuestion);
    }

    // Создаём первый вопрос по умолчанию для удобства
    if (!questionsContainer.querySelector('.test-editor-question')) {
        addQuestion();
    }
}

function collectTestEditorData() {
    const container = document.querySelector('.test-editor');
    if (!container) {
        showError('Редактор теста не найден');
        return null;
    }
    const errorBox = container.querySelector('#test-editor-error');
    const titleInput = container.querySelector('#test-title-input');
    const passPercentInput = container.querySelector('#test-pass-percent');
    const limitAttemptsCheckbox = container.querySelector('#test-limit-attempts');
    const maxAttemptsInput = container.querySelector('#test-max-attempts');
    const availableFromInput = container.querySelector('#test-available-from');
    const availableUntilInput = container.querySelector('#test-available-until');
    const timeLimitCheckbox = container.querySelector('#test-time-limit-enabled');
    const timeLimitMinutesInput = container.querySelector('#test-time-limit-minutes');
    const questionsEls = container.querySelectorAll('.test-editor-question');

    function setError(message) {
        if (!errorBox) return;
        if (!message) {
            errorBox.textContent = '';
            errorBox.style.display = 'none';
        } else {
            errorBox.textContent = message;
            errorBox.style.display = 'block';
        }
    }

    setError('');

    const title = (titleInput?.value || '').trim() || 'Тест';

    let passPercent = parseInt(passPercentInput?.value || '70', 10);
    if (isNaN(passPercent) || passPercent <= 0 || passPercent > 100) {
        setError('Минимальный процент должен быть числом от 1 до 100');
        return null;
    }

    let maxAttempts = null;
    const limitAttempts = !!limitAttemptsCheckbox?.checked;
    if (limitAttempts) {
        const raw = maxAttemptsInput?.value || '';
        const val = parseInt(raw, 10);
        if (isNaN(val) || val <= 0) {
            setError('Максимальное количество попыток должно быть положительным числом');
            return null;
        }
        maxAttempts = val;
    }

    const availableFrom = availableFromInput?.value || null;
    const availableUntil = availableUntilInput?.value || null;

    if (availableFrom && availableUntil && availableFrom > availableUntil) {
        setError('Дата начала не может быть позже даты окончания');
        return null;
    }

    let timeLimitMinutes = null;
    const timeLimitEnabled = !!timeLimitCheckbox?.checked;
    if (timeLimitEnabled) {
        const raw = timeLimitMinutesInput?.value || '';
        const val = parseInt(raw, 10);
        if (isNaN(val) || val <= 0) {
            setError('Лимит времени должен быть положительным числом минут');
            return null;
        }
        timeLimitMinutes = val;
    }

    if (!questionsEls.length) {
        setError('Добавьте хотя бы один вопрос');
        return null;
    }

    const questions = [];
    for (const qEl of questionsEls) {
        const textArea = qEl.querySelector('.test-editor-question-text');
        const answerTypeSelect = qEl.querySelector('.test-editor-answer-type');
        const optionsList = qEl.querySelectorAll('.test-editor-option-row');
        const acceptedAnswersInput = qEl.querySelector('.test-editor-accepted-answers');

        const qText = (textArea?.value || '').trim();
        if (!qText) {
            setError('У каждого вопроса должен быть текст');
            return null;
        }

        const answerType = (answerTypeSelect?.value || 'single').toLowerCase();
        if (answerType === 'input') {
            const raw = (acceptedAnswersInput?.value || '').trim();
            const accepted = raw
                ? raw.split(',').map((s) => s.trim()).filter((s) => s.length > 0)
                : [];
            if (!accepted.length) {
                setError('Для вопросов с вводом текста укажите хотя бы один допустимый ответ');
                return null;
            }
            questions.push({
                text: qText,
                answer_type: 'input',
                accepted_answers: accepted,
            });
        } else {
            const multiple = answerType === 'multiple';
            const options = [];
            const correctIndexes = [];
            optionsList.forEach((row, index) => {
                const optTextInput = row.querySelector('.test-editor-option-text');
                const correctCheckbox = row.querySelector('.test-editor-option-correct');
                const optText = (optTextInput?.value || '').trim();
                if (!optText) {
                    return;
                }
                options.push(optText);
                if (correctCheckbox && correctCheckbox.checked) {
                    correctIndexes.push(options.length - 1);
                }
            });

            if (!options.length) {
                setError('У каждого вопроса с вариантами должен быть хотя бы один вариант ответа');
                return null;
            }

            if (!correctIndexes.length) {
                setError('Отметьте хотя бы один правильный вариант для каждого вопроса с вариантами');
                return null;
            }

            if (!multiple && correctIndexes.length !== 1) {
                setError('Для вопросов с одним вариантом ответа можно выбрать только один правильный вариант');
                return null;
            }

            questions.push({
                text: qText,
                options,
                multiple,
                correct_answer: multiple ? correctIndexes : correctIndexes[0],
            });
        }
    }

    if (!questions.length) {
        setError('Добавьте хотя бы один корректно заполненный вопрос');
        return null;
    }

    const settings = {
        pass_percent: passPercent,
        limit_attempts: limitAttempts,
        max_attempts: maxAttempts,
        available_from: availableFrom || null,
        available_until: availableUntil || null,
        time_limit_enabled: timeLimitEnabled,
        time_limit_minutes: timeLimitMinutes,
    };

    return {
        title,
        settings,
        questions,
    };
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

