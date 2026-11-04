# Zaino — comportamento condizionato all'uscita (RC6)

La FSM registra eventi reali dallo zaino BLE, senza dedurre movimenti
dalla sola presenza persistente del sensore. Il motore non accende o spegne
l'allarme direttamente: le automazioni esterne possono però usare lo stato HOME.

## Uscita

Uno zaino che passa **ON → OFF** imposta la persona su **AWAY** se:

- Lo zaino è abilitato.
- L'evento avviene nel giorno e nella fascia configurati (ora locale HA).
- La persona **non è già AWAY**: un'uscita dello zaino non deve sovrascrivere
  un'assenza precedentemente confermata da iPhone o Watch.

Se lo zaino provoca davvero AWAY, la FSM registra per quella persona un
indicatore causale `bag_return_eligible = true`. Non è un blocco manuale:
un successivo evento valido di iPhone, Watch o una correzione manuale può
aggiornare normalmente lo stato e togliere il diritto di rientro allo zaino.

## Rientro

Il passaggio **OFF → ON** può impostare **HOME**, a qualsiasi ora, soltanto
se lo zaino è abilitato, il passaggio è fisicamente valido e:

1. La persona è `AWAY` oppure `NEAR_HOME`.
2. L'uscita che ha determinato l'assenza è stata un `BAG_LEFT` valido.
3. Nessun successivo evento autorevole ha sostituito la causa dell'assenza.

La FSM non confronta testi tradotti come `"Zaino uscito"`, ma un
flag di provenienza aggiornato dagli eventi. Un nuovo iPhone AWAY quando
lo stato era già AWAY revoca comunque il diritto dello zaino di marcare HOME.

**Caso NEAR_HOME:** se il Watch è stato rilevato e ha portato la persona da
AWAY (zaino) a NEAR_HOME senza confermare il rientro, la successiva rilevazione
dello zaino può confermare HOME. Se invece il Watch si perde nuovamente,
la FSM torna AWAY e revoca quel diritto.

**Forzatura manuale AWAY:** non autorizza il rientro dello zaino. Una
correzione manuale non può essere annullata da una semplice riconnessione BLE
dello zaino. Un successivo iPhone HOME o Watch con evidenze fisiche valide
può invece marcare HOME.

**HOME già confermato:** un altro evento ON dello zaino viene ignorato,
senza riscrivere motivo e data dell'ultimo cambio di presenza.

## Riavvii e aggiornamento da RC5

Il flag viene salvato nella snapshot della FSM assieme allo stato, usando
un campo opzionale del formato 5. Dopo un riavvio RC6, una partenza causata
dallo zaino conserva il diritto di rientro anche da NEAR_HOME.

Le snapshot RC5 non contengono il flag. Per prudenza, dopo il **primo**
aggiornamento, una persona già AWAY per lo zaino non viene automaticamente
riportata a HOME dal solo zaino ON: per quella situazione eccezionale serve
un normale evento di iPhone/Watch o un intervento manuale. Dopo una nuova
uscita reale dello zaino, il ciclo torna completamente automatico.

Un recupero `unavailable → on` o `unknown → on` non è un vero OFF → ON:
l'adapter continua a ignorarlo. Lo zaino OFF permanente non impedisce agli
altri sensori di determinare un rientro.

## Configurazione e orari

Ogni persona ha `enabled`, `start`, `end`, `days`:

- 07:00–09:10, lun–ven: finestra scolastica predefinita.
- 00:00–00:00, tutti i giorni: uscita consentita 24h.
- 22:00–02:00 il lunedì: comprende il martedì fino alle 01:59.
- `enabled = false`: ignora sia ON → OFF che OFF → ON.

I timeout di assenza BLE sono configurati nel sensore sorgente, non
nell'integrazione Family Presence.

I vecchi codici `always` e `legacy` restano solo compatibilità interna:
non ci sono due modalità di precedenza della presenza.

## Collaudo consigliato

Verificare almeno un'uscita vera nella fascia configurata e il successivo
rientro, una disconnessione BLE dello zaino mentre iPhone segnala AWAY,
il percorso AWAY → NEAR_HOME → HOME e il riavvio di HA dopo BAG_LEFT.
L'attributo `bag_return_eligible` del sensore individuale mostra il valore
attuale della condizione.
