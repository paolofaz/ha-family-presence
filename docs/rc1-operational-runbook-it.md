# RC1 — Attivazione controllata e rollback (NON eseguire con Beta 1)

Questa procedura è preparata per **dopo la pubblicazione della RC1** e
solo dopo l'approvazione del collaudo. Il branch di sviluppo non è una release
installabile. Nessuna operazione è stata eseguita nella tua istanza HA.

## Contratto tecnico implementato

- Assenza dell'opzione `output_profile` = **shadow** (compatibile Beta 1).
- `Configure → Attivazione / ritorno a Shadow (RC1)` espone un controllo di
  registro per le presenze individuali e l'aggregato. Richiede che tutte le
  entità siano registrate e non disabilitate, e che il binario nuovo non sia
  configurato come riferimento legacy.
- Per passare a `final` occorre digitare **ATTIVA**. Per tornare a `shadow`
  occorre digitare **OMBRA**. Entrambi ricaricano l'integrazione.
- I **unique_id** sono identici tra Shadow e Final. Gli **entity_id** reali
  rimangono quelli di Home Assistant: NON vengono rinominati automaticamente.
  Il profilo modifica nomi suggeriti, categoria e metadati.
- Il profilo Final **non inserisce/disinserisce l'allarme**, non scrive ai vecchi
  `input_select` e non modifica il package YAML.
- In Final le modifiche alle sorgenti/persone/fasce sono bloccate dal
  configuratore per limitare cambi involontari alla FSM operativa.
- L'aggregato continua a essere ON se e solo se TUTTI i membri sono AWAY,
  compresi AWAY manuali e ripristinati. HOME, NEAR_HOME e UNKNOWN ⇒ OFF.
- **Limite importante:** il controllo del registro non prova che gli
  automi YAML siano disabilitati, che il backup esista o che gli attuatori
  siano sicuri. La persona che esegue il cutover deve verificarli.
- **Altro limite:** tornare a Shadow non disconnette automaticamente eventuali
  automazioni YAML già puntate alle nuove entità. Il rollback completo richiede
  la procedura YAML sottostante. In Shadow i sensori rimangono leggibili per
  confronto, come nella Beta 1.

## Preflight prima di qualsiasi attivazione

1. Finire i test reali della Beta 1: entrambi i rientri degli zaini,
   rientri Watch-only, eventi porta/cancello, riavvio e casi near_home.
2. Backup HA completo, esportazione del vecchio package privato, screenshot
   delle impostazioni Family Presence e del registro entità.
3. Registrare in una tabella esterna e privata, per ciascun membro:
   `person_id`, `unique_id`, `entity_id` Shadow effettivo, sensore
   YAML di confronto e stato. Registrare anche l'`entity_id` effettivo
   del nuovo `binary_sensor` aggregato e quello del vecchio template.
4. Verificare parità persone e aggregato (esclusi test manuali deliberati):
   `legacy_comparison_status`, `actual_legacy_matches_expected`,
   `actual_legacy_matches_shadow`. Risolvere divergenze prima dell'uso.
5. Individuare le automazioni YAML *con nomi/ID reali* e ogni altro
   consumatore, anche dashboard, script e scene. Una ricerca solo del nome
   "Casa certamente vuota" non è sufficiente.
6. Avere a disposizione accesso amministratore e possibilità di ripristinare
   il backup anche se l'allarme non è raggiungibile.

## Cutover operativo — una sola finestra di manutenzione supervisionata

Non è un'operazione da compiere automaticamente all'installazione.

1. Disabilitare TEMPORANEAMENTE le automazioni attuatrici dipendenti dalla
   presenza: `familyuscita`, `familyrientro` e
   `presenza_avviso_casa_vuota_porta_non_locked`. Annotarne lo stato.
   `notificacristinalavoroout` è indipendente e non va modificata.
2. Disabilitare INSIEME tutti i writer della vecchia FSM:
   `presenza_uscita_watch`, `presenza_watch_rilevato`,
   `presenza_watch_allontanato_near_home`, `presenza_uscita_iphone`,
   `presenza_rientro_iphone`, `presenza_zaini_figlie` e
   **`presenza_evento_fisico`**. Quest'ultima scrive anche HOME sui
   vecchi `input_select`; non è solo un registro dei timestamp.
3. In Family Presence → Configura → Attivazione RC1, leggere il preflight,
   verificare che i suoi riferimenti corrispondano alla tabella e digitare
   **ATTIVA**. Controllare `mode: final` e `cutover_active: true` nei
   nuovi output; se il controllo fallisce, FERMARSI e restare in Shadow.
4. Leggere di nuovo gli **entity_id effettivi** dal registro. Non confondere
   `name` con `entity_id`. È possibile usare gli ID esistenti che
   contengono `shadow`: sono comunque gli output finali dopo l'attivazione.
   L'eventuale recupero del nome `binary_sensor.casa_certamente_vuota`
   richiede prima il ritiro del vecchio template e una rinomina esplicita;
   evitare conflitti e suffissi `_2`. La rinomina NON è necessaria alla
   correttezza se si aggiornano tutti i consumatori.
5. Aggiornare il **package privato**, senza copiarlo nel repository pubblico:
   `familyuscita` legge il nuovo binario e conserva i trigger di
   vuoto/serratura, il controllo lock=locked e alarm=disarmed;
   `familyrientro` legge i nuovi sensori persone (stati grezzi
   `home`, `away`, `near_home`) e disarma solo su
   `away/near_home → home` con allarme `arming/armed_away`;
   l'avviso porta legge il nuovo binario e rivaluta dopo 2 minuti.
   Conservare la notifica riscaldamento e le notifiche indipendenti.
   Usare l'esempio `rc1-yaml-consumers.example.yaml` come traccia, non
   come sostituto pronto all'uso.
6. Disabilitare/rimuovere `presenza_memorizza_ultimo_cambio` quando le
   dashboard usano il `last_transition` della nuova FSM. Lasciare gli
   helper legacy disponibili per un rollback, ma **senza doppia scrittura**.
7. Verificare configurazione e ricaricare le automazioni, poi abilitare solo
   i tre consumatori migrati. Non riabilitare i writer della vecchia FSM.
8. Test supervisionati: tutti AWAY/aggregato ON; un HOME o NEAR_HOME/OFF;
   blocco serratura con casa vuota ⇒ armamento solo se disarmed;
   rientro confermato HOME ⇒ disarmo solo se arming/armed_away;
   nessun disarmo in near_home; 2 minuti porta unlocked ⇒ avviso.
   Provare manual force con particolare attenzione: un force-away può
   contribuire all'inserimento dell'allarme.
9. Verificare riavvio e stato ripristinato. Per una prova con tutti AWAY,
   assicurarsi che sia atteso e supervisionato il comportamento dell'allarme.

## Rollback operativo (non basta digitare OMBRA)

1. DISABILITARE i tre consumatori YAML collegati ai nuovi output, così non
   scattano durante i ripristini. Non supporre che Shadow blocchi i trigger.
2. Ripristinare le precedenti versioni di `familyuscita`,
   `familyrientro` e avviso porta con **vecchi** riferimenti.
   Riconfermare la disponibilità del vecchio
   `binary_sensor.casa_certamente_vuota` e dei quattro helper.
3. Riallineare i vecchi stati alle presenze effettive prima di permettere
   nuovamente un inserimento automatico. Riabilitare in blocco i writer
   legacy originali, incluso `presenza_evento_fisico`.
4. In Family Presence → Configura → Attivazione RC1 digitare **OMBRA**;
   verificare `mode: shadow_only` e i confronti read-only.
5. Ricaricare e riabilitare i tre consumatori nella versione legacy.
   Verificare che ogni comando dell'allarme provenga SOLO dal YAML legacy.
6. Se la procedura di ripristino non è verificabile, lasciare i consumatori
   dipendenti dalla presenza disabilitati fino a un intervento manuale
   supervisionato. Il backup completo rimane l'ultima possibilità di recupero.

## Controlli che restano sul campo

Il CI controlla solo la logica Python, l'identità delle entità e il flusso
di opzioni. Non simula un vero Home Assistant con le specifiche entità
dell'abitazione e non garantisce un cutover automatico. Il passaggio operativo
richiede verifica umana dei riferimenti, eventi reali e rollback completo.
