"""
CRM Follow-up Agent — CLI
Reads contacts.csv, flags who needs outreach, drafts personalized emails via Groq.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import pandas as pd
from groq import Groq

load_dotenv()

CSV_PATH = Path(__file__).parent / "contacts.csv"
DRAFTS_DIR = Path(__file__).parent / "drafts"
MODEL = "llama-3.3-70b-versatile"

THRESHOLD_HOT_WARM = 30
THRESHOLD_COLD = 60
THRESHOLD_ACTIVE_DEAL = 14


def classify_contact(row: pd.Series) -> str | None:
    stage = row["deal_stage"]
    days = int(row["last_contact_days_ago"])

    if stage == "Lost":
        return None
    if stage == "Active Deal":
        return "Check-in needed" if days > THRESHOLD_ACTIVE_DEAL else None
    if stage in ("Hot Lead", "Warm Lead"):
        return "Follow-up needed" if days > THRESHOLD_HOT_WARM else None
    if stage == "Cold Lead":
        return "Follow-up needed" if days > THRESHOLD_COLD else None
    return None


def build_prompt(contact: pd.Series) -> str:
    return f"""You are a top-producing real estate agent based in Tulsa, Oklahoma.

Draft a personalized follow-up email for this client:
- Name: {contact['name']}
- Property interest: {contact['property_interest']}
- Budget: ${int(contact['budget']):,}
- Deal stage: {contact['deal_stage']}
- Days since last contact: {contact['last_contact_days_ago']}
- Notes: {contact['notes']}

Write a warm, professional email that:
1. Opens with a personal touch tied to their specific situation
2. Includes one brief, relevant Tulsa market insight (inventory, rates, or a local neighborhood note)
3. Proposes one clear next step (call, showing, document review, etc.)
4. Stays under 180 words in the body

Format your output as:
Subject: <subject line>

<email body>"""


def draft_email(client: Groq, contact: pd.Series) -> str:
    stream = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": build_prompt(contact)}],
        max_tokens=600,
        stream=True,
    )
    chunks = []
    for chunk in stream:
        text = chunk.choices[0].delta.content or ""
        chunks.append(text)
    return "".join(chunks)


def print_summary(flagged: list[tuple[pd.Series, str]]) -> None:
    col_name = 25
    col_stage = 15
    col_days = 8
    col_action = 22

    header = (
        f"{'Name':<{col_name}} {'Stage':<{col_stage}} {'Days':>{col_days}}  "
        f"{'Action':<{col_action}}"
    )
    divider = "-" * len(header)

    print(f"\n{'='*len(header)}")
    print(f"CRM Follow-up Agent  —  {len(flagged)} contact(s) need action")
    print(f"{'='*len(header)}")
    print(header)
    print(divider)
    for row, action in flagged:
        print(
            f"{row['name']:<{col_name}} {row['deal_stage']:<{col_stage}} "
            f"{int(row['last_contact_days_ago']):>{col_days}}  {action:<{col_action}}"
        )
    print()


def main() -> None:
    if not os.getenv("GROQ_API_KEY"):
        print("Error: GROQ_API_KEY is not set. Copy .env.example to .env and add your key.")
        sys.exit(1)

    if not CSV_PATH.exists():
        print(f"Error: {CSV_PATH} not found.")
        sys.exit(1)

    df = pd.read_csv(CSV_PATH)
    DRAFTS_DIR.mkdir(exist_ok=True)

    flagged: list[tuple[pd.Series, str]] = []
    for _, row in df.iterrows():
        action = classify_contact(row)
        if action:
            flagged.append((row, action))

    if not flagged:
        print("No contacts need follow-up right now.")
        return

    print_summary(flagged)

    client = Groq()
    print("Generating email drafts...\n")

    for row, action in flagged:
        first, *rest = row["name"].split()
        last = rest[-1] if rest else first
        filename = DRAFTS_DIR / f"{first}_{last}.txt"

        print(f"  {row['name']} ({action})...", end="", flush=True)
        draft = draft_email(client, row)
        filename.write_text(draft)
        print(f" → {filename.relative_to(Path(__file__).parent)}")

    print(f"\nDone. {len(flagged)} draft(s) saved to {DRAFTS_DIR.relative_to(Path(__file__).parent)}/")


if __name__ == "__main__":
    main()
