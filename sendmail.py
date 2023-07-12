import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pyntree import Node
from flask import render_template
from os import getenv
from jinja2 import Template

# Config
"""
This file looks for the following parameters to be set:
SMTP_EMAIL:    str
SMTP_ENVPASS:  str  (the name of the environment variable holding the password)
SMTP_SERVER:   str
SMTP_PORT:     int
"""
settings = Node('config.json')


def send_template(template_path, subject, *recipients, **kwargs):
    bcc = True if len(recipients) > 1 else False
    message = MIMEMultipart("alternative")

    message["Subject"] = "Email Verification"
    message["From"] = settings.SMTP_EMAIL()
    if not bcc:
        print(recipients)
        message["To"] = recipients[0]  # No bcc header because all headers are visible to the recipients

    with open('templates/' + template_path, 'r') as file:
        html = Template(file.read()).render(**kwargs)
    message.attach(MIMEText(html, "html"))
    context = ssl.create_default_context()

    with smtplib.SMTP_SSL(settings.SMTP_SERVER(), settings.SMTP_PORT(), context=context) as server:
        server.login(settings.SMTP_EMAIL(), getenv(settings.SMTP_ENVPASS()))
        server.sendmail(
            settings.SMTP_EMAIL(),
            recipients,
            message.as_string()
        )
