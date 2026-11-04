# Passaggio di contesto — Progetto Presenza famiglia (RC1)

**Repository:** https://github.com/paolofaz/ha-family-presence
**Sviluppo attuale:** `release/0.1.0rc1` → draft PR #12 verso `main`
**Ultima versione installata/testata:** Beta 1 `v0.1.0b1` (in modalità Shadow)
**Branch Beta di riferimento:** `chore/hacs-ready-foundation`
**`main`:** non promuovere nulla finché RC1 non è collaudata.

## Architettura concordata

La FSM nativa Python è responsabile delle presenze individuali
`home`, `near_home`, `away` e del loro aggregato.
Watch BLE, iPhone, zaini Giulia/Arianna e porta/cancelletto/serratura
sono le sorgenti di eventi. Il BLE resta nei provider esistenti.

**Regola inderogabile:** Casa certamente vuota è **ON se e solo se tutti
i componenti configurati sono AWAY**. Le forzature manuali e gli AWAY
ripristinati dalla memoria contano come AWAY; qualsiasi HOME, NEAR_HOME,
UNKNOWN rende OFF. Una forzatura manuale prevale sul passato ma può essere
sostituita da un nuovo evento automatico valido.

La Beta 1 rimane **solo Shadow**. Il vecchio package YAML è ancora
l'unico a comandare allarme, serrature, riscaldamento e notifiche.
La nuova integrazione non chiama quei servizi.

## Esiti osservati sul campo (4 novembre 2026)

- Uscite degli zaini: Giulia 07:36, Arianna 07:37 locali, `away` in
  entrambe le FSM, motivazione coerente con la fascia configurata.
- Cristina è passata AWAY tramite iPhone; anche Paolo AWAY via iPhone
  alle 08:15. Quattro membri AWAY, vecchio e nuovo aggregato ON.
- Riavvio Home Assistant: stati recuperati dallo storage e confronto
  riallineato. Origine `saved_shadow_unverified` segnala ripristino,
  **non** cambia la regola all-away.
- Parità vecchio YAML/nuovo Python osservata in dashboard. Collegamento
  opzionale al vero `binary_sensor.casa_certamente_vuota` attivato;
  `actual_legacy_matches_expected` conferma il template.
- Test ancora da completare: rientri reali, in particolare zaini;
  Watch-only; allarme dopo cutover.

## Codice esistente e validato nella Beta 1

Gestione eventi FSM e zaini per giorni/orari, pulsanti manuali,
snapshot format 5, motivo e provenienza stato, ultimi 12 eventi,
`binary_sensor` aggregato Shadow, parità membri e aggregato con
vecchio YAML, lettura opzionale dell'aggregato reale, diagnostica
eventi ignorati. Alla pubblicazione Beta 1: 149 test Python,
hassfest e HACS validati.

## Sviluppo RC1 avviato

- `presentation.py`: nomi di output Shadow e futuri definitivi,
  con **unique_id invariati** per preservare il registro Home Assistant.
  L'esecuzione corrente rimane hard-locked su Shadow.
- `activation_contract.py`: specifica pura delle condizioni di
  `familyuscita`, `familyrientro` e dell'avviso porta;
  nessun comando reale sull'allarme.
- Test di regressione per nomi/unique_id e condizioni dell'allarme.
- `docs/cutover-plan-it.md`: procedura di migrazione e rollback.

**Scoperta cruciale:** `presenza_evento_fisico` del vecchio YAML
non è soltanto diagnostica. Su certe correlazioni scrive anche
`input_select.presenza_*`. Durante il cutover va disabilitata
o suddivisa in versione solo registrazione timestamp, senza writer.

## Passaggio finale (non attuato)

Il piano prevede: backup, revisione degli entity_id reali (il cambio
display name non rinomina entity_id), ritiro dei writer della FSM YAML,
collegamento in un intervento unico degli output Python alle automazioni
indipendenti e rollback verificato. È fondamentale evitare due writer
della presenza e `_2` nel registro entità per Casa certamente vuota.

**Per una nuova chat del progetto:** aprire subito questo documento,
leggere PR #12 e lo stato del branch prima di cambiare codice. Non
dedurre che una PR draft sia una release RC installabile.

## Aggiornamento sviluppo RC1 (nuova sessione, 4 novembre 2026)

Il branch ha ora il modulo `operational.py` per controllare la presenza
nel registro HA degli output di ogni membro e dell'aggregato, e
`output_profile` con default Shadow. Configura offre conferme testuali
ATTIVA/OMBRA; gli output di persona/aggregato/pulsanti mantengono gli
unique_id e usano metadati Final solo se espressamente attivati.
Il ritorno a Shadow non scollega i consumer YAML: il runbook descrive il
rollback *completo*, che include la riconnessione ai vecchi helper.
Le modifiche a persone, sorgenti e fasce vengono bloccate mentre Final è
attivo. Non vengono introdotti comandi diretti all'allarme.

**Stato operativo invariato:** Beta 1 su HA, YAML legacy attivo; RC1 su
branch development-only. Nessuna installazione/cutover/merge/tag.
La pubblicazione come prerelease richiede conferma del CI aggiornato e
completamento del collaudo sul campo. Vedere
`docs/rc1-operational-runbook-it.md`.
