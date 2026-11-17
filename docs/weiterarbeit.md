# Entwicklungsstand

Stand: 17.11.2026. Einstieg über `AGENTS.md`, `README.md` und `CONTRIBUTING.md`.
Begriffe: [Glossar](../GLOSSARY.md). Geplante Entwicklung: [Roadmap](roadmap.md).

## Technischer Stand

Der PHP-Wrapper verbindet OIDC-Anmeldung mit persönlichen Layerling-Projekten,
Betreuungs-/Adminrechten, Vorlagen und einem kontrolliert gebauten statischen CAD-Export.
Die aktuelle Anbieteranbindung enthält noch IServ-spezifische Endpunktpfade, Claims und Texte.
Anbieter-, Anwendungs- und Callback-Adressen kommen beim Paketbau aus privater Konfiguration.
Öffentliche Quellen und Tests verwenden ausschließlich reservierte Beispieladressen.

Der Editor wird aus dem Pin in `upstream.lock.json` gebaut; Adapter und zusätzliche
Runtime-Prüfsummen stehen in `config/cad-adapter.lock.json`. Die vorhandenen Firefox-
Upload- und SVG-Silhouettenkorrekturen sind enthalten. Eine Internetverbindung und
getrennte Browserprofile sind für die erste Version vorgesehen.

Rechte werden aus validierten SSO-Claims und dem privaten Principal-Register abgeleitet.
Es gibt keinen IDM-/LDAP-Hintergrundabgleich. Die letzte Schülerzuordnung gilt bis zur
nächsten Anmeldung des Eigentümers. Der Rechtevertrag ist in den
[Architekturentscheidungen](adr/0001-sso-claims.md) und im
[Berechtigungsmodell](sso-berechtigungsmodell.md) dokumentiert.

## Private Daten und bestehende Installationen

Reale Zugangsdaten, Benutzer-/Gruppenkennungen, Betriebsnotizen und Installationsprotokolle
gehören ausschließlich in ignorierte private Dateien außerhalb öffentlicher Webverzeichnisse.
Sie sind kein Bestandteil dieses Repositories. Öffentliche Testnamen sind als unproblematisch
geprüft und müssen nicht bereinigt werden. Ihre fachlichen Zuordnungen sollen gemäß Roadmap
je Deployment konfigurierbar werden.

Bestehende Eigentümerbindungen, Projekte und Vorlagen bei Umstellungen erhalten.
Die [Migrationsbeschreibung](installation-und-migration.md) erläutert die Grenzen der
Umbenennung und der neuen Cookie-/Browser-Speichernamensräume.

## Prüfstand und offene Punkte

Der übernommene Quellstand wurde mit OIDC-, Speicher-, Paketierungs- und Installerprüfungen
sowie einem neu gebauten CAD-Export geprüft. Zuletzt bestanden sieben CAD-Build-/Paket-
und vier CAD-Installerprüfungen. Im 25er CAD-HTTP-/Browserlauf bestanden 24 Fälle;
ein sporadischer Konflikt beim Kopieren einer Vorlage für das zweite Schülerkonto trat auf.
Die anschließende Einzelwiederholung bestand einschließlich STEP-/SVG-Downloads und
unabhängiger Schülerkopien. Diese Testauffälligkeit ist noch nicht abschließend geklärt.
Historische Ergebnisse sind kein neuer Testlauf nach späteren Änderungen.

Die lokale MCP-Anbindung ist mit synthetischen Konten geprüft. Eine gehostete Freigabe
benötigt einen gesonderten PHP-FPM-Betriebstest. Anleitung: [MCP-Test](mcp-test.md).

## Nächste Schritte

Die [Roadmap](roadmap.md) konkretisiert die Anbieter-, Rollen-, Gruppen- und Klassen-
Generalisierung samt Abnahmekriterien für zwei unterschiedliche Deployment-Profile.
Den sporadischen Vorlagen-Browserkonflikt separat untersuchen.

Prüfaufrufe: [SSO-Teststand](sso-teststand.md), [CAD-Integration](cad-integration.md).
Commit, Push und Deployment nur im ausdrücklich beauftragten Umfang durchführen.
