import sys
import os

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.db.connection import engine, SessionLocal, Base
from src.db.seed_data import seed_database


def init_db():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")

    print("Seeding synthetic AML alerts and transaction history...")
    db = SessionLocal()
    try:
        count = seed_database(db)
        print(f"Successfully seeded {count} AML alerts with associated accounts and transactions.")
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
