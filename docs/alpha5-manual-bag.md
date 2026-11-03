# Alpha 5 — eccezione manuale quando la persona torna senza zaino

Questa alpha implementa **solo controlli shadow/diagnostici**, senza modificare il vecchio YAML o chiamare servizi per allarme, serrature e riscaldamento.

## Motivazione

Con la regola **Priorità assoluta**, lo zaino `off` prevale sull'iPhone, sul Watch e sul cancello. È utile contro il falso rientro creato da un Watch rimasto a casa, ma può dare un falso `away` se la persona ritorna senza il suo zaino.

La conferma esplicita di una persona presente deve vincere sulle deduzioni BLE, e **non deve decadere automaticamente in un'assenza**.

## Interfaccia Home Assistant

Per ciascuna persona con zaino e politica `always` sono esposti due **pulsanti diagnostici**:

- **Family Presence Shadow [persona] — Conferma in casa senza zaino**: disponibile soltanto quando lo zaino è `off`. Porta la FSM shadow a `home`, registra l'ora della conferma e la salva immediatamente su HA Store.
- **Family Presence Shadow [persona] — Revoca conferma senza zaino**: disponibile soltanto con deroga attiva. Porta la FSM shadow a stato **unknown** (`None` internamente), non a `away`, e imposta un blocco che richiede nuove prove di presenza/uscita.

Sono pulsanti di prova, non automazioni. Home Assistant non riceve entità di presenza definitive né comandi per dispositivi.

## Garanzie di sicurezza

1. La conferma manuale è permessa solo in `always` con zaino effettivamente `off`; non è attivata da Watch, cancello o riavvio.
2. Finché è attiva e lo zaino resta `off` o `unknown/unavailable`, gli eventi automatici non portano la persona a `away`. Gli eventi soppressi sono diagnosticabili.
3. Dopo **8 ore** si attiva un indicatore di controllo (`manual_review_required`), **senza** cambiare lo stato. È una scadenza di verifica, non una scadenza del riconoscimento di presenza.
4. Lo zaino osservato `on` termina la deroga, anche se passa da `unavailable` a `on`. Una recovery non è falsamente registrata come rientro fisico.
5. La revoca mette lo stato a non determinato. Uno zaino che resta `off`, un evento del cancello condominiale o un Watch perso **non** bastano da soli a forzare subito `away`. Un nuovo evento iPhone che lascia casa può invece stabilire una nuova uscita.
6. La deroga e la fase incerta successiva alla revoca sopravvivono ai riavvii tramite snapshot di formato **3**; formati 1 e 2 rimangono compatibili in lettura.
7. Dopo un riavvio lo stato ripristinato non è una prova abbastanza fresca per attestare `all_away=True`.
8. I pulsanti persistono immediatamente la modifica e scrivono una riga di log `[shadow][manual]`, senza dati BLE sensibili.

## Attributi del sensore shadow

`manual_home_active`, `manual_home_since`, `manual_review_due_at`, `manual_review_required`, `manual_last_action`, `manual_last_action_at`, `manual_suppressed_event`, `manual_suppressed_at`.

`manual_review_required` viene calcolato in base all'orologio, ma il sensore attualmente si aggiorna al successivo evento della sorgente: per sapere con precisione quando effettuare il controllo è disponibile anche `manual_review_due_at`. Non è ancora un sistema di notifiche.

## Prova sul campo e limiti

Verificare manualmente, senza alterare le automazioni dell'allarme:
- zaino `off`, conferma HOME e tentativo di nuovo rilevamento Watch/cancello: HOME deve restare;
- zaino `unavailable` e poi `on`: il blocco manuale termina senza inventare un rientro;
- revoca mentre lo zaino è ancora OFF: lo stato diventa unknown e non può stabilire casa certamente vuota;
- riavvio con conferma HOME, e riavvio dopo una revoca: persistenza e prudenza devono restare coerenti.

I pulsanti sono **sperimentali**; mancano ancora validazione completa del ciclo di vita Home Assistant, eventuale audit dell'identità di chi preme, report storico delle divergenze e integrazione sicura con le entità di produzione.

**Scelta da riprendere alla fine:** mantenere entrambe le politiche zaino (**Priorità assoluta** / **Fascia scolastica**) oppure semplificare. La decisione esplicita è tracciata in [issue #3](https://github.com/paolofaz/ha-family-presence/issues/3); le due opzioni rimangono inalterate durante il test.
