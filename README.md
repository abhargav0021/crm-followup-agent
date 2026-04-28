# CRM Follow-up Agent

An AI agent that reads real estate CRM contacts from CSV, SQLite, or the local API, flags who needs outreach based on inactivity rules, and drafts personalized emails using Groq (`llama-3.3-70b-versatile`).

## Setup

```bash
cd crm-followup-agent
pip install -r requirements.txt
cp .env.example .env          # then add your key
# GROQ_API_KEY=gsk_...
```

## Usage

### CLI

```bash
python3 agent.py
```

Prints a summary table of contacts needing action, then saves drafts to `drafts/`.

### SQLite Seed

```bash
python3 database.py
```

The CLI, API, and Streamlit app also seed `crm.db` from `contacts.csv` automatically when the database is empty.

### FastAPI

```bash
uvicorn api:app --reload
```

Serves contacts at `http://127.0.0.1:8000/contacts`.

For a cloud deployment, host this FastAPI app separately and set `CONTACTS_API_URL`
to the public `/contacts` endpoint.

### Streamlit UI

```bash
streamlit run app.py
```

Upload a CSV, use the local FastAPI server, or fall back to the seeded SQLite database. Generate all drafts at once or one at a time with live streaming output.

### Deploy to Streamlit Community Cloud

1. Push this project to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) and create a new app.
3. Select your repository, branch, and set the main file path to `app.py`.
4. Add this in **Advanced settings → Secrets**:

```toml
GROQ_API_KEY = "your_groq_api_key_here"
CONTACTS_API_URL = "https://your-fastapi-app.example.com/contacts"
```

5. Deploy the app.

On Streamlit Cloud, **Use FastAPI server** works only when `CONTACTS_API_URL`
points to a public FastAPI deployment. Without that URL, the app falls back to
an uploaded CSV or the included seeded data.

## Follow-up Rules

| Stage | Threshold |
|---|---|
| Hot Lead / Warm Lead | > 30 days → Follow-up needed |
| Cold Lead | > 60 days → Follow-up needed |
| Active Deal | > 14 days → Check-in needed |
| Lost | Never contacted |

## Project Structure

```
crm-followup-agent/
├── agent.py          CLI script
├── api.py            FastAPI contacts endpoint
├── app.py            Streamlit UI
├── contacts.csv      Sample CRM data (15 Tulsa OK contacts)
├── database.py       SQLite setup and seed helpers
├── scheduler.py      Daily automation runner
├── .env.example      API key template
├── .gitignore
├── requirements.txt
└── drafts/           Generated email drafts (git-ignored)
```

## CSV Format

```
name,email,phone,property_interest,budget,last_contact_days_ago,deal_stage,notes
```

`deal_stage` must be one of: `Hot Lead`, `Warm Lead`, `Cold Lead`, `Active Deal`, `Lost`
