from fastapi import FastAPI

app = FastAPI(title="SmartSchedule")


@app.get("/")
def root():
    return {"message": "SmartSchedule backend is running!"}