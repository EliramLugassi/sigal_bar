"""Utility for sending emails."""
import yagmail
import os
from localization import get_translation
import streamlit as st


def send_invoice_email(receiver_email, subject, body, attachment_path=None):
    """Send an invoice email with optional attachment."""
    yag = yagmail.SMTP(user="vaadmanagment@gmail.com", password=os.getenv("EMAIL_PASS"))
    yag.send(
        to=receiver_email,
        subject=subject,
        contents=[
                    body,
            "תודה רבה,",
            "ועד הבית"
        ],
        attachments=attachment_path
    )
