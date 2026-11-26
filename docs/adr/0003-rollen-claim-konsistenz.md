# 0003: Rollen-Claim zwischen ID-Token und UserInfo über Rollen-IDs abgleichen

Status: beschlossen (26.11.2026). Präzisiert die Konsistenzregel des
[OIDC-Profils](../oidc-profile.md) für den Rollen-Claim; 0001 und 0002 bleiben gültig.

## Anlass

Der Wrapper verlangt, dass überlappende Identitäts-, Rollen- und Gruppen-Claims im signierten
ID-Token und in der UserInfo übereinstimmen. Bisher wurde der Rollen-Claim bytegenau verglichen,
einschließlich Reihenfolge, Feldern und Feldwerten.

Ein Konto mit englischer IServ-Kontosprache konnte sich deshalb nicht anmelden
(`userinfo_mismatch:iserv:roles`). Die Diagnose ergab `same-ids:values:displayname:text:1-1`:
gleiche Rollen-ID, aber ein anders lautender `displayName`. Der Anbieter übersetzt den
Rollennamen offenbar nur in einer der beiden Antworten. Jedes Konto mit nicht-deutscher
Kontosprache ist betroffen.

Rechtewirksam ist nur die Rollen-ID. Gespeichert werden je Konto ausschließlich Rollen-IDs;
Rechteregeln, Schülerzuordnung und MCP-Freigabe prüfen nur deren Vorhandensein. Anzeigenamen,
Rollen-UUIDs, Zusatzfelder und die Reihenfolge werden nicht ausgewertet.

## Entscheidung

Für den Rollen-Claim gilt die Konsistenzprüfung als erfüllt, wenn beide Antworten exakt
übereinstimmen oder dieselbe Menge gültiger Rollen-IDs liefern. Die IDs werden mit derselben
Zuordnung gelesen wie für die Rechte (`id`-Feld bei Objekten, der Wert bei Zeichenketten) und
exakt mit Beachtung der Groß- und Kleinschreibung verglichen.

Abgelehnt bleiben abweichende Rollen-IDs in beide Richtungen sowie ungültige Rollenlisten,
ungültige und doppelte Rollen-IDs. Für `iss`, `aud`, den Identitäts-Claim und den
Gruppen-Claim bleibt der exakte Vergleich bestehen. Beim Gruppen-Claim werden neben der ID
auch Felder wie das Konto für die Klassenzuordnung ausgewertet; eine Lockerung dort braucht
eine eigene Entscheidung.

## Konsequenzen

- Konten mit übersetzten oder abweichend formatierten Rollennamen können sich anmelden.
  Die Rechte ändern sich dadurch nicht, weil die Rollen-IDs übereinstimmen müssen.
- Die UserInfo kann weiterhin keine Rolle gewähren, die das signierte ID-Token nicht enthält.
- Bei abgelehnten Rollen-Claims bleiben Protokollzusammenfassung und Kurzbefund auf der
  Fehlerseite erhalten (`ids:a-b`, `token:…`, `userinfo:…`). Die Befunde `same-ids:…`
  treten bei Ablehnungen nicht mehr auf, weil gleiche ID-Mengen jetzt akzeptiert werden.
- Regressionen prüfen angenommene Fälle (übersetzter Name, Reihenfolge, Feldreihenfolge,
  Zusatzfeld, Schreibweise, Unicode-Form, Typ der Rollen-UUID) samt gespeicherter Rollen-IDs
  sowie die weiterhin abgelehnten Fälle.
- Liefert ein Anbieter künftig rechtewirksame Rollendaten außerhalb der ID, ist diese
  Entscheidung neu zu prüfen.
