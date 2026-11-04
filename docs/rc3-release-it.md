# Family Presence v0.1.0rc3 — rilascio Latest installabile da HACS

La RC3 contiene il motore definitivo della RC2, senza modifiche alle
transizioni FSM. L'aggiornamento dalla Beta 1 / RC2 conserva gli unique_id
degli output, le impostazioni e gli snapshot.

## Correzione HACS

- Il branch predefinito **main** contiene ora l'integrazione Python completa,
  anziché lo scheletro iniziale con manifest 0.0.1.
- La release ufficiale usa **zip_release** e l'asset
  `family_presence.zip`, con i file Python e manifest.json **direttamente
  alla radice dello ZIP**: HACS lo estrae nella directory locale
  `/config/custom_components/family_presence/`.
- Manifest e pacchetto hanno entrambi versione `0.1.0rc3`.
- Il CI verifica il contenuto ZIP, i test Python, hassfest e HACS prima
  di pubblicare la release **normale Latest**.
- Una verifica reale in HACS dell'utente resta necessaria: i controlli CI
  non possono osservare lo stato della cache o l'accesso GitHub dell'istanza HA.

## Comportamento operativo

Le persone pubblicano stati home, near_home, away, con motivazioni e
ultimo cambio negli attributi; l'aggregato RC3 va su on soltanto
se tutti sono away. L'integrazione non invoca direttamente servizi di
allarme, serratura o riscaldamento, e non modifica i vecchi input_select.

**Non disabilitare il vecchio YAML finché non sono stati rilevati i reali
entity_id della RC3 e non sono state trascritte le automazioni consumer.**
I nomi nuovi non implicano la rinomina degli entity_id già registrati.

Vedi docs/rc2-migrazione-it.md per la tabella e la procedura di cutover.
