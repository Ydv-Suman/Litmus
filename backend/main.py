import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.application_submission_service import application_submission_handler
from routes.assessment_service import assessment_handler as assessment_view_handler
from routes.hr_auth_service import hr_auth_handler
from routes.job_listing_service import job_listing_handler


app = FastAPI()

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get('/health')
def check_health():
    return {"Message": "Backend is running!!!!"}
app.include_router(application_submission_handler.router)
app.include_router(assessment_view_handler.router)
app.include_router(hr_auth_handler.router)
app.include_router(job_listing_handler.router)
