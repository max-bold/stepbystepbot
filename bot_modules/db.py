from os import getenv

from dotenv import load_dotenv
from sqlalchemy import BigInteger
from sqlmodel import SQLModel, Field, create_engine

load_dotenv()

db_url = getenv("DB_URL")

if db_url is None:
    raise ValueError("DB_URL environment variable not set")
engine = create_engine(db_url)


class User(SQLModel, table=True):
    id: int = Field(primary_key=True, sa_type=BigInteger)
    current_step: int = Field(default=0)
    payment_status: str = Field(default="")
    payment_key: str = Field(default="")
    payed: bool = Field(default=False)
    step_sent_time: float = Field(default=0.0)
    next_step_invite_sent: bool = Field(default=False)
    upload_mode: bool = Field(default=False)
    is_admin: bool = Field(default=False)
    email: str = Field(default="")
