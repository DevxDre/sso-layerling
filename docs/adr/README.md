# Architekturentscheidungen

Hier werden Entscheidungen mit dauerhaften Folgen festgehalten, beispielsweise zur
Identitätsbindung, Rechteaktualität, Datenspeicherung oder einer neuen Anbieteranbindung.
Kleine Implementierungsdetails und reine Textänderungen brauchen keine ADR.
Echte Kontokennungen, Infrastrukturdetails und Zugangsdaten gehören nicht hierher.

Eine ADR enthält Anlass, Status, Entscheidung und Konsequenzen. Entwürfe ausdrücklich als
Vorschlag markieren; eine KI-Empfehlung ist keine beschlossene Projektentscheidung.
Ändert sich eine Entscheidung, dokumentiert eine neue ADR, welche frühere sie ablöst.
Alte Entscheidungen bleiben als solche nachvollziehbar.

## Entscheidungen

- [0001: SSO-Claims und letzte Schülerzuordnung](0001-sso-claims.md) – bestehende Entscheidung dokumentiert.
- [0002: OIDC-Profil und stabile Eigentümerbindung je Deployment](0002-oidc-deployment-profile.md).

## Vorlage

```markdown
# NNNN: Kurzer Titel

Status: Vorschlag / beschlossen / abgelöst durch NNNN

## Anlass

Welches konkrete Problem oder welche Einschränkung erfordert die Entscheidung?

## Entscheidung

Was wurde festgelegt? Welche Anforderung oder Abstimmung trägt diese Festlegung?

## Konsequenzen

Was bedeutet das für Verhalten, Daten, Kompatibilität, Prüfungen und verbleibende Grenzen?
```
