# Resolution Copilot (RAG) — Task Breakdown

A RAG-powered feature that, when an operator opens an alert, retrieves semantically
similar past resolved alerts / incidents / runbooks and uses Claude to generate a
grounded, cited remediation suggestion.

**Stack decisions (already made):**
- Generation: **Anthropic Claude** (Messages API, structured output via tool use).
- Embeddings: **Voyage AI** (`voyage-3`, 1024-dim; asymmetric `document` vs `query` input types).
- Vector store: **pgvector** inside the existing PostgreSQL — no new infrastructure.

Tasks are grouped into phases. Each phase is independently demoable; the project can
stop at any phase boundary with something working.

---

## Phase 0 — Infrastructure & configuration

- [ ] **Enable pgvector in Postgres.** Switch the dev DB image to a pgvector-capable
      build and ensure the `vector` extension is created on startup. Confirm the app
      can store and query vector columns end to end.
- [ ] **Add dependencies & settings.** Bring in the Anthropic and Voyage clients plus
      the pgvector type support. Add configuration for API keys, the chosen Claude and
      embedding models, embedding dimension, retrieval top-k, and the relevance floor.
- [ ] **Provision API keys for local dev.** Document how team members supply their own
      Anthropic + Voyage keys without committing them.

## Phase 1 — Indexing pipeline (the write path)

- [ ] **Design the unified chunk store.** A single table holding one row per searchable
      chunk with its embedding, the source type (alert / incident / runbook), a pointer
      back to the origin record, the flattened text, and a content hash. Add a vector
      similarity index.
- [ ] **Define how each source is flattened to text.** Decide the canonical string
      representation for a resolved alert (message + key labels + its resolution notes),
      an incident, and a runbook chunk, including the header that tells the LLM what it
      is reading.
- [ ] **Build the embedding service.** One service responsible for turning text into
      vectors via Voyage (batched, `input_type="document"`), persisting them, and
      skipping work when the content hash is unchanged (idempotent re-indexing).
- [ ] **Define chunking for long documents.** Runbooks get split into overlapping
      chunks; alerts/notes stay single-chunk. Pick chunk size and overlap.
- [ ] **Decide indexing triggers.** Index a resolved alert when its status becomes
      Solved, index operational notes when created, index runbooks on upload. Only
      resolved alerts are indexed.
- [ ] **Write a backfill routine.** A one-off pass that embeds all existing resolved
      alerts and notes so the feature works against historical data immediately.

## Phase 2 — Retrieval (semantic search, no LLM yet — first real demo)

- [ ] **Implement query embedding + vector search.** Embed an alert's own fields as a
      query (`input_type="query"`), run a cosine-similarity search over the chunk store,
      return the top-k ranked hits with similarity scores and source pointers.
- [ ] **Apply a relevance floor.** Drop hits below a similarity threshold; if nothing
      clears it, return a "no precedent found" result without proceeding.
- [ ] **Expose a "similar incidents" endpoint.** A read endpoint that returns the
      ranked matches for a given alert. This is demoable on its own as semantic search.
- [ ] **Evaluate retrieval quality.** Hand-label a small relevance set and measure
      precision/recall@k to tune the floor and top-k.

## Phase 3 — Knowledge Base (runbook ingestion)

- [ ] **Model and store uploaded runbooks.** A document store for curated runbooks with
      title, source, and raw text.
- [ ] **Build upload + management endpoints.** Create/list/delete runbooks; creating one
      triggers chunking + embedding into the same chunk store used by retrieval.
- [ ] **Add a Knowledge Base UI page.** Upload and list runbooks, linked from the
      sidebar. Curated runbooks then surface as retrieval results alongside history.

## Phase 4 — Generation (full RAG with Claude)

- [ ] **Assemble the grounded prompt.** Turn retrieved hits into numbered context blocks
      so the model can cite them by number; numbering is how citations map back to
      sources.
- [ ] **Design the grounding system prompt.** Instruct Claude to answer only from the
      provided context, cite every claim, and fall back to clearly-labeled generic
      triage with low confidence when the context doesn't support a specific fix.
- [ ] **Force structured output.** Use tool use to require a fixed result shape
      (diagnosis, ordered steps with per-step citations, confidence) instead of parsing
      free text.
- [ ] **Resolve citations back to records.** Map cited block numbers to their source
      type + id so the response carries clickable references with previews.
- [ ] **Expose the copilot endpoint.** A read endpoint that returns the structured,
      cited suggestion for an alert. Reuse the existing alert-exists validation.

## Phase 5 — Caching, performance & UX

- [ ] **Cache generated answers.** Persist a suggestion keyed to the alert and its
      current content; serve cached results instantly and regenerate only when the
      alert changes or the user requests it.
- [ ] **Keep the copilot off the hot path.** The alerts feed must not block on
      generation; the copilot runs only when the details panel opens (or when an alert
      first reaches "In progress").
- [ ] **Build the Copilot panel in the alert details UI.** Show diagnosis, ordered
      remediation steps, confidence, and citation chips that link to the source
      alert / incident / runbook. Add a Regenerate action.

## Phase 6 — Feedback loop & evaluation

- [ ] **Capture operator feedback.** A thumbs up/down control on each suggestion,
      persisted with the alert and the citations that were shown.
- [ ] **Use feedback as the evaluation dataset.** Report a thumbs-up rate for generation
      and retrieval precision@k from the labeled set; capture a before/after triage-time
      anecdote for the project writeup.

---

## Cross-cutting principles (keep these true throughout)

- **Trust comes from two mechanics together:** the retrieval relevance floor (decides
  whether there is anything real to say) and the "cite or say low-confidence" prompt
  rule (keeps the model inside the retrieved context). This pairing is what makes it
  RAG rather than a guessing chatbot.
- **Respect the existing layering.** Embedding and RAG logic live in services that never
  import FastAPI and raise only domain exceptions; routers stay thin and reuse existing
  dependencies. The only infrastructure change is pgvector.
- **Embeddings are isolated behind one service**, so the embedding/LLM provider can be
  swapped without touching retrieval, storage, or the API.
