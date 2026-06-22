# VidScholar — AI Powered YouTube Learning Assistant

VidScholar lets you paste a YouTube URL and instantly get an AI-generated
summary, structured notes, flashcards, a quiz, and a chat assistant that
answers questions about the video — complete with clickable timestamp
citations. Built with React + Vite + TailwindCSS + Shadcn UI on the
frontend, and FastAPI + LangChain + ChromaDB + OpenAI on the backend.

> **Status:** Phase 4 complete — Chat With Video (RAG-based, streaming,
> citation-grounded, hallucination-guarded) is fully implemented and
> tested. Summary/Notes/Flashcards/Quiz generation (Phase 3) and final
> UI polish (Phase 5) remain.

---

## Architecture Overview

```
Frontend (React + Vite + Tailwind)  <-- REST -->  Backend (FastAPI)
                                                        |
                                          +-------------+-------------+
                                          |                           |
                                   YouTube Transcript API      OpenAI Embeddings
                                   pytubefix (metadata)               |
                                          |                     ChromaDB (vectors)
                                          |                           |
                                          +------> SQLite/Postgres <--+
                                                  (video metadata)
```

### How video processing works (Phase 2)

1. User submits a YouTube URL via `POST /api/videos/process`.
2. The backend extracts the 11-character video ID and creates a `videos`
   row with status `pending`, then immediately returns `202` with status
   `processing` — the actual work happens in a background task.
3. **Background pipeline:**
   - Fetches video metadata (title, channel, duration, thumbnail) via
     `pytubefix`. This step is best-effort — failures here never block
     the rest of the pipeline.
   - Fetches the transcript (with per-line timestamps) via
     `youtube-transcript-api`, trying English first and falling back to
     any available language.
   - Splits the transcript into ~1000-character overlapping chunks,
     each retaining its start/end timestamp.
   - Embeds each chunk via OpenAI's embeddings API and stores it in a
     per-video ChromaDB collection (`video_<video_id>`).
   - Updates the `videos` row to status `completed` (or `failed` with
     an error message).
4. The frontend polls `GET /api/videos/{id}/status` every 2 seconds
   until it sees a terminal status, then renders the embedded player.

## Project Structure

```
VidScholar/
├── Backend/
│   ├── app/
│   │   ├── main.py                  Application factory, CORS, startup
│   │   ├── core/
│   │   │   ├── config.py            Centralized settings (env vars)
│   │   │   └── logging_config.py    Logging setup
│   │   ├── api/
│   │   │   ├── deps.py              Shared FastAPI dependencies
│   │   │   └── routers/
│   │   │       ├── videos.py        Video processing endpoints
│   │   │       └── chat.py          Chat With Video endpoints (streaming + non-streaming)
│   │   ├── schemas/
│   │   │   ├── video.py             Pydantic request/response models
│   │   │   └── chat.py              Chat request/response + citation models
│   │   ├── services/
│   │   │   ├── youtube_service.py   Video metadata fetching
│   │   │   ├── transcript_service.py Transcript fetching
│   │   │   ├── vectorstore_service.py Chunking + embedding + ChromaDB
│   │   │   └── chat_service.py      RAG pipeline: retrieve + ground + generate
│   │   ├── db/
│   │   │   ├── base.py              SQLAlchemy declarative base
│   │   │   ├── session.py           Engine, session factory, get_db()
│   │   │   └── models/
│   │   │       └── video.py         Video ORM model
│   │   ├── repositories/
│   │   │   └── video_repository.py  DB CRUD for videos
│   │   └── utils/
│   │       ├── youtube_utils.py     URL parsing, video ID extraction
│   │       ├── timestamp_formatter.py Seconds <-> "H:MM:SS"
│   │       └── text_splitter.py     Transcript chunking with timestamps
│   ├── chroma_data/                 Persistent vector store (gitignored)
│   ├── .env.example
│   ├── requirements.txt
│   └── Dockerfile
│
├── Frontend/
│   ├── src/
│   │   ├── main.tsx                 React bootstrap
│   │   ├── App.tsx                  Root component, ties everything together
│   │   ├── components/video/
│   │   │   ├── UrlInputForm.tsx     URL submission form
│   │   │   ├── ProcessingStatus.tsx Pipeline status indicator
│   │   │   └── VideoPlayer.tsx      Embedded YouTube player + metadata
│   │   ├── components/chat/
│   │   │   ├── ChatWindow.tsx       Main chat panel (message list + input)
│   │   │   ├── ChatBubble.tsx       Single user/assistant turn, incl. streaming cursor
│   │   │   └── CitationBadge.tsx    Clickable timestamp citation badges
│   │   ├── hooks/
│   │   │   ├── useVideoProcessing.ts Submit + poll lifecycle
│   │   │   └── useChat.ts           Chat conversation state + SSE streaming
│   │   ├── store/
│   │   │   └── videoStore.tsx       Shared "current video" Context
│   │   ├── lib/
│   │   │   └── api.ts               Axios client + all API calls
│   │   ├── types/
│   │   │   └── index.ts             Shared TypeScript interfaces
│   │   └── styles/globals.css
│   ├── .env.example
│   ├── package.json
│   └── Dockerfile
│
├── docker-compose.yml
└── README.md
```

## Prerequisites

- Python 3.11+
- Node.js 18+
- npm 9+
- An OpenAI API key (required from Phase 2 onward — needed for embeddings)
- (Optional) Docker & Docker Compose

## Local Setup

### 1. Backend

```bash
cd Backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then edit OPENAI_API_KEY at minimum
uvicorn app.main:app --reload --port 8000
```

Verify it's running:

```bash
curl http://localhost:8000/health
```

API docs available at: http://localhost:8000/api/docs

### 2. Frontend

```bash
cd Frontend
npm install
cp .env.example .env            # adjust VITE_API_BASE_URL if needed
npm run dev
```

Visit: http://localhost:5173

Paste a YouTube URL into the input box and submit. The page will show
a live processing status, then embed the video once transcript
extraction and embedding complete.

## Environment Variables

### Backend (`Backend/.env`)

| Variable | Description | Default |
|---|---|---|
| `PROJECT_NAME` | Display name of the service | `VidScholar` |
| `ENVIRONMENT` | `development` / `staging` / `production` | `development` |
| `HOST` / `PORT` | Server bind address | `0.0.0.0` / `8000` |
| `BACKEND_CORS_ORIGINS` | Comma-separated allowed frontend origins | `http://localhost:5173` |
| `OPENAI_API_KEY` | **Required.** Used for embeddings (and chat in Phase 4) | — |
| `OPENAI_MODEL` | Chat completion model (used from Phase 3) | `gpt-4o-mini` |
| `OPENAI_EMBEDDING_MODEL` | Embedding model for vector search | `text-embedding-3-small` |
| `CHROMA_PERSIST_DIR` | ChromaDB storage path | `./chroma_data` |
| `DATABASE_URL` | SQLAlchemy DB URL | `sqlite:///./vidscholar.db` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |

### Frontend (`Frontend/.env`)

| Variable | Description | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend base URL | `http://localhost:8000` |

## API Reference

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/videos/process` | Submit a YouTube URL for processing |
| `GET` | `/api/videos/{id}/status` | Poll processing status (lightweight) |
| `GET` | `/api/videos/{id}` | Get full video record |
| `GET` | `/api/videos` | List recently processed videos |
| `DELETE` | `/api/videos/{id}` | Delete a video and its vector collection |
| `POST` | `/api/videos/{id}/chat` | Ask a question, get a full grounded answer (non-streaming) |
| `POST` | `/api/videos/{id}/chat/stream` | Same as above, streamed via Server-Sent Events |
| `GET` | `/health` | Backend connectivity health check |

### Chat With Video (Phase 4)

Both chat endpoints require the target video's `status` to be
`completed` — chatting against a video that's still processing or that
failed returns `409 Conflict`, since there's no transcript context to
retrieve from yet.

**Hallucination prevention** is implemented at three layers:
1. Retrieved transcript chunks below a minimum relevance score are
   discarded before ever reaching the prompt. If nothing relevant
   remains, the LLM is **never called** — the fixed "not covered in
   this video" response is returned directly.
2. The system prompt strictly forbids the model from using outside
   knowledge and requires it to use a specific refusal sentence when
   the supplied excerpts don't answer the question.
3. If the model emits that refusal sentence despite having been given
   some context, the backend detects it and strips citations from the
   response, so the frontend never shows "sources" for an answer the
   model itself flagged as ungrounded.

`POST /api/videos/{id}/chat/stream` emits Server-Sent Events:
```
data: {"type": "token", "content": "..."}
data: {"type": "done", "citations": [...], "grounded": true}
data: {"type": "error", "detail": "..."}
```

## Running with Docker Compose

```bash
cp Backend/.env.example Backend/.env   # edit OPENAI_API_KEY
docker-compose up --build
```

Backend: http://localhost:8000 · Frontend: http://localhost:5173

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 | Scaffolding, health checks, frontend/backend connectivity | ✅ Complete |
| 2 | YouTube transcript extraction + ChromaDB vector storage | ✅ Complete |
| 3 | Summary, Notes, Flashcards, Quiz generation | Planned |
| 4 | Chat With Video (RAG + streaming + citations) | ✅ Complete |
| 5 | Dark mode UI polish, testing, deployment hardening | Planned |

## License

Proprietary — internal project (license terms TBD).
