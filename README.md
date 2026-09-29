# Weekend flight digest (NYC, nonstop only)

Emails you the cheapest nonstop round-trip weekend flights from JFK/LGA/EWR every Monday.
Runs free on GitHub Actions — no server needed.

## Setup (about 10 minutes)
1. **Flight data token:** create a free account at travelpayouts.com and copy your API token.
2. **Email login:** for Gmail, turn on 2-step verification, then create an App Password
   (Google Account → Security → App passwords). Don't use your normal password.
3. **Put this folder in a new private GitHub repo.**
4. Repo → Settings → Secrets and variables → Actions → add:
   `TRAVELPAYOUTS_TOKEN`, `SMTP_USER` (your Gmail address), `SMTP_PASS` (the app password),
   `EMAIL_TO` (where to send; can be the same address).
5. Actions tab → "Weekend flight digest" → **Run workflow** to test. After that it runs on its own.

## Tweaking
- Price cap, schedule, and trip shapes: `MAX_PRICE` in the workflow, the `cron` line, and
  `TRIP_PATTERNS` in `flight_digest.py` (default Fri→Sun and Fri→Mon, next 8 weekends).
- Non-Gmail email: set `SMTP_HOST` / `SMTP_PORT` env vars.
- Local test: `pip install -r requirements.txt`, then `python flight_digest.py --demo`
  (fake data) or `TRAVELPAYOUTS_TOKEN=... python flight_digest.py --dry-run`.
