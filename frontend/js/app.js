/* ============================================
   CV ANALYZER — APP.JS
   Connects to local FastAPI at http://localhost:8000
   ============================================ */

const API_BASE = 'http://localhost:8000';

// ─── DOM REFS ────────────────────────────────
const form           = document.getElementById('cv-form');
const dropZone       = document.getElementById('drop-zone');
const fileInput      = document.getElementById('file-input');
const fileSelected   = document.getElementById('file-selected');
const fileNameDisp   = document.getElementById('file-name-display');
const fileSizeDisp   = document.getElementById('file-size-display');
const fileRemoveBtn  = document.getElementById('file-remove');
const topKInput      = document.getElementById('top-k');
const topKMinus      = document.getElementById('top-k-minus');
const topKPlus       = document.getElementById('top-k-plus');
const thresholdInput = document.getElementById('threshold');
const thresholdDisp  = document.getElementById('threshold-display');
const analyzeBtn     = document.getElementById('analyze-btn');
const formError      = document.getElementById('form-error');

const loadingOverlay = document.getElementById('loading-overlay');
const loadingSub     = document.getElementById('loading-sub');
const progressBar    = document.getElementById('progress-bar');

const uploadSection  = document.getElementById('upload-section');
const resultsSection = document.getElementById('results-section');
const backBtn        = document.getElementById('back-btn');
const navResults     = document.getElementById('nav-results');
const themeToggles = document.querySelectorAll('.theme-toggle');

let selectedFile = null;

// ─── FILE HANDLING ───────────────────────────

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(2) + ' MB';
}

function showFileSelected(file) {
  selectedFile = file;
  fileSelected.style.display = 'flex';
  dropZone.style.display = 'none';
  fileNameDisp.textContent = file.name;
  fileSizeDisp.textContent = formatBytes(file.size);
  analyzeBtn.disabled = false;
}

function clearFileSelection() {
  selectedFile = null;
  fileSelected.style.display = 'none';
  dropZone.style.display = 'flex';
  fileInput.value = '';
  analyzeBtn.disabled = true;
}

fileInput.addEventListener('change', e => {
  if (e.target.files[0]) showFileSelected(e.target.files[0]);
});

fileRemoveBtn.addEventListener('click', clearFileSelection);

// Drag & drop
dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) {
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf','docx','doc','txt'].includes(ext)) {
      showError('Unsupported file type. Please use PDF, DOCX, DOC, or TXT.');
      return;
    }
    showFileSelected(file);
  }
});

// Click on drop zone opens file picker
dropZone.addEventListener('click', e => {
  if (e.target !== document.querySelector('.file-label')) {
    fileInput.click();
  }
});

// ─── CONTROLS ────────────────────────────────

topKMinus.addEventListener('click', () => {
  const v = parseInt(topKInput.value);
  if (v > 1) topKInput.value = v - 1;
});
topKPlus.addEventListener('click', () => {
  const v = parseInt(topKInput.value);
  if (v < 20) topKInput.value = v + 1;
});

if (thresholdInput && thresholdDisp) {
  thresholdInput.addEventListener('input', () => {
    thresholdDisp.textContent = parseFloat(thresholdInput.value).toFixed(2);
    updateSliderBackground();
  });
  updateSliderBackground();
}

function updateSliderBackground() {
  if (!thresholdInput || !thresholdInput.min || !thresholdInput.max) return;
  const min = parseFloat(thresholdInput.min);
  const max = parseFloat(thresholdInput.max);
  const val = parseFloat(thresholdInput.value);
  const pct = ((val - min) / (max - min) * 100).toFixed(1) + '%';
  thresholdInput.style.setProperty('--pct', pct);
}

// ─── ERROR DISPLAY ───────────────────────────

function showError(msg) {
  formError.textContent = msg;
  formError.style.display = 'block';
}
function clearError() {
  formError.style.display = 'none';
  formError.textContent = '';
}

// ─── LOADING STATES ──────────────────────────

const loadingMessages = [
  'Extracting text and detecting language…',
  'Embedding your CV with semantic model…',
  'Matching against job profiles…',
  'Scoring requirements and tools…',
  'Building your career report…',
];

let loadingInterval = null;
let progressInterval = null;

function startLoading() {
  loadingOverlay.style.display = 'flex';
  let msgIdx = 0;
  let prog = 0;

  loadingSub.textContent = loadingMessages[0];

  loadingInterval = setInterval(() => {
    msgIdx = (msgIdx + 1) % loadingMessages.length;
    loadingSub.style.opacity = '0';
    setTimeout(() => {
      loadingSub.textContent = loadingMessages[msgIdx];
      loadingSub.style.opacity = '1';
    }, 200);
  }, 2800);

  progressInterval = setInterval(() => {
    prog = Math.min(prog + Math.random() * 3, 90);
    progressBar.style.width = prog + '%';
  }, 200);
}

function stopLoading() {
  clearInterval(loadingInterval);
  clearInterval(progressInterval);
  progressBar.style.width = '100%';
  setTimeout(() => {
    loadingOverlay.style.display = 'none';
    progressBar.style.width = '0%';
  }, 400);
}

// ─── FORM SUBMIT ─────────────────────────────

form.addEventListener('submit', async e => {
  e.preventDefault();
  clearError();

  if (!selectedFile) {
    showError('Please upload your CV before analyzing.');
    return;
  }

  const formData = new FormData();
  formData.append('file', selectedFile);
  formData.append('top_k', topKInput.value);
  formData.append('threshold', thresholdInput ? thresholdInput.value : '0.30');

  startLoading();
  analyzeBtn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/analyze-cv`, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Unknown error from server.' }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    stopLoading();
    renderResults(data);

  } catch (err) {
    stopLoading();
    analyzeBtn.disabled = false;

    if (err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
      showError('Cannot reach the API. Make sure your local server is running at ' + API_BASE);
    } else {
      showError('Error: ' + err.message);
    }
  }
});

// ─── NAVIGATION ──────────────────────────────

backBtn.addEventListener('click', () => {
  resultsSection.style.display = 'none';
  uploadSection.style.display = 'flex';
  if (navResults) navResults.classList.remove('active');
  const firstNav = document.querySelector('.nav-link:first-child');
  if (firstNav) firstNav.classList.add('active');
});

function setTheme(isLight) {
  document.body.classList.toggle('light-theme', isLight);

  themeToggles.forEach(btn => {
    btn.textContent = isLight ? '☀️ Theme' : '🌙 Theme';
  });

  localStorage.setItem('azcv-theme', isLight ? 'light' : 'dark');
}

const savedTheme = localStorage.getItem('azcv-theme');

if (savedTheme) {
  setTheme(savedTheme === 'light');
}

themeToggles.forEach(btn => {
  btn.addEventListener('click', () => {
    const isLight = !document.body.classList.contains('light-theme');
    setTheme(isLight);
  });
});

// ─── RENDER RESULTS ──────────────────────────

function renderResults(data) {
  uploadSection.style.display = 'none';
  resultsSection.style.display = 'block';
  if (navResults) navResults.classList.add('active');
  const firstNav = document.querySelector('.nav-link:first-child');
  if (firstNav) firstNav.classList.remove('active');
  window.scrollTo({ top: 0, behavior: 'smooth' });

  // Meta
  document.getElementById('results-meta').textContent =
    `Analyzed: ${selectedFile ? selectedFile.name : 'CV'} · job matches=${topKInput.value}`;

  // ── Best Job ──
  const bj = data.best_job || {};
  document.getElementById('best-job-title').textContent = bj.title || '—';
  document.getElementById('best-job-sim').textContent =
    bj.similarity !== undefined ? (bj.similarity * 100).toFixed(1) + '% match' : '';
  document.getElementById('best-job-desc').textContent = bj.description || '';

  // ── Scores ──
  const sc = data.scores || {};
  animateGauge(sc.overall || 0);
  document.getElementById('sc-out-of-10').textContent = sc.out_of_10 !== undefined ? sc.out_of_10.toFixed(1) : '—';
  document.getElementById('sc-requirements').textContent = sc.requirements !== undefined ? (sc.requirements ).toFixed(1) + '%' : '—';
  document.getElementById('sc-tools').textContent = sc.tools !== undefined ? (sc.tools ).toFixed(1) + '%' : '—';
  document.getElementById('sc-occupation').textContent = sc.occupation_similarity !== undefined ? (sc.occupation_similarity ).toFixed(1) + '%' : '—';

  const badge = document.getElementById('score-label-badge');
  const label = (sc.label || '').toLowerCase().replace(/\s+/g,'');
  badge.textContent = sc.label || '—';
  badge.className = 'score-label-badge';
  if (label.includes('weak'))     badge.classList.add('weak');
  else if (label.includes('moderate')) badge.classList.add('moderate');
  else if (label.includes('good'))     badge.classList.add('good');
  else if (label.includes('strong'))   badge.classList.add('strong');

  // ── Language ──
  const lang = data.language || {};
  const langCard = document.getElementById('lang-card');
  if (lang.original && lang.original !== 'unknown') {
    langCard.style.display = 'block';
    const translated = lang.translated ? ' → translated to English' : '';
    document.getElementById('lang-info').innerHTML =
      `<span class="lang-badge">${lang.original.toUpperCase()}</span>${translated}`;
  } else {
    langCard.style.display = 'none';
  }

  // ── Summary ──
  document.getElementById('summary-text').textContent = data.summary || '';
  document.getElementById('score-explanation').textContent = data.score_explanation || '';

  // ── Detected Jobs ──
  const jobs = data.detected_jobs || [];
  document.getElementById('detected-jobs-count').textContent = jobs.length;
  const jobList = document.getElementById('detected-jobs-list');
  jobList.innerHTML = '';
  jobs.forEach((job, i) => {
    const isBest = i === 0;
    const simPct = ((job.similarity || 0) * 100).toFixed(1);
    const el = document.createElement('div');
    el.className = 'job-item' + (isBest ? ' best' : '');
    el.innerHTML = `
      <div class="job-rank ${isBest ? 'rank-1' : ''}">${i + 1}</div>
      <div class="job-info">
        <div class="job-title-sm">${escapeHtml(job.title || '—')}</div>
      </div>
      <div class="job-sim-bar">
        <span class="sim-pct">${simPct}%</span>
        <div class="sim-track"><div class="sim-fill" style="width:${simPct}%"></div></div>
      </div>
    `;
    jobList.appendChild(el);
  });

  // ── Strengths ──
  const strengths = data.top_strengths || [];
  const strengthsList = document.getElementById('strengths-list');
  strengthsList.innerHTML = '';
  if (strengths.length === 0) {
    strengthsList.innerHTML = '<p style="color:var(--text-3);font-size:13px;">No strong matches detected.</p>';
  } else {
    strengths.forEach(s => {
      const el = document.createElement('div');
      el.className = 'strength-item';
      el.innerHTML = `
        <div class="strength-name">${escapeHtml(s.name || '')}</div>
        ${s.evidence ? `<div class="strength-evidence">${escapeHtml(s.evidence)}</div>` : ''}
        <span class="strength-type">${escapeHtml(s.type || '')}</span>
      `;
      strengthsList.appendChild(el);
    });
  }

  // ── Improvements ──
  const improvements = data.priority_improvements || [];
  const improvList = document.getElementById('improvements-list');
  improvList.innerHTML = '';
  if (improvements.length === 0) {
    improvList.innerHTML = '<p style="color:var(--text-3);font-size:13px;">No critical gaps found.</p>';
  } else {
    improvements.forEach(item => {
      const el = document.createElement('div');
      el.className = 'improvement-item';
      el.innerHTML = `
        <div class="improvement-name">${escapeHtml(item.name || '')}</div>
        ${item.how_to_improve ? `<div class="improvement-how">${escapeHtml(item.how_to_improve)}</div>` : ''}
        <span class="improvement-type">${escapeHtml(item.type || '')}</span>
      `;
      improvList.appendChild(el);
    });
  }

  // ── Tech Chips ──
  const techs = data.technologies_found || [];
  const techChips = document.getElementById('tech-chips');
  techChips.innerHTML = '';
  if (techs.length === 0) {
    techChips.innerHTML = '<span style="color:var(--text-3);font-size:13px;">No specific technologies detected.</span>';
  } else {
    techs.forEach(t => {
      const chip = document.createElement('span');
      chip.className = 'tech-chip';
      chip.textContent = t;
      techChips.appendChild(chip);
    });
  }

  // ── Recommended Tools ──
  const toolIcons = ['🔧','⚙️','🛠️','📊','💻','🔬','📈','🗄️','🔗','🌐'];
  const tools = data.recommended_tools || [];
  const toolsList = document.getElementById('tools-list');
  toolsList.innerHTML = '';
  if (tools.length === 0) {
    toolsList.innerHTML = '<p style="color:var(--text-3);font-size:13px;">No tool recommendations generated.</p>';
  } else {
    tools.forEach((tool, i) => {
      const name = typeof tool === 'string' ? tool : (tool.name || '');
      const relevance = typeof tool === 'object' && tool.relevance !== undefined
        ? (tool.relevance * 100).toFixed(0) + '% relevant'
        : '';
      const el = document.createElement('div');
      el.className = 'tool-item';
      el.innerHTML = `
        <div class="tool-icon">${toolIcons[i % toolIcons.length]}</div>
        <span class="tool-name">${escapeHtml(name)}</span>
        ${relevance ? `<span class="tool-relevance">${relevance}</span>` : ''}
      `;
      toolsList.appendChild(el);
    });
  }

  // ── Action Plan ──
  const actions = data.action_plan || [];
  const actionList = document.getElementById('action-list');
  actionList.innerHTML = '';
  if (actions.length === 0) {
    actionList.innerHTML = '<p style="color:var(--text-3);font-size:13px;">No actions generated.</p>';
  } else {
    actions.forEach((action, i) => {
      const prio = (action.priority || '').toLowerCase();
      const el = document.createElement('div');
      el.className = `action-item priority-${prio}`;
      el.innerHTML = `
        <div class="action-num">0${i + 1}</div>
        <div class="action-body">
          <div class="action-title">${escapeHtml(action.title || '')}</div>
          <div class="action-desc">${escapeHtml(action.description || '')}</div>
        </div>
        <span class="action-priority ${prio}">${escapeHtml(action.priority || '')}</span>
      `;
      actionList.appendChild(el);
    });
  }
}

// ─── GAUGE ANIMATION ─────────────────────────

function animateGauge(targetScore) {
  const arc    = document.getElementById('gauge-arc');
  const numEl  = document.getElementById('gauge-num');
  const total  = 402; // circle circumference for r=64
  let current  = 0;
  const step   = Math.max(targetScore / 60, 0.5);
  const timer  = setInterval(() => {
    current = Math.min(current + step, targetScore);
    const offset = total - (current / 100) * total;
    arc.style.strokeDashoffset = offset;
    arc.style.stroke = 'var(--accent)';
    numEl.textContent = Math.round(current);

    if (current >= targetScore) clearInterval(timer);
  }, 16);
}

// ─── UTILS ───────────────────────────────────

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
