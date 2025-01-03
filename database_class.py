from sqlalchemy import create_engine, Column, Integer, String, Float, Date, Time
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class TransactionEntry(Base):
    __tablename__ = "transaktion"

    id = Column(Integer, primary_key=True, autoincrement=True)

    datum = Column(Date, nullable=False)
    zeit = Column(Time, nullable=False)
    summe = Column(Float, nullable=False)
    empfänger = Column(String, nullable=False)
    auftraggeber = Column(String, nullable=False)
    zahlungsart = Column(String, nullable=False)
    verwendungszweck = Column(String, nullable=False)
    gebühren = Column(Float, nullable=False)
    bankfiliale = Column(String, nullable=False)

    ausgabenkategorie = Column(String, nullable=False)


def get_engine(db_url="sqlite:///bank_statements.db"):
    return create_engine(db_url)


def create_tables(engine):
    Base.metadata.create_all(engine)


def get_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()
