# 0002: OIDC-Profil und stabile Eigentümerbindung je Deployment

Status: umgesetzt gemäß der [Roadmap](../roadmap.md).

## Anlass

Deployments sollen unterschiedliche Anmeldeserver und Claim-Strukturen verwenden
können. Die Eigentümer-IDs eines bestehenden IServ-Deployments müssen dabei gültig
bleiben.

## Entscheidung

Das private Deployment-Profil legt Endpunkte, Claims und deren Normalisierung fest.
Für bestehende IServ-Installationen bleibt die Bindung aus Issuer und normalisierter
UUID erhalten. Generisch ist die Bindung der SHA-256-Hash aus Issuer, Nullbyte und
normalisierter stabiler Kennung. Der Installer vergleicht die Identitätsbindung
einschließlich Claim und Format mit dem vorherigen Paket. Für `sub` ist auch die
Client-ID Teil dieses Vertrags, da Subjects clientabhängig sein können. Ein Wechsel erfordert
eine explizite Migration.

Rollen und Gruppen werden mit der Zuordnung gekennzeichnet, unter der sie geprüft
wurden. Wenn sich diese Zuordnung ändert, erteilt die Policy darauf beruhende
Rechte erst nach einer erneuten Anmeldung. Die zuletzt bestätigte Schülerzuordnung
bleibt gemäß [ADR 0001](0001-sso-claims.md) gültig. Der Grund der Einstufung wird beim
Login mitgespeichert. Beim Upgrade alter Pakete hält der Installer die damalige
Schülerbindung für bestehende Einträge fest.

## Konsequenzen

Eigentümer-IDs, Projekte und Vorlagen bleiben bei Konfigurationsänderungen ohne
Identitätswechsel erhalten. Die Berechtigungsgruppen verwenden exakte IDs.
Anzeigenamen und Klassen bleiben Präsentationsdaten. Die Implementierung führt
keinen Verzeichnisabgleich ein. Die unterstützten Einstellungen stehen in der
[Profilkonfiguration](../oidc-profile.md).
