from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from database import Base

class Users(Base):
    __tablename__='users'

    id=Column(Integer, primary_key=True, index=True)
    username=Column(String, unique=True, nullable=False)
    email=Column(String, unique=True, nullable=False)
    hashed_password=Column(String, nullable=False)
    is_active=Column(Boolean, default=True)
    is_superuser=Column(Boolean, default=False)

