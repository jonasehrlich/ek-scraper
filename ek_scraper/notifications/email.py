import smtplib
from email.mime.text import MIMEText

with open("results.txt") as f:
    body = f.read()

msg = MIMEText(body)
msg["Subject"] = "Scraper Results"
msg["From"] = "me@example.com"
msg["To"] = "you@example.com"

with smtplib.SMTP("smtp.example.com", 587) as server:
    server.login("me@example.com", "password")
    server.send_message(msg)
