# Roadmap

Die folgenden Punkte sind geplant und beschreiben noch keine vollständig vorhandenen
Funktionen. Anbieter-, Anwendungs- und Callback-Adressen werden bereits beim Paketbau aus
privater Konfiguration übernommen. Die übrige Anbieterbindung wird schrittweise aufgelöst.

## OIDC-Anbindung je Deployment konfigurieren

- Anzeigename des Anmeldeservers und zugehörige Oberflächentexte konfigurieren.
- Anbieterabhängige OIDC-Endpunktpfade aus dem festen Anwendungscode lösen.
- Identitäts-, Anzeigenamen-, Benutzerkennungs-, Rollen- und Gruppen-Claims zuordnen und
  unterschiedliche Claim-Strukturen in ein einheitliches internes Modell normalisieren.
- Die bestehende Anbindung als geprüftes Anbieterprofil erhalten.

## Rollen, Gruppen und Klassen generalisieren

- Fachliche Funktionen wie Schülerzuordnung, Vorlagenveröffentlichung, Betreuung und
  Admin-Dateirechte über explizite Konfiguration an Anbieterrollen und Gruppenkennungen binden.
- Fest eingetragene Rollenmarker und Gruppenbezeichnungen aus fachlichen Entscheidungen
  und Diagnosefiltern entfernen. Anzeigenamen dürfen weiterhin keine Rechte verleihen.
- Klassen- und Kurszuordnung konfigurierbar machen, einschließlich des aktuell fest
  ausgewerteten Gruppenaccount-Präfixes `klasse.`.
- Fachliche Begriffe der Oberfläche und Bezeichnungen von Berechtigungsgruppen getrennt halten.
- Suchfilter in Diagnose-/Metadatenwerkzeugen aus Konfiguration beziehen oder historische
  Werkzeuge entsprechend kennzeichnen. Daraus entsteht keine neue IDM-/LDAP-Laufzeitverbindung.

Die überprüften Benutzer-, Gruppen- und Klassennamen im aktuellen Projektstand sind als
unproblematisch bestätigt und dürfen bestehen bleiben. Ihre Verwendung als Testdaten ist
kein offener Bereinigungspunkt. Generalisiert werden die Annahmen im Anwendungscode;
Tests behalten nachvollziehbare, synthetische Fixtures.

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
- Die lokale MCP-Anbindung vor einer gehosteten Freigabe separat unter PHP-FPM prüfen.
