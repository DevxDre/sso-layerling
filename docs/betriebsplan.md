# Betriebs- und Entwicklungsplan

Stand: 03.11.2026. Arbeitsentwurf, keine Produktionsfreigabe.
Aktuelle Datenquelle: ausschließlich SSO, derzeit kein IDM-/LDAP-Abgleich.
Bei fehlenden Rollen können konfigurierte Schülergruppen einspringen; die letzte
Schülerzuordnung gilt bis zum nächsten Eigentümer-Login. Details und notwendige Anpassung
des Prototyps: [SSO-Berechtigungsmodell](sso-berechtigungsmodell.md).

## 1. Ziel und Grenzen

Bestätigte Ziele aus der Planung:

- IServ-SSO und persönliche Projektordner auf einem normalen Webhosting ermöglichen.
- Betreuungs- und Adminzugriff nach bestätigten IServ-Gruppen: `makerspace-betreuung`
  liest/bearbeitet Schülerdateien; `Admins` liest/bearbeitet/löscht alle Nutzerdateien.
  Verbindliche Matrix und offene technische Zuordnung: [Berechtigungen](berechtigungen.md).
- Layerling möglichst unverändert lassen; eigene Ergänzungen separat verwalten.
- Die laufende Entwicklung schrittweise übernehmen und bei jedem Update relevante Änderungen prüfen.
- Beobachtung, Prüfung und produktive Veröffentlichung voneinander trennen.

Vorgeschlagene Architektur: statischer Layerling-Export mit einer eigenen PHP-Zugangsschicht.
Die grundlegenden PHP-Hostingbedingungen sind inzwischen über Website-PHP erfolgreich geprüft:
[Hostingprüfung](hosting-pruefung.md). Die vollständige Integration und Browserisolation
sind weiterhin nachzuweisen.
Kein eigener CAD-Editor, keine neue gemeinsame Bearbeitung und zunächst keine KI-/MCP-Anbindung.

## 2. Lokal geprüfter Ausgangsstand

Repository: https://github.com/DevxDre/layerling

- Lokaler Commit: `4b61a20b49c6fce9910a7903f53989d40396dfa4`.
- Paketversion: `1.136.0`; im Paket angegebenes Node-Minimum: `22.18`.
- Statischer Build: `npm run export`; Ziel laut Buildskript: `apps/web/.next-export/`.
- `apps/web/src/lib/sharedProjectsEndpoint.ts`: statischer Export verwendet `store.php`.
- `apps/web/public/store.php`: `LAYERLING_USER_HEADER` aktiviert die Zuordnung zu `.users/<kennung>/`.
- Ohne verwertbare Kennung fällt das Skript auf den gemeinsamen Basisordner zurück.
- Die Kennung wird normalisiert; beliebige OIDC-Subjects dürfen deshalb nicht ungeprüft
  als Ordnerkennung durchgereicht werden. Unterschiedliche Subjects könnten gleich normalisiert werden.
- `apps/web/src/lib/designListStorage.ts`: Projektübersicht nutzt localStorage;
  Vorschaubilder und Projektinhalte werden auch in IndexedDB gehalten.

Dies ist eine gezielte Quelltextsichtung. Kein Build, keine Laufzeitprüfung, kein vollständiges
Sicherheitsaudit und kein Live-Abgleich mit dem Originalrepository. Der Commit ist ein
Untersuchungsstand, noch kein geprüfter Update- oder Produktionskandidat.

## 3. Repository- und Build-Grenze

`layerling/` bleibt möglichst unverändert. `sso-layerling/` enthält später die
SSO-Schicht, Paketierung, Konfiguration ohne Geheimnisse und eigene Integrationsprüfungen.

Ein Build soll einen exakten Layerling-Commit mit dessen Lockdatei in ein ignoriertes,
wegwerfbares Arbeitsverzeichnis laden. Ein vorhandener Entwicklercheckout ist keine Buildquelle.
Zunächst kein Submodul und keine dauerhaft gepflegte Produktkopie im Wrapper-Repository.

Pro veröffentlichtem Paket erfassen:

- Upstream- und Fork-Quelle sowie vollständige Commit-ID.
- Commit-ID dieser Erweiterung und Hashes verwendeter Lockdateien.
- Tatsächliche Node-/npm- und PHP-Version sowie relevante Erweiterungen/Konfiguration.
- Buildbefehle, Buildkennung, Paketprüfsumme und Testbericht.
- Erwartetes Projekt-/Speicherformat und Wiederherstellungsvoraussetzungen.

Das macht den Quellstand nachvollziehbar; ein byte-identischer Build ist damit noch nicht
bewiesen. Das aktuelle Exportskript verwendet beispielsweise eine zeitbasierte Buildkennung.

## 4. PHP- und SSO-Grenze

Vorgeschlagenes Installationslayout, noch kein fertiger Deploymentplan:

```text
private/
├── releases/<kennung>/layerling/store.php  # Original, nicht öffentlich erreichbar
├── auth/                                 # eigene Anmeldeschicht
├── identities/                           # persistente Identitätszuordnung
└── projects/                             # persistente persönliche Projekte
public/                                   # DocumentRoot der eigenen Subdomain
├── index.html, _next/, ...                # geprüfter statischer Export
├── store.php                             # eigener geschützter Einstiegspunkt
└── auth/...                              # Login, Callback, Logout
```

Die Ordneranordnung hängt von den Möglichkeiten des Hosters ab. Wesentlich sind die
Trennung öffentlicher Dateien von privaten Daten und die Versionszuordnung des Originals
zum restlichen Build. Sitzungen, Identitätszuordnung und Projekte überleben Code-Updates.

Im implementierten lokalen Speicherprototyp ([Bericht](speicherprototyp.md)) wird die
persönliche Ordnerzuordnung durch den Wrapper gesetzt und die Headerzuordnung im Original
deaktiviert. Die `.users`-Anordnung des Originals ist daher keine Vorgabe für unseren Datenspeicher.

Der eigene Einstiegspunkt prüft die Anmeldung bei jeder Operation und führt erst danach
das zur Veröffentlichung gehörende Originalskript aus. Keine Kopie des ungeschützten
Originals darf im öffentlichen Export verbleiben, auch nicht unter alternativen Dateinamen.
Auch künftige neue PHP-Dateien/Endpunkte müssen vor einer Veröffentlichung inventarisiert werden.
Unbekannte ausführbare Dateien blockieren die Paketfreigabe bis zur Bewertung.

Sicherheitsanforderungen:

- OIDC Authorization Code mit State, Nonce und PKCE S256; gepflegte Bibliothek verwenden.
  Bibliotheksauswahl und neue Abhängigkeiten vor Umsetzung abstimmen.
- Signatur, erlaubter Algorithmus, Issuer, Audience, Zeitangaben und weitere erforderliche
  Tokenbindungen prüfen; bei UserInfo muss dessen Subject zum ID-Token passen.
- Identitäten dauerhaft über `(iss, sub)` zuordnen. Eine zufällige interne ID aus einem
  beschränkten Alphabet wird kollisionsfrei zugeordnet und als Ordnerkennung verwendet.
  Keine Namens-/E-Mail-Zuordnung und kein Lowercasing des eigentlichen OIDC-Subjects.
- Nur ausdrücklich zugelassene IServ-Nutzer erhalten Zugriff. Für fremde Nutzerdateien
  gilt die bestätigte [Gruppenpolitik](berechtigungen.md). Persönlicher Speicher ist der
  Standard; Fremdzugriffe werden einzeln anhand Akteur, Eigentümer und Operation geprüft.
  Technische Gruppen-IDs, Studentenrolle und Aktualitäts-/Entzugsverfahren sind noch festzulegen.
- Fehlende, abgelaufene oder fehlerhafte Anmeldung immer ablehnen. Niemals gemeinsamer Fallback.
- Alle vom Client gelieferten Identitätsvarianten verwerfen; nur die serverseitig geprüfte
  Kennung so setzen, dass die tatsächliche PHP-Lesereihenfolge keinen Fremdheader bevorzugt.
- Schreibzugriffe gegen CSRF absichern; SameSite-Cookie allein ist kein vollständiges Konzept.
  API-Antworten auf Sitzungsablauf liefern einen Fehler statt HTML einer Loginweiterleitung.
- Sitzungs-ID nach Login erneuern; sichere Cookies, begrenzte Laufzeit und explizite Abmeldung.
- Geheimnisse ausschließlich serverseitig außerhalb Webroot/Git. Keine Tokens, Sitzungskennungen
  oder Projektdaten in Diagnoseprotokollen.
- Sitzungsspeicher, Identitätszuordnung und Backups ebenso schützen wie Projektdateien.

Die SSO-Bibliothek und deren Sicherheitsupdates bilden einen eigenen Wartungsbereich,
auch wenn Layerling unverändert bleibt.

## 5. Browserisolation als Freigabevoraussetzung

Persönliche Serverordner isolieren keine lokalen Browserdaten.
**Entschieden durch den Nutzer am 03.11.2026:** zuverlässig getrennte Browserprofile;
Version 1 zunächst nur online. Die Geräteorganisation muss diese Trennung tatsächlich durchsetzen.
Die Quelltextauswertung, Konsequenzen und der erste Prototyp sind in
[Browsernutzung und erster Prototyp](browser-und-prototyp.md) beschrieben.

Die folgenden Anforderungen gelten für einen späteren Ausbau mit geteilten Profilen.
Sie gehören nicht zur Freigabe von Version 1, solange die festgelegte Profiltrennung besteht:

- B sieht nach Abmeldung von A keine Projekte, Vorschaubilder oder wiederherstellbaren
  personenbezogenen Reste von A im unterstützten Nutzungsablauf.
- Ein alter Editor von A kann nach Anmeldung von B weder dessen Speicher lesen noch dorthin schreiben.
  Eine Sitzungscookie-Prüfung allein verhindert diesen Fall nicht.
- Benutzerwechsel, mehrere Tabs, Zurück-Navigation, Sitzungsablauf und laufende Uploads sind abgedeckt.
- Offline-Modus, Service Worker, Cache Storage, localStorage und IndexedDB verletzen die
  festgelegten Anmelde- und Abmeldegrenzen nicht. Login-/API-Antworten werden nicht offline gecacht.
- Datenverlust durch pauschales Löschen lokaler Projekte wird vermieden; das Verfahren für
  ungespeicherte Arbeit und noch offene Tabs ist ausdrücklich definiert.

Eine reine PHP-Schicht kann bereits geladene Editorzustände und lokale Ablagen nicht vollständig
kontrollieren. Falls erforderlich: kleine, dokumentierte Browserintegration mit begrenzter
Schnittstelle; allgemeine Verbesserungen möglichst upstream anbieten. Keine versteckten
Textersetzungen in generierten JavaScript-Bundles als Dauerlösung.

## 6. Upstream-Beobachtung und Updateprüfung

Vorschlag: tägliche automatische Beobachtung, gebündelte Kandidaten nach Bedarf und
vorgezogene Prüfung von Sicherheitskorrekturen. Noch keine Automation eingerichtet.

1. Original `henmedia/layerling`, Fork und zuletzt geprüften Stand getrennt erfassen.
   Ein veralteter Fork darf nicht als aktueller Originalstand gemeldet werden.
2. Alle Commits seit dem letzten erfolgreich geprüften Stand inventarisieren, auch wenn
   mehrere Beobachtungen zusammengefasst werden. Kandidaten auf feste Commit-IDs beziehen.
3. Änderung nach Auswirkungen bewerten: Authentifizierung/Speicher, Browserdaten/Offline,
   Projektformat, Endpunkte/externe Verbindungen, Build/Abhängigkeiten und Bedienung/CAD.
4. Nicht nur Dateinamen und Changelog prüfen: indirekte Abhängigkeiten und Verhalten einbeziehen.
   Automatische oder KI-gestützte Einordnung unterstützt die Prüfung, ersetzt sie nicht.
5. Bericht mit Commitbereich, relevanten Änderungen, Risiken, Tests, offenen Fragen und
   Entscheidung ablegen. Nicht ausgeführte Tests ausdrücklich kennzeichnen.
6. Keine automatische Veröffentlichung. Ungeklärte Sicherheits- oder Datenänderungen blockieren sie.

Künftige CI führt fremde Buildskripte/Abhängigkeiten nur ohne Produktionsgeheimnisse und
Deploymentrechte aus. Beobachten und Testen erhalten minimale Rechte. Bestehende Upstream-
Workflows für Releases/Container werden nicht ungeprüft als eigene Veröffentlichung aktiviert.

## 7. Prüfungen je Kandidat

Neben den geeigneten Upstream-Prüfungen (`typecheck`, Unit-/E2E-Tests, statischer Export)
werden eigene Tests gegen die tatsächlich gepackte PHP-Installation benötigt:

- Ohne Sitzung, mit abgelaufener Sitzung und mit gefälschten Identitätsheadern kein Zugriff.
- A/B-Trennung für normale Nutzer bei Listen, Suche, Download, Vorschaubildern, Upload,
  Umbenennen, Kopieren, Verschieben, Löschen, Ordnern, Einstellungen und eigenen Formen.
  Privilegierte Gegenproben und Operationsgrenzen nach [Berechtigungsmatrix](berechtigungen.md).
- Keine direkte Erreichbarkeit von Originalskript, Projekten, Sitzungen oder Sicherungen.
- Pfadmanipulationen und CSRF-Versuche scheitern.
- Version 1: zwei getrennte Profile, Abmeldung, Ablauf und verzögerte Speicherungen bestehen
  die Abnahmematrix in [Browsernutzung und erster Prototyp](browser-und-prototyp.md).
  Der Mehrbenutzerbetrieb innerhalb desselben Profils ist nicht freigegeben.
- Beispieldateien aus dem produktiven Stand lassen sich öffnen, ändern, speichern und exportieren.
- Beschädigte Dateien, Uploadgrenzen, Speichermangel, Konflikte und Verbindungsabbrüche
  führen zu verständlichen Fehlern ohne fremden Zugriff oder unbemerkten Datenverlust.
- Browser lädt passende JavaScript-/WASM-Dateien; alte Tabs während eines Updates berücksichtigen.

Die vorhandenen Tests in `tests/unit/sharedProjectsAuthIsolation.test.ts` betreffen die
Node-Route. Sie belegen nicht die Sicherheit unseres PHP-Einstiegspunkts.
Eigene Sicherheitstests bleiben bei Updates unverändert streng; Fehler nicht durch
abgeschwächte Erwartungen beseitigen. Das Kirby-Testskript gehört nicht zu diesem Projekt.

## 8. Testinstanz, Veröffentlichung und Rückkehr

Separate Test-Subdomain, Testdaten, IServ-Testzugänge und eigene Callback-Konfiguration.
Keine Kopie echter Schülerprojekte als Standard-Testbestand.

Vor Veröffentlichung: Prüfbericht, bekannte Einschränkungen, Datensicherung und
konkreter Rückweg. Codepaket vollständig bereitstellen und möglichst atomar umschalten.
Ob Symlinks/DocumentRoot-Wechsel erlaubt sind, muss der Hoster klären; sonst definierter
Wartungsablauf. Keine Mischung verschiedener Builds und keine Löschsynchronisation über Datenordner.

Ältere offene Tabs und gecachte Assets können einen Codewechsel überleben. Die Strategie
für alte Assets, Speicherschnittstellen und Wartungsfenster gehört zum Freigabetest.
Produktiv keine automatischen Git-Pulls oder Container-Updates auf einen beweglichen Stand.

Rollback unterscheidet Code, Konfiguration und Daten. Neue Projektformate können alte
Versionen inkompatibel machen. Restore mit synthetischen Daten erproben; bei Rücksicherung
auch zwischenzeitlich erstellte Projekte und Identitätszuordnungen berücksichtigen.
Aufbewahrungsdauer, maximaler Datenverlust und Wiederherstellungszeit vor Betrieb festlegen.
Lizenzhinweise und erforderliche Quellcodebereitstellung bei Paketierung berücksichtigen.

## 9. Etappen mit überprüfbarem Ergebnis

1. **Hosting und Nutzung klären:** PHP-Version/Erweiterungen, HTTPS-Subdomain, private Pfade,
   Schreibrechte, Upload-/Speichergrenzen, SSH/Deploymentmöglichkeiten, Sitzungen und Backup;
   außerdem Benutzerkreis, geteilte Geräte und Offline-Anforderung. Ergebnis: bestätigte Grenzen.
2. **SSO-/Speicher-Prototyp:** Anmeldung, stabile Zuordnung, geschützter PHP-Einstiegspunkt,
   zwei Testnutzer in getrennten Profilen, Abmeldung und Sitzungsablauf. Der lokale Speichereinstieg
   ist mit synthetischen Identitäten geprüft ([Bericht](speicherprototyp.md)); echter SSO-Login,
   dauerhafte Zuordnung und Frontend-Anbindung stehen aus. Die zusätzliche Gruppenpolitik
   ist lokal mit privatem Register implementiert und mit 35 HTTP-Testgruppen geprüft
   ([Gruppenprototyp](gruppenprototyp.md)); die produktive Claim-Aktualisierung fehlt noch.
3. **Paketierung und Sicherheitsprüfungen:** feste Commit-ID, getrennte Daten,
   Manifest und automatisierte HTTP-/Browsertests. Ergebnis: lokal reproduzierbarer Ablauf.
4. **Updateverfahren:** Original/Fork vergleichen, Bericht erstellen, Kandidaten auf Testinstanz
   prüfen. Ergebnis: ein vollständiger Probelauf mit einer echten Upstream-Änderung.
5. **Betriebsprobe:** Veröffentlichung und Wiederherstellung testen, Einschränkungen dokumentieren.
   Erst danach gesonderte Produktionsfreigabe.

Etappe 1 ist teilweise abgeschlossen: HTTPS, Website-PHP, private Dateioperationen,
Dateisitzungen und öffentliche IServ-Abrufe sind erfolgreich geprüft. Offen sind insbesondere
Benutzerkreis, endgültiger privater Pfad, Quoten und Backup/Restore
(siehe [Hostingprüfung](hosting-pruefung.md)). Noch keine Bibliotheken installieren, Secrets
anlegen, GitHub-Workflows aktivieren oder produktive Endpunkte bereitstellen.
Der ausdrücklich autorisierte lokale Speicherprototyp ist umgesetzt; die Testidentitäten
werden ausschließlich durch das lokale Testprogramm erzeugt.

## 10. Referenz aus Kirby 6 und offene Identitätsentscheidung

Das vorhandene Plugin `devxdre-iserv-auth` unter `rkm-kirby-k6/site/plugins/` und
`scripts/login-test.php` dienen als lokale Referenz für OIDC-Validierung und Angriffstests.
Die Sichtung erfolgte ohne Lesen lokaler Konfiguration mit Zugangsdaten und ohne Testausführung.
Kirby-Adapter, Kontoabgleich und LMS-Rechte sind keine unmittelbar übernehmbaren Wrapper-Bausteine.

Wichtige Abweichung vom bisherigen Vorschlag in Abschnitt 4: Die aktuelle Kirby-Anbindung
bindet dauerhaft über `(iss, iserv:uuid)`, weil IServ pairwise Subjects je Client vergibt.
`sub` wird trotzdem bei ID-Token/UserInfo geprüft. Für Layerling ist ausdrücklich zu entscheiden,
ob dieses IServ-spezifische Modell übernommen wird; insbesondere Auswirkungen eines Clientwechsels,
UUID-Vertrag und Namensraum der Zuordnung berücksichtigen. Abschnitt 4 ist bis dahin ein Vorschlag,
keine bereits bestätigte Identitätsentscheidung für Layerling.

Layerling erhält einen eigenen IServ-Client und eigene Sitzungen. Bestehende Kirby-Zugangsdaten,
Sitzungs-Cookies oder Kontoordner werden nicht wiederverwendet. Sitzungslaufzeiten und Logout-Verhalten
von Kirby sind ebenfalls keine automatisch übernommenen Anforderungen.
