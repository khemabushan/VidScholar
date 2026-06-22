"""
VidScholar Backend - SQLAlchemy Declarative Base
================================================
Defines the single Base class that every ORM model in app/db/models/
must inherit from. Kept in its own tiny module (rather than inside
session.py) to avoid circular imports: models need to import Base,
and session.py needs to import models' metadata for create_all().
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all VidScholar ORM models."""
    pass
