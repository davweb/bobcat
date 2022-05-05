"""Manage database via SQLAchemy"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

_SESSION_MAKER = None

Base = declarative_base()


def _initialise_database():
    """Use SQLAlchemy to initialise the database"""

    global _SESSION_MAKER

    # We need to make sure all models have been imported at least one before
    # creating the DB so we have all the metadata.
    engine = create_engine('sqlite:///bobcat.db', echo=False)
    _SESSION_MAKER = sessionmaker(engine)
    Base.metadata.create_all(engine)


def make_session():
    """Return an SQLAchmemy session"""

    if _SESSION_MAKER is None:
        _initialise_database()

    return _SESSION_MAKER()
