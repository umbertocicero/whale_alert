# Guida al deploy (server gratuiti)

Questa guida spiega **dove e come** eseguire il backend di Whale Alert 24 ore su 24, in modo che scheduler, polling Form 4/13F e bot Telegram interattivo funzionino in continuo — cosa che la rete aziendale usata in sviluppo non permette (blocca il TLS verso `api.telegram.org`).

## Cosa richiede questa app all'hosting

Prima di scegliere un servizio, verifica che soddisfi questi 4 requisiti — sono il motivo per cui **non tutte le piattaforme "gratis" vanno bene**:

1. **Processo persistente 24/7**: lo scheduler (APScheduler) e il long polling del bot Telegram girano dentro il processo Python; se il servizio "si addormenta" quando non riceve traffico HTTP, smettono di funzionare.
2. **Filesystem persistente**: il database SQLite (`whale_alert.db`) deve sopravvivere a riavvii/redeploy, altrimenti perdi lo storico di filing e insider trade ad ogni restart.
3. **Traffico in uscita (outbound) libero verso**: `api.telegram.org` (bot) e i domini SEC EDGAR usati da `edgartools` (`www.sec.gov`, ecc.). Alcune piattaforme free limitano o penalizzano proprio le chiamate API in uscita.
4. **~200–300 MB di RAM** e un runtime Python 3.13 — requisiti minimi, qualsiasi piano gratuito li copre.

## Confronto rapido

| Piattaforma | Sempre attivo? | Disco persistente? | Chiamate API in uscita | Adatto a questo progetto? |
|---|---|---|---|---|
| **Oracle Cloud "Always Free"** (VM Ampere A1/AMD) | ✅ Sì, nessuno spegnimento | ✅ Sì (storage a blocchi incluso) | ✅ Nessuna restrizione | ✅ **Consigliato** |
| Render (piano Free) | ❌ Si addormenta dopo 15 min di inattività | ❌ Filesystem effimero (si resetta ad ogni riavvio/redeploy) | ⚠️ Può sospendere il servizio se rileva "traffico in uscita insolito" (è esattamente quello che fa questo bot) | ⚠️ Solo per demo/test rapidi, non per uso continuativo |
| Railway (piano Free) | ✅ Sì | ✅ Volume da 0.5 GB incluso | ✅ Nessuna restrizione nota | ✅ Alternativa valida, ma dopo i 30 giorni di prova diventa a consumo (min. $1/mese) |
| Vercel (piano Hobby) | ❌ Nessun processo persistente: solo funzioni serverless con timeout max 300s | ❌ Filesystem effimero, nessun volume/disco | ✅ Nessuna restrizione durante l'esecuzione della funzione | ❌ Non adatto: architettura request/response, non supporta scheduler o long-polling in background |
| PythonAnywhere (piano Free) | ✅ Sì | ✅ Sì | ❌ Il piano free storicamente limita le richieste HTTPS in uscita a una whitelist di domini: bloccherebbe sia Telegram sia SEC EDGAR | ❌ Sconsigliato |

Fonti: [render.com/docs/free](https://render.com/docs/free), [railway.com/pricing](https://railway.com/pricing), [oracle.com/cloud/free](https://www.oracle.com/cloud/free/), [vercel.com/docs/functions/limitations](https://vercel.com/docs/functions/limitations).

---

## Opzione consigliata: Oracle Cloud "Always Free"

Oracle Cloud offre VM **gratuite per sempre** (non un trial): 2 VM AMD (1/8 OCPU, 1 GB RAM ciascuna) oppure una VM Ampere A1 (fino a 4 OCPU / 24 GB RAM, ripartibili su più istanze), più storage a blocchi incluso. Nessuno spegnimento per inattività, nessuna restrizione sul traffico in uscita: è l'ambiente più simile a un piccolo VPS "vero".

### 1. Crea l'account e la VM

1. Registrati su [oracle.com/cloud/free](https://www.oracle.com/cloud/free/) (richiede una carta per verifica identità, non viene addebitata per le risorse Always Free).
2. Nella console OCI: **Compute → Instances → Create Instance**.
3. Scegli un'immagine **Ubuntu 24.04** (o Oracle Linux) e uno shape **Always Free eligible** (`VM.Standard.A1.Flex` con 1–4 OCPU / fino a 24 GB, oppure `VM.Standard.E2.1.Micro`).
4. Genera/carica una coppia di chiavi SSH e crea la VM.
5. Annota l'IP pubblico assegnato.

### 2. Configura il firewall

Il bot funziona in **long polling** (connessioni in uscita), quindi non serve aprire porte in entrata per farlo funzionare. Apri la porta `8000` solo se vuoi esporre pubblicamente anche gli endpoint REST di FastAPI:

- Nella **Security List / Network Security Group** della VCN, aggiungi una regola Ingress per la porta `8000` (TCP) se necessario.
- Sulla VM stessa: `sudo ufw allow 8000/tcp` (se `ufw` è attivo).

### 3. Installa Python 3.13 e il progetto

```bash
ssh ubuntu@<IP_PUBBLICO>

sudo apt update && sudo apt install -y python3.13 python3.13-venv git

git clone <url-del-tuo-repo> whale_alert
cd whale_alert/backend

python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env
nano .env   # inserisci TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SEC_IDENTITY_EMAIL, ecc.
```

> Se il tuo repo non è pubblico, trasferisci i file con `scp -r backend ubuntu@<IP>:~/whale_alert` invece di `git clone`.

### 4. Esegui l'app come servizio systemd (24/7, riavvio automatico)

Crea `/etc/systemd/system/whale-alert.service`:

```ini
[Unit]
Description=Whale Alert backend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/whale_alert/backend
ExecStart=/home/ubuntu/whale_alert/backend/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Attiva e avvia il servizio:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now whale-alert
sudo systemctl status whale-alert     # verifica che sia "active (running)"
journalctl -u whale-alert -f          # segui i log in tempo reale
```

> ⚠️ **Non usare `--reload`** in produzione (è solo per lo sviluppo locale): con systemd il riavvio in caso di crash è già gestito da `Restart=always`.

Il file `whale_alert.db` (percorso da `DATABASE_PATH` in `.env`) resta sul disco della VM tra un riavvio e l'altro: nessuna perdita di dati.

### 5. Aggiornare il codice in futuro

```bash
cd ~/whale_alert
git pull
cd backend
.venv/bin/pip install -r requirements.txt   # se sono cambiate le dipendenze
sudo systemctl restart whale-alert
```

---

## Alternativa: Railway (piano Free)

Più semplice da configurare (deploy da GitHub in pochi click), con un volume persistente da 0.5 GB — sufficiente per il database SQLite di questo progetto.

1. Crea un account su [railway.com](https://railway.com) e collega il repository GitHub.
2. **New Project → Deploy from GitHub repo**, seleziona la cartella `backend/` come root del servizio.
3. Imposta il comando di avvio: `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
4. In **Variables**, aggiungi tutte le variabili di `.env.example` con i valori reali.
5. Aggiungi un **Volume** montato su `backend/` (o sulla cartella indicata da `DATABASE_PATH`) per persistere `whale_alert.db` tra i deploy.

> Il piano Free parte con 30 giorni di prova ($5 di credito), dopo di che resta attivo ma a consumo (minimo $1/mese) con risorse ridotte (fino a 1 vCPU / 0.5 GB RAM). Non è quindi "gratis a vita" in senso stretto, ma è economico e senza le limitazioni di sleep/disco effimero di Render.

## Perché evitare Render (piano Free) per questo progetto

Render è ottimo per demo rapide ma ha tre limitazioni che confliggono con i requisiti di questa app (fonte: [render.com/docs/free](https://render.com/docs/free)):

- **Spin-down dopo 15 minuti di inattività**: senza richieste HTTP in entrata, il processo (e quindi scheduler + bot) si ferma.
- **Filesystem effimero**: ad ogni riavvio/redeploy/spin-down, `whale_alert.db` viene azzerato.
- **Sospensione per traffico in uscita "insolito"**: Render segnala esplicitamente che chiamate frequenti verso API esterne (esattamente ciò che fa questo bot verso Telegram e SEC EDGAR) possono far sospendere il servizio.

Se vuoi comunque provarlo per una demo di breve durata, sappi che dovrai riconfigurare da zero il database ad ogni riavvio e che il bot potrebbe smettere di rispondere se il servizio si addormenta.

## Perché Vercel non è adatto a questo progetto

Vercel è pensato per siti/app **frontend e funzioni serverless a chiamata singola** (es. Next.js, API stateless), non per servizi backend persistenti. Dai [limiti ufficiali delle Vercel Functions](https://vercel.com/docs/functions/limitations):

- **Nessun processo persistente**: il codice gira solo dentro una funzione invocata da una richiesta HTTP e termina subito dopo la risposta. APScheduler e il long polling di Telegram richiedono invece un processo Python sempre attivo in background, cosa che l'architettura serverless di Vercel non supporta.
- **Timeout massimo di 300 secondi** (piano Hobby) per ogni invocazione: qualunque tentativo di "far girare" lo scheduler dentro una funzione verrebbe comunque interrotto.
- **Filesystem effimero e nessun volume persistente**: non c'è modo di salvare `whale_alert.db` in modo duraturo tra un'invocazione e l'altra.
- **Nessun vero cron/background worker gratuito**: i Cron Jobs di Vercel eseguono funzioni programmate periodicamente, ma restano invocazioni brevi e stateless — non un processo continuo come richiesto da questa app.

In sintesi: Vercel andrebbe bene solo per un'eventuale futura dashboard web statica/frontend, non per il backend FastAPI + scheduler + bot descritto in questa guida.

## Checklist finale prima del deploy

- [ ] `backend/.env` compilato con i valori reali (mai committarlo: è già in [`.gitignore`](../backend/.gitignore)).
- [ ] `ENABLE_BOT=true` se vuoi il bot interattivo attivo.
- [ ] Verifica che l'host scelto permetta connessioni HTTPS in uscita verso `api.telegram.org` e i domini SEC EDGAR (nessun proxy/firewall aziendale, a differenza della rete di sviluppo).
- [ ] Il processo va avviato con un supervisore (systemd, o l'equivalente della piattaforma) così da ripartire automaticamente in caso di crash.
- [ ] Il percorso di `DATABASE_PATH` punta a uno storage persistente, non a un filesystem effimero.
