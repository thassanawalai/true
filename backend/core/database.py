import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
from sqlalchemy.engine import make_url
from core.deployment import hosted

env_path = Path(__file__).resolve().parent.parent / ".env"
if not hosted():
    load_dotenv(dotenv_path=env_path)

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL or not SQLALCHEMY_DATABASE_URL.strip():
    raise ValueError("DATABASE_URL is required; set it in the service environment.")
if SQLALCHEMY_DATABASE_URL.startswith('postgres://'):
    SQLALCHEMY_DATABASE_URL = 'postgresql://' + SQLALCHEMY_DATABASE_URL[len('postgres://'):]
if SQLALCHEMY_DATABASE_URL.startswith('postgresql://'):
    # SQLAlchemy 2.1 defaults to psycopg v3; the demo explicitly ships psycopg2.
    SQLALCHEMY_DATABASE_URL = 'postgresql+psycopg2://' + SQLALCHEMY_DATABASE_URL[len('postgresql://'):]
try:
    database_url = make_url(SQLALCHEMY_DATABASE_URL)
except Exception:
    raise ValueError('DATABASE_URL must be a valid SQLAlchemy PostgreSQL URL.') from None
if hosted() and (database_url.get_backend_name() != 'postgresql' or not database_url.host
                 or database_url.host.lower() in {'localhost', '127.0.0.1', '::1', '0.0.0.0'}):
    raise ValueError('Hosted demo requires a remote PostgreSQL DATABASE_URL, not localhost or SQLite.')

options = {'pool_pre_ping': True}
if database_url.get_backend_name() == 'postgresql':
    options.update(pool_size=3, max_overflow=2, pool_timeout=10,
                   connect_args={'connect_timeout': 10})
engine = create_engine(database_url, **options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
