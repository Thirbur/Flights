#!/usr/bin/env python3
"""Weekly email of cheap NONSTOP weekend flights from NYC (JFK/LGA/EWR).

Data: Travelpayouts / Aviasales Data API (free token, cached fares).
Email: any SMTP server (Gmail app password works).

Usage:
  python flight_digest.py --dry-run        # fetch + print, no email
  python flight_digest.py --demo           # fake data, prints the email (no API needed)
  python flight_digest.py                  # fetch + send email
"""
import argparse, os, smtplib, ssl, sys, datetime as dt
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import quote
import requests

# ---------- settings (override with env vars) ----------
ORIGIN        = os.getenv("ORIGIN", "NYC")            # NYC = JFK + LGA + EWR
CURRENCY      = os.getenv("CURRENCY", "usd")
WEEKENDS      = int(os.getenv("WEEKENDS_AHEAD", "8"))  # how many upcoming weekends to scan
MAX_PRICE     = float(os.getenv("MAX_PRICE", "400"))   # round-trip, per person
TOP_N         = int(os.getenv("TOP_N", "15"))          # rows in the email
# (depart weekday, return weekday); Mon=0 ... Sun=6.  Fri->Sun, plus Fri->Mon:
TRIP_PATTERNS = [(4, 6), (4, 0)]
API_URL       = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"


def upcoming_trips():
    today = dt.date.today()
    trips = []
    for dep_wd, ret_wd in TRIP_PATTERNS:
        first = today + dt.timedelta(days=(dep_wd - today.weekday()) % 7 or 7)
        for w in range(WEEKENDS):
            dep = first + dt.timedelta(weeks=w)
            ret = dep + dt.timedelta(days=(ret_wd - dep_wd) % 7)
            trips.append((dep, ret))
    return sorted(set(trips))


def fetch_deals(token):
    deals = {}
    for dep, ret in upcoming_trips():
        params = {
            "origin": ORIGIN, "departure_at": dep.isoformat(), "return_at": ret.isoformat(),
            "one_way": "false", "direct": "true", "unique": "true",   # cheapest per destination
            "sorting": "price", "currency": CURRENCY, "limit": 100, "token": token,
        }
        try:
            r = requests.get(API_URL, params=params, timeout=30)
            r.raise_for_status()
            rows = r.json().get("data", [])
        except Exception as e:
            print(f"warn: {dep}->{ret}: {e}", file=sys.stderr)
            continue
        for d in rows:
            # belt and braces: both directions must be nonstop
            if d.get("transfers", 0) != 0 or d.get("return_transfers", 0) != 0:
                continue
            if d["price"] > MAX_PRICE:
                continue
            key = (d["destination"], d["departure_at"][:10], d["return_at"][:10])
            deals[key] = d
    return sorted(deals.values(), key=lambda d: d["price"])[:TOP_N]


def google_flights_url(d):
    q = (f"Nonstop flights from {d.get('origin_airport') or ORIGIN} to "
         f"{d.get('destination_airport') or d['destination']} on {d['departure_at'][:10]} "
         f"through {d['return_at'][:10]}")
    return "https://www.google.com/travel/flights?q=" + quote(q)


def render(deals):
    sym = {"usd": "$", "eur": "€", "gbp": "£"}.get(CURRENCY.lower(), "")
    subject = (f"✈️ {len(deals)} cheap nonstop weekend trips from NYC"
               + (f" — from {sym}{deals[0]['price']:.0f}" if deals else ""))
    if not deals:
        body = "<p>No nonstop weekend fares under your price cap this week.</p>"
        return subject, body, body
    rows_html, rows_txt = [], []
    for d in deals:
        dep = dt.datetime.fromisoformat(d["departure_at"][:19])
        ret = dt.datetime.fromisoformat(d["return_at"][:19])
        dest = d.get("destination_airport") or d["destination"]
        route = f"{d.get('origin_airport') or ORIGIN} → {dest}"
        dates = f"{dep:%a %b %d} – {ret:%a %b %d}"
        url = google_flights_url(d)
        rows_html.append(
            f"<tr><td style='padding:8px;border-bottom:1px solid #eee'><b>{route}</b><br>"
            f"<span style='color:#666'>{d.get('airline','')}</span></td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'>{dates}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right'>"
            f"<b>{sym}{d['price']:.0f}</b></td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'><a href='{url}'>Check</a></td></tr>")
        rows_txt.append(f"{sym}{d['price']:.0f}  {route}  {dates}  {url}")
    html = ("<div style='font-family:-apple-system,Segoe UI,sans-serif;max-width:640px'>"
            "<h2>Cheap nonstop weekend flights from NYC</h2>"
            f"<p style='color:#666'>Round-trip per person, nonstop both ways, under {sym}{MAX_PRICE:.0f}. "
            "Prices are cached fares seen recently — confirm before booking.</p>"
            "<table style='border-collapse:collapse;width:100%'>"
            "<tr style='text-align:left;color:#666'><th style='padding:8px'>Route</th><th>Dates</th>"
            "<th style='text-align:right'>Price</th><th></th></tr>"
            + "".join(rows_html) + "</table></div>")
    return subject, html, "\n".join(rows_txt)


def send(subject, html, text):
    host, port = os.getenv("SMTP_HOST", "smtp.gmail.com"), int(os.getenv("SMTP_PORT", "465"))
    user, pw = os.environ["SMTP_USER"], os.environ["SMTP_PASS"]
    to = os.getenv("EMAIL_TO", user)
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.attach(MIMEText(text, "plain")); msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context()) as s:
        s.login(user, pw); s.sendmail(user, [to], msg.as_string())


def demo_deals():
    base = dt.date.today() + dt.timedelta(days=(4 - dt.date.today().weekday()) % 7 or 7)
    mk = lambda dest, ap, price, air: dict(
        origin_airport="EWR", destination=dest, destination_airport=ap, price=price, airline=air,
        transfers=0, return_transfers=0,
        departure_at=f"{base}T18:30:00-04:00", return_at=f"{base + dt.timedelta(days=2)}T20:00:00-04:00")
    return [mk("MIA", "MIA", 118, "NK"), mk("BOS", "BOS", 129, "B6"), mk("DUB", "DUB", 342, "EI")]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    deals = demo_deals() if a.demo else fetch_deals(os.environ["TRAVELPAYOUTS_TOKEN"])
    subject, html, text = render(deals)
    if a.demo or a.dry_run:
        print(subject); print(text)
        if a.demo: open("demo_email.html", "w").write(html)
    else:
        send(subject, html, text); print("sent:", subject)
