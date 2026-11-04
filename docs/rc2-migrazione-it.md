# RC2 — Guida di migrazione verso gli output definitivi

La RC2 usa il profilo Final fin dalla prima installazione o dall'aggiornamento
della Beta 1. Non serve alcun comando ATTIVA/OMBRA. Il motore non comanda
direttamente allarme, serratura, riscaldamento, notifiche o vecchi input_select:
queste azioni continuano a dipendere da automazioni esterne.

## 1. ID nuovi: leggere il registro Home Assistant

Gli output nuovi usano gli stessi unique_id della Beta 1. Perciò, dopo un
aggiornamento, gli entity_id possono contenere ancora la parola shadow.
Le etichette cambiano, gli entity_id registrati NON vengono rinominati.

| Vecchio consumer | Nuova uscita RC2 | Nome suggerito in una installazione pulita |
|---|---|---|
| input_select di una persona | sensore RC2 della stessa persona (stati home/near_home/away) | sensor.presenza_famiglia_NOME |
| binary_sensor casa certamente vuota YAML | binary_sensor RC2 all_away | binary_sensor.presenza_famiglia_casa_certamente_vuota |
| input_text motivo persona | attributo reason del sensore RC2 | non è una nuova entità separata |
| input_datetime ultimo cambio persona | attributo last_transition ISO UTC del sensore RC2 | non è una nuova entità separata |
| sensor.presenza_NOME (template descrittivo) | stato grezzo della RC2 oppure nuova template card | non offre le vecchie etichette testuali |

La terza colonna è SOLO un esempio teorico di slug su una nuova configurazione:
leggere gli ID effettivi da Impostazioni → Dispositivi e servizi → Entità
(filtrando per l'integrazione Presenza famiglia). Non copiare questi nomi
come se fossero verificati. In particolare non usare il vecchio
binary_sensor.casa_certamente_vuota per l'aggregato RC2 finché il template
legacy è ancora registrato.

## 2. Prove iniziali con YAML ancora attivo

Aggiornare la Beta 1 alla prerelease RC2 e lasciare in esecuzione i vecchi
writer YAML e i vecchi consumer. La Python FSM pubblica nuovi output definitivi,
ma nessuna automazione di produzione li legge ancora. Verificare stati di tutte
le persone, attributo reason e aggregato. Confrontare l'aggregato RC2 con
il template storico. Raccogliere gli entity_id VERI dal registro.

## 3. Spostamento del controllo reale della casa

Fare una copia del package YAML privato prima delle sostituzioni. Non caricarlo
nella repository pubblica. Durante una finestra presidiata:

1. Sospendere i consumer automatici familyuscita, familyrientro e
   presenza_avviso_casa_vuota_porta_non_locked.
2. Disabilitare TUTTI i writer di vecchia presenza: presenza_evento_fisico,
   presenza_uscita_watch, presenza_watch_rilevato,
   presenza_watch_allontanato_near_home, presenza_uscita_iphone,
   presenza_rientro_iphone e presenza_zaini_figlie.
   presenza_evento_fisico NON è solo un recorder, scrive anche la presenza.
3. Modificare familyuscita: sostituire il binario YAML vecchio col binario
   RC2, conservando entrambi i trigger (casa vuota e serratura locked), il
   controllo all_away=on / lock=locked / alarm=disarmed e la notifica sul
   riscaldamento. Non sostituire la semantica del trigger con una condizione
   approssimativa.
4. Modificare familyrientro: usare i nuovi sensori RC2 per TUTTI i membri
   e rilevare solo passaggi away/near_home → home. Confermare che l'allarme
   si disarmi solo se arming oppure armed_away. near_home NON basta.
5. Modificare l'avviso serratura: usare il binario RC2, attendere 2 minuti
   e rivalutare che sia ancora on e la serratura non locked.
6. Rimuovere/convertire presenza_memorizza_ultimo_cambio se dashboard leggono
   già last_transition. Lasciare le notifiche indipendenti intatte.
7. Validare e ricaricare le automazioni, poi riabilitare i tre consumer nuovi.
   Non riabilitare i writer legacy mentre i nuovi consumer sono attivi.

## 4. Stati e dashboard

Il vecchio sensore descrittivo mostrava "In casa", "Vicino casa",
"Fuori casa" e talvolta la posizione geografica. La RC2 restituisce invece
i valori grezzi della FSM: home, near_home, away; per visualizzare le vecchie
etichette serve una template card o un template sensor apposito.

- stato: states('sensor.ID_EFFETTIVO_RC2')
- motivo: state_attr('sensor.ID_EFFETTIVO_RC2', 'reason')
- ultimo cambio UTC: state_attr('sensor.ID_EFFETTIVO_RC2', 'last_transition')
- ultimo cambio locale: convertire con as_local(as_datetime(...)) controllando
  prima che l'attributo non sia None; non aggiungere un +1h fisso a causa DST.
- aggregato: states('binary_sensor.ID_EFFETTIVO_RC2') in on/off.
- L'attributo picture e le geolocalizzazioni speciali dei vecchi template
  NON fanno parte del sensore RC2; vanno mantenuti in una template card separata.

## 5. Rischi espliciti

Il passaggio del binario all_away da off a on e il blocco serratura possono
avviare l'allarme attraverso familyuscita. Una transizione confermata a home
può disattivarlo attraverso familyrientro. Un "Forza AWAY" è uno stato valido
della FSM e può contribuire all'all_away. Confrontare i casi con le condizioni
del sistema reale, e provare i trigger in presenza di qualcuno che possa
interrompere il comportamento inatteso.

I test automatici NON simulano tutti gli eventi fisici dell'abitazione.
Nessun aggiornamento dell'integrazione da solo modifica i consumer YAML.
