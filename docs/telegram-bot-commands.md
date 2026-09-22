# Comandi del bot Telegram

Elenco dei comandi esposti dal bot interattivo ([`app/telegram_bot.py`](../backend/app/telegram_bot.py)), disponibile quando `ENABLE_BOT=true` in [`backend/.env`](../backend/.env).

## Registrazione su BotFather (opzionale)

Per abilitare l'autocomplete dei comandi nella chat Telegram:

1. Apri una conversazione con [@BotFather](https://t.me/BotFather).
2. Invia `/setcommands`.
3. Seleziona il tuo bot dall'elenco.
4. Incolla il blocco seguente e invialo:

```
list_whales - Elenca le whale monitorate
portfolio - Composizione portafoglio di una whale
week - Operazioni insider ultimi 7 giorni
month - Filing + insider ultimi 30 giorni
report - Report settimanale su richiesta
help - Guida ai comandi
```

## Icona e descrizione del bot (opzionale)

Sempre da [@BotFather](https://t.me/BotFather), puoi personalizzare l'aspetto del bot nell'elenco chat e nel suo profilo:

1. Invia `/setuserpic`, seleziona il tuo bot e carica un'immagine quadrata (es. 🐋) da usare come icona/avatar.
2. Invia `/setdescription`, seleziona il bot e incolla il testo mostrato nella schermata iniziale prima che l'utente avvii la chat:
   ```
   🐋 Whale Alert — monitora le balene di Wall Street.
   Ricevi alert su nuovi filing 13F e operazioni insider (Form 4), consulta portafogli e report settimanali direttamente in chat.
   ```
3. Invia `/setabouttext`, seleziona il bot e incolla il testo breve mostrato nella sezione "Info" del profilo:
   ```
   Bot di monitoraggio whale: filing 13F, insider trade e report settimanali.
   ```

## Elenco comandi

| Comando | Descrizione |
|---|---|
| `/start`, `/help` | Guida ai comandi disponibili |
| `/list_whales` | Elenca le whale monitorate con un indice di selezione |
| `/portfolio <n>` | Composizione del portafoglio della whale indicata |
| `/week [<n>]` | Operazioni insider (Form 4) degli ultimi 7 giorni |
| `/month [<n>]` | Filing 13F + operazioni insider degli ultimi 30 giorni |
| `/report` | Report settimanale su richiesta |

`<n>` è l'indice mostrato da `/list_whales` (in alternativa un CIK o un frammento del nome). Se omesso, `/week` e `/month` aggregano tutte le whale monitorate.

## Shortcut inline (pulsanti cliccabili)

Ogni risposta del bot (`/list_whales`, `/portfolio`, `/week`, `/month`, `/report`) include sotto il messaggio una tastiera inline con una riga per ogni whale monitorata:

```
🏦 Berkshire Hathaway   📅 Week   🗓️ Month
🏦 Scion Asset Mgmt     📅 Week   🗓️ Month
...
```

- Il pulsante **🏦 &lt;nome whale&gt;** apre direttamente `/portfolio` per quella whale.
- I pulsanti **📅 Week** e **🗓️ Month** aprono direttamente `/week` e `/month` per quella whale.

Il CIK della whale è incorporato nel `callback_data` del pulsante (es. `portfolio:0001067983`), quindi non è mai necessario digitarlo a mano: basta un tap per ottenere la richiesta desiderata. La tastiera resta disponibile anche sotto il risultato, permettendo di passare da una whale all'altra senza dover reinviare `/list_whales`.

## Formattazione dei messaggi

I messaggi usano la formattazione **HTML** di Telegram (grassetto per intestazioni e nomi, `codice monospazio` per i CIK) ed emoji per distinguere a colpo d'occhio acquisti (🟢 BUY) e vendite (🔴 SELL).

## Note

- Il bot funziona in **long polling**, avviato/arrestato automaticamente nel lifespan di FastAPI ([`app/main.py`](../backend/app/main.py)).
- Su reti che bloccano il TLS verso `api.telegram.org` (es. reti aziendali con SSL inspection) il bot non riceve/invia messaggi; l'errore viene loggato senza far crashare l'app.
- Per ricevere risposte ai comandi devi comunque avviare una chat col bot (inviargli `/start` o un qualsiasi messaggio prima).
