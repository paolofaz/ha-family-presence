# Family Presence v0.1.0rc5 — struttura dispositivi, cancelli lock e configurazione definitiva

Release Candidate pubblicata come release normale Latest (non prerelease) su main,
una volta superati test Python, HACS e hassfest.

## Novità rispetto a RC4

- Integrazione distribuita nel medesimo formato HACS funzionante di RC4:
  `content_in_root`, manifest di repository e asset di release
  `family_presence.zip` con file estratti direttamente nella cartella
  `custom_components/family_presence`.
- **Un dispositivo virtuale per ogni persona**: il sensore `Presenza`,
  il pulsante `Forza a casa` e il pulsante `Forza fuori casa` sono
  raggruppati sotto un dispositivo con il nome della persona.
- Un dispositivo virtuale `Famiglia` raccoglie
  `Casa certamente vuota` e `Diagnostica`. Per quattro persone rimangono
  quattordici entità, ma sono distribuite su cinque dispositivi.
- Non ci sono più nei form di configurazione né il confronto con
  `binary_sensor.casa_certamente_vuota` né gli `input_select` della vecchia
  FSM. Le impostazioni legacy eventualmente salvate vengono ignorate in
  runtime; non è necessario cancellare o ricreare l'integrazione.
- Gli attributi delle entità **Final** non espongono più i risultati del
  confronto con l'FSM YAML. Restano disponibili motivo, sorgenti, tempi,
  diagnostica degli eventi e stato delle persone.
- Il selettore di **eventi cancello** accetta `switch`, `binary_sensor` e
  `lock`. Per `switch` e `binary_sensor` registra solo **off → on**;
  per `lock` registra **locked/unlocking → unlocked/open**.
  Un evento di sblocco `lock` è una prova di azionamento, **non** una
  conferma che il cancello sia effettivamente aperto. Le transizioni
  `unknown`/`unavailable` non producono ingressi fisici.
- Nessuna modifica alle regole FSM di iPhone, Watch, zaini o al calcolo
  dell'aggregato. L'integrazione non apre cancelli, non chiama servizi
  `alarm_control_panel` e non scrive gli helper YAML.

## Aggiornamento dalla RC4

Aggiornare tramite HACS alla v0.1.0rc5 e riavviare Home Assistant.
Se la versione precedente è ancora nella cache, usare **Aggiorna informazioni**.

Controllare **Impostazioni → Dispositivi e servizi → Presenza famiglia →
Dispositivi**: dovrebbero comparire Famiglia, Paolo, Cristina, Giulia,
Arianna (o i membri effettivamente configurati).
La distribuzione dei dispositivi avviene mantenendo i vecchi
`unique_id`; gli `entity_id` già registrati potrebbero ancora contenere
`shadow`. Il nome visualizzato non li rinomina.

Per assegnare identificativi leggibili nelle dashboard e automazioni,
rinominarli nella pagina **Entità** di Home Assistant, verificando prima che
nessuna automazione esistente faccia riferimento agli ID da modificare.
Non è necessario cancellare la configurazione esistente per ottenere
il raggruppamento in dispositivi virtuali.

Per scegliere il cancello `lock`: **Riconfigura → Sorgenti condivise →
Eventi cancelli**, scegliere l'entità `lock.cancello_...`.
Se il `lock` non segnala realmente lo sblocco o rimane sempre unlocked,
preferire lo switch Shelly che segnala l'impulso.

## Verifiche necessarie sul tuo impianto

1. Verificare gli stati delle quattro persone e il loro motivo.
2. Controllare la registrazione degli eventi cancello via `lock` durante
   transizioni reali e confrontarli con la BLE Watch.
3. Leggere gli `entity_id` effettivi dal registro prima di modificare
   le automazioni e le dashboard.
4. Migrare in una finestra presidiata i consumer YAML dell'allarme secondo
   `docs/rc2-migrazione-it.md`, disabilitando i vecchi writer.

Il CI non sostituisce il collaudo reale dei sensori della casa.
