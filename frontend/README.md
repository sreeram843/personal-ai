# Personal AI Web UI

React + Vite single-page app that talks to the FastAPI backend running at `http://localhost:8080`.

## Features

- Standard or retrieval-augmented chat modes with persistent history (localStorage).
- Chat bubbles with latency indicator, streaming updates, and cited sources for RAG replies.
- Voice input toggle powered by the browser speech-recognition API (best in Chrome).
- Document ingestion via drag-and-drop file picker for `.txt`, `.md`, `.pdf` files.
- Light/Dark themes, responsive layout, and Tailwind styling inspired by ChatGPT.
- Persona selector (Harvey Specter persona by default) with inline preview of the merged system prompt.

## Getting Started

```bash
cd frontend
npm install
npm run dev
```

The dev server runs on `http://127.0.0.1:5173` by default. Ensure the FastAPI service is available at `http://localhost:8080` before chatting.

## API Integration

- `POST /chat` — direct responses (`{"message": "..."}`).
- `POST /rag_chat` — RAG answers with `sources` payload.
- `POST /ingest` — multi-file form-data upload (`files` field).
- Persona endpoints (`/persona/list`, `/persona/switch`, `/persona/preview`) for the selector and preview drawer.

Endpoints are called through simple `fetch` helpers in `src/api.ts`. The UI auto-detects text streaming via `text/event-stream`; otherwise it falls back to JSON responses.

## Build

```bash
npm run build
```

Outputs production assets to `dist/`. Use `npm run preview` to locally serve the build.

## Notes

- Voice capture is optional; unsupported browsers gracefully fall back to keyboard input.
- Upload notifications surface success and failure per file.
- Adjust the backend base URL in `src/api.ts` if the server lives elsewhere.
- Persona changes clear the current conversation to avoid mixing contexts.
