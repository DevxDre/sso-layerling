# Lokaler PHP-Speicherprototyp

Stand: 03.11.2026. Implementiert und lokal geprüft. Noch kein SSO und keine Produktionsfreigabe.
Dieser Bericht beschreibt die ursprüngliche persönliche Speichergrenze. Der aktuelle Stand
mit Register und zusätzlichen Gruppenrechten steht im [Gruppenprototyp](gruppenprototyp.md).

## Umfang

Der eigene Einstiegspunkt prüft die Wrapper-Sitzung und übergibt erst anschließend
das unveränderte Layerling-Skript an PHP. Verwendeter Quellstand:

- Fork-Commit: `4b61a20b49c6fce9910a7903f53989d40396dfa4`.
- Originaldatei: `apps/web/public/store.php`.
- SHA-256: `8172404bcb208d52a5fbbcfd9f6139616408752d6cd8260d904211241f37e30d`.
- Festgehalten in [upstream.lock.json](../upstream.lock.json).

Die Paketierung liest genau dieses Git-Objekt aus dem lokalen Layerling-Repo, ohne Fetch,
Pull, npm, Composer oder Ausführung von Upstream-Buildskripten. Ein vorhandenes Zielverzeichnis
wird nicht überschrieben. Geerbte `GIT_*`-Variablen werden für den lesenden Git-Aufruf entfernt.

## Sicherheitsgrenze

- Ausschließlich PHPs lokaler Entwicklungsserver und Loopback-Verbindungen sind zugelassen.
  Das Paket akzeptiert nur eine ausdrücklich konfigurierte Loopback-Origin. Das ist kein
  für PHP-FPM freigegebener Stand und darf nicht über einen öffentlichen Proxy bereitgestellt werden.
- Im öffentlichen Paketbereich liegen nur `store.php` und `session.php`.
- Quellcode, Originalskript, Konfiguration, Sitzungen und Projekte liegen außerhalb des DocumentRoot.
- Es gibt keinen HTTP-Login, keinen Schalter für synthetische Benutzer und keine Testkonten im Paket.
- Sitzungen/Identitäten erzeugt ausschließlich die CLI-Fixture des Testprogramms in temporären Ordnern.
- Fehlende, unbekannte, abgelaufene oder nicht autorisierte Sitzungen werden mit 401 abgewiesen.
- Prototypwerte: absolute Frist eine Stunde und Leerlauf 15 Minuten. Das sind ausdrücklich
  vorläufige Test-/Prototypwerte und keine festgelegte produktive Sitzungspolitik.
- Die Sitzung enthält eine interne 32-stellige Hex-ID. Der Wrapper setzt den Speicherpfad
  auf `private/projects/<id>` und deaktiviert Layerlings eigene Headerzuordnung.
  Eine dauerhafte Zuordnung zu geprüften IServ-Identitäten ist noch nicht implementiert.
- Die drei Upstream-Konfigurationswerte für Speicher, Benutzerheader und erlaubte Origins
  werden serverseitig überschrieben. Fremde Identitäts-/Proxyheader bestimmen keine Ordnerzuordnung.
- POST und DELETE benötigen die feste Origin und einen sitzungsgebundenen `X-SSO-CSRF`-Header.
  Fremde Origins und fremde Fetch-Kontexte sind auch bei GET gesperrt.
- `GET /session.php` liefert ausschließlich für angemeldete Sitzungen das CSRF-Token.
  `POST /session.php` meldet mit derselben Origin-/CSRF-Prüfung lokal ab.
- Alle Speicher-/Sitzungsantworten erhalten zuletzt `Cache-Control: private, no-store`,
  `Vary: Cookie`, `nosniff` und `Cross-Origin-Resource-Policy: same-origin`.
- Das Originalskript wird vor der Ausführung gegen seinen festgehaltenen Hash geprüft.

Der Session-Lock bleibt für einen zugelassenen Speicherrequest bis zu dessen Ende gehalten.
Ein bereits zugelassener Request darf abschließen; Logout wartet auf diesen Lock.
Nach abgeschlossenem Logout beginnende bzw. noch auf die Sitzungsprüfung wartende Requests
finden keine gültige Identität mehr.

## Zwei bei der Implementierung behandelte Befunde

**Vorschaubilder:** Das Original setzt `Cache-Control: public, max-age=31536000, immutable`.
Für persönliche geschützte Bilder überschreibt ein eigener `header_register_callback` diesen
Header unmittelbar vor dem Versand. Der entsprechende Bildabruf wird per HTTP getestet.
Das Original bleibt unverändert.

**Sitzungswiderruf:** Ein Regressionstest zeigte, dass `session_destroy()` allein eine schon
auf den nativen Dateilock wartende Anfrage noch mit alten Daten fortfahren lassen kann.
Der Widerruf schreibt deshalb unter dem Lock einen leeren Sitzungsdatensatz und schließt
danach die Sitzung. Der leere Datensatz darf später durch Garbage Collection entfernt werden;
Sitzungsdateien sofort zu löschen ist kein Bestandteil des Widerrufsverfahrens.
Der gleiche Regressionstest weist die wartende Anfrage jetzt mit 401 ab.

## Prüfung ausführen

Im Wrapper-Repository, auf diesem Mac:

```bash
python3 tests/storage_http_test.py \
  --php /opt/homebrew/opt/php@8.4/bin/php \
  --layerling ../layerling
```

Auf anderen Rechnern den expliziten PHP-8.4-Pfad anpassen. Die Suite verwendet keine
zusätzlichen Python-Pakete. Sie benötigt einen lokalen Loopback-Port. Unter einer Sandbox
kann dafür eine gesonderte Freigabe nötig sein.

Die Suite baut ein temporäres Paket, startet PHP auf `127.0.0.1`, erzeugt synthetische Sitzungen,
prüft echte HTTP-Anfragen und entfernt Server/Paket/Testdaten anschließend wieder.
Zwei unabhängige Cookies simulieren getrennte Clients; es wird kein Browser automatisiert.
Für die Parallelprüfung hält ein CLI-Prozess den echten Dateisitzungs-Lock und widerruft
mit derselben Widerrufsfunktion, während ein HTTP-Upload auf die Prüfung wartet.

Ergebnis am 03.11.2026: **16 Testgruppen bestanden**, PHP **8.4.19 CLI/cli-server** lokal.
Zusätzlich PHP-Syntaxprüfung der Quelldateien. PHP-FPM auf dem Hoster ist bisher nur durch
die separate [Hostingprüfung](hosting-pruefung.md) bestätigt, nicht mit diesem Wrapper getestet.

Abgedeckt: Paketgrenzen/Integrität, anonyme Operationen, ungültige/abgelaufene Sitzungen,
Headerfälschung, CSRF/Origin/Host, A/B-Projekte mit gleichen Dateinamen, Vorschaubilder,
Ordner/Suche/Gesamtliste/Einstellungen, Kopieren/Umbenennen/Verschieben/Löschen,
Revisionskonflikte, Pfadmanipulation/Symlinks, Abmeldung/Wiederanmeldung,
Exportvalidierung, unbekannte Methoden und Widerruf bei wartendem Upload.

## Paket separat ansehen

```bash
python3 scripts/package-prototype.py \
  --layerling ../layerling \
  --output /tmp/sso-layerling-storage-demo \
  --origin http://127.0.0.1:8080
```

Der Zielpfad darf noch nicht existieren. Ein so erzeugtes Paket enthält keine gültigen
Sitzungen: Ohne die ausschließlich testintern erzeugten Sitzungen bleiben die Speicherwege
gesperrt. Es ist kein interaktiv nutzbarer CAD-/Login-Prototyp.

## Verbleibende Arbeit

**Neue bestätigte Zielanforderung:** [Gruppenbasierte Fremdzugriffe](berechtigungen.md).
Betreuung darf Schülerdateien lesen/bearbeiten, Admins alle Nutzerdateien zusätzlich löschen.
Die Erweiterung ist inzwischen lokal mit synthetischen Claims und insgesamt 35 Testgruppen
geprüft; echte Gruppenkennungen sind noch nicht aktiviert ([Bericht](gruppenprototyp.md)).

1. Eigenen IServ-Client, Rollenpolitik, dauerhafte Identitätszuordnung und OIDC-Abhängigkeiten festlegen.
2. Echte Anmeldung mit den vorhandenen Kirby-6-Prüfprinzipien integrieren; eigene sichere HTTPS-Cookies.
3. Layerling-Frontend anbinden. Das Original sendet noch keinen `X-SSO-CSRF`-Header;
   ohne diese Integration bleiben seine Schreibanfragen absichtlich gesperrt.
4. Speichermeldungen, Login/Logout, Ablauf und Netzfehler im echten Browser prüfen.
5. Online-/Service-Worker-Paketierung, Quoten, Backup/Restore und produktives Deployment ergänzen.

Keine neuen Pakete installiert, kein Layerling-Code verändert und nichts auf dem Hoster
bereitgestellt. Der gesamte Upstream und seine Dateiformatprüfungen wurden nicht vollständig
auditiert; dies ist die abgegrenzte lokale Prüfung unseres Speichereinstiegs.
