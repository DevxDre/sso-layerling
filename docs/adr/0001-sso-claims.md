# 0001: SSO-Claims und letzte Schülerzuordnung

Status: beschlossen; bestehende Entscheidung aus dem [SSO-Berechtigungsmodell](../sso-berechtigungsmodell.md)
zusammengefasst. Diese ADR führt keine neue Rechteentscheidung ein.

## Anlass

Persönliche Projekte müssen getrennt bleiben. Betreuung benötigt Zugriff auf Schülerdateien,
auch wenn deren Eigentümer gerade nicht angemeldet sind. Dafür braucht der Wrapper eine
festgelegte Quelle und Aktualitätsregel für die Eigentümer-Einstufung.

## Entscheidung

Der Wrapper verwendet ausschließlich validierte SSO-Claims. Es gibt keine zusätzliche
IDM-/LDAP-Verbindung und keinen periodischen Verzeichnisabgleich. Die beim letzten Login
gespeicherte Schülerzuordnung eines Eigentümers gilt bis zu dessen nächster Anmeldung.
Betreuungs- und Admin-Dateirechte beruhen auf ausdrücklich konfigurierten, geprüften Gruppen;
Anzeigenamen und allgemeine Admin-Rollen genügen nicht.

## Konsequenzen

Ein Gruppen- oder Rollenwechsel beim Anbieter wird nicht durch einen Hintergrundabgleich
übernommen. Ein erneuter Login aktualisiert die gespeicherte Einstufung. Die Policy prüft
bei Dateizugriffen das private Register; vorhandene Sitzungen dürfen eine dort bereits
übernommene Rechteänderung nicht durch alte Browserangaben umgehen.
Die Betreuung darf Schülerdateien bearbeiten, aber nicht löschen. Admin-Dateirechte
umfassen zusätzlich Löschen und Zugriff auf alle registrierten Eigentümer.
Ein geänderter fachlicher Vertrag zur Aktualität benötigt eine neue Entscheidung samt Tests.
