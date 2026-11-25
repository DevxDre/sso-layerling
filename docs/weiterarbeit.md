# Entwicklungsstand

Stand: 19.11.2026. Einstieg über `AGENTS.md`, `README.md` und `CONTRIBUTING.md`.
Begriffe: [Glossar](../GLOSSARY.md). Geplante Entwicklung: [Roadmap](roadmap.md).

## Technischer Stand

Der PHP-Wrapper verbindet OIDC-Anmeldung mit persönlichen Layerling-Projekten,
Betreuungs-/Adminrechten, Vorlagen und einem kontrolliert gebauten statischen CAD-Export.
Das [OIDC-Profil](oidc-profile.md) legt Anzeigename, Endpunkte, Scopes und Claim-Zuordnungen
fest. Paketierte Profile und Berechtigungsbindungen liegen in der privaten App.
Öffentliche Quellen und Tests verwenden ausschließlich reservierte Beispieladressen.

Der Editor wird aus dem Pin in `upstream.lock.json` gebaut; Adapter und zusätzliche
Runtime-Prüfsummen stehen in `config/cad-adapter.lock.json`. Die vorhandenen Firefox-
Upload- und SVG-Silhouettenkorrekturen sind enthalten. Eine Internetverbindung und
getrennte Browserprofile sind für die erste Version vorgesehen.

Der CAD-Kandidatenbau kann mit `--layerling-commit` einen kompatiblen Nachfolger des
geprüften Pins verwenden. Paket und Buildbericht nennen den tatsächlich gebauten Commit.
Änderungen an Adapter-Eingabedateien, Speicher-Backend oder npm-Abhängigkeiten erfordern
eine gesonderte Prüfung und Aktualisierung des Pins. Die Runtime-Prüfsummen gelten weiter.

Der Pin steht auf Layerling 1.165.2 (`c3fb723e0`) mit Manifold 3.5.5 und OCCT 5.17.1.
Der CAD-Adapter hält auch beim neuen Rücksprung nach einem Ladefehler den ausgewählten
Projektbereich unter `/cad.php`. Der Schul-Build deaktiviert die neuen Live-Ankündigungen
von GitHub. Der OCCT-Adapter für die Content Security Policy wird weiterhin angewendet.

Rechte werden aus validierten SSO-Claims und dem privaten Principal-Register abgeleitet.
Es gibt keinen IDM-/LDAP-Hintergrundabgleich. Die letzte Schülerzuordnung gilt bis zur
nächsten Anmeldung des Eigentümers. Der Rechtevertrag ist in den
[Architekturentscheidungen](adr/0001-sso-claims.md) und im
[Berechtigungsmodell](sso-berechtigungsmodell.md) dokumentiert.

Dateien und CAD-Vorlagen nutzen eine gemeinsame Kopfzeile und ein responsives
Stylesheet mit Schrift und Farbwerten aus dem Layerling-Dashboard. Das CAD-Paket
liefert das vorhandene Layerling-Logo, im reinen Dateitest steht der Schriftzug
allein. Die Dateiansicht bricht lange Pfade um und setzt beim Ordnerwechsel den
Tastaturfokus auf die Ordnerüberschrift. Kopiererfolg und Namenskonflikte erscheinen
am Formular der ausgewählten Vorlage.

Die Rechteverwaltung nutzt dieselbe Gestaltung. Gespeicherte Regeln erscheinen
auf schmalen Ansichten mit beschrifteten Feldern. Bei Eingabefehlern bleiben
die Formularwerte zur Korrektur erhalten. Haben sich die Gruppenvorschläge
inzwischen geändert, müssen betroffene Gruppenaccounts erneut gewählt werden.

Die Kontoseite und der manuelle Anmeldeeinstieg verwenden dieselbe Gestaltung.
Im Konto stehen Name, Account und Klasse vor den aufklappbaren Angaben zu Rollen
und Gruppen. Das Stylesheet ist auch im reinen SSO-Testpaket enthalten.

Bei fehlgeschlagenen SSO-Anmeldungen zeigt die Fehlerseite jetzt einen festen
technischen Fehlercode und eine kurze Einordnung. Zulässige Detailcodes wie ein
OAuth-Fehlercode oder der betroffene Claim helfen bei der Diagnose; Freitext des
Anmeldedienstes und interne Serverfehlerdetails werden nicht ausgegeben.

Das Kontomenü in der CAD-Fußzeile öffnet sich über den Namen des ausgewählten
Kontos. Bei Konten mit der konfigurierten Schülerrolle folgen vorhandene Klassen
in Klammern. Ein fremder Projektbereich trägt den Zusatz „Fremdes Konto“.

## Private Daten und bestehende Installationen

Reale Zugangsdaten, Benutzer-/Gruppenkennungen, Betriebsnotizen und Installationsprotokolle
gehören ausschließlich in ignorierte private Dateien außerhalb öffentlicher Webverzeichnisse.
Sie sind kein Bestandteil dieses Repositories. Öffentliche Testnamen sind als unproblematisch
geprüft. Die fachlichen Zuordnungen sind je Deployment konfigurierbar.

Bestehende Eigentümerbindungen, Projekte und Vorlagen bei Umstellungen erhalten.
Die [Migrationsbeschreibung](installation-und-migration.md) erläutert die Grenzen der
Umbenennung und der neuen Cookie-/Browser-Speichernamensräume.

Die Rechteseite unter `/rechte.php` verwaltet Regeln über die in der privaten `.env`
gesetzte OIDC-Admin-Rolle. Sie ist über das Kontomenü in der CAD-Fußzeile und die
Kontoseite erreichbar.
Der [Rechteleitfaden](sso-berechtigungsmodell.md#rechte-über-die-oberfläche-verwalten)
beschreibt die Priorität der Regeln, Vorlagengruppen und MCP-Freigaben.
Der Gruppenfilter für die Vorlagenverteilung unterstützt zusätzlich reguläre Ausdrücke
in PCRE-Syntax zwischen Schrägstrichen. Die vorhandenen Exakt- und Präfixmuster gelten
weiter. Anzeige und serverseitige Verteilung prüfen dieselben Muster.

## Prüfstand und offene Punkte

Für Layerling 1.165.2 bestanden unter PHP 8.4.19 die CAD-Build-, Installer- und
Deployment-Konfigurationstests sowie beide CAD-HTTP-/Chromium-Läufe für IServ
und das synthetische alternative OIDC-Profil.
Der Browserlauf prüfte unter anderem Wiederöffnen vom Server, getrennte Vorlagenkopien,
MCP sowie STEP- und SVG-Downloads unter der Content Security Policy.

Ein früherer Quellstand wurde mit OIDC-, Speicher-, Paketierungs- und Installerprüfungen
sowie einem neu gebauten CAD-Export geprüft. Zuletzt bestanden sieben CAD-Build-/Paket-
und vier CAD-Installerprüfungen. Im 25er CAD-HTTP-/Browserlauf bestanden 24 Fälle;
ein sporadischer Konflikt beim Kopieren einer Vorlage für das zweite Schülerkonto trat auf.
Die anschließende Einzelwiederholung bestand einschließlich STEP-/SVG-Downloads und
unabhängiger Schülerkopien. Diese Testauffälligkeit ist noch nicht abschließend geklärt.
Historische Ergebnisse sind kein neuer Testlauf nach späteren Änderungen.

Die MCP-Brücke unterstützt die gehostete Freigabe unter PHP-FPM und die lokale
Demo. Der gehostete Token endet mit der zugehörigen SSO-Sitzung. Der Client
wird aus dem gepinnten Layerling-Stand erzeugt. Anleitung: [MCP](mcp-test.md).

## Abnahme der OIDC-Generalisierung

Mit PHP 8.4.19 und dem neu gebauten CAD-Kandidaten aus dem unveränderten Pin
bestanden 26 CAD-HTTP-/Browserfälle für IServ und 28 für das synthetische
Campus-Profil. Dazu gehören Vorlagen, Rollen- und Gruppenrechte, Kontodiagnose,
Klassen sowie lokale MCP-Freigaben. Die integrierten Campus-Dateitests prüften
zusätzlich den Wechsel einer Gruppen-Claim-Zuordnung mit vorhandener Eigentümer-ID.
Der Installer-Test bestätigt die Upgrade-Grenzen bei Änderung des Identitätsclaims
und bei neuer Client-Registrierung mit `sub` als Eigentümerbindung.
Echte Anmeldeserver und gehostetes PHP-FPM wurden in dieser Abnahme nicht verwendet.

## Nächste Schritte

Den sporadischen Vorlagen-Browserkonflikt separat untersuchen. Die [Roadmap](roadmap.md)
hält den Abnahmevertrag für beide Deployment-Profile fest.

Prüfaufrufe: [SSO-Teststand](sso-teststand.md), [CAD-Integration](cad-integration.md).
Commit, Push und Deployment nur im ausdrücklich beauftragten Umfang durchführen.


## Deployment-Vorbereitung

Die CAD-Paketierung verwendet den neutralen Schalter `--hosted-test`. Gehostete Pakete
benötigen weiterhin eine ausdrückliche private Deployment-Konfiguration und einen sauberen
Quellcommit. Für bestehende Installationen sind alte Marker/Layout und neue Zielpfade vor
der Umschaltung gesondert zu migrieren. Ein separates Staging-Ziel benötigt derzeit noch
geprüft konfigurierbare Installer-Pfade. Öffentliche Anleitungen enthalten keine konkreten
SSH-Zugangspunkte; reale Transfer- und Migrationspläne werden privat geführt.
