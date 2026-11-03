# Family Presence Beta 1 — collaudo completo (versione 0.1.0b1)

Questa beta **rimane in modalità ombra**. Il motore YAML esistente resta
l'unico a comandare l'allarme, il riscaldamento, le notifiche e i suoi
`input_select`. Non sostituire ora le entità nelle automazioni.

## Installazione e configurazione

1. Fai un backup completo di Home Assistant o almeno della configurazione,
   incluse le impostazioni dell'integrazione e lo storage.
2. Da HACS installa/aggiorna **Family Presence** alla **beta 0.1.0b1**.
   Se non appare, verifica che siano abilitate le versioni prerelease/beta
   per questo repository personalizzato. Poi riavvia Home Assistant.
3. In **Dispositivi e servizi → Family Presence → Riconfigura → Sensori condivisi**
   puoi configurare facoltativamente il confronto diretto con
   `binary_sensor.casa_certamente_vuota`. È una **sola lettura**.
   Non toccare i quattro vecchi riferimenti `input_select.presenza_*`
   già associati alle persone.
4. Nel primo riavvio da Alpha 5 non cambiare contemporaneamente le fasce
   degli zaini: la conversione del vecchio snapshot avviene al primo
   caricamento valido. Fai le modifiche degli orari soltanto dopo aver
   verificato che i quattro stati sono stati ripristinati.
5. Cerca in **Stati** queste entità con i loro nomi (gli `entity_id` possono
   differire se Home Assistant li ha personalizzati):
   - `Family Presence Shadow Paolo`
   - `Family Presence Shadow Cristina`
   - `Family Presence Shadow Giulia`
   - `Family Presence Shadow Arianna`
   - `Family Presence Shadow - Casa certamente vuota` (binary sensor)
   - `Family Presence Shadow - Diagnostica casa` (sensor)
   - I pulsanti `Forza a casa` / `Forza fuori casa` di ogni persona

## Verifiche di comportamento

| Prova | Risultato atteso |
| --- | --- |
| Tutti i quattro stati `away` | Il **binario Shadow** è `on` |
| Anche un solo `home` o `near_home` | Il **binario Shadow** è `off` |
| Stato persona non inizializzato `unknown` | Il **binario Shadow** è `off` |
| Forza `away` sull'ultima persona `home` | Shadow binario passa immediatamente `on` |
| Forza `home` con gli altri `away` | Shadow binario passa immediatamente `off` |
| Riavvio con tutti `away` memorizzati | Restano `away`; Shadow binario `on` |
| Uscita con solo Apple Watch | Transizione come nel YAML; registrata in `recent_events` |
| Zaino Giulia/Arianna `on → off` feriali 07:00–09:10 | `away` (fascia configurata) |
| Zaino `on → off` fuori fascia | Presenza invariata; `last_ignored_reason` spiega perché |
| Zaino `off → on`, qualsiasi ora | `home` |
| Ripristino del sensore zaino `unavailable → on` | Nessun falso rientro |
| Semplice modifica della fascia zaino + ricarica integrazione | Stato persona invariato |
| Sorgenti `unknown/unavailable` | Nessuna transizione inventata |
| Evento automatico valido successivo alla forzatura | Può sostituire lo stato forzato |
| Stato iPhone/Watch discordante da forzatura `away` | Avviso diagnostico, **senza veto** al binario Shadow |

I pulsanti manuali della beta **non cambiano** il vero YAML, quindi
una differenza dopo una forzatura è **attesa**, non è automaticamente un bug.

## Come interpretare il confronto

Apri gli attributi del binario Shadow:

- `legacy_comparison_status`: `aligned`, `member_divergence`,
  `aggregate_divergence`, `not_configured`,
  `reference_unavailable`.
- `legacy_expected_all_away`: risultato calcolato con i vecchi quattro
  `input_select`. Questo NON è un valore letto dal sensore binario reale.
- `actual_legacy_state`: valore **reale** letto dal
  `binary_sensor.casa_certamente_vuota` se lo hai associato.
- `actual_legacy_matches_expected`: dice se il sensore YAML reale concorda
  con il template ricostruito dai vecchi quattro input_select.
- `actual_legacy_matches_shadow`: confronto diretto binario YAML/Shadow.
- `legacy_differing_members`: nomi delle persone per cui gli stati differiscono.
- `legacy_divergence_since`: da quando la divergenza è osservata durante
  l'attuale sessione dell'integrazione.
- `source_warnings`: sensori raw discordanti/non disponibili, solo diagnostici.

**Nota:** dopo una forzatura Shadow è normale vedere divergenze con il
vecchio YAML. Il vecchio motore non riceve la forzatura.

## Protocollo veloce per domani

1. **Mattina**: annota stato iniziale e verifica le uscite reali delle ragazze
   con gli zaini (fascia feriale) e il Watch.
2. **Durante il giorno**: osserva se qualcuno resta `near_home`, se
   compaiono eventi ignorati o se sorgenti recuperano da `unavailable`.
3. **Rientri**: controlla zaini `off → on` e arrivi iPhone/Watch.
4. **Test manuali**: imposta i quattro Shadow su `away` uno alla volta;
   verifica `on` solo sull'ultimo. Forza uno `home`; verifica `off`.
   **Non tentare questa prova sul vecchio YAML o sull'allarme.**
5. **Riavvio**: salva screenshot degli stati, riavvia, verifica che restino
   invariati. Poi verifica che le nuove transizioni automatiche funzionino.
6. **Fine test**: riporta manualmente gli Shadow a valori coerenti con la
   situazione reale se le prove li hanno alterati, senza cambiare il YAML.

Segnala ogni anomalia con persona, orario, stato vecchio, stato Shadow,
`reason`, `last_ignored_reason`, `recent_events`, valori dei
sensori fisici e stato dell'allarme.

## Passaggio definitivo — NON eseguire con la beta

Dopo il collaudo: confermare i risultati, sostituire gli output Shadow con
entità definitive mantenendo gli **unique_id** stabili dove possibile,
spostare le automazioni indipendenti su quelle entità, disattivare i soli
writer YAML della vecchia FSM e verificare il rollback. Il tutto senza
doppie scritture né collegamenti prematuri all'allarme.

Un passaggio definitivo non può consistere nella sola rimozione della
parola *Shadow* dai nomi: occorre testare e aggiornare i riferimenti delle
automazioni YAML (soprattutto `familyuscita` e `familyrientro`).
