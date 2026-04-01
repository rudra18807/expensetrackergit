# Expense Tracker

Simple browser app with:

- Create new tracker or load existing tracker
- Unique 10-digit tracker ID stored in Airtable
- Transaction list with red (expense) and green (income) borders
- Auto-updating current balance

## Airtable setup

Create one table (example: Airtable `Table 1`) and make each row a transaction:

- `ClientID` (single line text)
- `Description` (single line text)
- `Amount` (number)
- `Type` (single select or text: `income` / `expense`)
- `CreatedAt` (date-time or single line text)

## Server setup (required for multi-user)

This is a multi-user app, so the Airtable token must be stored server-side.

1) Create an Airtable Personal Access Token (PAT) with:

- `data.records:read`
- `data.records:write`

2) Create a `.env` file (copy from `.env.example`) and fill:

- `AIRTABLE_PAT`
- `AIRTABLE_BASE_ID` (starts with `app...`)
- `AIRTABLE_TABLE_NAME` (example: `Table 1`)

## Run

Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start the server:

```bash
python server.py
```

Then open:

- `http://localhost:5173`
