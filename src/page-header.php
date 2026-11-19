<header class="sso-topbar">
  <div class="sso-topbar-inner">
    <span class="sso-brand">
      <?php if ($hasCad): ?>
      <img src="/assets/layerling/layerling-logo.svg" width="40" height="40" alt="">
      <?php endif; ?>
      Layerling
    </span>
    <?php if ($showBackLink ?? true): ?>
    <a class="sso-button" href="<?= htmlspecialchars($backHref ?? ($hasCad ? '/cad.php' : '/'), ENT_QUOTES, 'UTF-8') ?>"><?= htmlspecialchars($backLabel ?? ($hasCad ? 'Zum CAD-Editor' : 'Zur Anmeldung'), ENT_QUOTES, 'UTF-8') ?></a>
    <?php endif; ?>
  </div>
</header>
