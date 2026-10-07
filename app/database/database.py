from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

# For SQLite, we need connect_args={"check_same_thread": False}
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get db session in FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from sqlalchemy import text

def init_db():
    Base.metadata.create_all(bind=engine)
    if settings.DATABASE_URL.startswith("sqlite"):
        with engine.connect() as conn:
            # whatsapp_events table check
            cursor = conn.execute(text("PRAGMA table_info(whatsapp_events)"))
            columns = [row[1] for row in cursor.fetchall()]
            if columns:
                new_cols = {
                    "provider": "VARCHAR DEFAULT 'telegram'",
                    "event_type": "VARCHAR",
                    "recipient": "VARCHAR",
                    "phone_number": "VARCHAR",
                    "message_type": "VARCHAR",
                    "message": "TEXT",
                    "content": "TEXT",
                    "status": "VARCHAR DEFAULT 'PENDING'",
                    "provider_message_id": "VARCHAR",
                    "error_message": "TEXT",
                    "sent_at": "DATETIME",
                    "created_at": "DATETIME",
                    "updated_at": "DATETIME"
                }
                for col_name, col_type in new_cols.items():
                    if col_name not in columns:
                        conn.execute(text(f"ALTER TABLE whatsapp_events ADD COLUMN {col_name} {col_type}"))

            # calls table check
            cursor_calls = conn.execute(text("PRAGMA table_info(calls)"))
            call_cols = [row[1] for row in cursor_calls.fetchall()]
            if call_cols and "detected_language" not in call_cols:
                conn.execute(text("ALTER TABLE calls ADD COLUMN detected_language VARCHAR"))

            # transcripts table check
            cursor_tx = conn.execute(text("PRAGMA table_info(transcripts)"))
            tx_cols = [row[1] for row in cursor_tx.fetchall()]
            if tx_cols and "language" not in tx_cols:
                conn.execute(text("ALTER TABLE transcripts ADD COLUMN language VARCHAR"))

            conn.commit()

