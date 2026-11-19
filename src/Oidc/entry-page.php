<?php
declare(strict_types=1);

$escape = static fn(string $value): string => htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
$heading = $account ? 'Konto' : ($session === null ? 'Anmelden' : 'SSO-Test');
$showBackLink = $account;
$hasTemplates = $templateAccess !== null && ($templateAccess['teacher'] || $templateAccess['student']);
?>
<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title><?= $heading ?> · SSO Layerling</title>
  <link rel="stylesheet" href="/files.css">
</head>
<body class="sso-page">
<?php require dirname(__DIR__) . '/page-header.php'; ?>
<?php if ($session === null): ?>
<main class="sso-content sso-login">
  <section class="sso-card" aria-labelledby="login-heading">
    <h1 id="login-heading"><?= $heading ?></h1>
    <?php if (!$hasStorage): ?>
    <p>In diesem Test kannst du die Anmeldung prüfen.</p>
    <?php elseif (!$hasCad): ?>
    <p>Der Dateitest ist freigeschaltet. Nach der Anmeldung kannst du den persönlichen Speicher prüfen.</p>
    <?php endif; ?>
    <div class="sso-actions">
      <form method="post" action="/auth/start.php">
        <input type="hidden" name="csrf" value="<?= $escape($csrf) ?>">
        <button class="sso-button sso-button-primary sso-wrap" type="submit">Mit <?= $escape($provider) ?> anmelden</button>
      </form>
      <form method="post" action="/auth/logout.php">
        <input type="hidden" name="csrf" value="<?= $escape($csrf) ?>">
        <button class="sso-button" type="submit">Laufende Anmeldung abbrechen</button>
      </form>
    </div>
  </section>
</main>
<?php else: ?>
<main class="sso-content">
  <div class="sso-page-heading">
    <h1><?= $heading ?></h1>
    <form method="post" action="/auth/logout.php">
      <input type="hidden" name="csrf" value="<?= $escape($csrf) ?>">
      <button class="sso-button" type="submit">Lokal abmelden</button>
    </form>
  </div>
  <?php if ($canManagePermissions || $hasTemplates): ?>
  <nav class="sso-actions" aria-label="Kontonavigation">
    <?php if ($hasTemplates): ?><a class="sso-button" href="/vorlagen.php">CAD-Vorlagen</a><?php endif; ?>
    <?php if ($canManagePermissions): ?><a class="sso-button" href="/rechte.php">Rechte verwalten</a><?php endif; ?>
  </nav>
  <?php endif; ?>
  <section class="sso-card" aria-labelledby="account-heading">
    <h2 id="account-heading">Geprüfte Angaben des eigenen Kontos</h2>
    <p class="sso-wrap">Anmeldung über <?= $escape($provider) ?> erfolgreich.</p>
    <?php if ($profile !== null): ?>
    <?php $username = $diagnostic['preferredUsername'] ?? ''; ?>
    <dl class="sso-account-data">
      <dt>Name</dt>
      <dd class="sso-wrap"><?= $escape($profile['name'] ?? '–') ?></dd>
      <dt>Account</dt>
      <dd class="sso-wrap"><?= $escape(trim($username) === '' ? '–' : $username) ?></dd>
      <dt>Klasse</dt>
      <dd class="sso-wrap"><?= $escape($profile['classes'] === [] ? '–' : implode(', ', $profile['classes'])) ?></dd>
    </dl>
    <?php endif; ?>
    <details class="sso-account-details"<?= $account ? '' : ' open' ?>>
      <summary>Rollen und Gruppen</summary>
      <dl class="sso-account-data">
        <dt>Rollen</dt>
        <dd class="sso-wrap"><?= $escape($diagnostic['roles'] === [] ? '–' : implode(', ', $diagnostic['roles'])) ?></dd>
        <dt>Gruppenanzahl</dt>
        <dd><?= (int)$diagnostic['groupCount'] ?></dd>
        <?php if ($diagnosticGroups !== []): ?>
        <dt>Geprüfte Gruppen</dt>
        <dd>
          <ul class="sso-account-groups">
            <?php foreach ($diagnosticGroups as $group): ?>
            <li class="sso-wrap"><?= $escape($group['name']) ?> <code>(<?= $escape($group['id']) ?>)</code></li>
            <?php endforeach; ?>
          </ul>
        </dd>
        <?php endif; ?>
      </dl>
    </details>
    <?php if (!$hasStorage): ?><p>Diese Angaben schalten keine Fremddateirechte frei.</p><?php endif; ?>
  </section>
</main>
<?php endif; ?>
</body>
</html>
