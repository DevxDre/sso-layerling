# OIDC-Komponenten und Paketwahl

Stand der Vorbereitung: 03.11.2026. Schritt 1 der SSO-Vorbereitung abgeschlossen.
Ergebnis: konkrete Architektur- und Paketempfehlung, noch keine Paketfreigabe,
Installation oder OIDC-Implementierung im Wrapper.

**Aktualisierung 04.11.2026:** Paketfreigabe erteilt, unabhängiger OIDC-Kern und
separates Testportal implementiert. Aktueller Umsetzungs-/Prüfstand und Hoster-Sync:
[SSO-Teststand](sso-teststand.md). Folgende Abschnitte dokumentieren die vorherige Planung;
noch offene Paketfreigaben dort sind historisch. Die JSON-Vorlage wird vom Testportal nicht geladen.

## 1. Auswahl

Empfehlung: den begrenzten IServ-OIDC-Ablauf der Kirby-6-Anbindung als eigenständigen
PHP-Kern portieren und **genau ein neues Laufzeitpaket: `firebase/php-jwt` 7.2.1** verwenden.
Signaturprüfung und JWK-Umwandlung bleiben bei der Bibliothek; Transaktionen,
OIDC-Claim-Vertrag, sichere Sitzungsübergabe und Rechtepolitik liegen in eigenen Komponenten.
Das ist kein fertiger allgemeiner OIDC-Client und verlangt eigene Protokolltests und Pflege.

Keine Kirby-, Vue-, Node-, Datenbank- oder vollständige OAuth-Framework-Abhängigkeit
für die Anmeldung einführen. Netzverkehr über PHP-cURL; Uhr und HTTP-Transport injizierbar
statt produktive Tests über globale Schalter/Browserparameter zu aktivieren.

## 2. Geprüfte Referenz und Abhängigkeit

Lokaler Kirby-6-Stand: `62d396953cd3775e22e12f5591835220c8a51c8c`.
Gelesen: `site/plugins/devxdre-iserv-auth/src/`, Plugin-README und ausgewählte
Prüfungen/Fixtures aus `scripts/login-test.php`; keine lokalen Secrets oder Kontodateien.
Diese Sichtung ist keine neue Ausführung der Kirby-Tests und kein vollständiges Audit.

Im Kirby-Projekt sind `firebase/php-jwt` **v7.2.1** und Quellreferenz
`0501f5729b9e2448516674aff07c7d1727869b8e` festgehalten. Dieselbe Referenz wurde mit
[Release v7.2.1](https://github.com/googleapis/php-jwt/releases/tag/v7.2.1) und dem
[Paketmanifest dieses Tags](https://github.com/googleapis/php-jwt/blob/v7.2.1/composer.json)
abgeglichen. Der Composer-Paketname bleibt `firebase/php-jwt`, obwohl das Quellrepository
inzwischen unter `googleapis/php-jwt` liegt.

| Merkmal | Vorgesehener Umfang |
|---|---|
| Neues Laufzeitpaket | `firebase/php-jwt: 7.2.1`, nach ausdrücklicher Abstimmung |
| PHP-Voraussetzung des Pakets | `^8.0`; unser Ziel bleibt PHP 8.4 |
| Weitere zwingende Composer-Laufzeitpakete | keine laut Manifest des Tags |
| Signaturverfahren | ausschließlich RS256; native OpenSSL-Erweiterung |
| Lizenz des Pakets | BSD-3-Clause; Lizenzdatei bei Paketierung erhalten |
| Nicht benötigt für unseren RS256-Pfad | Sodium-Kompatibilität, phpseclib, PSR-HTTP-/Cache-Pakete |
| Entwicklungsabhängigkeiten des Fremdpakets | nicht als unsere Laufzeitabhängigkeiten übernehmen |

Nach Freigabe: eigene `composer.json`/`composer.lock`, lokales Installieren ohne fremde
Composer-Skripte/Plugins, Plattformprüfung unter PHP 8.4, aktuelles Composer-Audit und
gezielte Tests. `vendor/` privat in das Installationspaket aufnehmen, kein Composer auf dem Hoster.
Vorher `.gitignore` um die tatsächlich eingeführten lokalen/Dependency-Artefakte ergänzen;
`composer.json` und `composer.lock` versionieren. Kein Zugriff auf Kirbys `vendor/` im Betrieb.
Vor einer späteren Installation Sicherheitsstand erneut prüfen; dies ist keine automatische
Freigabe zukünftiger Paketversionen und kein bereits angelegter Composer-Lock.

## 3. Sicherheitshinweise zum Paketstand

Die aktuelle [Packagist-Advisoryliste](https://packagist.org/packages/firebase/php-jwt/advisories)
nennt drei Meldungen. Die veröffentlichten Bereiche betreffen Versionen unter 7.0.0,
unter 6.0.0 bzw. unter 2.0.0. 7.2.1 liegt außerhalb dieser drei Bereiche.
Referenzen: [GHSA-2x45-7fc3-mxwq](https://github.com/advisories/GHSA-2x45-7fc3-mxwq),
[GHSA-8xf4-w7qw-pjjw](https://github.com/advisories/GHSA-8xf4-w7qw-pjjw),
[GHSA-h533-5v22-8vcp](https://github.com/advisories/GHSA-h533-5v22-8vcp).
Das ist keine Aussage, dass das Paket oder unsere spätere Integration fehlerfrei sind.
Ein frischer `composer audit` gegen den tatsächlichen Wrapper-Lock wurde noch nicht ausgeführt,
weil es weder installierte Abhängigkeit noch diesen Lock gibt.

## 4. Abgewogene Alternativen

| Ansatz | Bewertung für dieses Projekt |
|---|---|
| Kleine Portierung + php-jwt | Empfehlung: gleicher Kern wie vorhandene Referenz, eine zusätzliche Bibliothek; eigene OIDC-Pflege bleibt bewusst bestehen |
| Vollständiger OIDC-Client | Mehr Protokollfunktionalität, aber deutlich größerer Integrations-/Abhängigkeitsumfang und erneute Bewertung des eigenen Sicherheitsvertrags |
| Reine PHP-/OpenSSL-Eigenentwicklung der JWT-/JWK-Prüfung | Keine Empfehlung: eigene Kryptografie-/Schlüsselformatlogik bringt hier keinen notwendigen Vorteil |

Der untersuchte [facile-it-Master](https://github.com/facile-it/php-openid-client/blob/master/composer.json)
verlangt u. a. JOSE-/JWT-Bibliotheken, Discovery und PSR-HTTP-Komponenten. Der untersuchte
[jumbojett-Master](https://github.com/jumbojett/OpenID-Connect-PHP/blob/master/composer.json)
verlangt phpseclib. Dies ist ein Vergleich der aktuellen Manifeste, keine vollständige
Versionen-/Sicherheitsbewertung dieser Alternativen und keine pauschale Ablehnung ihrer Qualität.
Die Einschränkung auf genau einen eigenen IServ-Anbieter und die vorhandene Referenz geben
hier den Ausschlag für den kleinen Ansatz.

## 5. Übertragbare Bausteine und klare Grenzen

| Referenz | Wrapper-Komponente / Vorgehen |
|---|---|
| `Transaction` | State, Nonce und PKCE-Verifier unabhängig zufällig erzeugen; S256, feste Bindungen und Frist übernehmen |
| `Transactions` | Speicheradapter neu für native PHP-Sitzungen/Versuchsregister; keine Kirby-Session verwenden |
| `OidcClient` | Autorisierungsadresse, Code-Tausch, geprüfter ID-Token und gebundene UserInfo; Netzwerk/Uhr explizit injizieren |
| `IdTokenVerifier`, `Jwks` | Prüfvertrag portieren; php-jwt für Signatur/JWK, zusätzliche OIDC-Prüfungen selbst |
| `Json`, `Identity`, `LoginFailed`, Clock/Transport-Verträge | Als kleine unabhängige Wert-/Fehlertypen adaptieren, keine Kirby-Typen nachziehen |
| `Config::fromKirby` | Durch validierte private Wrapper-Konfiguration ersetzen |
| `Claims` | IServ-UUID/Rollen/Gruppen streng normalisieren; Gruppen sind für die neue Rechtepolitik Pflichtdaten |
| `Flow`, `Login`, `Routes` | Ablaufgedanken übernehmen; eigene Start-/Callback-/Logout-Controller ohne Panel, Kirby-Auth oder rkm-access |
| `Accounts`, `Roles`, `SsoSession` | Nicht kopieren: privater Identity-/Principal-Writer und eigener SessionManager ersetzen die Kirby-Konten-/LMS-Semantik |
| `Services` | Testbarkeit beibehalten, aber produktive Dependencies über Konstruktoren liefern; kein HTTP-aktivierbarer Testtransport |

Vorgesehene Bereiche: `src/Oidc/` für Protokoll und Validierung,
eigene Session-/Identity-/Principal-Dienste für Anwendungspolitik und die vorhandene
`Policy`/`Gateway`-Grenze für Speicherzugriffe. Ein erfolgreicher JWT-Test allein erzeugt
keine Sitzung und schreibt keine Berechtigungen.

## 6. Sicherheitsvertrag des Kerns

Maßstab: [OIDC Core, ID-Token-Prüfung](https://openid.net/specs/openid-connect-core-1_0.html#IDTokenValidation)
und [OAuth Security BCP, Redirect-Flows](https://www.rfc-editor.org/rfc/rfc9700.html#section-2.1).

- Authorization Code, State, Nonce und PKCE S256; keine schwächeren Ausweichverfahren.
  Transaktion höchstens fünf Minuten, an den anonymen Anmeldekontext gebunden.
- Transaktion unter Lock genau einmal verbrauchen und vor dem ersten Netzaufruf speichern.
  Falscher State/abgelaufene Transaktion, doppelte oder parallele Callbacks erzeugen keine Anmeldung.
- Fester Issuer `https://login.example.invalid` und feste HTTPS-Endpunkte wie in der Referenz.
  Keine Schlüssel-/Token-URLs aus Request oder unbestätigtem JWT. Private Clientkonfiguration
  und Callback gegen den eigenen Ursprung prüfen; keine offenen Rücksprungziele.
- Transport: Zertifikats-/Hostprüfung, keine Redirects, etwa fünf Sekunden Verbindungs- und
  zehn Sekunden Gesamtlimit je Abruf, ein MiB Antwortlimit auch bei Streaming/Chunked-Antworten.
- `client_secret_post` und `code_verifier` wie bei IServ referenziert; Tokenantwort benötigt
  Bearer-Access-Token und ID-Token. Refresh-Token vorerst verwerfen und keine Tokens protokollieren.
- ID-Token: Format/Größenlimit, `alg` genau RS256, nichtleere `kid`; `crit`, `jku`, `x5u`,
  eingebettete `jwk` ablehnen. Header vor Signaturprüfung nur zum Ablehnen/Schlüsselnachschlagen
  verwenden, niemals als Identitäts- oder Berechtigungsnachweis.
- JWKS nur vom festen Endpunkt, öffentliche RSA-/Signaturschlüssel, eindeutige `kid`,
  erwarteter Algorithmus; unbekannte/mehrdeutige Schlüssel und nichtöffentliche Parameter ablehnen.
  Kein selbst gebauter RSA-/ASN.1-Parser. Pro Callback höchstens ein JWKS-Abruf; Rotation beim
  nächsten Callback sichtbar, kein stilles Weiterlaufen mit alten Schlüsseln bei Ausfall.
- Nach Signatur: exakter Issuer, eigene Audience und `azp`-Bindung, Pflichtfelder `exp`/`iat`,
  typgeprüftes `nbf`, nichtleeres `sub` und exakte Nonce. Kleine explizite Uhrtoleranz.
  Audience-Listen zusätzlich vollständig als nichtleere Strings prüfen; globale Zeit-/Leeway-
  Einstellungen der Bibliothek auch nach Ausnahmen zuverlässig wiederherstellen.
- UserInfo-`sub` muss dem geprüften ID-Token entsprechen; gemeinsame Identitätsclaims dürfen
  nicht widersprechen. Vorhandenes `at_hash` gegen das nur temporär gehaltene Access-Token prüfen.
- Daten erst nach Prüfung in eine tokenfreie Identität überführen. IServ-Rollen/Gruppen werden
  streng normalisiert; fehlender/unklarer Gruppenstand darf keine früheren Fremdrechte konservieren.

Die Referenz ist keine automatische Freigabe zum unveränderten Kopieren. Insbesondere die
vollständige Audience-Typprüfung, optionale Access-Token-Hashprüfung und Gruppennormalisierung
sind bei der Portierung explizit zu behandeln und mit eigenen Fällen zu prüfen.

## 7. Anbindung an den vorhandenen Wrapper

1. `POST`-Start mit CSRF, eigener anonymer Sitzung und persistent begrenzten Loginversuchen.
   Keine bereits angemeldete Identität stillschweigend ersetzen. Limits für Schulnetze bewerten;
   fremde Callbacks ohne Transaktion und Provider-Ausfälle nicht als Benutzerfehler zählen.
2. Anonymer Anmeldekontext und authentifizierte Sitzung erhalten getrennte Lebenszyklen.
   Die aktuelle Gateway-Prüfung verlangt bereits eine authentifizierte Sitzung und kann daher
   nicht direkt als OIDC-Startadapter verwendet werden.
3. Callback: Transaktion einmalig verbrauchen, Lock vor Netzwerk lösen, vollständig validieren.
   Noch keine globale Berechtigungssperre während externer HTTP-Anfragen halten.
   Scheitert der Callback nach dem Verbrauch, wird der Versuch als `failed` beendet: Der Code
   bleibt verbraucht, eine neue Anmeldung im selben Browser ist aber wieder möglich.
4. Tokenfreie Identität über einen privaten IdentityStore auf eine stabile interne Ordner-ID
   abbilden. IServ-spezifische Empfehlung: `(iss, iserv:uuid)`; `sub` weiterhin für Protokollbindung.
   Keine E-Mail-/Namenszuordnung, keine Übernahme vorhandener Kirby-Konten oder -Cookies.
5. Vertrauenswürdiger PrincipalWriter schreibt unter `authorization.lock` exklusiv und atomar.
   Fehlende Gruppen entfernen alte Freigaben; gespeicherte Nachweiszeiten nicht bloß durch
   Sitzungsaktivität verlängern. Alte/parallele Ergebnisse dürfen keinen neueren Entzug überschreiben
   (Version/Compare-and-Swap-Vertrag im Writer). UserInfo bestätigt nur den eigenen Akteur.
6. Anschließend separate neue authentifizierte Sitzung mit frischer serverseitiger ID und
   neuem CSRF-Token ausgeben; akzeptiertes ID-Format mit dem Gateway abstimmen. Keine alte
   Client-Sitzungs-ID übernehmen und keine noch gültige Alias-/Übergangsfrist für den alten Kontext.
7. Produktion: hostgebundene Cookies, Secure, HttpOnly und SameSite=Lax bei GET-Callback.
   HTTP-Ausnahme ausschließlich getrennt für Loopback-Tests; niemals aus einem Forwarded-Header
   eine unsichere Produktionskonfiguration ableiten.
8. Bisherigen Widerruf mit leerem Sitzungsdatensatz erhalten. Zusätzlich Abbruch/Logout eines
   laufenden Anmeldeversuchs vorsehen: ein verspäteter Callback darf nach serverseitiger
   Stornierung keine neue Sitzung erzeugen. Auch Rollenentzug zwischen Prüfung und Abschluss testen.
9. Antworten/Fehler `no-store`, Callback/Fehlerseiten `no-referrer`, keine fremden Ressourcen,
   keine Tokens/Provider-Antworttexte oder Query-Echos in App-Logs/Fehlermeldungen.
   Hoster-Protokollierung der Callback-Query vor Produktivbetrieb gesondert klären.

Produktive Fristen sind noch festzulegen. Die allgemeine Zulassung aller IServ-Benutzer
ist inzwischen bestätigt; sie gewährt keine Fremddateirechte.
Kirbys Sechs-Stunden-Regel, Admin-Ausschluss, Gruppenpriorität und lokales Logout-Verhalten
sind nicht automatisch für Layerling beschlossen. Der PHP-FPM-/Produktionsschutz des
Speicherprototyps bleibt während dieser Arbeit aktiv.

## 8. Übertragbarer Testplan

Die vorhandene Kirby-Suite dient als fachliche Vorlage, wird aber nicht samt Kirby installiert.
Neue isolierte PHP-Kerntests mit synthetischen RSA-Schlüsseln, festem Clock und FakeTransport;
anschließend echte lokale HTTP-Tests der eigenen Controller/Sitzungen. Keine zusätzlichen
Testpakete erforderlich, solange der bestehende Python-/PHP-Aufbau genügt.

| Gruppe | Aus Referenz übernehmen und an unseren Ablauf anpassen |
|---|---|
| O1 Konfiguration | fehlt/teilweise/fremde Callback-Adresse → kein Login; feste Providerpfade; kein externer Redirect |
| O2 Transaktion | State fehlt/falsch/fremde Sitzung/abgelaufen; Nonce; S256; Code-Replay, Parallel-Callback, ein Token-Tausch |
| O3 Token/Netz | falsche Signatur/Algorithmus, HS/RSA-Verwechslung, verbotene Header, unbekannte/doppelte kid, kaputtes JWKS, Rotation, Timeouts/Größenlimit |
| O4 Claims | iss/aud/azp, Zeittypen/-grenzen, sub/Nonce, UserInfo-Bindung, UUID/Gruppentypen und at_hash; positive Gegenprobe je Angriffsgruppe |
| O5 Anwendung | atomare Identitätszuordnung, PrincipalWriter, fehlende Gruppen entfernen Rechte, veraltete Writer-Ergebnisse, kein Schreibfehler mit Teilfreigabe |
| O6 Sitzung/Fehler | Fixierung, neue ID, Logout/Stornierung während Callback, keine Geheimnisse in Antworten/Logs/Dateien, Rate-Limits ohne schulweite Fremdsperre |

Kirby-spezifische Panel-, Passwort-/E-Mail-Code-, LMS- und Kontofeldtests nicht als
Wrapper-Nachweise ausgeben. Die bestehenden 35 Speicher-/Gruppentests müssen nach der
Implementierung weiterhin bestehen und durch neue OIDC-Prüfungen ergänzt werden.

**Aktualisierung der Datenquelle:** Der Nutzer hat inzwischen den Verzeichnisabgleich
zurückgestellt. Für die folgende Umsetzung gilt das [ausschließliche SSO-Modell](sso-berechtigungsmodell.md)
mit Gruppenfallback und letzter Eigentümer-Einstufung bis zur nächsten Anmeldung.

## 9. Ergebnis und nächste Schritte

Schritt 1 ist als Komponenten-/Paketprüfung abgeschlossen. Code, `.gitignore`, Composer-
Dateien und installierte Pakete wurden dadurch nicht verändert. Kein neuer Runtime-Test;
die bisherigen 35 erfolgreichen Speicherprüfungen stammen aus dem vorherigen Arbeitsschritt.

Als Nächstes den eigenen OIDC-Client konkret vorbereiten. Die Gruppenkennungen werden
über den geprüften Test-Login erhoben; ein IDM-Abgleich ist aktuell nicht vorgesehen.
Parallel kann der OIDC-Testvertrag konkretisiert werden. Vor einer Installation ist genau das hier beschriebene neue Paket
abzustimmen; bis dahin keine Abhängigkeiten hinzufügen oder aus Kirbys vendor kopieren.
Danach eigener IServ-Client/Callback und Implementierung des getrennten OIDC-Kerns.

## 10. Ergänzende bereitgestellte Messreferenz

Die vom Nutzer ergänzte [IServ-SSO-Referenz](iserv-sso-referenz.md) hält historische
Claim-Formen, Token-Eigenheiten und die damals gemessene Elternkonten-Beschränkung
fest. Als zusätzliche Testfälle übernehmen, nicht als neuen Test des Layerling-Clients
ausgeben. Keine Änderung der Paketfreigabe oder der bestätigten Gruppenpolitik.
