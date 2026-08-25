---
id: doc-digest
name: Document digest
description: Structured digest of the user's uploaded documents
triggers:
  - digest this
  - summarize my uploads
allowed_tools:
  - search_documents
---
When this skill is active, search uploaded documents with search_documents and stay on those files.
Do not use the open web. If nothing matches, say so.

Structure the response as:
1. Key facts
2. Open questions
3. Contradictions

Cite the source document for each claim.
