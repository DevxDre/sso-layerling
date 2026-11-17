# Arbeitsanweisungen für sso-layerling

## Einstieg und Übergabe

Zuerst `README.md`, `CONTRIBUTING.md` und `docs/weiterarbeit.md` lesen; Git-Status und tatsächliche Dateien prüfen.
Für Arbeiten an der bestehenden Installation zusätzlich die lokale, ignorierte
`.local/entwicklung-intern.md` lesen. Dort liegen die vollständigen früheren Fachpläne,
Betriebsnachweise, realen Zuordnungen und offene Punkte. Fehlt diese Datei, keine realen
Betriebsangaben oder Freigaben aus öffentlichen Beispielen ableiten.
Fachbegriffe: `GLOSSARY.md`; dauerhafte Entscheidungen: `docs/adr/README.md`.
Aufgaben und Abnahme: `docs/agents/aufgaben.md`; geplante Generalisierung: `docs/roadmap.md`.
Diese Quellen passend zur Aufgabe lesen.
Keine automatische Agent-Delegation.

Nach Zwischen- und Endständen die nächsten konkreten Schritte nennen. Innerhalb des
beauftragten lokalen Umfangs selbstständig fortfahren. Öffentlichen technischen Stand
in `docs/weiterarbeit.md`, reale Betriebsinformationen ausschließlich intern dokumentieren.
Historische Prüfergebnisse nicht als neue Testläufe ausgeben.

## Änderungen mit Coding-Assistenten

- Die Aufgabe aus Nutzersicht mit beobachtbaren Akzeptanzkriterien verstehen. Unklare
  Entscheidungen zu Daten, Identitätsbindung, Rechten oder Export früh klären. Für kleine,
  eindeutige Änderungen keine zusätzlichen Tickets oder Spezifikationen verlangen.
- Fachbegriffe aus `GLOSSARY.md` konsistent verwenden. Dauerhafte Architekturentscheidungen
  mit Anlass und Konsequenzen als ADR festhalten; Vorschläge nicht als beschlossen ausgeben.
- Vor Änderungen das zuständige Modul und seine Tests lesen. Bestehende Muster verwenden;
  pro Änderung ein konkretes Thema bearbeiten und zusätzliche Umbauten vermeiden.
- Vorhandene uncommittierte Änderungen anderer Mitwirkender erhalten. Kein pauschales
  Zurücksetzen, Überschreiben oder Aufräumen fremder Arbeit. Diffs vor und nach der Arbeit prüfen.
- Nicht vorhandene Konfiguration, Prüfergebnisse oder Freigaben nicht erfinden. Geplante
  Funktionen klar vom implementierten Verhalten unterscheiden.
- Allgemeines OIDC-SSO ist das Ziel; aktuelle IServ-spezifische Stellen bei Änderungen
  berücksichtigen. Anzeigename, Endpunktpfade und Claim-Zuordnung sollen später pro Deployment
  konfigurierbar werden. Bestehende Eigentümerbindungen dabei erhalten.
- Generierte Exporte nicht direkt reparieren: Quelle oder Adapter ändern, anschließend
  neu bauen. Pin, Preimages und Prüfsummen nicht nur anpassen, um eine Integritätsprüfung
  zu umgehen; den referenzierten Quellstand und die notwendige Änderung nachvollziehen.
- Für Verhaltensänderungen passende Prüfungen aus `CONTRIBUTING.md` wählen. Bei Bugs
  gezielte Regressionen ergänzen, wenn sie das fehlerhafte Verhalten sinnvoll absichern.
  Reine Dokumentationsänderungen brauchen Link-/Beispielprüfung, keine neuen Laufzeittests.
- Verhalten über den normalen Einstieg prüfen. Bloße Button-Existenz, Statuscodes oder
  Dateigrößen ersetzen keinen Nachweis für Speichern/Wiederöffnen, Inhaltsgleichheit oder
  Zugriffsschutz. Tests nicht auf eine Wiederholung der Implementierung reduzieren.
- Nach Umsetzung den Diff in einem eigenen Review-Schritt gegen Aufgabe, Rechtevertrag
  und Bestandsdaten prüfen. Offene Akzeptanzkriterien ausdrücklich nennen. Zusätzliche
  Personen oder Agents nur im dafür beauftragten Rahmen einbeziehen.
- UI-Abläufe nach Möglichkeit im Browser prüfen. Screenshots nur mit synthetischen Daten.
  Fehlende Browser-, Server- oder Buildmöglichkeiten als Grenze nennen.
- Abschluss und PR beschreiben Problem, neues Verhalten, tatsächlich ausgeführte Prüfungen,
  ausgelassene Checks und offene Punkte. Keine alten Ergebnisse als frische Prüfung ausgeben.

## Architektur und Rechte

Layerling möglichst unverändert aus einem gepinnten Git-Stand bauen. Änderungen am Wrapper,
Paketierung und Tests gehören hierher; das Geschwisterrepo möglichst unverändert lassen.
Erste Version online mit getrennten Browserprofilen. Validierte SSO-Anmeldung gewährt
persönlichen Speicher. Betreuung darf Schülerdateien lesen, herunterladen und bearbeiten,
nicht löschen. Admins dürfen Dateien aller Nutzer zusätzlich löschen. Nur exakt geprüfte
Gruppenkennungen entscheiden; Gruppennamen und `ROLE_ADMIN` allein reichen nicht.
Nur SSO-Daten, kein IDM-/LDAP-/periodischer Verzeichnisabgleich. Die letzte gespeicherte
Schülerklassifikation des Eigentümers gilt bis zu dessen nächstem Login.
Reale Gruppenbindungen privat konfigurieren, nicht raten oder in Beispiele übernehmen.

## Private Daten und Git

`.gitignore` laufend pflegen. `.local/`, private `config/*.local.json`, `.env`, Abhängigkeiten,
Builds, Logs, Sitzungen und Nutzerprojekte gehören nicht ins Repository. Bereits getrackte
Dateien werden durch Ignore-Regeln nicht geschützt; tatsächliche Dateiauswahl und Diff prüfen.
Öffentliche Beispiele und Tests müssen synthetische Kennungen und reservierte Beispiel-Domains verwenden.
Reale Schul-/Anwendungsadressen ausschließlich privat konfigurieren.
Gehostete Pakete benötigen `--deployment-config` mit expliziten privaten Metadaten.
Secrets ausschließlich in privater `.env` außerhalb aller DocumentRoots halten.
Private Betriebsinformationen und historische Installationsprotokolle gehören nicht in die öffentliche Git-Historie.

## Grenzen und Verifikation

Kein Commit, Push oder produktives Deployment ohne ausdrücklichen Auftrag.
Keine neuen Pakete/Versionen ohne Abstimmung. Keine Zugangsdaten ausgeben oder lokale
Geheimnisdateien ungefragt auslesen. Keine echten Konten oder Nutzerdateien für synthetische
Tests verändern. Fixtures nie als öffentlichen Login ausliefern. Sicherheitsprüfungen
nicht abschwächen; Rechte für jeden Speicherzugriff prüfen und bei fehlendem Nachweis ablehnen.
Prototyp-FPM-Sperre erhalten. Temporäre Server und Testdaten nach Prüfungen entfernen.

PHP 8.4 ausdrücklich wählen. Betroffene Tests nach Änderungen ausführen; Aufrufe stehen
in `docs/sso-teststand.md` und `docs/cad-integration.md`. Kirby-Tests gehören nicht hierher.
