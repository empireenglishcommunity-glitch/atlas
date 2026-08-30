# Deploying Atlas

Atlas runs as one Docker container on the existing Hetzner box (`77.42.43.250`), alongside the
other services. It is **simpler to deploy than the rest of the ecosystem** because it needs **no
inbound port and no Cloudflare Tunnel** — it talks to Telegram by *outbound* long-polling, calls
Groq over the internet, and reaches Kokoro on `localhost:8880` via host networking.

> We do this **together**: you run the commands on the box; everything else is prepared here.
> Nothing about Atlas is destructive to the other services — it only adds a new container.

---

## 0. What you need first (5 minutes, one-time)

1. **A bot token.** In Telegram, message **@BotFather** → `/newbot` → give it a name (e.g. `Atlas`)
   and a username ending in `bot` → copy the **token** it gives you.
2. **Your numeric chat id.** Message **@userinfobot** → it replies with your `Id` (a number like
   `123456789`). Atlas will only ever talk to this id.
3. **A Groq API key.** From <https://console.groq.com> → API Keys. You can reuse the ecosystem's
   key or make a new one — free tier is fine.

Keep these three values handy for step 2. **Never paste them into git or chat** — only into the
`.env` on the box.

---

## 1. Get the code onto the box

```bash
ssh root@77.42.43.250
cd /opt
git clone https://github.com/empireenglishcommunity-glitch/atlas.git
cd atlas
```

## 2. Configure

```bash
cp .env.example .env
nano .env
```
Fill in exactly these (leave the rest at their defaults):
```
TELEGRAM_BOT_TOKEN=<from BotFather>
OWNER_CHAT_ID=<from @userinfobot>
GROQ_API_KEY=<from console.groq.com>
```
Defaults already set for you: `TIMEZONE=Africa/Cairo`, `BRIEF_HOUR=6`, `KOKORO_URL=http://localhost:8880`,
`KOKORO_VOICE=af_heart`. Save and exit (Ctrl-O, Enter, Ctrl-X).

## 3. Make sure Kokoro is up (for the spoken brief)

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8880/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"model":"kokoro","input":"test","voice":"af_heart","response_format":"mp3"}'
```
Expect `200`. If not, start it: `cd /opt/kokoro-tts && docker compose up -d` (Atlas still works
without it — you'd just get the written brief and no voice note).

## 4. Build and run

```bash
cd /opt/atlas
docker compose up -d --build
docker compose logs --tail=20 atlas    # expect: "Atlas online — brief at 06:00 Africa/Cairo"
```

## 5. Verify it's alive (do this now, don't wait for 6 AM)

In Telegram, open your new bot and:
- send `/start` → it greets you.
- send a **voice note** (talk naturally, Arabic/English) → within a few seconds you get
  **"✅ Got it — …"** with how it understood and filed it.
- send `/today` → it builds and sends the full brief on demand (text + voice note), so you can hear
  it immediately instead of waiting for the morning.
- send `/domains` → see your life-areas and their neglect thresholds.

If a voice note comes back with **"📥 Saved — I'll sort this out in a moment"**, Groq was briefly
unreachable; Atlas kept your note and will interpret it within 15 minutes. Nothing is ever lost.

## 6. Wire it into the box's ops (so it survives reboots + gets backed up)

- `restart: unless-stopped` is already set, so it auto-starts on reboot.
- **Backup** — Atlas's whole brain is the `atlas-data` Docker volume (SQLite + the markdown
  archive). Add it to the nightly 3 AM backup routine the way the other services' data is backed
  up (tar the volume to `/opt/backups/`).
- **Watchdog** — add the `atlas` container to the health-check list in `/opt/monitor/watchdog.sh`
  so you're alerted if it ever goes down.
- Record the deploy in `empire-chronicle` (SESSION_CONTINUITY + STATUS), per the ecosystem rule.

---

## Updating later

```bash
cd /opt/atlas && git pull && docker compose up -d --build
```
Your `.env` and the `atlas-data` volume are preserved across updates.

## The daily rhythm, once it's live

- **06:00 Cairo** — the morning brief arrives (written + voice note).
- **Any time** — fire captures: text, voice, forwards, photos. `/done <id> [minutes]` when you
  finish something (the minutes teach it your real pace).
- **21:00 Cairo** — the evening close: "what did you get done?" + energy 1–5.
- **Always** — the Guardian watches; if gym/diet/deen goes 3 days quiet or a venture goes 7, it
  tells you in the next brief.

Then just **live with the spine for a few days** with your real voice notes. When you trust it,
we add the first organ — **People** — as its own branch + PR.
