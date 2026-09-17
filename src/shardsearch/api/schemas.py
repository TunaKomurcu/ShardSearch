"""The API's request/response contract (Pydantic models)."""

from pydantic import BaseModel


class AddDocumentRequest(BaseModel):
    doc_id: str
    text: str


class AddDocumentResponse(BaseModel):
    doc_id: str
    status: str


class SearchResult(BaseModel):
    doc_id: str
    score: float
    # Returns the FULL text rather than a snippet, a deliberate MVP scope
    # decision. In production this would likely return a short excerpt
    # around the matched portion (with highlighting) instead of the whole
    # document; that's a separate feature and out of scope for now.
    text: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    # If one or more shards errored out during the query, they're listed
    # here EXPLICITLY — a partial result whose cause is known, rather than
    # a silent loss of data. An empty list means every shard responded.
    failed_shards: list[str] = []


class ErrorResponse(BaseModel):
    error: str
