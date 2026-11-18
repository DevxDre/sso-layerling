<?php
declare(strict_types=1);

use Sso\Layerling\PermissionRules;

$escape = static fn(string $value): string => htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
$effects = ['allow' => 'Erlauben', 'deny' => 'Verbieten'];
$back = $this->hasCad() ? '/konto/' : '/';
?>
<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width">
<title>Rechte verwalten · SSO Layerling</title>
<link rel="stylesheet" href="/files.css">
</head>
<body>
<main>
<header><h1>Rechte verwalten</h1><a href="<?= $back ?>">Zurück zum Konto</a></header>
<?php if (isset($_GET['saved'])): ?><p role="status">Änderung gespeichert.</p><?php endif; ?>
<?php if ($invalid): ?><p role="alert">Die Änderung konnte nicht gespeichert werden. Prüfe die Eingaben und die angezeigten Regeln.</p><?php endif; ?>
<p>Bei mehreren passenden Regeln hat „Verbieten“ Vorrang. Ohne passende Regel gilt die bisherige Konfiguration.</p>

<section aria-labelledby="accounts-heading">
<h2 id="accounts-heading">Zugriff auf fremde Konten</h2>
<form method="post" action="/rechte.php">
  <input type="hidden" name="csrf" value="<?= $escape($csrf) ?>">
  <input type="hidden" name="action" value="save-rule">
  <p><label>Gruppe oder Rolle mit Zugriff <input name="actor" list="selectors" maxlength="134" required></label></p>
  <p><label>Gruppe oder Rolle der Zielkonten <input name="owner" list="selectors" maxlength="134" required></label></p>
  <p><label>Recht
    <select name="operation">
      <?php foreach (['read', 'write', 'delete'] as $operation): ?>
        <option value="<?= $operation ?>"><?= $escape(PermissionRules::OPERATIONS[$operation]) ?></option>
      <?php endforeach; ?>
    </select>
  </label></p>
  <label>Entscheidung <select name="effect"><option value="allow">Erlauben</option><option value="deny">Verbieten</option></select></label>
  <button>Regel speichern</button>
</form>
</section>

<section aria-labelledby="features-heading">
<h2 id="features-heading">Vorlagen und MCP</h2>
<form method="post" action="/rechte.php">
  <input type="hidden" name="csrf" value="<?= $escape($csrf) ?>">
  <input type="hidden" name="action" value="save-rule">
  <p><label>Gruppe oder Rolle <input name="actor" list="selectors" maxlength="134" required></label></p>
  <p><label>Recht
    <select name="operation">
      <?php foreach (['publish', 'mcp'] as $operation): ?>
        <option value="<?= $operation ?>"><?= $escape(PermissionRules::OPERATIONS[$operation]) ?></option>
      <?php endforeach; ?>
    </select>
  </label></p>
  <label>Entscheidung <select name="effect"><option value="allow">Erlauben</option><option value="deny">Verbieten</option></select></label>
  <button>Regel speichern</button>
</form>
</section>
<p>Wähle eine bekannte Kennung oder gib sie mit <code>group:</code> für Gruppen oder <code>role:</code> für Rollen ein.</p>
<datalist id="selectors">
  <?php foreach ($selectors as $selector => $label): ?>
    <option value="<?= $escape($selector) ?>"><?= $escape($label) ?></option>
  <?php endforeach; ?>
</datalist>

<section aria-labelledby="rules-heading">
<h2 id="rules-heading">Gespeicherte Regeln</h2>
<?php if ($rules === []): ?>
  <p>Es sind noch keine Regeln gespeichert.</p>
<?php else: ?>
<div class="permissions-table" tabindex="0" role="region" aria-labelledby="rules-heading">
<table>
<thead><tr><th scope="col">Gruppe oder Rolle</th><th scope="col">Zielkonten</th><th scope="col">Recht</th><th scope="col">Entscheidung</th><th scope="col">Aktion</th></tr></thead>
<tbody>
<?php foreach ($rules as $key => $rule): ?>
<tr>
  <td><?= $escape($rule['actor']) ?></td>
  <td><?= $escape($rule['owner'] ?: '–') ?></td>
  <td><?= $escape(PermissionRules::OPERATIONS[$rule['operation']]) ?></td>
  <td><?= $escape($effects[$rule['effect']]) ?></td>
  <td><form method="post" action="/rechte.php">
    <input type="hidden" name="csrf" value="<?= $escape($csrf) ?>">
    <input type="hidden" name="key" value="<?= $escape($key) ?>">
    <input type="hidden" name="effect" value="<?= $escape($rule['effect']) ?>">
    <button name="action" value="remove-rule">Entfernen</button>
  </form></td>
</tr>
<?php endforeach; ?>
</tbody>
</table>
</div>
<?php endif; ?>
</section>

<section aria-labelledby="patterns-heading">
<h2 id="patterns-heading">Gruppenfilter für die Vorlagenverteilung</h2>
<p><code>makerspace^</code> findet eigene Gruppen, deren Gruppenaccount mit <code>makerspace</code> beginnt. Ohne <code>^</code> muss der Gruppenaccount genau übereinstimmen. Liefert der Anmeldeserver keinen Gruppenaccount, gilt die Gruppen-ID. Eine leere Filterliste zeigt alle eigenen Gruppen.</p>
<form method="post" action="/rechte.php">
  <input type="hidden" name="csrf" value="<?= $escape($csrf) ?>">
  <label>Gruppenmuster <input name="pattern" maxlength="129" placeholder="makerspace^" required></label>
  <button name="action" value="add-pattern">Hinzufügen</button>
</form>
<?php if ($patterns !== []): ?>
<ul class="permission-patterns">
<?php foreach ($patterns as $pattern): ?>
  <li><form method="post" action="/rechte.php">
    <input type="hidden" name="csrf" value="<?= $escape($csrf) ?>">
    <input type="hidden" name="pattern" value="<?= $escape($pattern) ?>">
    <code><?= $escape($pattern) ?></code>
    <button name="action" value="remove-pattern" aria-label="Gruppenmuster <?= $escape($pattern) ?> entfernen">Entfernen</button>
  </form></li>
<?php endforeach; ?>
</ul>
<?php endif; ?>
</section>
</main>
</body>
</html>
