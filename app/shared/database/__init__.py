# app/shared/database/__init__.py
from . import core
from . import setup
from . import users
from . import containers
from . import items
from . import auth
from . import automation

# Expose core connection logic if needed
from .core import get_db_connection
