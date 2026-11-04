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
insieme, dopo aver installato e verificato i nuovi output.
**Anche `presenza_evento_fisico` è un writer**, come precisato sotto:

- `presenza_uscita_watch`
- `presenza_watch_rilevato`
- `presenza_watch_allontanato_near_home`
- `presenza_uscita_iphone`
- `presenza_rientro_iphone`
- `presenza_zaini_figlie`
- `presenza_evento_fisico` (oppure sostituita dalla sola registrazione eventi)

**ATTENZIONE: `presenza_evento_fisico` è anch'essa un writer.**
Non si limita a memorizzare i timestamp: quando rileva porta/cancello/
sblocco e un Watch compatibile, può scrivere `home` nei vecchi
`input_select.presenza_*`. Non può quindi restare attiva integralmente
insieme al nuovo motore. Nel cutover:
- disabilitarla con gli altri writer;
- eventualmente estrarne in una nuova automazione **solo** i timestamp
  degli eventi fisici, senza alcuna chiamata a
  `input_select.select_option` o `input_text.set_value`.

Anche `presenza_memorizza_ultimo_cambio` oggi ascolta i vecchi
`sensor.presenza_*`: va aggiornata o rimossa dopo la migrazione della
dashboard. La FSM Python legge già direttamente gli eventi fisici.

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

## Contratto delle automazioni YAML

La RC1 contiene `activation_contract.py` con funzioni **pure, senza
chiamate Home Assistant**, e test esaustivi delle condizioni:

- Inserimento (`familyuscita`): casa vuota ON **e** serratura
  `locked` **e** allarme `disarmed`.
- Disinserimento (`familyrientro`): transizione effettiva
  `away/near_home → home` **e** allarme `arming/armed_away`.
- Avviso porta: casa vuota ON e serratura diversa da `locked`,
  rivalutati dopo l'attesa prevista.

L'allarme è e resta comandato da automazioni YAML **indipendenti**.
Queste funzioni non sono connesse ad alcuna chiamata di servizio: servono
per verificare la logica prima di sostituire i riferimenti.

## Rischio nomi/ID in Home Assistant

Cambiare soltanto l'attributo `name` NON garantisce che Home Assistant
cambi l'`entity_id` registrato. Il modulo `presentation.py` prepara
i nomi definitivi ma mantiene **gli stessi unique_id** già registrati
nella Beta; nella RC1 la presentazione resta **Shadow**. Prima del cutover identificare
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

La Beta 1 e l'attuale sviluppo RC1 **non attivano** questi interventi.
Sono soltanto codice preparatorio, test e checklist. Il passaggio reale
richiederà una sessione di cutover esplicita e verificata.
