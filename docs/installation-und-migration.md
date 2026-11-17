# Installation und Umstellung auf sso-layerling

Der Quellstand verwendet durchgehend den Projektnamen `sso-layerling`. Die Umbenennung
betrifft neben Dokumentation und Composer-Paket auch PHP-Namensraum, Pakettypen,
Installationsmarker, Cookies, CSRF-Header, Eigentümerparameter und Browser-Speichernamensräume.

## Neue Installation

- Private Konfiguration nach [OIDC-Einrichtung](oidc-profile.md) und
  [Paketierungsleitfaden](sso-teststand.md) vorbereiten.
- Die private `.env` verwendet `SSO_LAYERLING_OIDC_CLIENT_ID` und
  `SSO_LAYERLING_OIDC_CLIENT_SECRET`. Secrets nicht in öffentliche Dateien übernehmen.
- Der voreingestellte private Installationsbereich liegt unter `/home/repos/sso-layerling/`.
  Der öffentliche Standardpfad bleibt `/home/www/layerling`.
- Composer-Autoload aus dem aktuellen `composer.json`/`composer.lock` erzeugen. Alte
  generierte Autoload-Dateien oder gebaute Editorpakete nicht weiterverwenden.
- CAD-Quelle aus dem Pin in einem neutral benannten temporären Verzeichnis neu vorbereiten,
  bauen und paketieren. Alte Adaptermarker und exportierte Browserdateien gehören nicht zum
  neuen Paket. Das fertige Paket auch auf eingebettete persönliche Buildpfade prüfen.

Anbieter-, Anwendungs- und Callback-Adresse werden aus der privaten Deployment-Konfiguration
in das Paket übernommen. Die öffentliche Vorlage enthält ausschließlich Beispieladressen.
Das [Anbieterprofil](oidc-profile.md) legt Endpunktpfade, Claims und Anzeigename fest.

## Bestehende Installation

Die Umbenennung ist keine automatische Migration einer bestehenden Installation.
Der Installer erwartet die neuen Pakettypen und Marker. Ein vorhandenes Webroot nicht
allein durch Umbenennen seiner Marker als kompatibel erklären.

Vor einer gesondert geplanten Umstellung sind private Konfiguration, Principal-Register,
Eigentümerzuordnung, Projekte und Vorlagen zu sichern und konsistent zu übernehmen.
Eigentümer-IDs nicht neu erzeugen. Neue Cookie-Namen erfordern eine erneute Anmeldung;
Dateien und Identitätsregister dürfen dafür nicht zurückgesetzt werden.

Browserkopien liegen unter einem neuen Speichernamensraum. Noch nicht serverseitig gespeicherte
Arbeit vor der Umstellung mit der bisherigen Anwendung sichern oder exportieren. Die neue
Fassung übernimmt alte Browserkopien nicht automatisch.

Reale Pfade, Sicherungen und konkrete Migrationsschritte ausschließlich in der privaten
Betriebsdokumentation festhalten. Ein lokaler Test oder erfolgreicher Paketbau verändert
keine bestehende gehostete Installation.
