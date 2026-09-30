from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.models import Base

SQLALCHEMY_DATABASE_URL = "postgresql+psycopg2://itsm_user:itsm_password@127.0.0.1:5432/itsm_db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully!")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()