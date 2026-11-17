# Fachbegriffe

Diese Begriffe sollen in Aufgaben, Oberfläche, Dokumentation und Tests dieselbe Bedeutung
haben. Bestehende Codebezeichner können abweichen; eine Begriffspräzisierung ist kein Auftrag,
sie überall umzubenennen.

| Begriff | Bedeutung und Beispiel |
|---|---|
| Anmeldeserver / OIDC-Anbieter | Externer Dienst, der die Anmeldung bestätigt. IServ ist die aktuelle Anbindung. Adressen werden je Deployment privat konfiguriert; freie Endpunktpfade, Anzeigename und Claim-Zuordnung sind als Verallgemeinerung geplant. |
| OIDC-Client | Registrierung des Wrappers beim Anmeldeserver mit Client-ID, Callback und privatem Secret. Eine Client-ID ist kein Benutzerkonto. |
| Claim | Vom Anbieter gelieferte Angabe über die angemeldete Identität. Nur geprüfte, normalisierte Claims dürfen eine Identitäts- oder Rechteentscheidung beeinflussen. |
| Externe Identität | Anbieter und stabile Kennung des Benutzers. Aktuell wird die Eigentümerbindung aus Issuer und `iserv:uuid` abgeleitet; `sub` bindet die OIDC-Antwort und UserInfo aneinander. Ein späterer Anbieterwechsel braucht eine ausdrückliche Zuordnungsstrategie. |
| Internes Konto / Eigentümer-ID | Interne stabile Kennung, der Projekte zugeordnet sind. Anzeigename, Client-ID und Rollenname ersetzen diese Kennung nicht. |
| Principal-Register | Privates serverseitiges Register der bekannten Identitäten und ihrer zuletzt gespeicherten SSO-Einstufung. Es ist kein vollständiges Schulverzeichnis. |
| Eigentümer | Konto, dessen Projektbereich eine Datei gehört. Öffnet die Betreuung eine Schülerdatei, bleibt der Schüler Eigentümer. |
| Handelndes Konto / Akteur | Konto, das die aktuelle Aktion ausführt. Es kann sich beim betreuten Bearbeiten vom Eigentümer unterscheiden. |
| Betreuung | Durch eine konfigurierte, geprüfte Gruppe erteilte Berechtigung, Schülerdateien zu lesen, herunterzuladen und zu bearbeiten. Sie erlaubt kein Löschen. |
| Admin-Dateirechte | Durch eine gesonderte geprüfte Gruppe erteilte Rechte auf Dateien aller registrierten Konten, einschließlich Löschen. Eine allgemeine Anbieterrolle wie `ROLE_ADMIN` genügt nicht. |
| Schülerzuordnung | Einstufung eines Eigentümers anhand der zuletzt gespeicherten SSO-Claims. Sie bleibt nach der aktuellen Entscheidung bis zu dessen nächster Anmeldung bestehen. |
| Sitzung | Serverseitig geprüfter Anmeldezustand mit Ablauf, Geltungsbereich und Widerruf. Eine sichtbare Profilanzeige oder ein MCP-Token allein ersetzt keine gültige Sitzung. |
| Vorlage / Arbeitsauftrag | Für Lernende bereitgestelltes CAD-Projekt beziehungsweise zugehörige Aufgabenbeschreibung. Die Veröffentlichung eines Projekts ist ein Snapshot; Lernende arbeiten an einer eigenen Kopie. |
| Kandidatenpaket | Lokal gebautes Paket für Prüfungen. Ein erfolgreicher Paketbau bedeutet weder Installation noch produktive Freigabe. |
| Deployment | Konkrete Bereitstellung mit eigener privater Konfiguration, öffentlichem Webverzeichnis und privaten Laufzeitdaten. Eine öffentliche Beispielkonfiguration ist kein Deployment-Nachweis. |

Rechte und Aktualität: [Berechtigungsmodell](docs/sso-berechtigungsmodell.md).
Dauerhafte Entscheidungen: [Architekturentscheidungen](docs/adr/README.md).
