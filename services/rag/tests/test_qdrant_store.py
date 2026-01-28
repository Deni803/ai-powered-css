from types import SimpleNamespace

from app.qdrant_store import QdrantStore
from qdrant_client.models import VectorParams, Distance


class FakeClient:
    def __init__(self):
        self.exists = False
        self.created = False
        self.vector_size = None

    def get_collection(self, name):
        if not self.exists:
            raise Exception("not found")
        return SimpleNamespace(
            config=SimpleNamespace(
                params=SimpleNamespace(vectors=SimpleNamespace(size=self.vector_size))
            )
        )

    def create_collection(self, collection_name, vectors_config):
        self.created = True
        self.exists = True
        self.vector_size = vectors_config.size

    def upsert(self, collection_name, points):
        pass

    def query_points(self, collection_name, query, limit, with_payload):
        return SimpleNamespace(points=[])


def test_ensure_collection_creates():
    fake = FakeClient()
    store = QdrantStore(url="http://fake", collection="test", client=fake)
    store.ensure_collection(vector_size=1536)
    assert fake.created is True
    assert fake.vector_size == 1536
