# Aufgaben mit KI-Assistenten bearbeiten

Dieser Ablauf ergänzt [CONTRIBUTING.md](../../CONTRIBUTING.md) und [AGENTS.md](../../AGENTS.md).
Für kleine, eindeutige Änderungen genügt die Aufgabenbeschreibung im Chat oder Issue.
Eine zusätzliche Spezifikationsdatei ist dafür nicht nötig. Bei umfangreichen oder
mehrstufigen Aufgaben die folgende Struktur im Issue oder in einer passenden Dokumentdatei nutzen.
Private Betriebsangaben bleiben in der ignorierten internen Dokumentation.

## Eine prüfbare Aufgabe beschreiben

```text
Ziel und Nutzer:
Wer soll nach welcher Handlung welches Ergebnis erreichen?

Aktueller Zustand:
Was geschieht bisher? Welche Beobachtung oder Quelle belegt das?

Umfang:
Was gehört zu dieser Änderung? Welche angrenzenden Themen bleiben offen?

Relevante Quellen:
Fachbegriffe, Rechtevertrag, Architekturentscheidungen, zuständige Module und Tests.

Akzeptanzkriterien:
Beobachtbare Ergebnisse eines vollständigen kleinen Nutzungspfads.
Bei Daten- und Rechteänderungen auch Wiederöffnen/Erhalt und unerlaubte Zugriffe abdecken.

Prüfung:
Welche Tests oder manuellen Abläufe belegen diese Kriterien?
Welche Voraussetzungen oder Grenzen hat die Prüfungsumgebung?
```

Vor der Umsetzung unklare Begriffe anhand des [Glossars](../../GLOSSARY.md) klären.
Fragen zu Datenverlust, Eigentümerbindung, Rechten oder Exportverhalten früh entscheiden.
Eine entscheidende fehlende Antwort nicht selbst als Zustimmung ersetzen; unabhängige
Arbeit kann weitergehen. Bereits klare Anforderungen brauchen keine erneute Bestätigung.

Beispiel für Betreuung: Eine berechtigte Lehrkraft öffnet ein Schülerprojekt, ändert eine
Form, speichert und öffnet es erneut. Die Änderung ist vorhanden, die Eigentümer-ID bleibt
gleich, und eine Löschanfrage wird abgelehnt. Ein fremdes Konto ohne passende Rechte erhält
auch über direkte API-Aufrufe keinen Zugriff.

## Verhalten belegen

Prüfungen sollen über den normalen Einstieg des betroffenen Ablaufs erfolgen: etwa Login,
Datei-API oder Editoroberfläche. Fachlogik lässt sich ergänzend mit kleinen Unit-Tests prüfen.
Ein Test, der ausschließlich private Hilfsfunktionen oder deren eigene Annahmen wiederholt,
belegt den vollständigen Nutzungspfad nicht.

Ein vorhandener Button, ein erfolgreicher HTTP-Status oder eine Dateigröße genügt nur,
wenn genau das die Anforderung ist. Beim Speichern beispielsweise Inhalt und Zuordnung
nach erneutem Öffnen prüfen. Beim Rechteentzug die nachfolgende tatsächliche Ablehnung
prüfen. Browserprüfungen sollen sichtbares Verhalten oder einen konkreten Browser-Vertrag
belegen, etwa dass nach Abmeldung gespeicherte Browserkopien entfernt werden.

## Abschließender Review

Nach der Umsetzung den gesamten Diff in einem eigenen Prüfschritt gegen die Akzeptanzkriterien,
Arbeitsregeln und Auswirkungen auf bestehende Daten ansehen. Das ist von der Aussage
„die Tests sind grün“ zu unterscheiden. Bei Änderungen an Rechten, Identitätsbindung oder
Unterrichtsabläufen ist eine zusätzliche fachliche Prüfung durch eine andere Person sinnvoll.
Das löst keine automatische Agent-Delegation aus und ersetzt keine beauftragte Freigabe.

Im Ergebnis nennen: gelöstes Problem, beobachtetes neues Verhalten, ausgeführte Prüfungen,
noch offene Kriterien und Auswirkungen auf Betrieb oder Daten. Vorher-/Nachher-Belege mit
synthetischen Daten verwenden. Für Unterrichtsabläufe hilft ein realistischer manueller
Versuch durch eine Lehrkraft; fehlende Rückmeldungen bleiben als offen gekennzeichnet.
