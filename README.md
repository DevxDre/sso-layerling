# sso-layerling

**Layerling mit Single Sign-on und persönlichem Projektspeicher für den Schuleinsatz.**

sso-layerling ergänzt den browserbasierten CAD-Editor [Layerling](https://github.com/henmedia/layerling)
um eine PHP-Schicht für Anmeldung, Dateiverwaltung und schulische Zugriffsrechte.
Schülerinnen und Schüler arbeiten in ihrem eigenen Projektbereich. Berechtigte Lehrkräfte
können Schülerentwürfe öffnen und bearbeiten sowie Vorlagen und Arbeitsaufträge bereitstellen.

Der Editor wird aus einem festgelegten Layerling-Stand gebaut. Die Anpassungen für den
Schulbetrieb werden beim Paketbau angewendet; der Layerling-Quellcode im benachbarten
Checkout bleibt dabei unverändert.

## Funktionen

- **Single Sign-on:** Anmeldung über OpenID Connect mit Authorization Code und PKCE; mit konfigurierbarem Anbieterprofil und IServ-Voreinstellung.
- **Persönliche Projekte:** serverseitiger Speicher mit Dateiverwaltung und getrennten Benutzerbereichen.
- **Betreuung:** berechtigte Gruppen können Schülerdateien lesen, herunterladen und bearbeiten.
- **Rechteverwaltung:** eine in der privaten `.env` konfigurierte OIDC-Rolle kann Dateizugriff, Vorlagenverteilung und MCP-Freigaben für Gruppen und Rollen verwalten.
- **Vorlagen:** CAD-Projekte und Arbeitsaufträge für Lernende bereitstellen.
- **Kontrollierte Updates:** festgelegte Quellstände, geprüfte Adapter und Paketmanifeste mit Datei-Prüfsummen.

Gruppenrechte werden aus validierten SSO-Daten abgeleitet. Ein Gruppenname oder eine
allgemeine Administratorrolle allein erteilt keine zusätzlichen Dateirechte.
Die zuletzt gespeicherte Schülerzuordnung gilt bis zur nächsten Anmeldung des Eigentümers.
Details beschreibt das [Berechtigungsmodell](docs/sso-berechtigungsmodell.md).

## Einsatzrahmen

Der Anmeldeserver wird je Deployment konfiguriert. Das Profil bestimmt Anzeigename,
Endpunktpfade, Scopes und Claim-Zuordnung. Die Oberfläche verwendet den konfigurierten
Namen, etwa „Mit Schulportal anmelden“. IServ steht als kompatibles Standardprofil
zur Verfügung. Adressen und fachliche Bindungen gelangen beim Paketbau in die private
App. Einrichtung und unterstützte Claim-Formate stehen im
[OIDC-Profil](docs/oidc-profile.md).

Die Anwendung setzt eine Internetverbindung voraus. Auf gemeinsam genutzten Geräten
sind getrennte Browserprofile vorgesehen. MCP lässt sich je Installation für
freigegebene SSO-Konten aktivieren. Einrichtung und Client-Build stehen im
[MCP-Leitfaden](docs/mcp-test.md).

## Voraussetzungen

Für den Webbetrieb:

- PHP **8.4** mit `curl`, `fileinfo`, `json`, `mbstring`, `openssl`, `session` und `zip`.
- HTTPS und private Verzeichnisse außerhalb aller öffentlichen Webverzeichnisse.
- Ein registrierter OIDC-Client beim Anmeldeserver mit den zum Profil passenden Scopes und Claims.

Für Entwicklung und Paketbau werden zusätzlich Composer, Python 3 und Git benötigt.
Der CAD-Build benötigt Node.js, npm und ein benachbartes Layerling-Checkout mit dem in
`upstream.lock.json` referenzierten Commit. Node.js und npm werden zum Bauen des Editors
verwendet; der Webbetrieb erfolgt mit PHP und statischen Editor-Dateien.

## Einstieg für Entwicklung und Betrieb

1. Die [Hostingvoraussetzungen](docs/hosting-pruefung.md) prüfen und einen OIDC-Client
   registrieren. Die [Profilkonfiguration](docs/oidc-profile.md) beschreibt die gemeinsamen
   Einstellungen. Für IServ gilt die [IServ-Einrichtung](docs/iserv-client-einrichtung.md).
2. Die PHP-Abhängigkeiten anhand von `composer.lock` installieren:

   ```bash
   composer install --no-dev --prefer-dist --no-interaction
   ```

3. Die Variablen aus `.env.example` in einer privaten `.env` außerhalb aller öffentlichen
   Webverzeichnisse hinterlegen. Dateirechte auf `0600` setzen.
4. `config/oidc.example.json` als `config/deployment.local.json` kopieren und dort die
   eigene Client-ID, `issuer`, `origin`, `redirectUri` sowie geprüfte Gruppenkennungen eintragen. Diese Datei ist von Git
   ausgeschlossen und benötigt ebenfalls `0600`. Ihr Feld `clientSecret` bleibt leer;
   das Secret gehört ausschließlich in die private `.env`.
5. Die [lokalen Prüfungen und Paketierung](docs/sso-teststand.md) durchführen.
   Für den vollständigen Editor folgt die [CAD-Integration](docs/cad-integration.md).

Die öffentliche Konfigurationsvorlage enthält synthetische Gruppenkennungen.
Gehostete Pakete benötigen eine explizite private Konfiguration über
`--deployment-config`. Der Installer gleicht die paketierte Client-ID mit der privaten
Anmeldekonfiguration ab. Konfiguration und Paketierung sind getrennte Schritte;
das Kopieren einer Vorlage aktiviert noch keine Installation.

## Tests

Die Tests verwenden temporäre synthetische Konten und lokale HTTP-Server.
Beispiel für die integrierte Anmeldung und Dateiverwaltung:

```bash
python3 -W error tests/integrated_storage_http_test.py \
  --php /pfad/zu/php8.4 \
  --layerling ../layerling
```

Den PHP-Pfad durch die eigene PHP-8.4-Installation ersetzen. Weitere Prüfungen decken
OIDC, Rechteentzug, Benutzertrennung, Paketintegrität, Installation, Rücksetzung und
CAD-Browserabläufe ab. Die Aufrufe stehen im [SSO-Leitfaden](docs/sso-teststand.md) und
in der [CAD-Dokumentation](docs/cad-integration.md).

Der historische Speicherprototyp ist ausschließlich für lokale Tests vorgesehen und
für PHP-FPM gesperrt. Für gehostete Installationen werden die ausdrücklich dafür
vorgesehenen Pakettypen verwendet.

## Dokumentation

| Thema | Leitfaden |
|---|---|
| Geplante Weiterentwicklung | [Roadmap](docs/roadmap.md) |
| Aktuelle OIDC-Anbindung und private Konfiguration | [OIDC-Profile](docs/oidc-profile.md), [Einrichtung für IServ](docs/iserv-client-einrichtung.md) |
| Dateirechte und Rollen | [Berechtigungsmodell](docs/sso-berechtigungsmodell.md) |
| Tests und Paketbau | [SSO-Teststand](docs/sso-teststand.md) |
| Statischer CAD-Editor | [CAD-Integration](docs/cad-integration.md) |
| Hosting | [Voraussetzungen](docs/hosting-pruefung.md) |
| Installation und bestehende Installationen | [Umstellung auf sso-layerling](docs/installation-und-migration.md) |
| SSO-gebundene Editorsteuerung | [MCP-Freigabe und Client](docs/mcp-test.md) |

## Mitwirken

Fehlerberichte, Dokumentationsverbesserungen und gezielte Codebeiträge sind willkommen.
Der [Mitwirkungsleitfaden](CONTRIBUTING.md) erklärt Einrichtung, Prüfungen und Pull Requests.
Für KI-Assistenten gelten zusätzlich die [Arbeitsregeln in AGENTS.md](AGENTS.md).
[Glossar](GLOSSARY.md), [Architekturentscheidungen](docs/adr/README.md) und
[Aufgabenleitfaden](docs/agents/aufgaben.md) halten Begriffe, Entscheidungen und Abnahmekriterien nachvollziehbar.
Sicherheitsprobleme bitte nach [SECURITY.md](SECURITY.md) vertraulich melden.
