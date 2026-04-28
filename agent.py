import os
import sys
import logging
from pathlib import Path

from database import ensure_seed_data
from dotenv import load_dotenv
import pandas as pd
from groq import Groq

# ── Config ─────────────────────────────────────────────
CONFIG = {
    "hot_warm_threshold": 30,
    "cold_threshold": 60,
    "active_threshold": 14
}

THRESHOLD_HOT_WARM = CONFIG["hot_warm_threshold"]
THRESHOLD_COLD = CONFIG["cold_threshold"]
THRESHOLD_ACTIVE_DEAL = CONFIG["active_threshold"]

# ── Setup ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)

load_dotenv()

DRAFTS_DIR = Path(__file__).parent / "drafts"
MODEL = "llama-3.3-70b-versatile"


# ── Core Logic ─────────────────────────────────────────
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


def process_pipeline(df):
    logging.info("Step 1: Data Ingestion")
    logging.info("Step 2: Classification Engine")

    flagged = []
    for _, row in df.iterrows():
        action = classify_contact(row)
        if action:
            logging.info(f"Processing {row['name']} - {action}")
            flagged.append((row, action))

    return flagged


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
2. Includes one brief, relevant Tulsa market insight
3. Proposes one clear next step
4. Stays under 180 words in the body

Format your output as:
Subject: <subject line>

<email body>"""


def draft_email(client: Groq, contact: pd.Series) -> str:
    logging.info("Step 3: AI Email Generation")

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
    header = f"{'Name':<25} {'Stage':<15} {'Days':>8}  {'Action':<22}"
    divider = "-" * len(header)

    print(f"\n{'=' * len(header)}")
    print(f"CRM Follow-up Agent - {len(flagged)} contact(s) need action")
    print(f"{'=' * len(header)}")
    print(header)
    print(divider)
    for row, action in flagged:
        print(
            f"{row['name']:<25} {row['deal_stage']:<15} "
            f"{int(row['last_contact_days_ago']):>8}  {action:<22}"
        )
    print()


def main():
    logging.info("Starting CRM pipeline...")

    if not os.getenv("GROQ_API_KEY"):
        print("Error: GROQ_API_KEY is not set. Copy .env.example to .env and add your key.")
        sys.exit(1)

    df = ensure_seed_data()
    logging.info(f"Loaded {len(df)} contacts")

    flagged = process_pipeline(df)

    if not flagged:
        print("No contacts need follow-up right now.")
        return

    print_summary(flagged)

    client = Groq()
    DRAFTS_DIR.mkdir(exist_ok=True)
    print("Generating email drafts...\n")

    for row, action in flagged:
        file_name = row["name"].replace(" ", "_")
        path = DRAFTS_DIR / f"{file_name}.txt"

        print(f"  {row['name']} ({action})...", end="", flush=True)
        draft = draft_email(client, row)
        path.write_text(draft)
        print(f" -> {path.relative_to(Path(__file__).parent)}")

    print(f"\nDone. {len(flagged)} draft(s) saved to {DRAFTS_DIR.relative_to(Path(__file__).parent)}/")


if __name__ == "__main__":
    main()
