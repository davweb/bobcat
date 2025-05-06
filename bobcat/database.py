"""Manage database via SQLAlchemy"""

import logging
from typing import Final
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from .config import CONFIG

_DATABASE_NAME: Final = 'bobcat.db'
_SESSION_MAKER = None

# pylint: disable=too-few-public-methods


class Base(DeclarativeBase):
    """SQLAlchemy boilerplate"""


def _initialise_database() -> sessionmaker:
    """Use SQLAlchemy to initialise the database"""

    database_path = f'{CONFIG.database_dir}/{_DATABASE_NAME}'
    logging.debug('Database is %s', database_path)

    # We need to make sure all models have been imported at least once before
    # creating the DB so we have all the metadata.
    engine = create_engine(f'sqlite:///{database_path}', echo=False)
    session_maker = sessionmaker(engine)
    Base.metadata.create_all(engine)
    return session_maker


def make_session() -> Session:
    """Return an SQLAlchemy session"""

    global _SESSION_MAKER

    if _SESSION_MAKER is None:
        _SESSION_MAKER = _initialise_database()

    return _SESSION_MAKER()
