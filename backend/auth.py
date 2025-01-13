from datetime import timedelta, datetime
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Users, Channels, Fields, API, DataReading
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError

from constants import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_bearer = OAuth2PasswordBearer(tokenUrl="auth/token")

class CreateUserRequest(BaseModel):
    username: str
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def authenticate_user(username: str, password: str, db):
    user = db.query(Users).filter(Users.username == username).first()
    if not user:
        return False
    if not bcrypt_context.verify(password, user.hashed_password):
        return False
    return user

def create_access_token(username: str, user_id: int, expires_delta=timedelta):
    encode = {'sub': username, 'id': user_id}
    expires = datetime.utcnow() + expires_delta
    encode.update({"exp": expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: Annotated[str, Depends(oauth2_bearer)]):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: str = payload.get("id")
        if (username is None or user_id is None):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user.")
        return {"username": username, "id": user_id}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user")
    
    
db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(create_user_request: CreateUserRequest, db: db_dependency):
    create_user_model = Users(
        username=create_user_request.username,
        email=create_user_request.email,
        hashed_password=bcrypt_context.hash(create_user_request.password)
    )
    db.add(create_user_model)
    db.commit()

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: db_dependency):
    user = authenticate_user(form_data.username, form_data.password, db)

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user.")
    token = create_access_token(user.username, user.id, timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES)))

    return {"access_token": token, "token_type":"bearer"}

# Endpoint to delete user
@router.delete("/user", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(db: db_dependency, user: user_dependency, user_id: int=Query(..., description="User id to be deleted.")):
    if (user["id"] != user_id):
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="Method not allowed for different user.")
    
    user_records_to_delete = db.query(Users).filter(Users.id == user_id).all()
    if (user_records_to_delete is None):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    channel_records_to_delete = db.query(Channels).filter(Channels.user_id).all()
    api_records_to_delete = db.query(API).filter(API.user_id == user_id).all()

    field_records_to_delete = []
    data_reading_records_to_delete = []

    for channel in channel_records_to_delete:
        field_records_to_delete.append(db.query(Fields).filter(Fields.channel_id == channel.id).all())
        data_reading_records_to_delete.append(db.query(DataReading).filter(Fields.channel_id == channel.id).all())

    for record in data_reading_records_to_delete:
        db.delete(record)

    for record in field_records_to_delete:
        db.delete(record)

    for record in channel_records_to_delete:
        db.delete(record)
    
    for record in api_records_to_delete:
        db.delete(record)

    for record in user_records_to_delete:
        db.delete(record)

    db.commit()


