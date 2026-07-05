"""Resolution Copilot (RAG) services.

This sub-package holds the write path (flattening, embedding, indexing) and,
in later phases, retrieval and generation. Like every service, nothing here
imports FastAPI; failures surface as domain exceptions.
"""
