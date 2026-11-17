# Berechtigungen für persönliche und betreute Projekte

Stand: 03.11.2026. Nutzeranforderung bestätigt und lokal mit synthetischen Gruppen/Rollen
implementiert: [Gruppenprototyp](gruppenprototyp.md). Noch keine echte IServ-Anbindung und
keine Produktionsfreigabe; die ausgelieferte Konfiguration aktiviert keine Gruppenkennungen.

## 1. Bestätigte Rechte

| Angemeldeter Nutzer | Eigene Dateien | Fremde Dateien von Students | Fremde Dateien anderer Nutzer |
|---|---|---|---|
| Ohne besondere Gruppe | bisheriger persönlicher Speicher | kein Zugriff | kein Zugriff |
| IServ-Gruppe `makerspace-betreuung` | bisheriger persönlicher Speicher | lesen, herunterladen, bearbeiten; nicht löschen | kein Zugriff |
| IServ-Gruppe `Admins` | bisheriger persönlicher Speicher | lesen, herunterladen, bearbeiten, löschen | lesen, herunterladen, bearbeiten, löschen |

Die zuerst genannten Gruppenrechte wurden im Chat durch den Nutzer bestätigt;
für `Admins` wurde das Löschrecht ausdrücklich ergänzt. Bei Mitgliedschaft in beiden Gruppen
umfasst die Admin-Freigabe die Betreuung. Normale Schüler, Lehrkräfte oder IServ-Verwalter
bekommen durch ihre Rolle allein keine zusätzlichen Fremdzugriffe.

Gemeint sind serverseitig gespeicherte Layerling-Nutzerdateien einschließlich Projekte,
zugehöriger Vorschaubilder, im Projekt enthaltener Anhänge und gespeicherter Exporte.
Ausschließlich lokal im persönlichen Browserprofil vorhandene Dateien sind für andere
Benutzer technisch nicht erreichbar. Sitzungen, Konfiguration, Anmeldedaten, Identitätsregister,
Logs und Backups gehören nicht zu den durch diese Gruppen freigegebenen Nutzerdateien.

Aktuelle Zusatzentscheidung: ausschließlich SSO, Gruppenfallback bei fehlenden Rollen
und gespeicherter Schülerstatus bis zur nächsten Anmeldung des Eigentümers.
Das [SSO-Berechtigungsmodell](sso-berechtigungsmodell.md) hat Vorrang vor der früheren
Recherche zu periodisch aktualisierten Verzeichnisdaten.

## 2. Herkunft der Berechtigungen

- Mitgliedschaft kommt ausschließlich aus dem geprüften IServ-SSO-Vorgang mit `iserv:groups`.
  Dieser Scope ist für die neue Gruppenpolitik erforderlich.
- Die Referenz in Kirby 6 beschreibt Gruppen als Objekte mit `id`, `act`, `name`.
  Die angegebenen Namen müssen vor Aktivierung mit den tatsächlichen Claims abgeglichen
  und vorzugsweise an die stabilen Gruppen-IDs gebunden werden. Noch liegen keine bestätigten
  IDs für `makerspace-betreuung` und `Admins` vor.
- Nicht auf vermutete Groß-/Kleinschreibung, Teilstrings oder ähnlich klingende Anzeigenamen ausweichen.
  Fehlende oder nicht eindeutig aufgelöste Gruppen gewähren keine Fremdrechte.
- Die IServ-Gruppe `Admins` ist eine eigene fachliche Freigabe. Sie ist weder mit einer
  Kirby-Adminrolle noch automatisch mit dem IServ-Rollenclaim `ROLE_ADMIN` gleichzusetzen.
  Kirbys Sonderregel gegen Admin-Anmeldung wird nicht in diese Anwendung übernommen.
- `Students` bezeichnet nach der vorhandenen IServ-Referenz voraussichtlich `ROLE_STUDENT`
  in `iserv:roles`. Die konkrete Zuordnung sowie Mehrfachrollen sind vor Aktivierung zu bestätigen.
  Ein unklarer oder widersprüchlicher Rollenstand gilt nicht als bestätigte Schülerrolle.
- Namen, Dateinamen, Verzeichnisnamen, Query-Parameter und Browserheader sind keine Belege
  für Mitgliedschaft oder die Rolle des Dateieigentümers.

## 3. Benötigte Ergänzung zur Architektur

Die Ordner bleiben nach Eigentümer getrennt. Es entsteht kein gemeinsamer physischer
Sammelordner für Betreuung oder Admins. Der eigene Einstiegspunkt erhält stattdessen eine
zentrale Entscheidung für Akteur, Eigentümer und Operation:

```text
geprüfte Sitzung + geprüfte Akteurgruppen
               + serverseitig bestätigter Eigentümer/Rollenstand
               + angeforderte Operation
                         ↓
             erlauben oder geschlossen ablehnen
                         ↓
        genau ein autorisierter persönlicher Speicherordner
```

Eine später vom Browser ausgewählte Eigentümer-ID ist nur ein angefragtes Ziel.
Der Server löst sie im privaten Register auf, prüft die Berechtigung bei jeder Operation
und setzt erst danach den konkreten Speicherpfad für das unveränderte Originalskript.
Auch Listen, Suche, Gesamtexport und Vorschaubilder müssen dieselbe Filterung beachten.
Es darf keinen ungeprüften alternativen Pfad zum Original geben.

Zusätzlich zur dauerhaften Identitätszuordnung wird ein privates Eigentümerregister mit
internen IDs, geprüftem Rollenstand, Zeit der Prüfung und Status/Sperrung benötigt.
Dateien behalten beim Bearbeiten durch Betreuung oder Admin ihren ursprünglichen Eigentümer.
Die Rolle des Bearbeiters darf keine Schülerdatei zur Lehrer-/Admindatei umklassifizieren.

Der ursprüngliche Prototyp prüfte nur 'authorized' und den eigenen Ordner. Inzwischen
entscheidet eine zentrale Policy zusätzlich anhand eines privaten Registers über Akteur,
Eigentümer und Operation. Der Besitzerparameter allein gewährt weiterhin keinen Zugriff.

## 4. Operationen und Änderungsgrenzen

Für fremde Dateien bedeutet 'bearbeiten' mindestens Öffnen und Zurückspeichern des
geänderten Inhalts beim bisherigen Eigentümer. Im lokalen Prototyp gehören Anlegen, Umbenennen, Kopieren und Verschieben innerhalb
desselben Eigentümers zum Bearbeiten. Persönliche Einstellungen bleiben ausgenommen;
unbekannte oder mehrdeutige Operationen werden nicht pauschal per POST freigegeben.

Explizite Datei- und rekursive Ordnerlöschungen benötigen Löschrechte. Eine Löschung darf
nicht durch alternative HTTP-Methoden oder Änderungsendpunkte ohne dieselbe Prüfung erreichbar sein.
Für Betreuung bleiben Löschoperationen gesperrt, auch wenn eine Datei zuvor geöffnet wurde.
Verschieben zwischen Eigentümern und Ändern der Eigentümerzuordnung sind nicht automatisch
Bestandteil der Gruppenfreigabe.

Konfliktprüfungen des Originals bleiben aktiv: Zwei Bearbeiter desselben Projekts dürfen
einander nicht unbemerkt überschreiben. Das ist keine gleichzeitige gemeinsame Bearbeitung.
Für fremde Änderungen ist ein datensparsames Audit mit Akteur-ID, Eigentümer-ID,
Operation, Zeitpunkt und Ergebnis vorgesehen; keine Projektinhalte oder Tokens protokollieren.

## 5. Aktualität und Entzug

Entschieden am 03.11.2026: Aktuell kein IDM-/LDAP-Abgleich. Gruppen und Rollen kommen aus
vollständig geprüften SSO-Anmeldungen. Die Schülerzuordnung des Dateieigentümers bleibt
bis zu dessen nächstem erfolgreichen Login bestehen, auch wenn dieser länger zurückliegt.
Bei fehlenden Rollen können explizit konfigurierte Schülergruppen einspringen.

Bei jeder Anfrage wird weiter der lokal gespeicherte Stand geprüft. Ein neuer erfolgreicher
Login ersetzt ihn und entfernt nicht mehr bestätigte Gruppenrechte. Die Anmeldung der
Betreuung aktualisiert nicht den Schülerdatensatz. Änderungen allein im IServ werden
zwischen den Anmeldungen nicht sofort bekannt; dies ist Teil des gewählten Modells.
Sitzungsfristen bleiben wirksam und sind vor Produktion gesondert festzulegen.

Die vorhandene kurze Nachweisfrist und reine Rollenprüfung des Prototyps müssen noch auf
[das neue SSO-Modell](sso-berechtigungsmodell.md) umgestellt und gezielt geprüft werden.

## 6. Erforderliche Prüfungen

Die bisherigen Tests gegen beliebigen Fremdzugriff bleiben als Gegenproben für normale
Nutzer bestehen. Hinzu kommen mindestens:

1. Betreuung liest und bearbeitet Dateien zweier unterschiedlicher bestätigter Schüler.
2. Betreuung kann dieselben Dateien weder direkt noch rekursiv löschen.
3. Betreuung erreicht keine Dateien von Lehrkräften, anderen Nichtschülern oder unklaren Rollen.
4. Admin-Gruppe liest, bearbeitet und löscht Schüler- und Nichtschülerdateien.
5. Bloße Lehrkraft-/IServ-Adminrolle ohne passende Gruppe gewährt keine Fremdrechte.
6. Überlappende Gruppen ergeben die Admin-Rechte; ähnlich benannte fremde Gruppen nicht.
7. Manipulierte Eigentümer-ID, Identitätsheader und Rollenangaben ändern keine Entscheidung.
8. Suche, Listen, Bilder, Downloads, Anhänge, gespeicherte Exporte und sämtliche Mutationswege
   bleiben im jeweils autorisierten Bereich.
9. Entzug der Gruppe, Rollenwechsel des Eigentümers und abgelaufene Nachweise sperren
   Fremdzugriffe nach dem definierten Aktualitätsvertrag, auch mit altem CSRF-Token.
10. Bearbeitung verändert keine Eigentümerzuordnung und umgeht keinen Revisionskonflikt.
11. Sitzungsablauf, Abmeldung, parallele Anfragen und CSRF-Schutz gelten auch für privilegierte Zugriffe.

Die lokalen Gegenproben sind inzwischen in 35 erfolgreichen HTTP-Testgruppen enthalten;
Details: [Gruppenprototyp](gruppenprototyp.md). Externe Aktualität der echten IServ-Daten,
produktive Fristen und Editor-/Browserverhalten sind weiterhin nicht nachgewiesen.
