"""Manage database via SQLAchemy"""

import logging
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

_DATABASE_NAME = 'bobcat.db'
_SESSION_MAKER = None

Base = declarative_base()


def _initialise_database():
    """Use SQLAlchemy to initialise the database"""

    global _SESSION_MAKER

    database_dir = os.environ.get('DATABASE_DIRECTORY')

    if database_dir is None:
        logging.error('DATABASE_DIRECTORY not specified')
        sys.exit(1)

    database_path = f'{database_dir}/{_DATABASE_NAME}'
    logging.debug('Database is %s', database_path)

    #  We need to make sure all models have been imported at least once before
    # creating the DB so we have all the metadata.
    engine = create_engine(f'sqlite:///{database_path}', echo=False)
    _SESSION_MAKER = sessionmaker(engine)
    Base.metadata.create_all(engine)


def make_session():
    """Return an SQLAchmemy session"""

    if _SESSION_MAKER is None:
        _initialise_database()

    return _SESSION_MAKER()
