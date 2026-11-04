# Family Presence v0.1.0rc2 — Prerelease di collaudo operativo

RC2 introduce gli output definitivi della FSM Python. L'aggiornamento dalla
Beta 1 conserva gli unique_id e gli snapshot della FSM; gli entity_id già
registrati su Home Assistant normalmente restano invariati.

## Novità

- Profilo Final attivo fin dall'installazione: niente attivazione manuale.
- Nomi definitivi distinguibili dai vecchi template: "Presenza famiglia Paolo"
  e "Presenza famiglia - Casa certamente vuota" (per tutti i membri).
- Sensori di presenza con stato grezzo home / near_home / away.
- Aggregato binario rigoroso: on solo quando TUTTI i membri sono away,
  compresi stati forzati o ripristinati; home, near_home e unknown => off.
- Pulsanti per forzare una transizione nella FSM: le rilevazioni successive
  valide possono sovrascriverla.
- Tutte le configurazioni delle sorgenti, finestre temporali e fasce zaino
  rimangono accessibili.
- Fino a prova contraria, il controllo dei dispositivi rimane esterno in YAML.

## Installazione / aggiornamento

Selezionare esplicitamente la prerelease v0.1.0rc2 in HACS se disponibile,
oppure installare il codice della release dalla pagina GitHub. Riavviare HA
secondo la procedura HACS e verificare tutti gli output.

Non modificare le vecchie automazioni durante il solo aggiornamento:
l'integrazione non scrive gli input_select storici e non chiama i servizi
di allarme, serratura e riscaldamento. Per collegare la casa ai nuovi output,
seguire docs/rc2-migrazione-it.md.

## Attenzione agli entity_id

La visualizzazione cambia ma il registro HA potrebbe mantenere gli ID Shadow
della Beta 1. Leggere i veri entity_id dal registro prima di modificare YAML
o dashboard. Se la RC2 viene installata ex novo, i nomi di visualizzazione
suggeriscono gli slug sensor.presenza_famiglia_NOME e
binary_sensor.presenza_famiglia_casa_certamente_vuota, non garantiti.

## Stato di rilascio

Prerelease di collaudo; non sostituisce la verifica degli eventi reali,
del corretto arm/disarm dell'allarme e della migrazione dei consumer YAML.
