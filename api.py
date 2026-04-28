import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from database import CONTACT_COLUMNS, ensure_seed_data, insert_contacts, load_data


class Contact(BaseModel):
    name: str
    email: str = ""
    phone: str = ""
    property_interest: str
    budget: int
    last_contact_days_ago: int
    deal_stage: str
    notes: str = ""

app = FastAPI()

@app.get("/")
def home():
    return {"message": "CRM API running"}

@app.get("/contacts")
def get_contacts():
    df = ensure_seed_data()
    return df.to_dict(orient="records")


@app.put("/contacts")
def replace_contacts(contacts: list[Contact]):
    try:
        df = pd.DataFrame([contact.model_dump() for contact in contacts])
        insert_contacts(df)
        return {"message": "Contacts replaced", "count": len(contacts)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/contacts")
def add_contact(contact: Contact):
    df = load_data()
    next_row = pd.DataFrame([contact.model_dump()])
    combined = pd.concat([df, next_row], ignore_index=True)
    insert_contacts(combined[CONTACT_COLUMNS])
    return {"message": "Contact added", "contact": contact.model_dump()}
