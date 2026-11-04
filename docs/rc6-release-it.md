# Family Presence v0.1.0rc6 — rientro zaino basato sulla causa dell'assenza

Release normale **Latest** (non prerelease), dopo Python unit tests, HACS e
hassfest. Lo stesso packaging HACS funzionante della RC5 viene mantenuto:
manifest alla radice e `family_presence.zip` piatto.

## Modifica funzionale

- Lo zaino ON → OFF continua a mettere AWAY esclusivamente nei giorni e nella
  fascia configurata, **solo se non già AWAY**.
- Lo zaino OFF → ON mette HOME a qualunque ora, ma **solo** se la FSM aveva
  registrato un vero AWAY causato dallo zaino.
- Se un Watch porta quell'AWAY a NEAR_HOME, il successivo zaino ON può
  confermare HOME. Altre uscite/rientri confermati o la forzatura manuale
  annullano questa autorizzazione.
- La forzatura manuale AWAY non viene annullata da una semplice riconnessione
  BLE dello zaino. iPhone e Watch conservano il loro normale funzionamento.
- Un nuovo iPhone LEFT quando AWAY era ancora attribuibile allo zaino
  ne sostituisce il motivo e revoca il diritto di rientro dello zaino.
- Il sensore della persona espone l'attributo `bag_return_eligible`,
  che mostra l'effettiva possibilità di conferma del rientro da parte dello
  zaino. Gli eventi ignorati mantengono una motivazione diagnostica.

## Compatibilità dei dati

La snapshot usa ancora il formato 5, con il nuovo **campo opzionale booleano**
`bag_return_eligible`. Il campo è persistito e verificato al riavvio con lo
stesso fingerprint delle sorgenti. Le vecchie snapshot senza campo lo
interpretano **False** (mai ricostruito dal testo del motivo).

**Attenzione al primissimo aggiornamento da RC5:** se la persona risulta
già AWAY perché era uscita con lo zaino, il primo OFF → ON dello zaino
può essere ignorato proprio perché non era stato registrato il flag in RC5.
Un evento valido di iPhone, Watch o una correzione manuale può risolvere
quello stato; il nuovo ciclo completo di zaino funzionerà normalmente.

## Nessun altro cambiamento

Rimangono **un solo dispositivo virtuale Casa**, una entità per persona,
l'aggregato Casa certamente vuota, i pulsanti di forzatura, la configurazione
di `lock`/switch/binary_sensor per cancelli, e gli stessi `unique_id`.
L'integrazione non scrive i vecchi helper YAML né invoca servizi per
allarme, serrature o riscaldamento. Lasciare il vecchio YAML operativo
finché non viene eseguito il cutover sorvegliato.

Dettagli: [Comportamento dello zaino](bag-policy.md).
