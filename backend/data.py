import uuid
from datetime import datetime, timedelta
from typing import Annotated, Optional, List, Literal
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Users, Channels, Fields, API, DataReading

from auth import get_current_user

router = APIRouter(
    prefix="/data",
    tags=['data']
)

class CreateChannel(BaseModel):
    user_id: int
    name: str
    description: Optional[str] = None

class Field(BaseModel):
    name:str
    description:Optional[str] = None
    units:Optional[str] = None

class AddFields(BaseModel):
    channel_id:int
    fields:List[Field]

class CreateAPIKey(BaseModel):
    user_id:int
    channel_id:int
    permissions:Literal['R','W']


class FieldOut(BaseModel):
    name:str
    description:str
    units:str

class ChannelOut(BaseModel):
    name:str
    description:str

class DataOut(BaseModel):
    id:int
    channel_id:int
    field_id:int
    value:float
    taken_at:datetime

    channel:ChannelOut
    field:FieldOut

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]

# def check_user(user_id):
#     loggedin_user = get_current_user()
#     if (loggedin_user.id == user_id):
#         return True
#     else:
#         return False


# Endpoint to create a channel. Channel names must be unique for every user.
@router.post("/create-channel", status_code=status.HTTP_201_CREATED)
async def createChannel(create_channel: CreateChannel, db: db_dependency, user: user_dependency):
    print(user)
    # if (check_user(create_channel.user_id) == False):
    #     raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="method not allowed for different user")
    if (user["id"] != create_channel.user_id):
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="method not allowed for different user")
    trimmed_name = create_channel.name.strip()
    exists = db.query(Channels).filter(
        Channels.user_id==create_channel.user_id, 
        func.lower(Channels.name)==func.lower(trimmed_name)
    ).first()
    if exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A channel with this name already exists."
        )
    else:
        create_channel_model = Channels(
            user_id=create_channel.user_id,
            name=func.lower(trimmed_name),
            description=create_channel.description
        )
        db.add(create_channel_model)
        db.commit()
        db.refresh(create_channel_model)

        api_key = str(uuid.uuid4())

        api_entry = API(
            api_key=api_key,
            user_id=create_channel.user_id,
            channel_id=create_channel_model.id,
            permissions="W"
        )
        db.add(api_entry)
        db.commit()

        return {"api_key": api_key, "permissions":"W"}
    
# Endpoint to create api key with required permissions
@router.post("/create-api-key", status_code=status.HTTP_201_CREATED)
async def createAPIKey(create_api_key: CreateAPIKey, db: db_dependency, user: user_dependency):
    if (user["id"] != create_api_key.user_id):
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="method not allowed for different user")
    channel = db.query(Channels).filter(Channels.user_id==create_api_key.user_id, Channels.id==create_api_key.channel_id).first()
    if channel:
        api_key = str(uuid.uuid4())

        api_entry = API(
            api_key=api_key,
            user_id=create_api_key.user_id,
            channel_id=create_api_key.channel_id,
            permissions=create_api_key.permissions
        )
        db.add(api_entry)
        db.commit()

        return {"api_key": api_key, "permissions":create_api_key.permissions}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel does not exist."
        )

# Endpoint to add fields to a channel. All fields must have unique name corresponding to a channel.
@router.put("/add-fields", status_code=status.HTTP_201_CREATED)
async def addFields(add_fields:AddFields, db: db_dependency, user: user_dependency):
    channel = db.query(Channels).filter(Channels.id==add_fields.channel_id).first()
    if (user["id"] != channel.user_id):
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="Method not allowed for different user.")
    create_fields = []
    exists = []
    for add_field in add_fields.fields:
        trimmed_name = add_field.name.strip()
        existing_field = db.query(Fields).filter(
            Fields.channel_id==add_fields.channel_id,
            func.lower(Fields.name)==func.lower(trimmed_name)
        ).first()

        if existing_field:
            exists.append(add_field)
        else:
            create_field = Fields(
                channel_id = add_fields.channel_id,
                name = func.lower(trimmed_name),
                description = add_field.description,
                units = add_field.units
            )
            create_fields.append(create_field)
            db.add(create_field)

    if create_fields:
        db.commit()

    if (len(create_fields) == 0):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fields cannot be created as they already exists."
        )
    
    response = {
        "Fields created": [field.name for field in create_fields],
        "Fields already exist": [field.name for field in exists]
    }

    return response



# Endpoint to put the data based on channel and fields mentioned.
@router.get("/update", status_code=status.HTTP_201_CREATED)
async def updateData(request:Request, db: db_dependency):
    query_params = request.query_params

    # Raise an exception if there is no api key
    api_key = query_params.get('api_key')
    if not api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="api_key is required")

    # Get all the fields
    fields_from_url = {k: v for k, v in query_params.items() if k != 'api_key'}
    fields = {}

    # Raise an exception if the field values are not float
    for key, value in fields_from_url.items():
        try:
            trimmed_field_name = key.strip().lower()
            print(trimmed_field_name, value)
            fields[trimmed_field_name] = float(value)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"value of field '{key}' must be float")
        except:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="error occured while verifying the fields.")    
        
    
    # Check for the channel
    api_result = db.query(API).filter(API.api_key==api_key).first()
    if api_result:
        # Raise an exception if the api key does not have write access
        if api_result.permissions == "R":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You don't have the access to write.")
        else:
            channel_id = api_result.channel_id
            fields_in_db = db.query(Fields).filter(Fields.channel_id == channel_id).all()

            # Convert fields_in_db to a dictionary for easy lookup
            fields_dict = {field.name: field.id for field in fields_in_db}

            # Check if all fields are present in the fields_in_db
            for field_name in fields.keys():
                if field_name not in fields_dict:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Entered field '{field_name}' is not present in the channel")

            # Now all the fields mentioned are present in the channel, so we can proceed entering it.
            response = {}
            response["channel_id"] = channel_id
            
            for field_name, value in fields.items():
                field_id = fields_dict[field_name]
                
                new_reading = DataReading(
                    channel_id=channel_id,
                    field_id=field_id,
                    value=value,
                    taken_at=func.now()
                ) 
                response[field_name] = value
                db.add(new_reading)
            
            db.commit()
            # response["added_time"] = func.now()
            return response

    # If there is no channel, raise an exception
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="There seems to be an error in API Key.")
    

# Endpoint to get all the channels based on user
@router.get("/channels", status_code=status.HTTP_200_OK)
async def getChannels(db: db_dependency, user: user_dependency, user_id: int = Query(..., description="User id for which the channels to be fetched")):
    if (user["id"] != user_id):
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="method not allowed for different user")
    result = db.query(Channels).filter(Channels.user_id == user_id).all()
    if result:
        return result
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="The user has no channel"
    )

# Endpoint to get all the api keys based on the channel and user
@router.get("/api-keys", status_code=status.HTTP_200_OK)
async def getAPIKeys(db: db_dependency, user: user_dependency, channel_id: int = Query(..., description="Channel id"), user_id: int = Query(..., description="User id of channel owner")):
    if (user["id"] != user_id):
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="method not allowed for different user")
    result = db.query(API).filter(API.channel_id==channel_id, API.user_id==user_id).all()
    if result:
        api_keys = []
        for key in result:
            api_keys.append({"api_key": key.api_key, "permissions":key.permissions})
        return api_keys
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Keys for specified channel and user is not found."
        )


# Endpoint to get all the fields based on channel
@router.get("/fields", status_code=status.HTTP_200_OK)
async def getFields(db: db_dependency, user: user_dependency, channel_id: int = Query(..., description="Channel id for which the fields needs to be fetched.")):
    channel = db.query(Channels).filter(Channels.id == channel_id).first()
    if (user["id"] != channel.user_id):
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="method not allowed for different user")
    fields = db.query(Fields).filter(Fields.channel_id == channel_id).all()
    if not fields:
       raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fields for the channel are not found.")
    else:
       return fields


# Endpoint to get all the data based on channel
@router.get("/read", status_code=status.HTTP_200_OK)
async def readData(db:db_dependency, user: user_dependency, channel_id:int=Query(..., description="Channel id for which the data needs to be read."), field_id:int=Query(None, description="Field for which the data needs to be fetched.")):
    channel = db.query(Channels).filter(Channels.id == channel_id).first()
    if (user["id"] != channel.user_id):
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="method not allowed for different user")
    if field_id:
        data_from_db = db.query(DataReading).filter(DataReading.channel_id==channel_id, DataReading.field_id==field_id).all()
    else:
        data_from_db = db.query(DataReading).filter(DataReading.channel_id==channel_id).all()
        
    if not data_from_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data is not available")
    
    
    response = {
        "channel": {
            "channel_id": data_from_db[0].channel_id,
            "channel_name": data_from_db[0].channel.name,
            "channel_description": data_from_db[0].channel.description
        },
        "fields": []
    }

    field_info = {}
    
    for data in data_from_db:
        field_id = data.field_id
        field = data.field

        if field_id not in field_info:
            field_info[field_id] = {
                "field_id": field.id,
                "field_name": field.name,
                "field_description": field.description,
                "field_units": field.units,
                "values": []
            }

        field_info[field_id]["values"].append({
            "value": data.value,
            "taken_at": data.taken_at
        })

    for field in field_info.values():
        field["values"].sort(key=lambda x: x["taken_at"], reverse=True)

    response["fields"] = list(field_info.values())

    return response


# Endpoint to delete channel
@router.delete("/channel", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel(db: db_dependency, user: user_dependency, channel_id: int = Query(..., description="Channel id for the channel that needs to be deleted.")):
    channel = db.query(Channels).filter(Channels.id == channel_id).first()
    if (channel is None):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found.")
    
    if (user["id"] != channel.user_id):
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="Method not allowed for different user.")
    api_records_to_delete = db.query(API).filter(API.channel_id == channel_id).all()
    field_records_to_delete = db.query(Fields).filter(Fields.channel_id == channel_id).all()
    data_reading_records_to_delete = db.query(DataReading).filter(DataReading.channel_id == channel_id).all()

    for record in api_records_to_delete:
        db.delete(record)

    for record in field_records_to_delete:
        db.delete(record)

    for record in data_reading_records_to_delete:
        db.delete(record)

    db.delete(channel)

    db.commit()


# Endpoint to delete a field in channel
@router.delete("/field", status_code=status.HTTP_204_NO_CONTENT)
async def delete_field(db: db_dependency, user: user_dependency, field_id: int = Query(..., description="field id for the field to be deleted."), channel_id: int = Query(..., description="channel id in which the to be deleted field is present.")):
    channel = db.query(Channels).filter(Channels.id == channel_id).first()
    if (channel is None):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found.")

    if (user["id"] != channel.user_id):
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="Method not allowed for different user.")
    
    field_record_to_delete = db.query(Fields).filter(Fields.id==field_id, Fields.channel_id==channel_id).first()
    if (field_record_to_delete is None):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found.")
    
    data_reading_records_to_delete = db.query(DataReading).filter(DataReading.channel_id == channel_id, DataReading.field_id == field_id).all()

    for record in data_reading_records_to_delete:
        db.delete(record)
    
    db.delete(field_record_to_delete)
    db.commit()