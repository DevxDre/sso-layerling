# Integrierter SSO- und Dateitest

Stand: 04.11.2026. Umsetzung nach Nutzerauftrag „Dann den nächsten Schritt umsetzen“.
Eigener Datei-Teststand, noch kein CAD-Editor und keine Produktionsfreigabe.
Layerling bleibt unverändert am geprüften Pin; keine neue Upstream-Version übernommen.

## Verhalten und Sitzungsgrenze

Der geprüfte OIDC-Callback schreibt den eigenen Principal mit den bestätigten Gruppen
und `ROLE_STUDENT`, dann erzeugt er eine neue gemeinsame native Sitzung für Anmeldung
und Speicher. Kennung: Cookie `SSO_LAYERLING_SESSION`, private Datei unter `sessions/`,
serverseitiger Geltungsbereich `sso-storage-v1`. Die bisherigen Portal-Cookies und
unmarkierte Prototypsitzungen werden für Dateizugriffe nicht akzeptiert. Nach dem ersten
Umstieg müssen Nutzer erneut anmelden; stabile Eigentümer-IDs bleiben erhalten.

`NativeSession` bündelt ID-/CSRF-/Zeit-/Geltungsbereichsprüfung, Cookie-Einstellungen,
Ausgabe und Widerruf. Fristen: `StorageConfig::ABSOLUTE_SECONDS` und `StorageConfig::IDLE_SECONDS` sind maßgeblich.
Secure, HttpOnly, SameSite=Lax, kein Domain-Attribut oder URL-Sitzungs-ID. HTTP-Ausnahme
nur für isolierte Loopback-/CLI-Server-Prüfungen. Der ursprüngliche Prototyp bleibt
weiter separat auf Loopback beschränkt; kein HTTP-Parameter schaltet diesen Schutz um.

Lokale Abmeldung läuft für den integrierten Stand ausschließlich über den geschützten
POST `/auth/logout.php`: zuerst Login-Kontext sperren/stornieren, dann native Sitzung
leeren. Damit erzeugt ein später Callback nach Abbruch keine neue Sitzung. Der Sitzungs-
Lock wird für angenommene Dateioperationen gehalten; nach abgeschlossenem Logout oder
Widerruf dürfen wartende neue Anfragen keine authentifizierten Daten mehr lesen.
`/session.php` ist im integrierten Stand GET-only; der alte Prototyp behält seinen bisherigen
POST-Vertrag. Ein zweiter Logout-Pfad ohne Kontextstornierung wird nicht eingeführt.

## Eigene private Konfiguration

Die explizite Paketoption `--layerling` erzeugt den Pakettyp `sso-layerling-storage-test`.
Ohne diese Option entsteht weiterhin das reine Loginportal. Kein automatischer Wechsel.
Die aktive, nicht geheime Dateitest-Konfiguration liegt in `private/app/storage.json`,
mit festem Ursprung, öffentlichem Zielpfad, `sso-last-login`, bestätigten Gruppenkennungen,
Schülerrolle und Testfristen. Der Loader prüft Typen, festen Ursprung, Pfade und HTTPS.

`config/oidc.example.json` enthält ausschließlich synthetische Zuordnungen für lokale Tests.
Gehostete Pakete lesen ausdrücklich die private `config/deployment.local.json` über
`--deployment-config` und übernehmen nur die benötigten Metadaten in die aktive Testkonfiguration.
Die private `.env` bleibt unverändert separat und wird niemals paketiert. Die Datei-APIs
laden kein Client-Secret. OIDC verwendet die bereits eingerichtete private `.env`.

Voraussetzungen bleiben PHP 8.4 mit session/curl/openssl/json/zip/fileinfo/mbstring.
Die drei zusätzlichen Composer-Erweiterungsanforderungen stammen aus der bereits bestätigten
Hostingausstattung; kein neues Composer-Paket und kein Versionsupdate hinzugefügt.

## Öffentliche Oberfläche und APIs

Der Teststand liefert zwölf bekannte öffentliche Dateien: die bisherigen sechs
Login-Dateien plus `files.php`, `files.js`, `files.css`, `store.php`, `session.php`, `owners.php`.
Originales Upstream-store.php, Composer-Dateien/vendor, Konfiguration und alle Benutzerdaten
bleiben privat. Der Installer prüft exakte öffentliche Dateiliste und sämtliche Hashes.

- `/files.php`: angemeldeter Dateibereich, sonst Rückleitung zur Startseite. Ordner öffnen/
  anlegen, eigene oder erlaubte fremde `.lyl` hochladen, herunterladen, umbenennen und
  berechtigt löschen. Ersetzen/Umbenennen/Löschen einer Datei verwendet deren Revision.
- `/session.php`: authentifizierter GET auf den nativen CSRF-Nachweis; keine Rollen aus Requests.
- `/owners.php`: nur authentifiziert, liefert eigene und aktuell berechtigte Eigentümer mit
  internen IDs, lesbaren Bezeichnungen und Aktionsrechten. Keine Identitäts-Hashes, UUIDs,
  vollständigen Rollen-/Gruppenlisten oder fremden Namen außerhalb der Berechtigung.
- `/store.php`: native Sitzung, exakte Herkunft/CSRF bei Änderungen, frischer Principal-
  Snapshot und feste private Benutzerwurzel vor jedem unveränderten Upstream-Aufruf.
  Fremde Dateioperationen werden wie bisher privat auditiert; die Katalogauswahl selbst
  ist kein Dateiabruf. Persönliche Einstellungen bleiben für fremde Nutzer gesperrt.

`SsoPolicy` nutzt dieselbe Zugriffsentscheidung für Katalog und Dateizugriff. Betreuung
sieht bestätigte Schüler sowie den eigenen Bereich; keine fremden Lehrerbereiche und
keine fremde Löschung. Admins sehen alle gültig registrierten Eigentümer. Bei Mitgliedschaft
in beiden Gruppen gilt Admin-Vorrang. Ein Konto mit beiden Gruppen kann deshalb nicht
zum realen Nachweis des Betreuungs-Löschverbots dienen.

Jede API-Entscheidung erfolgt erneut am Server. Die Oberfläche zeigt keine fremden
Bereiche allein wegen einer Browserangabe und bindet Dateiaktionen an den angezeigten
Eigentümer/Ordner. Nach einem erneuten bekannten SSO-Login wirken Rollen-/Gruppenentzug
auch bei noch laufenden Sitzungen. Historische Schülerzuordnung verfällt weiterhin
nicht nach fünf Minuten; neue Einstufung wird erst beim eigenen nächsten Login bekannt.

Keine lokale Projektablage, IndexedDB oder Offline-/Service-Worker-Funktion im Dateitest.
Seiten/APIs sind `private, no-store`; sensible Antworten/Redirects `no-referrer`.
Formularseiten bleiben wegen nativer Browser-POSTs bei `same-origin`. Dateiansicht nutzt
nur eigene JS-/CSS-Dateien, textuelle DOM-Ausgabe und eine passende CSP ohne Inline-Skripte.

## Prüfbelege

Am 04.11.2026 alle **180 Testgruppen** unter lokalem PHP 8.4.19 bestanden:
61 OIDC-Kern, 18 Login-HTTP, 40 lokale SSO-Speicher-, 35 historische Speicherregressionen,
14 neue integrierte HTTP- und je 6 alte/neue Installer-Prüfungen. JavaScript-/PHP-Syntax,
PHP-Plattformanforderungen und Git-Diff geprüft. Composer meldet nach der Lock-Aktualisierung
keine bekannten Sicherheitswarnungen; JWT-Paket bleibt exakt 7.2.1.

Neue gezielte Aufrufe:

```bash
python3 -W error tests/integrated_storage_http_test.py \
  --php /opt/homebrew/opt/php@8.4/bin/php --layerling ../layerling
python3 -W error tests/install_storage_test.py \
  --php /opt/homebrew/opt/php@8.4/bin/php --layerling ../layerling
```

Die neuen HTTP-Tests beginnen mit synthetischem OIDC-Code/RS256-Token/UserInfo und gehen
über den echten Callback/Writer/native Cookie bis zum gepinnten PHP-Dateispeicher.
Geprüft: zwei Eigentümer mit gleichen Dateinamen, Schüler ohne Gruppen, Katalogisolation,
Betreuung/Admin-Vorrang, edit/delete/settings-Grenzen, CSRF/Origin, Pfade/Header-Spoofing,
Sitzungsablauf/Geltungsbereich, Logout und paralleler Callback, wartender Upload nach
Widerruf, erneuter Eigentümer-/Akteur-Login und Upstream-/Konfigurationstamper.

Installerprüfungen: echter privater Bootstrap, Upgrade/Downgrade, Erhalt von Secret,
Principals/Sitzungen/Projektdateien, Paket-/Upstream-Integrität, feste Schülerrolle und
Zielpfade sowie Bereiniger für abgelaufene native Dateien. Alle Daten synthetisch in
temporären Verzeichnissen, keine echten Konten oder Inhalte verändert.

## Paketierung

Siehe [SSO-Teststand](sso-teststand.md). Gehostete Pakete benötigen eine explizite
private Deployment-Konfiguration. Reale Installationsnachweise bleiben privat.
