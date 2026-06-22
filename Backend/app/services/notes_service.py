from openai import OpenAI

from app.core.config import settings
from app.services.vectorstore_service import VectorStoreService


class NotesService:
    def __init__(self, vectorstore_service: VectorStoreService):
        self.vectorstore_service = vectorstore_service
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def generate_notes(self, video_id: str) -> str:

        chunks = self.vectorstore_service.get_all_chunks(video_id)

        if not chunks:
            return "No transcript available."

        transcript = "\n\n".join(
            chunk["text"]
            for chunk in chunks
        )

        prompt = f"""
You are an expert study assistant.

Generate comprehensive study notes from the following transcript.

Requirements:
- Use headings and subheadings
- Use bullet points
- Explain important concepts
- Keep examples if present
- Produce clean markdown
- Organize topics logically

TRANSCRIPT:

{transcript}
"""

        response = self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0.3,
        )

        return response.choices[0].message.content
    