# Family Presence v0.1.0rc7 — sensori puliti e meno scritture sul DB

Release normale **Latest**, pubblicata da `main` soltanto dopo test
Python, HACS e hassfest. Nessun cambiamento alla logica della FSM:
iPhone, Watch, zaini, `near_home`, forzature e aggregato conservano
gli stessi comportamenti della RC6. Resta il packaging HACS funzionante
delle release precedenti.

## Attributi dei sensori di presenza

I sensori individuali definitivi mostrano soltanto:

- **`reason`**: motivo in italiano dello stato attuale.
- **`last_transition`**: data e ora ISO dell'ultima transizione reale
  di presenza (o forzatura manuale), senza contatori crescenti.
- **`bag_return_eligible`**: solo per una persona con zaino; indica
  se il rientro OFF→ON dello zaino è autorizzato dal precedente BAG_LEFT.

Gli altri attributi di test e debugging (`mode`, `state_origin`,
`reason_origin`, `restored_from_storage`, `bag_state`, orari dello
zaino, `manual_last_action`, `last_ignored_*`, `ignored_event_count`,
`recent_events`, ecc.) **non sono più pubblicati** nei sensori di
presenza definitivi. Gli eventi e la provenienza restano gestiti
internamente dalla FSM.

## Casa certamente vuota e diagnostica

- `Casa certamente vuota`: pubblica soltanto il booleano ON/OFF, senza
  attributi extra potenzialmente variabili. Non cambia la regola:
  ON solo quando tutti sono AWAY.
- `Diagnostica presenza`: mantiene lo stato sintetico e pubblica
  `source_warnings` soltanto se ci sono anomalie delle sorgenti.
  Queste possono cambiare in corrispondenza di un reale cambiamento
  dell'anomalia, non continuamente in funzione del tempo.

## Riduzione delle scritture

Ogni sensore personale, l'aggregato e la diagnostica confrontano
`(valore, attributi)` con l'ultima rappresentazione visibile.

Quando il motore notifica per un BLE ON/OFF ignorato, un aggiornamento
di sorgente che non cambia la presenza, o un evento scartato, **non viene
eseguito `async_write_ha_state` per i sensori il cui output è invariato**.

Le transizioni reali, i cambiamenti di motivo, le forzature manuali e
l'autorizzazione del ritorno dello zaino continuano invece ad aggiornare
correttamente la relativa entità, così lo storico mantiene gli
avvenimenti importanti. Non ci sono attributi calcolati in base
all'ora corrente né aggiornamenti ogni secondo.

## Aggiornamento da RC6

1. Aggiornare via HACS e riavviare Home Assistant.
2. Verificare stato, `reason`, `last_transition` e,
   sulle ragazze con zaino, `bag_return_eligible`.
3. Verificare che `Casa certamente vuota` continui a seguire tutte
   le persone AWAY e che `NEAR_HOME` lo porti a OFF.
4. Se una dashboard usa un vecchio attributo diagnostico eliminato,
   sostituirlo con quelli essenziali o leggere il dato dai sensori
   sorgente. I vecchi valori di storico non vengono cancellati.

Nessuna riconfigurazione è necessaria: dispositivi, `unique_id`,
`entity_id` registrati e opzioni rimangono invariati.
