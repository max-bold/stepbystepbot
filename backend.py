from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from os import getenv
import json
import shutil

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine, select
from sqlalchemy import BigInteger


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


class LogRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, sa_type=BigInteger)
    level: str = Field(default="info")
    message: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class UserCreate(BaseModel):
    id: int
    current_step: int = 0
    payment_status: str = ""
    payment_key: str = ""
    payed: bool = False
    step_sent_time: float = 0.0
    next_step_invite_sent: bool = False
    upload_mode: bool = False
    is_admin: bool = False


class UserUpdate(BaseModel):
    current_step: Optional[int] = None
    payment_status: Optional[str] = None
    payment_key: Optional[str] = None
    payed: Optional[bool] = None
    step_sent_time: Optional[float] = None
    next_step_invite_sent: Optional[bool] = None
    upload_mode: Optional[bool] = None
    is_admin: Optional[bool] = None


class UserRead(BaseModel):
    id: int
    current_step: int
    payment_status: str
    payment_key: str
    payed: bool
    step_sent_time: float
    next_step_invite_sent: bool
    upload_mode: bool
    is_admin: bool


class LogCreate(BaseModel):
    user_id: Optional[int] = None
    level: str = "info"
    message: str


class LogRead(BaseModel):
    id: int
    user_id: Optional[int]
    level: str
    message: str
    created_at: datetime


load_dotenv()
db_url = getenv("DB_URL")
data_dir = Path(getenv("DATA_DIR", ".")).resolve()
default_settings_path = data_dir / "default_settings.json"
default_script_path = data_dir / "test_script.json"
settings_path = data_dir / "settings.json"
script_path = data_dir / "script.json"

if db_url is None:
    raise ValueError("DB_URL environment variable not set")


def ensure_data_files() -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    if not default_settings_path.exists():
        raise FileNotFoundError(
            f"Default settings file not found: {default_settings_path}"
        )
    if not default_script_path.exists():
        raise FileNotFoundError(
            f"Default script file not found: {default_script_path}"
        )
    if not settings_path.exists():
        shutil.copyfile(default_settings_path, settings_path)
    if not script_path.exists():
        shutil.copyfile(default_script_path, script_path)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=4, ensure_ascii=False)


engine = create_engine(db_url)
app = FastAPI(title="StepByStepBot Backend")


@app.on_event("startup")
def on_startup() -> None:
    ensure_data_files()
    SQLModel.metadata.create_all(engine)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/settings")
def get_settings() -> dict[str, Any]:
    return load_json(settings_path)


@app.put("/settings")
def update_settings(payload: dict[str, Any]) -> dict[str, str]:
    save_json(settings_path, payload)
    return {"status": "saved"}


@app.get("/script")
def get_script() -> list[dict[str, Any]]:
    payload = load_json(script_path)
    if not isinstance(payload, list):
        raise HTTPException(status_code=500, detail="Script is not a list")
    return payload


@app.put("/script")
def update_script(payload: list[dict[str, Any]]) -> dict[str, str]:
    save_json(script_path, payload)
    return {"status": "saved"}


@app.get("/users")
def list_users(
    is_admin: Optional[bool] = None,
    payed: Optional[bool] = None,
    payment_status: Optional[str] = None,
    next_step_invite_sent: Optional[bool] = None,
    current_step_lt: Optional[int] = None,
    current_step_eq: Optional[int] = None,
    step_sent_time_lt: Optional[float] = None,
) -> list[UserRead]:
    with Session(engine) as session:
        statement = select(User)
        if is_admin is not None:
            statement = statement.where(User.is_admin == is_admin)
        if payed is not None:
            statement = statement.where(User.payed == payed)
        if payment_status is not None:
            statement = statement.where(User.payment_status == payment_status)
        if next_step_invite_sent is not None:
            statement = statement.where(
                User.next_step_invite_sent == next_step_invite_sent
            )
        if current_step_lt is not None:
            statement = statement.where(User.current_step < current_step_lt)
        if current_step_eq is not None:
            statement = statement.where(User.current_step == current_step_eq)
        if step_sent_time_lt is not None:
            statement = statement.where(User.step_sent_time < step_sent_time_lt)
        users = session.exec(statement).all()
        return [UserRead(**user.dict()) for user in users]


@app.post("/users")
def create_user(payload: UserCreate) -> UserRead:
    with Session(engine) as session:
        existing = session.get(User, payload.id)
        if existing:
            return UserRead(**existing.dict())
        user = User(**payload.dict())
        session.add(user)
        session.commit()
        session.refresh(user)
        return UserRead(**user.dict())


@app.get("/users/{user_id}")
def get_user(user_id: int) -> UserRead:
    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return UserRead(**user.dict())


@app.patch("/users/{user_id}")
def update_user(user_id: int, payload: UserUpdate) -> UserRead:
    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        update_data = payload.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        session.add(user)
        session.commit()
        session.refresh(user)
        return UserRead(**user.dict())


@app.delete("/users/{user_id}")
def delete_user(user_id: int) -> dict[str, str]:
    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        session.delete(user)
        session.commit()
        return {"status": "deleted"}


@app.post("/logs")
def create_log(payload: LogCreate) -> LogRead:
    with Session(engine) as session:
        log = LogRecord(**payload.dict())
        session.add(log)
        session.commit()
        session.refresh(log)
        return LogRead(
            id=log.id,
            user_id=log.user_id,
            level=log.level,
            message=log.message,
            created_at=log.created_at,
        )


@app.get("/logs")
def list_logs(
    user_id: Optional[int] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[LogRead]:
    with Session(engine) as session:
        statement = select(LogRecord)
        if user_id is not None:
            statement = statement.where(LogRecord.user_id == user_id)
        logs = session.exec(
            statement.order_by(LogRecord.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return [
            LogRead(
                id=log.id,
                user_id=log.user_id,
                level=log.level,
                message=log.message,
                created_at=log.created_at,
            )
            for log in logs
        ]
