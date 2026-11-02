'use strict';

var DEFAULT_API = 'http://127.0.0.1:5000';
var state = { api: DEFAULT_API, skills: [], lastRole: '', lastMissing: [], lastMatched: [], lastPct: null, history: [] };

function $(id) { return document.getElementById(id); }

function setStatus(text, isError) {
    var el = $('status');
    el.textContent = text || '';
    el.className = 'status' + (isError ? ' error' : '');
}

function parseSkills(text) {
    var seen = {};
    return text.split(/[,\n]/).map(function (s) { return s.trim(); }).filter(function (s) {
        var key = s.toLowerCase();
        if (!s || seen[key]) { return false; }
        seen[key] = true;
        return true;
    });
}

function updateSkillCount() {
    $('skills-count').textContent = state.skills.length ? state.skills.length + ' skills saved' : '';
}

function storageGet(keys) {
    return new Promise(function (resolve) { chrome.storage.local.get(keys, resolve); });
}
function storageSet(values) {
    return new Promise(function (resolve) { chrome.storage.local.set(values, resolve); });
}

function normalizeApi(value) {
    var url = (value || '').trim().replace(/\/+$/, '');
    if (!/^https?:\/\/[^\s/]+$/i.test(url) && !/^https?:\/\/[^\s/]+\/[^\s]*$/i.test(url)) { return null; }
    return url;
}

// Ask Chrome for permission to talk to a server other than the built-in local one.
function ensureHostPermission(api) {
    var origin = new URL(api).origin + '/*';
    return new Promise(function (resolve) {
        chrome.permissions.contains({ origins: [origin] }, function (has) {
            if (has) { resolve(true); return; }
            chrome.permissions.request({ origins: [origin] }, function (granted) { resolve(!!granted); });
        });
    });
}

function apiFetch(path, options) {
    return fetch(state.api + path, options).then(function (response) {
        return response.json().catch(function () { return {}; }).then(function (data) {
            if (!response.ok) { throw new Error(data.error || 'Request failed (' + response.status + ')'); }
            return data;
        });
    }, function () {
        throw new Error('Could not reach ' + state.api + '. Is the app running?');
    });
}

function chipList(container, items, cls) {
    container.textContent = '';
    if (!items.length) {
        var none = document.createElement('span');
        none.className = 'none';
        none.textContent = 'Nothing';
        container.appendChild(none);
        return;
    }
    items.slice(0, 40).forEach(function (item) {
        var chip = document.createElement('span');
        chip.className = 'chip ' + cls;
        chip.textContent = item;
        container.appendChild(chip);
    });
}

function showResult(data, title) {
    $('result').hidden = false;
    $('pct').textContent = data.match_percentage + '%';
    $('verdict').textContent = data.verdict;
    $('job-title').textContent = title || '';
    $('bar-fill').style.width = data.match_percentage + '%';
    chipList($('matched'), data.matched, 'ok');
    chipList($('missing'), data.missing, 'miss');

    var roadmap = $('roadmap');
    roadmap.textContent = '';
    if (data.roadmap) {
        roadmap.appendChild(document.createTextNode('Suggested path: ' + data.roadmap.title + ' (' + data.roadmap.duration_weeks + ' weeks). '));
        var link = document.createElement('a');
        link.href = state.api + data.roadmap.url;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = 'Open roadmap';
        roadmap.appendChild(link);
    }
}

// Runs inside the page: prefer the user's selection, otherwise the visible page text.
function readPage() {
    var selection = String(window.getSelection ? window.getSelection() : '').trim();
    var text = selection.length > 200 ? selection : (document.body ? document.body.innerText : '');
    return { text: text.slice(0, 20000), title: document.title || '', url: location.href };
}

function checkJob() {
    if (!state.skills.length) { setStatus('Add your skills first, or import them from your resume.', true); return; }
    var button = $('check-btn');
    button.disabled = true;
    setStatus('Reading this page...');

    chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
        var tab = tabs && tabs[0];
        if (!tab || !tab.id || !/^https?:/i.test(tab.url || '')) {
            setStatus('Open a job page (a normal website) and try again.', true);
            button.disabled = false;
            return;
        }
        chrome.scripting.executeScript({ target: { tabId: tab.id }, func: readPage }, function (results) {
            if (chrome.runtime.lastError || !results || !results[0] || !results[0].result) {
                setStatus('Could not read this page. Try selecting the job description text first.', true);
                button.disabled = false;
                return;
            }
            var page = results[0].result;
            setStatus('Checking your match...');
            apiFetch('/api/match-jd', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ skills: state.skills, jd_text: page.text })
            }).then(function (data) {
                state.lastMissing = data.missing;
                state.lastMatched = data.matched;
                state.lastPct = data.match_percentage;
                state.lastRole = page.title.slice(0, 80);
                showResult(data, page.title.slice(0, 80));
                setStatus('');
            }).catch(function (error) {
                setStatus(error.message, true);
            }).then(function () { button.disabled = false; });
        });
    });
}

function importResume(file) {
    if (!file) { return; }
    setStatus('Reading your resume...');
    var form = new FormData();
    form.append('resume_file', file);
    apiFetch('/api/analyze', { method: 'POST', body: form }).then(function (data) {
        var skills = (data.extracted_skills || []).slice(0, 150);
        if (!skills.length) { throw new Error('No skills were found in that resume.'); }
        state.skills = skills;
        $('skills').value = skills.join(', ');
        updateSkillCount();
        return storageSet({ skills: skills }).then(function () {
            setStatus('Imported ' + skills.length + ' skills. The resume file was not stored.');
        });
    }).catch(function (error) { setStatus(error.message, true); });
}

function addChatMessage(text, who, links) {
    var log = $('chat-log');
    var el = document.createElement('div');
    el.className = 'msg ' + who;
    el.textContent = text;
    (links || []).forEach(function (item) {
        if (typeof item.url !== 'string' || item.url.charAt(0) !== '/') { return; }
        el.appendChild(document.createElement('br'));
        var a = document.createElement('a');
        a.href = state.api + item.url;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
        a.textContent = item.label;
        el.appendChild(a);
    });
    log.appendChild(el);
    log.scrollTop = log.scrollHeight;
    return el;
}

function sendChat(text) {
    text = text.trim();
    if (!text) { return; }
    addChatMessage(text, 'me');
    var waiting = addChatMessage('Thinking...', 'bot');
    apiFetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message: text,
            history: state.history.slice(-6),
            context: { role: state.lastRole, skills: state.skills, matched: state.lastMatched,
                       missing: state.lastMissing, match_pct: state.lastPct }
        })
    }).then(function (data) {
        waiting.remove();
        state.history.push({ role: 'user', content: text }, { role: 'assistant', content: data.reply });
        addChatMessage(data.reply, 'bot', data.links);
    }).catch(function (error) {
        waiting.remove();
        addChatMessage(error.message, 'bot');
    });
}

function init() {
    storageGet(['api', 'skills']).then(function (saved) {
        state.api = saved.api || DEFAULT_API;
        state.skills = Array.isArray(saved.skills) ? saved.skills : [];
        $('api-url').value = state.api;
        $('skills').value = state.skills.join(', ');
        updateSkillCount();
        addChatMessage('Hi! After you check a job, ask me what to learn first or how to close the gaps.', 'bot');
    });

    $('settings-toggle').addEventListener('click', function () { $('settings').hidden = !$('settings').hidden; });

    $('save-settings').addEventListener('click', function () {
        var api = normalizeApi($('api-url').value);
        if (!api) { setStatus('Enter a valid address such as http://127.0.0.1:5000', true); return; }
        ensureHostPermission(api).then(function (granted) {
            if (!granted) { setStatus('Permission to contact that server was not granted.', true); return; }
            state.api = api;
            return storageSet({ api: api }).then(function () { setStatus('Saved.'); $('settings').hidden = true; });
        });
    });

    $('skills').addEventListener('change', function () {
        state.skills = parseSkills($('skills').value);
        updateSkillCount();
        storageSet({ skills: state.skills });
    });

    $('import-btn').addEventListener('click', function () { $('resume-file').click(); });
    $('resume-file').addEventListener('change', function () {
        importResume(this.files && this.files[0]);
        this.value = '';
    });

    $('check-btn').addEventListener('click', function () {
        state.skills = parseSkills($('skills').value);
        updateSkillCount();
        storageSet({ skills: state.skills }).then(checkJob);
    });

    $('chat-form').addEventListener('submit', function (event) {
        event.preventDefault();
        var value = $('chat-input').value;
        $('chat-input').value = '';
        sendChat(value);
    });
}

document.addEventListener('DOMContentLoaded', init);
