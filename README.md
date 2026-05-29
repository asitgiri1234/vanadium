# Vanadium

> **AI-powered content intelligence for creators.** Drop in two social videos
> (YouTube / Instagram Reels), and Vanadium explains *why* one outperforms the
> other — with evidence-backed answers, source citations, and concrete
> recommendations to improve future content.

Vanadium behaves like an AI **content strategist**, not a chatbot. It ingests
both videos, extracts transcripts + metadata, computes engagement, indexes
everything in a vector store, and answers natural-language questions over a
RAG pipeline with conversation memory and streaming responses.

---

## ✨ What it does

- **Compare two videos** side by side: views, likes, comments, engagement rate,
  hashtags, creator + follower count, thumbnails.
- **Ask anything**, e.g.:
  - *Why did Video A get more engagement than Video B?*
  - *Compare the hooks used in the first 5 seconds.*
  - *Which video had a stronger CTA?*
  - *Suggest improvements for Video B based on what worked in Video A.*
- **Evidence-backed**: every answer cites transcript chunks (video + timestamp).
- **Memory**: ask *"which one was stronger?"* after *"compare the hooks"* — it
  understands context.

## 🧱 Tech Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js (App Router), TypeScript, TailwindCSS, shadcn-style UI |
| Backend | FastAPI |
| AI orchestration | LangChain |
| Embeddings | OpenAI `text-embedding-3-small` |
| Vector DB | ChromaDB (persistent) |
| LLM | OpenAI `gpt-4o-mini` |
| Transcripts | `youtube-transcript-api` (YT), `yt-dlp` + Whisper (IG Reels) |

See **[ARCHITECTURE.md](./ARCHITECTURE.md)** for the full design, API contract,
data model, RAG pipeline, and roadmap.

---

## 🚀 Quickstart

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env          # then add your OPENAI_API_KEY
python run.py                 # serves on http://localhost:8000
```

> No `OPENAI_API_KEY`? Vanadium still runs — it falls back to a deterministic
> extractive analyst and a local hash-based embedder so you can demo the full
> flow offline.

### 2. Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                        # serves on http://localhost:3000
```

Open <http://localhost:3000>, paste two video URLs, hit **Analyze**, then chat.

---

## 🔌 API summary

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/api/health` | liveness + capability probe |
| `POST` | `/api/ingest` | ingest two videos → analysis snapshot |
| `GET`  | `/api/analysis/{id}` | fetch a saved analysis |
| `POST` | `/api/chat` | streaming RAG chat (SSE) with citations |

Full request/response shapes live in [ARCHITECTURE.md](./ARCHITECTURE.md#3-api-design).

---

## 📁 Project layout

```
vanadium/
├── backend/    # FastAPI + LangChain + ChromaDB RAG service
└── frontend/   # Next.js dashboard + streaming chat
```

## ⚠️ Notes

- Instagram Reel transcription uses `yt-dlp` + Whisper and can be slow; in
  production this should run in a background worker (see ARCHITECTURE §8).
- The analysis + memory store is in-memory by default; swap for Redis/Postgres
  for multi-instance deployments.
