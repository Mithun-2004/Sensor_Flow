import os
from dotenv import load_dotenv

load_dotenv()

POSTGRESQL_DATABASE_URL = os.getenv("POSTGRESQL_DATABASE_URL")

SECRET_KEY=os.getenv("SECRET_KEY")
ALGORITHM=os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES=os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")


