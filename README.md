# CRM Follow-up Agent

An AI agent that reads a CSV of real estate CRM contacts, flags who needs outreach based on inactivity rules, and drafts personalized emails using Groq (`llama-3.3-70b-versatile`).

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
python agent.py
```

Prints a summary table of contacts needing action, then saves drafts to `drafts/`.

### Streamlit UI

```bash
streamlit run app.py
```

Upload a CSV or use the included `contacts.csv`. Generate all drafts at once or one at a time with live streaming output.

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
├── app.py            Streamlit UI
├── contacts.csv      Sample CRM data (15 Tulsa OK contacts)
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
