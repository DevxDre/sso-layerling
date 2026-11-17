# Browsernutzung und erster Prototyp

Stand: 03.11.2026. Nutzungsentscheidungen und Quelltextprüfung.
Der abgegrenzte lokale Speicherprototyp ist inzwischen implementiert und getestet:
[Speicherprototyp](speicherprototyp.md). Browserintegration und SSO stehen noch aus.

## 1. Festgelegter Nutzungsrahmen

Entscheidungen des Nutzers im Chat am 03.11.2026:

- Verschiedene Benutzer verwenden zuverlässig getrennte Browserprofile.
- Die erste Version setzt eine Internetverbindung voraus; Offline-Nutzung wird zunächst nicht unterstützt.

Damit muss Version 1 keine mehreren Identitäten im selben Browserprofil unterstützen.
Getrennte Betriebssystem-Anmeldungen sind geeignet, sofern sie tatsächlich getrennte
Browserdaten ergeben. Verschiedene Tabs, verschiedene Fenster oder bloßes Abmelden von
IServ ergeben keine Profiltrennung. Diese Betriebsbedingung ist vor dem Einsatz an den
Schulgeräten zu überprüfen und gehört in die spätere Nutzungsanleitung.

## 2. Ergebnis der Quelltextprüfung

Untersuchter lokaler Layerling-Commit: `4b61a20b49c6fce9910a7903f53989d40396dfa4`.
Keine Pakete installiert und keine Layerling-Dateien geändert. Kein Browser-Laufzeittest.

| Stelle | Beobachtung | Bedeutung |
|---|---|---|
| `apps/web/src/app/page.tsx`, `DashboardProject` | Serverbindung enthält Dateiname, Revision und Pfad, keine Benutzerkennung | Die lokale Arbeitskopie gehört technisch zum Browserprofil |
| `page.tsx`, `openLylProjectFromFile` | Auch ein Serverprojekt wird durch `saveProjectShapes` lokal gespeichert | Serverbetrieb verhindert keine lokalen Projektkopien |
| `page.tsx`, `saveProjectShapes` | Vollständiges Projektpaket mit Historie und Anhängen wird in IndexedDB geschrieben | Lokale Daten sind mehr als Vorschaubilder |
| `page.tsx`, Projektlisten-Effekt | Projektübersicht liegt unter `layerling.projects` in localStorage | Nach Abmeldung verbleibende Daten sind bei persönlichem Profil zu erwarten |
| `apps/web/src/lib/storageMigration.ts` | Übernahme alter sketchForge-Daten; Altdaten bleiben bestehen | Späteres pauschales Löschen nur neuer Schlüsselnamen wäre unvollständig |
| `apps/web/src/lib/designThumbnailStore.ts`, `sketchDraftStore.ts`, `myShapes.ts`, `customFontStore.ts` | Weitere IndexedDB-Datenbanken für Bilder, Entwürfe, Formen und Schriften | Ein späterer Mehrbenutzermodus hätte mehrere Ablagen einzubeziehen |
| `page.tsx`, `saveActiveProjectToShared` | Upload mit Revision/Dateiname, ohne Benutzer-/Sitzungskontext im Projekt | Benutzertrennung muss der PHP-Einstiegspunkt aus der geprüften Sitzung ableiten |
| `apps/web/src/components/LayerlingEditor.tsx` | Verzögertes Serverspeichern nach fünf Sekunden | Abmeldung, Ablauf und noch laufende Speicherungen sind im Prototyp zu testen |
| `apps/web/src/components/ServiceWorkerRegistration.tsx` | Registrierung von `/sw.js` mit Scope `/` | Statischer Export ist nicht automatisch auf Online-Nutzung beschränkt |
| `scripts/generate-service-worker.mjs` | Offline-Dateien werden vom Export erzeugt; PHP-Endpunkte sind vom Cache ausgenommen | Offline-Strategie ist ein ausdrücklicher Paketierungsschritt |
| `page.tsx`, Initialisierung der Servervorgaben | Im statischen Export kein Abruf von `fetchServerDefaults` | Node-Umgebungsvariablen wie erzwungenes Serverspeichern lassen sich nicht einfach per PHP setzen |

Die Prüfung belegt Datenflüsse im Quelltext, keine praktisch reproduzierte Fremdzugriffslücke.
Bei getrennten Profilen ist die lokale Arbeitskopie ein Bestandteil des persönlichen Arbeitsplatzes.

## 3. Konsequenz für Version 1

Die erste Integration konzentriert sich auf den PHP-Zugangsschutz. Ein eigener Ersatz
für Layerlings CAD-, Projekt- oder Browserspeicherlogik wird nicht geplant.
Es wird nicht zugesichert, dass Abmeldung bereits heruntergeladene Projekte oder den
Inhalt eines schon geöffneten Editors vom persönlichen Endgerät entfernt.

Verbindliche Grenzen:

- Jeder Serverzugriff benötigt die aktuelle, geprüfte Wrapper-Sitzung.
- Lokale Browserdaten ersetzen niemals die Prüfung der Serverberechtigung.
- Ohne gültige Sitzung sind auch verspätete Speicheranfragen gesperrt.
- Ein anderes IServ-Konto im selben Browserprofil ist kein unterstützter Ablauf.
  Ein solcher Wechsel darf nicht als sicherer persönlicher Speicherwechsel beworben werden.
- Keine automatische Übernahme vorhandener lokaler Projekte in ein neues Serverkonto.
- Im persönlichen Profil verbleibende lokale Kopien sind nicht automatisch ein Serverbackup.
- Version 1 erhält keinen Offline-Modus als unterstützte Funktion und keine PWA-Installationsaufforderung.
  Die Paketierung muss Service-Worker-Verhalten ausdrücklich festlegen. Falls bereits ein Worker
  vorhanden ist, reicht das Weglassen von `sw.js` für dessen Entfernung nicht aus.
- Das Verhalten bei kurzzeitigem Netzverlust bleibt zu testen: Speicherfehler sichtbar melden,
  keine Speicherung als erfolgreich ausgeben und keine ungespeicherte Arbeit stillschweigend verwerfen.

Eine mögliche Umsetzung für Online-Betrieb ist ein eigener, explizit paketierter
Service Worker ohne Offline-Cache, der alte Layerling-Caches kontrolliert entfernt.
Das ist vor Umsetzung gegen frische und zuvor verwendete Profile zu erproben.
Die Bedingung 'Online-Nutzung' ist keine Zusage, bereits geladene Daten aus dem Browser zu widerrufen.

## 4. Konkreter Umfang des ersten Prototyps

Nur lokal bzw. mit synthetischen Daten; kein produktives Deployment ohne eigene Freigabe.

1. Öffentlichen und privaten Paketbereich herstellen. Das unveränderte Layerling-`store.php`
   kommt privat zu liegen; nur der eigene Einstiegspunkt ist öffentlich ausführbar.
2. Wrapper-Sitzung mit festen Sicherheitsgrenzen und eigenem Cookie bereitstellen.
   Die Grundprüfung nutzt zunächst isolierte Testidentitäten; ein solcher Testzugang darf
   niemals Bestandteil eines veröffentlichbaren Pakets werden.
3. Originalspeicher ausführen, nachdem Sitzung, Berechtigung und Schreibschutz geprüft sind.
   Browserheader können die interne Identität nicht bestimmen; fehlende Identität führt zum Abbruch.
4. Mit zwei getrennten Browserprofilen und HTTP-Clients die vollständige Servertrennung testen.
5. Anschließend den echten OIDC-Ablauf mit eigenem IServ-Client ergänzen. Bibliotheksauswahl
   und Abhängigkeiten vorher konkret festlegen. Kirby-Quellcode und Tests als Referenz nutzen;
   keinen Kirby-Bootstrap und keine Kirby-Konten als Laufzeitabhängigkeit einführen.
6. Statischen Layerling-Export mit diesem Einstiegspunkt verbinden. Login-Einstieg und Verhalten
   bei 401/403 zunächst prüfen; nur bei belegtem Bedarf kleine explizite Schnittstellen ergänzen.

IServ-spezifische Empfehlung für die dauerhafte Zuordnung: `(iss, iserv:uuid)` wie bei
Kirby 6, intern auf eine opake Ordner-ID abbilden. `sub` bleibt für die OIDC-Bindungsprüfungen
verpflichtend. Dies ist eine Architektur-Empfehlung, noch keine gesonderte Nutzerentscheidung.
Die für Kirby verwendete Rollenpolitik und Sitzungslaufzeit werden nicht automatisch übernommen.

## 5. Abnahmematrix für den Prototyp

| Fall | Erwartung |
|---|---|
| Keine Sitzung | Kein Listen, Download, Upload oder sonstiger Speicherzugriff |
| Fehlende interne Identität trotz Sitzung | Abbruch; kein gemeinsamer Fallback |
| Gefälschte Identitätsheader | Keine Änderung der zugeordneten Identität |
| A und B in getrennten Profilen, gleiche Projektnamen | Jeder sieht und verändert ausschließlich eigene Projekte |
| Direkte private Pfade / Original-PHP | Nicht über HTTP erreichbar |
| Schreibanfrage von fremder Website | Abgelehnt |
| Lokale Abmeldung von A | A kann keine neue Speicheroperation mehr beginnen |
| Abgelaufene Sitzung, verzögerter Autosave | Abgelehnt, im Editor erkennbarer Speicherfehler |
| Bereits laufender Upload bei Logout | Festgelegte Reihenfolge; keine nachträgliche Nutzung einer widerrufenen Sitzung; bereits autorisierte Vorgänge gesondert behandeln |
| Öffentliche Projekt- oder Bildadresse ohne Sitzung | Kein Projekt-/Vorschaubildzugriff |
| Netzunterbrechung während Arbeit | Kein unbemerkter Verlust und kein falscher Erfolgsstatus |
| Statischer Build mit/ohne vorherigen Worker | Definierter Online-Betrieb; keine gecachten Login-/API-Antworten |
| Wiederanmeldung derselben Identität | Persönlicher Serverspeicher bleibt zugeordnet |
| Wechsel des Kontos innerhalb eines Profils | Nicht als unterstützter Ablauf freigegeben; kein automatischer Projekttransfer |

## 6. Noch benötigte Festlegungen

Vor echtem SSO-Prototyp: zulässige IServ-Rollen/Benutzerkreis und konkreter Client mit
Callback-Adresse. Vor Produktion zusätzlich: endgültiger privater Pfad, sämtliche relevanten
Domainzuordnungen, Quoten, Backup/Restore, Sitzungsfristen und Veröffentlichungsverfahren.

Der lokale PHP-Speichereinstieg ist mit zwei synthetischen Identitäten über echte HTTP-Anfragen
geprüft. Details und Grenzen: [Speicherprototyp](speicherprototyp.md). Nächster Schritt ist die
Festlegung des echten SSO-Ablaufs und der Frontend-Anbindung; noch kein Live-Login.
