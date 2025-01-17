import logging
import os
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from prometheus_client import Counter, Summary, start_http_server
from starlette_exporter import PrometheusMiddleware, handle_metrics
import requests
from fastapi import status
from .database import SessionLocal, engine, Base
from .models import Weather
from typing import Generator

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Metrics
REQUEST_COUNT = Counter("request_count", "Total number of requests")
REQUEST_LATENCY = Summary("request_latency_seconds", "Latency of HTTP requests in seconds")

app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", handle_metrics)

# Dependency
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

OPENWEATHER_API_KEY = os.environ.get("OPENWEATHERMAP_API_KEY")
if not OPENWEATHER_API_KEY:
    raise RuntimeError("OPENWEATHERMAP_API_KEY environment variable is not set.")

BASE_URL = "http://api.openweathermap.org/data/2.5/weather"

@app.on_event("startup")
def startup_event():
    start_http_server(8001)

@app.post("/weather/", response_model=dict, status_code=status.HTTP_200_OK)
async def get_weather(city: str, db: Session = Depends(get_db)): # async def
    REQUEST_COUNT.inc()
    with REQUEST_LATENCY.time():
        weather_data = db.query(Weather).filter(Weather.city == city).first()
        if weather_data:
            logger.info(f"Weather data for {city} retrieved from database.")
            return {"city": weather_data.city, "temperature": weather_data.temperature}

        params = {"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric"}
        try:
            response = await requests.get(BASE_URL, params=params) # await
            response.raise_for_status() # Генерирует исключение для плохого статуса
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching weather data for {city}: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching weather data: {e}")

        weather_info = response.json()
        temperature = weather_info["main"]["temp"]

        new_weather = Weather(city=city, temperature=temperature)
        db.add(new_weather)
        db.commit()
        db.refresh(new_weather)

        logger.info(f"Weather data for {city} fetched from API and saved to database.")
        return {"city": new_weather.city, "temperature": new_weather.temperature}