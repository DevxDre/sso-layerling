# CAD-Integration

Technische Architektur und historische lokale Prüfbelege. Maßgeblich für den aktuellen
Pin sind `upstream.lock.json` und `config/cad-adapter.lock.json`. Konkrete
Installationen und Rollbacks werden ausschließlich privat dokumentiert.

## Abgeschlossener Build-Nachweis

Die Buildquelle wurde ausschließlich mit `git archive` aus dem festgelegten Commit
`4b61a20b49c6fce9910a7903f53989d40396dfa4` (Layerling 1.136.0) extrahiert.
Der benachbarte Layerling-Checkout blieb sauber und unverändert auf diesem Pin.
Keine Wrapper-Secrets oder lokalen Konfigurationsdateien wurden kopiert.

- Node v26.3.0, npm 11.16.0, Next.js 15.5.28 aus der Lockdatei.
- SHA-256 von `package-lock.json` vor/nach Installation identisch:
  `98c268a530f8e3110715802b89105282dee8d9589f328e4e3f382b64559658c6`.
- `npm ci --ignore-scripts --no-audit --no-fund`: 151 bestehende gelockte Pakete installiert;
  keine Paketupdates. Installationsskripte nicht ausgeführt.
- `NEXT_TELEMETRY_DISABLED=1 LAYERLING_BUILD_CPUS=2 npm run export`: Exit 0.
- Compiler, Typprüfung, statischer Export und Upstream-Workerprüfung erfolgreich;
  fünf Worker-Runtimes verwenden `/_next/`.
- Export unter `apps/web/.next-export/`: 705 Dateien, 129.362.343 Bytes.
- Upstream erzeugt zusätzlich `sw.js` mit 548 Offline-Dateien. Originales `store.php`
  liegt ebenfalls im Export. Diese Ausgabe darf nicht ungefiltert ins Webroot gelangen.
- Node meldete eine Deprecation-Warnung zu `module.register()`, der Build lief erfolgreich.

Temporärer Arbeitsordner: `/private/tmp/sso-layerling-cad-4b61a20b49c6`.
Dieser Ordner ist ein entfernbares Buildartefakt, keine dauerhafte Quelle. Ein erneuter
Build muss den Pin neu extrahieren und darf nicht von diesem Ordner abhängen.
Der Nachweis belegt einen erfolgreichen Build, noch keinen Browser-CAD-Test,
keine Sicherheitsabnahme und keine byteidentische Reproduzierbarkeit. Upstreams
Buildskript verwendet einen Zeitstempel für `LAYERLING_BUILD_ID`.

## Erneut isoliert bauen

Aus dem Wrapper-Repository; benötigt die bereits geprüften Node-/npm-Werkzeuge:

```bash
set -euo pipefail
LAYERLING_CAD_PIN="$(python3 -c 'import json; print(json.load(open("upstream.lock.json"))["commit"])')"
LAYERLING_CAD_BUILD="$(mktemp -d /private/tmp/sso-layerling-cad.XXXXXX)"
git -C ../layerling archive --format=tar "$LAYERLING_CAD_PIN" | tar -x -C "$LAYERLING_CAD_BUILD"
cd "$LAYERLING_CAD_BUILD"
npm ci --ignore-scripts --no-audit --no-fund
NEXT_TELEMETRY_DISABLED=1 LAYERLING_BUILD_CPUS=2 npm run export
```

Keine neue Upstream-Version übernehmen. Dieser Ablauf ist ein lokaler Build,
kein Hoster-Sync. Auf dem Webhoster sind weiterhin kein npm oder Node-Daemon nötig.

## Geprüfte Integrationspunkte

| Bereich | Quelle im gepinnten Layerling | Erforderliche Wrapper-Anbindung |
| --- | --- | --- |
| Datei-Endpunkt | `apps/web/src/lib/sharedProjectsEndpoint.ts` | Statischer Export nutzt relatives `store.php`; geschützten Wrapper-Endpunkt beibehalten. |
| Dashboard/Editor-Dateien | `apps/web/src/app/page.tsx` | GET/POST/DELETE inklusive Uploads, Revisionen, Umbenennen, Ordnern und Exporten anbinden. |
| Weitere Datei-Aufrufer | `customShapesServer.ts`, `backupDownload.ts`, `serverWorkspaceDefault.ts` unter `apps/web/src/lib/` | Eigene Formen, Backups und persönliche Einstellungen ebenfalls erfassen. |
| Sitzungsnachweis | Wrapper `GET /session.php` | Vor Editorstart prüfen; Änderungen mit `X-SSO-CSRF`; bei 401 Editor sperren. |
| Eigentümer | Wrapper `GET /owners.php`, Parameter `_sso_owner` | Servergefilterten Katalog verwenden; Ziel einer geöffneten Datei dauerhaft binden. |
| Neue Projekte | `page.tsx`, Einstellung `newDesignsOnServer` im Store | Bewusst serverseitiges Speichern vorsehen; Browserkopie darf nicht unbemerkt einziger Speicher bleiben. |
| Offline-Modus | `offlineSupport.ts`, `ServiceWorkerRegistration.tsx`, `scripts/generate-service-worker.mjs` | Offline-Angebot und Registrierung im Wrapper-Build deaktivieren; `sw.js` nicht ausliefern. |
| Browserkopien | `page.tsx`, `storageMigration.ts`, `projectShapePersistence.ts`, `designListStorage.ts` | localStorage/IndexedDB und Vorschauen auf Konten- und Eigentümerkontext prüfen. |
| Worker/Assets | Next-Konfiguration und Workerprüfung | Root-relative Pfade berücksichtigen; nicht ungeprüft in `/cad/` verschieben. |

Die originalen Änderungsaufrufe enthalten Revisionsheader, aber nicht den vom
Wrapper verlangten `X-SSO-CSRF`-Header. Einfaches Ausliefern des Exports würde
Änderungen deshalb zu Recht blockieren. Die PHP-Prüfungen bleiben bestehen.
Fremde persönliche Einstellungen bleiben durch die bestehende Policy gesperrt.

## Integrationsstufen und Freigabekriterien

1. Kleinen, überprüfbaren Buildadapter im Wrapper erstellen. Anpassungen nur in der
   isolierten Quelle, gebunden an geprüfte Dateien/Hashes; bei unbekanntem Quellstand
   abbrechen. Keine Änderungen am Layerling-Fork und keine Updates seiner Pakete.
2. Zunächst eigene Projekte: Sitzung vor Start prüfen, CSRF für Änderungen ergänzen,
   bestätigtes Speichern und Wiederöffnen nachweisen. Fehler dürfen keine Meldung
   über erfolgreiches Serverspeichern ergeben.
3. Online-Betrieb und Logout: geschützten HTML-Einstieg vorsehen, Offline-Registrierung
   entfernen, abgelaufene Sitzungen und alte Tabs sperren. Nur fehlendes `sw.js`
   genügt nicht, falls später eine frühere Worker-Installation existiert.
4. Eigentümerkontext und Browserkopien integrieren: Datei, Revision und lokaler Cache
   müssen beim ursprünglich ausgewählten Eigentümer bleiben, auch bei parallel
   geöffneten Editoren. Fremde Daten nicht in persönliche Backups übernehmen.
5. Admin-/Betreuungsrechte im Editor abbilden und serverseitige Grenzen unverändert
   testen: Betreuung ohne Löschrecht, Admin mit Löschrecht, unberechtigte direkte
   Zugriffe weiterhin gesperrt. Besitzwechsel nicht durch bloßen UI-Wechsel erzeugen.
6. Erst nach lokalen HTTP-/Browserprüfungen ein explizites CAD-Testpaket erstellen;
   vorhandene Installation, Secrets und Nutzerprojekte erhalten. Hoster-Sync und
   echte CAD-Praxisprüfung separat dokumentieren.

Aktueller Datei-Teststand und dessen belegte Grenzen: [SSO-Dateitest](sso-dateitest.md).


## Erste lokale Stufe mit eigenem CAD-Speicher

Der erste lokale CAD-Kandidat ist jetzt implementiert. Die ursprüngliche
Layerling-Arbeitskopie bleibt unverändert. Der Adapter in `scripts/cad-candidate.py`
extrahiert den Pin neu und verändert nur drei Dateien in dieser isolierten Kopie:

- `page.tsx`: neue Entwürfe starten im persönlichen Serverspeicher; ein fehlgeschlagener
  erster Upload öffnet keinen stillen lokalen Ersatz; Editor-URLs bleiben unter `/cad.php`.
- `offlineSupport.ts`: Offline-Angebot und Service-Worker-Registrierung deaktiviert.
- `useAppUpdate.ts`: direkte GitHub-Releaseabfragen deaktiviert. Hinweise auf tatsächlich
  hier bereitgestellte Versionen über die lokale `version.json` bleiben erhalten.

`config/cad-adapter.lock.json` bindet diese Anpassungen an den geprüften Commit und
Original-Hashes. Vor/nach dem Build sowie beim Paketieren werden alle 1.786 ursprünglichen
Dateien gegen das Git-Archiv plus diese Anpassungen geprüft. Zusätzliche Quellrouten,
Build-Konfigurationen und lokale `.env`-Dateien werden abgewiesen. Die Dependency-Lockdatei
bleibt unverändert; es wurden keine neuen Pakete oder Versionen hinzugefügt. Das lokale
Deploy-Skript setzt `NEXT_PUBLIC_SOURCE_CODE_URL` beim Build; der Wert steht im privaten
Buildbericht. Die Quell- und Installationsadressen bleiben in ignorierten Deployment-Dateien.

Der öffentliche `/cad.php`-Controller liefert erst nach nativer SSO-Sitzungs- und
Registerprüfung das private, hashgeprüfte Editor-HTML. Scripts erhalten pro Antwort
eine CSP-Nonce; JavaScript benötigt kein `unsafe-inline`. WebAssembly sowie lokale
`data:`-/`blob:`-Vorschaubilder sind gezielt zugelassen, externe Verbindungen nicht.
Das HTML bleibt `private, no-store` und wird nicht als öffentliche `index.html` kopiert.

### Datenschutz und externe Verbindungen

Die ausgelieferte Layerling-Oberfläche darf keine Ressourcen oder Programmteile von
anderen Webseiten nachladen. Die CSP setzt deshalb `default-src 'none'` und nennt
jede benötigte lokale Ausnahme ausdrücklich. Scripts, API-Verbindungen, Worker und
Medien bleiben auf den eigenen Ursprung begrenzt; `data:` und `blob:` gelten nur dort,
wo der Editor sie für Vorschaubilder, Geometrie und Worker benötigt. Frames, Plugins
und Web-App-Manifeste sind gesperrt. HTTPS wird für unsichere Unterressourcen erzwungen.
Jede Antwort nutzt eine frische Script-Nonce, während die HTML-Datei selbst privat
und gegen den Paket-Hash geprüft bleibt.

Der Wrapper baut ausschließlich aus dem gepinnten Layerling-Commit, geprüften
Adapteränderungen und der unveränderten Dependency-Lockdatei. Upstream-Releaseabfragen
und Service Worker sind für diesen Schulbuild deaktiviert. Damit erhält der Browser
Programmdaten vom Schulserver und registriert keinen Offline-Service-Worker.
Der OIDC-Anmeldedienst bleibt eine beabsichtigte externe Verbindung für die Anmeldung;
er bekommt keine CAD-Dateien über die Editor-API. Beim Wechsel zu externen Links wird
kein Referrer mitgeschickt (`Referrer-Policy: same-origin`). `no-referrer` ist für den
Editor ungeeignet: Browser senden dann bei Formular-POSTs wie dem Abmelden und Firefox
auch bei Speicheraufrufen der Bridge `Origin: null`, das die Origin-Prüfung ablehnt
(`foreign_request`). `connect-src` erlaubt `data:`, weil Layerling Vorschaubilder vor dem
Hochladen per `fetch` aus `data:`-Adressen liest; dabei entsteht kein Netzwerkverkehr.

Diese Regeln verhindern Browser-seitige Requests und Ausführung fremder Webressourcen,
solange die HTML-Antwort und die ausgelieferten Dateien vertrauenswürdig sind und der
Browser die CSP durchsetzt. Sie schützen nicht vor Schadcode, der bereits im geprüften
Upstream-/Buildstand oder auf dem Schulserver liegt, vor kompromittierten Admin-Konten,
Hoster-/Serverlogs oder lokalen Browsererweiterungen. Darum bleiben Quellpin,
Paketprüfsummen, private Serververzeichnisse, Updates aus geprüften Ständen, Backups
und die sparsame Protokollierung zusätzliche Schutzmaßnahmen.

`cad/bridge.js` läuft vor den Layerling-Scripts und bindet jeden `store.php`-Aufruf an
die eigene stabile Eigentümer-ID. Änderungen erhalten `X-SSO-CSRF`; Revisionsheader
bleiben erhalten. Die Sitzungsprüfung erfolgt vor und nach Dateiaufrufen. Dateiinhalte
werden für die Übertragung als Blob verwendet, damit auch Chromium über HTTP/1.1
Multipart-/ZIP-Uploads unterstützt. Vorschaubild-URLs behalten den eigenen Eigentümer.
Die ursprünglichen PHP-Rechteprüfungen bleiben maßgeblich und unverändert.
Antwortet `store.php` mit 403 `access_denied`, prüft die Bridge die Sitzung erneut: Bei
gewechselter oder beendeter Anmeldung sperrt sie den Editor, sonst bleibt er offen und
Layerling zeigt eine deutsche Berechtigungsmeldung. Jede andere 403-Antwort, etwa
`foreign_request` oder `csrf_rejected`, sperrt den Editor, statt den Code anzuzeigen.

localStorage, sessionStorage, IndexedDB und BroadcastChannel erhalten vor dem Start
des Editors einen Benutzer-Namensraum; Storage-Events werden entsprechend gefiltert.
Ungeschützte alte Browserkopien werden nicht importiert. Das ist eine Trennung der
Anwendungsdaten, keine Verschlüsselung oder Ersatz für die vereinbarten Browserprofile.

`GET /cad-session.php` prüft die aktive Sitzung und den Registereintrag, ohne `lastSeen`
zu verlängern. Die sichtbare Seite prüft alle 30 Sekunden sowie bei Fokus und vor
Dateizugriffen; eine lokale Frist endet spätestens mit der bekannten Sitzungsfrist.
Bei Wechsel der Anmeldung, Abmeldung, fehlender Verbindung oder abgelaufener Sitzung
sperrt die Oberfläche und fordert einen neuen Seitenaufruf. Die bestehenden
serverseitigen Sitzungs-/CSRF-Grenzen gelten für jeden Zugriff unmittelbar.
Vorherige Worker auf dem Root-Scope werden abgemeldet; eine noch kontrollierte Seite
muss neu geladen werden. Fremde Caches oder Projekte werden dabei nicht gelöscht.

Diese erste Stufe bindet eigene Dateien an den Editor. Der folgende Abschnitt
beschreibt den aktuellen Kandidaten mit Eigentümerauswahl.

## Lokalen Kandidaten erstellen und prüfen

Aus dem Wrapper-Repository; Zielordner dürfen jeweils noch nicht existieren.
Für öffentliche Pakete eine neutral benannte temporäre Buildquelle verwenden:
Einige Editor-Abhängigkeiten betten absolute Quellpfade in JavaScript ein. Das fertige
Paket zusätzlich auf persönliche Pfade prüfen; ein Build aus dem Benutzerverzeichnis
kann dessen Namen enthalten.

```bash
mkdir -p build
python3 scripts/cad-candidate.py prepare --layerling ../layerling --output /private/tmp/sso-layerling-cad-source
python3 scripts/cad-candidate.py build --source /private/tmp/sso-layerling-cad-source --layerling ../layerling
python3 scripts/cad-candidate.py package --source /private/tmp/sso-layerling-cad-source --layerling ../layerling --output build/cad-own-candidate
python3 -W error tests/cad_http_test.py --php /opt/homebrew/opt/php@8.4/bin/php --layerling ../layerling --candidate build/cad-own-candidate
python3 -W error tests/cad_build_test.py --php /opt/homebrew/opt/php@8.4/bin/php --layerling ../layerling --candidate build/cad-own-candidate
```

Der Browsertest verwendet einen eigenen temporären Chromium-Profilordner und
synthetische OIDC-Konten auf Loopback-HTTP. Standard: lokales Google Chrome unter
macOS; anderer ausführbarer Pfad über `SSO_CAD_CHROME`. Node stellt WebSocket/CDP
bereit; kein zusätzliches Browserpaket nötig. Testserver und Browserprofil werden
nach dem Lauf entfernt. Der Test verändert ausschließlich seine synthetischen Daten.

Das Paket hat absichtlich den eigenen Typ `sso-layerling-cad-candidate`. Der vorhandene
Hoster-Installer akzeptiert ihn noch nicht; dies ist automatisiert geprüft. Öffentliches
Original-`store.php`, `index.html`/`index.txt`, alternative App-Einstiege, `sw.js` und
Installationsmanifest sind ausgeschlossen. Private App-/Build-Manifeste verzeichnen
Quelldaten und Datei-Hashes. Die `.env` und sämtliche Nutzerdaten werden nicht kopiert.

Die bestehenden Ignore-Regeln für `build/`, `.local/`, `.env*` und Python-Artefakte
decken diese Arbeitsweise ab; neue Quellen, Tests und Adapter-Lockdatei werden versioniert.
Der laufende gehostete Dateitest wurde in dieser lokalen Phase nicht verändert.

## Prüfstand der ersten Stufe

Am 04.11.2026 erfolgreich: **191 Testgruppen** unter PHP 8.4.19. Das sind 61 OIDC,
18 SSO-HTTP, 35 historischer Speicher, 40 SSO-Speicher, 18 CAD-/Integrations-HTTP
(einschließlich der bisherigen 14 Integrationsfälle und eines echten Browserlaufs)
sowie 6 Portal-Installer, 6 Datei-Installer und 7 neue CAD-Build-/Paketgruppen.

Der echte Chromium-Lauf weist nach:

- neuer Entwurf und eingefügter 3D-Quader tatsächlich auf dem PHP-Server gespeichert;
  der Test liest anschließend die `.lyl`-ZIP und prüft enthaltene Geometrieknoten;
- Wiederöffnen nach Neuladen und zusätzlich nach vollständigem Entfernen der
  synthetischen localStorage-/IndexedDB-Kopien direkt aus der Server-Dateikarte;
- simuliertes HTTP 500 beim ersten Upload bleibt sichtbar auf dem Dashboard,
  statt einen ungespeicherten lokalen Entwurf als Ersatz zu öffnen;
- ungeschützter Alt-Cache wird ignoriert, angemeldete Benutzer haben getrennte Kopien;
- neue Anmeldung sperrt den alten Tab; Offline-Zustand und entfernte Sitzung ebenfalls;
- kein aktiver Service Worker, keine ungefangenen Scriptfehler oder CSP-Verstöße.

Der finale geprüfte temporäre Kandidat liegt unter
`/private/tmp/sso-cad-own-candidate-6`, die Buildquelle unter
`/private/tmp/sso-cad-own-source-v3`. Nach Commit wird derselbe Kandidat mit sauberer
Commitkennung unter `build/cad-own-<Commit>/` paketiert. Ein Vergleich seiner
Datei-Hashes mit dem geprüften Kandidaten muss unveränderte Inhalte bestätigen.
Der Screenshot `/private/tmp/sso-layerling-cad-own.png` zeigt ausschließlich das
synthetische Testprojekt nach Wiederöffnen aus dem Server.

PHP-/JavaScript-Syntax, Python-Kompilierung und Diff sind geprüft. Die bestehenden
Sicherheitsassertionen bleiben erhalten. Nach den letzten CAD-/Startseitenänderungen
wurden CAD-/Integrations- und SSO-HTTP erneut geprüft.

Ein lokaler Chromium-Nachweis ist noch kein CAD-Hostertest oder vollständiger
Import-/Export-/Gerätetest. Die nächste Stufe ergänzt die nachfolgend dokumentierte Eigentümerauswahl.


## CAD-Eigentümerauswahl am 05.11.2026

Das Auswahlfeld im Editor bietet die von der PHP-Policy freigegebenen Dateibereiche an.
**Öffnen** lädt den ausgewählten Bereich in einem neuen Dokument. Der laufende
Editor hält seine Zuordnung bis zum Seitenwechsel. Die URL behält die Auswahl
beim Öffnen und Schließen eines Entwurfs sowie beim Neuladen.

Die Betreuung kann Schülerdateien lesen, herunterladen und bearbeiten.
Datei- und Ordnerlöschungen sind für sie im fremden Bereich gesperrt.
Admins können Dateien aller registrierten Eigentümer auch löschen.
Umbenennungen von gespeicherten Formen verwenden die revisionsgeprüfte
PHP-Operation. Jeder Dateizugriff unterliegt der bestehenden Server-Policy.
Die Sitzungsprüfung kontrolliert zusätzlich den gewählten Dateibereich
und übernimmt Änderungen am Löschrecht. Bei Verlust des Leserechts sperrt
sie den geöffneten Editor.

Eigene Browserkopien behalten ihren Namensraum. Fremde Arbeitskopien,
Vorschauen und Bibliotheken sind nach angemeldetem Benutzer und gewähltem
Eigentümer getrennt. Sicherungen beziehen ihre Daten aus diesem Bereich.
Persönliche Servereinstellungen werden im fremden Bereich nicht synchronisiert.
CAD-Dateiaufrufe binden auch Lesezugriffe mit dem Sitzungswert an die
ursprüngliche Anmeldung.

**192 Testgruppen bestanden** einschließlich des gepinnten Builds, der
bestehenden Rechteprüfungen und des realen Chromium-Laufs mit synthetischen
Konten. Im Browser wurden der Wechsel über die Auswahl, eine Geometrieänderung
in der Schülerdatei, das erneute Öffnen im selben Bereich, getrennte
Browserkopien, das gesperrte Löschen für die Betreuung und das Löschen einer
Testkopie durch einen Admin geprüft. Der HTTP-Test deckt zusätzlich
unerlaubte Eigentümer, einen Anmeldewechsel und den Entzug des Leserechts ab.

Die Buildquelle liegt lokal unter `/private/tmp/sso-cad-owner-source`.
Der geprüfte Kandidat liegt unter `/private/tmp/sso-cad-owner-candidate`.
Das Paket mit Commitkennung liegt unter `build/cad-owner-<Commit>/`.
Der folgende Abschnitt dokumentiert den installierten CAD-Teststand.



Für gehostete Pakete zusätzlich `--hosted-test --deployment-config config/deployment.local.json` angeben.
