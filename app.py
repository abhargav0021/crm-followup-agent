import os
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv
from groq import Groq

from database import ensure_seed_data

CONFIG = {
    "hot_warm_threshold": 30,
    "cold_threshold": 60,
    "active_threshold": 14,
}

THRESHOLD_HOT_WARM = CONFIG["hot_warm_threshold"]
THRESHOLD_COLD = CONFIG["cold_threshold"]
THRESHOLD_ACTIVE_DEAL = CONFIG["active_threshold"]

load_dotenv()

DRAFTS_DIR = Path(__file__).parent / "drafts"
API_URL = "http://127.0.0.1:8000/contacts"
MODEL = "llama-3.3-70b-versatile"

LEAD_LABELS = {
    "Hot Lead": "Hot Lead",
    "Warm Lead": "Warm Lead",
    "Cold Lead": "Cold Lead",
    "Active Deal": "Active Lead",
    "Lost": "Lost",
}

REQUIRED_COLUMNS = [
    "name",
    "deal_stage",
    "last_contact_days_ago",
    "property_interest",
    "budget",
    "notes",
]


def get_default_api_key() -> str:
    env_key = os.getenv("GROQ_API_KEY", "")
    if env_key:
        return env_key

    try:
        return st.secrets.get("GROQ_API_KEY", "")
    except (FileNotFoundError, KeyError):
        return ""


def is_streamlit_cloud() -> bool:
    return (
        os.getenv("STREAMLIT_CLOUD", "").lower() == "true"
        or os.getenv("STREAMLIT_SHARING_MODE", "").lower() == "streamlit_cloud"
        or str(Path.home()) == "/home/appuser"
    )


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


def label_contact(row: pd.Series) -> str:
    return LEAD_LABELS.get(row["deal_stage"], row["deal_stage"])


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


def load_contacts(uploaded, use_api: bool) -> pd.DataFrame:
    if uploaded:
        return pd.read_csv(uploaded)

    if use_api and not is_streamlit_cloud():
        try:
            response = requests.get(API_URL, timeout=2)
            response.raise_for_status()
            return pd.DataFrame(response.json())
        except requests.RequestException:
            pass

    return ensure_seed_data()


def stream_email(contact: pd.Series, api_key: str) -> str:
    client = Groq(api_key=api_key)
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
    path = DRAFTS_DIR / f"{name.replace(' ', '_')}.txt"
    path.write_text(content)
    return path


st.set_page_config(page_title="CRM Follow-up Agent", layout="wide")
st.title("CRM Follow-up Agent")
st.caption("AI-powered outreach for Tulsa real estate contacts")

with st.sidebar:
    st.header("Settings")

    api_key = st.text_input(
        "Groq API Key",
        value=get_default_api_key(),
        type="password",
        help="Loaded from Streamlit secrets or .env if present",
    )
    st.caption(f"Model: `{MODEL}`")

    st.divider()
    st.header("Data Source")
    uploaded = st.file_uploader("Upload a contacts CSV", type="csv")
    if is_streamlit_cloud():
        use_api = False
    else:
        use_api = st.checkbox(
            "Use local FastAPI server",
            value=False,
            help="For local development only. Streamlit Cloud uses upload or the seeded SQLite data.",
        )

    st.divider()
    st.markdown(
        "**Thresholds**\n"
        f"- Hot/Warm leads: >{THRESHOLD_HOT_WARM} days\n"
        f"- Cold leads: >{THRESHOLD_COLD} days\n"
        f"- Active Deal: >{THRESHOLD_ACTIVE_DEAL} days"
    )

df = load_contacts(uploaded, use_api)

if df.empty:
    st.warning("No contacts loaded.")
    st.stop()

missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
if missing:
    st.error(f"Missing columns: {missing}")
    st.stop()

df = df.copy()
df["action"] = df.apply(classify_contact, axis=1)
df["lead_label"] = df.apply(label_contact, axis=1)

flagged_df = df[df["action"].notna()].reset_index(drop=True)
ok_df = df[df["action"].isna() & (df["deal_stage"] != "Lost")].reset_index(drop=True)
lost_df = df[df["deal_stage"] == "Lost"].reset_index(drop=True)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Contacts", len(df))
col2.metric("Need Action", len(flagged_df))
col3.metric("Up to Date", len(ok_df))
col4.metric("Lost", len(lost_df))

st.divider()
st.subheader("Contacts Needing Action")

if flagged_df.empty:
    st.success("All contacts are up to date.")
else:
    display_cols = [
        "lead_label",
        "name",
        "deal_stage",
        "last_contact_days_ago",
        "property_interest",
        "budget",
        "action",
    ]
    st.dataframe(
        flagged_df[display_cols].rename(
            columns={
                "lead_label": "Lead Label",
                "name": "Name",
                "deal_stage": "Stage",
                "last_contact_days_ago": "Days Ago",
                "property_interest": "Interest",
                "budget": "Budget ($)",
                "action": "Action",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.subheader("Generate Email Drafts")

    if not api_key:
        st.error("Enter your Groq API key in the sidebar to generate drafts.")
    else:
        if "drafts" not in st.session_state:
            st.session_state.drafts = {}

        if st.button("Generate All Drafts", type="primary"):
            progress = st.progress(0, text="Starting...")
            for index, (_, row) in enumerate(flagged_df.iterrows(), start=1):
                progress.progress(index / len(flagged_df), text=f"Drafting email for {row['name']}...")
                with st.spinner(f"Writing email for {row['name']}..."):
                    draft = stream_email(row, api_key)
                st.session_state.drafts[row["name"]] = draft
                save_draft(row["name"], draft)
            st.success(f"Generated {len(flagged_df)} draft(s). Saved to drafts/")

        st.caption("Or generate drafts one at a time:")
        for _, row in flagged_df.iterrows():
            with st.expander(
                f"{row['lead_label']} - {row['name']} - "
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
                            draft = stream_email(row, api_key)
                        st.session_state.drafts[row["name"]] = draft
                        save_draft(row["name"], draft)

                if row["name"] in st.session_state.drafts:
                    draft_text = st.session_state.drafts[row["name"]]
                    st.text_area("Draft", value=draft_text, height=260, key=f"draft_{row['name']}")
                    st.download_button(
                        "Download .txt",
                        data=draft_text,
                        file_name=f"{row['name'].replace(' ', '_')}.txt",
                        key=f"dl_{row['name']}",
                    )

with st.expander("All Contacts"):
    all_display = df[
        ["lead_label", "name", "deal_stage", "last_contact_days_ago", "property_interest", "budget"]
    ].rename(
        columns={
            "lead_label": "Lead Label",
            "name": "Name",
            "deal_stage": "Stage",
            "last_contact_days_ago": "Days Ago",
            "property_interest": "Interest",
            "budget": "Budget ($)",
        }
    )
    st.dataframe(all_display, use_container_width=True, hide_index=True)
