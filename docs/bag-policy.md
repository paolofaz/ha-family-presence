# Zaino — comportamento condizionato all'uscita (v1.0.1)

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
un successivo rientro iPhone valido o una correzione manuale può aggiornare
normalmente lo stato e togliere il diritto di rientro allo zaino.
Il semplice Watch ON e un accesso fisico condiviso **non possono**
sovrascrivere questa uscita mentre il flag resta `true`.

## Rientro

Il passaggio **OFF → ON** può impostare **HOME**, a qualsiasi ora, soltanto
se lo zaino è abilitato, il passaggio è fisicamente valido e:

1. La persona è `AWAY` oppure `NEAR_HOME`.
2. L'uscita che ha determinato l'assenza è stata un `BAG_LEFT` valido.
3. Nessun successivo evento autorevole ha sostituito la causa dell'assenza.

La FSM non confronta testi tradotti come `"Zaino uscito"`, ma un
flag di provenienza aggiornato dagli eventi. Un nuovo iPhone AWAY quando
lo stato era già AWAY revoca comunque il diritto dello zaino di marcare HOME.

**Watch lasciato in casa (correzione v1.0.1):** dopo un'uscita causata
dallo zaino, il Watch lasciato in carica può accendersi anche mentre
la persona è a scuola. Con `bag_return_eligible = true`, Watch ON e
gli ingressi condivisi non possono passare a NEAR_HOME o HOME. Rimane AWAY.
Il successivo OFF→ON dello zaino può ancora confermare HOME anche nel
pomeriggio, fuori dalla fascia di uscita.

**Migrazione degli stati esistenti:** un vecchio snapshot v1.0.0 con
NEAR_HOME e `bag_return_eligible = true` viene corretto in AWAY
al riavvio, mantenendo il diritto di rientro dello zaino.
Poiché questo può modificare «Casa certamente vuota», controllare
le automazioni dell'allarme quando si installa l'aggiornamento.
Se il Watch diventa OFF da un NEAR_HOME preesistente mentre il flag
è attivo, il ritorno ad AWAY conserva la provenienza dello zaino.

**Forzatura manuale AWAY:** non autorizza il rientro dello zaino. Una
correzione manuale non può essere annullata da una semplice riconnessione BLE
dello zaino. Un successivo iPhone HOME o Watch con evidenze fisiche valide
può invece marcare HOME se non è attiva un'altra uscita autorevole
causata dallo zaino.

**HOME già confermato:** un altro evento ON dello zaino viene ignorato,
senza riscrivere motivo e data dell'ultimo cambio di presenza.

## Riavvii e aggiornamento da RC5

Il flag viene salvato nella snapshot della FSM assieme allo stato, usando
un campo opzionale del formato 5. Dopo un riavvio v1.0.1, una partenza causata
dallo zaino conserva il diritto di rientro anche da NEAR_HOME.

Le snapshot RC5 non contengono il flag. Per prudenza, dopo il **primo**
aggiornamento, una persona già AWAY per lo zaino non viene automaticamente
riportata a HOME dal solo zaino ON: per quella situazione eccezionale serve
un normale evento di iPhone/Watch o un intervento manuale. Dopo una nuova
uscita reale dello zaino, il ciclo torna completamente automatico.

Un recupero `unavailable → on` o `unknown → on` non è un vero OFF → ON:
l'adapter continua a ignorarlo. Lo zaino OFF permanente non impedisce
un autentico rientro iPhone o una correzione manuale. La restrizione
sul Watch dipende dal **flag causale** e non dalla sola lettura OFF dello
zaino: senza una partenza accettata, Watch e ingressi fisici mantengono
la loro normale logica.

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
il Watch lasciato in casa che resta AWAY, il riavvio dopo BAG_LEFT,
la normalizzazione di un vecchio NEAR_HOME con flag true e il rientro
zaino OFF→ON nel pomeriggio.
L'attributo `bag_return_eligible` del sensore individuale mostra il valore
attuale della condizione.
