// ========== DOM References ==========
const urlInput = document.getElementById('url-input');
const fetchBtn = document.getElementById('fetch-btn');
const formatsContainer = document.getElementById('formats-container');
const pendingList = document.getElementById('pending-list');
const downloadingList = document.getElementById('downloading-list');
const completedList = document.getElementById('completed-list');
const pendingCount = document.getElementById('pending-count');
const downloadingCount = document.getElementById('downloading-count');
const completedCount = document.getElementById('completed-count');
const logContainer = document.getElementById('log-container');

// ========== State ==========
let pendingQueue = [];
let downloadingJobs = [];
let completedJobs = [];
let jobEventSources = {};
let activeDownloads = 0;
let MAX_CONCURRENT = 3;
fetch("/api/health").then(r => r.json()).then(d => { MAX_CONCURRENT = d.workers || MAX_CONCURRENT; updateUI(); }).catch(() => {});
let queuedSet = new Set();

// ========== Sample links ==========
document.querySelectorAll('.sample-link').forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        urlInput.value = link.getAttribute('data-url');
        fetchBtn.click();
    });
});

// ========== Event Listeners ==========
fetchBtn.addEventListener('click', () => {
    const url = urlInput.value.replace(/[\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]/g, '').trim();
    if (!url) return alert('Enter a URL');
    try { new URL(url); } catch { return alert('Paste a complete http:// or https:// URL.'); }
    urlInput.value = url;
    fetchFormats(url);
});

urlInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') fetchBtn.click();
});

// ========== Logging ==========
function addLog(message, type = 'info') {
    const entry = document.createElement('div');
    entry.className = `log-entry log-${type}`;
    entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    logContainer.appendChild(entry);
    logContainer.scrollTop = logContainer.scrollHeight;
}

// ========== Format Fetching ==========
async function fetchFormats(url) {
    formatsContainer.replaceChildren();
    fetchBtn.disabled = true; fetchBtn.textContent = 'Fetching…';
    addLog(`⏳ Fetching formats for ${url}...`, 'info');
    try {
        const resp = await fetch('/api/info', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.error || 'Failed to fetch');
        }
        const data = await resp.json();
        addLog(`${data.cache_hit ? '⚡ Cached metadata' : '✅ Fresh metadata'} · ${data.formats.length} formats`, 'success');
        displayFormats(data.formats, data.url || url);
    } catch (err) {
        addLog(`❌ Error: ${err.message}`, 'error');
        const errorBox = document.createElement('div'); errorBox.className = 'error-msg'; errorBox.textContent = err.message; formatsContainer.replaceChildren(errorBox);
    } finally { fetchBtn.disabled = false; fetchBtn.innerHTML = '<span>↗</span> Fetch media'; }
}

// ========== displayFormats ==========
function displayFormats(formats, pageUrl) {
    const grid = document.createElement('div'); grid.className = 'format-grid';
    formats.forEach((f) => {
        const card = document.createElement('div'); card.className = 'format-card';
        const badge = document.createElement('span'); badge.className = 'badge ' + (f.has_video && f.has_audio ? 'both' : f.has_video ? 'video' : f.has_audio ? 'audio' : '');
        badge.textContent = f.has_video && f.has_audio ? '✓ Both' : f.has_video ? 'Video' : f.has_audio ? 'Audio' : 'Unknown';
        const quality = document.createElement('div'); quality.className = 'format-quality'; quality.textContent = f.quality || 'unknown';
        const details = document.createElement('div'); details.className = 'format-details';
        const bits = [f.height ? `${f.height}p` : '', f.fps ? `${f.fps}fps` : '', f.ext || '', f.size ? `${(f.size/1048576).toFixed(1)} MB` : '', f.note || ''].filter(Boolean);
        details.textContent = bits.join(' · ');
        const btn = document.createElement('button'); btn.className = 'format-select-btn'; btn.textContent = 'Add to Queue';
        btn.addEventListener('click', () => addToQueue(pageUrl, String(f.format_id), ''));
        card.append(badge, quality, details, btn); grid.appendChild(card);
    });
    formatsContainer.replaceChildren(grid);
}

// ========== Queue Management ==========
function addToQueue(pageUrl, formatId, videoUrl) {
    const key = `${pageUrl}::${formatId}`;
    if (queuedSet.has(key)) {
        addLog('⚠️ Already in queue', 'error');
        return;
    }
    queuedSet.add(key);

    const job = {
        id: `job-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`,
        pageUrl,
        formatId,
        videoUrl,
        title: pageUrl,
        status: 'pending',
        progress: 0,
        error: null,
        fileUrl: null,
        jobId: null,
    };
    pendingQueue.push(job);
    updateUI();
    addLog(`📥 Added to queue: ${pageUrl}`, 'info');
    processQueue();
}

function processQueue() {
    while (activeDownloads < MAX_CONCURRENT && pendingQueue.length > 0) {
        const job = pendingQueue.shift();
        job.status = 'downloading';
        downloadingJobs.push(job);
        activeDownloads++;
        startDownload(job);
        updateUI();
    }
}

function startDownload(job) {
    addLog(`⏳ Starting download: ${job.title}`, 'info');
    const payload = {
        url: job.pageUrl,
        format_id: job.formatId,
        video_url: job.videoUrl || undefined
    };
    fetch('/api/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            job.status = 'error';
            job.error = data.error || 'Download failed.';
            activeDownloads--;
            addLog(`❌ ${data.error}`, 'error');
            const idx = downloadingJobs.indexOf(job);
            if (idx !== -1) downloadingJobs.splice(idx, 1);
            queuedSet.delete(`${job.pageUrl}::${job.formatId}`);
            updateUI();
            processQueue();
            return;
        }
        job.jobId = data.job_id;
        connectSSE(job);
        updateUI();
    })
    .catch(err => {
        job.status = 'error';
        job.error = err.message;
        activeDownloads--;
        addLog(`❌ Failed to start: ${err.message}`, 'error');
        const idx = downloadingJobs.indexOf(job);
        if (idx !== -1) downloadingJobs.splice(idx, 1);
        queuedSet.delete(`${job.pageUrl}::${job.formatId}`);
        updateUI();
        processQueue();
    });
}

function connectSSE(job) {
    if (jobEventSources[job.jobId]) {
        jobEventSources[job.jobId].close();
    }
    const es = new EventSource(`/api/progress/${job.jobId}`);
    jobEventSources[job.jobId] = es;

    es.onmessage = (e) => {
        try {
            const data = JSON.parse(e.data);
            if (data.error || data.status === 'error') {
                job.status = 'error';
                job.error = data.error || 'Download failed.';
                es.close();
                activeDownloads--;
                addLog(`❌ ${data.error}`, 'error');
                const idx = downloadingJobs.indexOf(job);
                if (idx !== -1) downloadingJobs.splice(idx, 1);
                queuedSet.delete(`${job.pageUrl}::${job.formatId}`);
                updateUI();
                processQueue();
                return;
            }
            if (data.progress !== undefined) {
                job.progress = data.progress;
                updateUI();
            }
            if (data.complete && data.file_url) {
                job.status = 'completed';
                job.fileUrl = data.file_url;
                es.close();
                activeDownloads--;
                addLog(`✅ Download complete: ${job.title}`, 'success');
                const idx = downloadingJobs.indexOf(job);
                if (idx !== -1) downloadingJobs.splice(idx, 1);
                completedJobs.push(job);
                updateUI();
                processQueue();
            }
        } catch (err) {
            console.error('SSE parse error', err);
        }
    };

    es.onerror = () => {
        if (job.status === 'downloading') {
            setTimeout(() => {
                if (es.readyState !== EventSource.CLOSED) {
                    es.close();
                    connectSSE(job);
                }
            }, 3000);
        }
    };
}

// ========== Actions: Delete, Retry, Save ==========
function deleteJob(jobId) {
    let job = pendingQueue.find(j => j.id === jobId);
    if (job) {
        pendingQueue = pendingQueue.filter(j => j.id !== jobId);
        queuedSet.delete(`${job.pageUrl}::${job.formatId}`);
        updateUI();
        addLog(`🗑️ Removed from pending: ${job.title}`, 'info');
        return;
    }
    job = downloadingJobs.find(j => j.id === jobId);
    if (job) {
        if (job.jobId) {
            fetch(`/api/delete/${job.jobId}`, { method: 'DELETE' })
                .catch(err => console.error(err));
        }
        downloadingJobs = downloadingJobs.filter(j => j.id !== jobId);
        queuedSet.delete(`${job.pageUrl}::${job.formatId}`);
        activeDownloads--;
        updateUI();
        addLog(`🗑️ Removed from downloading: ${job.title}`, 'info');
        processQueue();
        return;
    }
    job = completedJobs.find(j => j.id === jobId);
    if (job) {
        if (job.jobId) {
            fetch(`/api/delete/${job.jobId}`, { method: 'DELETE' })
                .catch(err => console.error(err));
        }
        completedJobs = completedJobs.filter(j => j.id !== jobId);
        queuedSet.delete(`${job.pageUrl}::${job.formatId}`);
        updateUI();
        addLog(`🗑️ Removed from completed: ${job.title}`, 'info');
        return;
    }
}

function retryJob(jobId) {
    let job = completedJobs.find(j => j.id === jobId);
    if (!job) return;
    completedJobs = completedJobs.filter(j => j.id !== jobId);
    job.status = 'pending';
    job.progress = 0;
    job.error = null;
    job.fileUrl = null;
    job.jobId = null;
    pendingQueue.push(job);
    updateUI();
    addLog(`↻ Retrying: ${job.title}`, 'info');
    processQueue();
}

function saveFile(fileUrl) {
    const a = document.createElement('a');
    a.href = fileUrl;
    a.download = '';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    addLog('📂 File download started', 'info');
}

// ========== UI Update ==========
function makeJobCard(job, status) {
    const card = document.createElement('div'); card.className = 'download-item';
    const title = document.createElement('div'); title.className = 'title'; title.textContent = job.title || job.pageUrl || 'Media download'; card.appendChild(title);
    if (status === 'downloading') {
        const track = document.createElement('div'); track.className = 'progress-track';
        const bar = document.createElement('div'); bar.className = 'progress-bar'; bar.style.width = `${Math.max(0, Math.min(100, Number(job.progress) || 0))}%`; track.appendChild(bar); card.appendChild(track);
    }
    const label = document.createElement('div'); label.className = 'status';
    label.textContent = status === 'pending' ? 'Pending' : status === 'completed' ? 'Complete' : `${Number(job.progress || 0).toFixed(1)}%`;
    card.appendChild(label);
    if (job.error) { const error = document.createElement('div'); error.className = 'error-text'; error.textContent = job.error; card.appendChild(error); }
    const actions = document.createElement('div'); actions.className = 'actions';
    if (status === 'completed' && job.fileUrl) { const save = document.createElement('button'); save.className = 'save-btn'; save.textContent = 'Save'; save.addEventListener('click', () => saveFile(job.fileUrl)); actions.appendChild(save); }
    const del = document.createElement('button'); del.className = 'delete-btn'; del.textContent = 'Delete'; del.addEventListener('click', () => deleteJob(job.id)); actions.appendChild(del);
    card.appendChild(actions); return card;
}
function updateUI() {
    pendingList.replaceChildren(...pendingQueue.map(j => makeJobCard(j, 'pending')));
    downloadingList.replaceChildren(...downloadingJobs.map(j => makeJobCard(j, 'downloading')));
    completedList.replaceChildren(...completedJobs.map(j => makeJobCard(j, 'completed')));
    pendingCount.textContent = pendingQueue.length;
    downloadingCount.textContent = `${downloadingJobs.length}/${MAX_CONCURRENT}`;
    completedCount.textContent = completedJobs.length;
}

async function restoreJobs() {
    try {
        const response = await fetch('/api/jobs'); if (!response.ok) return;
        const data = await response.json(); MAX_CONCURRENT = data.max_concurrent || MAX_CONCURRENT;
        for (const saved of data.jobs.reverse()) {
            const job = {id:saved.id, pageUrl:saved.url, formatId:saved.format_id, title:saved.url, status:saved.status,
                progress:saved.progress || 0, error:saved.error, fileUrl:saved.status === 'completed' ? `/api/file/${saved.id}` : null};
            if (saved.status === 'pending' || saved.status === 'downloading') { downloadingJobs.push(job); connectSSE(job); }
            else if (saved.status === 'completed') completedJobs.push(job);
        }
        updateUI(); processQueue();
    } catch (error) { addLog(`Could not restore previous jobs: ${error.message}`, 'error'); }
}
restoreJobs();

// ========== Log Export & Clear ==========
document.getElementById('export-log-btn')?.addEventListener('click', () => {
    const entries = logContainer.querySelectorAll('.log-entry');
    const lines = Array.from(entries).map(e => e.textContent);
    const blob = new Blob([lines.join('\n')], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `ump-log-${new Date().toISOString().slice(0,10)}.txt`;
    a.click();
    URL.revokeObjectURL(a.href);
});

document.getElementById('clear-log-btn')?.addEventListener('click', () => {
    logContainer.innerHTML = '';
});

// ========== Initial Log ==========
addLog('🔄 Ready – enter a URL and click Fetch', 'info');