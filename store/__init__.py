"""Storage adapters implementing the ports in `core.repositories`.

`memory` backs local development and tests; `firestore` is added when the
emulator and Cloud Run wiring land (T-A1 step 3).
"""

from .memory import InMemoryStores, Stores

__all__ = ["InMemoryStores", "Stores"]
