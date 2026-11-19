<?php
declare(strict_types=1);
$e = static fn(string $value): string => htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
$label = static fn(string $id): string => is_string($labels[$id] ?? null) && $labels[$id] !== '' ? $labels[$id] : $id;
$displayGroups = $access['publishGroups'];
usort($displayGroups, static fn(string $a, string $b): int => strnatcasecmp($label($a), $label($b)) ?: strcmp($a, $b));
$labelCounts = array_count_values(array_map($label, $displayGroups));
?>
<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="sso-csrf" content="<?= $e($csrf) ?>">
  <title>CAD-Vorlagen · SSO Layerling</title>
  <link rel="stylesheet" href="/files.css">
  <script src="/vorlagen.js" defer></script>
</head>
<body class="sso-page">
<?php require __DIR__ . '/page-header.php'; ?>
<main class="sso-content">
  <h1>CAD-Vorlagen</h1>
  <noscript>Zum Veröffentlichen und Kopieren ist JavaScript erforderlich.</noscript>
  <?php if ($access['teacher'] && $displayGroups !== []): ?>
  <section class="sso-card">
    <h2>Vorlage veröffentlichen</h2>
    <form id="publish-template" enctype="multipart/form-data">
      <div class="sso-form-fields">
        <label class="sso-field">Titel <input name="title" maxlength="100" required></label>
        <label class="sso-field">Kurzer Arbeitsauftrag <textarea name="instructions" rows="4" maxlength="2000" required></textarea></label>
        <label class="sso-field">Layerling-Datei (.lyl, bis 32 MiB) <input name="project" type="file" accept=".lyl" required></label>
        <fieldset class="sso-groups">
          <legend>Gruppen für diesen Arbeitsauftrag</legend>
          <?php foreach ($displayGroups as $id): ?>
          <label class="sso-group">
            <input type="checkbox" name="groups[]" value="<?= $e($id) ?>">
            <span class="sso-wrap"><?= $e($labelCounts[$label($id)] > 1 ? $label($id) . ' (' . $id . ')' : $label($id)) ?></span>
          </label>
          <?php endforeach; ?>
        </fieldset>
        <button class="sso-button sso-button-primary" type="submit">Veröffentlichen</button>
      </div>
      <p class="sso-status" data-template-status role="status"></p>
    </form>
  </section>
  <?php elseif ($access['teacher']): ?>
  <p class="sso-status">Für deine Gruppen ist aktuell keine Veröffentlichung möglich.</p>
  <?php endif; ?>
  <section class="sso-template-list">
    <h2><?= $access['teacher'] ? 'Meine veröffentlichten Vorlagen' : 'Verfügbare Vorlagen' ?></h2>
    <?php if ($entries === []): ?><p class="sso-status">Keine Vorlagen vorhanden.</p><?php endif; ?>
    <?php foreach ($entries as $entry): ?>
    <article class="sso-card">
      <h3 class="sso-wrap"><?= $e($entry['title']) ?></h3>
      <p class="sso-instructions sso-wrap"><?= $e($entry['instructions']) ?></p>
      <?php if ($canCopy($entry)): ?>
      <form data-copy-template="<?= $e($entry['id']) ?>">
        <div class="sso-form-row">
          <label class="sso-field">Entwurfsname <input name="name" value="<?= $e($entry['title']) ?>" maxlength="100" required></label>
          <button class="sso-button sso-button-primary" type="submit">Eigene Kopie erstellen</button>
        </div>
        <p class="sso-status" data-template-status role="status"></p>
      </form>
      <?php else: ?>
      <p class="sso-wrap">Zielgruppen: <?= $e(implode(', ', array_map($label, $entry['groups']))) ?></p>
      <div>
        <button class="sso-button sso-button-danger" type="button" data-withdraw-template="<?= $e($entry['id']) ?>">Vorlage zurückziehen</button>
        <p class="sso-status" data-template-status role="status"></p>
      </div>
      <?php endif; ?>
    </article>
    <?php endforeach; ?>
  </section>
</main>
</body>
</html>
