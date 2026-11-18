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
