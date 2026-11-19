"use strict";
(() => {
  const owner = document.getElementById("owner");
  const status = document.getElementById("status");
  const entries = document.getElementById("entries");
  const upload = document.getElementById("upload");
  const folder = document.getElementById("folder");
  const up = document.getElementById("up");
  const folderHeading = document.getElementById("folder-heading");
  const pathLabel = document.getElementById("path");
  let csrf = "", path = "", owners = [], projects = [], serial = 0;
  const message = text => { status.textContent = text; };
  function url(query = {}, selected = owner.value, location = path) {
    return "/store.php?" + new URLSearchParams({ _sso_owner: selected, path: location, ...query });
  }
  async function api(target, options = {}) {
    const response = await fetch(target, { credentials: "same-origin", cache: "no-store", ...options });
    const data = await response.json();
    if (!response.ok) {
      if (response.status === 401) {
        entries.replaceChildren(); owner.disabled = true;
        upload.querySelector("button").disabled = true; folder.querySelector("button").disabled = true;
      }
      const errors = { 401: "Sitzung abgelaufen. Bitte auf der Startseite erneut anmelden.",
        403: "Für diese Aktion fehlen die Rechte. Bitte die Liste aktualisieren.",
        409: "Die Datei wurde inzwischen geändert. Bitte neu laden.",
        413: "Die Datei überschreitet das Upload-Limit des Servers.",
        503: "Der Speicher ist vorübergehend nicht verfügbar." };
      throw new Error(errors[response.status] || "Die Aktion konnte nicht ausgeführt werden (" + response.status + ").");
    }
    return data;
  }
  async function change(query, method = "POST", body, revision, selected = owner.value, location = path) {
    const headers = { "X-SSO-CSRF": csrf };
    if (body) headers["Content-Type"] = "application/vnd.layerling.project+zip";
    if (revision) headers["If-Match"] = '"' + revision + '"';
    await api(url(query, selected, location), { method, headers, body });
    await load();
  }
  const action = fn => async event => {
    event.preventDefault();
    try { await fn(); } catch (error) { message(error instanceof TypeError ? "Verbindung unterbrochen. Bitte erneut versuchen." : error.message); }
  };
  function button(label, fn, modifier = "") {
    const element = document.createElement("button");
    element.textContent = label; element.type = "button";
    element.className = "sso-button";
    if (modifier) element.classList.add(modifier);
    element.addEventListener("click", action(fn)); return element;
  }
  function addEntry(name, actions) {
    const entry = document.createElement("li");
    entry.className = "sso-card sso-file-entry";
    const title = document.createElement("span");
    title.className = "sso-file-name sso-wrap";
    title.textContent = name;
    const controls = document.createElement("div");
    controls.className = "sso-actions";
    for (const control of actions) {
      control.setAttribute("aria-label", control.textContent + " – " + name);
      controls.append(control);
    }
    entry.append(title, controls);
    entries.append(entry);
  }
  function renderPath(location) {
    pathLabel.replaceChildren("/");
    for (const [index, segment] of location.split("/").entries()) {
      if (index > 0) pathLabel.append("/", document.createElement("wbr"));
      pathLabel.append(segment);
    }
  }
  async function load(focusFolder = false) {
    const turn = ++serial;
    message("Dateien werden geladen …");
    entries.replaceChildren(); owner.disabled = true; up.disabled = true;
    upload.querySelector("button").disabled = true; folder.querySelector("button").disabled = true;
    const session = await api("/session.php");
    const available = (await api("/owners.php")).owners;
    if (turn !== serial) return;
    csrf = session.csrfToken; owners = available;
    const previous = owner.value;
    owner.replaceChildren();
    for (const item of owners) {
      const option = document.createElement("option"); option.value = item.userId; option.textContent = item.label; owner.append(option);
    }
    if (owners.some(item => item.userId === previous)) owner.value = previous;
    else path = "";
    const current = owners.find(item => item.userId === owner.value);
    if (!current) throw new Error("Kein Speicherbereich verfügbar.");
    const selected = owner.value, location = path;
    const list = await api(url({}, selected, location));
    if (turn !== serial || owner.value !== selected || path !== location) return;
    owner.disabled = false;
    projects = list.projects; entries.replaceChildren();
    renderPath(location); up.disabled = location === "";
    upload.querySelector("button").disabled = !current.canWrite;
    folder.querySelector("button").disabled = !current.canWrite;
    for (const item of list.folders) {
      const next = location ? location + "/" + item.name : item.name;
      const controls = [button("Öffnen", async () => { path = next; await load(true); })];
      if (current.canDelete) controls.push(button("Löschen", async () => {
        if (window.confirm("Ordner „" + item.name + "“ mit Inhalt unwiderruflich löschen?")) {
          await change({ path: next, deleteFolder: "1", recursive: "1" }, "DELETE", undefined, undefined, selected, location);
        }
      }, "sso-button-danger"));
      addEntry("Ordner " + item.name, controls);
    }
    for (const item of projects) {
      const download = document.createElement("a"); download.textContent = "Herunterladen";
      download.className = "sso-button";
      download.href = url({ fileName: item.fileName }, selected, location); download.download = item.fileName;
      const controls = [download];
      if (current.canWrite) controls.push(button("Umbenennen", async () => {
        const name = window.prompt("Neuer Dateiname", item.fileName);
        if (name && name !== item.fileName) await change({ fileName: item.fileName, renameFileTo: name }, "POST", undefined, item.revision, selected, location);
      }));
      if (current.canDelete) controls.push(button("Löschen", async () => {
        if (window.confirm("Datei „" + item.fileName + "“ unwiderruflich löschen?")) await change({ fileName: item.fileName }, "DELETE", undefined, item.revision, selected, location);
      }, "sso-button-danger"));
      addEntry(item.fileName, controls);
    }
    message((projects.length + list.folders.length ? "Liste geladen." : "Dieser Ordner ist leer.") + (current.canDelete ? "" : " Löschen ist in diesem Bereich nicht erlaubt."));
    if (focusFolder && document.activeElement === document.body) folderHeading.focus();
  }
  document.getElementById("refresh").addEventListener("click", action(load));
  owner.addEventListener("change", action(async () => { path = ""; await load(); }));
  up.addEventListener("click", action(async () => { path = path.split("/").slice(0,-1).join("/"); await load(true); }));
  upload.addEventListener("submit", action(async () => {
    const file = document.getElementById("project").files[0]; if (!file) return;
    const existing = projects.find(item => item.fileName === file.name);
    if (existing && !window.confirm("Vorhandene Datei „" + file.name + "“ ersetzen?")) return;
    await change({ fileName: file.name }, "POST", file, existing?.revision);
    upload.reset();
  }));
  folder.addEventListener("submit", action(async () => {
    const name = document.getElementById("folderName").value.trim(); if (!name) return;
    await change({ folder: name }); folder.reset();
  }));
  load().catch(error => message(error instanceof TypeError ? "Verbindung unterbrochen. Bitte erneut versuchen." : error.message));
})();
