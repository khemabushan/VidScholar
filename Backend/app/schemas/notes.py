from pydantic import BaseModel


class NotesGenerateRequest(BaseModel):
    video_row_id: int


class NotesGenerateResponse(BaseModel):
    video_row_id: int
    video_id: str
    title: str
    notes_markdown: str
    chunk_count: int