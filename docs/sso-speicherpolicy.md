# Lokale Speicherprüfung mit letzter SSO-Einstufung

Technische Beschreibung der lokalen Policy. Konkrete Login- und Betriebsnachweise
werden privat dokumentiert. Aktueller Stand: [Weiterarbeit](weiterarbeit.md).

## Zwei explizite Modelle

- `prototype-fresh-evidence`: bisherige `Policy` mit 300-Sekunden-Nachweisen. Bleibt
  ausschließlich als historischer lokaler Prototyp mit seinen Sicherheitsregressionen erhalten.
- `sso-last-login`: neue `SsoPolicy` mit bestätigter letzter Login-Einstufung. Der lokale
  Gateway wählt sie nur über den expliziten privaten Konfigurationswert `authorizationModel`.
  Fehlende/unbekannte Modelle werden abgelehnt. Die Paketierung des alten Prototyps
  bezeichnet dessen Modell ausdrücklich; kein stiller Wechsel bestehender Instanzen.

Die neue Policy liest das Register bei jedem Zugriff unter derselben gemeinsamen
`authorization.lock` wie der PrincipalWriter. Der Lock bleibt während der Dateioperation
bestehen. Die Registerform und jeder verwendete Datensatz werden strikt geprüft:
interner Identitäts-Hash, positive Login-Reihenfolge, gültiger Nachweiszeitpunkt,
normalisierte Gruppen/Rollen, Aktivstatus und boolesche Schülerklassifikation.
Fehlerhafte/widersprüchliche Datensätze, unbekannte Eigentümer und Zukunftszeiten
führen zu keiner Dateifreigabe. Das Register muss ein JSON-Objekt sein.

## Zeit und Rollen

Die Schülerklassifikation eines Eigentümers verfällt nicht nach fünf Minuten. Der
PrincipalWriter ersetzt sie beim nächsten erfolgreichen eigenen SSO-Login; ein neuer
Login der Betreuung aktualisiert keinen fremden Eigentümer. Die Rechte des Akteurs
sind weiter durch dessen gültige Sitzung begrenzt, deren Ablauf/Logout der Gateway prüft.
Aktivität schreibt keinen neuen SSO-Zeitpunkt. Ein neuer bekannter Registerstand wirkt
auch auf bereits laufende Sitzungen; ältere Login-Ergebnisse überschreiben ihn nicht.

`ROLE_STUDENT` alleine bestätigt die Schülerrolle auch ohne Gruppen. Bei fehlenden oder
valide leeren Rollen können ausschließlich explizit konfigurierte Schülergruppen dienen.
Bekannte Lehrer-/Mehrfachrollen oder beschädigte Rollen liefern keinen Gruppenfallback.
Eine gespeicherte positive Klassifikation muss zu den normalisierten Nachweisen passen;
aus einer negativen Einstufung wird nicht durch eine Browserangabe eine positive.

Betreuung: Schülerdateien lesen/herunterladen/bearbeiten, keine Datei-/Ordnerlöschung.
Admins: Dateien aller gültig registrierten Eigentümer einschließlich deaktivierter
Eigentümer lesen/bearbeiten/löschen. Admin-Gruppe hat Vorrang vor Betreuung.
Fremde persönliche Einstellungen sind in beiden Fällen gesperrt. Rollenbezeichner
`ROLE_ADMIN` oder Header/Parameter ersetzen niemals eine Gruppenmitgliedschaft.

## Nachweise

```bash
python3 -W error tests/sso_storage_http_test.py \
  --php /opt/homebrew/opt/php@8.4/bin/php --layerling ../layerling
python3 -W error tests/storage_http_test.py \
  --php /opt/homebrew/opt/php@8.4/bin/php --layerling ../layerling
python3 -W error tests/install_sso_test.py \
  --php /opt/homebrew/opt/php@8.4/bin/php
```

Am 04.11.2026 bestanden: **40 neue SSO-Speichergruppen, 35 historische Speichergruppen
und 6 Installer-Gruppen** unter lokalem PHP 8.4.19. Keine neuen Konten oder echten Daten.
Temporäre CLI-Sitzungen, synthetische Identitäten und Loopback-Testserver werden entfernt.

Die neue Suite übernimmt die allgemeinen Datei-/Isolation-/Export-/CSRF-/Widerrufsprüfungen.
Nur die zwei modellspezifischen Frist-/Konfigurationsprüfungen werden in der neuen Klasse
nach dem neuen Vertrag überschrieben; die historischen Erwartungen laufen weiterhin
separat im alten Modell. Zusätzlich gehen synthetische normalisierte Claims über den
wirklichen PrincipalWriter und anschließend über echte HTTP-Dateioperationen:

- Rolle ohne Gruppen, fehlende/leere Rollen mit explizitem Schülergruppenfallback.
- Lehrer-/gemischte Rollen verhindern den Fallback.
- Jahresalter Eigentümernachweis bleibt gültig; native Sitzungen laufen weiterhin ab.
- Neuer Eigentümer-Login entzieht Schülerstatus und lässt Eigentümer-ID/Dateien unverändert.
- Neuer Akteur-Login ohne Gruppen entzieht bestehender Sitzung Fremdrechte; `ROLE_ADMIN`
  alleine hebt den Entzug nicht auf. Verspätete Writer werden weiter abgelehnt.
- Wartende Uploads beobachten Logout/Gruppenentzug; Admin-Vorrang und Betreuungs-Löschgrenzen.

Während dieser Läufe wurde eine bestehende zeitabhängige ZIP-Testfixture sichtbar:
Neu erzeugte Vergleichsarchive konnten wegen des eingebetteten aktuellen Zeitstempels
andere Bytes haben. Die Fixture verwendet jetzt einen festen ZIP-Zeitstempel. Keine
Sicherheitsassertion oder Erwartung wurde abgeschwächt; beide Suites bestehen damit stabil.

## Klare Laufzeitgrenze und nächster Schritt

**Noch keine SSO-Sitzungsanbindung an öffentliche Dateioperationen.** Der Gateway ist
weiter ausschließlich für Loopback/PHP-CLI-Server zugelassen. Das installierte SSO-Portal
bleibt auf Quellcommit `71f24256e8ca01e9bb4f5c86287f119530c2d089`; private Vorlage
und neue lokale Policy werden dort nicht geladen. Kein FPM-Schutz wurde aufgehoben,
keine privilegierte Gruppe auf dem Hoster aktiviert und keine `.env` gelesen/geändert.

Als Nächstes den SSO-Sitzungs-/Principal-Writer kontrolliert an den Speicherdienst anbinden:
eine gemeinsame authentifizierte Sitzung, feste private Benutzerverzeichnisse, explizit
validierte Gruppen-/Rollen-Konfiguration und Eigentümerauswahl. Die bisherige Portal-
Klassifikation wurde ohne aktive Schülerkonfiguration geschrieben; vor einem Dateitest
müssen Nutzer sich nach der Integration erneut anmelden. Danach getrennter Datei-Teststand
mit echten Browserprofilen/Negativprüfungen; erst anschließend CAD-Editor und vollständiger Build.
