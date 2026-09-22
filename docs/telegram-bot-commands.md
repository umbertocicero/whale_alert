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

## Note

- Il bot funziona in **long polling**, avviato/arrestato automaticamente nel lifespan di FastAPI ([`app/main.py`](../backend/app/main.py)).
- Su reti che bloccano il TLS verso `api.telegram.org` (es. reti aziendali con SSL inspection) il bot non riceve/invia messaggi; l'errore viene loggato senza far crashare l'app.
- Per ricevere risposte ai comandi devi comunque avviare una chat col bot (inviargli `/start` o un qualsiasi messaggio prima).
