# MagiFab Knowledge Engine (Replacement Backend)

This module is a clean replacement candidate for the current interval/scene-first companion runtime. It deliberately has no imports from `app.py`, `services/companion_pipeline.py`, UI code, or the legacy file cache.

## Runtime invariant

A work is not queryable until its **entire source is ingested and finalized**:

- Movies must have detected segments covering the declared duration.
- Books must have detected paragraphs covering every declared page.
- `KnowledgeEngine.retrieve()` is read-only and raises `whole_work_ingestion_required` until the snapshot is `READY`.

## Ingestion architecture

```text
Video -> scene/subtitle/character/object adapters -> segments + mentions
PDF -> OCR/layout/chapter/entity adapters           -> paragraphs + mentions
                                              \       /
                                           entity resolver
                                                 |
                timeline events + entity memory + relationship graph + embeddings
                                                 |
                                    durable knowledge snapshot + vector index
                                                 |
                          current context + prior events + semantic matches + graph expansion
                                                 |
                                           grounded LLM companion
```

Model integrations are adapter inputs, not request-time assumptions. A production worker should use FFmpeg/PySceneDetect, Whisper, OCR/layout analysis, object/face tracking, and an LLM extraction pass to create `Segment`, `EntityMention`, and `RelationshipMention` records. `FileKnowledgeRepository` provides atomic JSON persistence locally; production workers write once to a Postgres transaction, with graph tables and `pgvector` embeddings replacing it.

## Retrieval contract

`retrieve()` always assembles an auditable context containing:

1. the playback/page segment (if supplied),
2. preceding timeline segments,
3. semantic vector matches across the whole work,
4. canonical entity memories and aliases,
5. relationship graph edges, and
6. source spans for every relation.

The LLM must receive this `RetrievalContext`, source-cite claims from it, and say it cannot verify information absent from the context. It must not receive raw current-frame state as its sole factual input.
