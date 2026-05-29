# Vanadium — Architecture & Design

> AI-powered content intelligence platform for creators. Compare two social
> videos (YouTube / Instagram Reels), understand *why* one outperforms the
> other, and get evidence-backed, actionable recommendations.

This document is the source of truth for the system design. It covers the
high-level architecture, folder structure, API contract, data model, the RAG
pipeline, and the phased implementation roadmap.

---

## 1. System Overview

```
                       ┌─────────────────────────────────────────────┐
                       │                FRONTEND (Next.js)            │
                       │  Comparison Dashboard  +  Streaming AI Chat  │
                       └───────────────┬─────────────────────────────┘
                                       │ REST / SSE (JSON)
                                       ▼
              ┌──────────────────────────────────────────────────────┐
              │                  BACKEND (FastAPI)                     │
              │                                                        │
              │  /api/ingest      → Ingestion orchestration           │
              │  /api/chat        → RAG chat (streaming + citations)   │
              │  /api/analysis    → Comparison & intelligence          │
              │                                                        │
              │  ┌───────────┐  ┌───────────┐  ┌────────────────────┐ │
              │  │ Services  │  │   RAG     │  │   Vector Store     │ │
              │  │ ingestion │  │ retriever │  │   ChromaDB         │ │
              │  │ metadata  │  │ prompts   │  │   (persistent)     │ │
              │  │ transcript│  │ chat      │  └────────────────────┘ │
              │  │ chunking  │  │ citations │  ┌────────────────────┐ │
              │  │ embedding │  │ memory    │  │  Analysis Store    │ │
              │  │ comparison│  └───────────┘  │  (session state)   │ │
              │  └───────────┘                 └────────────────────┘ │
              └───────────────┬────────────────────────┬──────────────┘
                              │                         │
              ┌───────────────▼──────────┐   ┌──────────▼─────────────┐
              │   External Extraction    │   │      OpenAI API        │
              │  youtube-transcript-api  │   │  embeddings: text-      │
              │  yt-dlp + Whisper (IG)   │   │   embedding-3-small     │
              │  metadata scrapers       │   │  llm: gpt-4o-mini       │
              └──────────────────────────┘   └────────────────────────┘
```

### Design principles

- **Separation of concerns.** Each capability (extraction, chunking,
  embedding, retrieval, generation) is an independently testable service.
- **Provider abstraction.** Platform-specific logic (YouTube vs Instagram)
  lives behind a common `Extractor` interface so new platforms drop in.
- **Graceful degradation.** Missing API keys or extraction failures never
  crash the app; they surface structured errors and fall back to partial
  data so the product remains demonstrable.
- **Stateless services, stateful stores.** Services are pure; state lives in
  ChromaDB (vectors) and the analysis/session store (metadata + memory).
- **Streaming-first UX.** Chat responses stream token-by-token over SSE.

---

## 2. Folder Structure

```
vanadium/
├── ARCHITECTURE.md            # this document
├── README.md                  # quickstart + product overview
├── .gitignore
│
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│   ├── run.py                 # uvicorn entrypoint
│   └── app/
│       ├── main.py            # FastAPI app factory, CORS, router mount
│       ├── core/
│       │   ├── config.py      # pydantic-settings configuration
│       │   └── logging.py     # structured logging setup
│       ├── api/
│       │   ├── router.py      # aggregates all route modules
│       │   └── routes/
│       │       ├── health.py
│       │       ├── ingest.py  # POST /api/ingest, GET /api/analysis/{id}
│       │       └── chat.py    # POST /api/chat (SSE stream)
│       ├── models/
│       │   └── schemas.py     # Pydantic request/response/domain models
│       ├── services/
│       │   ├── ingestion_service.py   # orchestrates a full ingest
│       │   ├── metadata_service.py    # title, creator, views, likes...
│       │   ├── transcript_service.py  # YouTube / Instagram transcript
│       │   ├── chunking_service.py    # clean + split + window
│       │   ├── embedding_service.py   # OpenAI embeddings (+ fallback)
│       │   └── comparison_service.py  # engagement + intelligence metrics
│       ├── vectorstore/
│       │   └── chroma_store.py        # ChromaDB wrapper (upsert/query)
│       ├── rag/
│       │   ├── retriever.py           # hybrid metadata + vector retrieval
│       │   ├── prompts.py             # system + analyst prompt templates
│       │   ├── chat_service.py        # RAG chain + streaming generation
│       │   └── citations.py           # build structured source citations
│       ├── store/
│       │   └── analysis_store.py      # in-memory analysis + chat memory
│       └── utils/
│           ├── url_utils.py           # platform detection + id parsing
│           └── text.py                # cleaning / timestamp helpers
│
└── frontend/
    ├── package.json
    ├── next.config.mjs
    ├── tsconfig.json
    ├── tailwind.config.ts
    ├── postcss.config.mjs
    ├── .env.local.example
    └── src/
        ├── app/
        │   ├── layout.tsx
        │   ├── page.tsx               # dashboard (cards + chat)
        │   └── globals.css
        ├── components/
        │   ├── ui/                    # shadcn-style primitives
        │   │   ├── button.tsx
        │   │   ├── card.tsx
        │   │   ├── input.tsx
        │   │   └── badge.tsx
        │   ├── url-form.tsx           # two-URL input + ingest trigger
        │   ├── video-card.tsx         # per-video metrics card
        │   ├── comparison-bar.tsx     # side-by-side engagement bar
        │   ├── chat-panel.tsx         # streaming chat + memory
        │   └── citation.tsx           # source citation chip
        └── lib/
            ├── api.ts                 # typed backend client (fetch/SSE)
            └── types.ts               # shared TS types
```

---

## 3. API Design

Base URL: `http://localhost:8000`

### `GET /api/health`
Liveness + capability probe.
```json
{ "status": "ok", "openai_configured": true, "version": "0.1.0" }
```

### `POST /api/ingest`
Ingest two videos: extract metadata + transcript, compute engagement, chunk,
embed, and index. Returns the analysis snapshot used by the dashboard.

Request:
```json
{ "video_a_url": "https://youtu.be/...", "video_b_url": "https://www.instagram.com/reel/..." }
```

Response `200`:
```json
{
  "analysis_id": "a1b2c3",
  "videos": {
    "A": {
      "video_id": "A",
      "platform": "youtube",
      "url": "...",
      "title": "...",
      "creator": "...",
      "follower_count": 120000,
      "thumbnail": "https://...",
      "views": 50000, "likes": 4200, "comments": 310,
      "duration_seconds": 47,
      "upload_date": "2026-02-14",
      "hashtags": ["#ai", "#growth"],
      "engagement_rate": 9.02,
      "transcript_available": true,
      "chunk_count": 12
    },
    "B": { "...": "..." }
  },
  "comparison": {
    "winner": "A",
    "engagement_delta": 4.1,
    "headline_insights": ["A's hook poses a question in the first 3s", "..."]
  }
}
```

### `GET /api/analysis/{analysis_id}`
Fetch a previously computed analysis snapshot (used on reload).

### `POST /api/chat`  *(Server-Sent Events stream)*
Ask a natural-language question about the comparison. Retrieves transcript
chunks + metadata, generates an analyst answer, and streams it back with
citations. Conversation memory is keyed by `analysis_id`.

Request:
```json
{ "analysis_id": "a1b2c3", "message": "Why did Video A get more engagement?" }
```

SSE event stream:
```
event: token   data: {"text": "Video A "}
event: token   data: {"text": "opens with a question..."}
event: citations data: [{"video_id":"A","chunk_index":4,"timestamp":"00:12-00:20","source_platform":"youtube"}]
event: done     data: {"message_id":"m_12"}
```

Errors are emitted as `event: error  data: {"detail": "..."}`.

---

## 4. Data Model

### Domain objects (Pydantic)

`VideoMetadata`
| field | type | notes |
|---|---|---|
| video_id | `"A" \| "B"` | logical slot |
| platform | `youtube \| instagram` | from URL detection |
| url | str | original input |
| title, creator | str | |
| follower_count, views, likes, comments | int | |
| duration_seconds | int | |
| upload_date | str (ISO date) | |
| hashtags | list[str] | parsed from description/caption |
| thumbnail | str (url) | |
| engagement_rate | float | computed |
| transcript_available | bool | |
| chunk_count | int | |

`TranscriptChunk` (also the ChromaDB record)
| field | type |
|---|---|
| id | str — `{analysis_id}:{video_id}:{chunk_index}` |
| text | str |
| embedding | list[float] (managed by Chroma) |
| metadata | see below |

Chunk metadata (exact spec required by product):
```json
{
  "analysis_id": "a1b2c3",
  "video_id": "A",
  "chunk_index": 4,
  "timestamp": "00:12-00:20",
  "source_platform": "youtube"
}
```

### Engagement formula
```
engagement_rate = ((likes + comments) / views) * 100   # 0 when views == 0
```

### Stores
- **ChromaDB** — persistent collection `vanadium_chunks`; one collection for
  all analyses, partitioned logically via the `analysis_id` metadata filter.
- **Analysis store** — in-memory map `analysis_id -> AnalysisSnapshot` plus
  `analysis_id -> ConversationMemory` (last N turns). Swappable for Redis /
  Postgres in production (interface kept narrow on purpose).

---

## 5. RAG Pipeline

1. **Retrieve.** For a question + `analysis_id`, query ChromaDB filtered by
   `analysis_id`. We retrieve top-k chunks *per video* (balanced retrieval) so
   the model always sees both sides of the comparison, then attach the full
   metadata for both videos.
2. **Assemble context.** Build a structured prompt: video A/B metadata table,
   engagement numbers, and the retrieved transcript chunks (each tagged with
   its citation handle).
3. **Generate.** `gpt-4o-mini` with the *Content Strategist* system prompt
   produces an evidence-backed answer that references chunks by handle.
4. **Cite.** We map the chunk handles the model used (plus the top retrieved
   chunks) into structured `Citation` objects returned alongside the answer.
5. **Remember.** Append the turn to the conversation memory for `analysis_id`
   so follow-ups ("which one was stronger?") resolve in context.

When OpenAI keys are absent, the pipeline degrades to a deterministic,
extractive analyst (metadata + keyword heuristics) so the product still runs.

---

## 6. Intelligence Layer

Beyond raw numbers, `comparison_service` derives strategist-grade signals:

- **Hook analysis** — first ~5s of transcript per video.
- **CTA analysis** — detect call-to-action language (subscribe, comment, link).
- **Engagement analysis** — rate delta + likely drivers.
- **Content structure / pacing** — words-per-second, segment cadence.
- **Topic comparison** — keyword overlap & divergence.
- **Recommendations** — concrete suggestions for the weaker video.

These feed both the dashboard `comparison.headline_insights` and the RAG
context so chat answers stay grounded.

---

## 7. Implementation Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 | Project setup, config, structure | ✅ |
| 2 | Video ingestion orchestration | ✅ |
| 3 | Transcript extraction (YouTube + IG) | ✅ |
| 4 | Metadata extraction | ✅ |
| 5 | Engagement calculations | ✅ |
| 6 | Vector DB integration (ChromaDB) | ✅ |
| 7 | RAG retrieval + generation | ✅ |
| 8 | Streaming chat responses (SSE) | ✅ |
| 9 | Conversation memory | ✅ |
| 10 | Frontend dashboard | ✅ |
| 11 | Testing & optimization | 🔄 ongoing |

---

## 8. Production Considerations (next steps)

- Replace in-memory analysis store with Redis (memory) + Postgres (snapshots).
- Move ingestion to a background worker (Celery / RQ) with job status polling;
  Instagram Whisper transcription is slow and should not block the request.
- Add auth (Clerk/Auth.js), per-user rate limiting, and usage metering.
- Cache extraction results by canonical video id to avoid re-downloads.
- Observability: OpenTelemetry traces around extraction + LLM calls.
- Cost controls: token budgeting, embedding cache, model routing.
