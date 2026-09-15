/**
 * app.js — Lenny Growth Assistant frontend logic
 * Vanilla JS, no build step. Includes theme switcher & animated UI interactions.
 */

const API = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:8000/api'
  : '/api';

// ── State ─────────────────────────────────────────────────────
let currentSessionId = null;
let currentArtifact  = null;
let currentProvider  = { name: 'mock', model: 'mock-v1' };
let isSending        = false;
let artifactTab      = 'preview';

// ── DOM refs ──────────────────────────────────────────────────
const $msgs          = document.getElementById('messages');
const $input         = document.getElementById('msg-input');
const $btnSend       = document.getElementById('btn-send');
const $sessionList   = document.getElementById('session-list');
const $chatTitle     = document.getElementById('chat-title');
const $provLabel     = document.getElementById('provider-label');
const $provDot       = document.getElementById('provider-dot');
const $fallback      = document.getElementById('fallback-banner');
const $emptyState    = document.getElementById('empty-state');
const $artifactPanel = document.getElementById('artifact-panel');
const $artifactTitle = document.getElementById('artifact-title');
const $artifactBadge = document.getElementById('artifact-kind-badge');
const $mdRendered    = document.getElementById('md-rendered');
const $htmlFrame     = document.getElementById('html-frame');
const $codeArea      = document.getElementById('artifact-code');
const $codePre       = document.getElementById('artifact-code-pre');
const $preview       = document.getElementById('artifact-preview');

// Catch cross-origin iframe security errors gracefully (caused when devtools/subagents inspect sandboxed iframe contentWindow)
window.addEventListener('error', e => {
  if (e.message && (e.message.includes('SecurityError') || e.message.includes('cross-origin frame'))) {
    e.stopImmediatePropagation();
    e.preventDefault();
  }
});

// ── Init ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  loadSessions();
  refreshHealth();
  setInterval(refreshHealth, 15000);
  setupInput();
  document.getElementById('btn-new-chat').addEventListener('click', createSession);
  document.getElementById('provider-modal').addEventListener('click', e => {
    if (e.target === document.getElementById('provider-modal')) closeProviderModal();
  });
});

// ── Theme Manager ─────────────────────────────────────────────
function initTheme() {
  const savedTheme = localStorage.getItem('lenny_theme') || 'dark';
  setTheme(savedTheme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
  const next = current === 'dark' ? 'light' : 'dark';
  setTheme(next);
}

function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('lenny_theme', theme);
}

// ── Auto-resize textarea & Keyboard shortcut ─────────────────
function setupInput() {
  $input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
  $input.addEventListener('input', () => {
    $input.style.height = 'auto';
    $input.style.height = Math.min($input.scrollHeight, 160) + 'px';
  });
  $btnSend.addEventListener('click', sendMessage);
}

// ── Sessions ──────────────────────────────────────────────────
async function loadSessions() {
  try {
    const data = await api('GET', '/sessions');
    renderSessionList(data);
  } catch { /* silently ignore on startup */ }
}

function renderSessionList(sessions) {
  $sessionList.innerHTML = '';
  if (!sessions.length) {
    $sessionList.innerHTML = '<div style="padding:16px;font-size:12px;color:var(--text-muted);text-align:center;">No chats yet.<br>Click + New Chat to start.</div>';
    return;
  }
  sessions.forEach(s => {
    const el = document.createElement('div');
    el.className = 'session-item' + (s.id === currentSessionId ? ' active' : '');
    el.dataset.id = s.id;
    el.innerHTML = `
      <span class="session-icon">💬</span>
      <span class="session-title">${esc(s.title || 'Untitled')}</span>
      <button class="session-del" title="Delete" onclick="deleteSession(event,'${s.id}')">✕</button>`;
    el.addEventListener('click', () => openSession(s.id, s.title));
    $sessionList.appendChild(el);
  });
}

async function createSession() {
  try {
    const s = await api('POST', '/sessions', { title: 'New Chat' });
    await loadSessions();
    openSession(s.id, s.title);
  } catch (e) { showError('Could not create session: ' + e.message); }
}

async function openSession(id, title) {
  currentSessionId = id;
  $chatTitle.textContent = title || 'Chat';
  document.querySelectorAll('.session-item').forEach(el => {
    el.classList.toggle('active', el.dataset.id === id);
  });
  $msgs.innerHTML = '';
  closeArtifactPanel();
  try {
    const data = await api('GET', `/sessions/${id}`);
    $chatTitle.textContent = data.session.title || 'Chat';
    if (data.messages.length === 0) {
      showEmpty();
    } else {
      hideEmpty();
      let lastArtifact = null;
      data.messages.forEach(m => {
        renderMessage(m);
        if (m.artifact) lastArtifact = m.artifact;
      });
      scrollBottom();
      if (lastArtifact) {
        if (lastArtifact.id && !lastArtifact.id.startsWith('client-')) {
          fetchAndOpenArtifact(lastArtifact.id, lastArtifact.title, lastArtifact.kind);
        } else {
          openArtifactPanel(lastArtifact, lastArtifact.title, lastArtifact.kind);
        }
      }
    }
  } catch (e) { showError('Could not load session: ' + e.message); }
}

async function deleteSession(e, id) {
  e.stopPropagation();
  if (!confirm('Delete this chat?')) return;
  try {
    await api('DELETE', `/sessions/${id}`);
    if (currentSessionId === id) {
      currentSessionId = null;
      $msgs.innerHTML = '';
      showEmpty();
      $chatTitle.textContent = 'Select or start a chat';
    }
    await loadSessions();
  } catch (err) { showError('Could not delete: ' + err.message); }
}

// ── Messaging ─────────────────────────────────────────────────
async function sendMessage() {
  if (isSending) return;
  const text = $input.value.trim();
  if (!text) return;
  if (!currentSessionId) {
    try {
      const s = await api('POST', '/sessions', { title: text.slice(0, 60) });
      currentSessionId = s.id;
      $chatTitle.textContent = s.title;
      await loadSessions();
    } catch (e) { showError(e.message); return; }
  }

  hideEmpty();
  isSending = true;
  $btnSend.disabled = true;

  // Show user message
  const userMsg = { id: 'tmp-u', role: 'user', content: text, skill: null, provider: null, model: null, used_fallback: false, is_grounded: null, sources: [], artifact: null, latency_ms: null, created_at: new Date().toISOString() };
  renderMessage(userMsg);
  $input.value = '';
  $input.style.height = 'auto';

  // Show typing
  const typingEl = addTyping();
  scrollBottom();

  try {
    const skill = document.getElementById('skill-select').value;
    const resp = await api('POST', `/sessions/${currentSessionId}/chat`, {
      message: text, skill
    });
    typingEl.remove();
    const msg = resp.message;

    // Update provider badge
    if (msg.provider) updateProviderBadge(msg.provider, msg.model, msg.used_fallback);
    // Show/hide fallback banner
    $fallback.classList.toggle('visible', !!msg.used_fallback);

    renderMessage(msg);
    scrollBottom();

    // Auto-open artifact panel in 50/50 split sandbox
    if (msg.artifact) {
      if (msg.artifact.id && !msg.artifact.id.startsWith('client-')) {
        fetchAndOpenArtifact(msg.artifact.id, msg.artifact.title, msg.artifact.kind);
      } else {
        openArtifactPanel(msg.artifact, msg.artifact.title, msg.artifact.kind);
      }
    }

    loadSessions();
  } catch (e) {
    typingEl.remove();
    renderErrorMsg(e.message || 'Request failed');
    scrollBottom();
  } finally {
    isSending = false;
    $btnSend.disabled = false;
    $input.focus();
  }
}

function sendChipText(text) {
  $input.value = text;
  $input.style.height = 'auto';
  $input.style.height = Math.min($input.scrollHeight, 160) + 'px';
  sendMessage();
}

// ── Client Artifact Extraction Helper ─────────────────────────
function extractClientArtifact(content) {
  if (!content) return null;
  // 1. Look for ```html ... ```
  const htmlFence = content.match(/```(?:html|xml|htm)?\s*\n([\s\S]*?)```/i);
  if (htmlFence && (htmlFence[1].includes('<html') || htmlFence[1].includes('<!DOCTYPE') || htmlFence[1].includes('<body') || htmlFence[1].includes('<div') || htmlFence[1].includes('<style'))) {
    const titleMatch = htmlFence[1].match(/<title[^>]*>([^<]+)<\/title>/i) || htmlFence[1].match(/<h1[^>]*>([^<]+)<\/h1>/i);
    const title = titleMatch ? titleMatch[1].trim() : 'dashboard.html';
    return { id: 'client-html', kind: 'html', content: htmlFence[1].trim(), title };
  }
  // 2. Look for raw <!DOCTYPE html> ... </html> or <html> ... </html>
  const rawHtml = content.match(/(<!DOCTYPE html[\s\S]*?<\/html>|<html[\s\S]*?<\/html>)/i);
  if (rawHtml) {
    const titleMatch = rawHtml[1].match(/<title[^>]*>([^<]+)<\/title>/i) || rawHtml[1].match(/<h1[^>]*>([^<]+)<\/h1>/i);
    const title = titleMatch ? titleMatch[1].trim() : 'dashboard.html';
    return { id: 'client-html', kind: 'html', content: rawHtml[1].trim(), title };
  }
  // 3. Look for ```markdown ... ```
  const mdFence = content.match(/```markdown\s*\n([\s\S]*?)```/i);
  if (mdFence) {
    const titleMatch = mdFence[1].match(/^#+\s+(.+)$/m);
    const title = titleMatch ? titleMatch[1].trim() : 'document.md';
    return { id: 'client-md', kind: 'markdown', content: mdFence[1].trim(), title };
  }
  return null;
}

// ── Message rendering ─────────────────────────────────────────
function renderMessage(msg) {
  const el = document.createElement('div');
  el.className = 'msg ' + msg.role + (msg.is_grounded === false && msg.role === 'assistant' ? ' not-grounded' : '');
  el.dataset.msgId = msg.id;

  if (msg.role === 'user') {
    el.innerHTML = `<div class="msg-bubble">${esc(msg.content)}</div>`;
    $msgs.appendChild(el);
    return;
  }

  // Auto-detect client artifact if backend didn't attach one
  if (!msg.artifact) {
    const extracted = extractClientArtifact(msg.content);
    if (extracted) msg.artifact = extracted;
  }

  // Assistant message formatting
  let displayContent = msg.content || '';
  let checklistHtml = '';

  if (msg.artifact && msg.artifact.kind === 'html') {
    // Strip the massive raw code block so the chat bubble remains clean like the reference UI
    displayContent = displayContent
      .replace(/```(?:html|xml|htm)?\s*\n[\s\S]*?```/gi, '')
      .replace(/<!DOCTYPE html[\s\S]*?<\/html>/gi, '')
      .replace(/<html[\s\S]*?<\/html>/gi, '')
      .trim();

    const artTitle = msg.artifact.title || 'dashboard.html';
    checklistHtml = `
      <div class="agent-step-list">
        <div class="agent-step-item"><span class="asi-check">✓</span> <span class="asi-text">Generate ${esc(artTitle)} (HTML5 + Responsive CSS + Interactive JS)</span></div>
        <div class="agent-step-item"><span class="asi-check">✓</span> <span class="asi-text">Mount isolated Virtual Sandbox with strict CSP</span></div>
        <div class="agent-step-item"><span class="asi-check">✓</span> <span class="asi-text">Render live interactive simulator in right-hand split screen</span></div>
      </div>`;
    
    if (!displayContent) {
      displayContent = `The interactive application **${artTitle}** is ready and running in the Virtual Sandbox on the right.`;
    }
  }

  const html = marked.parse(displayContent);
  const skillLabel = { qa: 'Q&A Grounded', ship30_essay: 'Ship30 Essay', artifact: 'Artifact' }[msg.skill] || msg.skill || '';
  const skillClass = { qa: 'qa', ship30_essay: 'ship30', artifact: 'artifact' }[msg.skill] || 'qa';
  const latency = msg.latency_ms ? `${msg.latency_ms}ms` : '';
  const notGrounded = msg.is_grounded === false;

  let metaHtml = `<div class="msg-meta">`;
  if (skillLabel) metaHtml += `<span class="msg-skill-badge ${skillClass}">${skillLabel}</span>`;
  if (msg.provider) metaHtml += `<span>${esc(msg.provider)}·${esc(msg.model || '')}</span>`;
  if (latency) metaHtml += `<span>${latency}</span>`;
  if (notGrounded) metaHtml += `<span class="not-grounded-tag">⚠ Not Grounded</span>`;
  if (msg.used_fallback) metaHtml += `<span style="color:var(--yellow);font-size:10px;">↩ Fallback Used</span>`;
  metaHtml += `</div>`;

  // Sources button
  let sourcesHtml = '';
  if (msg.sources && msg.sources.length > 0) {
    const panelId = `sources-${msg.id}`;
    sourcesHtml = `
      <button class="sources-toggle" onclick="toggleSources('${panelId}')">
        📚 ${msg.sources.length} Transcript Sources
      </button>`;
  }

  // Artifact button & banner
  let artifactBannerHtml = '';
  let artifactBtnHtml = '';
  if (msg.artifact) {
    const isHtml = msg.artifact.kind === 'html';
    const artTitle = msg.artifact.title || (isHtml ? 'dashboard.html' : 'document.md');
    const artAction = msg.artifact.id && !msg.artifact.id.startsWith('client-')
      ? `fetchAndOpenArtifact('${msg.artifact.id}','${esc(artTitle)}','${msg.artifact.kind}')`
      : `openArtifactPanel(window.__lastArt || ${JSON.stringify(msg.artifact).replace(/"/g, '&quot;')},'${esc(artTitle)}','${msg.artifact.kind}')`;
    
    window.__lastArt = msg.artifact;

    artifactBannerHtml = `
      <div class="artifact-card-banner" onclick="${artAction}">
        <div class="acb-icon">${isHtml ? '⚡' : '✍️'}</div>
        <div class="acb-info">
          <div class="acb-title">${esc(artTitle)}</div>
          <div class="acb-sub">Rendered in Virtual Sandbox &nbsp;•&nbsp; Click to focus live preview</div>
        </div>
        <button class="acb-btn">View in Sandbox →</button>
      </div>`;
    artifactBtnHtml = `<button class="btn-open-artifact-badge" onclick="${artAction}">⚡ View ${isHtml ? 'HTML Sandbox' : 'Document'} →</button>`;
  }

  // Regenerate button
  const regenHtml = `<button class="btn-action" onclick="regenerateMsg('${msg.id}','${esc(msg.content.slice(0, 60))}')">↻ Regenerate</button>`;

  el.innerHTML = `
    <div class="msg-bubble">
      ${checklistHtml}
      ${html}
      ${artifactBannerHtml}
    </div>
    ${metaHtml}
    <div class="msg-actions-row">
      ${sourcesHtml}
      ${artifactBtnHtml}
      ${msg.role === 'assistant' && msg.skill ? regenHtml : ''}
    </div>
    ${msg.sources && msg.sources.length > 0 ? `
      <div class="sources-panel" id="sources-${msg.id}">
        ${msg.sources.map(s => `
          <div class="source-chip">
            <div class="source-chip-header">
              <span class="source-guest">${esc(s.guest)}</span>
              <span class="source-score">score ${s.score.toFixed(1)}</span>
            </div>
            <div class="source-title">${esc(s.title)}</div>
            <div class="source-snippet">"${esc(s.snippet)}"</div>
            ${s.youtube_url ? `<a class="source-link" href="${esc(s.youtube_url)}" target="_blank" rel="noopener">▶ Watch Episode Segment</a>` : ''}
          </div>`).join('')}
      </div>` : ''}`;

  $msgs.appendChild(el);
}

function renderErrorMsg(text) {
  const el = document.createElement('div');
  el.className = 'msg assistant';
  el.innerHTML = `<div class="msg-bubble" style="background:rgba(239,68,68,0.1);border-color:rgba(239,68,68,0.3);color:var(--red);">⚠ ${esc(text)}</div>`;
  $msgs.appendChild(el);
}

function addTyping() {
  const el = document.createElement('div');
  el.className = 'msg assistant';
  el.innerHTML = `<div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>`;
  $msgs.appendChild(el);
  return el;
}

function toggleSources(panelId) {
  const el = document.getElementById(panelId);
  if (el) el.classList.toggle('open');
}

// ── Regenerate with other provider ───────────────────────────
async function regenerateMsg(msgId, preview) {
  if (!currentSessionId || isSending) return;
  const altProvider = currentProvider.name === 'ollama' ? 'anthropic'
    : currentProvider.name === 'anthropic' ? 'ollama' : 'mock';
  const text = prompt(`Re-run query with provider "${altProvider}"?\nOriginal: "${preview}"`, preview);
  if (!text) return;

  isSending = true;
  $btnSend.disabled = true;
  const typing = addTyping();
  scrollBottom();

  try {
    const resp = await api('POST', `/sessions/${currentSessionId}/chat`, {
      message: text,
      skill: document.getElementById('skill-select').value,
      provider_override: altProvider,
    });
    typing.remove();
    renderMessage(resp.message);
    scrollBottom();
    if (resp.message?.artifact) {
      fetchAndOpenArtifact(resp.message.artifact.id, resp.message.artifact.title, resp.message.artifact.kind);
    }
  } catch (e) {
    typing.remove();
    renderErrorMsg(e.message);
  } finally {
    isSending = false;
    $btnSend.disabled = false;
  }
}

// ── Artifact Panel ────────────────────────────────────────────
async function fetchAndOpenArtifact(id, title, kind) {
  try {
    const art = await api('GET', `/artifacts/${id}`);
    currentArtifact = art;
    openArtifactPanel(art, title, kind);
  } catch (e) {
    showError('Could not load artifact: ' + e.message);
  }
}

function openArtifactPanel(art, title, kind) {
  if (!art) return;
  currentArtifact = art;
  $artifactPanel.classList.add('open');
  const dispTitle = art.title || title || (art.kind === 'html' ? 'dashboard.html' : 'document.md');
  $artifactTitle.textContent = dispTitle;
  const isHtml = (art.kind || kind) === 'html';
  $artifactBadge.textContent = isHtml ? 'HTML APP' : 'ESSAY / DOC';
  $artifactBadge.className = 'artifact-kind-badge ' + (isHtml ? 'html' : 'markdown');
  
  const iconEl = document.getElementById('sft-icon');
  if (iconEl) iconEl.textContent = isHtml ? '⚡' : '📄';

  switchArtifactTab('preview');
  renderArtifactContent(art);
}

function renderArtifactContent(art) {
  $codePre.textContent = art.content || '';

  if (art.kind === 'html') {
    $mdRendered.style.display = 'none';
    $htmlFrame.style.display = 'block';
    let htmlContent = art.content || '';
    // If wrapped in iframe srcdoc by backend, unwrap or use raw
    const match = (art.rendered || '').match(/srcdoc="([\s\S]*?)(?:"(?:\s*\/>|>))/);
    if (match) {
      const tmp = document.createElement('div');
      tmp.innerHTML = `<div srcdoc="${match[1]}"></div>`;
      const srcdocValue = tmp.firstChild ? tmp.firstChild.getAttribute('srcdoc') : null;
      htmlContent = srcdocValue || art.content;
    }
    $htmlFrame.srcdoc = htmlContent;
  } else {
    $htmlFrame.style.display = 'none';
    $htmlFrame.srcdoc = '';
    $mdRendered.style.display = 'block';
    $mdRendered.innerHTML = art.rendered || marked.parse(art.content || '');
  }
}

function switchArtifactTab(tab) {
  artifactTab = tab;
  document.getElementById('tab-preview').classList.toggle('active', tab === 'preview');
  document.getElementById('tab-code').classList.toggle('active', tab === 'code');
  $preview.classList.toggle('visible', tab === 'preview');
  $preview.style.display = tab === 'preview' ? 'block' : 'none';
  $codeArea.classList.toggle('visible', tab === 'code');
  $codeArea.style.display = tab === 'code' ? 'block' : 'none';
}

function closeArtifactPanel() {
  $artifactPanel.classList.remove('open');
  $htmlFrame.srcdoc = '';
  currentArtifact = null;
}

function copyArtifactContent() {
  if (!currentArtifact || !currentArtifact.content) return;
  navigator.clipboard.writeText(currentArtifact.content).then(() => {
    alert('Artifact content copied to clipboard!');
  }).catch(() => {
    // fallback
    const ta = document.createElement('textarea');
    ta.value = currentArtifact.content;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    alert('Artifact content copied to clipboard!');
  });
}

function downloadArtifact() {
  if (!currentArtifact) return;
  const ext = currentArtifact.kind === 'html' ? 'html' : 'md';
  const filename = (currentArtifact.title || 'artifact').replace(/[^a-z0-9]/gi, '_').toLowerCase() + '.' + ext;
  const blob = new Blob([currentArtifact.content], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

// ── Provider Badge & Picker Modal ─────────────────────────────
function updateProviderBadge(provider, model, usedFallback) {
  currentProvider = { name: provider, model };
  $provLabel.textContent = `${provider} · ${model || ''}`;
  $provDot.style.background = usedFallback ? 'var(--yellow)' : 'var(--green)';
}

function openProviderModal() {
  fetchHealth().then(health => {
    const opts = document.getElementById('provider-options');
    const providers = [
      { id: 'ollama',    icon: '🦙', name: 'Ollama (Local)', model: 'gemma3:4b', status: health?.components?.llm_primary },
      { id: 'mock',      icon: '🤖', name: 'Mock Engine', model: 'mock-v1',  status: health?.components?.llm_fallback },
      { id: 'anthropic', icon: '🧠', name: 'Anthropic Cloud', model: 'claude-3-5-haiku', status: null },
    ];
    opts.innerHTML = providers.map(p => {
      const isSelected = currentProvider.name === p.id;
      const statusText = p.status?.status === 'ok' ? 'Available' : p.status?.status === 'unconfigured' ? 'No API key' : 'Degraded';
      const statusClass = p.status?.status === 'ok' ? 'po-ok' : 'po-warn';
      return `<div class="provider-option ${isSelected ? 'selected' : ''}" onclick="selectProvider('${p.id}','${p.model}')">
        <span class="po-icon">${p.icon}</span>
        <div><div class="po-name">${p.name}</div><div class="po-model">${p.model}</div></div>
        ${p.status ? `<span class="po-status ${statusClass}">${statusText}</span>` : ''}
      </div>`;
    }).join('');
    document.getElementById('provider-modal').classList.add('open');
  });
}

function selectProvider(name, model) {
  currentProvider = { name, model };
  $provLabel.textContent = `${name} · ${model}`;
  closeProviderModal();
}

function closeProviderModal() {
  document.getElementById('provider-modal').classList.remove('open');
}

// ── Health Bar ────────────────────────────────────────────────
async function refreshHealth() {
  const health = await fetchHealth();
  if (!health) return;
  const strip = document.getElementById('health-strip');
  const comps = health.components || {};
  const rows = Object.entries(comps).map(([name, c]) => {
    const dotClass = c.status === 'ok' ? 'ok' : c.status === 'degraded' ? 'degraded' : c.status === 'unconfigured' ? 'unconfigured' : 'error';
    const label = { db: '🗄 DB', retrieval: '🔍 Index', llm_primary: '🤖 Ollama', llm_fallback: '↩ Fallback' }[name] || name;
    return `<div class="health-row"><div class="health-dot ${dotClass}"></div><span>${label}: ${c.status}</span></div>`;
  }).join('');
  strip.innerHTML = rows;

  if (comps.llm_primary?.status === 'ok') {
    $provDot.style.background = 'var(--green)';
  } else {
    $provDot.style.background = 'var(--yellow)';
  }
}

async function fetchHealth() {
  try { return await api('GET', '/health'); }
  catch { return null; }
}

// ── API helper ────────────────────────────────────────────────
async function api(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) opts.body = JSON.stringify(body);
  const resp = await fetch(API + path, opts);
  if (!resp.ok) {
    let msg = `HTTP ${resp.status}`;
    try {
      const err = await resp.json();
      msg = err.detail?.message || err.detail || JSON.stringify(err);
    } catch {}
    throw new Error(msg);
  }
  if (resp.status === 204) return null;
  return resp.json();
}

// ── Helpers ───────────────────────────────────────────────────
function esc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function showEmpty() { $emptyState.style.display = 'flex'; }
function hideEmpty() { $emptyState.style.display = 'none'; }
function scrollBottom() { $msgs.scrollTop = $msgs.scrollHeight; }
function showError(msg) { alert('Error: ' + msg); }
