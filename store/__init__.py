"""Storage adapters implementing the ports in `core.repositories`.

`memory` backs tests and a throwaway run, `sqlite` a local demo that must
survive a restart, and `firestore` anything deployed -- Cloud Run replaces
containers freely, so a file on a container filesystem does not survive.

`firestore` is deliberately not imported here: it needs the `cloud` extra, and
importing it eagerly would make every backend depend on it.
"""

from .memory import InMemoryStores, Stores
from .sqlite import SqliteStores

__all__ = ["InMemoryStores", "SqliteStores", "Stores"]
