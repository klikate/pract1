from sqlalchemy import Column, Integer, String, Float
from .database import Base

class Weather(Base):
    __tablename__ = "weather" 

    id = Column(Integer, primary_key=True, index=True)
    city = Column(String, index=True, nullable=False, unique=True)
    temperature = Column(Float, nullable=False)

