# Roadmap

## OIDC-Generalisierung

Die [Profilkonfiguration](oidc-profile.md) setzt die Anbieter-, Rollen-, Gruppen- und
Klassenzuordnung pro Deployment um. IServ bleibt das kompatible Standardprofil.
Der Abnahmevertrag für Änderungen an der Profilkonfiguration steht unten.

## Abnahme der Generalisierung

- Zwei synthetische Deployment-Profile mit verschiedenen Anzeigenamen, Rollen-, Gruppen-
  und Klassenkonventionen funktionieren ohne manuelle Änderungen am Anwendungscode.
- Beide Profile erfüllen denselben fachlichen Rechtevertrag: persönliche Dateitrennung,
  Betreuung ohne Löschrecht und gesonderte Admin-Dateirechte. Unbekannte oder beschädigte
  Claims gewähren keine zusätzlichen Rechte.
- Login, Dateiverwaltung, Vorlagen, Diagnose und MCP-Freigaben verwenden die jeweils
  konfigurierten Zuordnungen. Keine zusätzlichen Rechte durch gleichlautende Anzeigenamen.
- Bestehende Eigentümer-IDs, Projekte und Vorlagen bleiben bei einer Konfigurationsumstellung
  erhalten. Ein Anbieter- oder Identitätswechsel benötigt eine ausdrückliche Migrationsstrategie.
- Die [bestehende Entscheidung zur Rechteaktualität](adr/0001-sso-claims.md) bleibt gültig;
  die Generalisierung führt keinen Hintergrundabgleich ein.

## Weitere Arbeit

- Den dokumentierten sporadischen Browserkonflikt beim Kopieren einer Vorlage untersuchen.
- Neue gehostete MCP-Installationen unter PHP-FPM mit dem jeweiligen OIDC-Profil abnehmen.

## Datenschutz und zusätzliche Schutzschichten

Der Beitrag [„Datenschutz geprüft: nicht alles bleibt im Haus“](https://schmidbauer.io/layerling-teil-3-zeichnung-app-und-eigener-server-in-der-schule/)
berichtet für eine Layerling-Instanz von 117 Anfragen an den eigenen Server, vier an
`api.github.com` und zwei an `raw.githubusercontent.com`. Laut Beitrag lösten Update-
und Entwicklermitteilungen diese GitHub-Anfragen aus; die beobachteten Anfragen
enthielten keine Entwürfe oder Namen, übermittelten GitHub aber die IP-Adresse des
Schulnetzes. Das ist ein Befund des Beitrags, noch keine eigene Messung dieses Wrappers.

Der Wrapper deaktiviert bereits die direkte Release-Abfrage und den Offline-Service-
Worker. Die CAD-Antwort begrenzt mit CSP Ressourcen und Verbindungen auf den eigenen
Ursprung; notwendige lokale `blob:`-Ressourcen bleiben erlaubt. Die folgende Prüfung
ist noch offen, insbesondere nach Änderungen am Layerling-Pin:

- [ ] Einen frisch gebauten Kandidaten in einem sauberen Browserprofil netzwerktechnisch
  prüfen: Startseite, Editor, Versionshinweise, Hilfeseiten, Import und Export. Ziele,
  Initiator und Auslöser dokumentieren und bestätigen, dass kein automatischer Request
  an GitHub, andere Drittserver oder Videoplattformen erfolgt.
- [ ] Gezielte Regression ergänzen, die im Browser externe Script-, Bild- und
  Verbindungsziele als durch die CSP blockiert nachweist. Beim Upstream-Update wiederholen.
- [ ] YouTube-/Video-Hilfen prüfen: Inhalte dürfen erst nach einem bewussten Klick laden;
  den dann entstehenden Drittanbieteraufruf verständlich dokumentieren.
- [ ] Prüfen, ob der sichtbare „Source“-Verweis auf den lokal konfigurierten
  Layerling-Fork zusammen mit `sso-layerling` den vollständigen passenden Quellstand
  der gebauten Schulinstanz zugänglich macht. Buildadapter und Wrapperänderungen
  müssen für Nutzer auffindbar sein; Umsetzung und Freigabe der AGPLv3-Pflichten
  fachlich prüfen.
- [ ] Für den Hostingbetrieb ausgehenden Netzwerkverkehr des Webprozesses auf die
  tatsächlich nötigen Ziele begrenzen, insbesondere den konfigurierten OIDC-Anbieter.
  DNS, Paketupdates und Administration getrennt berücksichtigen; keine pauschale
  Sperre umsetzen, bevor Login und Wartungswege geprüft sind.
- [ ] Betriebsrechte und Aufbewahrung abnehmen: Webroot/Programmdateien schreibgeschützt
  für den Webprozess, private Daten getrennt und minimal berechtigt, Logs ohne Tokens
  oder Projektinhalte mit festgelegter Löschfrist sowie verschlüsselte Backups mit
  nachvollziehbarer Retention und Löschverfahren.
- [ ] Prüfen, ob Build- und Abhängigkeitsprüfung durch reproduzierbare Builds,
  nachvollziehbare Herkunft und einen dokumentierten Freigabeschritt ergänzt werden soll.
