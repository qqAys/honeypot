import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Optional

import uvicorn
from fastapi import FastAPI, Request, Form, Depends, status
from fastapi.background import BackgroundTasks
from fastapi.responses import HTMLResponse, Response
from jinja2 import Template
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlmodel import SQLModel, Field, Column, JSON
from sqlmodel import create_engine, Session

project_root = Path(__file__).parent


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HP_",
        env_file_encoding="utf-8",
    )

    PROJECT_NAME: str = "HoneyPot"

    MAX_VALUE_LENGTH: int = 100

    DATABASE_TYPE: str
    DATABASE_HOST: str
    DATABASE_PORT: int
    DATABASE_USER: str
    DATABASE_PASSWORD: str
    DATABASE_NAME: str

    LOG_LEVEL: str = "DEBUG"

    @property
    def DATABASE_DSN(self) -> str:
        return f"{self.DATABASE_TYPE}+pymysql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"


config = Config()


class Logger:
    def __init__(self):
        log_path = Path(project_root / "logs")
        log_path.mkdir(parents=True, exist_ok=True)

        log_file = Path(log_path / "app.log")
        self.logger = logging.getLogger(config.PROJECT_NAME)
        self.logger.setLevel(config.LOG_LEVEL.upper())

        formatter = logging.Formatter(
            '{"level": "%(levelname)s", "time": "%(asctime)s", "file": "%(filename)s", "line": %(lineno)d, "message": "%(message)s"}'
        )

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        self._configure_uvicorn_loggers(
            file_handler, console_handler, config.LOG_LEVEL.upper()
        )

    @staticmethod
    def _configure_uvicorn_loggers(file_handler, console_handler, level):
        uvicorn_logger = logging.getLogger("uvicorn")
        uvicorn_logger.handlers = []
        uvicorn_logger.setLevel(level)

        formatter = logging.Formatter(
            '{"level": "%(levelname)s", "time": "%(asctime)s", "file": "%(filename)s", "line": %(lineno)d, "message": "%(message)s"}'
        )

        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        uvicorn_logger.addHandler(file_handler)
        uvicorn_logger.addHandler(console_handler)

        def custom_log(message: str, *args, **kwargs):
            expanded_message = Logger._expand_message(message)
            uvicorn_logger._log(logging.INFO, expanded_message, args, **kwargs)

        uvicorn_logger.info = custom_log

    @staticmethod
    def _expand_message(message: str) -> str:
        return str(message).replace("\n", "[NEWLINE]").replace('"', "'")

    def debug(self, message: str) -> None:
        self.logger.debug(self._expand_message(message), stacklevel=2)

    def info(self, message: str) -> None:
        self.logger.info(self._expand_message(message), stacklevel=2)

    def warning(self, message: str) -> None:
        self.logger.warning(self._expand_message(message), stacklevel=2)

    def error(self, message: str) -> None:
        self.logger.error(self._expand_message(message), stacklevel=2)


logger = Logger()

engine = create_engine(
    config.DATABASE_DSN,
    echo=True if config.LOG_LEVEL.upper() == "DEBUG" else False,
    json_serializer=lambda v: json.dumps(v, ensure_ascii=False),
    json_deserializer=lambda s: json.loads(s),
)


class ActivityLog(SQLModel, table=True):
    __tablename__ = "activity_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    action: str = Field(max_length=255, nullable=False)

    data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, server_default="{}"),
    )

    ip_address: Optional[str] = Field(max_length=255, nullable=True)
    user_agent: Optional[str] = Field(max_length=255, nullable=True)
    timestamp: datetime = Field(default_factory=datetime.now)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


def get_session():
    with Session(engine) as session:
        yield session


def render_html_template(template_name: str, context: dict[str, Any] = None) -> str:
    template_str = (Path(__file__).parent / "templates" / template_name).read_text()
    if context is None:
        context = {}
    html_content = Template(template_str).render(context)
    return html_content


def log_activity(
    session: Session,
    action: str,
    ip: str,
    ua: str,
    data: dict = None,
):
    log = ActivityLog(
        action=action,
        data=data,
        ip_address=ip,
        user_agent=ua,
    )
    session.add(log)
    session.commit()


def handle_background_task(session: Session, request: Request, action: str, data: dict):
    ip = request.headers.get("X-Real-IP", request.client.host)
    ua = request.headers.get("user-agent", None)

    length_attack_data = {}

    for k, v in data.items():
        v_length = len(v)
        if v_length > config.MAX_VALUE_LENGTH:
            length_attack_data[k + "_length"] = v_length

    if length_attack_data:
        length_attack_data.update(
            {k: v for k, v in data.items() if k + "_length" not in length_attack_data}
        )
        logger.warning(
            f"IP: {ip} 存在长度攻击, 字段长度: {length_attack_data}, ua: {ua}"
        )
        log_activity(
            session,
            action=f"{action}_length_attack",
            ip=ip,
            ua=ua,
            data=length_attack_data,
        )
        return

    log_activity(session, action=action, ip=ip, ua=ua, data=data)


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)


@app.get("/", response_class=HTMLResponse)
def home():
    return render_html_template("home.j2")


@app.post("/login", response_class=Response)
def login(
    request: Request,
    background_tasks: BackgroundTasks,
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    data = {
        "email": email,
        "password": password,
    }
    background_tasks.add_task(handle_background_task, session, request, "login", data)
    return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


@app.post("/register", response_class=Response)
def register(
    request: Request,
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    phone: str = Form(...),
    city: str = Form(...),
    session: Session = Depends(get_session),
):
    data = {
        "name": name,
        "phone": phone,
        "city": city,
    }
    background_tasks.add_task(
        handle_background_task, session, request, "register", data
    )
    return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8200, log_config=None)
