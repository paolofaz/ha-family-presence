# Piano di passaggio dalla beta alla FSM definitiva (NON APPLICARE IN BETA)

Riferimento: package privato `Gestione presenza famiglia.txt`, verificato
per preparare la migrazione; non pubblicare il package su GitHub.

## Decisioni già approvate

- La FSM Python sarà l'unico motore di presenza.
- **Casa certamente vuota** sarà `on` se e solo se tutti e quattro
  i membri sono `away`, anche con forzature manuali e dopo un riavvio.
- I pulsanti `Forza a casa` / `Forza fuori casa` decidono lo stato
  subito; un successivo evento automatico valido può cambiarlo.
- Le automazioni indipendenti (allarme, riscaldamento, notifiche) restano
  in YAML, ma leggono gli output **definitivi** del motore Python.
- Nessuna doppia scrittura: mai due FSM che controllano la stessa presenza.

## Vecchio YAML: quali parti disattivare quando si farà il cutover

Le seguenti automazioni sono writer/motore logico e andranno disabilitate
insieme, dopo aver installato e verificato i nuovi output:

- `presenza_uscita_watch`
- `presenza_watch_rilevato`
- `presenza_watch_allontanato_near_home`
- `presenza_uscita_iphone`
- `presenza_rientro_iphone`
- `presenza_zaini_figlie`

Valutare anche `presenza_evento_fisico` e i timestamp vecchi: possono
essere conservati come diagnostica, ma la FSM Python legge già
direttamente gli eventi fisici. L'automazione
`presenza_memorizza_ultimo_cambio` oggi ascolta i vecchi
`sensor.presenza_*` e andrà sostituita o rimossa solo dopo la
migrazione della dashboard.

## Vecchio YAML: azioni da mantenere e collegare agli output nuovi

- `familyuscita`: ascolta attualmente
  `binary_sensor.casa_certamente_vuota`; inserisce l'allarme solo
  quando la casa è vuota, la serratura è `locked` e l'allarme è
  `disarmed`. Il trigger e il controllo verranno spostati al binario
  definitivo della nuova integrazione.
- `familyrientro`: ascolta gli
  `input_select.presenza_{paolo,cristina,giulia,arianna}` e controlla
  transizioni `away/near_home → home`, poi disarma l'allarme se armato.
  Andrà collegata ai sensori persona definitivi, mantenendo il controllo
  sulle transizioni e gli stati dell'allarme.
- `presenza_avviso_casa_vuota_porta_non_locked`: conserva la notifica,
  ma aggiorna il sensore di casa vuota al nuovo output definitivo.
- `notificacristinalavoroout`: basata su `person.cristina`, è già
  indipendente e deve rimanere invariata.

Gli `input_select`, gli `input_text` e i vecchi sensori template
possono essere mantenuti brevemente per rollback. Non vanno usati
contemporaneamente per comandare allarme o presenza. Le dashboard che
usano `sensor.presenza_*` richiederanno un aggiornamento ai nuovi stati.

## Rischio nomi/ID in Home Assistant

Cambiare soltanto l'attributo `name` NON garantisce che Home Assistant
cambi l'`entity_id` registrato. Prima del cutover identificare
`unique_id`, `entity_id` reali e dipendenze delle automazioni.
Il sensore legacy `binary_sensor.casa_certamente_vuota` dovrà essere
ritirato prima di assegnare lo stesso `entity_id` al nuovo sensore.
Verificare che non nasca un `_2` e che il rollback sia riproducibile.

## Procedura atomica (solo dopo beta approvata)

1. Backup completo; conservare il YAML originale e la configurazione
   Home Assistant.
2. Verificare tutti gli output definitivi e i loro ID in HA senza
   collegarli ancora all'allarme.
3. Disabilitare insieme tutti i writer della vecchia FSM.
4. Reindirizzare in un unico intervento i consumatori YAML alle entità
   definitive (anche le condizioni dell'allarme).
5. Ricaricare le automazioni e confermare che ci sia un solo motore
   logico di presenza.
6. Provare HOME/AWAY manuali, rientro, uscita, zaini e Watch con
   le condizioni dell'allarme e della serratura verificate.
7. Se fallisce: disabilitare i nuovi output operativi, ripristinare
   riferimenti e writer YAML, ricaricare, verificare
   `binary_sensor.casa_certamente_vuota` e stato allarme.

L'Alpha 9/Beta 1 **non** attiva alcuno di questi interventi. Questo
documento è solo una checklist di cutover da adattare dopo il test reale.
