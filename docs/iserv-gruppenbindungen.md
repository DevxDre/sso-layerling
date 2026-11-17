# Private IServ-Gruppenbindungen

Dateirechte beruhen auf exakt geprüften Gruppenkennungen aus validierten SSO-Claims.
Gruppennamen und `ROLE_ADMIN` allein gewähren keine Fremddateirechte.
Die Betreuung darf Schülerdateien lesen und bearbeiten; Admins dürfen zusätzlich löschen.
`ROLE_STUDENT` dient zur Schülerklassifikation, bei fehlenden Rollen können ausdrücklich
konfigurierte Schülergruppen greifen. Maßgeblich ist das [Berechtigungsmodell](sso-berechtigungsmodell.md).

`config/oidc.example.json` enthält ausschließlich synthetische Gruppenkennungen.
Für ein gehostetes Paket eine private `config/deployment.local.json` mit bestätigten
Gruppen und registrierter Client-ID ausdrücklich über `--deployment-config` übergeben.
Keine Gruppenkennungen raten. Secrets bleiben ausschließlich in der privaten `.env`.

Lokale Prüfungen verwenden `maker-fixture` und `admin-fixture`.
Die internen echten Zuordnungen und Loginbelege werden separat und ignoriert aufbewahrt.
