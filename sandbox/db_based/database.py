from typing import Optional

from sqlmodel import Field, Session, SQLModel, create_engine, select, Relationship
from sqlalchemy import BigInteger, asc
from sqlalchemy.orm import load_only
from streamlit.runtime.uploaded_file_manager import UploadedFile


class User(SQLModel, table=True):
    id: int = Field(primary_key=True, sa_type=BigInteger)
    email: str = Field(default="")
    key: str = Field(default="")
    step_id: int = Field(foreign_key="step.id", default=None)
    current_step: "Step" = Relationship(back_populates="users")


class File(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    filename: str
    data: bytes
    step_id: int = Field(foreign_key="step.id", default=None)
    step: "Step" = Relationship(back_populates="files")


class Step(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    order: int = Field(default=0)
    name: str = Field(default="")
    step_text: str = Field(default="")
    files: list[File] = Relationship(back_populates="step")
    users: list[User] = Relationship(back_populates="current_step")


db_url = "sqlite:///database.db"
engine = create_engine(db_url)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_all_steps() -> list[Step]:
    with Session(engine) as session:
        steps = session.exec(select(Step).order_by(Step.order)).all()  # type: ignore
        return list(steps)


def update_step(step_id: int, name: str, text: str) -> None:
    with Session(engine) as session:
        step = session.get(Step, step_id)
        if step:
            step.name = name
            step.step_text = text
            session.add(step)
            session.commit()


def get_files(step_id: int) -> list[File]:
    with Session(engine) as session:
        # load only metadata (id, filename, step_id) to avoid loading large
        # `data` blobs into memory when listing files.
        files = session.exec(
            select(File)
            .options(load_only(File.id, File.filename, File.step_id))
            .where(File.step_id == step_id)
        ).all()
        return list(files)


def get_file_data(file_id: int) -> Optional[bytes]:
    """Return raw file bytes for a single file. This loads the `data` column.

    Use this only when the user requests the file (download/view), not when
    listing files.
    """
    with Session(engine) as session:
        file = session.get(File, file_id)
        if file:
            return file.data
        return None


def add_files(step_id: int, files: list[UploadedFile]) -> None:
    with Session(engine) as session:
        step = session.get(Step, step_id)
        if step:
            for file in files:
                file_data = file.read()
                file_record = File(
                    filename=file.name,
                    data=file_data,
                    step_id=step_id,
                )
                session.add(file_record)
                step.files.append(file_record)
            session.commit()


def delete_file(file_id: int) -> None:
    with Session(engine) as session:
        file = session.get(File, file_id)
        if file:
            session.delete(file)
            session.commit()


def add_step(
    order: int,
    name: str = "",
    text: str = "",
    files: list[UploadedFile] = [],
) -> None:
    with Session(engine) as session:
        step = Step(order=order, name=name, step_text=text)
        session.add(step)
        for file in files:
            file_data = file.read()
            file_record = File(
                filename=file.name,
                data=file_data,
            )
            session.add(file_record)
            step.files.append(file_record)
        session.commit()
