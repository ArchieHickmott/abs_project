import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, Table, MetaData, select, inspect
from sqlalchemy import Column, text, insert
from sqlalchemy.orm import Session

load_dotenv()

engine = create_engine(
    os.environ["DATABASE_URL"]
)

inspector = inspect(engine)

print(inspector.get_table_names())

with engine.begin() as session:
    print(session.execute(text("""
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE lower(table_name) = lower('G13A_SA1');
    """)).fetchall())

    print(session.execute(text("SHOW search_path;")).fetchall())
