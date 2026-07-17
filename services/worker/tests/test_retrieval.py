from types import SimpleNamespace

from worker.context import retrieve_relevant_chunks
from worker.embeddings import batched, embed_texts, to_pgvector


class FakeEmbeddings:
    def create(self, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3]) for _ in kwargs["input"]])


class FakeRpc:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self.rows)


class FakeClient:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.rpc_calls: list[tuple[str, dict[str, object]]] = []

    def rpc(self, function: str, arguments: dict[str, object]) -> FakeRpc:
        self.rpc_calls.append((function, arguments))
        return FakeRpc(self.rows)


def test_to_pgvector_uses_bracketed_form() -> None:
    assert to_pgvector([0.5, 0.25, 1.0]) == "[0.5,0.25,1]"


def test_embed_texts_batches_and_validates_dimensions() -> None:
    openai = SimpleNamespace(embeddings=FakeEmbeddings())
    result = embed_texts(openai, "embedding", 3, ["a", "b", "c"], batch_size=2)
    assert result == [[0.1, 0.2, 0.3]] * 3
    assert batched(["a", "b", "c"], 2) == [["a", "b"], ["c"]]


def test_retrieve_relevant_chunks_calls_match_with_serialized_query() -> None:
    client = FakeClient([{"id": "chunk-1", "content": "Relevant.", "similarity": 0.9}])
    openai = SimpleNamespace(embeddings=FakeEmbeddings())

    chunks = retrieve_relevant_chunks(client, openai, "embedding", 3, ["version-a"], "reject expired tokens", 5)

    assert chunks == [{"id": "chunk-1", "content": "Relevant."}]
    function, arguments = client.rpc_calls[0]
    assert function == "match_source_chunks"
    assert arguments == {"p_version_ids": ["version-a"], "p_query_embedding": "[0.1,0.2,0.3]", "p_limit": 5}


def test_retrieve_relevant_chunks_short_circuits_without_versions() -> None:
    client = FakeClient([])
    openai = SimpleNamespace(embeddings=FakeEmbeddings())

    assert retrieve_relevant_chunks(client, openai, "embedding", 3, [], "anything", 5) == []
    assert client.rpc_calls == []
