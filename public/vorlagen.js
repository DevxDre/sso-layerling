'use strict';

(() => {
  const csrf = document.querySelector('meta[name="sso-csrf"]').content;
  const status = document.getElementById('status');
  let busy = false;

  async function request(url, options = {}) {
    const response = await fetch(url, {
      ...options,
      credentials: 'same-origin',
      cache: 'no-store',
      redirect: 'error',
      headers: {...options.headers, 'X-SSO-CSRF': csrf},
    });
    if (response.ok) return response;
    const data = await response.json().catch(() => ({}));
    const messages = {
      invalid_template_groups: 'Bitte mindestens eine IServ-Gruppe auswählen.',
      template_group_not_allowed: 'Diese Gruppe steht nicht mehr zur Auswahl. Bitte die Seite neu laden.',
      invalid_template_file: 'Bitte eine gültige .lyl-Datei wählen.',
      invalid_template_text: 'Bitte Titel und Arbeitsauftrag prüfen.',
      template_catalog_full: 'Der Vorlagenbereich ist voll.',
      template_not_found: 'Diese Vorlage ist nicht mehr verfügbar.',
      401: 'Die Sitzung ist abgelaufen. Bitte erneut anmelden.',
      403: 'Die Anmeldung oder Berechtigung hat sich geändert. Bitte die Seite neu laden.',
      409: 'Der Entwurfsname ist bereits belegt oder wird gerade verwendet. Bitte einen anderen Namen wählen.',
      413: 'Die Datei überschreitet das Upload-Limit.',
    };
    throw new Error(messages[data.error] || messages[response.status] || 'Der Server konnte die Aktion nicht abschließen.');
  }

  function action(handler) {
    return async event => {
      event.preventDefault();
      if (busy) return;
      busy = true;
      status.textContent = 'Wird verarbeitet …';
      try {
        await handler(event.currentTarget);
      } catch (error) {
        status.textContent = error instanceof TypeError
          ? 'Die Verbindung ist unterbrochen. Bitte den Stand prüfen, bevor du es erneut versuchst.'
          : error.message;
      } finally {
        busy = false;
      }
    };
  }

  document.getElementById('publish-template')?.addEventListener('submit', action(async form => {
    await request('/vorlagen.php?action=publish', {method: 'POST', body: new FormData(form)});
    location.reload();
  }));

  for (const button of document.querySelectorAll('[data-withdraw-template]')) {
    button.addEventListener('click', action(async button => {
      if (!window.confirm('Vorlage zurückziehen? Bereits erstellte Kopien bleiben erhalten.')) {
        status.textContent = '';
        return;
      }
      await request('/vorlagen.php?action=withdraw', {
        method: 'POST',
        body: new URLSearchParams({id: button.dataset.withdrawTemplate}),
      });
      location.reload();
    }));
  }

  for (const form of document.querySelectorAll('[data-copy-template]')) {
    form.addEventListener('submit', action(async form => {
      const name = new FormData(form).get('name').trim();
      if (!name) throw new Error('Bitte einen Entwurfsnamen eingeben.');
      const template = await request('/vorlagen.php?' + new URLSearchParams({id: form.dataset.copyTemplate}));
      const response = await request('/store.php?' + new URLSearchParams({fileName: name}), {
        method: 'POST',
        headers: {'If-None-Match': '*', 'Content-Type': 'application/vnd.layerling.project+zip'},
        body: await template.blob(),
      });
      const {project} = await response.json();
      status.textContent = '„' + project.name + '“ liegt jetzt in deinen eigenen Dateien.';
    }));
  }
})();
