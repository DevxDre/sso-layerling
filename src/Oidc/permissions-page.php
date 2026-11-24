<?php
declare(strict_types=1);

use Sso\Layerling\PermissionRules;

$escape = static fn(string $value): string => htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
$effects = ['allow' => 'Erlauben', 'deny' => 'Verbieten'];
$operationLabels = ['read' => 'Lesen', 'write' => 'Bearbeiten', 'delete' => 'Löschen',
    'publish' => 'Vorlagen verteilen', 'mcp' => 'MCP-Token erstellen'];
$forms = [
    'accounts' => ['Zugriff auf fremde Konten', ['read', 'write', 'delete']],
    'features' => ['Vorlagen und MCP', ['publish', 'mcp']],
];
$action = $submitted['action'] ?? '';
$submittedOperation = $submitted['operation'] ?? '';
$activeForm = $action === 'save-rule'
    ? (in_array($submitted['ruleForm'] ?? null, ['accounts', 'features'], true)
        ? $submitted['ruleForm']
        : (in_array($submittedOperation, $forms['features'][1], true) ? 'features' : 'accounts'))
    : null;
$fieldMessages = [
    'actor' => 'Gib eine gültige Gruppe oder Rolle ein.',
    'owner' => 'Gib eine gültige Gruppe oder Rolle für die Zielkonten ein.',
    'operation' => 'Wähle ein Recht aus der Liste.',
    'effect' => 'Wähle „Erlauben“ oder „Verbieten“.',
    'pattern' => 'Gib ein gültiges Gruppenmuster ein, zum Beispiel makerspace oder /^makerspace$/i.',
];
$formError = 'Die Änderung konnte nicht gespeichert werden. Prüfe den aktuellen Stand und versuche es erneut.';
$submittedValue = static function (string $name, int $maxLength) use ($submitted, $error): string {
    $value = $submitted[$name] ?? null;
    // A namesake can now refer to a different group. Require a fresh selection.
    if (!is_string($value) || mb_strlen($value, 'UTF-8') > $maxLength
        || ($error === 'group-names' && str_starts_with($value, 'groups:'))) {
        return '';
    }
    return $value;
};
$invalidField = static fn(string $id): string =>
    ' aria-invalid="true" aria-describedby="' . $id . '-error" autofocus';
$backHref = $hasCad ? '/konto/' : '/';
$backLabel = $hasCad ? 'Zurück zum Konto' : 'Zur Anmeldung';
?>
<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Rechte verwalten · SSO Layerling</title>
  <link rel="stylesheet" href="/files.css">
</head>
<body class="sso-page">
<?php require dirname(__DIR__) . '/page-header.php'; ?>
<main class="sso-content">
  <h1>Rechte verwalten</h1>
  <?php if ($error === null && isset($_GET['saved'])): ?>
  <p class="sso-status" data-state="success" role="status">Änderung gespeichert.</p>
  <?php endif; ?>
  <?php if ($error !== null && !in_array($action, ['save-rule', 'remove-rule', 'add-pattern', 'remove-pattern'], true)): ?>
  <p class="sso-status" data-state="error" role="alert" tabindex="-1" autofocus><?= $escape($formError) ?></p>
  <?php endif; ?>
  <p>Bei mehreren passenden Regeln hat „Verbieten“ Vorrang. Für fremde Konten, Vorlagenverteilung und MCP-Token ist eine passende Freigabe erforderlich.</p>
  <p class="sso-field-help" id="selector-help">Wähle einen Gruppenaccount (<code>groups:</code>) oder eine Rolle (<code>role:</code>) aus den Vorschlägen. Eine Gruppen-ID kannst du mit <code>group:</code> direkt eingeben.</p>
  <datalist id="selectors">
    <?php foreach ($selectors as $selector => $label): ?>
    <option value="<?= $escape($selector) ?>"><?= $escape($label) ?></option>
    <?php endforeach; ?>
  </datalist>

  <div class="sso-rule-forms">
    <?php foreach ($forms as $form => [$heading, $operations]): ?>
    <?php
    $currentError = $form === $activeForm ? $error : null;
    $selectorFields = ['actor' => $form === 'accounts' ? 'Gruppe oder Rolle mit Zugriff' : 'Gruppe oder Rolle'];
    if ($form === 'accounts') {
        $selectorFields['owner'] = 'Gruppe oder Rolle der Zielkonten';
    }
    $savedOperation = $currentError === null ? $operations[0] : $submittedOperation;
    $savedEffect = $currentError === null ? 'allow' : ($submitted['effect'] ?? '');
    ?>
    <section class="sso-card" aria-labelledby="<?= $form ?>-heading">
      <h2 id="<?= $form ?>-heading"><?= $heading ?></h2>
      <?php if ($currentError === 'group-names'): ?>
      <p class="sso-status" data-state="error" role="alert" tabindex="-1" autofocus>Die Gruppenvorschläge haben sich geändert. Wähle die betroffenen Gruppenaccounts erneut aus.</p>
      <?php endif; ?>
      <form method="post" action="/rechte.php" class="sso-form-fields">
        <input type="hidden" name="csrf" value="<?= $escape($csrf) ?>">
        <input type="hidden" name="action" value="save-rule">
        <input type="hidden" name="ruleForm" value="<?= $form ?>">
        <input type="hidden" name="groupNamesVersion" value="<?= $escape($groupNamesVersion) ?>">
        <?php foreach ($selectorFields as $name => $label): ?>
        <?php $id = $form . '-' . $name; ?>
        <div class="sso-field">
          <label for="<?= $id ?>"><?= $label ?></label>
          <input id="<?= $id ?>" name="<?= $name ?>" list="selectors" maxlength="207" required
            value="<?= $escape($currentError === null ? '' : $submittedValue($name, 207)) ?>"
            <?= $currentError === $name ? $invalidField($id) : 'aria-describedby="selector-help"' ?>>
          <?php if ($currentError === $name): ?>
          <span class="sso-field-error" id="<?= $id ?>-error" role="alert"><?= $fieldMessages[$name] ?></span>
          <?php endif; ?>
        </div>
        <?php endforeach; ?>
        <?php foreach (['operation' => ['Recht', array_intersect_key($operationLabels, array_flip($operations)), $savedOperation],
            'effect' => ['Entscheidung', $effects, $savedEffect]] as $name => [$label, $options, $value]): ?>
        <?php
        $id = $form . '-' . $name;
        $hasReadingHelp = $form === 'accounts' && $name === 'operation';
        $attributes = $currentError === $name ? $invalidField($id)
            : ($hasReadingHelp ? ' aria-describedby="accounts-operation-help"' : '');
        ?>
        <div class="sso-field">
          <label for="<?= $id ?>"><?= $label ?></label>
          <select id="<?= $id ?>" name="<?= $name ?>" required<?= $attributes ?>>
            <?php if (!in_array($value, array_keys($options), true)): ?>
            <option value="" selected>Bitte auswählen</option>
            <?php endif; ?>
            <?php foreach ($options as $key => $text): ?>
            <option value="<?= $key ?>"<?= $value === $key ? ' selected' : '' ?>><?= $text ?></option>
            <?php endforeach; ?>
          </select>
          <?php if ($hasReadingHelp): ?>
          <span class="sso-field-help" id="accounts-operation-help">„Lesen“ erlaubt, Konten aufzulisten und deren Inhalte einzusehen.</span>
          <?php endif; ?>
          <?php if ($currentError === $name): ?>
          <span class="sso-field-error" id="<?= $id ?>-error" role="alert"><?= $fieldMessages[$name] ?></span>
          <?php endif; ?>
        </div>
        <?php endforeach; ?>
        <button class="sso-button sso-button-primary" type="submit">Regel speichern</button>
        <?php if ($currentError === 'form' || ($currentError === 'owner' && $form === 'features')): ?>
        <p class="sso-status" data-state="error" role="alert" tabindex="-1" autofocus><?= $escape($formError) ?></p>
        <?php endif; ?>
      </form>
    </section>
    <?php endforeach; ?>
  </div>

  <section class="sso-card" aria-labelledby="rules-heading">
    <h2 id="rules-heading">Gespeicherte Regeln</h2>
    <?php if ($error !== null && $action === 'remove-rule'): ?>
    <p class="sso-status" data-state="error" role="alert" tabindex="-1" autofocus><?= $escape($formError) ?></p>
    <?php endif; ?>
    <?php if ($rules === []): ?>
    <p>Es sind noch keine Regeln gespeichert.</p>
    <?php else: ?>
    <table class="sso-rule-table" role="table" aria-labelledby="rules-heading">
      <thead role="rowgroup"><tr role="row">
        <th role="columnheader" scope="col">Gruppe oder Rolle</th>
        <th role="columnheader" scope="col">Zielkonten</th>
        <th role="columnheader" scope="col">Recht</th>
        <th role="columnheader" scope="col">Entscheidung</th>
        <th role="columnheader" scope="col">Aktion</th>
      </tr></thead>
      <tbody role="rowgroup">
        <?php foreach ($rules as $key => $rule): ?>
        <?php
        $actor = $groupNames[$rule['actor']] ?? $rule['actor'];
        $owner = $groupNames[$rule['owner']] ?? ($rule['owner'] ?: '–');
        ?>
        <tr role="row">
          <td role="cell"><span class="sso-rule-label" aria-hidden="true">Gruppe oder Rolle</span><span class="sso-wrap"><?= $escape($actor) ?></span></td>
          <td role="cell"><span class="sso-rule-label" aria-hidden="true">Zielkonten</span><span class="sso-wrap"><?= $escape($owner) ?></span></td>
          <td role="cell"><span class="sso-rule-label" aria-hidden="true">Recht</span><?= $escape(PermissionRules::OPERATIONS[$rule['operation']]) ?></td>
          <td role="cell"><span class="sso-rule-label" aria-hidden="true">Entscheidung</span><?= $effects[$rule['effect']] ?></td>
          <td role="cell">
            <form method="post" action="/rechte.php">
              <input type="hidden" name="csrf" value="<?= $escape($csrf) ?>">
              <input type="hidden" name="key" value="<?= $escape($key) ?>">
              <input type="hidden" name="effect" value="<?= $escape($rule['effect']) ?>">
              <button class="sso-button sso-button-danger" name="action" value="remove-rule"
                aria-label="Regel entfernen – <?= $escape($actor . ', ' . $owner . ', ' . $operationLabels[$rule['operation']]) ?>">Entfernen</button>
            </form>
          </td>
        </tr>
        <?php endforeach; ?>
      </tbody>
    </table>
    <?php endif; ?>
  </section>

  <section class="sso-card" aria-labelledby="patterns-heading">
    <h2 id="patterns-heading">Gruppenfilter für die Vorlagenverteilung</h2>
    <p id="group-pattern-help">Schreibe reguläre Ausdrücke zwischen Schrägstriche. Darin steht <code>^</code> für den
      Anfang, <code>$</code> für das Ende und <code>|</code> für ODER. <code>/^makerspace$/</code> findet genau
      <code>makerspace</code>, <code>/^makerspace\..+/</code> findet etwa <code>makerspace.cad</code> und
      <code>/\.technik$/</code> findet etwa <code>kurs.technik</code>.</p>
    <p>Bei einfachen Mustern passt <code>makerspace</code> genau. Mit einem <code>^</code> am Ende passt
      <code>makerspace^</code> auf alle Gruppenaccounts, die mit <code>makerspace</code> beginnen.</p>
    <p>Für die Vorlagenverteilung genügt ein passendes Muster. Der Filter prüft den Gruppenaccount, ersatzweise
      die Gruppen-ID. Ohne Muster stehen alle eigenen Gruppen zur Auswahl.</p>
    <?php $patternInvalid = $action === 'add-pattern' && $error === 'pattern'; ?>
    <form method="post" action="/rechte.php">
      <input type="hidden" name="csrf" value="<?= $escape($csrf) ?>">
      <div class="sso-form-row">
        <label class="sso-field">Gruppenmuster
          <input id="group-pattern" name="pattern" maxlength="<?= PermissionRules::PATTERN_MAX_LENGTH ?>" placeholder="/^makerspace$/" required
            value="<?= $escape($action === 'add-pattern' ? $submittedValue('pattern', PermissionRules::PATTERN_MAX_LENGTH) : '') ?>"
            <?= $patternInvalid ? $invalidField('group-pattern') : 'aria-describedby="group-pattern-help"' ?>>
        </label>
        <button class="sso-button sso-button-primary" name="action" value="add-pattern">Hinzufügen</button>
      </div>
      <?php if ($patternInvalid): ?>
      <p class="sso-field-error" id="group-pattern-error" role="alert"><?= $fieldMessages['pattern'] ?></p>
      <?php elseif ($error !== null && $action === 'add-pattern'): ?>
      <p class="sso-status" data-state="error" role="alert" tabindex="-1" autofocus><?= $escape($formError) ?></p>
      <?php endif; ?>
    </form>
    <?php if ($error !== null && $action === 'remove-pattern'): ?>
    <p class="sso-status" data-state="error" role="alert" tabindex="-1" autofocus><?= $escape($formError) ?></p>
    <?php endif; ?>
    <?php if ($patterns !== []): ?>
    <ul class="sso-patterns" role="list">
      <?php foreach ($patterns as $pattern): ?>
      <li><form class="sso-form-row" method="post" action="/rechte.php">
        <input type="hidden" name="csrf" value="<?= $escape($csrf) ?>">
        <input type="hidden" name="pattern" value="<?= $escape($pattern) ?>">
        <code class="sso-wrap"><?= $escape($pattern) ?></code>
        <button class="sso-button sso-button-danger" name="action" value="remove-pattern"
          aria-label="Gruppenmuster <?= $escape($pattern) ?> entfernen">Entfernen</button>
      </form></li>
      <?php endforeach; ?>
    </ul>
    <?php endif; ?>
  </section>
</main>
</body>
</html>
