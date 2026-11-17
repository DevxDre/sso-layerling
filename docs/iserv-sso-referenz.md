# IServ-SSO: technischer Prüfvertrag

Der Wrapper verwendet feste Anbieter- und Callback-Adressen aus `src/Oidc/Config.php`,
Authorization Code mit PKCE S256 und RS256. Endpunkte dürfen nicht aus Browserparametern
oder ungeprüften Tokens übernommen werden.

`sub` und `iserv:uuid` haben unterschiedliche Aufgaben: UserInfo wird an das geprüfte
Token-Subject gebunden; die stabile Eigentümerbindung verwendet Issuer und IServ-UUID.
Rollenobjekte werden anhand geprüfter technischer Kennungen normalisiert.
Gruppen können als Objekt mit `{id, act, name}` vorliegen; eine leere Liste wird ebenfalls
unterstützt. Widersprüchliche Schlüssel, beschädigte Claims und unklare Typen ablehnen.
Öffentliche Tests enthalten ausschließlich synthetische Identitäten und Gruppen.

Zeit-, Audience-, State-, Nonce- und Signaturprüfung bleiben zwingend. JWKS auf öffentliche
RSA-Signaturschlüssel mit eindeutigen `kid` begrenzen; gefährliche Header und private
Schlüsselbestandteile ablehnen. Ein gültiges Token allein autorisiert keinen Fremddateizugriff.
Access-/Refresh-Tokens nicht dauerhaft speichern oder protokollieren; UserInfo an das
geprüfte Token binden. Ein `amr`-/`acr`-Wert begründet keine ungeprüfte 2FA-Zusage.

Konkrete echte Loginmessungen und deren Aussagegrenzen stehen ausschließlich in der
ignorierten internen Dokumentation. Rechtevertrag: [SSO-Modell](sso-berechtigungsmodell.md).
