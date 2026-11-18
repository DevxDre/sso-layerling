# MCP für SSO Layerling

SSO Layerling koppelt einen MCP-Client mit einem offenen Editor im eigenen
Projektbereich. Die Freigabe, Token-Ausgabe und Sitzungsprüfung liegen im
PHP-Wrapper. Den Editor und die CAD-Werkzeuge liefert der in
[`upstream.lock.json`](../upstream.lock.json) festgelegte Layerling-Stand.

## Gehostete Installation freigeben

Der CAD-Build enthält den Endpunkt `/mcp.php` für HTTPS und PHP-FPM. MCP ist
anfangs deaktiviert. Kopiere [`config/mcp.example.json`](../config/mcp.example.json)
als `mcp.json` in das private Laufzeitverzeichnis neben `principals.json`.
Setze die Dateirechte auf `0600`. Die Datei schaltet mit `{"enabled": true}`
die Brücke ein. Eine bereits vorhandene gültige Konfiguration im alten Format
schaltet sie ebenfalls ein. Die Rechte für einzelne Rollen und Gruppen werden
auf [der Rechteseite](sso-berechtigungsmodell.md#rechte-über-die-oberfläche-verwalten)
mit „MCP-Token erstellen“ vergeben. Die bisherigen MCP-Listen erteilen und
sperren keine Kontenrechte mehr. Entferne die Datei oder setze
`{"enabled": false}`, um die Brücke abzuschalten.

Der Wrapper prüft bei jedem Zugriff die Sitzung und die MCP-Freigabe.
Die Kopplung ist im eigenen Projektbereich verfügbar. Öffne dort einen
Entwurf und wähle **SSO-Menü → MCP-Token erstellen**. Der Token gilt für genau
diese Browsersitzung bis zur Abmeldung oder bis zum Sitzungsablauf. Die
Sitzung endet nach 70 Minuten Inaktivität oder spätestens 140 Minuten nach
der Anmeldung. Ein neu ausgestellter Token ersetzt den bisherigen.

MCP verarbeitet Nachrichten bis 4 MiB und höchstens einen laufenden Befehl je
Sitzung. Der normale Speicherweg legt Änderungen im ausgewählten eigenen
Entwurf ab. Die Eigentümerzuordnung gilt auf Projektebene.

## stdio-Client vorbereiten und verbinden

Der Build erzeugt den Client lokal aus den vier MCP-Quelldateien des
gepinnten Layerling-Commits. Er wendet den Adapter aus `cad/mcp-client.patch`
an und übernimmt die Layerling-Lizenzdatei. Der Layerling-Checkout dient als
Git-Quelle. Der fertige statische CAD-Build und eine Node-Paketinstallation
sind für diesen Schritt nicht erforderlich.

```sh
python3 scripts/prepare-mcp-client.py \
  --layerling ../layerling \
  --output build/sso-mcp-client
```

Im MCP-Client `node` mit dem absoluten Pfad zur erzeugten
`build/sso-mcp-client/scripts/layerling-mcp-server.mjs` als Argument
hinterlegen. Setze `LAYERLING_URL` auf die HTTPS-Origin deiner Installation
und übergib den kopierten `LAYERLING_MCP_TOKEN` aus dem lokalen
Geheimnisspeicher des Clients. Der erzeugte Client wählt `/mcp.php` und fragt
laufende Befehle per HTTP 202 ab. Gib den Token nur dem Client auf deinem
Rechner.

Lass den Entwurf im Browser geöffnet. Mit `layerling_list_editors` lässt sich
die Kopplung prüfen. Wenn mehrere Tabs offen sind, verwende die angezeigte
`editorNumber` für `layerling_read_scene` und weitere Befehle.

## Lokaler Test mit synthetischem Konto

Der PHP-Test-Router stellt `/api/layerling-mcp` am Loopback bereit. Verwende
einen [gebauten CAD-Kandidaten](cad-integration.md) und starte die Demo aus
dem sso-layerling-Verzeichnis:

```sh
python3 tests/cad_http_test.py \
  --php php8.4 \
  --layerling ../layerling \
  --candidate build/sso-mcp-candidate \
  --mcp-demo
```

Die Demo öffnet Chromium mit einem synthetischen Konto und gibt die lokale
HTTP-Origin im Terminal aus. Wähle im eigenen Entwurf **MCP-Testtoken
erstellen**. Der Token gilt lokal höchstens 30 Minuten. Setze beim erzeugten
Client `LAYERLING_URL` auf die angezeigte Loopback-Adresse. Hier verwendet er
automatisch die lokale Route. Zum Beenden schließe das Demo-Fenster oder
drücke im Terminal Strg+C.
