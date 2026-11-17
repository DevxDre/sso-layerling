# Lokaler MCP-Teststand


Der Kandidat `build/sso-mcp-candidate/` verwendet den gepinnten statischen
Layerling-Export. Der PHP-Test-Router stellt `/api/layerling-mcp` am Loopback bereit.
Der angepasste Export aktiviert die Anbindung auf der persönlichen CAD-Seite,
wenn die geprüfte IServ-Sitzung für MCP freigegeben ist. Der Layerling-Fork
liefert weiterhin den stdio-Client. Der Test-Router liegt außerhalb des
DocumentRoots und wird bei der Paketierung für einen gehosteten Betrieb nicht mitgeliefert.

#### Selbst ausprobieren

Im Verzeichnis `sso-layerling` starten. Der Befehl öffnet ein separates Chrome-Profil
mit einem synthetischen IServ-Testkonto und zeigt die lokale Adresse im Terminal an.

```bash
python3 tests/cad_http_test.py \
  --php /opt/homebrew/opt/php@8.4/bin/php \
  --layerling ../layerling \
  --candidate build/sso-mcp-candidate \
  --mcp-demo
```

1. Einen Entwurf öffnen oder anlegen. Im SSO-Menü **MCP-Testtoken erstellen** wählen.
2. Im MCP-Client `node` mit dem absoluten Pfad zu
   `layerling/scripts/layerling-mcp-server.mjs` als Argument hinterlegen.
   Dem Prozess `LAYERLING_URL` aus dem Terminal, den kopierten
   `LAYERLING_MCP_TOKEN` und `LAYERLING_MCP_OPEN_EDITOR=0` übergeben.
3. Mit `layerling_list_editors` den Tab suchen, mit `layerling_read_scene`
   die Szene lesen. Chrome-Fenster schließen oder im Terminal Strg+C drücken,
   um den Test zu beenden.

Falls ein neuer Kandidat nötig ist, werden die Zielverzeichnisse zuerst frei
gewählt. `prepare` und `package` verlangen einen noch nicht existierenden Pfad.

```bash
python3 scripts/cad-candidate.py prepare --layerling ../layerling --output /private/tmp/sso-layerling-mcp-source
python3 scripts/cad-candidate.py build --layerling ../layerling --source /private/tmp/sso-layerling-mcp-source
python3 scripts/cad-candidate.py package --layerling ../layerling --source /private/tmp/sso-layerling-mcp-source --output build/sso-mcp-candidate
```

#### Freigaben und Grenzen

Die private `app/mcp-test.json` im temporären Laufzeitverzeichnis enthält die
Regeln. Der Demo-Start setzt automatisch eine Freigabe für das synthetische
Konto. Für einen anderen lokalen Testlauf haben die Regeln diese Form:

```json
{
  "allow": {"accounts": [], "roles": ["ROLE_TEACHER"], "groups": ["layerling-mcp"]},
  "deny": {"accounts": [], "roles": [], "groups": []}
}
```

`accounts` erwartet interne 32-stellige Konto-IDs, `roles` und `groups`
erwarten die geprüften IServ-Kennungen. Ein Treffer in `allow` genügt, sofern
kein Treffer in `deny` vorliegt. Leere Freigabelisten sperren alle Konten.
Die Gruppen und Rollen entsprechen dem letzten erfolgreichen SSO-Login.

Ein Token gilt für höchstens 30 Minuten und für genau die Browsersitzung,
in der er erzeugt wurde. Ein neuer Token ersetzt den bisherigen. Der Server
prüft die Sitzung und die Freigabe bei jedem Zugriff. Der Teststand nimmt
JSON-Nachrichten bis 4 MiB und höchstens einen laufenden Befehl pro Sitzung an.

Der automatisierte CAD-Test prüft die Regeln, den CSRF-Schutz und die
Trennung zwischen Konten sowie zwischen zwei Sitzungen desselben Kontos.
Chromium prüft das Ausstellen eines Tokens im SSO-Menü und verwendet den
Layerling-stdio-Client zum Auflisten, Lesen und Anlegen eines Quaders.
Danach prüft der Client, dass die Abmeldung seinen Token ungültig macht.
Alle 25 CAD-Integrationsprüfungen und sieben Build-/Paketprüfungen sind
bestanden. Der Demo-Start und das Aufräumen nach Strg+C wurden separat geprüft.

Nächster Schritt ist ein manueller Versuch mit einem eigenen Entwurf im
lokalen Demo-Browser. Eine gehostete Teststellung erfordert einen separaten
Betriebstest für die PHP-FPM-Anbindung mit echten IServ-Gruppen.
