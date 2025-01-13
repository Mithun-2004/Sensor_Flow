from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base

class Users(Base):
    __tablename__='users'

    id=Column(Integer, primary_key=True, index=True)
    username=Column(String, unique=True, nullable=False)
    email=Column(String, unique=True, nullable=False)
    hashed_password=Column(String, nullable=False)
    created_at=Column(DateTime(timezone=True), server_default=func.now())

class Channels(Base):
    __tablename__='channels'

    id=Column(Integer, primary_key=True, index=True)
    user_id=Column(Integer, ForeignKey("users.id"))
    name=Column(String, nullable=False)
    description=Column(String)
    created_at=Column(DateTime(timezone=True), server_default=func.now())
    updated_at=Column(DateTime(timezone=True), onupdate=func.now())

    user=relationship("Users")


class Fields(Base):
    __tablename__='fields'

    id=Column(Integer, primary_key=True, index=True)
    channel_id=Column(Integer, ForeignKey("channels.id"))
    name=Column(String, nullable=False, index=True)
    description=Column(String)
    units=Column(String, default="No Unit")

    channel=relationship("Channels")


class API(Base):
    __tablename__='api'

    id=Column(Integer, primary_key=True, index=True)
    api_key=Column(String, unique=True, index=True)
    user_id=Column(Integer, ForeignKey("users.id"))
    channel_id=Column(Integer, ForeignKey("channels.id"))
    permissions=Column(String, default="R")
    created_at=Column(DateTime(timezone=True), server_default=func.now())
    # expires_at=Column(DateTime(timezone=True))

    user=relationship("Users")
    channel=relationship("Channels")


class DataReading(Base):
    __tablename__='data_reading'

    id=Column(Integer, primary_key=True, index=True)
    channel_id=Column(Integer, ForeignKey("channels.id"))
    field_id=Column(Integer, ForeignKey("fields.id"))
    value=Column(Float, nullable=False)
    taken_at=Column(DateTime(timezone=True), server_default=func.now())

    channel=relationship("Channels")
    field=relationship("Fields")



    

