# Family Presence — Home Assistant

Integrazione Python per la gestione familiare della presenza tramite una
macchina a stati finiti (FSM) indipendente per ogni persona. Gli stati pubblici
sono `home`, `near_home`, `away`. L'integrazione produce informazioni di
presenza: non comanda allarme, serrature, cancello o riscaldamento.

> **Latest: v0.1.0rc7.** La release ufficiale conserva il packaging HACS
> collaudato dalla RC4: manifest alla radice del repository,
> `hacs.json` con `content_in_root: true` e `zip_release: true`,
> archivio piatto `family_presence.zip`.
> [Note RC7](docs/rc7-release-it.md).

## Entità

Tutte le entità sono raccolte sotto il dispositivo virtuale **Casa**.
Ogni persona ha un sensore autonomo `Presenza [nome]` con stato
`home` / `near_home` / `away` e due pulsanti di forzatura.

### Attributi essenziali dalla RC7

| Entità | Attributi esposti in produzione |
| --- | --- |
| Sensore presenza (senza zaino) | `reason`, `last_transition` |
| Sensore presenza (con zaino) | `reason`, `last_transition`, `bag_return_eligible` |
| `Casa certamente vuota` | Nessun attributo extra: il valore è `on` / `off` |
| `Diagnostica presenza` | Solo `source_warnings` quando ci sono anomalie |

Il motivo `reason` è presentato in italiano. `last_transition` è il
timestamp ISO della **transizione di stato**, non un contatore che aumenta
con il passare del tempo. Può essere `null` quando non è ancora nota una
transizione verificata. `bag_return_eligible` compare solo per chi ha uno
zaino e vale `true` se il suo prossimo evento zaino OFF→ON può confermare
il rientro dopo un'uscita causata proprio dallo zaino.

**Anti-spam Recorder:** ogni entità confronta il valore e gli attributi
pubblici con l'ultima rappresentazione inviata. Notifiche interne, input
BLE cambiati senza transizione, eventi scartati e aggiornamenti della
diagnostica non generano una riscrittura del sensore personale o
dell'aggregato se non cambia nulla di visibile.

Gli eventi dettagliati e i relativi contatori restano nella memoria della
FSM per la gestione interna e nei suoi snapshot, ma non sono attributi
pubblici che fanno crescere inutilmente la cronologia.

## Logica essenziale

- Un iPhone entra/esce dalla zona casa e può determinare `home` / `away`.
- Il Watch BLE, correlato a eventi di porta/serratura/cancello, determina
  entrate e uscite. Se è rilevato vicino casa senza conferme fisiche, può
  impostare `near_home`, che **non significa `home`**.
- Un evento cancello accetta `switch`, `binary_sensor` o `lock`. Un
  `lock` conta come evento di sblocco, non come prova di apertura fisica.
- Lo zaino ON→OFF causa `away` solo nella fascia/giorni configurati e
  se la persona non era già `away`. Il suo OFF→ON conferma `home`
  a qualunque ora solo se l'uscita che determinò `away` proveniva
  dallo zaino, anche attraverso un `near_home` provvisorio.
  Una forzatura manuale `away` non è annullata dal solo zaino ON.
- `Casa certamente vuota` è `on` **solo se tutte** le persone
  configurate sono `away`. Una persona `near_home` lo porta a `off`.
  Le automazioni dell'allarme devono però richiedere `home` per un
  eventuale disinserimento.
- Stati e provenienza dello zaino vengono salvati e recuperati con
  snapshot interne (formato 5). Non si sintetizzano eventi dal riavvio.

## Configurazione e migrazione

Da Home Assistant: Impostazioni → Dispositivi e servizi → Family Presence.
Nelle opzioni si configurano i tempi di correlazione e, per ogni zaino,
finestra oraria, giorni e abilitazione.

L'integrazione non scrive i vecchi `input_select`, `input_datetime` o
gli helper YAML. Se si proviene dal precedente motore YAML, verificare che
**non rimangano due FSM che gestiscono la presenza contemporaneamente**.
Aggiornare separatamente le automazioni che comandano l'allarme,
usando gli `entity_id` effettivi del registro di Home Assistant.

Gli `unique_id` delle entità non sono cambiati fra Beta e RC7.
Pertanto un `entity_id` salvato in passato può contenere ancora `shadow`,
anche se l'entità pubblica è ormai definitiva: rinominarlo solo dopo aver
verificato tutti i riferimenti nelle automazioni e nella dashboard.

## Documentazione

- [Regola dello zaino](docs/bag-policy.md)
- [RC7: attributi e prevenzione scritture](docs/rc7-release-it.md)
- [Architettura e snapshot](docs/architecture.md)
- [Migrazione dei consumer YAML](docs/rc2-migrazione-it.md)

I documenti e i test dedicati alle Beta e alle RC precedenti restano nel
repository come riferimento storico; la versione attiva è descritta qui.
