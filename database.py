from sqlalchemy import create_engine,Column,Integer,String
from sqlalchemy.orm import declarative_base,sessionmaker



DATABASE_URL="sqlite:///./o2c.db"

engine=create_engine(DATABASE_URL)
SessionLocal=sessionmaker(bind=engine)

Base=declarative_base()

class CustomerDB(Base):

    __tablename__="Customers"

    id=Column(Integer,primary_key=True,index=True)
    name=Column(String)
    country=Column(String)
    email=Column(String)

def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()

Base.metadata.create_all(bind=engine)