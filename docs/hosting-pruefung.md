# Hostingvoraussetzungen

Die Anwendung benötigt PHP 8.4 mit curl, openssl, json, session, zip, fileinfo und
mbstring, HTTPS sowie private Verzeichnisse außerhalb sämtlicher DocumentRoots.
Öffentliche Einstiegspunkte und private Laufzeitdaten müssen getrennt sein.

Vor einer Bereitstellung sind PHP-FPM-Verhalten, Dateirechte, Sitzungspersistenz,
Transport zu IServ, Uploadgrenzen, Quota und Backup/Restore auf dem Zielsystem zu prüfen.
Andere Domains dürfen private Verzeichnisse nicht veröffentlichen.

Konkrete Server, SSH-Konten, Hostingmessungen und Betriebsnachweise gehören in die
ignorierte interne Dokumentation, nicht in dieses Repository.
