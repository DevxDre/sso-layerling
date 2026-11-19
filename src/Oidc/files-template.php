<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Dateien · SSO Layerling</title>
  <link rel="stylesheet" href="/files.css">
  <script src="/files.js" defer></script>
</head>
<body class="sso-page">
<?php require dirname(__DIR__) . '/page-header.php'; ?>
<main class="sso-content">
  <div class="sso-page-heading">
    <h1>Dateien</h1>
    <form method="post" action="/auth/logout.php">
      <input type="hidden" name="csrf" value="<?= htmlspecialchars($logoutCsrf, ENT_QUOTES, 'UTF-8') ?>">
      <button class="sso-button">Lokal abmelden</button>
    </form>
  </div>
  <noscript>Der Dateibereich benötigt JavaScript. Die Anmeldung bleibt über die Startseite erreichbar.</noscript>
  <div class="sso-card">
    <div class="sso-form-row">
      <label class="sso-field">Speicherbereich <select id="owner" disabled></select></label>
      <button class="sso-button" id="refresh" type="button">Aktualisieren</button>
    </div>
    <nav class="sso-folder-nav" aria-label="Ordner">
      <h2 class="sso-folder-heading" id="folder-heading" tabindex="-1">Ordner <span class="sso-wrap" id="path">/</span></h2>
      <button class="sso-button" id="up" type="button" disabled>Eine Ebene nach oben</button>
    </nav>
  </div>
  <div class="sso-file-tools">
    <form class="sso-card sso-form-row" id="upload">
      <label class="sso-field">Layerling-Datei (.lyl) <input id="project" type="file" accept=".lyl" required></label>
      <button class="sso-button sso-button-primary" disabled>Hochladen</button>
    </form>
    <form class="sso-card sso-form-row" id="folder">
      <label class="sso-field">Name des neuen Ordners <input id="folderName" maxlength="100" required></label>
      <button class="sso-button" disabled>Ordner anlegen</button>
    </form>
  </div>
  <p class="sso-status" id="status" role="status"></p>
  <ul class="sso-file-list" id="entries" role="list" aria-label="Inhalt des Ordners"></ul>
</main>
</body>
</html>
