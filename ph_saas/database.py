"""
database.py — Configuración de SQLAlchemy + sesión de base de datos.
Fuerza timezone America/Bogota en cada conexión para evitar desfase UTC.
"""

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from ph_saas.config import settings


# ── Engine ─────────────────────────────────────────────────────────────────────
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,          # Detecta conexiones caídas
    pool_size=10,
    max_overflow=20,
)


# ── Forzar timezone Bogotá en cada nueva conexión ──────────────────────────────
@event.listens_for(engine, "connect")
def set_timezone(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("SET timezone = 'America/Bogota'")
    cursor.close()


# ── Fábrica de sesiones ────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ── Dependencia FastAPI: get_db() ──────────────────────────────────────────────
def get_db() -> Session:
    """
    Generador de sesión de base de datos para inyección de dependencias.
    Uso en routers:
        @router.get("/")
        def mi_endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
