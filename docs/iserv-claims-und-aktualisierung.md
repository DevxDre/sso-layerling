# Claims und Aktualität der Berechtigungen

Aktuell verwendet der Wrapper ausschließlich Claims aus validierten SSO-Anmeldungen.
Es gibt keinen IDM-/LDAP-Zugang und keinen periodischen Verzeichnisabgleich.
Die letzte Schülerklassifikation eines Eigentümers bleibt bis zu dessen nächstem Login
bestehen. Maßgeblich ist das [SSO-Berechtigungsmodell](sso-berechtigungsmodell.md).

Der historische Metadatenprüfer `scripts/iserv-claims-metadata.py` ist keine Laufzeitabhängigkeit
und kein nächster Betriebsschritt. Er darf nicht als öffentlicher Einstieg bereitgestellt werden.
Die frühere Recherche und reale Beobachtungen werden ausschließlich intern aufbewahrt.
Aus öffentlich angebotenen Scopes oder API-Schemata keine freigeschalteten Rechte ableiten.
Neue Verzeichnisanbindungen benötigen eine eigene Entscheidung und Prüfung.
