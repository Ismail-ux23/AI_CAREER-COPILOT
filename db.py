import certifi
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = (
    "mysql+pymysql://38DFJLJN9vArz8q.root:UVpUkfrThDH0gdoY@"
    "gateway01.ap-northeast-1.prod.aws.tidbcloud.com:4000/test"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={
        "ssl": {
            "ca": certifi.where(),
            "check_hostname": True,
        }
    },
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()