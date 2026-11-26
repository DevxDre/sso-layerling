# OIDC-Profil je Deployment

Die private Deployment-Datei enthält Issuer, Web-Origin, Callback, Client-ID und
Berechtigungsbindungen. Als Ausgangspunkt dienen die [IServ-Deployment-Vorlage](../config/oidc.example.json)
und das [synthetische Campus-Profil](../tests/oidc-alternate.json). Für den Paketbau die
Datei an einen ignorierten Pfad kopieren, mit Dateirechten 0600 ablegen und eigene Werte
eintragen. Das Client-Secret gehört in die separate private `.env` außerhalb des Webroots.

## Anmeldeserver und Claims

Ohne `provider` gilt das [IServ-Profil](../config/oidc-iserv.json). Für einen anderen
Anmeldeserver enthält `provider` alle folgenden Felder.

| Feld | Bedeutung |
|---|---|
| `name` | Anzeigename auf der Anmeldeseite und in der Kontodiagnose |
| `endpoints` | Absolute Pfade `authorize`, `token`, `userinfo` und `jwks` auf dem HTTPS-Origin des Issuers |
| `scopes` | Angeforderte Scopes als Liste einschließlich `openid` |
| `claims.identity` | Stabiler Claim mit `format` `uuid` oder `opaque`. Für das geprüfte OIDC-Subject `{"claim":"sub","format":"opaque"}` verwenden |
| `claims.name`, `claims.username` | Schlüssel für optionale Anzeige- und Benutzerkennung |
| `claims.roles` | Claim mit `format` `strings` für eine Liste von Rollenkennungen oder `objects` mit einem konfigurierten `id`-Feld |
| `claims.groups` | Claim mit `format` `strings`, `objects` oder `map`. Bei `map` muss der Objektschlüssel der Gruppen-ID im `id`-Feld entsprechen. `label` und `account` sind optionale Felder für Objektformate |
| `classPrefixes` | Geordnete Liste der Präfixe für Klassen und Kurse aus dem Gruppenfeld `account`, etwa `["cohort-", "course-"]`. Das erste passende Präfix wird entfernt |
| `templatePublisherRoleIds` | Kompatibilitätsfeld für bestehende Profile. Freigaben für Vorlagen werden auf der Rechteseite vergeben |

Claim-Schlüssel beziehen sich auf die oberste Ebene von ID-Token oder gebundener
UserInfo. Überlappende Identitäts-, Rollen- und Gruppen-Claims müssen zwischen beiden
Antworten übereinstimmen; beim Rollen-Claim genügt dieselbe Menge gültiger Rollen-IDs
([ADR 0003](adr/0003-rollen-claim-konsistenz.md)), etwa bei übersetzten Rollennamen. IDs werden exakt und mit Beachtung der Groß- und Kleinschreibung
verglichen. UUIDs in der Eigentümerbindung werden wie bisher in Kleinbuchstaben
normalisiert. Gruppenkennungen bestehen aus ASCII-Buchstaben, Ziffern, Unterstrich und
Bindestrich. Rollenkennungen dürfen zusätzlich Punkt und Doppelpunkt enthalten.

Der Issuer darf einen Pfad enthalten. Die Endpunktpfade beziehen sich auf seinen
Origin, einschließlich eines gegebenenfalls konfigurierten Ports. Der Anbieter muss
Authorization Code mit PKCE S256, RS256, `client_secret_post` sowie UserInfo mit
passendem `sub` unterstützen. Die RSA-Schlüssel im JWKS brauchen `alg: RS256`,
`use: sig` und ein eindeutiges `kid`. Alle Endpunkte werden beim Paketbau festgelegt.

## Berechtigungsbindungen

- `studentRoleId` und `groupBindings.students` steuern die Schülerzuordnung. Eine
  nichtleere Rollenliste hat Vorrang. Ohne Rollen greifen die Schülergruppen.
  `studentRoleId: null` schaltet die rollenbasierte Schülerzuordnung ab.
- `groupBindings.makerspace` und `groupBindings.admins` werden für bestehende
  Deployment-Dateien und Diagnosevorgaben eingelesen. Freigaben für fremde
  Konten, Vorlagenverteilung und MCP werden auf der Rechteseite vergeben.
- `diagnosticGroupIds` beschränkt die Gruppenanzeige auf exakte IDs. Standard sind
  die beiden früheren Betreuungs- und Admin-Gruppen. `[]` blendet Gruppen aus.

Für Rechte zählen ausschließlich die geprüften Kennungen. Gruppentitel, Benutzername,
Name und die aus Gruppen abgeleiteten Klassen werden für die Anzeige verwendet.
Der historischen IServ-Metadatenprobe [iserv-claims-metadata.py](../scripts/iserv-claims-metadata.py)
liegt ein eigener fester Satz früherer Suchfilter zugrunde.

## Kompatibilität

Bestehende IServ-Deployments können ihre bisherige Deployment-Datei weiterverwenden.
Die Bindung aus Issuer und kleingeschriebener IServ-UUID ergibt weiterhin dieselbe
Eigentümer-ID. Der Installer führt Projekte und Vorlagen bei einer Aktualisierung
unter ihren bestehenden IDs weiter. Einen Wechsel des Issuers, Identitätsclaims
oder Identitätsformats lehnt er ab. Bei Bindung an `sub` prüft er auch die Client-ID,
da eine andere Registrierung andere Subjects erhalten kann. Für einen Identitätswechsel
ist vor der Umstellung eine explizite Zuordnung der bisherigen Eigentümer zu den neuen
Identitäten erforderlich.

Bei Änderung der Rollen- oder Gruppen-Claim-Zuordnung benötigen davon abhängige
Freigaben einen neuen Login. Die letzte Schülerzuordnung und vorhandene Projekte
bleiben für die bisherige Eigentümer-ID erhalten. Änderungen an Anzeigename,
Scope, Endpunkten, Klassenpräfixen und Anzeigefeldern benötigen keine Datenmigration.
