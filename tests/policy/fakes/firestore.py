from __future__ import annotations

from copy import deepcopy
from typing import Callable, TypeVar


T = TypeVar("T")


class FakeDocumentSnapshot:
    def __init__(self, reference: "FakeDocumentReference", data=None) -> None:
        self.reference = reference
        self.id = reference.id
        self._data = deepcopy(data)
        self.exists = data is not None

    def to_dict(self):
        return deepcopy(self._data)


class FakeDocumentReference:
    def __init__(self, client: "FakeFirestoreClient", path: str) -> None:
        self._client = client
        self.path = path
        self.id = path.rsplit("/", 1)[-1]

    def get(self) -> FakeDocumentSnapshot:
        return FakeDocumentSnapshot(self, self._client.documents.get(self.path))

    def create(self, data) -> None:
        if self.path in self._client.documents:
            raise ValueError("document already exists")
        self._client.documents[self.path] = deepcopy(data)

    def set(self, data) -> None:
        self._client.documents[self.path] = deepcopy(data)

    def update(self, data) -> None:
        if self.path not in self._client.documents:
            raise KeyError(self.path)
        self._client.documents[self.path].update(deepcopy(data))


class FakeCollection:
    def __init__(self, client: "FakeFirestoreClient", name: str) -> None:
        self._client = client
        self._name = name

    def document(self, document_id: str | None = None) -> FakeDocumentReference:
        if document_id is None:
            self._client.auto_id += 1
            document_id = f"auto_{self._client.auto_id:03d}"
        return FakeDocumentReference(self._client, f"{self._name}/{document_id}")

    def stream(self):
        prefix = f"{self._name}/"
        paths = sorted(
            path
            for path in self._client.documents
            if path.startswith(prefix) and "/" not in path[len(prefix):]
        )
        return [self.document(path[len(prefix):]).get() for path in paths]


class FakeTransaction:
    def __init__(self, client: "FakeFirestoreClient") -> None:
        self._client = client

    def get(self, reference: FakeDocumentReference) -> FakeDocumentSnapshot:
        return reference.get()

    def create(self, reference: FakeDocumentReference, data) -> None:
        reference.create(data)

    def set(self, reference: FakeDocumentReference, data) -> None:
        reference.set(data)

    def update(self, reference: FakeDocumentReference, data) -> None:
        reference.update(data)


class FakeFirestoreClient:
    def __init__(self) -> None:
        self.documents: dict[str, dict[str, object]] = {}
        self.auto_id = 0

    def collection(self, name: str) -> FakeCollection:
        return FakeCollection(self, name)

    def transaction(self) -> FakeTransaction:
        return FakeTransaction(self)

    def run_transaction(self, callback: Callable[[FakeTransaction], T]) -> T:
        before = deepcopy(self.documents)
        try:
            return callback(self.transaction())
        except Exception:
            self.documents = before
            raise
