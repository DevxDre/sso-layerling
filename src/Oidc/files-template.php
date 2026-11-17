<!doctype html>
<html lang="de">
<meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>SSO Layerling – Dateien</title>
<link rel="stylesheet" href="/files.css"><script src="/files.js" defer></script>
<main>
<noscript>Der Dateibereich benötigt JavaScript. Die Anmeldung bleibt über die Startseite erreichbar.</noscript>
<header><h1>SSO Layerling – Dateien</h1><a href="<?= $hasCad ? '/cad.php' : '/' ?>"><?= $hasCad ? 'Zum CAD-Editor' : 'Zur Anmeldung' ?></a></header>
<p>Projekte hochladen, herunterladen und verwalten.</p>
<form method="post" action="/auth/logout.php"><input type="hidden" name="csrf" value="<?= htmlspecialchars($logoutCsrf, ENT_QUOTES, 'UTF-8') ?>"><button>Lokal abmelden</button></form>
<p id="status" role="status" aria-live="polite">Dateien werden geladen …</p>
<label>Speicherbereich <select id="owner" disabled></select></label>
<button id="refresh" type="button">Aktualisieren</button>
<nav aria-label="Ordner"><button id="up" disabled>Übergeordneter Ordner</button> <span id="path">/</span></nav>
<form id="upload"><label>Layerling-Projekt <input id="project" type="file" accept=".lyl" required></label> <button>Hochladen</button></form>
<form id="folder"><label>Neuer Ordner <input id="folderName" maxlength="100" required></label> <button>Ordner anlegen</button></form>
<table><thead><tr><th>Name</th><th>Aktionen</th></tr></thead><tbody id="entries"></tbody></table>
</main></html>
