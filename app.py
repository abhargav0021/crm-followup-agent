"""
CRM Follow-up Agent — Streamlit UI
"""

import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

CSV_PATH = Path(__file__).parent / "contacts.csv"
DRAFTS_DIR = Path(__file__).parent / "drafts"
MODEL = "llama-3.3-70b-versatile"

THRESHOLD_HOT_WARM = 30
THRESHOLD_COLD = 60
THRESHOLD_ACTIVE_DEAL = 14

ACTION_BADGE = {
    "Follow-up needed": "🔴",
    "Check-in needed": "🟡",
    None: "✅",
}


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


def stream_email(contact: pd.Series) -> str:
    client = Groq(api_key=st.session_state.api_key)
    placeholder = st.empty()
    full_text = ""

    stream = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": build_prompt(contact)}],
        max_tokens=600,
        stream=True,
    )
    for chunk in stream:
        text = chunk.choices[0].delta.content or ""
        full_text += text
        placeholder.markdown(f"```\n{full_text}\n```")

    placeholder.empty()
    return full_text


def save_draft(name: str, content: str) -> Path:
    DRAFTS_DIR.mkdir(exist_ok=True)
    parts = name.split()
    first = parts[0]
    last = parts[-1] if len(parts) > 1 else parts[0]
    path = DRAFTS_DIR / f"{first}_{last}.txt"
    path.write_text(content)
    return path


# ── Page setup ─────────────────────────────────────────────────────────────

st.set_page_config(page_title="CRM Follow-up Agent", page_icon="🏠", layout="wide")
st.title("CRM Follow-up Agent")
st.caption("AI-powered outreach for Tulsa real estate contacts · powered by Groq")

# ── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Settings")

    api_key_env = os.getenv("GROQ_API_KEY", "")
    api_key_input = st.text_input(
        "Groq API Key",
        value=api_key_env,
        type="password",
        help="Loaded from .env if present",
    )
    st.session_state.api_key = api_key_input
    st.caption(f"Model: `{MODEL}`")

    st.divider()
    st.header("Data Source")
    uploaded = st.file_uploader("Upload a contacts CSV", type="csv")
    if uploaded:
        st.session_state.df = pd.read_csv(uploaded)
        st.success(f"Loaded {len(st.session_state.df)} contacts from upload.")
    elif "df" not in st.session_state:
        if CSV_PATH.exists():
            st.session_state.df = pd.read_csv(CSV_PATH)
        else:
            st.session_state.df = pd.DataFrame()

    st.divider()
    st.markdown(
        "**Thresholds**\n"
        f"- Hot/Warm leads: >{THRESHOLD_HOT_WARM} days\n"
        f"- Cold leads: >{THRESHOLD_COLD} days\n"
        f"- Active Deal: >{THRESHOLD_ACTIVE_DEAL} days"
    )

# ── Load data ────────────────────────────────────────────────────────────────

df: pd.DataFrame = st.session_state.get("df", pd.DataFrame())

if df.empty:
    st.warning("No contacts loaded. Upload a CSV or ensure contacts.csv exists.")
    st.stop()

# ── Annotate dataframe ───────────────────────────────────────────────────────

df = df.copy()
df["action"] = df.apply(classify_contact, axis=1)
df["status"] = df["action"].map(lambda a: ACTION_BADGE.get(a, ""))

flagged_df = df[df["action"].notna()].reset_index(drop=True)
ok_df = df[df["action"].isna() & (df["deal_stage"] != "Lost")].reset_index(drop=True)
lost_df = df[df["deal_stage"] == "Lost"].reset_index(drop=True)

# ── Metrics row ──────────────────────────────────────────────────────────────

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Contacts", len(df))
col2.metric("Need Action", len(flagged_df), delta=f"{len(flagged_df)} contacts", delta_color="inverse")
col3.metric("Up to Date", len(ok_df))
col4.metric("Lost", len(lost_df))

st.divider()

# ── Contacts needing action ───────────────────────────────────────────────────

st.subheader("Contacts Needing Action")

if flagged_df.empty:
    st.success("All contacts are up to date.")
else:
    display_cols = ["status", "name", "deal_stage", "last_contact_days_ago", "property_interest", "budget", "action"]
    st.dataframe(
        flagged_df[display_cols].rename(columns={
            "status": "",
            "name": "Name",
            "deal_stage": "Stage",
            "last_contact_days_ago": "Days Ago",
            "property_interest": "Interest",
            "budget": "Budget ($)",
            "action": "Action",
        }),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.subheader("Generate Email Drafts")

    if not st.session_state.api_key:
        st.error("Enter your Groq API key in the sidebar to generate drafts.")
    else:
        if "drafts" not in st.session_state:
            st.session_state.drafts = {}

        if st.button("Generate All Drafts", type="primary"):
            progress = st.progress(0, text="Starting...")
            for i, (_, row) in enumerate(flagged_df.iterrows()):
                progress.progress(i / len(flagged_df), text=f"Drafting email for {row['name']}...")
                with st.spinner(f"Writing email for {row['name']}..."):
                    draft = stream_email(row)
                st.session_state.drafts[row["name"]] = draft
                save_draft(row["name"], draft)
            progress.progress(1.0, text="Done!")
            st.success(f"Generated {len(flagged_df)} draft(s). Saved to drafts/")

        st.caption("Or generate drafts one at a time:")
        for _, row in flagged_df.iterrows():
            with st.expander(
                f"{ACTION_BADGE.get(row['action'])} {row['name']} — "
                f"{row['deal_stage']} ({int(row['last_contact_days_ago'])} days ago)"
            ):
                col_a, col_b = st.columns([2, 1])
                with col_a:
                    st.markdown(f"**Interest:** {row['property_interest']}")
                    st.markdown(f"**Budget:** ${int(row['budget']):,} | **Action:** {row['action']}")
                    st.markdown(f"**Notes:** {row['notes']}")
                with col_b:
                    if st.button("Draft Email", key=f"btn_{row['name']}"):
                        with st.spinner(f"Writing email for {row['name']}..."):
                            draft = stream_email(row)
                        st.session_state.drafts[row["name"]] = draft
                        save_draft(row["name"], draft)

                if row["name"] in st.session_state.get("drafts", {}):
                    draft_text = st.session_state.drafts[row["name"]]
                    st.text_area("Draft", value=draft_text, height=260, key=f"draft_{row['name']}")
                    st.download_button(
                        "Download .txt",
                        data=draft_text,
                        file_name=f"{row['name'].replace(' ', '_')}.txt",
                        key=f"dl_{row['name']}",
                    )

# ── All contacts table ───────────────────────────────────────────────────────

with st.expander("All Contacts"):
    all_display = df[["status", "name", "deal_stage", "last_contact_days_ago", "property_interest", "budget"]].rename(
        columns={
            "status": "",
            "name": "Name",
            "deal_stage": "Stage",
            "last_contact_days_ago": "Days Ago",
            "property_interest": "Interest",
            "budget": "Budget ($)",
        }
    )
    st.dataframe(all_display, use_container_width=True, hide_index=True)
