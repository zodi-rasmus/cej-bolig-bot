import requests
from bs4 import BeautifulSoup
import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

URL = "https://udlejning.cej.dk/find-bolig/overblik?collection=residences&floorArea=45-250&minRooms=2&monthlyPrice=0-8000&p=k%C3%B8benhavn"
KNOWN_FILE = "known_listings.json"

GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT = os.environ.get("RECIPIENT_EMAIL", GMAIL_USER)


def load_known():
    if os.path.exists(KNOWN_FILE):
        with open(KNOWN_FILE) as f:
            return set(json.load(f))
    return set()


def save_known(ids):
    with open(KNOWN_FILE, "w") as f:
        json.dump(list(ids), f)


def scrape_listings():
    headers = {"User-Agent": "Mozilla/5.0 (compatible; bolig-bot/1.0)"}
    r = requests.get(URL, headers=headers, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    listings = []
    for a in soup.select("a[href*='/boliger/']"):
        href = a.get("href", "")
        listing_id = href.split("/boliger/")[-1].strip("/")
        if not listing_id:
            continue

        title_el = a.select_one("h6, h5, h4, strong")
        title = title_el.get_text(strip=True) if title_el else "Ny bolig"

        # Extract details from text spans
        spans = [s.get_text(strip=True) for s in a.select("span, p")]
        details = " | ".join(s for s in spans if s)

        full_url = f"https://udlejning.cej.dk{href}" if href.startswith("/") else href

        listings.append({
            "id": listing_id,
            "title": title,
            "details": details,
            "url": full_url,
        })

    # Deduplicate by id
    seen = set()
    unique = []
    for l in listings:
        if l["id"] not in seen:
            seen.add(l["id"])
            unique.append(l)
    return unique


def send_email(new_listings):
    subject = f"🏠 {len(new_listings)} ny(e) lejlighed(er) på CEJ Udlejning"

    html_rows = ""
    for l in new_listings:
        html_rows += f"""
        <div style="border:1px solid #e0e0e0; border-radius:8px; padding:16px; margin-bottom:16px;">
          <h3 style="margin:0 0 8px 0; color:#1a1a1a;">{l['title']}</h3>
          <p style="margin:0 0 8px 0; color:#666; font-size:14px;">{l['details']}</p>
          <a href="{l['url']}" style="display:inline-block; background:#2563eb; color:white;
             padding:8px 16px; border-radius:6px; text-decoration:none; font-size:14px;">
            Se bolig →
          </a>
        </div>
        """

    html_body = f"""
    <html><body style="font-family:sans-serif; max-width:600px; margin:auto; padding:20px;">
      <h2 style="color:#1a1a1a;">Nye boliger fundet 🎉</h2>
      <p style="color:#444;">Følgende boliger matcher dine kriterier (2+ vær., 45+ m², maks 8.000 kr./md., København):</p>
      {html_rows}
      <hr style="border:none; border-top:1px solid #eee; margin:24px 0;">
      <p style="color:#999; font-size:12px;">
        Fundet {datetime.now().strftime('%d. %b %Y kl. %H:%M')} —
        <a href="{URL}">Se alle boliger på CEJ</a>
      </p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = RECIPIENT
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENT, msg.as_string())

    print(f"✅ Mail sendt med {len(new_listings)} ny(e) bolig(er)")


def main():
    known_ids = load_known()
    listings = scrape_listings()

    print(f"Fandt {len(listings)} bolig(er) i alt. Kendte: {len(known_ids)}")

    new = [l for l in listings if l["id"] not in known_ids]

    if new:
        print(f"🆕 {len(new)} ny(e) bolig(er) — sender mail...")
        send_email(new)
        all_ids = known_ids | {l["id"] for l in listings}
        save_known(all_ids)
    else:
        print("Ingen nye boliger siden sidst.")
        # Still update known list in case listings were removed
        save_known({l["id"] for l in listings})


if __name__ == "__main__":
    main()
