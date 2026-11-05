# Architettura Family Presence v1.0.1

La FSM è composta da livelli senza cicli di retroazione:

1. **Sorgenti HA**: `device_tracker` (iPhone), `binary_sensor` Watch e
   zaini BLE, eventi di `switch`/`binary_sensor`/`lock` per gli accessi,
   allarme (solo come indizio di uscita).
2. **`sources.py`**: traduce soltanto transizioni reali, filtra
   `unknown`/`unavailable`, legge `last_seen_before_off` e rifiuta
   eventi sintetici post-boot.
3. **`coordinator.py`**: cronologia di segnali fisici a breve termine
   **solo in RAM**, finestre temporali, lock per persona,
   revisione di eventi accodati, causa dell'uscita zaino,
   decisioni, origini e persistenza della snapshot.
4. **`fsm.py`**: regole pure sui tre stati. Non dipende da Home Assistant,
   né da servizi che attuano comandi.
5. **`sensor.py`, `binary_sensor.py`, `button.py`**: presentazione
   dei risultati, con `unique_id` stabili; nessuna automazione comandata.
6. **`access_history.py`**: timestamp persistenti degli ultimi eventi
   per dispositivo fisico, **isolati** dalle prove usate dalla FSM.
7. **`diagnostics.py` / `diagnostic_data.py`**: esportazione opt-in
   privata dei motivi, degli stati e degli eventi, senza ID personali.

## Stato e aggregato

Ogni persona ha `home`, `away` o `near_home`. Stato non determinato
e `near_home` non contribuiscono alla certezza «tutti fuori».
`Casa certamente vuota` è ON solo se **tutti** gli stati sono `away`.

`near_home` è una rilevazione Watch non ancora confermata. Non ha
timeout di scadenza verso `away`. Un'apertura di accesso condiviso
successiva conferma HOME solo se `near_home_entered_at` è noto,
se il Watch è ON e se l'età della rilevazione è compresa fra
0 e `near_home_entry_seconds` inclusi. Uno stato `near_home`
ripristinato non ha un timestamp di rilevamento Watch affidabile,
perciò non può essere risolto dal solo evento fisico.

Il Watch ON mentre la persona è AWAY può invece correlare
con un evento fisico recente entro le finestre `entry_*_seconds`.
Le aperture comuni non individuano la persona; anche con finestre
temporali questo resta un limite di affidabilità dei dati.

## Evidenza Watch OFF

Quando il Watch diventa OFF, l'uscita da HOME è condizionata a
iPhone fuori casa, oppure a cancello/porta chiusa/lock bloccato
entro le finestre configurate rispetto a `last_seen_before_off`,
oppure allarme inserito (`armed_away`).
Il timestamp del trigger di OFF non viene sostituito arbitrariamente
a `last_seen_before_off` se quest'ultimo è sconosciuto.

## Zaino

Una transizione ON→OFF dentro la fascia e i giorni configurati
può stabilire AWAY se non già AWAY. Una transizione OFF→ON
può riportare HOME solo se `bag_return_eligible` è stato
acquisito con quell'uscita ed è ancora valido.
In v1.0.1, quando `bag_return_eligible` è attivo,
Watch ON e PHYSICAL_ENTRY non possono stabilire NEAR_HOME/HOME:
si evita che un Watch lasciato a casa e un accesso condiviso
sovrascrivano la partenza dello zaino. Il bag flag non è un blocco
assoluto: un ingresso iPhone valido o una correzione manuale
possono revocarlo. Il bag OFF in sé non è un veto: conta soltanto
la partenza effettivamente riconosciuta e ancora autorevole.

## Salvataggi

Lo Store `family_presence_shadow.<entry_id>` contiene
snapshot **format 5**, con source fingerprint, stati, motivi,
tempi di cambio, provenance zaino, ultimi eventi ignorati.
Non cambia formato nella v1.0. Il fingerprint delle sorgenti
resta distinto dal calendario dello zaino.

La FSM distingue due canali di notifica:
- **UI listeners** per tutte le variazioni diagnostiche;
- **persistence listeners** solo per le decisioni applicate.

I pulsanti manuali salvano inoltre immediatamente.
All'unload il dato corrente viene salvato esplicitamente.
Gli eventi scartati non chiedono salvataggi frequenti;
possono perdersi dopo un crash prima della prossima decisione
accettata, ma ciò **non cambia i tre stati FSM**.

Lo Store indipendente `family_presence_access_events.<entry_id>`
conserva il quadro degli ultimi eventi per entità fisica.
I dati ripristinati servono solo alla UI: `_physical`
riparte vuoto ed è l'unica fonte temporale delle decisioni Watch.

## Riavvio e confidenza

Gli snapshot precedenti che riportano NEAR_HOME con
`bag_return_eligible = true` vengono convertiti una sola volta
al ripristino in AWAY, mantenendo il flag. Non vengono fabbricati
eventi Watch/porta; la conversione può cambiare l'aggregato
e richiede quindi attenzione alle automazioni dell'allarme.

Uno stato ripristinato, anche AWAY, conta come il suo valore
per retrocompatibilità con le automazioni dell'utente.
`restored_from_storage` resta vero finché un evento successivo
non viene effettivamente applicato: il sensore di diagnostica
espone allora `restored_unverified_members`, senza cambiare
lo stato o creare un rientro sintetico.

Dopo un riavvio la FSM non garantisce che l'occupazione reale
coincida con quella salvata. Il report diagnostico consente
di riconoscere l'incertezza e intervenire consapevolmente.

## Privilegi e responsabilità

Questa integrazione legge fonti HA e pubblica sensori/pulsanti.
Non chiama servizi di allarme, cancello, lock o riscaldamento.
Le automazioni YAML o UI restano componenti indipendenti,
responsabili delle azioni e delle condizioni di sicurezza.

I nomi interni come `ShadowCoordinator` e alcuni vecchi
`unique_id` con suffisso `shadow` rimangono intenzionalmente
per compatibilità: non indicano un motore parallelo ancora in uso.
