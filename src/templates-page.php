<?php
declare(strict_types=1);
$e = static fn(string $value): string => htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
$label = static fn(string $id): string => is_string($labels[$id] ?? null) && $labels[$id] !== '' ? $labels[$id] : $id;
$displayGroups = $access['groups'];
usort($displayGroups, static fn(string $a, string $b): int => strnatcasecmp($label($a), $label($b)) ?: strcmp($a, $b));
$labelCounts = array_count_values(array_map($label, $displayGroups));
?>
<!doctype html>
<html lang="de">
<meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta name="sso-csrf" content="<?= $e($csrf) ?>">
<title>CAD-Vorlagen</title>
<link rel="stylesheet" href="/files.css"><script src="/vorlagen.js" defer></script>
<main>
<header><h1>CAD-Vorlagen</h1><a href="<?= $hasCad ? '/cad.php' : '/' ?>"><?= $hasCad ? 'Zum CAD-Editor' : 'Zur Anmeldung' ?></a></header>
<noscript>Zum Veröffentlichen und Kopieren ist JavaScript erforderlich.</noscript>
<p id="status" role="status" aria-live="polite"></p>
<?php if ($access['teacher'] && $displayGroups !== []): ?>
<section>
<h2>Vorlage veröffentlichen</h2>
<form id="publish-template" enctype="multipart/form-data">
  <p><label>Titel <input name="title" maxlength="100" required></label></p>
  <p><label>Kurzer Arbeitsauftrag<br><textarea name="instructions" rows="4" maxlength="2000" required></textarea></label></p>
  <p><label>Layerling-Datei (.lyl, bis 32 MiB) <input name="project" type="file" accept=".lyl" required></label></p>
  <fieldset>
    <legend>Gruppen für diesen Arbeitsauftrag</legend>
    <?php foreach ($displayGroups as $id): ?>
      <div><label><input type="checkbox" name="groups[]" value="<?= $e($id) ?>"> <?= $e($labelCounts[$label($id)] > 1 ? $label($id) . ' (' . $id . ')' : $label($id)) ?></label></div>
    <?php endforeach; ?>
  </fieldset>
  <p><button type="submit">Veröffentlichen</button></p>
</form>
</section>
<?php elseif ($access['teacher']): ?>
<p>Für die Veröffentlichung ist mindestens eine Gruppe aus deiner Anmeldung erforderlich.</p>
<?php endif; ?>
<section>
<h2><?= $access['teacher'] ? 'Meine veröffentlichten Vorlagen' : 'Verfügbare Vorlagen' ?></h2>
<?php if ($entries === []): ?><p>Keine Vorlagen vorhanden.</p><?php endif; ?>
<?php foreach ($entries as $entry): ?>
<article>
  <h3><?= $e($entry['title']) ?></h3>
  <p><?= nl2br($e($entry['instructions'])) ?></p>
  <?php if ($canCopy($entry)): ?>
  <form data-copy-template="<?= $e($entry['id']) ?>">
    <label>Entwurfsname <input name="name" value="<?= $e($entry['title']) ?>" maxlength="100" required></label>
    <button type="submit">Eigene Kopie erstellen</button>
  </form>
  <?php else: ?>
  <p>Zielgruppen: <?= $e(implode(', ', array_map($label, $entry['groups']))) ?></p>
  <button type="button" data-withdraw-template="<?= $e($entry['id']) ?>">Vorlage zurückziehen</button>
  <?php endif; ?>
</article>
<?php endforeach; ?>
</section>
</main>
</html>
