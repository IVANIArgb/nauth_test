/**
 * JavaScript для страницы просмотра урока
 */

const API_BASE = '/api';

// Глобальные переменные
let currentLesson = null;
let currentUserRole = 'user';
let isEditMode = false;
let scrollTrackingEnabled = false;
let videoTrackingEnabled = false;
let lessonCompleted = false;
let scrollProgress = 0;
let videosWatched = new Set();

// DOM элементы
let lessonContentContainer = null;
let breadcrumbsContainer = null;
let navigationContainer = null;
let lessonBlocksContainer = null;

// Статусы тестов текущего урока (для блокировки завершения)
let lessonTestsGate = { has_tests: false, all_passed: true, tests: [] };

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    lessonContentContainer = document.querySelector('.lesson-content') || document.querySelector('.main-content');
    breadcrumbsContainer = document.querySelector('.breadcrumbs');
    navigationContainer = document.querySelector('.lesson-navigation');
    
    // Если контейнер не найден, создаем его или ищем альтернативный
    if (!lessonContentContainer) {
        console.error('Контейнер контента не найден. Ищем альтернативный...');
        // Пытаемся найти main или body
        const main = document.querySelector('main') || document.querySelector('.main-content') || document.body;
        if (main) {
            lessonContentContainer = document.createElement('div');
            lessonContentContainer.className = 'lesson-content';
            main.appendChild(lessonContentContainer);
        } else {
            console.error('Не удалось найти или создать контейнер контента');
            document.body.innerHTML = '<div style="padding: 2rem; text-align: center;"><h1>Ошибка загрузки страницы</h1><p>Не удалось найти контейнер для контента</p></div>';
            return;
        }
    }
    
    // Получаем lesson_id из URL
    const urlParams = new URLSearchParams(window.location.search);
    const lessonId = urlParams.get('lesson_id');
    
    if (lessonId) {
        checkUserRole();
        loadLesson(parseInt(lessonId));
    } else {
        showError('ID урока не указан');
    }
    
    setupEventListeners();
});

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
        showError('Не удалось проверить роль пользователя');
    }
}

// Загрузка урока
async function loadLesson(lessonId) {
    try {
        const response = await fetch(`${API_BASE}/lessons/${lessonId}`);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        
        currentLesson = data;
        renderLesson(data);
        loadBreadcrumbs(lessonId);
        loadNavigation(lessonId);
    } catch (error) {
        console.error('Ошибка загрузки урока:', error);
        showError('Не удалось загрузить урок');
    }
}

// Отображение урока
function renderLesson(lesson) {
    if (!lessonContentContainer) {
        console.error('Контейнер контента не найден');
        return;
    }
    
    // Обновляем заголовок страницы
    const pageTitle = document.querySelector('.page-title');
    if (pageTitle) {
        pageTitle.textContent = lesson.title;
    }
    
    // Проверяем доступность
    if (!lesson.is_accessible && lesson.locked_reason) {
        lessonContentContainer.innerHTML = `
            <div class="lesson-locked">
                <h2>Урок недоступен</h2>
                <p>${escapeHtml(lesson.locked_reason)}</p>
                ${lesson.required_lesson_id ? 
                    `<button onclick="openLesson(${lesson.required_lesson_id})">Перейти к необходимому уроку</button>` : 
                    ''}
            </div>
        `;
        return;
    }
    
    // Очищаем контейнер перед загрузкой блоков
    if (lessonContentContainer) {
        lessonContentContainer.innerHTML = '<div class="loading-message" style="padding: 2rem; text-align: center;">Загрузка контента...</div>';
    }
    
    // Загружаем блоки контента
    loadLessonBlocks(lesson.id);
    
    // Добавляем кнопки действий
    addActionButtons(lesson);
}

// Загрузка блоков контента
async function loadLessonBlocks(lessonId) {
    if (!lessonContentContainer) {
        console.error('Контейнер контента не найден при загрузке блоков');
        showError('Контейнер контента не найден');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/lessons/${lessonId}/blocks`);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        renderContentBlocks(data.blocks || []);
    } catch (error) {
        console.error('Ошибка загрузки блоков:', error);
        if (lessonContentContainer) {
            lessonContentContainer.innerHTML = `
                <div style="padding: 2rem; text-align: center; background: #ffebee; border: 2px solid #d32f2f; border-radius: 8px; color: #d32f2f; margin: 1rem;">
                    <h3>⚠️ Ошибка загрузки контента</h3>
                    <p>${escapeHtml(error.message || 'Не удалось загрузить блоки урока')}</p>
                    <button onclick="location.reload()" style="margin-top: 1rem; padding: 0.5rem 1rem; background: #d32f2f; color: white; border: none; border-radius: 4px; cursor: pointer;">Обновить страницу</button>
                </div>
            `;
        }
        showError('Не удалось загрузить блоки урока: ' + error.message);
    }
}

async function loadLessonTestsStatus() {
    if (!currentLesson?.id) return { has_tests: false, all_passed: true, tests: [] };
    try {
        const resp = await fetch(`${API_BASE}/lessons/${currentLesson.id}/tests/status`);
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) throw new Error(data.error || 'Не удалось получить статус тестов');
        return data;
    } catch (e) {
        console.error('Ошибка загрузки статуса тестов:', e);
        return { has_tests: false, all_passed: true, tests: [] };
    }
}

function updateCompletionGateUI() {
    const completeBtn = document.querySelector('.btn-complete-lesson');
    const actionsContainer = document.querySelector('.lesson-actions');
    if (!actionsContainer) return;

    let hint = actionsContainer.querySelector('.lesson-test-gate-hint');
    if (!hint) {
        hint = document.createElement('div');
        hint.className = 'lesson-test-gate-hint';
        hint.style.cssText = 'width:100%;max-width:900px;margin:0.25rem auto 0;padding:0.75rem 1rem;border-radius:10px;background:rgba(255,152,0,0.12);border:1px solid rgba(255,152,0,0.35);color:#7a4b00;font-size:0.95rem;display:none;';
        actionsContainer.appendChild(hint);
    }

    if (lessonTestsGate?.has_tests && !lessonTestsGate?.all_passed) {
        const anyExhausted = (lessonTestsGate.tests || []).some(t => t && t.attempts_exhausted);
        const attemptsLine = (lessonTestsGate.tests || [])
            .filter(t => t && typeof t.block_id === 'number')
            .map((t) => {
                if (typeof t.max_attempts === 'number') {
                    return `тест #${t.block_id}: ${t.attempts_used || 0}/${t.max_attempts}, осталось ${typeof t.attempts_left === 'number' ? t.attempts_left : '—'}`;
                }
                return `тест #${t.block_id}: попытки без лимита`;
            })
            .join(' · ');

        hint.textContent = anyExhausted
            ? `Урок нельзя завершить: тест не пройден и попытки исчерпаны. ${attemptsLine || ''}`.trim()
            : `Чтобы завершить урок, нужно пройти тест. ${attemptsLine || ''}`.trim();
        hint.style.display = 'block';
        if (completeBtn) {
            completeBtn.disabled = true;
            completeBtn.title = 'Сначала пройдите тест';
        }
    } else {
        hint.style.display = 'none';
        if (completeBtn) {
            completeBtn.disabled = false;
            completeBtn.title = '';
        }
    }
}

// Отображение блоков контента
function renderContentBlocks(blocks) {
    if (!lessonContentContainer) {
        console.error('Контейнер контента не найден при рендеринге блоков');
        showError('Контейнер контента не найден');
        return;
    }
    
    // Находим контейнер для блоков или создаем его
    lessonBlocksContainer = document.querySelector('.lesson-blocks');
    if (!lessonBlocksContainer) {
        lessonBlocksContainer = document.createElement('div');
        lessonBlocksContainer.className = 'lesson-blocks';
        lessonContentContainer.innerHTML = ''; // Очищаем контейнер перед добавлением
        lessonContentContainer.appendChild(lessonBlocksContainer);
    }
    
    lessonBlocksContainer.innerHTML = '';
    
    if (!blocks || blocks.length === 0) {
        console.warn('Блоки пусты или отсутствуют');
        lessonBlocksContainer.innerHTML = '<p class="empty-message" style="padding: 2rem; text-align: center; color: #666;">Контент урока пуст</p>';
        return;
    }
    
    try {
        let renderedCount = 0;
        blocks.forEach((block, index) => {
            if (block) {
                const blockElement = renderContentBlock(block, index);
                if (blockElement) {
                    lessonBlocksContainer.appendChild(blockElement);
                    renderedCount++;
                } else {
                    console.warn(`Не удалось создать элемент для блока ${index}`);
                }
            }
        });
        
        // Запускаем отслеживание прокрутки после рендеринга
        setTimeout(() => {
            startScrollTracking();
        }, 500);

        // После рендера — подгружаем статусы тестов и обновляем блокировку завершения
        const hasTests = Array.isArray(blocks) && blocks.some((b) => b && b.block_type === 'test');
        if (hasTests) {
            loadLessonTestsStatus().then((gate) => {
                lessonTestsGate = gate && typeof gate === 'object' ? gate : { has_tests: false, all_passed: true, tests: [] };
                updateCompletionGateUI();
            });
        } else {
            lessonTestsGate = { has_tests: false, all_passed: true, tests: [] };
            updateCompletionGateUI();
        }
    } catch (error) {
        console.error('Ошибка рендеринга блоков:', error);
        console.error('Stack trace:', error.stack);
        lessonBlocksContainer.innerHTML = `<p style="padding: 2rem; text-align: center; color: #d32f2f;">Ошибка отображения контента: ${escapeHtml(error.message)}</p>`;
    }
}

// Отображение одного блока контента
function renderContentBlock(block, index) {
    const wrapper = document.createElement('div');
    wrapper.className = `content-block content-block-${block.block_type}`;
    wrapper.dataset.blockId = block.id;
    wrapper.dataset.blockIndex = index;
    
    const content = block.content || {};
    
    switch (block.block_type) {
        case 'heading':
            const heading = document.createElement(`h${content.level || 2}`);
            heading.textContent = content.text || '';
            wrapper.appendChild(heading);
            break;
            
        case 'text':
            const textDiv = document.createElement('div');
            textDiv.className = 'text-block';
            // Классы размера и выравнивания
            const size = content.size || 'md';
            const align = content.align || 'left';
            textDiv.classList.add('text-size-' + size, 'text-align-' + align);
            // Стили выделения (жирный, курсив, цвет)
            const styles = [];
            if (content.bold) styles.push('font-weight: bold');
            if (content.italic) styles.push('font-style: italic');
            if (content.color) styles.push('color: ' + content.color);
            if (styles.length) textDiv.style.cssText = styles.join('; ');
            // Поддерживаем как content.text, так и content.html
            let textContent = content.html || content.text || '';
            if (textContent) {
                const rawUrl = (content.linkUrl || '').trim();
                const isSafeLink = rawUrl && (rawUrl.startsWith('http://') || rawUrl.startsWith('https://') || rawUrl.startsWith('/'));
                if (textContent.includes('<') && textContent.includes('>')) {
                    let html = textContent;
                    if (typeof DOMPurify !== 'undefined') {
                        html = DOMPurify.sanitize(html, { ADD_ATTR: ['target'] });
                    } else {
                        html = sanitizeHtml(html);
                    }
                    if (isSafeLink && html) {
                        const a = document.createElement('a');
                        a.href = rawUrl;
                        a.target = '_blank';
                        a.rel = 'noopener';
                        a.innerHTML = html;
                        textDiv.appendChild(a);
                    } else {
                        textDiv.innerHTML = html;
                    }
                } else {
                    const paragraphs = textContent.split('\n').filter(p => p.trim());
                    paragraphs.forEach(para => {
                        const p = document.createElement('p');
                        if (isSafeLink) {
                            const a = document.createElement('a');
                            a.href = rawUrl;
                            a.target = '_blank';
                            a.rel = 'noopener';
                            a.textContent = para.trim();
                            p.appendChild(a);
                        } else {
                            p.textContent = para.trim();
                        }
                        textDiv.appendChild(p);
                    });
                }
            }
            wrapper.appendChild(textDiv);
            break;
            
        case 'video':
            const videoWrapper = document.createElement('div');
            videoWrapper.className = 'video-wrapper';
            videoWrapper.dataset.videoId = `video-${block.id}`;
            
            // Определяем, является ли URL iframe (YouTube/Rutube) или локальным файлом
            let videoUrl = content.url || '';
            const videoFilename = content.stored_filename || content.filename || '';
            
            // Формируем URL для локального файла
            if (videoUrl && (videoUrl.startsWith('http') || videoUrl.startsWith('/categories-data/'))) {
                // Уже корректный URL
            } else if (currentLesson && currentLesson.path_identifier && videoFilename) {
                const fn = (videoUrl && !videoUrl.startsWith('http') && videoUrl.includes('/')) ? videoUrl.split('/').pop() : videoFilename;
                videoUrl = `/categories-data/${currentLesson.path_identifier}/videos/${fn}`;
            }
            
            const isHttpUrl = videoUrl && (videoUrl.startsWith('http://') || videoUrl.startsWith('https://'));
            const isDirectVideoFile = isHttpUrl && /\.(mp4|webm|ogg|ogv|mov|m4v|avi|mkv|flv)(\?|$)/i.test(videoUrl);
            const isEmbedSite = isHttpUrl && /(youtube\.com|youtu\.be|rutube\.ru|vimeo\.com|vk\.com\/video|kinescope\.io|dzen\.ru\/video)/i.test(videoUrl);
            
            // Явные сервисы-страницы — через iframe
            if (isHttpUrl && !isDirectVideoFile && isEmbedSite) {
            const iframe = document.createElement('iframe');
                iframe.src = videoUrl;
                iframe.width = '100%';
                iframe.height = '100%';
            iframe.frameBorder = '0';
            iframe.allowFullscreen = true;
                iframe.setAttribute('allow', 'fullscreen; autoplay; picture-in-picture');
                iframe.dataset.videoUrl = videoUrl;
            
            // Отслеживание просмотра видео через postMessage API (для Rutube/YouTube)
            setupVideoTracking(iframe, block.id);
            
            videoWrapper.appendChild(iframe);
            } else if (videoUrl) {
                // Локальный файл - используем video тег
                const video = document.createElement('video');
                videoWrapper.classList.add('video-file');
                video.src = videoUrl;
                video.controls = true;
                video.setAttribute('controlsList', 'nodownload');
                video.setAttribute('preload', 'metadata');
                
                // Обработка ошибок загрузки
                video.addEventListener('error', () => {
                    console.error('Ошибка загрузки видео:', videoUrl);
                    if (isHttpUrl && !isDirectVideoFile) {
                        // Фолбэк: если это не файл, пробуем iframe
                        videoWrapper.innerHTML = '';
                        const iframe = document.createElement('iframe');
                        iframe.src = videoUrl;
                        iframe.width = '100%';
                        iframe.height = '100%';
                        iframe.frameBorder = '0';
                        iframe.allowFullscreen = true;
                        iframe.setAttribute('allow', 'fullscreen; autoplay; picture-in-picture');
                        iframe.dataset.videoUrl = videoUrl;
                        setupVideoTracking(iframe, block.id);
                        videoWrapper.appendChild(iframe);
                        return;
                    }
                    videoWrapper.innerHTML = `
                        <div style="display: flex; align-items: center; justify-content: center; height: 100%; background: #f5f5f5; color: #666; flex-direction: column; gap: 1rem;">
                            <span style="font-size: 3rem;">🎥</span>
                            <span>Не удалось загрузить видео</span>
                            <a href="${videoUrl}" style="text-decoration: underline;">Скачать видео</a>
                        </div>
                    `;
                });
                
                videoWrapper.appendChild(video);
            }
            
            const videoInfo = document.createElement('div');
            if (content.title) {
                const videoTitle = document.createElement('p');
                videoTitle.className = 'video-title';
                videoTitle.textContent = content.title;
                videoInfo.appendChild(videoTitle);
            }
            
            // Прикрепленные файлы к видео
            if (content.attachments && Array.isArray(content.attachments) && content.attachments.length > 0) {
                const attachmentsDiv = document.createElement('div');
                attachmentsDiv.className = 'video-attachments';
                
                const attachmentsTitle = document.createElement('h4');
                attachmentsTitle.textContent = 'Прикрепленные файлы:';
                attachmentsDiv.appendChild(attachmentsTitle);
                
                content.attachments.forEach((attachment, index) => {
                    const attachmentCard = document.createElement('div');
                    attachmentCard.className = 'file-card';
                    attachmentCard.style.marginTop = '0.5rem';
                    
                    const fileIcon = getFileIcon(attachment.type || '');
                    let attachmentUrl = attachment.url || '';
                    const attachmentName = attachment.name || attachment.filename || 'Файл';
                    const attachmentStored = attachment.stored_filename || attachment.filename;
                    const attachmentType = attachment.type || 'files';
                    let folderType = 'files';
                    if (attachmentType.includes('image')) folderType = 'images';
                    else if (attachmentType.includes('video')) folderType = 'videos';
                    
                    if (attachmentUrl && (attachmentUrl.startsWith('http') || attachmentUrl.startsWith('/categories-data/'))) {
                        // Уже корректный URL
                    } else if (currentLesson && currentLesson.path_identifier && attachmentStored) {
                        const fn = (attachmentUrl && attachmentUrl.includes('/')) ? attachmentUrl.split('/').pop() : attachmentStored;
                        attachmentUrl = `/categories-data/${currentLesson.path_identifier}/${folderType}/${fn}`;
                    }
                    attachmentCard.innerHTML = `
                        <div class="file-icon">${fileIcon}</div>
                        <div class="file-info">
                            <div class="file-name">${escapeHtml(attachmentName)}</div>
                            <div class="file-size">${formatFileSize(attachment.size || 0)}</div>
                        </div>
                        <a href="${attachmentUrl || '#'}" class="btn-download" onclick="event.preventDefault(); downloadFileWithStructure('${attachmentUrl || ''}', '${escapeHtml(attachmentName)}', '${folderType}'); return false;">Скачать</a>
                    `;
                    
                    attachmentsDiv.appendChild(attachmentCard);
                });
                
                videoInfo.appendChild(attachmentsDiv);
            }
            
            wrapper.appendChild(videoWrapper);
            wrapper.appendChild(videoInfo);
            
            // Серая полосочка с иконкой вопроса под видео
            const videoActionBar = document.createElement('div');
            videoActionBar.className = 'content-action-bar';
            if (currentUserRole === 'admin' || currentUserRole === 'super_admin') {
                const askQuestionIcon = document.createElement('button');
                askQuestionIcon.className = 'btn-ask-question-icon';
                askQuestionIcon.innerHTML = '❓';
                askQuestionIcon.title = 'Задать вопрос по видео';
                askQuestionIcon.onclick = () => askQuestionAboutBlock(block.id, 'video');
                videoActionBar.appendChild(askQuestionIcon);
            }
            wrapper.appendChild(videoActionBar);
            break;
            
        case 'file':
            const fileCard = document.createElement('div');
            fileCard.className = 'file-card';
            const fileIcon = getFileIcon(content.type || '');
            // Исправляем URL для файлов из categories-data
            let fileUrl = content.url || '';
            const fileName = content.filename || 'Файл';
            const storedName = content.stored_filename || content.filename;
            if (fileUrl && (fileUrl.startsWith('http') || fileUrl.startsWith('/categories-data/'))) {
                // Уже корректный URL
            } else if (currentLesson && currentLesson.path_identifier && storedName) {
                const fn = (fileUrl && fileUrl.includes('/')) ? fileUrl.split('/').pop() : storedName;
                fileUrl = `/categories-data/${currentLesson.path_identifier}/files/${fn}`;
            }
            fileCard.innerHTML = `
                <div class="file-icon">${fileIcon}</div>
                <div class="file-info">
                    <div class="file-name">${escapeHtml(fileName)}</div>
                    <div class="file-size">${formatFileSize(content.size || 0)}</div>
                </div>
                <a href="${fileUrl || '#'}" class="btn-download" onclick="event.preventDefault(); downloadFileWithStructure('${fileUrl || ''}', '${escapeHtml(fileName)}', 'files'); return false;">Скачать</a>
            `;
            
            // Серая полосочка с иконкой вопроса под файлом
            const fileActionBar = document.createElement('div');
            fileActionBar.className = 'content-action-bar';
            if (currentUserRole === 'admin' || currentUserRole === 'super_admin') {
                const askQuestionIcon = document.createElement('button');
                askQuestionIcon.className = 'btn-ask-question-icon';
                askQuestionIcon.innerHTML = '❓';
                askQuestionIcon.title = 'Задать вопрос по файлу';
                askQuestionIcon.onclick = () => askQuestionAboutBlock(block.id, 'file');
                fileActionBar.appendChild(askQuestionIcon);
            }
            fileCard.appendChild(fileActionBar);
            
            wrapper.appendChild(fileCard);
            break;
            
        case 'image':
            const imageWrapper = document.createElement('div');
            imageWrapper.className = 'image-wrapper';
            const img = document.createElement('img');
            // Исправляем URL для изображений из categories-data
            let imageUrl = content.url || '';
            const imageFilename = content.stored_filename || content.filename || '';
            
            if (imageUrl && (imageUrl.startsWith('http') || imageUrl.startsWith('/categories-data/'))) {
                // Уже корректный URL
            } else if (currentLesson && currentLesson.path_identifier && imageFilename) {
                const fn = (imageUrl && !imageUrl.startsWith('http') && imageUrl.includes('/')) ? imageUrl.split('/').pop() : imageFilename;
                imageUrl = `/categories-data/${currentLesson.path_identifier}/images/${fn}`;
            }
            
            img.src = imageUrl;
            img.alt = content.alt || imageFilename || 'Изображение';
            img.style.maxWidth = '100%';
            img.style.height = 'auto';
            img.loading = 'lazy';
            
            // Обработка ошибок загрузки
            img.addEventListener('error', (e) => {
                console.error('Ошибка загрузки изображения:', imageUrl);
                img.style.display = 'none';
                const errorDiv = document.createElement('div');
                errorDiv.style.cssText = 'padding: 2rem; text-align: center; color: #999; background: #f5f5f5; border-radius: 8px;';
                errorDiv.innerHTML = `
                    <span style="font-size: 3rem; display: block; margin-bottom: 1rem;">🖼️</span>
                    <div>Не удалось загрузить изображение</div>
                    ${imageUrl ? `<a href="${imageUrl}" style="color: #67add3; text-decoration: underline; margin-top: 0.5rem; display: inline-block;">Открыть изображение</a>` : ''}
                `;
                imageWrapper.appendChild(errorDiv);
            });
            
            if (content.width) img.style.width = `${content.width}px`;
            if (content.height) img.style.height = `${content.height}px`;
            img.addEventListener('click', () => openImageFullscreen(imageUrl));
            img.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                downloadFileWithStructure(imageUrl, content.alt || imageFilename || 'image.jpg', 'images');
            });
            imageWrapper.appendChild(img);
            if (content.alt) {
                const imageCaption = document.createElement('p');
                imageCaption.className = 'image-caption';
                imageCaption.textContent = content.alt;
                imageWrapper.appendChild(imageCaption);
            }
            
            // Серая полосочка с иконкой вопроса под изображением
            const imageActionBar = document.createElement('div');
            imageActionBar.className = 'content-action-bar';
            if (currentUserRole === 'admin' || currentUserRole === 'super_admin') {
                const askQuestionIcon = document.createElement('button');
                askQuestionIcon.className = 'btn-ask-question-icon';
                askQuestionIcon.innerHTML = '❓';
                askQuestionIcon.title = 'Задать вопрос по изображению';
                askQuestionIcon.onclick = () => askQuestionAboutBlock(block.id, 'image');
                imageActionBar.appendChild(askQuestionIcon);
            }
            imageWrapper.appendChild(imageActionBar);
            
            wrapper.appendChild(imageWrapper);
            break;
            
        case 'test':
            const testContainer = document.createElement('div');
            testContainer.className = 'test-container';

            const questions = Array.isArray(content.questions) ? content.questions : [];
            const settings = (content.settings && typeof content.settings === 'object') ? content.settings : {};
            const timeLimitSecondsRaw = settings.time_limit_seconds;
            const timeLimitSeconds = (typeof timeLimitSecondsRaw === 'number')
                ? timeLimitSecondsRaw
                : (typeof timeLimitSecondsRaw === 'string' ? parseInt(timeLimitSecondsRaw, 10) : 0);
            const hasTimeLimit = Number.isFinite(timeLimitSeconds) && timeLimitSeconds > 0;
            const availableFrom = settings.available_from || null;
            const availableUntil = settings.available_until || null;
            const hasTemporary = !!(availableFrom || availableUntil);

            let timeHeader = null;
            let timeValueEl = null;
            let startScreen = null;
            let startBtn = null;
            let timerIntervalId = null;

            function formatSeconds(s) {
                const sec = Math.max(0, parseInt(s, 10) || 0);
                const m = Math.floor(sec / 60);
                const r = sec % 60;
                return `${m}:${String(r).padStart(2, '0')}`;
            }
            function formatDateLocal(iso) {
                if (!iso || typeof iso !== 'string') return '—';
                try {
                    const d = new Date(iso);
                    return isNaN(d.getTime()) ? iso : d.toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' });
                } catch (e) { return iso; }
            }

            // Парсим значение datetime-local как локальное время Екатеринбурга (UTC+5)
            function parseEkaterinburgLocalToDate(value) {
                if (!value || typeof value !== 'string') return null;
                const parts = value.split('T');
                if (parts.length !== 2) return null;
                const [datePart, timePart] = parts;
                const [y, m, d] = datePart.split('-').map(Number);
                const [hh, mm] = timePart.split(':').map(Number);
                if (!Number.isFinite(y) || !Number.isFinite(m) || !Number.isFinite(d) || !Number.isFinite(hh) || !Number.isFinite(mm)) {
                    return null;
                }
                // Екатеринбург UTC+5: локальное → UTC
                const utcMs = Date.UTC(y, m - 1, d, hh - 5, mm);
                return new Date(utcMs);
            }

            function isWithinAvailability() {
                if (!hasTemporary) return true;
                const now = new Date().getTime();
                if (availableFrom) {
                    const fromDate = parseEkaterinburgLocalToDate(availableFrom);
                    const from = fromDate ? fromDate.getTime() : NaN;
                    if (!Number.isNaN(from) && now < from) return false;
                }
                if (availableUntil) {
                    const untilDate = parseEkaterinburgLocalToDate(availableUntil);
                    const until = untilDate ? untilDate.getTime() : NaN;
                    if (!Number.isNaN(until) && now > until) return false;
                }
                return true;
            }

            if (content.title) {
                const testTitle = document.createElement('h3');
                testTitle.className = 'test-title';
                testTitle.textContent = content.title;
                testContainer.appendChild(testTitle);
            }

            if (questions.length > 0) {
                // Экран старта: лимит времени или временная доступность — до «Начать» табы некликабельны
                const showStartScreen = hasTimeLimit || hasTemporary;
                if (showStartScreen) {
                    if (hasTimeLimit) {
                        timeHeader = document.createElement('div');
                        timeHeader.className = 'test-timebox';
                        timeHeader.innerHTML = `
                            <div class="test-timebox__label">Осталось времени</div>
                            <div class="test-timebox__value"></div>
                        `;
                        timeValueEl = timeHeader.querySelector('.test-timebox__value');
                        if (timeValueEl) timeValueEl.textContent = formatSeconds(timeLimitSeconds);
                        testContainer.appendChild(timeHeader);
                        timeHeader.style.display = 'none'; // показываем только после нажатия «Начать»
                    }

                    startScreen = document.createElement('div');
                    startScreen.className = 'test-start-screen';
                    const lines = [];
                    if (hasTimeLimit) {
                        const minutes = Math.max(1, Math.ceil(timeLimitSeconds / 60));
                        lines.push(`На прохождение этого теста даётся <strong>${minutes} мин.</strong> По истечении этого времени тест автоматически завершится.`);
                    }
                    if (hasTemporary) {
                        const fromStr = formatDateLocal(availableFrom);
                        const untilStr = formatDateLocal(availableUntil);
                        lines.push(`Тест доступен с ${fromStr} по ${untilStr}. Кнопка «Начать» доступна только в этот период.`);
                    }
                    lines.push('Табы с вопросами станут доступны только после нажатия кнопки «Начать».');
                    startScreen.innerHTML = `
                        <div class="test-start-title">Внимание</div>
                        <div class="test-start-text">${lines.join('<br>')}</div>
                        <div class="test-start-actions"></div>
                        <div class="test-start-hint" id="test-start-hint"></div>
                    `;
                    startBtn = document.createElement('button');
                    startBtn.type = 'button';
                    startBtn.className = 'test-start-btn';
                    startBtn.textContent = 'Начать';
                    const hintEl = startScreen.querySelector('#test-start-hint');
                    const within = isWithinAvailability();
                    if (!within && hasTemporary) {
                        startBtn.disabled = true;
                        if (hintEl) {
                            const now = new Date().getTime();
                            const from = availableFrom ? new Date(availableFrom).getTime() : 0;
                            const until = availableUntil ? new Date(availableUntil).getTime() : Infinity;
                            if (now < from) {
                                hintEl.textContent = 'Тест будет доступен с ' + formatDateLocal(availableFrom);
                                hintEl.className = 'test-start-hint test-start-hint--wait';
                            } else {
                                hintEl.textContent = 'Срок действия теста истёк.';
                                hintEl.className = 'test-start-hint test-start-hint--expired';
                            }
                        }
                    }
                    startScreen.querySelector('.test-start-actions')?.appendChild(startBtn);
                    testContainer.appendChild(startScreen);
                }
                const tabsHeader = document.createElement('div');
                tabsHeader.className = 'test-tabs-header';
                const tabsContent = document.createElement('div');
                tabsContent.className = 'test-tabs-content';

                questions.forEach((question, qIndex) => {
                    const tabBtn = document.createElement('button');
                    tabBtn.className = 'test-tab-btn' + (qIndex === 0 ? ' active' : '');
                    tabBtn.textContent = `Вопрос ${qIndex + 1}`;
                    tabBtn.dataset.index = String(qIndex);
                    tabsHeader.appendChild(tabBtn);

                    const questionWrapper = document.createElement('div');
                    questionWrapper.className = 'test-question' + (qIndex === 0 ? ' active' : '');
                    questionWrapper.dataset.index = String(qIndex);

                    const answerType = (question.answer_type || (question.multiple ? 'multiple' : 'single')).toLowerCase();
                    questionWrapper.dataset.answerType = answerType;

                    const questionText = document.createElement('div');
                    questionText.className = 'question-text';
                    questionText.textContent = `${qIndex + 1}. ${question.text || ''}`;
                    questionWrapper.appendChild(questionText);

                    const optionsDiv = document.createElement('div');
                    optionsDiv.className = 'test-options';

                    if (answerType === 'input') {
                        const inputWrapper = document.createElement('div');
                        inputWrapper.className = 'test-option';
                        const input = document.createElement('input');
                        input.type = 'text';
                        input.name = `question-${qIndex}-input`;
                        input.className = 'test-input-answer';
                        input.placeholder = 'Введите ответ';
                        inputWrapper.appendChild(input);
                        optionsDiv.appendChild(inputWrapper);
                    } else if (question.options && Array.isArray(question.options)) {
                        question.options.forEach((option, oIndex) => {
                            const optionDiv = document.createElement('div');
                            optionDiv.className = 'test-option';

                            const input = document.createElement('input');
                            input.type = answerType === 'multiple' ? 'checkbox' : 'radio';
                            input.name = `question-${qIndex}`;
                            input.id = `question-${qIndex}-option-${oIndex}`;
                            input.value = oIndex;

                            const label = document.createElement('label');
                            label.htmlFor = `question-${qIndex}-option-${oIndex}`;
                            label.textContent = option;

                            optionDiv.appendChild(input);
                            optionDiv.appendChild(label);
                            optionsDiv.appendChild(optionDiv);
                        });
                    }

                    questionWrapper.appendChild(optionsDiv);
                    tabsContent.appendChild(questionWrapper);
                });

                testContainer.appendChild(tabsHeader);
                testContainer.appendChild(tabsContent);

                // Навигация по табам (при showStartScreen табы скрыты, после «Начать» — доступны)
                const blockElForTabs = wrapper;
                tabsHeader.addEventListener('click', (e) => {
                    const btn = e.target.closest('.test-tab-btn');
                    if (!btn || btn.classList.contains('test-tab-btn--disabled')) return;
                    if (showStartScreen && blockElForTabs?.dataset?.testStarted !== '1') return;
                    const idx = btn.dataset.index;
                    tabsHeader.querySelectorAll('.test-tab-btn').forEach(b => b.classList.remove('active'));
                    tabsContent.querySelectorAll('.test-question').forEach(q => q.classList.remove('active'));
                    btn.classList.add('active');
                    const target = tabsContent.querySelector(`.test-question[data-index="${idx}"]`);
                    if (target) target.classList.add('active');
                });

                const controls = document.createElement('div');
                controls.className = 'test-controls';

                const prevBtn = document.createElement('button');
                prevBtn.type = 'button';
                prevBtn.className = 'test-nav-btn prev';
                prevBtn.textContent = 'Назад';
                const nextBtn = document.createElement('button');
                nextBtn.type = 'button';
                nextBtn.className = 'test-nav-btn next';
                nextBtn.textContent = 'Далее';
                const submitBtn = document.createElement('button');
                submitBtn.type = 'button';
                submitBtn.className = 'test-submit-btn';
                submitBtn.textContent = 'Проверить тест';
                submitBtn.onclick = () => {
                    if (submitBtn.textContent === 'Повторить попытку') {
                        resetTestForRetry(block.id);
                    } else {
                        submitTest(block.id);
                    }
                };

                controls.appendChild(prevBtn);
                controls.appendChild(nextBtn);
                controls.appendChild(submitBtn);
                testContainer.appendChild(controls);

                // До нажатия «Начать» скрываем интерфейс теста (табы некликабельны), после — запускаем таймер при лимите
                if (showStartScreen && startBtn && startScreen) {
                    tabsHeader.style.display = 'none';
                    tabsContent.style.display = 'none';
                    controls.style.display = 'none';

                    const blockEl = wrapper; // .content-block

                    function setAllDisabled(disabled) {
                        try {
                            blockEl.querySelectorAll('input, button').forEach((el) => {
                                if (el === startBtn) return;
                                el.disabled = !!disabled;
                            });
                        } catch (e) {}
                    }

                    function startTimerOnce() {
                        if (blockEl.dataset.testTimerStarted === '1') return;
                        blockEl.dataset.testTimerStarted = '1';

                        let remaining = timeLimitSeconds;
                        if (timeValueEl) timeValueEl.textContent = formatSeconds(remaining);

                        timerIntervalId = window.setInterval(async () => {
                            remaining -= 1;
                            if (timeValueEl) timeValueEl.textContent = formatSeconds(remaining);
                            if (remaining <= 0) {
                                window.clearInterval(timerIntervalId);
                                timerIntervalId = null;
                                if (timeValueEl) timeValueEl.textContent = '0:00';

                                setAllDisabled(true);
                                if (typeof customAlert === 'function') {
                                    customAlert('Время закончилось. Ответы отправляются автоматически.', 'Внимание');
                                } else {
                                    showInlineTestError(blockEl, 'Время закончилось. Отправляем попытку...');
                                }
                                if (blockEl.dataset.testAutoSubmitted !== '1') {
                                    blockEl.dataset.testAutoSubmitted = '1';
                                    try {
                                        await submitTest(block.id);
                                    } catch (e) {
                                        // submitTest сам покажет ошибку
                                    }
                                }
                            }
                        }, 1000);
                    }

                    startBtn.addEventListener('click', () => {
                        if (startBtn.disabled) return;
                        if (hasTimeLimit && blockEl.dataset.testTimerStarted === '1') return;
                        startScreen.style.display = 'none';
                        if (timeHeader) timeHeader.style.display = '';
                        tabsHeader.style.display = '';
                        tabsContent.style.display = '';
                        controls.style.display = '';
                        blockEl.dataset.testStarted = '1';
                        setAllDisabled(false);
                        if (hasTimeLimit) startTimerOnce();
                    });
                }

                // При рендере, если пользователь уже проходил этот тест, подгружаем последнюю попытку
                const renderedQuestionDivs = tabsContent.querySelectorAll('.test-question');
                loadLastTestResultForBlock(block.id, renderedQuestionDivs, wrapper);

                function switchQuestion(delta) {
                    const activeBtn = tabsHeader.querySelector('.test-tab-btn.active');
                    if (!activeBtn) return;
                    const idx = parseInt(activeBtn.dataset.index, 10);
                    const newIdx = idx + delta;
                    if (newIdx < 0 || newIdx >= questions.length) return;
                    const targetBtn = tabsHeader.querySelector(`.test-tab-btn[data-index="${newIdx}"]`);
                    if (targetBtn) targetBtn.click();
                }

                prevBtn.onclick = () => switchQuestion(-1);
                nextBtn.onclick = () => switchQuestion(1);
            }

            if (hasTimeLimit) {
                wrapper.dataset.timeLimitSeconds = String(timeLimitSeconds);
            }
            wrapper.appendChild(testContainer);
            break;
    }
    
    return wrapper;
}

// Загрузка breadcrumbs
async function loadBreadcrumbs(lessonId) {
    try {
        const response = await fetch(`${API_BASE}/lessons/${lessonId}/course-tree`);
        const data = await response.json();
        
        if (response.ok && breadcrumbsContainer) {
            breadcrumbsContainer.innerHTML = `
                <a href="/main-pg">Главная</a> >
                <a href="/all-categories-pg">Категории</a> >
                <a href="/all-courses-pg?category_id=${data?.category?.id || ''}">${escapeHtml(data?.category?.title || '')}</a> >
                <a href="/all-lessons-pg?course_id=${data?.course?.id || ''}">${escapeHtml(data?.course?.title || '')}</a> >
                <span>${escapeHtml(data?.lesson?.title || '')}</span>
            `;
        }
    } catch (error) {
        console.error('Ошибка загрузки breadcrumbs:', error);
        // Не показываем ошибку пользователю, так как breadcrumbs не критичны
    }
}

// Загрузка навигации (предыдущий/следующий урок)
async function loadNavigation(lessonId) {
    try {
        const [prevResponse, nextResponse] = await Promise.all([
            fetch(`${API_BASE}/lessons/${lessonId}/previous`),
            fetch(`${API_BASE}/lessons/${lessonId}/next`)
        ]);
        
        const prevData = prevResponse.ok ? await prevResponse.json() : { lesson: null };
        const nextData = nextResponse.ok ? await nextResponse.json() : { lesson: null };
        
        if (navigationContainer) {
            navigationContainer.innerHTML = `
                <button class="btn-nav btn-prev" 
                        ${!prevData.lesson ? 'disabled' : ''}
                        onclick="openLesson(${prevData.lesson?.id || 0})">
                    ← Предыдущий урок
                </button>
                <button class="btn-nav btn-next" 
                        ${!nextData.lesson || !nextData.lesson.is_accessible ? 'disabled' : ''}
                        onclick="openLesson(${nextData.lesson?.id || 0})">
                    Следующий урок →
                </button>
            `;
        }
    } catch (error) {
        console.error('Ошибка загрузки навигации:', error);
    }
}

// Добавление кнопок действий
function addActionButtons(lesson) {
    let actionsContainer = document.querySelector('.lesson-actions');
    if (!actionsContainer) {
        actionsContainer = document.createElement('div');
        actionsContainer.className = 'lesson-actions';
        lessonContentContainer.appendChild(actionsContainer);
    }
    
    actionsContainer.innerHTML = '';
    
    // Кнопка "Завершить урок" (только если не завершен)
    if (!lesson.is_completed) {
        const completeBtn = document.createElement('button');
        completeBtn.className = 'btn-complete-lesson';
        completeBtn.textContent = 'Завершить урок';
        completeBtn.onclick = () => completeLesson(lesson.id);
        actionsContainer.appendChild(completeBtn);
    }
    
    // Кнопка "Задать вопрос по уроку"
    const askQuestionBtn = document.createElement('button');
    askQuestionBtn.className = 'btn-ask-question';
    askQuestionBtn.textContent = 'Задать вопрос по уроку';
    askQuestionBtn.onclick = () => askQuestionAboutLesson(lesson.id);
    actionsContainer.appendChild(askQuestionBtn);
}

// Завершить урок
async function completeLesson(lessonId) {
    try {
        const response = await fetch(`${API_BASE}/lessons/${lessonId}/complete`, {
            method: 'POST'
        });
        
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const code = data.code || '';
            if (code === 'test_not_passed' || code === 'test_not_passed_exhausted') {
                // Обновляем статусы тестов и UI блокировки
                lessonTestsGate = await loadLessonTestsStatus();
                updateCompletionGateUI();
                throw new Error(data.error || 'Сначала пройдите тест');
            }
            throw new Error(data.error || `HTTP error! status: ${response.status}`);
        }
        // Показываем уведомление только при первом завершении (не при повторном заходе)
        if (data.just_completed) {
            showSuccess('Урок завершен!');
        }
        // Перезагружаем урок
        loadLesson(lessonId);
    } catch (error) {
        console.error('Ошибка:', error);
        showError('Не удалось завершить урок');
    }
}

// Задать вопрос по уроку — переход на страницу вопросов с формой создания
function askQuestionAboutLesson(lessonId) {
    window.location.href = `/questions-pg?tab=ask&lesson_id=${lessonId}`;
}

// Показать элементы управления для admin
function showAdminControls() {
    // Добавляем кнопку редактирования
    const editBtn = document.createElement('button');
    editBtn.className = 'btn-edit-lesson';
    editBtn.textContent = 'Редактировать урок';
    editBtn.onclick = () => toggleEditMode();
    
    const actionsContainer = document.querySelector('.lesson-actions');
    if (actionsContainer) {
        actionsContainer.insertBefore(editBtn, actionsContainer.firstChild);
    }
}

// Переключение режима редактирования
function toggleEditMode() {
    // Импортируем функции из lesson-editor.js
    if (typeof window.toggleEditMode === 'function') {
        window.toggleEditMode();
    } else {
        customAlert('Редактор урока загружается...', 'Информация');
    }
}

// Утилиты
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function sanitizeHtml(html) {
    // Используем DOMPurify если доступен, иначе базовое экранирование
    if (typeof DOMPurify !== 'undefined') {
        return DOMPurify.sanitize(html, { ALLOWED_TAGS: [], ALLOWED_ATTR: [] });
    }
    // Базовое экранирование HTML
    if (!html) return '';
    const div = document.createElement('div');
    div.textContent = html;
    return div.innerHTML
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#x27;')
        .replace(/\//g, '&#x2F;');
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function getFileIcon(mimeType) {
    if (mimeType.includes('pdf')) return '📄';
    if (mimeType.includes('word') || mimeType.includes('document')) return '📝';
    if (mimeType.includes('excel') || mimeType.includes('spreadsheet')) return '📊';
    if (mimeType.includes('image')) return '🖼️';
    if (mimeType.includes('video')) return '🎥';
    return '📎';
}

function openImageFullscreen(url) {
    // Создаем модальное окно для полноэкранного просмотра
    let fullscreenModal = document.getElementById('image-fullscreen-modal');
    if (!fullscreenModal) {
        fullscreenModal = document.createElement('div');
        fullscreenModal.id = 'image-fullscreen-modal';
        fullscreenModal.className = 'image-fullscreen-modal';
        document.body.appendChild(fullscreenModal);
    }
    
    fullscreenModal.innerHTML = `
        <div class="image-fullscreen-content">
            <span class="image-fullscreen-close" onclick="closeImageFullscreen()">&times;</span>
            <img src="${escapeHtml(url)}" alt="Fullscreen image" />
        </div>
    `;
    
    fullscreenModal.classList.add('active');
    
    // Закрытие по клику вне изображения
    fullscreenModal.addEventListener('click', (e) => {
        if (e.target === fullscreenModal) {
            closeImageFullscreen();
        }
    });
    
    // Закрытие по Escape
    document.addEventListener('keydown', function escapeHandler(e) {
        if (e.key === 'Escape') {
            closeImageFullscreen();
            document.removeEventListener('keydown', escapeHandler);
        }
    });
}

function closeImageFullscreen() {
    const fullscreenModal = document.getElementById('image-fullscreen-modal');
    if (fullscreenModal) {
        fullscreenModal.classList.remove('active');
    }
}

/** Сбросить тест для новой попытки: разблокировать табы и поля, очистить ответы, кнопка «Ответить» */
function resetTestForRetry(blockId) {
    const blockEl = document.querySelector(`.content-block[data-block-id="${blockId}"]`);
    if (!blockEl) return;
    const tabsHeader = blockEl.querySelector('.test-tabs-header');
    const tabsContent = blockEl.querySelector('.test-tabs-content');
    const submitBtn = blockEl.querySelector('.test-submit-btn');
    const controls = blockEl.querySelector('.test-controls');
    const startScreen = blockEl.querySelector('.test-start-screen');

    // Если предыдущая попытка завершилась таймером/блокировкой — снимаем disabled со всех кнопок/инпутов.
    // Иначе UI может остаться "зависшим" (табы/кнопка «Далее» неактивны).
    try {
        blockEl.querySelectorAll('input, button').forEach((el) => { el.disabled = false; });
    } catch (e) {}
    // Сбрасываем маркеры автосабмита/таймера, чтобы новая попытка была предсказуемой
    delete blockEl.dataset.testAutoSubmitted;
    delete blockEl.dataset.testRetryTimerStarted;
    // Считаем тест уже начатым после ретрая: табы/навигация должны работать сразу
    blockEl.dataset.testStarted = '1';
    if (startScreen) startScreen.style.display = 'none';
    if (tabsHeader) tabsHeader.style.display = '';
    if (tabsContent) tabsContent.style.display = '';
    if (controls) controls.style.display = '';

    // Разблокируем табы вопросов
    if (tabsHeader) {
        tabsHeader.querySelectorAll('.test-tab-btn').forEach((b) => {
            if (b.dataset.index !== 'results') {
                b.classList.remove('test-tab-btn--disabled');
                b.disabled = false;
            }
        });
    }

    // Разблокируем все поля ввода (только в вопросах, не в панели результатов)
    blockEl.querySelectorAll('.test-question:not([data-index="results"])').forEach((qDiv) => {
        qDiv.classList.remove('test-question-correct', 'test-question-incorrect');
        qDiv.querySelectorAll('.test-option').forEach((opt) => {
            opt.classList.remove('test-option-correct', 'test-option-user-wrong');
        });
        const answerType = (qDiv.dataset.answerType || '').toLowerCase();
        if (answerType === 'input') {
            const input = qDiv.querySelector('input.test-input-answer');
            if (input) {
                input.value = '';
                input.disabled = false;
            }
        } else {
            qDiv.querySelectorAll('input[type="radio"], input[type="checkbox"]').forEach((inp) => {
                inp.checked = false;
                inp.disabled = false;
            });
        }
    });

    // Переключаемся на первый вопрос
    const firstTab = tabsHeader ? tabsHeader.querySelector('.test-tab-btn[data-index="0"]') : null;
    if (firstTab && tabsContent) {
        tabsHeader.querySelectorAll('.test-tab-btn').forEach((b) => b.classList.remove('active'));
        tabsContent.querySelectorAll('.test-question').forEach((q) => q.classList.remove('active'));
        firstTab.classList.add('active');
        const firstPanel = tabsContent.querySelector('.test-question[data-index="0"]');
        if (firstPanel) firstPanel.classList.add('active');
    }

    // Кнопка «Ответить» — включается после выбора варианта
    if (submitBtn) {
        submitBtn.textContent = 'Ответить';
        submitBtn.disabled = true;
        blockEl.dataset.retryMode = '1';

        function checkCanSubmit() {
            const qs = blockEl.querySelectorAll('.test-question:not([data-index="results"])');
            for (const q of qs) {
                const at = (q.dataset.answerType || '').toLowerCase();
                if (at === 'input') {
                    const i = q.querySelector('input.test-input-answer');
                    if (i && (i.value || '').trim()) { submitBtn.disabled = false; return; }
                } else {
                    const checked = q.querySelectorAll('input:checked');
                    if (checked.length > 0) { submitBtn.disabled = false; return; }
                }
            }
            submitBtn.disabled = true;
        }
        blockEl.querySelectorAll('.test-question:not([data-index="results"]) input').forEach((inp) => {
            inp.addEventListener('change', checkCanSubmit);
            inp.addEventListener('input', checkCanSubmit);
        });
        checkCanSubmit();
    }

    const errEl = blockEl.querySelector('.test-inline-error');
    if (errEl) errEl.textContent = '';

    // Если тест с таймером — запускаем таймер при нажатии «Повторить»
    const timeLimitSeconds = parseInt(blockEl.dataset.timeLimitSeconds, 10);
    if (Number.isFinite(timeLimitSeconds) && timeLimitSeconds > 0 && blockEl.dataset.testRetryTimerStarted !== '1') {
        blockEl.dataset.testRetryTimerStarted = '1';
        const timeHeader = blockEl.querySelector('.test-timebox');
        const timeValueEl = timeHeader ? timeHeader.querySelector('.test-timebox__value') : null;
        function fmt(s) {
            const sec = Math.max(0, parseInt(s, 10) || 0);
            return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`;
        }
        if (timeHeader) timeHeader.style.display = '';
        if (timeValueEl) timeValueEl.textContent = fmt(timeLimitSeconds);
        let remaining = timeLimitSeconds;
        const iv = window.setInterval(async () => {
            remaining -= 1;
            if (timeValueEl) timeValueEl.textContent = fmt(remaining);
            if (remaining <= 0) {
                window.clearInterval(iv);
                if (timeValueEl) timeValueEl.textContent = '0:00';
                blockEl.querySelectorAll('input, button').forEach((el) => { el.disabled = true; });
                if (typeof customAlert === 'function') {
                    customAlert('Время закончилось. Ответы отправляются автоматически.', 'Внимание');
                } else {
                    showInlineTestError(blockEl, 'Время закончилось. Отправляем попытку...');
                }
                if (blockEl.dataset.testAutoSubmitted !== '1') {
                    blockEl.dataset.testAutoSubmitted = '1';
                    try { await submitTest(blockId); } catch (e) {}
                }
            }
        }, 1000);
    }
}

async function submitTest(blockId) {
    if (!currentLesson || !currentLesson.id) {
        const blockEl = document.querySelector(`.content-block[data-block-id="${blockId}"]`);
        if (blockEl) {
            showInlineTestError(blockEl, 'Урок не загружен');
        } else {
            showError('Урок не загружен');
        }
        return;
    }
    const blockEl = document.querySelector(`.content-block[data-block-id="${blockId}"]`);
    if (!blockEl) {
        showError('Блок теста не найден');
        return;
    }
    // Не включаем панель "Результаты" в ответы
    const questionDivs = blockEl.querySelectorAll('.test-question:not([data-index="results"])');
    const answers = [];
    questionDivs.forEach((qDiv, idx) => {
        const answerType = (qDiv.dataset.answerType || '').toLowerCase();
        if (answerType === 'input') {
            const input = qDiv.querySelector('input.test-input-answer');
            answers[idx] = input ? (input.value || '').trim() : '';
        } else {
            const checked = qDiv.querySelectorAll('input:checked');
            const selected = Array.from(checked).map(inp => parseInt(inp.value, 10)).filter(n => !isNaN(n));
            answers[idx] = selected;
        }
    });
    const submitBtn = blockEl.querySelector('.test-submit-btn');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Проверка...';
    }
    try {
        const response = await fetch(`${API_BASE}/lessons/${currentLesson.id}/blocks/${blockId}/submit-test`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ answers })
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            // Пытаемся показать полезный текст прямо в блоке
            const msg = data.error || 'Ошибка при проверке';
            showInlineTestError(blockEl, msg);
            // Если попытки исчерпаны — блокируем кнопку
            if (data.code === 'attempts_exhausted' && submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = 'Попытки исчерпаны';
            } else if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Проверить тест';
            }
            return;
        }
        showTestResult(blockEl, data, questionDivs);

        // Обновляем блокировку завершения урока после попытки
        lessonTestsGate = await loadLessonTestsStatus();
        updateCompletionGateUI();
    } catch (err) {
        showInlineTestError(blockEl, err.message || 'Не удалось отправить ответы');
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Проверить тест';
        }
    }
}

async function loadLastTestResultForBlock(blockId, questionDivs, fallbackBlockEl) {
    if (!currentLesson || !currentLesson.id) return;
    try {
        const resp = await fetch(`${API_BASE}/lessons/${currentLesson.id}/blocks/${blockId}/submit-test/last`);
        if (!resp.ok) return;
        const data = await resp.json().catch(() => ({}));
        if (!data || !Array.isArray(data.feedback)) return;
        const blockEl = document.querySelector(`.content-block[data-block-id="${blockId}"]`) || fallbackBlockEl;
        if (!blockEl) return;
        showTestResult(blockEl, data, questionDivs);
    } catch (e) {
        console.error('Ошибка загрузки последнего результата теста:', e);
    }
}

function showTestResult(blockEl, data, questionDivs) {
    const { score, total, score_percent, passed, feedback, attempts_used, attempts_left, max_attempts, pass_percent } = data;

    // Сбрасываем подсветку, значения инпутов и предыдущий результат перед новой попыткой
    (questionDivs || []).forEach((qDiv) => {
        if (!qDiv) return;
        qDiv.classList.remove('test-question-correct', 'test-question-incorrect');
        // Сбрасываем подсветку вариантов
        qDiv.querySelectorAll('.test-option').forEach((opt) => {
            opt.classList.remove('test-option-correct', 'test-option-user-wrong');
        });
        // Сбрасываем отметки вариантов
        qDiv.querySelectorAll('input[type="radio"], input[type="checkbox"]').forEach((inp) => {
            inp.checked = false;
        });
        // Сбрасываем текстовый ответ
        const inputAnswer = qDiv.querySelector('input.test-input-answer');
        if (inputAnswer) {
            inputAnswer.value = '';
        }
    });
    const prevResult = blockEl.querySelector('.test-result');
    if (prevResult) prevResult.remove();

    const hasLimit = typeof max_attempts === 'number';
    const left = (typeof attempts_left === 'number') ? attempts_left : null;
    const canRetry = !passed && (!hasLimit || (left !== null && left > 0));

    // Контейнер результата: таб «Результаты» + блокировка полей + логика табов по попыткам
    const feedbackContainer = document.createElement('div');
    feedbackContainer.className = 'test-result-feedback';
    if (canRetry) {
        // При нескольких попытках и провале — только процент, без раскрытия правильных/неправильных ответов
        const pct = typeof score_percent === 'number' ? score_percent : (total ? Math.round((score / total) * 100) : 0);
        feedbackContainer.innerHTML = `
            <div class="test-feedback-summary">
                <p>Набрано <strong>${pct}%</strong> (${score || 0} из ${total || 0}).</p>
                ${hasLimit && left !== null ? `<p>Осталось попыток: ${left}</p>` : ''}
                <p>Нажмите «Повторить попытку», чтобы ответить снова.</p>
            </div>
        `;
    } else {
        (feedback || []).forEach((fb, i) => {
            const qDiv = questionDivs[i];
            const item = document.createElement('div');
            item.className = `test-feedback-item ${fb.correct ? 'correct' : 'incorrect'}`;
            const isInput = (fb.answerType || '').toLowerCase() === 'input';
            const correctText = isInput
                ? ((fb.acceptedAnswersText || []).join(', ') || '—')
                : ((fb.correctOptionsText || []).join(', ') || '—');
            item.innerHTML = `
                <span class="feedback-icon">${fb.correct ? '✓' : '✗'}</span>
                <span>Вопрос ${(i + 1)}: ${fb.correct ? 'Верно' : (isInput ? ('Неверно. Допустимые ответы: ' + correctText) : ('Неверно. Правильный ответ: ' + correctText))}</span>
            `;
            feedbackContainer.appendChild(item);

            if (!qDiv) return;

            // Восстанавливаем выбранные пользователем ответы
            if (isInput) {
                const textInput = qDiv.querySelector('input.test-input-answer');
                if (textInput && typeof fb.userAnswerText === 'string') {
                    textInput.value = fb.userAnswerText;
                }
            } else if (Array.isArray(fb.userSelected)) {
                const userSelected = fb.userSelected || [];
                qDiv.querySelectorAll('input[type="radio"], input[type="checkbox"]').forEach((inp) => {
                    const idx = parseInt(inp.value, 10);
                    if (!Number.isNaN(idx)) inp.checked = userSelected.includes(idx);
                });
            }

            // Подсветка только если НЕ canRetry (последняя попытка или тест пройден)
            if (fb.correct) {
                qDiv.classList.add('test-question-correct');
            } else {
                qDiv.classList.add('test-question-incorrect');
            }
            if (!isInput && Array.isArray(fb.correctAnswer)) {
                const correctAnswer = fb.correctAnswer || [];
                const userSelected = fb.userSelected || [];
                qDiv.querySelectorAll('.test-option').forEach((opt) => {
                    const input = opt.querySelector('input[type="radio"], input[type="checkbox"]');
                    if (!input) return;
                    const idx = parseInt(input.value, 10);
                    if (Number.isNaN(idx)) return;
                    const isCorrectOpt = correctAnswer.includes(idx);
                    const isUserOpt = userSelected.includes(idx);
                    if (isCorrectOpt) opt.classList.add('test-option-correct');
                    if (isUserOpt && !isCorrectOpt) opt.classList.add('test-option-user-wrong');
                });
            }
        });
    }

    const submitBtn = blockEl.querySelector('.test-submit-btn');
    if (submitBtn) {
        if (passed) {
            submitBtn.disabled = true;
            submitBtn.textContent = 'Тест пройден';
        } else if (canRetry) {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Повторить попытку';
        } else {
            submitBtn.disabled = true;
            submitBtn.textContent = 'Попытки исчерпаны';
        }
    }

    // Блокируем все поля после прохождения/проверки
    blockEl.querySelectorAll('input.test-input-answer, input[type="radio"], input[type="checkbox"]').forEach((inp) => {
        inp.disabled = true;
    });

    const testContainer = blockEl.querySelector('.test-container');
    const tabsHeader = blockEl.querySelector('.test-tabs-header');
    const tabsContent = blockEl.querySelector('.test-tabs-content');
    const resultsTabId = 'results';

    // Таб «Результаты»: находим или создаём
    let resultsTabBtn = tabsHeader ? tabsHeader.querySelector('.test-tab-btn[data-index="' + resultsTabId + '"]') : null;
    let resultsPanel = tabsContent ? tabsContent.querySelector('.test-question[data-index="' + resultsTabId + '"]') : null;

    if (tabsHeader && tabsContent) {
        if (!resultsTabBtn) {
            resultsTabBtn = document.createElement('button');
            resultsTabBtn.type = 'button';
            resultsTabBtn.className = 'test-tab-btn';
            resultsTabBtn.textContent = 'Результаты';
            resultsTabBtn.dataset.index = resultsTabId;
            tabsHeader.appendChild(resultsTabBtn);

            resultsPanel = document.createElement('div');
            resultsPanel.className = 'test-question test-results-panel';
            resultsPanel.dataset.index = resultsTabId;
            tabsContent.appendChild(resultsPanel);

            // Обработчик переключения табов (в т.ч. «Результаты»); блокирует клик по отключённым табам
            tabsHeader.addEventListener('click', function tabClick(e) {
                const btn = e.target.closest('.test-tab-btn');
                if (!btn) return;
                if (btn.classList.contains('test-tab-btn--disabled')) {
                    e.preventDefault();
                    e.stopImmediatePropagation();
                    return;
                }
                const idx = btn.dataset.index;
                tabsHeader.querySelectorAll('.test-tab-btn').forEach((b) => b.classList.remove('active'));
                tabsContent.querySelectorAll('.test-question').forEach((q) => q.classList.remove('active'));
                btn.classList.add('active');
                const target = tabsContent.querySelector('.test-question[data-index="' + idx + '"]');
                if (target) target.classList.add('active');
            }, true);
        }

        // Контент результата в панель (каждый раз новый)
        if (resultsPanel) {
            let resultWrap = resultsPanel.querySelector('.test-result');
            if (!resultWrap) {
                resultWrap = document.createElement('div');
                resultWrap.className = 'test-result';
                resultsPanel.appendChild(resultWrap);
            }
            resultWrap.innerHTML = '';
            resultWrap.appendChild(feedbackContainer);
        }

        // Показываем таб «Результаты»; при canRetry табы вопросов блокируются до нажатия «Повторить»
        const multiAttempt = typeof max_attempts === 'number' && max_attempts > 1;
        const blockQuestionTabs = canRetry || multiAttempt;
        tabsHeader.querySelectorAll('.test-tab-btn').forEach((b) => {
            if (b.dataset.index === resultsTabId) {
                b.classList.remove('test-tab-btn--disabled');
                b.classList.add('active');
            } else {
                if (blockQuestionTabs) {
                    b.classList.add('test-tab-btn--disabled');
                } else {
                    b.classList.remove('test-tab-btn--disabled');
                }
                b.classList.remove('active');
            }
        });
        tabsContent.querySelectorAll('.test-question').forEach((q) => {
            q.classList.toggle('active', q.dataset.index === resultsTabId);
        });
    } else {
        const resultDiv = document.createElement('div');
        resultDiv.className = 'test-result';
        resultDiv.appendChild(feedbackContainer);
        if (testContainer) testContainer.appendChild(resultDiv);
    }
}

function showInlineTestError(blockEl, message) {
    if (!blockEl) return;
    let errorDiv = blockEl.querySelector('.test-inline-error');
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.className = 'test-inline-error';
        const container = blockEl.querySelector('.test-container') || blockEl;
        container.appendChild(errorDiv);
    }
    errorDiv.textContent = message;
}

function showError(message) {
    console.error('Error:', message);
    // Показываем ошибку в контейнере, если он доступен
    if (lessonContentContainer) {
        const errorDiv = document.createElement('div');
        errorDiv.style.cssText = 'padding: 2rem; margin: 1rem; background: #ffebee; border: 2px solid #d32f2f; border-radius: 8px; color: #d32f2f; text-align: center;';
        errorDiv.innerHTML = `
            <h3 style="margin: 0 0 0.5rem 0;">⚠️ Ошибка</h3>
            <p style="margin: 0;">${escapeHtml(message)}</p>
        `;
        // Удаляем предыдущие ошибки
        const oldError = lessonContentContainer.querySelector('.error-message');
        if (oldError) oldError.remove();
        errorDiv.className = 'error-message';
        lessonContentContainer.insertBefore(errorDiv, lessonContentContainer.firstChild);
    } else {
        // Если контейнер не найден, используем кастомное модальное окно
        customAlert(message, 'Ошибка');
    }
}

function showSuccess(message) {
    customAlert(message, 'Успешно');
}

function openLesson(lessonId) {
    if (lessonId) {
        window.location.href = `/lessons-content-pg?lesson_id=${lessonId}`;
    }
}

// Отслеживание прокрутки урока
function startScrollTracking() {
    if (scrollTrackingEnabled || !lessonBlocksContainer) return;
    
    scrollTrackingEnabled = true;
    const container = lessonBlocksContainer;
    
    // Проверяем прокрутку при скролле
    const checkScroll = () => {
        if (lessonCompleted) return;
        
        const containerRect = container.getBoundingClientRect();
        const windowHeight = window.innerHeight;
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const containerBottom = containerRect.bottom + scrollTop;
        const windowBottom = scrollTop + windowHeight;
        
        // Если прокрутили до конца контейнера (с небольшим допуском)
        if (windowBottom >= containerBottom - 50) {
            scrollProgress = 100;
            checkLessonCompletion();
        } else {
            // Вычисляем процент прокрутки
            const totalHeight = container.scrollHeight;
            const visibleHeight = windowHeight;
            const scrolled = scrollTop - (containerRect.top + scrollTop);
            scrollProgress = Math.min(100, Math.max(0, ((scrolled + visibleHeight) / totalHeight) * 100));
        }
    };
    
    // Отслеживаем скролл
    // Сохраняем обработчики для возможной очистки
    const scrollHandler = () => checkScroll();
    const resizeHandler = () => checkScroll();
    
    window.addEventListener('scroll', scrollHandler, { passive: true });
    window.addEventListener('resize', resizeHandler);
    
    // Сохраняем ссылки для очистки
    if (!window.lessonViewerHandlers) {
        window.lessonViewerHandlers = [];
    }
    window.lessonViewerHandlers.push(
        { element: window, event: 'scroll', handler: scrollHandler },
        { element: window, event: 'resize', handler: resizeHandler }
    );
    
    // Проверяем сразу
    checkScroll();
}

// Настройка отслеживания видео
function setupVideoTracking(iframe, blockId) {
    if (videoTrackingEnabled || !iframe.src) return;
    
    // Для iframe видео (Rutube, YouTube) используем postMessage API
    // Отслеживаем события через периодическую проверку
    const videoId = `video-${blockId}`;
    
    // Пытаемся отследить через postMessage (работает для YouTube/Rutube)
    window.addEventListener('message', (event) => {
        // Проверяем сообщения от видео плееров
        if (event.data && typeof event.data === 'object') {
            // YouTube API события
            if (event.data.event === 'video-progress' || event.data.info?.currentTime) {
                const progress = event.data.info?.currentTime / event.data.info?.duration;
                if (progress >= 0.95) { // 95% просмотрено считается завершенным
                    videosWatched.add(videoId);
                    checkLessonCompletion();
                }
            }
        }
    });
    
    // Альтернативный метод: отслеживание времени на странице
    // Если пользователь провел достаточно времени на странице с видео, считаем просмотренным
    let timeOnPage = 0;
    const timeCheckInterval = setInterval(() => {
        timeOnPage += 5; // Проверяем каждые 5 секунд
        
        // Если прошло более 2 минут на странице с видео, считаем просмотренным
        // (это эвристика, так как напрямую отследить iframe сложно)
        if (timeOnPage >= 120 && !videosWatched.has(videoId)) {
            videosWatched.add(videoId);
            checkLessonCompletion();
            clearInterval(timeCheckInterval);
        }
    }, 5000);
    
    // Сохраняем ID интервала для возможной очистки
    if (!window.videoTrackingIntervals) {
        window.videoTrackingIntervals = new Set();
    }
    window.videoTrackingIntervals.add(timeCheckInterval);
}

// Проверка условий завершения урока
async function checkLessonCompletion() {
    if (lessonCompleted || !currentLesson) return;
    
    // Проверяем условия:
    // 1. Урок прокручен до конца (scrollProgress >= 95%)
    // 2. Все видео просмотрены (если есть)
    
    const allVideosWatched = checkAllVideosWatched();
    const scrolledToEnd = scrollProgress >= 95;
    
    if (scrolledToEnd && allVideosWatched) {
        // Автоматически завершаем урок
        await autoCompleteLesson();
    }
}

// Проверка просмотра всех видео
function checkAllVideosWatched() {
    if (!lessonBlocksContainer) return true;
    
    const videoBlocks = lessonBlocksContainer.querySelectorAll('.video-wrapper');
    if (videoBlocks.length === 0) return true; // Нет видео - условие выполнено
    
    // Проверяем, что все видео просмотрены
    for (const videoBlock of videoBlocks) {
        const videoId = videoBlock.dataset.videoId;
        if (!videosWatched.has(videoId)) {
            return false;
        }
    }
    
    return true;
}

// Автоматическое завершение урока
async function autoCompleteLesson() {
    // Не показываем уведомление и не дергаем API, если урок уже пройден
    if (lessonCompleted || currentLesson?.is_completed || currentLesson?.lesson_status === 2) return;

    // Не автозавершаем, если есть непройденный тест
    if (lessonTestsGate?.has_tests && !lessonTestsGate?.all_passed) return;
    
    try {
        if (!currentLesson?.id) {
            console.error('currentLesson.id не определен');
            return;
        }
        
        const response = await fetch(`${API_BASE}/lessons/${currentLesson.id}/complete`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            lessonCompleted = true;
            // Показываем уведомление только при первом завершении
            if (data.just_completed) {
                showSuccess('Урок автоматически завершен! Вы просмотрели весь контент.');
            }
            
            // Обновляем UI
            const completeBtn = document.querySelector('.btn-complete-lesson');
            if (completeBtn) {
                completeBtn.textContent = 'Урок завершен';
                completeBtn.disabled = true;
            }
            
            // Перезагружаем урок для обновления статуса
            setTimeout(() => {
                if (currentLesson?.id) {
                    loadLesson(currentLesson.id);
                }
            }, 1000);
        }
    } catch (error) {
        console.error('Ошибка автоматического завершения урока:', error);
        // Не показываем ошибку пользователю, автоматическое завершение не критично
    }
}

// Задать вопрос по блоку контента — переход на страницу вопросов с формой создания
function askQuestionAboutBlock(blockId, blockType) {
    if (!currentLesson) return;
    const blockTypeLabels = { 'video': 'Видео', 'file': 'Файл', 'image': 'Изображение', 'text': 'Текст' };
    const title = `Вопрос по ${blockTypeLabels[blockType] || blockType} в уроке «${currentLesson?.title || ''}»`;
    const tags = `Урок: ${currentLesson?.title || ''}, Блок: ${blockTypeLabels[blockType] || blockType}`;
    window.location.href = `/questions-pg?tab=ask&lesson_id=${currentLesson.id}&title=${encodeURIComponent(title)}&tags=${encodeURIComponent(tags)}`;
}

// Настройка обработчиков событий
function setupEventListeners() {
    // Дополнительные обработчики при необходимости
}

// Скачивание файла с сохранением структуры папок
async function downloadFileWithStructure(fileUrl, filename, fileType) {
    try {
        if (!currentLesson) {
            showError('Урок не загружен');
            return;
        }

        // Используем path_identifier из урока, если он есть
        let folderPath = '';
        if (currentLesson?.path_identifier) {
            folderPath = `${currentLesson.path_identifier}/${fileType}`;
        } else {
            // Fallback: получаем путь к уроку из API
            if (!currentLesson?.id) {
                console.error('currentLesson.id не определен');
                showError('Урок не загружен');
                return null;
            }

            const response = await fetch(`${API_BASE}/lessons/${currentLesson.id}/course-tree`);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData?.error || 'Не удалось получить путь к уроку');
            }

            const data = await response.json();

            // Формируем структуру папок только для имени файла (для имени скачивания),
            // но сам браузер сохраняет файл стандартным диалогом.
            const categorySlug = data?.category?.title ? slugify(data.category.title) : '';
            const courseSlug = data?.course?.title ? slugify(data.course.title) : '';
            const lessonSlug = data?.lesson?.title ? slugify(data.lesson.title) : '';
            folderPath = `category-${categorySlug}/course-${courseSlug}/lesson-${lessonSlug}/${fileType}`;
        }

        // Упрощаем: всегда используем стандартное скачивание браузера (fallback),
        // без File System Access API, чтобы не вылезали системные ошибки вроде
        // «не удалось открыть папку».
        await downloadFileFallback(fileUrl, filename, folderPath);
    } catch (error) {
        console.error('Ошибка скачивания файла:', error);
        showError(error.message || 'Не удалось скачать файл');
    }
}

// Fallback метод скачивания (создает имя файла с путем)
async function downloadFileFallback(fileUrl, filename, folderPath) {
    try {
        if (!fileUrl) {
            throw new Error('URL файла не задан');
        }

        // Предварительно проверяем, что файл вообще существует
        const headResponse = await fetch(fileUrl, { method: 'HEAD' });
        if (!headResponse.ok) {
            let backendMessage = '';
            try {
                const maybeJson = await headResponse.clone().json();
                if (maybeJson && maybeJson.error) {
                    backendMessage = `: ${maybeJson.error}`;
                }
            } catch (e) {
                // Ответ не JSON — игнорируем
            }
            throw new Error(`Файл недоступен (код ${headResponse.status})${backendMessage}`);
        }

        const link = document.createElement('a');
        link.href = fileUrl;
        link.download = `${folderPath.replace(/\//g, '_')}_${filename}`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        showSuccess(`Файл скачан: ${filename}`);
    } catch (error) {
        console.error('Ошибка fallback-скачивания файла:', error);
        showError(error.message || 'Не удалось скачать файл');
    }
}

// Функция для создания slug из строки
function slugify(text) {
    return text
        .toString()
        .toLowerCase()
        .trim()
        .replace(/\s+/g, '-')
        .replace(/[^\w\-]+/g, '')
        .replace(/\-\-+/g, '-')
        .replace(/^-+/, '')
        .replace(/-+$/, '');
}

// Экспорт функций
window.openLesson = openLesson;
window.completeLesson = completeLesson;
window.askQuestionAboutLesson = askQuestionAboutLesson;
window.askQuestionAboutBlock = askQuestionAboutBlock;
window.openImageFullscreen = openImageFullscreen;
window.closeImageFullscreen = closeImageFullscreen;
window.submitTest = submitTest;
window.downloadFileWithStructure = downloadFileWithStructure;
