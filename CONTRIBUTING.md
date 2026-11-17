# Mitwirken an sso-layerling

Fehlerberichte, nachvollziehbare Tests, verständliche Dokumentation und gezielte
Codeänderungen helfen dem Projekt. Das gilt für menschliche Mitwirkende ebenso wie
für Beiträge, die mit einem KI-Assistenten entstehen.

## Orientierung

Lies zuerst die [README](README.md) und die [Arbeitsregeln](AGENTS.md).
Der [Entwicklungsstand](docs/weiterarbeit.md) unterscheidet zwischen vorhandenem Verhalten
und geplanten Änderungen. Insbesondere die anbieterunabhängige OIDC-Anbindung ist ein
Entwicklungsziel; die aktuelle Implementierung enthält noch IServ-spezifische Stellen.

| Bereich | Dateien und Verzeichnisse |
|---|---|
| OIDC-Anmeldung und Claims | `src/Oidc/` |
| Sitzung, Rechte und Dateizugriffe | `src/NativeSession.php`, `src/SsoPolicy.php`, `src/Gateway.php` |
| Öffentliche PHP-Einstiege und Dateiverwaltung | `public/` |
| Anpassungen der Editor-Oberfläche | `cad/bridge.js`, `cad/bridge.css` |
| Isolierter CAD-Build, Adapter und Paketierung | `scripts/`, `config/cad-adapter.lock.json`, `upstream.lock.json` |
| Synthetische Tests | `tests/` |

Der Layerling-Editor ist ein separates Projekt. Editoränderungen, die unabhängig vom
Schulwrapper sinnvoll sind, gehören in das Layerling-Projekt. Wrapper-Anpassungen werden
hier auf eine isolierte, gepinnte Buildquelle angewendet. Generierte Builds nicht von Hand
ändern und nicht ins Repository übernehmen.

## Gemeinsames Projektwissen

Das [Glossar](GLOSSARY.md) klärt die fachlichen Begriffe. Dauerhafte Entscheidungen stehen
unter [docs/adr/](docs/adr/README.md). Nutze die Begriffe auch in Issues und Tests und halte
beschlossene Änderungen an diesen Quellen aktuell. Private Betriebsinformationen bleiben privat.
Der [Aufgabenleitfaden](docs/agents/aufgaben.md) zeigt, wie Nutzungsziel, Akzeptanzkriterien,
Prüfung und abschließender Review zusammenpassen. Für kleine Änderungen genügt eine kurze
Beschreibung; zusätzliche Tickets oder ADRs sind dafür nicht erforderlich.

## Einen Beitrag vorbereiten

1. Prüfe vorhandene Issues und beschreibe den Fehler oder das gewünschte Verhalten.
   Größere Änderungen an Architektur, Abhängigkeiten, Datenformaten oder Anmeldemodell
   zuerst mit der Projektbetreuung abstimmen.
2. Arbeite auf einem eigenen Branch oder in einem Fork. Halte jeden Pull Request auf ein
   Thema begrenzt und vermeide zusätzliche Umformatierungen oder Umbauten.
3. Nutze vorhandene Muster. Ergänze neue Abstraktionen nur, wenn die konkrete Änderung sie
   benötigt. Kommentare sollen Gründe oder Grenzen erklären, die aus dem Code nicht hervorgehen.
4. Ergänze bei Fehlerkorrekturen nach Möglichkeit eine gezielte Regression, die das fehlerhafte
   Verhalten nachstellt. Reine Textänderungen benötigen keine neuen Laufzeittests.
5. Prüfe die betroffenen Abläufe über ihren normalen Einstieg. Zum Beispiel belegt ein
   gespeichertes und erneut geöffnetes Projekt mehr als ein vorhandener Speichern-Button.
6. Prüfe den gesamten Diff abschließend gegen die Akzeptanzkriterien und beschreibe Ergebnis,
   offene Kriterien und Grenzen im Pull Request. Bei Unterrichtsabläufen nach Möglichkeit
   eine Lehrkraft einen realistischen Nutzungspfad mit synthetischen Daten erproben lassen.

## Lokal einrichten und prüfen

Benötigt werden PHP 8.4 mit den Erweiterungen aus `composer.json`, Composer und Python 3.
CAD-Prüfungen benötigen zusätzlich das benachbarte Layerling-Checkout mit dem gepinnten
Commit; für den Editor-Build kommen Node.js und npm hinzu. Installiere die PHP-Abhängigkeiten
mit `composer install --no-dev --prefer-dist --no-interaction` anhand der vorhandenen Lockdatei.
Für synthetische Tests sind keine echten SSO-Zugangsdaten und keine produktive `.env` nötig.

Die folgenden Beispiele verwenden `php8.4`. Ersetze den Befehl und die `--php`-Angabe
gegebenenfalls durch den absoluten Pfad zur eigenen PHP-8.4-Installation.

| Änderung | Passende Prüfungen |
|---|---|
| OIDC, Claim-Normalisierung oder Login-Sitzung | `tests/oidc_test.php`, `tests/sso_http_test.py` |
| Dateirechte, Speicher oder Rechteentzug | `tests/sso_storage_http_test.py`, `tests/integrated_storage_http_test.py`; bei Änderungen am alten Prototyp auch `tests/storage_http_test.py` |
| Private Deployment-Metadaten oder Paketierung | `tests/deployment_config_test.py`, `tests/install_sso_test.py`, `tests/install_storage_test.py` |
| CAD-Adapter, Editor-Oberfläche oder MCP | `tests/cad_build_test.py`, `tests/cad_http_test.py` mit einem neu gebauten Kandidaten |
| CAD-Installation oder Rücksetzung | `tests/install_cad_test.py` mit einer geprüften Buildquelle |
| Dokumentation | Verweise und Beispiele prüfen; keine Laufzeittests allein wegen Textänderungen |

Beispiele:

```bash
php8.4 tests/oidc_test.php
python3 -W error tests/sso_http_test.py --php php8.4
python3 -W error tests/integrated_storage_http_test.py --php php8.4 --layerling ../layerling
python3 -W error tests/deployment_config_test.py --php php8.4 --layerling ../layerling
git diff --check
```

Vollständige Aufrufe und Voraussetzungen stehen im [SSO-Leitfaden](docs/sso-teststand.md)
und in der [CAD-Dokumentation](docs/cad-integration.md). Manche Tests starten temporäre
Loopback-Server; Browserprüfungen benötigen Chrome. Für einen CAD-Kandidaten ohne die
Option `--candidate` ausgelassene Browserprüfungen gelten nicht als bestanden.

Teste geänderte Benutzerabläufe zusätzlich von Hand, soweit die Umgebung das erlaubt.
Bei Oberflächenänderungen helfen Screenshots oder kurze Aufnahmen mit synthetischen Daten.
Bei Änderungen an Dateirechten auch die Ablehnung unerlaubter Zugriffe prüfen.

## Besonders sorgfältig prüfen

- Eigentümerbindung und Trennung zwischen Konten, auch bei gleichem Dateinamen.
- Änderungen an Anmeldung, Claim-Zuordnung, Gruppenrechten und Sitzungswiderruf.
- Speicherung, Vorlagen, Import/Export und bestehende Projektformate.
- Paketziele, Datei-Prüfsummen, Erhalt privater Laufzeitdaten und Rücksetzung nach Fehlern.
- Browserkopien und Verhalten auf gemeinsam genutzten Geräten.

Ein Anbieterwechsel darf bestehende Konten und Projektzuordnungen nicht stillschweigend
neu verbinden. Sicherheitsprüfungen nicht lockern, um einen Test zum Bestehen zu bringen.

## Mit KI-Assistenten arbeiten

`AGENTS.md` ist der gemeinsame Einstieg für Coding-Assistenten. Lass den Assistenten den
vorhandenen Arbeitsstand lesen, bevor er Änderungen macht. Uncommittierte Änderungen anderer
Mitwirkender müssen erhalten bleiben. Gib ein konkretes Ziel und den gewünschten Umfang an.

Wer einen KI-gestützten Beitrag einreicht, prüft den Diff und die betroffenen Abläufe selbst.
Beschreibe tatsächliche Änderungen und Prüfergebnisse; generierte Erklärungen ersetzen keine
Verifikation. Nenne ausgelassene Prüfungen und offene Annahmen ausdrücklich.
Der MCP-Skill des Editors dient der Modellierung im laufenden Editor und ersetzt nicht die
Arbeitsregeln für Änderungen am Wrapper-Quellcode.

## Pull Requests und Fehlerberichte

Ein Pull Request soll das Problem, das neue Verhalten, die betroffenen Bereiche und die
Prüfung verständlich erklären. Hebe Änderungen an Datenformaten, Eigentümerbindungen,
Konfiguration oder Deployment hervor. Gib an, ob bestehende Installationen eine Migration
oder neue Einstellungen benötigen. Nutze die [PR-Vorlage](.github/pull_request_template.md).

Ein Fehlerbericht benötigt den betroffenen Commit oder die Version, Schritte zum Nachstellen,
erwartetes und tatsächliches Verhalten sowie relevante Angaben zu PHP, Browser und Betriebssystem.
Protokolle und Screenshots vor dem Teilen anonymisieren. Keine Secrets, Cookies, Tokens,
echten Kontokennungen oder Schülerprojekte veröffentlichen.

Sicherheitsprobleme vertraulich nach [SECURITY.md](SECURITY.md) melden.
Gehe respektvoll und konstruktiv mit anderen um; hilfreiche Nachfragen und sorgfältige
Fehlerberichte sind ebenso willkommen wie Code.
