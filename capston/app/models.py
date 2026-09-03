import datetime
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    widgets = relationship("Widget", back_populates="owner", cascade="all, delete-orphan")

class Widget(Base):
    __tablename__ = "widgets"

    id = Column(String, primary_key=True, default=generate_uuid)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    widget_type = Column(String, nullable=False, default="signup") # signup, cta, popover
    button_text = Column(String, nullable=False, default="Submit")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    owner = relationship("User", back_populates="widgets")
    submissions = relationship("Submission", back_populates="widget", cascade="all, delete-orphan")

class Submission(Base):
    __tablename__ = "submissions"

    id = Column(String, primary_key=True, default=generate_uuid)
    widget_id = Column(String, ForeignKey("widgets.id"), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    ip_address = Column(String, nullable=True)
    geo_country = Column(String, nullable=True)
    geo_city = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    widget = relationship("Widget", back_populates="submissions")