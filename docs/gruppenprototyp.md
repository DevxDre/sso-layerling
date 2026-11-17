# Lokaler Prototyp: gruppenbasierte Zugriffe

Stand: 03.11.2026. Lokal implementiert und geprüft; keine echten IServ-Claims,
kein Browser-Frontend und keine Produktionsfreigabe.

**Neue Zielentscheidung:** ausschließlich SSO mit Gruppenfallback bei fehlenden Rollen;
Eigentümer-Schülerstatus bis zum nächsten Login. Das ist im folgenden historischen
35-Test-Stand noch nicht implementiert. Siehe [SSO-Modell](sso-berechtigungsmodell.md).

## Umgesetzte Rechte

| Akteur | Ziel | Lesen/Download | Bearbeiten | Löschen |
|---|---|---|---|---|
| Normaler Nutzer | eigener Ordner | ja | ja | ja |
| Normaler Nutzer | fremder Ordner | nein | nein | nein |
| Betreuung | bestätigter aktiver Schüler | ja | ja | nein |
| Betreuung | Nichtschüler/unklare Rolle | nein | nein | nein |
| Admin-Gruppe | jeder registrierte Eigentümer | ja | ja | ja |

Bearbeiten umfasst Anlegen, Speichern, Kopieren, Umbenennen und Verschieben innerhalb
desselben Eigentümerordners, einschließlich Ordnern und gespeicherten Exporten.
Eigentümerwechsel sind nicht implementiert. Fremde persönliche Einstellungen werden auch
für Admins nicht freigegeben. Betreuungsrechte erfordern im Prototyp genau die bestätigte
Rolle `ROLE_STUDENT`; zusätzliche oder unbekannte Rollen gewähren keine Schülerfreigabe.
Admins können auch auf Dateien archivierter/gesperrter Eigentümer zugreifen. Ein gesperrter
Akteur kann hingegen keine Speicheroperation ausführen und sich weiterhin lokal abmelden.

## Privates Register und aktuelle Entscheidungen

- `private/principals.json`: interne Benutzer-ID → `enabled`, `checkedAt`, `roles`, `groups`.
  Keine dieser Angaben kommt aus einem Speicherrequest oder einem frei setzbaren Header.
- `Policy` liest das Register für jede Speicheranfrage neu, statt sich auf Gruppen in der
  Sitzung zu verlassen. Eine Registeränderung wirkt nach abgeschlossener Aktualisierung
  auf die folgenden bzw. noch nicht zugelassenen Anfragen derselben Sitzung.
- `private/authorization.lock`: Request hält einen Shared-Lock für seine gesamte Laufzeit.
  Vertrauenswürdige Writer müssen einen Exclusive-Lock nehmen und das Register atomar ersetzen.
  Bereits zugelassene Requests dürfen abschließen. Writer dürfen unter dem Exclusive-Lock
  nicht auf native Sitzungssperren warten; sonst wäre ein umgekehrter Lock-Ablauf möglich.
- `privilegeEvidenceSeconds = 300` ist ein vorläufiger Prototypwert. Für Fremdzugriff muss
  der Gruppenstand des Akteurs innerhalb dieser Frist liegen. Betreuung benötigt außerdem
  einen frischen Schülernachweis des Eigentümers. Admins benötigen keinen Schülernachweis.
- Fehlende, zukünftige, abgelaufene, beschädigte oder widersprüchliche Nachweise gewähren
  keine Fremdrechte. Fehlendes/defektes Gesamtregister sperrt Speicherzugriffe geschlossen.
- Eigene Dateien erfordern weiterhin ein freigeschaltetes Konto und eine gültige Sitzung;
  abgelaufene Gruppennachweise allein entziehen nicht den persönlichen Speicher.

Die Paketierung legt Gruppenkennungen zunächst auf `null`: Fremdrechte sind standardmäßig aus.
Nur die Test-Fixture setzt `test-makerspace-id` und `test-admins-id`. Das sind ausdrücklich
keine vermuteten IServ-Gruppenkennungen. Namen wie `Admins`, Rollen wie `ROLE_ADMIN`,
Teilstrings und ähnlich geschriebene Kennungen verleihen keine zusätzlichen Rechte.

## Eigentümerauswahl und unverändertes Original

`_sso_owner=<interne 32-stellige Hex-ID>` ist ein angefragter Eigentümer, keine Berechtigung.
Ohne Parameter bleibt der eigene Ordner gewählt. Der Server prüft Akteur, Eigentümer und
Operation zentral und setzt erst danach den konkreten Pfad für das unveränderte Layerling-Skript.

`Operation` bildet die Dispatch-Fälle des festgehaltenen Originals ausdrücklich auf Lesen,
Schreiben, Einstellungen und Löschen ab. Unbekannte Parameter, Arraywerte und mehrdeutige
Aktionen werden abgelehnt. Alle Zugriffe bleiben auf genau einen Eigentümer begrenzt;
Suche und Gesamtliste sind noch keine eigentümerübergreifende Sammelansicht.

JSON-Vorschaubildlinks erhalten den gewählten Eigentümerparameter. Der spätere Bildabruf
prüft die Rechte erneut und bleibt `private, no-store`. Ein Rollenentzug macht einen zuvor
berechtigten Bildlink damit nicht zu einem dauerhaften Zugriffsschlüssel.

Die Originaldatei ist weiterhin identisch mit dem in `upstream.lock.json` festgehaltenen
Commit/Hash. Das neue Verhalten liegt ausschließlich in unserer Schicht.

## Gespeicherte Exporte

Das Original speichert STL, 3MF, OBJ, STEP/STP, SVG, DXF, PNG und PDF, bietet aber einzelne
Downloads/Löschungen nur für Projekte. `ExportFiles` ergänzt deshalb im autorisierten Ordner:

- `GET store.php?exportFile=shape.stl`: Download als Attachment mit No-Store und Nosniff.
- `DELETE store.php?exportFile=shape.stl`: Löschen mit geprüftem CSRF/Origin und `If-Match`.
- `POST` mit `exportFile` bleibt beim unveränderten Uploadpfad des Originals.

Für fremde Dateien kommt jeweils `_sso_owner` hinzu. Downloads bleiben auch bei SVG/PDF
Attachments, keine aktive Seite auf dem Ursprung der Anwendung. Nur die erlaubten Dateitypen
und bestehende persönliche Unterordner sind zugelassen; private Pfade und Symlinks werden
abgelehnt. Löschungen teilen die Dateilock-Konvention mit dem Original-Upload. Ein Hash-ETag
und die Prüfung von `If-Match` verhindern die Löschung einer inzwischen geänderten Exportdatei.

## Audit

Jeder wohlgeformte Fremdzugriffsversuch erhält vor der Berechtigungsentscheidung einen
Intent-Eintrag und am Requestende einen Abschlusseintrag mit HTTP-Status in `private/audit.jsonl`.
Erfasst werden ausschließlich zufällige Vorgangs-ID, interne Akteur-/Eigentümer-ID,
Operationsklasse, Zeitpunkt und Status. Keine Projektinhalte, Dateinamen, Sitzungstokens oder
CSRF-Tokens. Kann der Intent nicht geschrieben werden, wird der Fremdzugriff abgelehnt.
Ein bereits geschriebener Intent bleibt auch dann erhalten, wenn das Abschlussprotokoll scheitert.
Aufbewahrung, Begrenzung und Auswertung sind vor Produktion noch festzulegen.

## Nachweise

Aufruf unverändert:

```bash
python3 -W error tests/storage_http_test.py \
  --php /opt/homebrew/opt/php@8.4/bin/php \
  --layerling ../layerling
```

Ergebnis am 03.11.2026: **35 HTTP-Testgruppen bestanden**, lokal unter PHP 8.4.19.
Die ursprünglichen 16 persönlichen Speicherprüfungen bleiben enthalten. Zusätzliche Gruppen:
Betreuung für zwei Schüler, Löschsperren, Nichtschüler/unklare Rollen, Admin-Dateirechte,
exakte Gruppenkennungen und Überlappung, Fälschungen, Register-/Rollenentzug, Nachweisfristen,
private Einstellungen, Bildkontext, Suche/Dateioperationen, rekursive Admin-Löschung,
fehlerhafte Konfiguration, Audit, wartende Schreibanfrage bei Gruppenentzug, CSRF/Logout,
Abmeldung gesperrter Konten sowie Exportzugriffe und Pfad-/Symlinkschutz.

Testidentitäten, Register und Testserver liegen ausschließlich temporär außerhalb des Repos
und werden nach dem Lauf entfernt. Keine öffentlichen Test-Login-Routen und keine neuen Pakete.

## Noch nicht nachgewiesen

- Die echten Gruppen-IDs und die tatsächliche Students-Zuordnung beim IServ-Client.
- Eine externe Quelle für die regelmäßige Aktualisierung der Rollen anderer Eigentümer.
  UserInfo des Betreuers beweist nicht die Schülerrolle eines anderen Kontos.
- Rechtzeitiger externer Rechteentzug: lokal ist die Registerwirkung geprüft, nicht ein IServ-Push
  oder regelmäßiger Abruf. 300 Sekunden sind keine produktiv zugesicherte Aktualität.
- Dauerhafte OIDC-Identitätszuordnung und echte Anmeldung.
- Browser-/Editorintegration: Eigentümer muss Teil der Projektbindung und jeder Speicheradresse
  werden; gleiche Dateinamen verschiedener Eigentümer dürfen keine Arbeitskopien vermischen.
- Eigentümerauswahl/Sammelansicht, Online-Worker, PHP-FPM und Veröffentlichung auf dem Hoster.

Diese Grenzen bleiben vor produktiver Nutzung zu schließen. Kein Commit, Push oder Deployment
ist Bestandteil dieses Arbeitsschritts.
