from fastapi import FastAPI
from typing import Optional
from pydantic import BaseModel
try:
    from .persona_loader import load_persona
    ACTIVE_PERSONA_NAME: Optional[str] = None  # will set on startup
except Exception:
    load_persona = None
    ACTIVE_PERSONA_NAME = None

app = FastAPI()

@app.on_event("startup")
def _cache_persona_name():
    global ACTIVE_PERSONA_NAME
    if load_persona is not None:
        try:
            persona = load_persona()  # your loader should default to current persona
            # try name field if available; else fallback to known default
            ACTIVE_PERSONA_NAME = persona.get("name") or persona.get("persona") or "harvey_specter"
        except Exception:
            ACTIVE_PERSONA_NAME = "harvey_specter"
    else:
        ACTIVE_PERSONA_NAME = "harvey_specter"

# existing endpoints and code...

from .rag import retrieve_with_persona

# In your existing /rag_chat endpoint, replace retrieval + context assembly with:
persona_hits, doc_hits = retrieve_with_persona(m.message, persona_name=ACTIVE_PERSONA_NAME, k_docs=6, k_persona=3)

persona_ctx = "\n".join([f"[PERSONA:{h.payload.get('persona')}/{h.payload.get('category')}] {h.payload.get('text','')[:800]}" for h in persona_hits])
doc_ctx = "\n".join([f"[{h.payload.get('path')}] {h.payload.get('text','')[:800]}" for h in doc_hits])

ctx = (persona_ctx + "\n" + doc_ctx).strip()

messages = [
    {"role":"system","content": "Use the persona guidance first, then the documents. Cite persona as [PERSONA:<name>/<section>] and docs as [path]. If unsure, say 'I cannot verify this.'"},
    {"role":"user","content": f"Context:\n{ctx}\n\nQ: {m.message}"}
]
answer = chat(messages)
return {"answer": answer, "sources": [h.payload.get("path") for h in doc_hits]}

@app.post("/ingest_personas")
def _ingest_personas():
    from .rag import ingest_personas
    n = ingest_personas()
    return {"status":"ok","chunks": n}

# ---------------- Persona utility endpoints ----------------
class PersonaSelect(BaseModel):
    name: str

@app.get("/persona/active")
def persona_active():
    """Return the name of the currently active persona (for RAG retrieval)."""
    return {"active": ACTIVE_PERSONA_NAME}

@app.get("/persona/preview")
def persona_preview():
    """Return the merged system prompt for the currently loaded persona."""
    try:
        if load_persona is None:
            return {"error": "persona loader not available"}
        persona = load_persona()  # expects {"system": str, ...}
        return {
            "persona": persona.get("name") or ACTIVE_PERSONA_NAME or "unknown",
            "system_prompt": persona.get("system", ""),
            "fewshots": len(persona.get("fewshots", [])),
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/persona/switch")
def persona_switch(p: PersonaSelect):
    """Switch the active persona name used for persona-aware retrieval.

    Note: This assumes your loader can load by name via an environment variable
    or internal state. If your loader requires a different mechanism,
    adjust accordingly.
    """
    global ACTIVE_PERSONA_NAME
    try:
        # optimistic set; if loader fails, we still keep the name for RAG filtering
        ACTIVE_PERSONA_NAME = p.name
        # Optionally trigger a load to validate and warm caches
        if load_persona is not None:
            _ = load_persona()  # ignore contents; ensures files are readable
        return {"status": "ok", "active": ACTIVE_PERSONA_NAME}
    except Exception as e:
        return {"error": str(e)}

@app.post("/persona/reload")
def persona_reload():
    """Reload persona files from disk and return summary."""
    try:
        if load_persona is None:
            return {"error": "persona loader not available"}
        persona = load_persona()
        return {
            "status": "ok",
            "persona": persona.get("name") or ACTIVE_PERSONA_NAME or "unknown",
            "fewshots": len(persona.get("fewshots", [])),
            "chars": len(persona.get("system", "")),
        }
    except Exception as e:
        return {"error": str(e)}