"""Database configuration; credentials belong in the environment."""
import os
from pathlib import Path

import certifi
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()
instance = Path(__file__).resolve().parent / 'instance'
instance.mkdir(exist_ok=True)
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{instance / "copilot.db"}')
connect_args = {}
if make_url(DATABASE_URL).drivername == 'mysql+pymysql':
    connect_args['ssl'] = {'ca': certifi.where(), 'check_hostname': True}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()
