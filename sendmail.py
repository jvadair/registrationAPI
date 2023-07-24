import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pyntree import Node
from flask import render_template
import os
from jinja2 import Template
from uuid import uuid4
from copy import copy

# Config
"""
This file looks for the following parameters to be set:
SMTP_EMAIL:    str
SMTP_ENVPASS:  str  (the name of the environment variable holding the password)
SMTP_SERVER:   str
SMTP_PORT:     int
"""

settings = Node('config.json')
nocontact = Node('db/do_not_email.pyn', autosave=True)
if nocontact() == {}:  # First-run with nocontact db
    nocontact.emails = []
email_ids = Node('db/email_map.pyn', autosave=True)


def associate_email(email):
    try:
        return email_ids.get(email)._val
    except AttributeError:
        ID = str(uuid4())
        email_ids.set(email, ID)
        return ID


def send_template(template_path, subject, *recipients, ignore_unsubscribed=False, **kwargs):
    """
    Fill and send a Jinja template
    :param template_path: The HTML template to send
    :param subject: The subject of the email
    :param recipients: All emails receiving the message
    :param ignore_unsubscribed: You can choose to ignore users who have unsubscribed
    :param kwargs: Pass variables to the Jinja template
    :return:
    """
    recipients = list(recipients)
    if not ignore_unsubscribed:
        for recipient in recipients:
            if associate_email(recipient) in nocontact.emails():
                recipients.remove(recipient)

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = settings.SMTP_EMAIL()
    context = ssl.create_default_context()

    with smtplib.SMTP_SSL(settings.SMTP_SERVER(), settings.SMTP_PORT(), context=context) as server:
        server.login(settings.SMTP_EMAIL(), os.getenv(settings.SMTP_ENVPASS()))
        for recipient in recipients:
            to_send = copy(message)
            to_send["To"] = recipient
            with open('templates/' + template_path, 'r') as file:
                html = Template(file.read()).render(**kwargs, unsub_id=associate_email(recipient))
            to_send.attach(MIMEText(html, "html"))
            server.sendmail(
                settings.SMTP_EMAIL(),
                recipient,
                to_send.as_string()
            )


def unsubscribe(email_id):
    if not email_id:
        return "No user ID was provided.", 400
    elif email_id in nocontact.emails():
        return "You have already unsubscribed.", 400
    elif email_id not in nocontact().values():
        return "There is no email associated with that ID", 400
    else:
        nocontact.emails().append(email_id)
        nocontact.save()  # .append() doesn't trigger autosave!
        return "You are no longer subscribed to emails from HashCards."
