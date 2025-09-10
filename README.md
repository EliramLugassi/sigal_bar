# Vaad Management App

This project is a Streamlit application for managing apartment building finances.
It allows administrators and residents to track charges, record payments and
handle suppliers and expenses.

## Features
- User authentication with admin and regular roles
- Dashboard with KPIs and cash flow charts
- Manage buildings, apartments and residents
- Record expenses and transactions
- Generate and email invoices
- Supplier management
- Onboarding wizard for initial setup
- Optional GPT assistant for quick data questions

## Running Locally
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set environment variables for the database and OpenAI API key
   (see `.env.example`).
3. Launch the app:
   ```bash
   streamlit run app.py
   ```
