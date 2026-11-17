/* Executes before Layerling's scripts. Native PHP authorization remains the security boundary. */
(() => {
  'use strict';
  const root = document.documentElement;
  root.dataset.ssoCad = 'pending';
  let locked = false;
  let reason = 'Die Anmeldung wird geprüft …';
  let expiryTimer;
  let pendingProbe;
  let onlineGate;
  let clearMcpToken;
  const nativeFetch = window.fetch.bind(window);
  const context = JSON.parse(document.getElementById('sso-cad-context').textContent);
  if (!/^[a-f0-9]{32}$/.test(context.userId) || !/^[a-f0-9]{64}$/.test(context.csrfToken)) {
    throw new Error('Invalid CAD context');
  }
  const actor = context.userId;
  const selected = context.selected;
  if (!selected || !/^[a-f0-9]{32}$/.test(selected.userId) || !Array.isArray(context.owners)) {
    throw new Error('Invalid CAD owner');
  }
  const owner = selected.userId;
  const mcpEditorId = context.mcpTest === true && owner === actor ? crypto.randomUUID() : null;
  const mcpEditorNumber = mcpEditorId === null ? null : 10000 + crypto.getRandomValues(new Uint32Array(1))[0] % 90000;
  if (mcpEditorId !== null) root.dataset.ssoMcpTest = 'true';
  let canDelete = selected.canDelete === true;
  root.dataset.ssoCanDelete = String(canDelete);
  const csrf = context.csrfToken;
  // Keep existing personal work copies and isolate foreign work copies by actor and owner.
  const prefix = actor === owner ? `sso.cad.v1.${actor}.` : `sso.cad.owner.v1.${actor}.${owner}.`;
  document.getElementById('sso-cad-context').remove();
  const assertOpen = () => { if (locked) throw new Error('Editor gesperrt. Bitte erneut anmelden.'); };
  function renderAccountPicker(panel, toggle) {
    const nameKey = name => name.trim().normalize('NFC').toLocaleLowerCase('de');
    const name = record => record.name ?? record.label;
    const title = record => name(record) + (record.classes.length ? ' (' + record.classes.join(', ') + ')' : '');
    const countNames = records => {
      const counts = new Map();
      for (const record of records) {
        const key = nameKey(title(record));
        counts.set(key, (counts.get(key) ?? 0) + 1);
      }
      return counts;
    };
    let owners = context.owners;
    let nameCounts = countNames(owners);
    const displayName = record => title(record) + (nameCounts.get(nameKey(title(record))) > 1 ? ' · ' + record.userId.slice(0, 8) : '');
    const current = displayName(selected);
    const active = document.createElement('strong');
    active.textContent = 'Aktives Konto: ' + current;
    panel.append(active);
    const foreign = actor !== owner;
    toggle.textContent += foreign ? ' · Fremdes Konto: ' + current : ' · ' + current;
    toggle.title = toggle.textContent;
    toggle.classList.toggle('sso-cad-foreign-account', foreign);
    if (owners.length < 2) return;

    const picker = document.createElement('details');
    picker.id = 'sso-cad-accounts';
    const choose = document.createElement('summary');
    choose.textContent = 'Konto auswählen';
    const label = document.createElement('label');
    label.textContent = 'Nach Name oder Klasse filtern';
    const filter = document.createElement('input');
    filter.type = 'search';
    filter.autocomplete = 'off';
    label.append(filter);
    const list = document.createElement('ul');
    const empty = document.createElement('p');
    empty.setAttribute('role', 'status');
    empty.textContent = 'Keine passenden Konten';
    const hint = document.createElement('p');
    hint.textContent = 'Ohne Filter erscheinen fremde Konten mit einer Dateispeicherung in der letzten Stunde.';
    function showMatches() {
      const term = nameKey(filter.value);
      const matches = owners.filter(record => term
        ? nameKey([name(record), ...record.classes].join(' ')).includes(term)
        : record.isSelf || record.recentProjectSave);
      list.replaceChildren();
      for (const record of matches) {
        const item = document.createElement('li');
        const link = document.createElement('a');
        link.href = record.isSelf ? '/cad.php' : '/cad.php?' + new URLSearchParams({owner: record.userId});
        link.textContent = displayName(record);
        if (record.userId === owner) {
          link.setAttribute('aria-current', 'true');
          link.addEventListener('click', event => event.preventDefault());
        }
        item.append(link);
        list.append(item);
      }
      empty.hidden = matches.length > 0;
      hint.hidden = term !== '';
    }
    filter.addEventListener('input', showMatches);
    let refresh;
    picker.addEventListener('toggle', async () => {
      if (!picker.open || refresh) return;
      filter.focus();
      refresh = nativeFetch('/owners.php?cad=1', {
        headers: {'X-SSO-CSRF': csrf}, cache: 'no-store', signal: AbortSignal.timeout(10000),
      });
      try {
        const response = await refresh;
        if (response.status === 401 || response.status === 403) {
          await probe();
          return;
        }
        if (!response.ok) return;
        owners = (await response.json()).owners;
        nameCounts = countNames(owners);
        showMatches();
      } catch {
        // The current document already has an authorized catalogue snapshot.
      } finally {
        refresh = null;
      }
    });
    showMatches();
    picker.append(choose, label, hint, list, empty);
    panel.append(picker);
  }

  function renderFooter() {
    const footer = document.createElement('footer');
    footer.id = 'sso-cad-footer';
    const menu = document.createElement('details');
    const toggle = document.createElement('summary');
    toggle.textContent = 'SSO-Menü';
    const panel = document.createElement('nav');
    panel.id = 'sso-cad-nav';
    panel.setAttribute('aria-label', 'SSO-Kontonavigation');
    renderAccountPicker(panel, toggle);
    const actions = document.createElement('div');
    actions.className = 'sso-cad-actions';
    const close = () => {
      menu.open = false;
      clearMcpToken?.();
      const picker = panel.querySelector('details');
      if (picker) picker.open = false;
    };
    const searchDesign = document.createElement('button');
    searchDesign.type = 'button';
    searchDesign.id = 'sso-cad-find-design';
    searchDesign.textContent = 'Entwürfe im aktiven Bereich suchen';
    searchDesign.addEventListener('click', () => {
      close();
      document.querySelector('[data-sso-server-tab][aria-selected="false"]')?.click();
      document.querySelector('[data-sso-design-search]')?.focus();
    });
    actions.append(searchDesign);
    if (context.canUseTemplates) {
      const templates = document.createElement('a');
      templates.href = '/vorlagen.php';
      templates.textContent = 'CAD-Vorlagen';
      actions.append(templates);
    }
    if (mcpEditorId !== null) {
      const pair = document.createElement('button');
      pair.type = 'button';
      pair.id = 'sso-mcp-pair';
      pair.textContent = 'MCP-Testtoken erstellen';
      const token = document.createElement('input');
      token.readOnly = true;
      token.hidden = true;
      token.autocomplete = 'off';
      token.setAttribute('aria-label', 'MCP-Testtoken');
      const status = document.createElement('span');
      status.setAttribute('role', 'status');
      clearMcpToken = () => { token.value = ''; token.hidden = true; status.textContent = ''; };
      pair.addEventListener('click', async () => {
        clearMcpToken();
        pair.disabled = true;
        try {
          const response = await fetch('/api/layerling-mcp', {
            method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({type: 'pair'}),
          });
          if (!response.ok) throw new Error('MCP pairing rejected');
          const result = await response.json();
          if (!menu.open || locked) return;
          status.textContent = 'Für diese Sitzung. Gültig bis ' + new Date(result.expiresAt * 1000).toLocaleTimeString('de-DE');
          token.value = result.token;
          token.hidden = false;
          token.select();
        } catch {
          if (menu.open) status.textContent = 'MCP-Testtoken konnte nicht erstellt werden.';
        } finally {
          pair.disabled = false;
        }
      });
      actions.append(pair, token, status);
    }
    const logout = document.createElement('form');
    logout.action = '/auth/logout.php';
    logout.method = 'post';
    for (const [name, value] of [['csrf', context.logoutCsrf], ['cadCsrf', csrf]]) {
      const token = document.createElement('input');
      token.type = 'hidden';
      token.name = name;
      token.value = value;
      logout.append(token);
    }
    const signOut = document.createElement('button');
    signOut.type = 'submit';
    signOut.textContent = 'Abmelden';
    logout.append(signOut);
    actions.append(logout);
    panel.append(actions);
    menu.append(toggle, panel);
    footer.append(menu);
    document.body.append(footer);

    document.addEventListener('click', event => {
      if (menu.open && !menu.contains(event.target)) close();
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && menu.open && menu.contains(event.target)) {
        event.stopPropagation();
        close();
        toggle.focus();
      }
    }, true);
  }
  function renderGuard() {
    let guard = document.getElementById('sso-cad-guard');
    if (!guard && document.body) {
      guard = document.createElement('aside'); guard.id = 'sso-cad-guard'; guard.setAttribute('role', 'alert');
      const message = document.createElement('p'); message.id = 'sso-cad-status'; guard.append(message);
      const home = document.createElement('a'); home.href = '/cad.php'; home.textContent = 'CAD neu öffnen'; guard.append(home);
      document.body.append(guard);
      renderFooter();
    }
    const message = document.getElementById('sso-cad-status');
    if (message) message.textContent = reason;
  }
  function lock(message) {
    locked = true; reason = message; root.dataset.ssoCad = 'locked'; clearTimeout(expiryTimer); renderGuard();
  }
  window.addEventListener('DOMContentLoaded', renderGuard, {once: true});
  function scopedStorage(native) {
    const keys = () => Array.from({length: native.length}, (_, i) => native.key(i)).filter(k => k?.startsWith(prefix));
    const api = {
      get length() { assertOpen(); return keys().length; },
      key(index) { assertOpen(); return keys()[index]?.slice(prefix.length) ?? null; },
      getItem(key) { assertOpen(); return native.getItem(prefix + String(key)); },
      setItem(key, value) { assertOpen(); native.setItem(prefix + String(key), String(value)); },
      removeItem(key) { assertOpen(); native.removeItem(prefix + String(key)); },
      clear() { assertOpen(); keys().forEach(k => native.removeItem(k)); },
    };
    return new Proxy(api, {
      ownKeys() { assertOpen(); return keys().map(k => k.slice(prefix.length)); },
      getOwnPropertyDescriptor(target, key) {
        if (typeof key === 'string' && native.getItem(prefix + key) !== null) return {configurable: true, enumerable: true, value: api.getItem(key)};
        return Reflect.getOwnPropertyDescriptor(target, key);
      },
    });
  }
  try {
    for (const name of ['localStorage', 'sessionStorage']) {
      const scoped = scopedStorage(window[name]);
      Object.defineProperty(window, name, {configurable: false, get: () => scoped});
    }
    const idb = window.indexedDB;
    if (!idb) throw new Error('IndexedDB unavailable');
    const factory = new Proxy(idb, {get(target, property) {
      if (property === 'open' || property === 'deleteDatabase') return (name, ...args) => {
        assertOpen(); return target[property](prefix + String(name), ...args);
      };
      if (property === 'databases') return async () => {
        assertOpen(); return (await target.databases()).filter(d => d.name?.startsWith(prefix)).map(d => ({...d, name: d.name.slice(prefix.length)}));
      };
      const value = Reflect.get(target, property, target); return typeof value === 'function' ? value.bind(target) : value;
    }});
    Object.defineProperty(window, 'indexedDB', {configurable: false, get: () => factory});
    if (window.BroadcastChannel) {
      const NativeChannel = window.BroadcastChannel;
      window.BroadcastChannel = class extends NativeChannel { constructor(name) { assertOpen(); super(prefix + String(name)); } };
    }
    // Translate native storage events once; suppress events belonging to another account.
    const translated = new WeakSet();
    window.addEventListener('storage', event => {
      if (translated.has(event)) return;
      event.stopImmediatePropagation();
      if (locked || !event.key?.startsWith(prefix)) return;
      const scoped = new StorageEvent('storage', {key: event.key.slice(prefix.length), oldValue: event.oldValue, newValue: event.newValue, url: event.url});
      translated.add(scoped); window.dispatchEvent(scoped);
    }, true);
  } catch {
    lock('Der Browser unterstützt den getrennten Projektspeicher nicht. Bitte ein eigenes Browserprofil verwenden.');
  }
  async function probe() {
    assertOpen();
    if (!pendingProbe) pendingProbe = (async () => {
      try {
        await onlineGate;
        const response = await nativeFetch('/cad-session.php?' + new URLSearchParams({owner}), {
          headers: {'X-SSO-CSRF': csrf}, cache: 'no-store', credentials: 'same-origin',
          redirect: 'error', signal: AbortSignal.timeout(10000),
        });
        if (!response.ok) throw new Error('Session rejected');
        const value = await response.json();
        if (value.userId !== actor || value.ownerId !== owner || value.csrfToken !== csrf
            || typeof value.canDelete !== 'boolean' || !Number.isInteger(value.expiresAt)
            || value.expiresAt <= Date.now() / 1000) throw new Error('Session changed');
        canDelete = value.canDelete;
        root.dataset.ssoCanDelete = String(canDelete);
        assertOpen();
        clearTimeout(expiryTimer);
        expiryTimer = setTimeout(() => lock('Die Sitzung ist abgelaufen. Bitte erneut anmelden.'), Math.max(0, value.expiresAt * 1000 - Date.now()));
        root.dataset.ssoCad = 'ready';
      } catch (error) {
        lock('Der Dateibereich, die Sitzung oder die Internetverbindung ist nicht mehr verfügbar.'); throw error;
      }
    })().finally(() => { pendingProbe = null; });
    return pendingProbe;
  }
  function bindThumbnail(record) {
    if (!record || typeof record.thumbnailUrl !== 'string') return;
    const url = new URL(record.thumbnailUrl, location.href);
    if (url.origin === location.origin && url.pathname === '/store.php') {
      url.searchParams.set('_sso_owner', owner); record.thumbnailUrl = url.pathname + url.search;
    }
  }
  window.fetch = async (input, init) => {
    const request = new Request(input, init);
    const url = new URL(request.url);
    if (mcpEditorId !== null && url.origin === location.origin && url.pathname === '/api/layerling-mcp') {
      assertOpen();
      await onlineGate;
      assertOpen();
      const headers = new Headers(request.headers);
      headers.set('X-SSO-CSRF', csrf);
      let body;
      if (request.method === 'POST') {
        const payload = await request.json();
        // Duplicating a tab can copy sessionStorage. Give each mounted document its own bridge identity.
        if (payload.type === 'heartbeat') Object.assign(payload.editor, {editorId: mcpEditorId, editorNumber: mcpEditorNumber});
        if (payload.type === 'poll' || payload.type === 'result') payload.editorId = mcpEditorId;
        body = JSON.stringify(payload);
      }
      return nativeFetch(url, {method: request.method, headers, body, signal: request.signal,
        credentials: 'same-origin', mode: 'same-origin', cache: 'no-store', redirect: 'error'});
    }
    if (url.origin !== location.origin || url.pathname !== '/store.php') return nativeFetch(input, init);
    assertOpen();
    const owners = url.searchParams.getAll('_sso_owner');
    if (owners.some(value => value !== owner)) throw new Error('Diese Datei gehört zu einem anderen Dateibereich.');
    url.searchParams.set('_sso_owner', owner);
    await probe();
    // The workspace defaults belong to the signed-in person. A foreign tab uses its
    // own browser-scoped defaults and never syncs them to either person's server settings.
    if (owner !== actor && url.searchParams.has('settings')) {
      return request.method === 'GET'
        ? Response.json({enabled: false})
        : Response.json({error: 'Persönliche Einstellungen sind in diesem Dateibereich gesperrt.'}, {status: 403});
    }
    if (request.method === 'DELETE' && !canDelete) {
      return Response.json({error: 'In diesem Dateibereich darfst du keine Dateien löschen.'}, {status: 403});
    }
    const headers = new Headers(request.headers);
    headers.set('X-SSO-CSRF', csrf);
    let response;
    try {
      // A Request's ReadableStream body cannot be re-sent over HTTP/1.1 in Chromium.
      // Keep its encoded multipart boundary intact by sending the encoded body as a Blob.
      // Firefox can read the payload with blob() even when it does not expose Request.body.
      const body = request.method === 'GET' || request.method === 'HEAD' ? undefined : await request.blob();
      response = await nativeFetch(url, {method: request.method, headers, body: body?.size ? body : undefined, signal: request.signal,
        credentials: 'same-origin', mode: 'same-origin', cache: 'no-store', redirect: 'error'});
    } catch (error) {
      if (request.signal.aborted) throw error;
      lock('Die Übertragung ist fehlgeschlagen. Der Server-Speicherstand ist nicht bestätigt.'); throw error;
    }
    if (response.status === 401 || response.status === 403) {
      lock('Der Zugriff wurde beendet. Bitte erneut anmelden.'); throw new Error('Access revoked');
    }
    await probe(); // Also reject responses completed after another login/logout.
    if (response.headers.get('content-type')?.includes('application/json') && response.ok) {
      const value = await response.json();
      bindThumbnail(value.project);
      for (const record of value.projects ?? []) bindThumbnail(record);
      const out = new Headers(response.headers); out.delete('content-length');
      return new Response(JSON.stringify(value), {status: response.status, statusText: response.statusText, headers: out});
    }
    return response;
  };
  // A prior offline installation could bypass this online bootstrap. Remove only same-origin
  // root workers, never caches or user data. Require a fresh navigation after unregistering.
  async function onlineOnly() {
    if (!('serviceWorker' in navigator)) return;
    const registrations = await navigator.serviceWorker.getRegistrations();
    const roots = registrations.filter(r => r.scope === location.origin + '/');
    await Promise.all(roots.map(r => r.unregister()));
    if (navigator.serviceWorker.controller) throw new Error('Existing service worker controls page');
  }
  onlineGate = onlineOnly();
  if (!locked) void probe().catch(() => {});
  else void onlineGate.catch(() => {});
  window.addEventListener('offline', () => lock('Die Internetverbindung ist getrennt. Der Server-Speicherstand ist nicht bestätigt.'));
  window.addEventListener('focus', () => { if (!locked) void probe().catch(() => {}); });
  window.addEventListener('pageshow', event => {
    if (!locked) { if (event.persisted) root.dataset.ssoCad = 'pending'; void probe().catch(() => {}); }
  });
  document.addEventListener('visibilitychange', () => { if (!document.hidden && !locked) void probe().catch(() => {}); });
  setInterval(() => { if (!locked && !document.hidden) void probe().catch(() => {}); }, 30000);
})();
