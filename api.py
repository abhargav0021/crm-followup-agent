from fastapi import FastAPI

from database import ensure_seed_data

app = FastAPI()

@app.get("/")
def home():
    return {"message": "CRM API running"}

@app.get("/contacts")
def get_contacts():
    df = ensure_seed_data()
    return df.to_dict(orient="records")
