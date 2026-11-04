# Family Presence v0.1.0rc4 — correzione installazione HACS

## Causa tecnica affrontata

Il messaggio di errore HACS era `custom_components/None/manifest.json`.
Nel percorso di aggiornamento di HACS, **prima di scaricare l'asset ZIP**,
l'integrazione individua il manifest nel repository. Senza `content_in_root`,
cerca la prima directory sotto `custom_components` e può ricavare il nome
`None` dall'albero che HACS riceve: la RC3 aveva aggiunto lo ZIP ma lasciato
attivo questo passaggio critico.

La RC4 imposta `content_in_root: true` in `hacs.json` e include un
`manifest.json` alla radice, uguale al manifest dell'integrazione.
HACS legge direttamente `manifest.json` dalla radice e **non** chiama
la ricerca della sottocartella che produceva `None`.

La stessa release fornisce `family_presence.zip`, con file e manifest
direttamente nella radice dell'archivio. `zip_release: true` indica a HACS
di estrarre i file dello ZIP in
`/config/custom_components/family_presence/`.

## Compatibilità e limitazioni

- Nessuna regola di presenza o automazione YAML è stata modificata.
- La versione manifest è `0.1.0rc4`; unique_id e snapshot della FSM invariati.
- La nuova modalità risolve nello specifico il percorso errato del manifest.
  Non può prevenire problemi di rete, download o versioni HACS incompatibili.
- I controlli GitHub verificano che entrambi i manifest siano identici e che
  l'asset ZIP possa essere estratto nella posizione corretta.
- L'effettiva installazione dal HACS dell'utente resta un collaudo a parte.
- Lasciare le vecchie automazioni YAML attive durante la prima verifica RC4.

**Quando HACS non installa RC4**, leggere versione HACS e log precisi prima
di un ulteriore rilascio: non disinstallare la configurazione HA e non
cancellare `.storage/hacs.*`.
