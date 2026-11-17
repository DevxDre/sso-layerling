# SSO-Teststand und Paketierung

Der Wrapper prüft OIDC-Anmeldungen mit PKCE S256, RS256, Nonce, State und gebundener
UserInfo. Tokens werden nicht dauerhaft gespeichert. Sitzung, Principal-Register,
Audit und Projekte liegen außerhalb der öffentlichen Dateien.
Der historische Speicherprototyp bleibt auf Loopback und PHP-CLI-Server begrenzt.

## Lokale Prüfungen

PHP 8.4 ausdrücklich wählen, beispielsweise `/opt/homebrew/opt/php@8.4/bin/php`.

```bash
/opt/homebrew/opt/php@8.4/bin/php tests/oidc_test.php
python3 -W error tests/integrated_storage_http_test.py --php /opt/homebrew/opt/php@8.4/bin/php --layerling ../layerling --alternate-profile
python3 -W error tests/deployment_config_test.py --php /opt/homebrew/opt/php@8.4/bin/php --layerling ../layerling
python3 -W error tests/sso_http_test.py --php /opt/homebrew/opt/php@8.4/bin/php
python3 -W error tests/install_sso_test.py --php /opt/homebrew/opt/php@8.4/bin/php
python3 -W error tests/integrated_storage_http_test.py --php /opt/homebrew/opt/php@8.4/bin/php --layerling ../layerling
python3 -W error tests/install_storage_test.py --php /opt/homebrew/opt/php@8.4/bin/php --layerling ../layerling
```

## Gehostete Pakete

Nur einen geprüften, sauberen Quellcommit paketieren. Die eigene Client-ID und Gruppenbindungen
in `config/deployment.local.json` konfigurieren (0600, ignoriert). Client-Secret ausschließlich
in einer separaten privaten `.env` halten. Beispielgruppen werden für Deployments abgelehnt.

```bash
python3 scripts/package-sso-test.py --output build/sso-test --deployment-config config/deployment.local.json
python3 scripts/package-sso-test.py --output build/storage-test --layerling ../layerling --deployment-config config/deployment.local.json
```

Die Paketierung schreibt das validierte [OIDC-Profil](oidc-profile.md) in die private App.
Dort werden Issuer, Origin und Claim-Zuordnung zur Laufzeit geladen. Der Callback entspricht
dem konfigurierten Origin mit `/auth/callback.php`. Für Installation den zum Paket gehörenden Installer unter
`private/app/scripts/install-sso-test.php` verwenden, damit Zielprüfungen und App übereinstimmen. Interne Dokumente,
`.env`, Testsitzungen und Nutzerprojekte gehören nicht dazu. Das Installer-Ziellayout ist im
Quellcode festgelegt; Änderungen daran separat prüfen. Die feste Client-ID im Quellcode wurde
durch einen Vergleich mit der explizit paketierten Zielkennung ersetzt.
Lokale Python-Testaufrufe verwenden ohne private Konfiguration synthetische Beispielgruppen;
diese Pakete sind durch die fehlende registrierte Zielkennung nicht für gehostete Installation freigegeben.

Für CAD siehe [CAD-Integration](cad-integration.md). SSH-Zugang, Upload, konkrete
Installationen, Paketstand und Rücksetzung ausschließlich intern dokumentieren.
Vor Aktivierung die Installer-, API- und Rollenprüfungen abschließen; bestehende
Nutzerprojekte und private Laufzeitdaten erhalten.
