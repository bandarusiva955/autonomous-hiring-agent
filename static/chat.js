/*
 * Floating career-assistant chat widget.
 * Reads optional page context from window.HIRING_CHAT_CONTEXT:
 *   { role, skills: [], matched: [], missing: [], match_pct }
 * Self-contained: injects its own styles, no external libraries.
 */
(function () {
    'use strict';
    if (window.__hiringChatLoaded) { return; }
    window.__hiringChatLoaded = true;

    var SUGGESTIONS = ['What skills am I missing?', 'Give me a learning roadmap',
                       'Practice interview questions', 'How do I get shortlisted?'];
    var history = [];
    var busy = false;

    var css = [
        '.hc-btn{position:fixed;right:20px;bottom:20px;z-index:9998;background:#5b4fd8;color:#fff;border:0;',
        'border-radius:999px;padding:12px 18px;font:600 15px system-ui,sans-serif;cursor:pointer;',
        'box-shadow:0 6px 20px rgba(0,0,0,.25)}',
        '.hc-btn:hover{background:#463bb8}',
        '.hc-panel{position:fixed;right:20px;bottom:76px;z-index:9999;width:360px;max-width:calc(100vw - 24px);',
        'height:480px;max-height:calc(100vh - 100px);background:#fff;border-radius:14px;display:none;',
        'flex-direction:column;box-shadow:0 12px 40px rgba(0,0,0,.28);overflow:hidden;font:15px/1.45 system-ui,sans-serif;color:#1f2430}',
        '.hc-panel.open{display:flex}',
        '.hc-head{background:#5b4fd8;color:#fff;padding:12px 14px;display:flex;justify-content:space-between;align-items:center;font-weight:600}',
        '.hc-head button{background:none;border:0;color:#fff;font-size:20px;cursor:pointer;line-height:1}',
        '.hc-msgs{flex:1;overflow-y:auto;padding:12px;background:#f4f5fb}',
        '.hc-m{margin:0 0 10px;padding:9px 12px;border-radius:12px;max-width:88%;white-space:pre-wrap;word-wrap:break-word}',
        '.hc-m.bot{background:#fff;border:1px solid #e4e7ee}',
        '.hc-m.me{background:#5b4fd8;color:#fff;margin-left:auto}',
        '.hc-m a{display:inline-block;margin-top:8px;color:#5b4fd8;font-weight:600}',
        '.hc-chips{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 10px}',
        '.hc-chip{background:#e8edff;color:#463bb8;border:0;border-radius:999px;padding:5px 10px;font:13px system-ui,sans-serif;cursor:pointer}',
        '.hc-form{display:flex;gap:8px;padding:10px;border-top:1px solid #e4e7ee;background:#fff}',
        '.hc-form input{flex:1;padding:9px 10px;border:1px solid #e4e7ee;border-radius:8px;font:inherit}',
        '.hc-form button{background:#5b4fd8;color:#fff;border:0;border-radius:8px;padding:0 14px;font-weight:600;cursor:pointer}',
        '.hc-form button:disabled{opacity:.6;cursor:default}'
    ].join('');
    var style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);

    var button = document.createElement('button');
    button.className = 'hc-btn';
    button.type = 'button';
    button.textContent = 'Ask AI assistant';

    var panel = document.createElement('div');
    panel.className = 'hc-panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', 'Career assistant');
    panel.innerHTML =
        '<div class="hc-head"><span>Career assistant</span><button type="button" aria-label="Close">&times;</button></div>' +
        '<div class="hc-msgs"></div>' +
        '<form class="hc-form"><input type="text" maxlength="500" placeholder="Ask about skills, roadmaps, interviews..." aria-label="Message">' +
        '<button type="submit">Send</button></form>';

    var msgs = panel.querySelector('.hc-msgs');
    var form = panel.querySelector('form');
    var input = panel.querySelector('input');
    var sendBtn = panel.querySelector('form button');

    function addMessage(text, who, links) {
        var el = document.createElement('div');
        el.className = 'hc-m ' + who;
        el.textContent = text;
        (links || []).forEach(function (link) {
            if (typeof link.url !== 'string' || link.url.charAt(0) !== '/') { return; }
            el.appendChild(document.createElement('br'));
            var a = document.createElement('a');
            a.href = link.url;
            a.textContent = link.label + ' →';
            el.appendChild(a);
        });
        msgs.appendChild(el);
        msgs.scrollTop = msgs.scrollHeight;
        return el;
    }

    function addChips(items) {
        if (!items || !items.length) { return; }
        var wrap = document.createElement('div');
        wrap.className = 'hc-chips';
        items.forEach(function (text) {
            var chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'hc-chip';
            chip.textContent = text;
            chip.addEventListener('click', function () { wrap.remove(); send(text); });
            wrap.appendChild(chip);
        });
        msgs.appendChild(wrap);
        msgs.scrollTop = msgs.scrollHeight;
    }

    function send(text) {
        text = (text || '').trim();
        if (!text || busy) { return; }
        busy = true;
        sendBtn.disabled = true;
        addMessage(text, 'me');
        var thinking = addMessage('Thinking...', 'bot');

        fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                context: window.HIRING_CHAT_CONTEXT || null,
                history: history.slice(-6)
            })
        }).then(function (response) {
            return response.json().then(function (data) { return { ok: response.ok, data: data }; });
        }).then(function (result) {
            thinking.remove();
            if (!result.ok) {
                addMessage(result.data.error || 'Something went wrong. Please try again.', 'bot');
                return;
            }
            history.push({ role: 'user', content: text });
            history.push({ role: 'assistant', content: result.data.reply });
            addMessage(result.data.reply, 'bot', result.data.links);
            addChips(result.data.suggestions);
        }).catch(function () {
            thinking.remove();
            addMessage('I could not reach the server. Please try again.', 'bot');
        }).then(function () {
            busy = false;
            sendBtn.disabled = false;
            input.focus();
        });
    }

    button.addEventListener('click', function () {
        panel.classList.toggle('open');
        if (panel.classList.contains('open')) { input.focus(); }
    });
    panel.querySelector('.hc-head button').addEventListener('click', function () {
        panel.classList.remove('open');
    });
    form.addEventListener('submit', function (event) {
        event.preventDefault();
        var value = input.value;
        input.value = '';
        send(value);
    });

    document.body.appendChild(panel);
    document.body.appendChild(button);
    addMessage('Hi! I can explain your skill gaps, suggest a learning roadmap, and prepare you for interviews.', 'bot');
    addChips(SUGGESTIONS);
})();
