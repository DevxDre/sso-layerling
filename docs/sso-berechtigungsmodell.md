# Berechtigungsmodell ausschließlich aus SSO

Stand: 03.11.2026. Aktuelle Nutzerentscheidung, ersetzt den vorgeschlagenen IDM-Abgleich.
Dies ist das Zielmodell für die weitere Implementierung, noch kein neuer Laufzeitnachweis.

## Bestätigt

- Aktuell keine IDM-Verbindung, keine LDAP-Anbindung und kein periodischer Verzeichnisabgleich.
- Gruppen und gegebenenfalls Rollen stammen ausschließlich aus einem vollständig geprüften
  SSO-Login. Keine fremden Rollen über UserInfo der Betreuung ableiten.
- IServ-Gruppe `makerspace-betreuung`: Schülerdateien lesen, herunterladen, bearbeiten;
  keine expliziten Datei-/Ordnerlöschungen.
- IServ-Gruppe `Admins`: alle registrierten Nutzerdateien lesen, herunterladen, bearbeiten, löschen.
- Falls Rollen fehlen, können ausdrücklich zugeordnete Schülergruppen die Schülerzuordnung liefern.
- **Ausdrücklich bestätigt:** Die beim letzten erfolgreichen SSO-Login gespeicherte
  Schülerzuordnung eines Dateieigentümers gilt bis zu dessen nächster Anmeldung.

## Konkrete Zuordnung

Gruppen für Betreuung, Admins und Schüler werden nach einem geprüften Test-Login explizit
konfiguriert, vorzugsweise anhand stabiler Gruppenkennungen. Die Schülergruppen können
mehrere Einträge umfassen. Keine automatische Freigabe anhand vermuteter Namensmuster,
Teilstrings oder frei übergebener Gruppen-/Rollenfelder.

Für die Normalisierung ist vorgesehen:

1. Vorhandene valide Rollen auswerten. Bestätigte Schülerrolle ergibt Schülerstatus;
   eine vorhandene Nichtschülerrolle oder widersprüchliche Mehrfachrollen werden nicht
   durch Schülergruppen zu einer Schülerfreigabe umgedeutet.
2. Bei fehlendem Rollenclaim oder einer gültig leeren Rollenliste die explizit konfigurierten
   Schülergruppen prüfen. Dies ist die für die Umsetzung vorgesehene Auslegung von 'Rollen fehlen'.
3. Ein beschädigter/falsch typisierter Rollenclaim ist kein Anlass für großzügigen Fallback:
   keine neue Schülerfreigabe aus widersprüchlichen Daten.
4. Fehlen auch geeignete Gruppen, bleibt die Schülerzuordnung unbestätigt. Betreuung erhält
   dadurch keinen Fremdzugriff; die Admin-Freigabe richtet sich weiterhin nach der Admin-Gruppe.

Technische Rollen-/Gruppenkennungen und Mehrfachrollen werden am eigenen Client geprüft.
`ROLE_ADMIN` allein ersetzt keine Mitgliedschaft in der konfigurierten Admin-Gruppe.

## Speicherung und Aktualität

Der vertrauenswürdige Login-Writer aktualisiert die eigene Identität des Anmeldenden:
interne Eigentümer-ID, bestätigte Gruppen, Rollenstatus bzw. Schülerklassifikation,
Quelle der Klassifikation und Zeitpunkt des SSO-Nachweises. Fehlende Daten behalten
keine alten privilegierten Gruppen bei. Ein erfolgreicher neuer Login ersetzt den vorherigen Stand.

Bei jedem Dateizugriff entscheidet der Wrapper weiter serverseitig anhand des gespeicherten
Registers über Akteur, Eigentümer und Operation. Der Registereintrag eines anderen Eigentümers
wird dabei **als zuletzt beim SSO-Login bekannte Einstufung** verwendet; er wird nicht als
live mit IServ abgeglichen bezeichnet. Er verfällt für die Schülerzuordnung nicht nach fünf Minuten.

Die Gruppenrechte eines angemeldeten Akteurs sind durch dessen authentifizierte Sitzung
begrenzt. Sitzungslaufzeiten müssen vor Produktion festgelegt werden. Eine später lokal
bekannt gewordene neue Einstufung muss auch bei noch laufenden Sitzungen berücksichtigt werden.
Eine Änderung allein im IServ wird ohne erneuten Login nicht sofort bekannt. Bereits geladene
oder heruntergeladene Dateien können nach einem späteren Entzug nicht zurückgerufen werden.

Der Login der Betreuung aktualisiert nicht automatisch den Registereintrag eines Schülers.
Eigentümer und deren Dateien bleiben auch nach späteren Rollenänderungen dieselben;
allein die Zugriffsentscheidung ändert sich beim nächsten bekannten Stand.

## Auswirkungen auf den aktuellen Prototyp

Der bestehende Prototyp mit 35 bestandenen Testgruppen verwendet noch eine begrenzte
Nachweisfrist (`privilegeEvidenceSeconds = 300`) und verlangt `ROLE_STUDENT` ohne Gruppenfallback.
Diese bisherigen Tests sind kein Nachweis des neuen Zielmodells. Die Policy muss vor der
SSO-Freigabe gezielt angepasst und mit zusätzlichen Fällen geprüft werden:

- Schülergruppe bei fehlendem/leerem Rollenclaim gewährt die vorgesehene Schülerklassifikation.
- Lehrerrolle mit Schülergruppe, beschädigte Claims und unklare Mehrfachrollen gewähren sie nicht.
- Ein alter erfolgreicher Eigentümer-Login bleibt bis zur nächsten Anmeldung maßgeblich.
- Neue Anmeldung ohne Schülerzuordnung entzieht den Betreuungszugriff.
- Neue Anmeldung ohne privilegierte Gruppe entzieht entsprechende Fremdrechte.
- Sitzungslaufzeit, Logout, Lock-Reihenfolge und Schutz gegen verspätete Writer bleiben wirksam.

Die bisherige Fünf-Minuten-Nachweisfrist wird nicht pauschal abgeschaltet, bevor diese
Semantik umgesetzt und geprüft ist. Transaktionsfristen für State/Nonce und native
Sitzungslaufzeiten sind separate Sicherheitsgrenzen und werden dadurch nicht aufgehoben.

## Nächste Schritte

1. Eigenen Layerling-OIDC-Client vorbereiten: Callback, benötigte Scopes, zulässiger Benutzerkreis
   und private Konfiguration. Benötigt werden `openid`, `iserv:uuid`, `iserv:groups` sowie
   gegebenenfalls `iserv:roles`; zusätzliche Profilfelder nur bei tatsächlichem Bedarf.
2. Nach Abstimmung des Pakets den unabhängigen OIDC-Kern und einen begrenzten Claim-Bericht
   für den eigenen Test-Client umsetzen. Keine bestehenden Kirby-Secrets übernehmen.
3. Beim geprüften SSO-Test-Login nur die benötigten Gruppen-/Rollenmetadaten erfassen,
   die drei Gruppenzuordnungen bestätigen und die Policy auf das neue Modell anpassen.
4. Editor, Online-Betrieb und Updateverfahren anschließend wie geplant anbinden.

Der IDM-Metadatenprüfer und die vorangegangene Recherche gehören nicht mehr zum aktuellen
Arbeitsauftrag. Ihre Ausführung auf dem IServ ist nicht erforderlich.


## Rechte über die Oberfläche verwalten

Setze in der privaten `.env` beispielsweise `SSO_LAYERLING_ADMIN_ROLE=ROLE_ADMIN`.
Der Wert muss mit der Rollen-ID aus dem normalisierten OIDC-Rollenclaim
übereinstimmen. Mit leerem Wert ist der Zugriff auf die Rechteseite gesperrt.
Administratoren erreichen die Seite über das SSO-Menü, die Kontoseite oder
direkt unter `/rechte.php`.

- Wähle als Akteur einen Gruppenaccount (`groups:<Accountname>`) oder eine Rolle
  (`role:<ID>`). Die Vorschläge zeigen Gruppen mit einem eindeutigen Accountnamen.
  Andere Gruppen kannst du über ihre ID (`group:<ID>`) eintragen.
  Die Regeln bleiben an die Gruppen-ID gebunden.
  Wähle für fremde Dateizugriffe zusätzlich die Gruppe oder Rolle der Zielkonten.
  Auflisten und Lesen, Bearbeiten und Löschen lassen sich einzeln freigeben oder sperren.
- Bei mehreren passenden Regeln hat „Verbieten“ Vorrang. Ohne Treffer greift für
  die jeweilige Aktion die bisherige Konfiguration. Eigene Dateien und persönliche
  Einstellungen behalten ihre bisherige Behandlung.
- Die Rechte für Vorlagen und MCP können nach Gruppe oder Rolle gesetzt werden.
  MCP setzt weiterhin eine für die Installation aktivierte Brücke mit gültiger
  privater MCP-Konfiguration voraus. Wenn eine passende Regel vorhanden ist,
  entscheidet sie anstelle der bisherigen MCP-Freigabeliste.
- Gruppenmuster filtern die beim Verteilen auswählbaren eigenen Gruppen.
  `makerspace^` sucht nach Gruppenaccounts mit dem Präfix `makerspace`.
  Ohne abschließendes `^` gilt exakte Übereinstimmung. Liefert der Anmeldeserver
  keinen Gruppenaccount, wird die Gruppen-ID verwendet. Ohne Muster stehen alle
  eigenen Gruppen zur Auswahl. Gleiche Prüfung beim Speichern der Verteilung.
- Der Server prüft Regeln bei jeder geschützten Anfrage. Geänderte OIDC-Rollen
  und Gruppenmitgliedschaften werden bei der nächsten erfolgreichen Anmeldung
  des jeweiligen Kontos übernommen. Bei Bestandskonten stehen die Gruppenaccounts
  nach dem ersten Login mit dem aktualisierten Wrapper zur Verfügung.

Die Änderungen werden in `private/permissions.json` außerhalb des Webroots
gespeichert. Die Datei gehört zu den privaten Laufzeitdaten der Installation.
