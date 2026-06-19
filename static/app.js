// ----------------------------------------------------
// SubTrans.ai Frontend Application Logic
// ----------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const keyStatusBadge = document.getElementById('key-status-badge');
    const notifyPermBtn = document.getElementById('notify-perm-btn');
    const dirPathInput = document.getElementById('dir-path-input');
    const scanBtn = document.getElementById('scan-btn');
    const fileCountLabel = document.getElementById('file-count-label');
    const filesListBody = document.getElementById('files-list-body');
    
    // Modal Elements
    const progressModal = document.getElementById('progress-modal');
    const modalTitle = document.getElementById('modal-title');
    const modalSubtitle = document.getElementById('modal-subtitle');
    const modalCloseBtn = document.getElementById('modal-close-btn');
    const modalActionBtn = document.getElementById('modal-action-btn');
    const progressStepText = document.getElementById('progress-step-text');
    const progressPercentText = document.getElementById('progress-percent-text');
    const progressBarFill = document.getElementById('progress-bar-fill');
    const terminalLogs = document.getElementById('terminal-logs');
    const statusSummaryText = document.getElementById('status-summary-text');
    
    const toastArea = document.getElementById('toast-area');

    // Providers and Models
    const providers = [
        { value: 'gemini', text: 'Gemini' },
        { value: 'openrouter', text: 'OpenRouter' }
    ];

    // Gemini model presets (shown when provider == gemini)
    const geminiPrimaryModels = [
        { value: 'gemini-3.5-flash', text: 'Gemini 3.5 Flash' },
        { value: 'gemini-2.5-flash', text: 'Gemini 2.5 Flash' },
        { value: 'gemini-2.0-flash', text: 'Gemini 2.0 Flash' },
        { value: 'gemini-1.5-flash', text: 'Gemini 1.5 Flash' },
        { value: 'gemini-3.1-pro-preview', text: 'Gemini 3.1 Pro (Preview)' },
        { value: 'gemini-2.5-pro', text: 'Gemini 2.5 Pro' },
        { value: 'gemini-1.5-pro', text: 'Gemini 1.5 Pro' }
    ];

    const geminiFallbackModels = [
        { value: 'gemini-3.1-pro-preview', text: 'Gemini 3.1 Pro (Preview)' },
        { value: 'gemini-2.5-pro', text: 'Gemini 2.5 Pro' },
        { value: 'gemini-3.5-flash', text: 'Gemini 3.5 Flash' },
        { value: 'gemini-2.5-flash', text: 'Gemini 2.5 Flash' },
        { value: 'gemini-1.5-pro', text: 'Gemini 1.5 Pro' }
    ];

    // Helper to create a provider select element
    function createProviderSelect(defaultValue = 'gemini') {
        const sel = document.createElement('select');
        sel.className = 'provider-select';
        providers.forEach(p => {
            const o = document.createElement('option');
            o.value = p.value;
            o.textContent = p.text;
            sel.appendChild(o);
        });
        sel.value = defaultValue;
        return sel;
    }

    // Helper to create a model control (select for Gemini, input for OpenRouter)
    function createModelControl(provider, defaultModel = '') {
        if (provider === 'gemini') {
            const s = document.createElement('select');
            s.className = 'model-select';
            geminiPrimaryModels.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m.value;
                opt.textContent = m.text;
                s.appendChild(opt);
            });
            if (defaultModel) s.value = defaultModel;
            return s;
        } else {
            const input = document.createElement('input');
            input.type = 'text';
            input.className = 'model-input';
            input.placeholder = 'OpenRouter model (e.g. gpt-4o-mini)';
            if (defaultModel) input.value = defaultModel;
            return input;
        }
    }

    // Initialization
    checkApiKeyStatus();
    loadDefaultWorkspace();
    setupNotificationButton();

    // Event Listeners
    scanBtn.addEventListener('click', () => {
        const path = dirPathInput.value.trim();
        if (path) {
            scanDirectory(path);
        } else {
            showToast('경로를 입력해 주세요.', 'error');
        }
    });

    modalCloseBtn.addEventListener('click', closeModal);
    modalActionBtn.addEventListener('click', closeModal);

    // Functions

    // API Key 상태 체크
    async function checkApiKeyStatus() {
        try {
            const res = await fetch('/api/key_status');
            const data = await res.json();

            keyStatusBadge.className = 'status-badge';
            keyStatusBadge.classList.remove('status-configured','status-missing','status-loading');
            const parts = [];
            if (data.gemini) parts.push('Gemini ✓');
            if (data.openrouter) parts.push('OpenRouter ✓');
            if (parts.length) {
                keyStatusBadge.classList.add('status-configured');
                keyStatusBadge.querySelector('.badge-text').textContent = parts.join(' | ');
            } else {
                keyStatusBadge.classList.add('status-missing');
                keyStatusBadge.querySelector('.badge-text').textContent = 'API 키 유실 (.env)';
                showToast('지원되는 모델 제공자(Gemini 또는 OpenRouter) API 키가 설정되지 않았습니다. .env 파일을 작성해 주세요!', 'error');
            }
        } catch (e) {
            console.error('API Key check error:', e);
            keyStatusBadge.className = 'status-badge status-missing';
            keyStatusBadge.querySelector('.badge-text').textContent = '서버 통신 실패';
        }
    }

    // 기본 작업 폴더 정보 불러오기
    async function loadDefaultWorkspace() {
        try {
            const res = await fetch('/api/default_directory');
            if (res.ok) {
                const data = await res.json();
                if (data.directory) {
                    dirPathInput.value = data.directory;
                    // 자동으로 한 번 스캔
                    scanDirectory(data.directory);
                }
            }
        } catch (e) {
            console.error('Failed to load default workspace:', e);
        }
    }

    // 데스크톱 알림 버튼 초기 설정
    function setupNotificationButton() {
        if (!("Notification" in window)) {
            notifyPermBtn.style.display = 'none';
            return;
        }

        if (Notification.permission === 'granted') {
            notifyPermBtn.style.display = 'none';
        } else {
            notifyPermBtn.addEventListener('click', async () => {
                const permission = await Notification.requestPermission();
                if (permission === 'granted') {
                    showToast('알림 권한이 허용되었습니다!', 'success');
                    notifyPermBtn.style.display = 'none';
                }
            });
        }
    }

    // 데스크톱 알림 트리거
    function triggerNotification(title, message) {
        if (Notification.permission === 'granted') {
            new Notification(title, {
                body: message,
                icon: '/static/favicon.ico' // 브라우저 아이콘 설정
            });
        }
    }

    // 디렉토리 스캔 API 호출
    async function scanDirectory(directory) {
        scanBtn.disabled = true;
        scanBtn.querySelector('span').textContent = '스캔 중...';
        
        try {
            const res = await fetch(`/api/scan?directory=${encodeURIComponent(directory)}`);
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || '폴더 스캔 실패');
            }
            
            const data = await res.json();
            renderFilesList(data.files);
            showToast('디렉토리가 성공적으로 스캔되었습니다.', 'success');
        } catch (e) {
            console.error(e);
            showToast(e.message, 'error');
            filesListBody.innerHTML = `
                <tr>
                    <td colspan="6" class="empty-state">
                        <svg xmlns="http://www.w3.org/2000/svg" height="40px" viewBox="0 -960 960 960" width="40px" fill="var(--color-error)"><path d="m256-200-56-56 224-224-224-224 56-56 224 224 224-224 56 56-224 224 224 224-56 56-224-224-224 224Z"/></svg>
                        <p style="color: var(--color-error)">오류: ${e.message}</p>
                    </td>
                </tr>
            `;
            fileCountLabel.textContent = '0개 발견';
        } finally {
            scanBtn.disabled = false;
            scanBtn.querySelector('span').textContent = '폴더 스캔';
        }
    }

    // 파일 목록 테이블 렌더링
    function renderFilesList(files) {
        if (!files || files.length === 0) {
            filesListBody.innerHTML = `
                <tr>
                    <td colspan="6" class="empty-state">
                        <svg xmlns="http://www.w3.org/2000/svg" height="40px" viewBox="0 -960 960 960" width="40px" fill="currentColor"><path d="M140-160q-24 0-42-18t-18-42v-520q0-24 18-42t42-18h300l80 80h300q24 0 42 18t18 42v520q0 24-18 42t-42 18H140Zm0-80h680v-400H480l-80-80H140v480Zm0 0v-480 480Z"/></svg>
                        <p>디렉토리 내에 스캔 가능한 영어 자막(.srt) 파일이 없습니다.</p>
                    </td>
                </tr>
            `;
            fileCountLabel.textContent = '0개 발견';
            return;
        }

        fileCountLabel.textContent = `${files.length}개 발견`;
        filesListBody.innerHTML = '';

        files.forEach((file, index) => {
            const tr = document.createElement('tr');
            
            // 파일 크기 포맷팅 (KB)
            const sizeKB = (file.size_bytes / 1024).toFixed(1);
            
            // Primary Provider + Model Control
            const primProviderSelect = createProviderSelect('gemini');
            const primModelControl = createModelControl(primProviderSelect.value);

            // Fallback Provider + Model Control
            const fbProviderSelect = createProviderSelect('gemini');
            const fbModelControl = createModelControl(fbProviderSelect.value);


            // Action Button
            const actionBtn = document.createElement('button');
            actionBtn.className = 'btn-table-action';
            actionBtn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" height="18px" viewBox="0 -960 960 960" width="18px" fill="currentColor"><path d="M380-380h200v-200H380v200Zm100 300q-79 0-149-30t-122.5-82.5Q156-345 126-415T96-560q0-80 30-150t82.5-122.5Q281-904 351-934t149-30q80 0 150 30t122.5 82.5Q804-780 834-710t30 150q0 79-30 149t-82.5 122.5Q679-206 609-176t-149 30Zm0-80q162 0 276-114t114-276q0-162-114-276T480-880q-162 0-276 114T90-560q0 162 114 276t276 114Zm0-300Z"/></svg>
                <span>번역</span>
            `;
            
            actionBtn.addEventListener('click', () => {
                // gather primary provider/model
                const primProvider = primProviderSelect.value;
                const fbProvider = fbProviderSelect.value;
                let primModel = '';
                let fbModel = '';
                const primControl = primWrapper.querySelector('.model-select, .model-input');
                const fbControl = fbWrapper.querySelector('.model-select, .model-input');
                if (primControl) primModel = primControl.value || primControl.textContent || '';
                if (fbControl) fbModel = fbControl.value || fbControl.textContent || '';

                startTranslation(file.path, file.filename, primModel, fbModel, primProvider, fbProvider);
            });

            // Appending Cells
            const tdName = document.createElement('td');
            tdName.textContent = file.filename;
            tdName.style.fontWeight = '500';
            
            const tdSize = document.createElement('td');
            tdSize.className = 'text-right';
            tdSize.textContent = `${sizeKB} KB`;
            
            const tdBlocks = document.createElement('td');
            tdBlocks.className = 'text-right';
            tdBlocks.innerHTML = `${file.block_count} <span class="badge-info" style="margin-left:5px;">${file.estimated_chunks} 청크</span>`;
            
            const tdPrim = document.createElement('td');
            // provider select + model control container
            const primWrapper = document.createElement('div');
            primWrapper.style.display = 'flex';
            primWrapper.style.gap = '6px';
            primWrapper.appendChild(primProviderSelect);
            primWrapper.appendChild(primModelControl);
            tdPrim.appendChild(primWrapper);

            const tdFb = document.createElement('td');
            const fbWrapper = document.createElement('div');
            fbWrapper.style.display = 'flex';
            fbWrapper.style.gap = '6px';
            fbWrapper.appendChild(fbProviderSelect);
            fbWrapper.appendChild(fbModelControl);
            tdFb.appendChild(fbWrapper);

            // After wrappers exist, attach provider change listeners to swap inner control
            primProviderSelect.addEventListener('change', () => {
                const newControl = createModelControl(primProviderSelect.value);
                const old = primWrapper.querySelector('.model-select, .model-input');
                if (old) primWrapper.replaceChild(newControl, old);
                else primWrapper.appendChild(newControl);
            });
            fbProviderSelect.addEventListener('change', () => {
                const newControl = createModelControl(fbProviderSelect.value);
                const old = fbWrapper.querySelector('.model-select, .model-input');
                if (old) fbWrapper.replaceChild(newControl, old);
                else fbWrapper.appendChild(newControl);
            });

            const tdAction = document.createElement('td');
            tdAction.className = 'text-center';
            tdAction.appendChild(actionBtn);

            tr.appendChild(tdName);
            tr.appendChild(tdSize);
            tr.appendChild(tdBlocks);
            tr.appendChild(tdPrim);
            tr.appendChild(tdFb);
            tr.appendChild(tdAction);

            filesListBody.appendChild(tr);
        });
    }

    // 번역 실행 및 SSE 스트림 처리
    async function startTranslation(filePath, filename, primaryModel, fallbackModel) {
        // 모달 상태 초기화
        modalTitle.textContent = '자막 번역 실행 중';
        modalSubtitle.textContent = filename;
        progressStepText.textContent = '서버 연결 중...';
        progressPercentText.textContent = '0%';
        progressBarFill.style.width = '0%';
        terminalLogs.innerHTML = `<div class="log-line info">[준비] '${filename}' 번역 세션이 시작되었습니다.</div>`;
        statusSummaryText.textContent = '서버 응답 대기 중';
        
        modalCloseBtn.disabled = true;
        modalActionBtn.disabled = true;
        progressModal.classList.add('active');

        try {
                    const response = await fetch('/api/translate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        file_path: filePath,
                        primary_model: primaryModel,
                        fallback_model: fallbackModel,
                        primary_provider: primaryProvider,
                        fallback_provider: fallbackProvider
                    })
                });

            if (!response.ok) {
                throw new Error('번역 요청 전송 실패');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';

                while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');

                // 마지막 줄이 미완성일 수 있으므로 버퍼에 보관
                buffer = lines.pop();

                for (const line of lines) {
                    if (line.trim().startsWith('data: ')) {
                        try {
                            const rawData = line.trim().substring(6);
                            const event = JSON.parse(rawData);
                            processTranslationEvent(event);
                        } catch (e) {
                            console.error('SSE 파싱 에러:', e, line);
                        }
                    }
                }
            }
        } catch (e) {
            console.error(e);
            appendLog('error', `오류 발생: ${e.message}`);
            updateProgress(0, '에러 발생', 'error');
            showToast('번역 요청을 처리하지 못했습니다.', 'error');
        }
    }

    // SSE 이벤트 수신에 따른 화면 상태 업데이트
    function processTranslationEvent(event) {
        const { step, status, message, percent } = event;
        
        // 1. 터미널 로그 추가
        let logClass = 'info';
        if (status === 'success' || status === 'success_chunk') {
            logClass = 'success';
        } else if (status === 'error') {
            logClass = 'error';
        } else if (status === 'warning') {
            logClass = 'warning';
        } else if (status === 'running') {
            logClass = 'running';
        }
        
        appendLog(logClass, message);

        // 2. 진행률 바 및 텍스트 업데이트
        let stepLabel = '진행 중';
        if (step === 'init') stepLabel = '초기 준비 단계';
        else if (step === 'pre_process') stepLabel = '번역 전처리 (pre_srt)';
        else if (step === 'chunking') stepLabel = '자막 청크 분할';
        else if (step === 'translate') {
            // Generic translation label — provider/model info is shown in the event message
            stepLabel = `자막 번역 (청크 ${event.chunk}/${event.total_chunks})`;
        }
        else if (step === 'save') stepLabel = '한글 자막 임시 저장';
        else if (step === 'verify') stepLabel = '자막 최종 정합성 검증';
        else if (step === 'post_process') stepLabel = '자막 후처리 (post_srt)';
        else if (step === 'complete') stepLabel = '작업 완료';

        updateProgress(percent, stepLabel, status);

        // 3. 작업 성공/실패 시 모달 하단 요약 및 버튼 활성화
        if (status === 'error') {
            statusSummaryText.innerHTML = `<span style="color: var(--color-error)">❌ 작업 실패</span>`;
            modalTitle.textContent = '자막 번역 실패';
            modalCloseBtn.disabled = false;
            modalActionBtn.disabled = false;
            modalActionBtn.textContent = '닫기';
            modalActionBtn.className = 'btn-primary';
            modalActionBtn.style.background = 'var(--color-error)';
            modalActionBtn.style.boxShadow = 'none';
            triggerNotification('SubTrans.ai 번역 실패', `자막 번역 도중 오류가 발생했습니다: ${message}`);
            showToast('번역 처리에 실패했습니다.', 'error');
        } else if (step === 'complete' && status === 'success') {
            statusSummaryText.innerHTML = `<span style="color: var(--color-success)">✅ 작업 완료</span>`;
            modalTitle.textContent = '자막 번역 완료';
            modalCloseBtn.disabled = false;
            modalActionBtn.disabled = false;
            modalActionBtn.textContent = '확인';
            modalActionBtn.className = 'btn-primary';
            modalActionBtn.style.background = 'var(--accent-gradient)';
            modalActionBtn.style.boxShadow = '0 4px 15px var(--accent-glow)';
            triggerNotification('SubTrans.ai 번역 완료', '한글 자막 번역 및 후처리가 성공적으로 끝났습니다!');
            showToast('자막 번역이 완료되었습니다!', 'success');
            
            // 완료 후 목록 리프레시
            const currentPath = dirPathInput.value.trim();
            if (currentPath) {
                scanDirectory(currentPath);
            }
        }
    }

    // 터미널 로그 추가 헬퍼
    function appendLog(className, text) {
        const div = document.createElement('div');
        div.className = `log-line ${className}`;
        div.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
        terminalLogs.appendChild(div);
        
        // 자동 스크롤
        terminalLogs.scrollTop = terminalLogs.scrollHeight;
    }

    // 게이지 바 업데이트 헬퍼
    function updateProgress(percent, stepLabel, status) {
        progressStepText.textContent = stepLabel;
        progressPercentText.textContent = `${percent}%`;
        progressBarFill.style.width = `${percent}%`;
        statusSummaryText.textContent = `${stepLabel} 진행 중 (${percent}%)`;
        
        if (status === 'error') {
            progressBarFill.style.background = 'var(--color-error)';
            progressBarFill.style.boxShadow = 'none';
            progressPercentText.style.color = 'var(--color-error)';
        } else {
            progressBarFill.style.background = 'var(--accent-gradient)';
            progressBarFill.style.boxShadow = '0 0 10px rgba(6, 182, 212, 0.5)';
            progressPercentText.style.color = 'var(--accent-secondary)';
        }
    }

    // 모달 닫기
    function closeModal() {
        progressModal.classList.remove('active');
    }

    // 토스트 팝업 띄우기
    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        let icon = '';
        if (type === 'success') {
            icon = `<svg xmlns="http://www.w3.org/2000/svg" height="20px" viewBox="0 -960 960 960" width="20px" fill="currentColor"><path d="m382-320 338-338-56-56-282 282-142-142-56 56 198 198Zm98 240q-79 0-149-30t-122.5-82.5Q156-245 126-315T96-470q0-80 30-150t82.5-122.5Q281-806 351-836t149-30q80 0 150 30t122.5 82.5Q804-620 834-550t30 150q0 79-30 149t-82.5 122.5Q679-146 609-116t-149 30Zm0-80q162 0 276-114t114-276q0-162-114-276T480-800q-162 0-276 114T90-470q0 162 114 276t276 114Zm0-330Z"/></svg>`;
        } else if (type === 'error') {
            icon = `<svg xmlns="http://www.w3.org/2000/svg" height="20px" viewBox="0 -960 960 960" width="20px" fill="currentColor"><path d="m256-200-56-56 224-224-224-224 56-56 224 224 224-224 56 56-224 224 224 224-56 56-224-224-224 224ZM480-80q-79 0-149-30t-122.5-82.5Q156-245 126-315T96-470q0-80 30-150t82.5-122.5Q281-806 351-836t149-30q80 0 150 30t122.5 82.5Q804-620 834-550t30 150q0 79-30 149t-82.5 122.5Q679-146 609-116t-149 30Zm0-80q162 0 276-114t114-276q0-162-114-276T480-800q-162 0-276 114T90-470q0 162 114 276t276 114Zm0-330Z"/></svg>`;
        } else {
            icon = `<svg xmlns="http://www.w3.org/2000/svg" height="20px" viewBox="0 -960 960 960" width="20px" fill="currentColor"><path d="M440-280h80v-240h-80v240Zm40-320q17 0 28.5-11.5T520-640q0-17-11.5-28.5T480-680q-17 0-28.5 11.5T440-640q0 17 11.5 28.5T480-600Zm0 520q-79 0-149-30t-122.5-82.5Q156-245 126-315T96-470q0-80 30-150t82.5-122.5Q281-806 351-836t149-30q80 0 150 30t122.5 82.5Q804-620 834-550t30 150q0 79-30 149t-82.5 122.5Q679-146 609-116t-149 30Zm0-80q162 0 276-114t114-276q0-162-114-276T480-800q-162 0-276 114T90-470q0 162 114 276t276 114Zm0-330Z"/></svg>`;
        }

        toast.innerHTML = `
            <div class="toast-icon">${icon}</div>
            <div class="toast-content">${message}</div>
        `;
        
        toastArea.appendChild(toast);
        
        // 4초 후 삭제
        setTimeout(() => {
            toast.classList.add('removing');
            toast.addEventListener('transitionend', () => {
                toast.remove();
            });
        }, 4000);
    }
});
