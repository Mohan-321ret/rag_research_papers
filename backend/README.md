# DAA-RAG Backend

FastAPI backend for **Drift-Aware Adaptive Retrieval-Augmented Generation (DAA-RAG)**
for Dynamic Enterprise Knowledge Management.

Implemented so far:

- **Phase 0** — application skeleton, configuration, PostgreSQL + Neo4j wiring,
  structured logging, global error handling, health endpoint, Docker, tests.
- **Phase 1** — core database schema (13 tables, Alembic migration) and
  authentication (`/auth/register`, `/auth/login`, `/auth/me`) with roles
  (ADMIN / RESEARCHER / USER / VIEWER).
- **Phase 2** — enterprise knowledge ingestion: `POST /documents/upload`
  (PDF, DOCX, TXT, HTML, XLSX), list/get/delete, and per-document version
  history (`GET /documents/{id}/versions`).
- **Phase 3** — intelligent document processing: cleaning → noise removal →
  language detection → semantic chunking → embeddings
  (all-MiniLM-L6-v2) → PostgreSQL chunks + persistent FAISS index.
  `POST /documents/{id}/process`, `GET /documents/{id}/chunks`.
- **Phase 4** — hybrid knowledge repository: Neo4j graph projection
  (Document/Version/Chunk/Entity/Author/Department/Topic nodes; HAS_VERSION,
  SUPERSEDES, CONTAINS, MENTIONS, AUTHORED_BY, BELONGS_TO, HAS_TOPIC) with
  rule-based entity/topic extraction. `POST /graph/documents/{id}/sync`,
  `GET /graph/documents/{id}`, `GET /graph/stats`.
- **Phase 5** — baseline RAG: `POST /chat/query` — question → embedding →
  FAISS top-K → current-version chunks → prompt → answer + citations
  (document, page, section, chunk). Full evidence trail persisted
  (queries, retrieval_logs, answers, citations).
- **Phase 6** — query intelligence (Module 5): parser → intent detection →
  NER (knowledge-base aware) → complexity analysis → temporal detection →
  context expansion → structured query. `POST /chat/analyze`; integrated
  into `/chat/query` (intent persisted, expansions widen retrieval).
- **Phase 7** — adaptive retrieval (Module 6): a deterministic router sends
  each query to BM25 (exact terms/IDs/clauses), FAISS vector search
  (conceptual questions), Neo4j graph traversal (relationships/multi-hop),
  or all three fused by Reciprocal Rank Fusion (complex questions), with an
  automatic vector fallback if the chosen route comes up empty. Wired
  directly into `/chat/query`; routing decision, reasons, and per-retriever
  hit counts are returned alongside the answer.
- **Phase 8** — context fusion (Module 7): the routed candidate pool is
  deduplicated (by chunk id and by content), reranked by a real
  cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`), compressed to the
  top 5–8 most relevant chunks, and rendered as numbered `SOURCE N`
  blocks for the generator. `retrieval_logs` now records the full raw
  candidate pool while `citations` records only the final fused set that
  actually reached the LLM; a `context_fusion` object in every
  `/chat/query` response reports candidates → after-dedup → final counts.
- **Phase 9** — enterprise LLM (Module 8): a formal generation pipeline —
  Prompt Constructor → LLM Provider → Citation Generator → Initial Answer.
  The LLM sits behind a narrow `LLMProvider.generate(prompt) -> str`
  interface with two concrete backends, **Ollama** (local Llama/Gemma —
  this module's zero-credential starting point) and **Anthropic**,
  swappable via `LLM_PROVIDER` with no changes anywhere else in the RAG
  pipeline. The Citation Generator parses the model's own `[n]` markers
  out of its answer and validates them against the offered sources, so
  `citations` now reflects only what the model actually used (falling
  back to "cite everything offered" if the model forgets to mark, and
  flagging any hallucinated marker) — and a dead LLM provider degrades to
  the extractive baseline instead of failing the request.
- **Phase 10** — evidence verification (Module 9): every generated answer
  is split into per-sentence claims, each independently checked against
  its evidence with a real NLI (Natural Language Inference) cross-encoder
  (`cross-encoder/nli-deberta-v3-xsmall`) — not the Module 7 relevance
  reranker, which can't tell "same topic" from "same fact." Produces a
  per-claim `support_score`, `supported`, `verdict`
  (entailment/contradiction/neutral), and `citation_verified`, an
  aggregate `confidence` and `hallucination_detected` on every
  `/chat/query` response, and a **refined answer** with unsupported
  sentences flagged inline (`[⚠ unverified]` / `[⚠ contradicted by
  source]`) before it's returned or persisted.
- **Phase 11** — knowledge evolution (Module 3), the project's core
  research contribution: every new document version is run through a
  Change Detector, a text-level Diff Detector, an embedding-based Drift
  Detector, and a Conflict Detector (reusing Module 9's NLI model) that
  flags when a revision actually contradicts what it replaced — recorded
  as a `VersionComparison` and browsable via
  `GET /documents/{id}/evolution`. Old versions are never deleted, and
  `/chat/query` now resolves temporal intent ("what was the policy
  before 2024?") to the document version active at that time instead of
  always answering from the current one — verified live: the same
  question returns 20 days pre-2024 and 30 days today, from the same
  document.
- **Phase 12** — concept drift detection: chunk-level, embedding
  nearest-neighbor comparison classified by bidirectional NLI entailment
  into rewording/expansion/narrowing/contradiction/topic-shift, recorded
  as a `ConceptDriftReport` and browsable via
  `GET /documents/{id}/concept-drift`. Built on a real empirical finding
  (documented in [concept_drift_detector.py](app/modules/evolution/concept_drift_detector.py)):
  raw cosine distance cannot reliably separate a harmless rewording from
  a one-word factual change — a paraphrase measured **0.132** drift while
  "2 days" -> "3 days" measured only **0.037**, *lower* than the harmless
  case — so NLI verdict, not embedding distance, gates whether a chunk
  pair is flagged. Verified live on the spec's own example: "confidential
  info includes customer records" -> "...customer and employee records"
  is correctly typed `expansion` (broadened scope, not a contradiction —
  Phase 11's contradiction-only Conflict Detector correctly reports no
  conflict for the same transition, confirming Phase 12 catches a real
  gap, not a duplicate).
- **Phase 13** — knowledge conflict detection: unlike Phases 11–12 (one
  document's versions over time), this compares *different* documents —
  every new chunk is checked against the rest of the corpus for
  contradicting claims, resolved by metadata (document priority → date →
  version; department is recorded but never auto-ranked) via
  [authority_resolver.py](app/modules/conflict/authority_resolver.py),
  and browsable via `GET /conflicts` and `GET /documents/{id}/conflicts`.
  Context Fusion then looks the precomputed conflicts up among each
  query's candidates (a cheap DB read, no live NLI) and does *both* of
  the design's options at once: drops the losing claim from what the LLM
  sees, and reports the resolution transparently in
  `context_fusion.conflicts` — or, if authority ties, keeps both claims
  and flags the disagreement instead of guessing. Verified live with the
  spec's own example: "Employees get 20 days leave" (HR Handbook,
  priority 1) vs "Employees get 25 days leave" (Legal Policy, priority
  5) — detected at 0.98 contradiction, resolved in Legal Policy's favor,
  and confirmed absent from the final `/chat/query` citations.
- **Phase 14** — incremental re-indexing: a changed document no longer
  rebuilds the knowledge base. Each run diffs the freshly produced chunks
  against what is already indexed
  ([incremental.py](app/modules/processing/incremental.py)) and pays the
  transformer cost only for chunks that actually changed — unchanged ones
  keep their row and vector outright (same-version re-run) or copy the
  stored vector via FAISS `reconstruct` (new version). Old versions'
  vectors are never retired, so historical retrieval keeps working. Every
  `/process` response reports the saving (`embedded_count`,
  `chunks_reused`, `vectors_added`, `vectors_removed`), and
  `INCREMENTAL_REINDEX_ENABLED=false` restores the full-rebuild ablation
  baseline for comparison. Measured live: editing one clause of a
  12-clause policy re-embedded **1 of 12** chunks; re-running an
  unchanged version re-embedded **0** and wrote **no** vectors at all.
- **Phase 15** — frontend-facing API surface: the endpoint set the React
  app talks to, completed and verified against the running frontend.
  Adds `GET /chat/history`, `POST /search/semantic`, `POST /search/hybrid`,
  `GET /knowledge/{entities,relationships,versions,drift}`,
  `POST /feedback`, `GET /analytics/{dashboard,metrics}`, and
  `GET /admin/{system-status,audit-logs}` (ADMIN-only). Everything reads
  from what earlier phases already persist — no new bookkeeping.

The DAA-RAG pipeline modules exist as typed interfaces only
(see [app/modules/](app/modules/)) and are implemented in later phases.

### Data model

```
users ──< documents ──< document_versions ──< document_chunks
                │                                    │
                └ metadata (JSON)                    ├──< retrieval_logs >── queries >── users
knowledge_entities ──< knowledge_relationships       └──< citations >── answers >── queries
system_metrics   audit_logs   feedback >── answers
```

The documents → document_versions → document_chunks chain is the backbone of
temporal knowledge management: each re-ingestion creates a new immutable
version, drift is measured between versions, and historical queries can filter
by version/metadata.

### Ingestion (Module 1)

Upload flow: validation → file-type detection (magic bytes over extension) →
per-format text extraction → OCR fallback for scanned PDFs → metadata assembly
→ PostgreSQL (document + immutable version) → raw file stored under
`UPLOAD_DIR/{document_id}/v{n}.<ext>`. Chunking/embedding attach in Phase 3.

- Re-uploading the same filename with **changed** content creates a new
  version (temporal knowledge management); with **identical** content it
  deduplicates by SHA-256 and returns the existing version.
- Document metadata (JSON): `title`, `filename`, `file_type`, `source`,
  `author`, `department`, `created_at`, `access_level`, plus extraction info
  (`characters`, `page_count`, `used_ocr`, `warnings`). `title`/`author` fall
  back to values embedded in the file (PDF info, DOCX/XLSX properties, HTML
  `<title>`/meta author).
- **OCR** requires the [Tesseract](https://github.com/tesseract-ocr/tesseract)
  binary on PATH; without it, scanned PDFs are ingested with a warning in
  metadata instead of failing. Disable via `OCR_ENABLED=false`.
- Deleting a document requires being its owner or an ADMIN.

### Processing (Module 2)

Uploads are processed automatically (`AUTO_PROCESS_ON_UPLOAD=true`), and
`POST /documents/{id}/process` re-runs the pipeline on the current version:

1. **Cleaning/noise removal** — unicode normalization, de-hyphenation across
   line breaks, page-marker/separator removal, duplicate-line collapse.
   Page boundaries (`\f`, inserted by the PDF extractor) are preserved.
2. **Language detection** — langdetect (deterministic seed), stored on the
   document and every chunk.
3. **Semantic chunking** — structure-aware: section headings (numbered,
   markdown, ALL-CAPS, `[Sheet: …]`) start new chunks and are recorded as
   `section`; paragraphs are packed to `CHUNK_TARGET_TOKENS`; oversized
   paragraphs split at sentence boundaries with sentence overlap; each chunk
   carries `page_number` for citations.
4. **Embeddings** — sentence-transformers all-MiniLM-L6-v2 (configurable),
   L2-normalized, encoded off the event loop.
5. **Storage** — chunk rows in PostgreSQL hold the full relationship
   (embedding_ref → chunk → version → document) plus content, section, page,
   token estimate and metadata; vectors live in a persistent FAISS index
   under `VECTOR_INDEX_DIR` (a NumPy brute-force store is used automatically
   on interpreters without faiss wheels). Reprocessing a version replaces its
   chunks/vectors (idempotent); old versions keep theirs for historical
   answers; deleting a document removes its vectors.

### Hybrid knowledge repository (Module 4)

Three coordinated stores, with PostgreSQL as the source of truth:

| Store      | Holds                                                            |
| ---------- | ---------------------------------------------------------------- |
| PostgreSQL | users, documents, versions, chunks, metadata, queries, answers, feedback, metrics, audit |
| FAISS      | chunk embeddings (`embedding_ref` on each chunk row links back)  |
| Neo4j      | graph projection for structural/temporal queries                 |

Graph model:

```
(Document)-[:HAS_VERSION]->(Version)-[:CONTAINS]->(Chunk)-[:MENTIONS]->(Entity)
(Version v2)-[:SUPERSEDES]->(Version v1)
(Document)-[:AUTHORED_BY]->(Author)   (Document)-[:BELONGS_TO]->(Department)
(Document)-[:HAS_TOPIC]->(Topic)
```

Entities (acronyms + capitalized terms) and topics are extracted during
processing by a rule-based extractor
([app/modules/processing/entities.py](app/modules/processing/entities.py)),
stored per-chunk in PostgreSQL (`knowledge_entities` + chunk metadata) and
mirrored into Neo4j. Sync is an idempotent MERGE (`GRAPH_AUTO_SYNC=true`
runs it after every processing pass; `POST /graph/documents/{id}/sync`
re-runs it manually). If Neo4j is down the pipeline continues and marks
`graph_synced: false`; graph endpoints return 503. Browse the graph at
<http://localhost:7474> (neo4j / daarag-neo4j).

### Baseline RAG (Phase 5)

`POST /api/v1/chat/query` with `{"query": "...", "top_k": 6}` returns
`{answer, citations[], query_id, answer_id, model, retrieved_chunks,
latency_ms, analysis, retrieval, context_fusion, citation_generation}`
where each citation carries `document_id`, `document_name`, `version`,
`page`, `chunk_id`, `section`, `score`, `snippet` and `retrievers` (which
retriever(s) found it — see Module 6). `top_k` now means the *final*
number of chunks offered to the LLM, after Module 7's fusion pipeline
(default `CONTEXT_TOP_K` = 6) — retrieval itself over-fetches a larger
candidate pool. `citations` reflects only the sources the LLM's answer
actually cites (see Module 8 below), which can be fewer than `top_k`.

- Retrieval is routed adaptively (Module 6 — BM25 / vector / graph / hybrid,
  see below), filters hits below `RETRIEVAL_MIN_SCORE`, and answers **only
  from current document versions** (superseded versions keep their vectors
  for later historical-query phases but are excluded here).
- The candidate pool is then deduplicated, reranked, and compressed by
  Module 7, then generated and cited by Module 8 (both below).
- Every query is persisted end-to-end: `queries` → `retrieval_logs` (the
  full raw candidate pool) → `answers` (model, tokens, latency) →
  `citations` (only the sources the Citation Generator found the answer
  actually references).

### Query intelligence (Module 5)

`POST /api/v1/chat/analyze` turns a raw question into a structured query
(also embedded in every `/chat/query` response as `analysis`):

```json
{
  "original_query": "What was the leave policy before 2024?",
  "intent": "factual_lookup",
  "entities": ["leave policy"],
  "complexity": "simple",
  "temporal": true,
  "temporal_direction": "before",
  "target_date": "2024",
  "expanded_query": ["employee leave", "vacation policy", "leave rules", "..."]
}
```

Pipeline ([app/modules/query_intelligence/](app/modules/query_intelligence/)),
fully rule-based and deterministic:

1. **Parser** — normalization, tokenization, stopword-filtered keywords.
2. **Intent detection** — factual_lookup / procedural / comparative /
   analytical / summarization via pattern rules.
3. **NER** — three strategies: matching against `knowledge_entities`
   extracted from the corpus (the analyzer knows the KB's own vocabulary),
   cased-entity extraction, and a noun-phrase heuristic for lowercase queries.
4. **Complexity analyzer** — simple/moderate/complex scoring + sub-query
   decomposition of compound questions.
5. **Temporal detection** — before/after/at + year or month-year dates,
   past-tense markers, current-state markers. (Feeds a future historical
   version retrieval phase — the SUPERSEDES chain in Neo4j and versioned
   chunks in Postgres already exist for it.)
6. **Context expansion** — enterprise-domain synonym variants of the
   detected entities; the retrieval router embeds them as a second search
   vector and merges hits, widening recall beyond the literal phrasing.

The detected intent and normalized text are persisted on each `queries` row.

### Adaptive retrieval (Module 6)

```
Query → Query Intelligence → Retrieval Router
                               /    |    \
                            BM25  Vector  Graph
                               \    |    /
                               Hybrid (RRF)
                                   ↓
                                 Top-K
```

[app/modules/retrieval/](app/modules/retrieval/) replaces the Phase 5 "always
FAISS" retrieval with routing between four strategies:

| Route | Trigger (deterministic rule) | Backend |
| --- | --- | --- |
| **BM25** | Identifier/code (`POL-123`), clause reference (`Section 4.2`), quoted exact phrase, or a short (≤3 keyword) non-question query | [`rank-bm25`](app/modules/retrieval/bm25_index.py) over current-version chunk text, cached in memory and rebuilt automatically when the corpus changes (chunk-count + newest-chunk-id fingerprint) |
| **Vector** | Default — conceptual questions with no other trigger | FAISS (same store as Phase 3/5), query text plus expanded phrasings as a second search vector |
| **Graph** | Relationship/multi-hop phrasing (`related to`, `who wrote`, `between X and Y`, `depends on`, …) | Neo4j: chunks whose `MENTIONS` entities match the query's detected entities, plus a one-hop co-mention expansion (half-weighted) for the "multi-hop" part |
| **Hybrid** | `complexity == "complex"` (from Module 5's scorer) | All three retrievers, merged |

Routing lives in [router.py](app/modules/retrieval/router.py) as plain,
inspectable rules — swapping in a learned router later only requires
replacing `decide_route()`; every retriever and the fusion step are unchanged.

**Ranking**: results from more than one retriever are merged with
[Reciprocal Rank Fusion](app/modules/retrieval/fusion.py)
(`score = Σ 1/(60 + rank)`), so chunks found by multiple retrievers outrank
single-retriever hits. A single-retriever result keeps its native ordering
and scores unchanged.

**Robustness**: if Neo4j is unreachable, the graph retriever degrades to an
empty result instead of failing the request; if a non-vector route's chosen
retriever(s) return nothing, the service automatically falls back to vector
search, so routing can only add recall, never remove it. Every
`/chat/query` response includes a `retrieval` object — `route`, `reasons`,
`retriever_hits`, `fallback_used` — and each citation lists which
retriever(s) found it.

### Context fusion (Module 7)

```
BM25 results
      \
Vector results → Fusion (RRF) → Deduplication → Reranking → Compression → Context Builder
      /
Graph results
```

The retrieval router over-fetches a candidate pool (`RETRIEVAL_CANDIDATE_K`,
default 20 — already fused/deduplicated across retrievers by Module 6's
RRF) and hands it to [app/modules/context_fusion/](app/modules/context_fusion/),
which narrows it down to what actually reaches the LLM:

1. **Duplicate removal** ([dedup.py](app/modules/context_fusion/dedup.py)) —
   a defensive second pass beyond RRF's same-chunk-id merge: chunks with
   byte-identical normalized content (e.g. the same paragraph copied into
   two different documents) collapse to one, keeping the best-ranked
   occurrence.
2. **Reranking** ([reranker.py](app/modules/context_fusion/reranker.py)) — a
   real `cross-encoder/ms-marco-MiniLM-L-6-v2` model scores every
   (query, chunk) pair jointly (more precise than comparing independent
   embeddings) and reorders the candidates. Degrades to a passthrough
   (keeps retrieval order/score) if `RERANKER_ENABLED=false` or the
   `sentence-transformers` stack isn't installed — this also serves as the
   paper's rerank-on/off ablation baseline.
3. **Compression** ([compressor.py](app/modules/context_fusion/compressor.py))
   — truncates to the final `CONTEXT_TOP_K` (default 6, spec range 5–8),
   so the LLM never sees the full candidate pool.
4. **Context builder** ([builder.py](app/modules/context_fusion/builder.py))
   — renders the final chunks as numbered blocks:

   ```
   SOURCE 1
   Document: Employee Policy
   Version: 3
   Page: 4

   CONTENT:
   ...

   SOURCE 2
   Document: Leave Policy
   Version: 2
   Page: 7

   CONTENT:
   ...
   ```

   This exact text is embedded into the prompt the LLM receives (see Module 8
   below), citing `[1]`, `[2]`, … matching `SOURCE 1`, `SOURCE 2`, ….

Every `/chat/query` response carries a `context_fusion` object —
`candidates`, `after_dedup`, `final_count`, `reranker_model` — and each
citation now also reports its source document `version`.

### Enterprise LLM (Module 8)

```
Prompt Constructor
       |
System Prompt + User Query + Retrieved Context
       |
      LLM
       |
Citation Generator
       |
  Initial Answer
```

[app/modules/llm/](app/modules/llm/) turns the SOURCE-N context from Module 7
into a grounded, cited answer:

1. **Prompt Constructor** ([prompt_constructor.py](app/modules/llm/prompt_constructor.py))
   — combines the system instructions, the SOURCE-N context, and the
   question into a single flat string. One string (not a system/user
   split) so any provider — a raw completion endpoint, a chat API, a
   future local model — can consume it identically.
2. **LLM** ([providers.py](app/modules/llm/providers.py)) — every backend
   implements the same narrow interface:

   ```python
   class LLMProvider(Protocol):
       async def generate(self, prompt: str) -> str: ...
   ```

   Two concrete providers today: **`OllamaProvider`** (local inference —
   this module's zero-credential starting point; works with any pulled
   model, `OLLAMA_MODEL` default `gemma3:4b`, also tested against
   `llama3.2`-class models) and **`AnthropicProvider`** (Claude, via the
   official SDK). Adding OpenAI, Groq, or another backend later means
   writing one more class here — nothing in retrieval, fusion, or the
   API layer changes.
3. **Citation Generator** ([citation_generator.py](app/modules/llm/citation_generator.py))
   — parses the `[n]` markers the model actually wrote into its answer
   and validates them against the offered SOURCE blocks. The final
   `citations` list reflects only what the model used — not everything
   it was offered — with two safeguards: if the answer has *no* `[n]`
   markers at all, every offered source is kept (grounding evidence is
   never silently dropped); a marker citing a SOURCE number that doesn't
   exist is reported separately as a hallucinated citation, never treated
   as real evidence.

**Provider selection** (`LLM_PROVIDER`): `auto` (default) prefers Anthropic
when `ANTHROPIC_API_KEY` is set, else Ollama; force one explicitly with
`ollama` | `anthropic` | `extractive`. If the chosen LLM provider's call
fails at request time (e.g. Ollama isn't running), generation degrades to
the deterministic extractive baseline for that one response — the answer
still comes back (tagged `"<provider> (unavailable, used ...)"` in `model`)
instead of the request failing, the same graceful-degradation pattern used
for the embedding stack, reranker, and graph store elsewhere in this app.

Every `/chat/query` response carries a `citation_generation` object —
`cited`, `invalid_markers`, `used_fallback` — alongside `context_fusion`,
so it's visible exactly how many of the offered sources the answer used.

### Evidence verification (Module 9)

```
Generated Answer
       |
Claim Extraction
       |
For each claim
       |
Retrieve evidence  (cited SOURCE block + independent corpus-wide search)
       |
Compare claim <-> evidence   (NLI: entailment / contradiction / neutral)
       |
Support score
       |
Hallucination detection
       |
Response refinement
       |
Verified Answer
```

[app/modules/verification/](app/modules/verification/) checks a generated
answer against its evidence instead of trusting it:

1. **Claim Extraction** ([claim_extraction.py](app/modules/verification/claim_extraction.py))
   — splits the answer into per-sentence claims, each carrying the `[n]`
   citation marker(s) written after it and its exact character span in
   the original text (so refinement can annotate in place, not
   substring-replace).
2. **Evidence Retrieval** ([verification_service.py](app/services/verification_service.py))
   — two sources per claim: the SOURCE block(s) it actually cited (from
   Module 7's fused context), and an independent top-1 vector search over
   the *entire* current-version corpus using the claim text itself as the
   query. The independent search catches what citing alone can't: a claim
   unsupported by anything offered, or a claim mis-citing the wrong
   source.
3. **Fact Verification** ([nli_verifier.py](app/modules/verification/nli_verifier.py))
   — a real NLI cross-encoder (`cross-encoder/nli-deberta-v3-xsmall`)
   scores (evidence, claim) as entailment / contradiction / neutral. This
   is a deliberate departure from reusing Module 7's
   `cross-encoder/ms-marco-MiniLM-L-6-v2` reranker: a relevance model
   scores "same topic" — it would rate *"employees get 20 days of leave"*
   as highly relevant against evidence saying 25 days, because both
   sentences are about the same policy. NLI is the only one of the two
   that can tell a contradiction from a paraphrase.
4. **Support Score** — the model's entailment probability, `0.0`-`1.0`.
   `supported = verdict == "entailment" and support_score >= threshold`
   (`VERIFICATION_SUPPORT_THRESHOLD`, default `0.5`).
5. **Citation Verification** — checked separately from the overall support
   score: does the *specific source the answer cited* actually entail the
   claim, independent of whether some other, uncited chunk would have?
   Surfaced per-claim as `citation_verified`.
6. **Hallucination Detection** — `hallucination_detected = any claim not
   supported`. An honest "I could not find relevant information..."
   answer (no context was ever offered) is never flagged — there's
   nothing to fact-check, and declining to answer isn't a hallucination.
7. **Response Refinement** ([refinement.py](app/modules/verification/refinement.py))
   — inserts an inline warning right after every unsupported sentence:
   `[⚠ contradicted by source]` when the evidence actively disagrees,
   `[⚠ unverified]` for neutral/no-evidence claims. This refined text is
   what gets persisted and returned as `answer`, not the raw model output.

Every `/chat/query` response carries `confidence`, `hallucination_detected`,
a `claim_verifications` list (`claim`, `support_score`, `supported`,
`verdict`, `source`, `page`, `citation_verified`, ...), and a
`verification` transparency object (`enabled`, `model`, `threshold`,
`claims_checked`). Verified live against real Ollama-generated answers: a
faithful answer ("employees receive 10 paid sick days") scored `supported:
true` with `hallucination_detected: false`; a real Gemma3:4b hallucination
that added an unsupported detail ("...in addition to public holidays" —
not in the source document) was caught with `support_score: 0.04`,
`hallucination_detected: true`, and the refined answer visibly flagged.

Like the reranker, verification degrades instead of failing the request:
`VERIFICATION_ENABLED=false` or a missing `sentence-transformers` stack
skips it entirely (`verification.enabled: false`, `confidence`/
`hallucination_detected` come back `null`) rather than fabricating a score.

### Knowledge evolution (Module 3)

```
New Document / Updated Document
             |
       Change Detector
             |
       Version Comparator
             |
      +------+------+
      |             |
 Text Change   Semantic Change
      |             |
 Diff Detector  Drift Detector
      +------+------+
             |
      Conflict Detector
             |
       Version Manager
             |
   Incremental Re-indexer
             |
     FAISS / Neo4j update
```

[app/modules/evolution/](app/modules/evolution/) turns every re-upload
into a measured, recorded transition instead of a silent overwrite:

1. **Change Detector** ([change_detector.py](app/modules/evolution/change_detector.py))
   — content-hash comparison. By the time this stage runs, a real change
   is guaranteed: `DocumentService` already deduplicates identical
   re-uploads before a version is even created. Its job is only to
   classify a brand-new document (no prior version) from a genuine
   revision.
2. **Diff Detector** ([diff_detector.py](app/modules/evolution/diff_detector.py))
   — sentence-level text diff via Python's `difflib`
   (Ratcliff/Obershelp), classifying every region as unchanged, added,
   removed, or *replaced*. The replaced pairs — an old sentence 1:1
   aligned with the new sentence that took its place — are exactly what
   the Conflict Detector needs.
3. **Drift Detector** ([drift_detector.py](app/modules/evolution/drift_detector.py))
   — semantic-level comparison the Diff Detector can't do: each
   version's chunks are mean-pooled into a centroid embedding, and drift
   is `1 - cosine_similarity(old_centroid, new_centroid)`, bucketed into
   none/minor/moderate/major. A heavy rewording with the same meaning
   shows low drift; a one-word policy change ("20 days" -> "30 days")
   shows real drift — verified live: a pure rephrasing scored
   measurably lower drift than an actual value change over the same
   sentence.
4. **Conflict Detector** ([conflict_detector.py](app/modules/evolution/conflict_detector.py))
   — reuses Module 9's NLI cross-encoder rather than a second model,
   applied to the Diff Detector's replaced pairs: does the new sentence
   *contradict* the one it replaced? Caught live, unprompted: "Employees
   receive 20 days..." -> "...30 days..." scored a 0.99 contradiction
   probability and was flagged as a conflict, not just a wording change.
5. **Version Manager** — already the backbone of the data model from
   Phase 1: `document_versions.is_current` marks exactly one active
   version per document, and old versions/chunks/vectors are **never
   deleted** (`DocumentVersionRead.status` reports `"active"` or
   `"deprecated"`). This is what makes step 6 possible.
6. **Incremental Re-indexer** — already how `ProcessingService` has
   worked since Phase 3: a new version adds its vectors to FAISS and
   re-syncs the Neo4j projection without touching any prior version's
   vectors or graph nodes — a true incremental update, not a rebuild.

Every version transition is persisted as a `VersionComparison`
(`GET /documents/{id}/evolution`): from/to version, text similarity,
added/removed/replaced counts and sentences, drift score and magnitude,
detected conflicts with their contradiction score, and re-indexing
stats — a full, queryable timeline of how a document's knowledge
changed, not just its content.

**Temporal-aware retrieval.** Module 5's temporal detector already
recognized "before 2024" / "as of 2023" phrasing; through Phase 10 nothing
consumed it, so every query answered from current knowledge regardless of
tense. `/chat/query` now resolves that intent
([temporal.py](app/modules/retrieval/temporal.py)) to a cutoff datetime
and retrieves each document's version that was active *at that time*
instead of its current one — implemented for vector search, the router's
default for exactly this kind of conceptual/historical question (BM25
and graph retrieval remain current-only, a documented scope boundary).
Verified live against the same document: **"What is the current leave
policy?"** answered 30 days (today's version); **"What was the leave
policy before 2024?"** answered 20 days, citing the version created in
2023 — the same underlying data, two different truths depending on when
you ask, exactly the DAA-RAG thesis.

### Concept drift detection (Phase 12)

```
old chunk embedding
       |
cosine similarity  -> nearest-neighbor match to a new chunk
       |
new chunk embedding
       |
drift_score = 1 - cosine_similarity        (reported; secondary gate)
       |
bidirectional NLI entailment                (primary gate)
       |
rewording / expansion / narrowing / contradiction / topic_shift
```

Phase 11's Drift Detector reduces a whole document to one centroid
number; its Conflict Detector only asks "does this contradict?" over
sentence pairs a text diff happened to align. Neither can say *which
chunk* changed meaning, and neither can tell a broadened scope from a
reworded sentence. [concept_drift_detector.py](app/modules/evolution/concept_drift_detector.py)
closes both gaps: each old chunk is paired with its *mutual* nearest
neighbor in the new version by embedding cosine similarity (not
position — chunk boundaries shift between versions), and every matched
pair is classified by running NLI **in both directions**:

- both directions entail → **rewording** (same meaning, different words)
- new entails old, not the reverse → **expansion** (broader scope)
- old entails new, not the reverse → **narrowing** (narrower scope)
- either direction contradicts → **contradiction**
- neither entails, no contradiction → **topic_shift**
- no reciprocal match at all → **removed** (old side) / **added** (new side)

**Why NLI gates the flag, not cosine distance.** The spec's own recipe
(`drift_score > threshold`) was tried first and measured against the
real embedder:

| Change | Cosine drift |
|---|---|
| Paraphrase ("25 days... per year" → "twenty-five days... annually") | **0.132** |
| "2 days" → "3 days" (a real, contradicting fact) | **0.037** |
| "customer records" → "customer and employee records" | 0.059 |
| Unrelated topic swap | 0.796 |

No single threshold separates the harmless paraphrase from the one-digit
contradiction — the paraphrase measures as *more* drifted than the
actual fact change. Sentence embeddings track lexical overlap more than
exact numeric content. So a matched pair is flagged when **NLI says
it isn't a plain rewording, or cosine distance crosses the threshold**
(`CONCEPT_DRIFT_THRESHOLD`, default `0.15`) — NLI is the primary
signal for *meaning* change; cosine distance still does the chunk
*alignment* and remains a backstop for large topic-level shifts.

Every version transition (after the first) gets a `ConceptDriftReport`
(`GET /documents/{id}/concept-drift`): `drift_score` (mean over matched
pairs), a dominant `drift_type`, and `changed_chunks` — each with both
chunks' ids/content, its own drift score, and its own type. Verified
live on the spec's own examples: "confidential info includes customer
records" → "...customer and employee records" measured 0.059 cosine
drift (well under the 0.15 threshold) and was still correctly caught and
typed `expansion` via the NLI gate; the same document run through
Phase 11's evolution endpoint shows `has_conflict: false` for that exact
transition — proof this is new detection capability, not a duplicate.
"2 days" → "3 days" measured 0.037 (the same value found in
calibration) and was correctly typed `contradiction`, agreeing with
Phase 11's independent text-diff-based conflict detector for the same
change reached a different way.

### Knowledge conflict detection (Phase 13)

```
Document A: "Employees get 20 days leave."
Document B: "Employees get 25 days leave."

      Claim A
         |
    Contradiction
         |
      Claim B
         |
  priority -> date -> version -> unresolved
         |
  Context Fusion: drop the loser, or keep both and flag it
```

Phases 11–12 compare a document against *its own* earlier versions.
Phase 13 compares it against *every other document* — the enterprise
reality of two independent sources of truth quietly disagreeing.
[conflict_service.py](app/services/conflict_service.py) runs at
ingestion time, alongside evolution/drift analysis: for each new chunk,
a corpus-wide vector search (excluding the chunk's own document) finds
same-topic candidates above `CONFLICT_SIMILARITY_THRESHOLD` (default
`0.5`), and NLI flags a contradiction above
`CONFLICT_CONTRADICTION_THRESHOLD` (default `0.5`).

**Authority resolution** ([authority_resolver.py](app/modules/conflict/authority_resolver.py))
then decides which claim to prefer, stopping at the first factor that
isn't a tie:

1. **Document priority** — an explicit rank set at upload
   (`priority` form field, default `0`; higher wins). This is the one
   factor a human actually controls — Legal overrides a draft HR memo
   because someone said so, not because of an inferred rule.
2. **Date** — the more recently created version wins.
3. **Version number** — the more revised document wins.
4. **Unresolved** — all three tie. Department is carried on both sides
   for display but deliberately never auto-ranked: there's no universal
   ordering of "HR" vs "Legal" vs "Facilities" without
   organization-specific rules, so treating one as inherently more
   authoritative would be a fabricated signal, not a real one.

Detection is corpus-wide and runs once, at ingestion — not per query.
`GET /conflicts` and `GET /documents/{id}/conflicts` browse everything
found. **Context Fusion** then does the cheap part at query time
([conflict_resolution.py](app/modules/context_fusion/conflict_resolution.py)):
look up precomputed conflicts among today's retrieval candidates (a
plain DB read — no live NLI on the query path) and either drop the
losing chunk from what the LLM sees, or, if authority never resolved it,
keep both claims and surface the disagreement in
`context_fusion.conflicts` instead — the spec's two options ("select the
authoritative version or expose the conflict"), applied together rather
than as an either/or choice.

Verified live with the spec's own example: uploaded "HR Handbook"
(priority 1, "Employees get 20 days leave") and "Legal Policy" (priority
5, "Employees get 25 days leave") as two independent documents.
`GET /conflicts` showed the pair at **0.98 contradiction**, resolved in
Legal Policy's favor ("higher document priority (5 > 1)"). A subsequent
`/chat/query` about leave days confirmed the HR Handbook's "20 days"
chunk was absent from the final citations — dropped by Context
Fusion — while `context_fusion.conflicts` still reported exactly what
was resolved and why. The same corpus-wide scan also caught (and
correctly resolved) two more contradictions against an unrelated
leftover "30 days" document from an earlier demo, confirming detection
generalizes across the whole corpus, not just a hand-picked pair.

### Incremental re-indexing (Phase 14)

```
Document changed
       |
Identify changed chunks        (diff new chunks vs. what is indexed)
       |
Process only changed chunks
       |
Generate embeddings            <- only for those
       |
Update affected vectors        (unchanged ones keep/copy their vector)
       |
Update Neo4j nodes             (only the changed version's chunks)
```

The naive reaction to an edited document is to drop everything it
produced and start over. Embedding is by far the most expensive step in
the pipeline — a transformer forward pass per chunk — and in a typical
enterprise edit (one clause in a fifty-clause policy) all but one chunk
are byte-for-byte identical to what is already indexed. Re-embedding
them buys nothing.

[incremental.py](app/modules/processing/incremental.py) is the "identify
changed chunks" stage: it diffs the freshly produced chunk drafts against
the stored ones and classifies each as **reused**, **to embed**, or
**obsolete**. Matching is by exact chunk content — chunking is
deterministic, so an untouched region produces byte-identical chunks —
and duplicate chunks are matched one-for-one rather than collapsed, so
every draft still gets its own vector. Reordering is free: a chunk that
merely moved is matched by content and reused.

Two paths, because they differ in what may be thrown away:

- **Re-running the same version** — unchanged chunks keep their existing
  row *and* vector; nothing is written to the index at all. Only genuinely
  changed chunks are embedded, and only removed chunks are retired. (Row
  indices are permuted through a parked range first, so the
  `(version_id, chunk_index)` unique constraint can't trip mid-update.)
- **A new version** — new rows are required (the old version's rows are
  preserved for historical retrieval), but an unchanged chunk's stored
  vector is copied via FAISS `reconstruct` instead of recomputed. The
  previous version's vectors are **never** removed: Phase 11's temporal
  ("what was the policy in 2023?") retrieval depends on them.

Two correctness guards worth naming: a chunk embedded by a *different*
model is never offered for reuse (its vector isn't interchangeable with
the current model's), and a reusable chunk whose vector has gone missing
from the index falls back to being embedded rather than failing the run.

The Neo4j projection is incremental in the same spirit — only the version
just processed is sent, since every other version's nodes are already in
the graph and unchanged. All graph writes are idempotent MERGEs, so a
partial payload converges to the same graph.

Every `/process` response reports the saving:

```json
{
  "chunk_count": 4,
  "embedded_count": 1,
  "chunks_reused": 3,
  "vectors_added": 4,
  "vectors_removed": 0,
  "incremental": true
}
```

`embedded_count + chunks_reused == chunk_count` always, which makes the
claim auditable rather than asserted. Setting
`INCREMENTAL_REINDEX_ENABLED=false` restores the naive full rebuild as
the paper's ablation baseline — the same one-clause edit then reports
`embedded_count == chunk_count` and `chunks_reused == 0`.

**Measured, live.** A 12-clause policy was ingested against real
PostgreSQL/Neo4j/FAISS, then re-uploaded with exactly one clause edited
(`Sick leave is 10 days` → `15 days`):

| Run | chunks | embedded | reused | vectors added | vectors removed |
|---|---|---|---|---|---|
| First ingest (v1) | 12 | 12 | 0 | 12 | 0 |
| One clause edited (v2) | 12 | **1** | **11** | 12 | 0 |
| Re-run of an unchanged version | 12 | **0** | **12** | **0** | **0** |

Version 1 kept all 12 of its chunks and vector ids (still returning the
old "10 days" text for historical queries), and the two versions' vector
ids do not overlap — no aliasing between versions.

How much that saves depends on chunk size, and it is worth being precise
rather than quoting the 12→1 count as if it were a 12× speedup. Measured
directly on `all-MiniLM-L6-v2` (CPU) with realistic ~300-token chunks,
one chunk edited:

| Document | Full rebuild | Incremental | Saving |
|---|---|---|---|
| 12 chunks | 551 ms | 55 ms | 90.0% (10×) |
| 50 chunks | 2094 ms | 52 ms | 97.5% (40×) |
| 120 chunks | 4789 ms | 66 ms | 98.6% (73×) |

The benefit grows with document size, which is exactly the regime that
matters for enterprise knowledge bases. On *very small* chunks the
advantage is much smaller (a 12-clause doc of one-line clauses measured
only 2.3×, since fixed per-call overhead dominates and short texts batch
efficiently) — worth stating plainly, since it bounds the claim honestly.
Note also that end-to-end `/process` wall-clock is not 10× faster: the
Phase 11–13 analysis passes (drift, concept drift, cross-document
conflict detection) run alongside re-indexing and dominate on small
documents. The saving being claimed here is specifically the embedding
and vector-write work.

### Frontend API surface (Phase 15)

The React app (`../frontend`, Vite dev server on `:5173`) talks to this
backend over REST only — no direct database or service access — using a
single fetch wrapper (`src/lib/api.ts`) that attaches the Bearer token and
clears it on any 401. `VITE_API_URL` defaults to `http://localhost:8000/api/v1`,
which is where `uvicorn app.main:app` serves.

| Group | Endpoints |
|---|---|
| `/auth` | `POST /register`, `POST /login`, `GET /me` |
| `/documents` | `POST /upload`, `GET ""`, `GET /{id}`, `DELETE /{id}`, `GET /{id}/versions` (plus `/chunks`, `/process`, `/evolution`, `/concept-drift`, `/conflicts`) |
| `/chat` | `POST /query`, `GET /history` (plus `POST /analyze`) |
| `/search` | `POST /semantic`, `POST /hybrid` |
| `/knowledge` | `GET /entities`, `GET /relationships`, `GET /versions`, `GET /drift` |
| `/feedback` | `POST ""` |
| `/analytics` | `GET /dashboard`, `GET /metrics` |
| `/admin` | `GET /system-status`, `GET /audit-logs` — **ADMIN only** |
| other | `GET /health`, `GET /conflicts`, `/graph/*` |

Notes on the design:

- **`/search/*` vs `/chat/query`.** `/chat/query` runs the whole RAG
  pipeline and returns a generated, verified answer. The search endpoints
  stop after retrieval + fusion and return the ranked evidence itself —
  what a results page needs. They reuse Modules 6 and 7 rather than
  reimplementing retrieval, and simply pin the route the adaptive router
  would otherwise pick (`semantic` → vector, `hybrid` → BM25 + vector +
  graph fused by RRF), via a `force_route` argument that `/chat/query`
  never passes.
- **`/chat/history` is per-caller.** It is scoped to the authenticated
  user's own queries; one user's questions are never visible to another.
- **`/knowledge/*` and `/analytics/*` are read-only views** over data
  earlier phases already wrote — entities (Module 2), the corpus-wide
  version history (Phase 11), the drift feed (Phases 11–12), the
  verification fields Module 9 stamps on each answer, and Phase 13's
  conflicts. There is no separate metrics pipeline to keep in sync.
- **`/feedback` is the Module 10 signal** — the human judgement continuous
  learning will train on. It is validated against a real answer row (404
  otherwise), audited, and surfaced in the analytics aggregates.
- **`/admin/*` is role-guarded.** Registration creates a `USER`; these
  endpoints expose operational internals and everyone's audit trail.
  Promote an operator explicitly:

  ```sql
  UPDATE users SET role = 'ADMIN' WHERE email = 'you@example.com';
  ```

  `/admin/system-status` reports whether each optional ML feature is
  *actually* live — enabled in config **and** with its dependency
  importable, the same two conditions the services themselves check — so
  it cannot claim a module is on when the model isn't installed.
- **Pagination is totally ordered.** Every feed orders by
  `created_at DESC` plus a tiebreak (`id`/`version_number`); without one,
  rows sharing a timestamp can repeat or vanish between pages.

**Verified live** with both servers running (backend `:8000`, Vite
`:5173`, real PostgreSQL/Neo4j/FAISS/Ollama): CORS preflight from
`http://localhost:5173` returns the correct
`access-control-allow-origin`; register → login → `/auth/me` round-trips
in exactly the shape `AuthContext` expects
(`{access_token, token_type, expires_in, user}`); a bad token returns
`401` with a string `detail`, which is the field `api.ts` reads before
clearing the session; and every Phase 15 endpoint was exercised against
real data (history with citations, both search modes, all four knowledge
feeds, feedback, dashboard/metrics, and — after the SQL promotion above —
both admin endpoints, with a plain `USER` correctly refused `403`).

**Frontend wiring status.** The React app currently calls only the three
`/auth` endpoints for real; its other pages (chat, search, dashboard,
collections, …) still render from `src/data/mock*.ts`. Those pages need
frontend changes to consume the endpoints above, and the frontend has been
treated as read-only for this project — so Phase 15 delivers and verifies
the backend contract they will bind to, rather than modifying the app.

### Authentication (kept deliberately simple)

Single signed access token (HS256 JWT) with a 7-day expiry — **no refresh
tokens, rotation, or server-side sessions**. JWT (rather than an opaque token)
is required because the frontend decodes the token's `exp` claim client-side.
Flow: `POST /auth/login` → `{access_token, token_type, expires_in, user}` →
frontend sends `Authorization: Bearer <token>` → `get_current_user` dependency
resolves the user. Role guards are available via `require_roles(...)` in
[app/api/deps.py](app/api/deps.py).

## Architecture

```
backend/
  app/
    main.py               # App factory, middleware, lifespan
    core/                 # config, logging, database, neo4j, security (JWT), exceptions
    api/
      deps.py             # Dependency wiring (settings -> repos -> services)
      v1/                 # /api/v1 routers and endpoints
    models/               # SQLAlchemy declarative base + mixins
    schemas/              # Pydantic v2 request/response models
    services/             # Business logic (routes stay thin)
    repositories/         # Data access over async SQLAlchemy sessions
    modules/              # DAA-RAG pipeline module interfaces (Phases 1-4)
      ingestion/ processing/ evolution/ repository/ query_intelligence/
      retrieval/ context_fusion/ llm/ verification/ learning/
    utils/
  alembic/                # Async migration environment
  tests/                  # pytest suite
```

Layering rule: **route → service → repository → database**. Route handlers contain
no business logic.

## Prerequisites

- Python 3.11+ (3.11/3.12 required for the ML extras — see below)
- Docker Desktop (for PostgreSQL and Neo4j), or native installs
- The frontend expects the API at `http://localhost:8000/api/v1`
- Optional but recommended: [Ollama](https://ollama.com) running locally
  with a model pulled (`ollama pull gemma3:4b` or `llama3.2`) — the default
  LLM provider for `/chat/query`. Without it, `LLM_PROVIDER=auto` falls
  back to the extractive baseline (no LLM call, still fully functional
  for testing/demoing retrieval), or set `LLM_PROVIDER=anthropic` with
  `ANTHROPIC_API_KEY` instead.

## Setup

### 1. Environment

```powershell
cd backend
Copy-Item .env.example .env    # then edit values (JWT_SECRET_KEY at minimum)
```

### 2. Databases (Docker Compose, from the repo root)

```powershell
docker compose up -d
```

Starts PostgreSQL 16 (role `daarag`/`daarag`, **db `rag_research_paper`**) on
5432 and Neo4j 5 (`neo4j`/`daarag-neo4j`) on 7474 (browser) / 7687 (bolt).

> **This project's database is `rag_research_paper`.** Do not point
> `DATABASE_URL` at another project's database. If the Postgres server was
> first initialised by a different project, `POSTGRES_DB` won't take effect
> (it only applies to an empty data volume) — create this project's database
> once, by hand:
>
> ```powershell
> docker exec <postgres-container> psql -U daarag -d postgres -c "CREATE DATABASE rag_research_paper OWNER daarag;"
> cd backend; python -m alembic upgrade head
> ```

> **Port conflict note:** this machine runs a native PostgreSQL 18 service on 5432.
> Either stop it (`Stop-Service postgresql-x64-18` as admin), or start compose with
> `POSTGRES_HOST_PORT=5433 docker compose up -d` and set
> `DATABASE_URL=postgresql+asyncpg://daarag:daarag@localhost:5433/rag_research_paper`
> in `.env`. Alternatively, create the role/db in the native server and point
> `DATABASE_URL` at it.

### 3. Python dependencies

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-core.txt      # API runtime (Phase 0)
pip install -r requirements-dev.txt       # + test tooling
```

`requirements.txt` (core + ML: LangChain, Sentence Transformers, FAISS) is the full
production set used by the Docker image. Install it locally only on Python 3.11/3.12,
where torch/faiss wheels are available.

### 4. Migrations

```powershell
alembic upgrade head                       # no-op until Phase 1 adds models
alembic revision --autogenerate -m "..."   # when models change
```

### 5. Run

```powershell
uvicorn app.main:app --reload --port 8000
```

- Health: <http://localhost:8000/api/v1/health>
- OpenAPI docs: <http://localhost:8000/docs> (disabled in production)

The health response reports per-component status; the API returns HTTP 200 with
`"status": "degraded"` when PostgreSQL or Neo4j are unreachable.

### 6. Tests

```powershell
pytest
```

The health tests do not require running databases.

## Docker image

```powershell
cd backend
docker build -t daa-rag-backend .
docker run --rm -p 8000:8000 --env-file .env daa-rag-backend
```

When running the container against the compose databases, set
`DATABASE_URL`/`NEO4J_URI` to use `host.docker.internal` instead of `localhost`.
Same for Ollama running on the host: set `OLLAMA_BASE_URL=http://host.docker.internal:11434`.

## Configuration reference

All settings are environment variables (see [.env.example](.env.example)):
app metadata, `LOG_LEVEL`/`LOG_JSON`, `DATABASE_URL` (async SQLAlchemy URL),
`NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD`, JWT settings, `CORS_ORIGINS`
(comma-separated; defaults cover the Vite dev/preview servers), evidence
verification (`VERIFICATION_ENABLED`, `VERIFICATION_MODEL_NAME`,
`VERIFICATION_SUPPORT_THRESHOLD`, `VERIFICATION_MIN_EVIDENCE_SCORE`),
knowledge evolution (`EVOLUTION_ENABLED`, `EVOLUTION_CONFLICT_THRESHOLD`),
concept drift detection (`CONCEPT_DRIFT_THRESHOLD`), knowledge
conflict detection (`CONFLICT_DETECTION_ENABLED`,
`CONFLICT_SIMILARITY_THRESHOLD`, `CONFLICT_CONTRADICTION_THRESHOLD`), and
incremental re-indexing (`INCREMENTAL_REINDEX_ENABLED`).
