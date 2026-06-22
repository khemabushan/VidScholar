from fastapi import APIRouter, Depends

from app.api.deps import get_vectorstore_service
from app.services.vectorstore_service import VectorStoreService
from app.services.notes_service import NotesService

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("/{video_id}")
def generate_notes(
    video_id: str,
    vectorstore_service: VectorStoreService = Depends(get_vectorstore_service),
):
    notes_service = NotesService(vectorstore_service)

    notes = notes_service.generate_notes(video_id)

    return {
        "video_id": video_id,
        "notes": notes,
    }