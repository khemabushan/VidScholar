# VidScholar 🎓

AI-Powered YouTube Learning Assistant

VidScholar transforms YouTube videos into an interactive learning experience by automatically extracting transcripts, generating study notes, and answering questions grounded in the video's content.

## Live Demo

Frontend:
https://vidscholar-1.onrender.com

Backend:
https://vidscholar.onrender.com

---

## Features

* Extracts YouTube video transcripts
* Transcript fallback using Supadata when YouTube blocks requests
* Generates comprehensive study notes
* AI-powered question answering using Retrieval-Augmented Generation (RAG)
* Semantic search using ChromaDB
* Timestamped source citations
* Modern React frontend
* FastAPI backend

---

## Tech Stack

### Frontend

* React
* TypeScript
* Vite
* Tailwind CSS

### Backend

* FastAPI
* Python
* OpenAI API
* ChromaDB
* SQLAlchemy

### Deployment

* Render

---

## Architecture

User → React Frontend → FastAPI Backend

Backend Flow:

1. Extract transcript from YouTube
2. Fallback to Supadata if transcript retrieval fails
3. Split transcript into chunks
4. Generate embeddings using OpenAI
5. Store chunks in ChromaDB
6. Retrieve relevant chunks for user queries
7. Generate answers and study notes using GPT

---

## Project Highlights

* Implemented Retrieval-Augmented Generation (RAG)
* Integrated OpenAI embeddings and chat models
* Designed transcript fallback strategy for cloud deployments
* Built scalable vector search with ChromaDB
* Deployed full-stack application on Render

---

## Installation

### Backend

```bash
cd Backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd Frontend
npm install
npm run dev
```

---

## Environment Variables

```env
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
SUPADATA_API_KEY=your_key
```

---

## Author

Hemabushan K

B.Tech CSE (AI & ML)

SRM Institute of Science and Technology
