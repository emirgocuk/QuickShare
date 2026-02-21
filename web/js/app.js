// State
let selectedFiles = [];

// Navigation Logic
function switchTab(tabId) {
    // Update nav buttons
    document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
    const tabBtn = document.getElementById(`tab-${tabId}`);
    if (tabBtn) tabBtn.classList.add('active');

    // Update views
    document.querySelectorAll('.page-view').forEach(view => {
        view.classList.remove('active');
        view.classList.add('hidden');
    });

    const targetView = document.getElementById(`view-${tabId}`);
    if (targetView) {
        targetView.classList.remove('hidden');
        // Using a tiny timeout to allow display:block to apply before adding active for animation
        setTimeout(() => {
            targetView.classList.add('active');
        }, 10);
    }

    // Auto-load settings when switching to settings tab
    if (tabId === 'settings') {
        apiLoadSettings();
    }
}

// Drag and Drop (Visuals only, actual dropping needs Python hook usually, 
// but we can catch HTML drop and send paths if running locally in WebView2)
const dropZone = document.getElementById('drop-zone');

if (dropZone) {
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('border-primary', 'bg-primary/5');
    });

    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropZone.classList.remove('border-primary', 'bg-primary/5');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('border-primary', 'bg-primary/5');

        const files = [];
        if (e.dataTransfer.files) {
            for (let i = 0; i < e.dataTransfer.files.length; i++) {
                if (e.dataTransfer.files[i].path) {
                    files.push(e.dataTransfer.files[i].path);
                }
            }
        }

        if (files.length > 0 && window.pywebview) {
            window.pywebview.api.add_files_from_drop(files).then(updateFileList);
        }
    });
}

// Enter key on receive input
const receiveInput = document.getElementById('receive-input');
if (receiveInput) {
    receiveInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            apiConnect();
        }
    });
}

// API Calls (Bridged to Python)
function apiSelectFiles() {
    if (window.pywebview) {
        window.pywebview.api.select_files().then(updateFileList);
    } else {
        console.log("Not running in PyWebView");
        updateFileList([{ name: 'test_file.txt', size: '15 MB', status: 'Hazır' }]);
    }
}

function apiSelectFolder() {
    if (window.pywebview) {
        window.pywebview.api.select_folder().then(updateFileList);
    }
}

function apiClearFiles() {
    if (window.pywebview) {
        window.pywebview.api.clear_files().then(updateFileList);
    } else {
        updateFileList([]); // Mock
    }
}

function apiStartCloudShare() {
    if (window.pywebview) {
        window.pywebview.api.start_cloud_share().then(handleShareResponse);
    }
}

function apiStartDirectShare() {
    if (window.pywebview) {
        window.pywebview.api.start_direct_share().then(handleShareResponse);
    } else {
        handleShareResponse({ success: true, type: 'p2p', code: '482910' }); // Mock
    }
}

function apiStopShare() {
    if (window.pywebview) {
        window.pywebview.api.stop_share().then(() => {
            document.getElementById('transfer-status').classList.add('hidden');
        });
    } else {
        document.getElementById('transfer-status').classList.add('hidden');
    }
}

// --- Receive / Connect ---
function apiConnect() {
    const input = document.getElementById('receive-input');
    const codeOrUrl = input ? input.value.trim() : '';

    if (!codeOrUrl) {
        alert('Lütfen bir kod veya link girin.');
        return;
    }

    if (window.pywebview) {
        window.pywebview.api.connect_to_peer(codeOrUrl).then(handleConnectResponse);
    } else {
        // Mock
        handleConnectResponse({
            success: true,
            type: 'p2p',
            code: codeOrUrl,
            message: `Mock P2P bağlantısı: ${codeOrUrl}`
        });
    }
}

function handleConnectResponse(response) {
    if (!response || !response.success) {
        alert(response ? response.error : 'Bilinmeyen hata');
        return;
    }

    const contentArea = document.querySelector('#view-receive .flex-1.border');
    if (!contentArea) return;

    if (response.type === 'cloud' && response.files) {
        // Show file list from cloud
        let html = '<div class="w-full p-4 space-y-2">';
        html += `<h3 class="text-lg font-bold text-white mb-4"><i class="fa-solid fa-cloud text-primary mr-2"></i>${response.files.length} dosya bulundu</h3>`;
        response.files.forEach(f => {
            html += `
                <div class="bg-background border border-border rounded-lg p-3 flex justify-between items-center">
                    <div class="flex items-center gap-3">
                        <i class="fa-solid fa-file-lines text-blue-400"></i>
                        <span class="text-white text-sm font-medium">${f.name}</span>
                    </div>
                    <span class="text-textMuted text-sm">${f.size}</span>
                </div>`;
        });
        html += '</div>';
        contentArea.innerHTML = html;
    } else if (response.type === 'p2p') {
        contentArea.innerHTML = `
            <div class="text-center">
                <div class="animate-pulse w-4 h-4 bg-warning rounded-full mx-auto mb-4"></div>
                <p class="text-lg text-white font-medium">${response.message || 'P2P bağlantısı kuruluyor...'}</p>
                <p class="text-textMuted mt-2">Oda: ${response.code}</p>
            </div>`;
    }
}

// --- Settings ---
function apiLoadSettings() {
    if (!window.pywebview) return;

    window.pywebview.api.get_settings().then(settings => {
        if (!settings) return;
        const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
        const setChecked = (id, val) => { const el = document.getElementById(id); if (el) el.checked = !!val; };

        setVal('setting-signaling-url', settings.signaling_url);
        setVal('setting-cf-token', settings.cf_tunnel_token);
        setVal('setting-cf-url', settings.cf_tunnel_url);
        setVal('setting-duckdns-domain', settings.duckdns_domain);
        setVal('setting-duckdns-token', settings.duckdns_token);
        setChecked('setting-use-duckdns', settings.use_duckdns);
    });
}

function apiSaveSettings() {
    if (!window.pywebview) {
        alert('PyWebView bağlantısı bulunamadı.');
        return;
    }

    const getVal = (id) => { const el = document.getElementById(id); return el ? el.value : ''; };
    const getChecked = (id) => { const el = document.getElementById(id); return el ? el.checked : false; };

    const settings = {
        signaling_url: getVal('setting-signaling-url'),
        cf_tunnel_token: getVal('setting-cf-token'),
        cf_tunnel_url: getVal('setting-cf-url'),
        duckdns_domain: getVal('setting-duckdns-domain'),
        duckdns_token: getVal('setting-duckdns-token'),
        use_duckdns: getChecked('setting-use-duckdns')
    };

    window.pywebview.api.save_settings(settings).then(response => {
        if (response && response.success) {
            alert('✅ ' + response.message);
        } else {
            alert('❌ ' + (response ? response.error : 'Kayıt hatası'));
        }
    });
}

// UI Updaters (Called by Python or Promises)
function updateFileList(files) {
    const listDiv = document.getElementById('file-list');
    const emptyState = document.getElementById('empty-state');

    if (!listDiv || !emptyState) return;

    if (!files || files.length === 0) {
        emptyState.style.display = 'block';
        // Remove file items
        Array.from(listDiv.children).forEach(child => {
            if (child.id !== 'empty-state') child.remove();
        });
        return;
    }

    emptyState.style.display = 'none';

    // Clear old items 
    Array.from(listDiv.children).forEach(child => {
        if (child.id !== 'empty-state') child.remove();
    });

    files.forEach((file, index) => {
        const item = document.createElement('div');
        item.className = 'file-item bg-background border border-border rounded-lg p-3 flex justify-between items-center';
        item.style.animationDelay = `${index * 0.05}s`;

        let icon = file.is_folder ? '<i class="fa-solid fa-folder text-purple-400"></i>' : '<i class="fa-solid fa-file-lines text-blue-400"></i>';

        item.innerHTML = `
            <div class="flex items-center gap-3 truncate">
                <div class="w-8 h-8 rounded bg-surface flex items-center justify-center border border-border">
                    ${icon}
                </div>
                <span class="text-white truncate font-medium text-sm">${file.name}</span>
            </div>
            <div class="flex items-center gap-4 text-sm whitespace-nowrap">
                <span class="text-textMuted">${file.size}</span>
                <span class="px-2 py-1 rounded bg-surface text-textMuted border border-border min-w-[80px] text-center" id="status-${index}">
                    ${file.status || 'Bekliyor'}
                </span>
            </div>
        `;
        listDiv.appendChild(item);
    });
}

function handleShareResponse(response) {
    if (!response || !response.success) {
        alert(response.error || "Bir hata oluştu.");
        return;
    }

    const statusPanel = document.getElementById('transfer-status');
    const codeInput = document.getElementById('share-code');
    const title = document.getElementById('transfer-title');

    statusPanel.classList.remove('hidden');

    if (response.type === 'p2p') {
        title.innerHTML = '<div class="animate-pulse w-3 h-3 bg-warning rounded-full"></div> P2P Oda Kodu (Alıcıya İletin)';
        codeInput.value = response.code;
        // Make it easy to read
        codeInput.classList.remove('text-sm');
        codeInput.classList.add('text-3xl', 'tracking-widest');
    } else {
        title.innerHTML = '<div class="animate-pulse w-3 h-3 bg-primary rounded-full"></div> Web Linki Hazır';
        codeInput.value = response.url;
        codeInput.classList.remove('text-3xl', 'tracking-widest');
        codeInput.classList.add('text-sm');
    }
}

// Global hook for Python to update specific file progress
window.updateFileProgress = (index, statusText, progressPercent) => {
    const statusBadge = document.getElementById(`status-${index}`);
    if (statusBadge) {
        statusBadge.innerText = statusText;
        if (progressPercent === 100) {
            statusBadge.classList.replace('text-textMuted', 'text-secondary');
            statusBadge.classList.replace('bg-surface', 'bg-secondary/10');
            statusBadge.classList.replace('border-border', 'border-secondary/20');
        }
    }
};

window.updateStats = (speed, sent) => {
    document.getElementById('transfer-speed').innerText = `Hız: ${speed}`;
    document.getElementById('transfer-sent').innerText = `Gönderilen: ${sent}`;
}

