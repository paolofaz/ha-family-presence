# Family Presence · Home Assistant

**Gestione avanzata della presenza familiare**, basata su una macchina a stati
finiti (FSM) indipendente per ciascuna persona. Integra iPhone, Apple Watch
rilevati via BLE, eventuali zaini BLE ed eventi fisici della casa.

**Versione stabile: 1.0.0** · Integrazione custom per Home Assistant ·
Licenza MIT · [Release e changelog](docs/v1.0.0-release-it.md)

> **Principio di sicurezza:** Family Presence calcola la presenza e rende
> disponibili entità di sola lettura. Non comanda direttamente allarmi,
> serrature, cancelli o riscaldamento. Le automazioni che li comandano sono
> indipendenti: verificane condizioni e ID prima di utilizzarle.

## Indice

1. [Come funziona](#come-funziona)
2. [Installazione e aggiornamento](#installazione-e-aggiornamento)
3. [Configurazione](#configurazione)
4. [Regole della FSM](#regole-della-fsm)
5. [Entità e attributi](#entità-e-attributi)
6. [Riavvii e persistenza](#riavvii-e-persistenza)
7. [Diagnostica e prestazioni](#diagnostica-e-prestazioni)
8. [Compatibilità con YAML e dashboard](#compatibilità-con-yaml-e-dashboard)
9. [Test e verifica](#test-e-verifica)
10. [Limiti conosciuti e risoluzione problemi](#limiti-conosciuti-e-risoluzione-problemi)

## Come funziona

Le persone non condividono uno stato unico: ciascuna ha un FSM con
**tre soli stati**:

| Stato | Significato | «Casa certamente vuota» |
| --- | --- | --- |
| `home` | Presenza in casa confermata dalla FSM | OFF |
| `near_home` | Rientro probabile ma ancora da verificare | OFF |
| `away` | Persona dichiarata fuori | Può contribuire a ON |
| Non determinato | Manca un evento sufficiente a inizializzare | OFF |

L'aggregato **Casa certamente vuota** va su ON **solo se tutte** le persone
configurate risultano `away`. Anche una sola persona `home`, `near_home`
o con stato non determinato lo lascia OFF.

`near_home` **non equivale a `home`**. Una automazione dell'allarme
che disinserisce al rientro deve richiedere un passaggio a `home`,
non soltanto il passaggio dell'aggregato a OFF.

### Architettura

`device_tracker` iPhone + Watch BLE + zaino BLE + porta/serratura/cancelli
→ adattatore eventi validati (`sources.py`)
→ coordinatore temporale per persona (`coordinator.py`)
→ regole deterministiche (`fsm.py`)
→ sensori, aggregato, pulsanti e diagnostica.

La posizione geografica («Work», scuola, altre zone) non è uno stato della FSM:
resta di competenza di `person.*` o di sensori template YAML per la dashboard.

## Installazione e aggiornamento

### Con HACS (consigliato)

1. In HACS aggiungi `https://github.com/paolofaz/ha-family-presence`
   come repository personalizzato di categoria **Integration**, se non è già presente.
2. Installa **Family Presence** dalla release stabile più recente.
3. Riavvia Home Assistant.
4. Vai in **Impostazioni → Dispositivi e servizi → Aggiungi integrazione**
   e configura **Family Presence**.

Per aggiornare dalla RC8 o da una RC precedente: **aggiorna da HACS e riavvia**.
Non eliminare e ricreare l'integrazione. La v1.0.0 conserva i suoi
`unique_id`, il dispositivo virtuale `Casa`, le associazioni sorgente,
gli stati e i salvataggi compatibili. L'`entity_id` effettivo può
contenere ancora `shadow` per ragioni storiche: prima di rinominarlo
controlla ogni automazione e dashboard che lo usa.

HACS scarica l'asset **`family_presence.zip`**, un archivio *piatto*
dell'integrazione. La release contiene anche manifest identici alla radice
del repository e nella cartella dell'integrazione.

### Installazione manuale

Dall'archivio sorgente del tag `v1.0.0` copia la directory
`custom_components/family_presence/` sotto
`<config_home_assistant>/custom_components/family_presence/`.
Riavvia, poi configura dall'interfaccia.
**Non** estrarre l'archivio ZIP HACS piatto direttamente dentro
`custom_components/`: quello ZIP contiene i file alla radice ed è pensato
per il meccanismo di installazione HACS.

## Configurazione

Nella procedura guidata scegli almeno una persona e le sue sorgenti.
L'integrazione gestisce più componenti della famiglia; per ogni persona
serve almeno una fonte fra iPhone, Watch e zaino.

| Campo | Entità Home Assistant | Uso |
| --- | --- | --- |
| Nome persona | Testo | Nome visualizzato |
| iPhone | `device_tracker` | Entrata/uscita dalla zona `home` |
| Watch | `binary_sensor` | Segnale BLE ON/OFF del Watch |
| Zaino (facoltativo) | `binary_sensor` | Uscita/rientro con regole dedicate |
| Cancelli | Uno o più `switch` / `binary_sensor` / `lock` | Impulso o sblocco di accesso |
| Contatto porta | `binary_sensor` | Apertura OFF→ON, chiusura ON→OFF |
| Serratura porta | `lock` | Blocco/sblocco |
| Allarme | `alarm_control_panel` | Solo evidenza ausiliaria per l'uscita Watch |

I campi relativi a cancelli, porta, serratura e allarme sono condivisi
dall'intero nucleo familiare. Le fonti iPhone/Watch/zaino sono personali:
evita di assegnare lo stesso dispositivo a più persone.

### Opzioni: finestre di correlazione

In **Family Presence → Configura** sono disponibili:

| Opzione | Predefinito |
| --- | ---: |
| Uscita: cancello | 120 secondi |
| Uscita: porta | 90 secondi |
| Uscita: serratura | 90 secondi |
| Rientro: cancello | 120 secondi |
| Rientro: porta | 120 secondi |
| Rientro: serratura | 120 secondi |
| **Conferma accesso dopo `near_home`** | **180 secondi** |

La nuova finestra `near_home_entry_seconds` è un **limite massimo per
confermare `home` tramite un evento fisico condiviso successivo alla
rilevazione personale del Watch**. Trascorsa la finestra,
la persona **rimane in `near_home`**: non passa automaticamente a `away`.
Un rientro iPhone valido continua a poter impostare `home`.
Questa opzione non sostituisce le altre tre finestre di rientro,
usate per i casi in cui il Watch torna ON da `away`.

I valori sono espressi in secondi e si applicano agli eventi,
**non** alla durata di disponibilità dei sensori BLE.
I timeout dei Watch e degli zaini si configurano nelle rispettive
integrazioni BLE; Family Presence non scansiona dispositivi e non ha
un proprio timeout di ricezione Bluetooth.

### Orari e giorni dello zaino

Ogni zaino ha:
- abilitazione `enabled`;
- orario di inizio `start` e fine `end`;
- giorni della settimana `days`, secondo il fuso orario di Home Assistant.

La fascia si applica **solo all'evento di uscita `ON → OFF`**:
il rientro `OFF → ON`, se autorizzato, funziona a qualsiasi ora.
Orari uguali, come `00:00–00:00`, significano 24 ore nei giorni selezionati;
sono ammesse fasce a cavallo della mezzanotte.

Il vecchio comportamento `always` / `legacy` viene letto per
compatibilità con la configurazione pregressa, ma non è una scelta
di precedenza attiva nella FSM.

Per rinominare, aggiungere o rimuovere persone o cambiare le sorgenti
fisiche usa **Riconfigura**. Per gli orari e le finestre usa **Configura**.

## Regole della FSM

### iPhone

- Transizione dalla zona `home` a una zona esterna → `away`.
- Transizione da una zona esterna a `home` → `home`.
- Le zone «Work», «Scuola» ecc. sono informazioni di posizione,
  non stati della FSM.
- La ripartenza con un tracker già `home` non viene trattata
  automaticamente come una nuova entrata: la macchina non inventa eventi.

### Apple Watch

- **Watch OFF** da `home` può portare ad `away` se corroborato
  da iPhone fuori, da un evento fisico di uscita temporalmente compatibile
  con l'attributo `last_seen_before_off`, o dall'allarme inserito `armed_away`.
- **Watch ON** da `away` attende due secondi e verifica che il segnale
  sia ancora ON. Se trova un evento recente di porta, sblocco o cancello,
  conferma `home`; altrimenti passa a `near_home`.
- **Watch OFF** da `near_home` non ancora confermato → `away`.
- **Evento fisico successivo** da `near_home` può confermare `home`
  soltanto se il Watch è ancora ON e il suo rilevamento personale
  che ha originato `near_home` è **recente**, entro la finestra configurata.
  Un evento condiviso arrivato troppo tardi non basta.

Un contatto porta condiviso non identifica chi l'ha attraversata.
La correlazione temporale limita i falsi riconoscimenti ma **non fornisce
una prova biometrica o individuale certa**. Per gli ingressi dall'esterno
la FSM usa dati probabilistici, non garantisce sicurezza antintrusione.

### Zaini BLE

- `ON → OFF`, se abilitato e nell'orario/giorno previsti,
  può portare ad `away` se la persona non era già `away`.
- Quando **quello zaino ha davvero causato `away`**, il motore
  registra internamente `bag_return_eligible = true`.
- `OFF → ON` può confermare `home` soltanto se tale diritto è ancora
  valido e la persona è `away` o `near_home`.
- Un nuovo evento iPhone, Watch o una forzatura manuale possono
  sostituire la precedente causa d'uscita; `bag_return_eligible`
  torna a `false`.
- Un recupero da `unknown`/`unavailable` a `on`/`off` non è
  un attraversamento reale e non provoca movimenti inventati.
- Uno zaino stabilmente OFF **non impedisce** a iPhone/Watch
  di stabilire un rientro.

L'attributo `bag_return_eligible` sui sensori personali con zaino
è una spiegazione della regola, **non** la lettura ON/OFF del beacon.

### Pulsanti manuali

Per ogni persona ci sono **Forza a casa** e **Forza fuori casa**.
La pressione applica subito `home` / `away` e salva il risultato.
Non è un «blocco» persistente: un evento realmente **successivo**
può prevalere. Un callback accodato con data precedente alla correzione
manuale non può annullarla.

## Entità e attributi

Tutte le entità appartengono a **un solo dispositivo virtuale Casa**.

| Entità | Stato/attributi | Uso |
| --- | --- | --- |
| `Presenza [nome]` | `home`, `near_home`, `away`; `reason` e `last_transition` | Presenza logica |
| `Presenza [nome]` con zaino | Come sopra + `bag_return_eligible` | Regola di rientro |
| `Casa certamente vuota` | Binary sensor `on/off`, senza attributi aggiuntivi | Aggregato per le automazioni |
| `Diagnostica presenza` | Stato sintetico, `source_warnings` e eventuale `restored_unverified_members` | Controllo anomalie |
| `Ultimi eventi accessi` | Tipologia dell'ultimo evento, timestamp per sorgente | Diagnostica storica degli accessi |
| `[Nome] — Forza a casa/fuori casa` | Pulsanti | Correzione manuale |

Il sensore `Ultimi eventi accessi` appare soltanto se è configurato
almeno un accesso fisico. Gli attributi sono:
`cancelli` (mappa dei singoli entity_id e ultimo impulso),
`porta_aperta`, `porta_chiusa`, `serratura_sbloccata`,
`serratura_bloccata`, `ultimo_evento_alle` e `ultima_sorgente`.

Per cancelli a impulso `switch`, un evento ON indica un
**azionamento**, non che il cancello sia fisicamente aperto.
Lo stesso vale per un cancello configurato come `lock`: uno sblocco
non prova l'apertura fisica. Lo stato istantaneo di un accesso
va letto dalle sue **entità originali Home Assistant**.

Gli attributi `last_transition` e quelli degli accessi sono
timestamp ISO con offset temporale; per mostrarli in orario locale
nella dashboard usa la conversione di Home Assistant/Jinja.

## Riavvii e persistenza

La FSM conserva in uno Store interno (formato snapshot **5**)
lo stato, l'ultimo motivo, la data dell'ultimo cambio, la
provenienza dello zaino e un breve contesto diagnostico.
Il nuovo rilascio mantiene la compatibilità con i dati salvati
dalle RC precedenti, **senza rinominare le entità esistenti**.

- **Stati ripristinati:** se un membro era `away` prima del riavvio,
  ritorna `away`. L'aggregato lo considera ancora `away`,
  anche se manca una verifica nuova dopo il boot.
- **Incertezza esplicita:** `Diagnostica presenza` espone
  `restored_unverified_members` finché il singolo membro non
  riceve una nuova decisione applicata dalla FSM.
  Questa indicazione **non modifica** `Casa certamente vuota`:
  non è una nuova regola di attivazione/disattivazione allarme.
- **Eventi fisici:** i timestamp di correlazione a breve termine
  **non vengono ripristinati** dal salvataggio.
  Gli ultimi eventi accesso visibili sono salvati separatamente,
  ma non possono essere usati come nuove prove di presenza.
- **`near_home` ripristinato:** non recupera un'età di rilevamento
  Watch fittizia; un semplice evento fisico dopo il reboot
  non può confermare `home` senza un nuovo rilevamento valido.
  È sempre possibile un rientro iPhone o la correzione manuale.

Questa scelta privilegia l'assenza di **falsi eventi sintetici**
rispetto alla ricostruzione automatica di movimenti avvenuti
mentre Home Assistant era spento.

**Attenzione operativa:** se il dispositivo era offline mentre qualcuno
rientrava, uno stato `away` ripristinato può essere ormai superato.
Il sensore «Casa certamente vuota» non è una misura indipendente
di occupazione fisica. Controlla l'eventuale avviso diagnostico
e la coerenza delle sorgenti dopo un riavvio problematico.

## Diagnostica e prestazioni

### Scaricare un rapporto diagnostico

In **Impostazioni → Dispositivi e servizi → Family Presence**,
apri il menu dell'integrazione e scegli **Scarica diagnostica**
(quando disponibile nell'interfaccia di Home Assistant).

Il file JSON viene **generato solo su richiesta**.
Contiene versioni, finestre di correlazione, stati FSM, provenienza
e motivo, sorgenti in forma di stati sintetici, eventi accettati/ignorati
recenti (massimo 12 per membro) e riepilogo degli accessi.
**Non include** nomi delle persone, ID di entità, zone geografiche
reali, indirizzi BLE, coordinate o dati di configurazione grezzi.
Contiene comunque **orari di eventi domestici**: condividilo solo
con persone di fiducia.

### Riduzione delle scritture

- I sensori pubblici sono aggiornati **solo quando cambiano
  stato o attributi effettivamente visibili**.
- I contatori degli eventi ignorati e lo storico di debugging non
  sono attributi dei sensori personali.
- I salvataggi della FSM vengono richiesti **solo per decisioni
  accettate** (e al disinstallo/unload), non per ogni variazione BLE
  senza cambio di presenza.
- Il salvataggio usa il meccanismo differito di Home Assistant,
  che può unire scritture ravvicinate.
- Gli orari degli accessi sono conservati in uno Store **separato**,
  soltanto quando viene riconosciuto un vero nuovo evento fisico.
- Nessun sensore calcola «minuti trascorsi» aggiornando il suo
  stato a ogni secondo.

Gli eventi scartati restano consultabili nei dati interni
durante la sessione e nel rapporto diagnostico; potrebbero non
essere recuperati dopo un crash se non si è verificata
un'altra decisione accettata che ha salvato la snapshot.

## Compatibilità con YAML e dashboard

Family Presence **sostituisce il motore di presenza YAML**,
non le automazioni indipendenti che gestiscono allarme, notifiche,
riscaldamento o dispositivi.

Se hai migrato dal vecchio package:
1. Disattiva le vecchie automazioni che calcolano o scrivono
   `input_select.presenza_*`, `input_text.presenza_*_motivo` e timestamp FSM.
2. Mantieni/adatta le automazioni indipendenti, usando i nuovi
   entity_id della FSM. Per il disinserimento considera solo
   transizioni a `home`, **non** `near_home`.
3. Se vuoi vedere «Work», «Scuola», «In casa», «Fuori casa» e la
   foto della persona, usa sensori **template YAML di presentazione**
   che combinano `sensor.presenza_[nome]` e `person.[nome]`.
   Non inserire le zone geografiche negli stati FSM.
4. Rimuovi eventuali helper precedenti solo dopo aver verificato
   che **nessun consumer YAML/Lovelace** li stia ancora usando.

La nuova integrazione **non** scrive sugli helper del vecchio motore
e **non** attiva servizi dell'allarme. I pulsanti di forzatura agiscono
solo sullo stato della persona dentro la FSM.

## Test e verifica

Esecuzione della suite, dalla radice del repository con Python 3.13:

```sh
python -m unittest discover -s tests -v
python -m compileall -q custom_components tests
```

La pipeline GitHub esegue inoltre **HACS validation** e **hassfest**.
La release stabile viene pubblicata soltanto se i controlli
sono tutti verdi e se il codice verificato coincide con `main`.

Dopo un aggiornamento importante prova nella tua installazione reale:
- Un'uscita iPhone e un rientro iPhone.
- Watch OFF con correlazione fisica; Watch ON con accesso recente.
- `away → near_home` (aggregato OFF) e successiva conferma `home`.
- Un'apertura tardiva di porta quando `near_home` è vecchio:
  non deve causare `home` fittizio.
- Un ciclo zaino `ON → OFF → ON` nella fascia di uscita.
- Un riavvio con qualcuno `away` e/o `near_home`.
- Gli ultimi eventi accessi, distinti per cancelletto,
  carrabile, porta e serratura.
- Un rapporto diagnostico e l'assenza di eventi duplicati nel Recorder.

I test automatici coprono la logica e la struttura HACS;
**non sostituiscono** un collaudo dei dispositivi reali.

## Limiti conosciuti e risoluzione problemi

| Sintomo | Verifica |
| --- | --- |
| Una persona rimane `near_home` | Attendi un nuovo evento valido; nessun timeout automatico cambia lo stato. Un accesso condiviso fuori finestra non basta. |
| Dopo il reboot `away` sembra vecchio | Controlla `restored_unverified_members`, iPhone/Watch e, se necessario, usa il pulsante manuale. |
| `bag_return_eligible: false` | Non è un errore BLE: indica soltanto che lo zaino non può confermare da solo il rientro. |
| «Casa certamente vuota» è OFF | Almeno una persona non è `away`, oppure ha stato non determinato. |
| Un impulso di cancello appare ma non è aperto | Gli impulsi non equivalgono a contatti di apertura; usa il sensore fisico vero per conoscere lo stato. |
| Non compare «Ultimi eventi accessi» | Configura almeno una sorgente fra cancello, contatto porta o serratura. |
| Un `entity_id` contiene ancora `shadow` | Identità conservata dal registro HA: non rinominare senza aggiornare tutti i riferimenti. |
| Il rientro durante un'interruzione non è stato visto | Un riavvio non inventa transizioni; occorre una nuova evidenza o una correzione manuale. |
| Il file diagnostico mostra motivi ma non ID sensibili | È voluto per non esportare identificatori privati. |

**Limite strutturale:** i segnali BLE possono essere intermittenti e
gli eventi fisici condivisi non identificano da soli una persona.
La FSM è un motore di automazione domestica avanzata,
non un sistema certificato di sicurezza, presenza fisica
o antintrusione.

## Documentazione e licenza

- [Note di rilascio v1.0.0](docs/v1.0.0-release-it.md)
- [Architettura attuale](docs/architecture.md)
- [Regole dello zaino](docs/bag-policy.md)
- [Analisi sorgenti BLE](docs/ble-sources.md)
- [Licenza MIT](LICENSE)

La cronologia di Alpha, Beta e RC rimane nel repository come
documentazione **storica**, non come comportamento attivo della v1.0.
