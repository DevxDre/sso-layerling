# IServ-Client einrichten

Einen eigenen OIDC-Client für den Wrapper registrieren. Anbieter (`issuer`), Anwendung
(`origin`) und Callback (`redirectUri`) in der privaten Deployment-Konfiguration festlegen.
Die Paketierung übernimmt diese Adressen in die private App; der öffentliche Quellcode
enthält nur reservierte Beispieladressen. Endpunktpfade und Claim-Zuordnung stammen aus
dem [IServ-Standardprofil](../config/oidc-iserv.json).
Authorization Code mit PKCE S256, RS256 und den Scopes `openid`, `iserv:uuid`,
`iserv:groups`, `iserv:roles` und `profile` verwenden. Keine fremden Client-Secrets übernehmen.

Client-ID und Client-Secret in einer privaten `.env` außerhalb sämtlicher DocumentRoots
mit Dateirechten 0600 hinterlegen. `.env.example` enthält nur leere Variablen.
Die Client-ID ist kein Geheimnis, wird aber für die konkrete Installation privat konfiguriert.

Für die Paketierung `config/oidc.example.json` nach `config/deployment.local.json` kopieren,
Dateirechte 0600 setzen und registrierte Client-ID, Zieladressen sowie geprüfte Gruppenkennungen
eintragen. `issuer` und `origin` müssen reine HTTPS-Origins ohne Pfad, Zugangsdaten oder
Query sein. `redirectUri` muss exakt `origin` plus `/auth/callback.php` entsprechen.
Die JSON-Datei ist eine ignorierte Eingabe der Paketierung. Der Installer vergleicht
die paketierte Client-ID mit der privaten `.env`.

Echte Loginprüfungen, Rollenbelege und Installationsdetails ausschließlich intern dokumentieren.
