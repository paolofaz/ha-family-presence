# Family Presence v0.1.0rc8 — ultimi eventi accessi

Release normale Latest via HACS, con lo stesso archivio
`family_presence.zip` piatto della RC7.

## Novità: una sola entità diagnostica sotto Casa

La nuova entità `Ultimi eventi accessi` registra solo le transizioni
fisiche già riconosciute dalla FSM:

| Attributo | Significato |
| --- | --- |
| `cancelli` | Ultimo azionamento per **ciascun** `entity_id` del cancello configurato |
| `porta_aperta` | Ultimo passaggio OFF→ON del contatto porta |
| `porta_chiusa` | Ultimo passaggio ON→OFF del contatto porta |
| `serratura_sbloccata` | Ultimo evento di sblocco del lock principale |
| `serratura_bloccata` | Ultimo evento di blocco del lock principale |
| `ultimo_evento_alle` | Timestamp completo dell'evento più recente |
| `ultima_sorgente` | `entity_id` della sorgente dell'ultimo evento |

Il valore del sensore è il tipo dell'ultimo evento: `Cancello azionato`,
`Porta aperta`, `Porta chiusa`, `Serratura sbloccata`, `Serratura bloccata`
oppure `Nessun evento` fino alla prima rilevazione.

I timestamp sono stringhe ISO 8601 con fuso orario. Quando ancora non è
stato registrato un evento, gli attributi hanno valore `null`.
Gli ID reali delle sorgenti servono a distinguere cancelletto, carrabile e
altri eventuali ingressi senza inventare uno stato di apertura/chiusura.

**Attenzione:** per i cancelli che utilizzano `switch` viene osservato
l'impulso OFF→ON; se si utilizza `lock`, l'evento è lo sblocco. Non
significa che il cancello si sia realmente aperto, e non viene inferita
la sua chiusura. Lo stato fisico corrente va letto dagli originali
`switch`, `binary_sensor` e `lock` di Home Assistant.

## Persistenza e sicurezza

Gli eventi visibili sono memorizzati in uno Store separato dalla snapshot
della FSM e recuperati al riavvio. I timestamp utilizzati dal motore
per correlare Watch, porta, cancello e serratura rimangono **solo in RAM** e
sono azzerati a ogni avvio. Gli eventi storici recuperati **non possono
mai determinare una presenza falsa**.

Non sono presenti timer o aggiornamenti al secondo: l'entità viene
aggiornata solo in risposta a un vero evento valido nuovo.
Gli eventi duplicati, fuori ordine, recuperi da
`unknown`/`unavailable`, o modifiche dei soli attributi delle
sorgenti non generano scritture inutili. Se si riconfigura una sorgente,
lo storico precedente relativo a sorgenti eliminate viene escluso.

## Cosa resta invariato

- Un dispositivo virtuale `Casa`, con le quattro presenze individuali,
  `Casa certamente vuota`, i pulsanti e la diagnostica generale.
- L'attributo `bag_return_eligible` resta **presente e invariato** nelle
  entità delle persone con lo zaino.
- Le regole della FSM, gli `unique_id` delle entità esistenti e le
  configurazioni dell'allarme non cambiano.
- Nessun comando a serrature, porte, cancelli o allarme: la nuova entità
  è rigorosamente di sola lettura.

Aggiornare tramite HACS e riavviare Home Assistant: non è necessaria
alcuna riconfigurazione. Gli orari storici precedenti alla RC8 non
possono essere ricostruiti retroattivamente dalla FSM.
