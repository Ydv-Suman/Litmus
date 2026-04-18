from fastapi import FastAPI

from routes.application_submission_service import application_submission_handler


app = FastAPI()

@app.get('/health')
def check_health():
    return {"Message": "Backend is running!!!!"}
app.include_router(application_submission_handler.router)
