# Phase 2b: Intelligence Layer & Full Integration - Complete How-To Guide

> 🚧 **PHASE 2b IN PROGRESS**
>
> | Component | URL |
> |-----------|-----|
> | **Frontend (CloudFront)** | `https://d2bhnqevtvjc7f.cloudfront.net` |
> | **Backend (App Runner)** | `https://yhvmf3inyx.us-east-1.awsapprunner.com` |
>
> Building on Phase 2a with advanced retrieval intelligence.

**Purpose:** This guide adds the intelligence layer to the agent: Knowledge Graph for entity-based queries, advanced RAG with hybrid search and reranking, and multi-tool orchestration for complex queries that combine SQL and document retrieval.

**Estimated Time:** 6-10 hours depending on familiarity with graph databases and information retrieval

**Prerequisites:** Phase 2a must be complete and verified before starting Phase 2b. This includes:
- Neo4j AuraDB account created and local Neo4j running
- VLM extraction completed for all documents
- SQL tool working with 10-K financial data
- Basic RAG tool working with dense vector search in Pinecone
- All documents indexed in Pinecone (~1400 vectors)

**💰 Cost Estimate:** 
- Query expansion: ~$0.005/query (Nova Lite, 3 variants)
- Reranking: ~$0.015/query (Nova Lite, 15 candidates scored)
- Knowledge Graph: $0 (Neo4j queries are free)
- Monthly estimate: ~$3-5 for ~200 queries/month
- No significant one-time costs (using existing infrastructure from Phase 2a)

**⚠️ Important:** This phase adds multiple retrieval components. Test each component independently before integration to isolate issues.

**🖥️ Development Environment:** Continue using Windows with WSL 2 as in previous phases. All terminal commands run in your WSL terminal (Ubuntu).

---

## Table of Contents

- [Quick Start Workflow Summary](#quick-start-workflow-summary)
- [1. Prerequisites Verification](#1-prerequisites-verification)
- [2. Knowledge Graph Ontology](#2-knowledge-graph-ontology)
- [3. Entity Extraction](#3-entity-extraction)
- [4. Neo4j Graph Store](#4-neo4j-graph-store)
- [5. Entity Indexing Pipeline](#5-entity-indexing-pipeline)
- [6. Graph Query Implementation](#6-graph-query-implementation)
- [7. BM25 Sparse Vectors](#7-bm25-sparse-vectors)
- [8. Query Expansion](#8-query-expansion)
- [9. RRF Fusion](#9-rrf-fusion)
- [10. Cross-Encoder Reranking](#10-cross-encoder-reranking)
- [11. Hybrid RAG Integration](#11-hybrid-rag-integration)
- [12. Multi-Tool Orchestration](#12-multi-tool-orchestration)
- [12b. Cross-Document Analysis Workflow](#12b-cross-document-analysis-workflow)
- [13. End-to-End Verification](#13-end-to-end-verification)
- [Phase 2b Completion Checklist](#phase-2b-completion-checklist)
- [Common Issues and Solutions](#common-issues-and-solutions)
- [Files Created/Modified in Phase 2b](#files-createdmodified-in-phase-2b)
- [Branch Management and Next Steps](#branch-management-and-next-steps)

---

## Quick Start Workflow Summary

**📋 This guide is designed to be followed linearly.** Complete each section in order (1→2→3→...→13).

**Overall Phase 2b Workflow:**
1. **Prerequisites** (Section 1): Verify Phase 2a complete, Neo4j running, Pinecone indexed
2. **Ontology** (Section 2): Define entity types and relationships for financial domain
3. **Entity Extraction** (Section 3): spaCy NER with custom financial patterns
4. **Graph Store** (Section 4): Neo4j connection and CRUD operations
5. **Entity Indexing** (Section 5): Extract and store entities from all documents
6. **Graph Queries** (Section 6): Implement 1-hop and 2-hop traversals
7. **BM25 Vectors** (Section 7): Add sparse vectors to Pinecone for keyword matching
8. **Query Expansion** (Section 8): Generate query variants via Nova Lite
9. **RRF Fusion** (Section 9): Merge results from multiple retrieval sources
10. **Reranking** (Section 10): LLM-based relevance scoring
11. **Hybrid RAG** (Section 11): Integrate all retrieval components
12. **Multi-Tool** (Section 12): SQL + RAG + Tavily combined queries
12b. **Cross-Document Analysis** (Section 12b): News vs 10-K verification workflow
13. **Verification** (Section 13): End-to-end testing

**Key Principle:** Build retrieval intelligence in layers. Each component improves retrieval quality and can be tested independently before integration.

**Architecture Overview:**
```
┌─────────────────────────────────────────────────────────────────────────┐
│                          User Query                                      │
│                  "What are Apple's China risks?"                        │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Query Expansion                                   │
│                      (Nova Lite - 3 variants)                           │
│                                                                          │
│  Original: "What are Apple's China risks?"                              │
│  Variant 1: "Apple supply chain exposure to China"                      │
│  Variant 2: "Apple Inc China-related risk factors"                      │
│  Variant 3: "AAPL Chinese market business risks"                        │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         ▼                      ▼                      ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  Dense Search   │   │  BM25 Search    │   │ Knowledge Graph │
│   (Pinecone)    │   │   (Pinecone)    │   │    (Neo4j)      │
│                 │   │                 │   │                 │
│ Semantic match  │   │ Keyword match   │   │ Entity lookup   │
│ "supply chain   │   │ "China" "risk"  │   │ Apple→China     │
│  risks"         │   │ exact terms     │   │ relationships   │
│                 │   │                 │   │                 │
│ top_k = 15      │   │ top_k = 15      │   │ 1-2 hop query   │
│ (×4 variants)   │   │ (×4 variants)   │   │                 │
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         RRF Fusion                                       │
│              (Reciprocal Rank Fusion - merge results)                   │
│                                                                          │
│  Score = Σ 1/(60 + rank) across all sources                             │
│  Combines semantic + keyword + entity matches                           │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Cross-Encoder Reranking                               │
│                   (Nova Lite relevance scoring)                         │
│                                                                          │
│  "Rate 1-10: Query='Apple China risks' Doc='The Company faces...' "    │
│  Keep top 5 highest scoring passages                                    │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       Final Response                                     │
│                                                                          │
│  [1] Apple 10-K 2024, Item 1A, Page 18 (Score: 9/10)                   │
│      "The Company's operations in Greater China..."                     │
│  [2] Apple 10-K 2024, Item 1A, Page 19 (Score: 8/10)                   │
│      "Geopolitical tensions between the US and China..."                │
└─────────────────────────────────────────────────────────────────────────┘
```

**Estimated Time:** 6-10 hours

---

## 1. Prerequisites Verification

### What We're Doing
Verifying Phase 2a is complete and all components are working before adding intelligence layer.

### Why This Matters
- **Foundation:** Phase 2b builds on Phase 2a infrastructure
- **Dependencies:** Knowledge Graph requires Neo4j, hybrid search requires existing Pinecone index
- **Integration:** Advanced RAG upgrades the basic RAG from Phase 2a

### 1.1 Verify Phase 2a Completion

**Command (run in WSL terminal):**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Check Neo4j is running
docker-compose ps neo4j

# Test Neo4j connection
docker-compose exec neo4j cypher-shell -u neo4j -p localdevpassword "RETURN 1 as test"
```

**Expected Output:**
```
+------+
| test |
+------+
| 1    |
+------+
```

### 1.2 Verify Pinecone Has Indexed Vectors

**Command:**
```bash
docker-compose exec backend python -c "
from src.utils.pinecone_client import PineconeClient
from src.config.settings import get_settings

settings = get_settings()
client = PineconeClient(
    api_key=settings.pinecone_api_key,
    index_name=settings.pinecone_index_name
)
stats = client.get_stats()
print(f'Total vectors indexed: {stats[\"total_vector_count\"]}')
"
```

**Expected Output:** `Total vectors indexed: 1400+` (approximate)

**If import fails:** Complete Phase 2a Section 9 (Pinecone Client Setup) first - the `PineconeClient` class must exist.

**If vectors are 0:** Complete Phase 2a Section 9 (RAG Indexing Pipeline) first.

### 1.3 Verify SQL Tool Works

**Command:**
```bash
docker-compose exec backend python -c "
from src.agent.tools.sql import sql_query
result = sql_query('How many companies are in the database?')
print(result)
"
```

**Expected Output:** Response mentioning 7 companies.

### 1.4 Verify Basic RAG Tool Works

**Command:**
```bash
docker-compose exec backend python -c "
from src.agent.tools.rag import retrieve_documents
result = retrieve_documents('What are supply chain risks?', top_k=2)
print(result)
"
```

**Expected Output:** 2 relevant passages with citations.

### 1.5 Verify Extracted Documents Exist

**Command:**
```bash
# Check extracted JSON files from Phase 2a
ls documents/extracted/*.json | wc -l
```

**Expected Output:** 7+ files (10-Ks and reference docs)

### 1.6 Prerequisites Checklist

- [ ] Neo4j running locally (`docker-compose ps neo4j` shows healthy)
- [ ] Neo4j connection works (cypher-shell returns test result)
- [ ] Pinecone has 1400+ vectors indexed
- [ ] SQL tool returns correct results
- [ ] Basic RAG tool returns relevant passages
- [ ] Extracted JSON files exist in documents/extracted/

### 1.7 Verify Pinecone Supports Hybrid Search

**⚠️ Important:** Pinecone hybrid search (dense + sparse) requires specific index configuration. Most Phase 2a indexes should already support this, but verify.

**Command:**
```bash
docker-compose exec backend python -c "
from pinecone import Pinecone
from src.config.settings import get_settings

settings = get_settings()
pc = Pinecone(api_key=settings.pinecone_api_key)

# Get index info
index_list = pc.list_indexes()
for idx in index_list:
    if idx.name == settings.pinecone_index_name:
        print(f'Index: {idx.name}')
        print(f'Metric: {idx.metric}')
        print(f'Dimension: {idx.dimension}')
        print(f'Status: {idx.status}')
        
        # dotproduct metric is required for hybrid search
        if idx.metric == 'dotproduct':
            print('\\n✓ Index supports hybrid search (dotproduct metric)')
        elif idx.metric == 'cosine':
            print('\\n⚠️ Index uses cosine metric - hybrid search will work but dotproduct is recommended')
        else:
            print(f'\\n⚠️ Metric {idx.metric} may not support hybrid search optimally')
"
```

**If hybrid search is not supported**, you'll need to create a new index with `metric='dotproduct'` and re-index documents. Follow Section 1.8 below.

### 1.8 Upgrade Pinecone Index and Embeddings Model

**⚠️ Required if:** Your index uses `cosine` metric (from Phase 0/2a) OR you want to upgrade to Titan v2 embeddings.

Since we're recreating the index anyway, we'll make two improvements at once:

1. **Metric:** `cosine` → `dotproduct` (optimal for hybrid search)
2. **Embeddings:** Titan v1 (1536 dim) → Titan v2 (1024 dim, better benchmarks)

**Why These Changes?**

| Change | Reason |
|--------|--------|
| `dotproduct` metric | Hybrid search combines dense + sparse vectors; dotproduct doesn't distort sparse scores like cosine does |
| Titan v2 embeddings | Better performance on benchmarks, variable dimensions, L2 normalization support |
| 1024 dimensions | Titan v2 default; smaller vectors = faster search, lower storage, comparable quality |

**What Changes Are Needed:**

| Component | Changes Required |
|-----------|------------------|
| `backend/src/config/settings.py` | ✅ Update default embedding model to v2 |
| `backend/src/utils/embeddings.py` | ✅ Update default constant to v2 |
| Pinecone Console | ✅ Delete old index, create new with dotproduct + 1024 dims |
| Secrets | ❌ None - keep same API key |
| Environment Variables | ❌ None - keep same index name |
| Data | ✅ Re-run indexing script to repopulate vectors |

---

**Step 1: Update Embedding Model in Code**

**File: `backend/src/config/settings.py`**

Find and change:
```python
bedrock_embedding_model_id: str = Field(
    default="amazon.titan-embed-text-v1",
```

To:
```python
bedrock_embedding_model_id: str = Field(
    default="amazon.titan-embed-text-v2:0",
```

**File: `backend/src/utils/embeddings.py`**

Find and change:
```python
DEFAULT_EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v1"
```

To:
```python
DEFAULT_EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"
```

**Verify the code change:**
```bash
docker-compose exec backend python -c "
from src.config.settings import get_settings
from src.utils.embeddings import BedrockEmbeddings

settings = get_settings()
embeddings = BedrockEmbeddings()

print(f'Settings model: {settings.bedrock_embedding_model_id}')
print(f'Embeddings model: {embeddings.model_id}')
print(f'Dimension: {embeddings.get_dimension()}')
"
```

**Expected Output:**
```
Settings model: amazon.titan-embed-text-v2:0
Embeddings model: amazon.titan-embed-text-v2:0
Dimension: 1024
```

---

**Step 2: Note Your Current Index Name**

```bash
docker-compose exec backend python -c "
from src.config.settings import get_settings
settings = get_settings()
print(f'Current index name: {settings.pinecone_index_name}')
"
```

---

**Step 3: Delete Old Index in Pinecone Console**

1. Go to https://app.pinecone.io
2. Navigate to your index (e.g., `dense-local-demo`)
3. Click **Delete Index**
4. Confirm deletion

---

**Step 4: Create New Index with Dotproduct + 1024 Dimensions**

1. In Pinecone console, click **Create Index**
2. Configure with these settings:
   - **Name:** Same as before (e.g., `dense-local-demo`) - keeps env vars unchanged
   - **Setup Mode:** Manual
   - **Vector Type:** Dense
   - **Dimensions:** `1024` ← **Changed from 1536 for Titan v2**
   - **Metric:** `dotproduct` ← **Changed from cosine for hybrid search**
   - **Cloud:** AWS
   - **Region:** `us-east-1`
3. Click **Create Index**
4. Wait for status to show "Ready"

---

**Step 5: Re-index Documents**

```bash
# Re-run indexing (uses existing extracted JSON, re-embeds with Titan v2)
python scripts/extract_and_index.py --index-only

# This will:
# - Skip PDF extraction (already done)
# - Re-embed all chunks using Titan v2 (1024 dimensions)
# - Upload vectors to the new index
```

---

**Step 6: Verify New Index**

```bash
docker-compose exec backend python -c "
from pinecone import Pinecone
from src.config.settings import get_settings

settings = get_settings()
api_key = settings.pinecone_api_key.get_secret_value() if hasattr(settings.pinecone_api_key, 'get_secret_value') else settings.pinecone_api_key
pc = Pinecone(api_key=api_key)

index_list = pc.list_indexes()
for idx in index_list:
    if idx.name == settings.pinecone_index_name:
        print(f'Index: {idx.name}')
        print(f'Metric: {idx.metric}')
        print(f'Dimension: {idx.dimension}')
        
        index = pc.Index(idx.name)
        stats = index.describe_index_stats()
        print(f'Vector count: {stats.total_vector_count}')
        
        if idx.metric == 'dotproduct' and idx.dimension == 1024:
            print('\\n✓ Index upgraded: dotproduct metric + Titan v2 (1024 dims)')
"
```

**Expected Output:**
```
Index: dense-local-demo
Metric: dotproduct
Dimension: 1024
Vector count: 352

✓ Index upgraded: dotproduct metric + Titan v2 (1024 dims)
```

---

**Step 7: Update Documentation References**

After completing the upgrade, update these files to reflect 1024 dimensions:
- `DEVELOPMENT_REFERENCE.md` - embedding dimensions reference
- `docs/RAG_README.md` - component summary table

**Estimated Time:** ~20-25 minutes (code changes + Pinecone + re-indexing)

---

## 2. Knowledge Graph Ontology

### What We're Doing
Defining the entity types and relationships for the financial domain Knowledge Graph. This ontology guides entity extraction and graph structure.

### Why This Matters
- **Structured Knowledge:** Ontology defines what entities and relationships we track
- **Query Capability:** Relationship types determine what graph queries are possible
- **Domain Relevance:** Financial-specific entities improve retrieval quality

### 2.1 Create Knowledge Graph Package

**Agent Prompt:**
```
Create `backend/src/knowledge_graph/__init__.py`

Contents:
1. Module docstring explaining the knowledge graph package
2. Import and export classes from submodules (to be created)
3. Define __all__ for public exports

Structure:
"""Knowledge Graph package for entity extraction and graph queries.

This package provides:
- Entity extraction using spaCy NER with financial domain patterns
- Neo4j graph store for entity and relationship storage
- Graph query functions for 1-hop and 2-hop traversals
"""

# Imports will be added as modules are created
# from src.knowledge_graph.ontology import EntityType, RelationType
# from src.knowledge_graph.extractor import EntityExtractor
# from src.knowledge_graph.store import Neo4jStore
# from src.knowledge_graph.queries import GraphQueries

__all__ = []  # Will be populated as modules are added

Reference:
- Existing package __init__.py patterns
- [backend.mdc] for Python patterns

Verify: docker-compose exec backend python -c "import src.knowledge_graph; print('OK')"
```

### 2.2 Create Ontology Module

**Agent Prompt:**
```
Create `backend/src/knowledge_graph/ontology.py`

Requirements:
1. Define EntityType enum for all entity categories
2. Define RelationType enum for all relationship types
3. Define mapping from spaCy labels to our entity types
4. Define financial domain patterns for custom entities

Structure:
- EntityType enum with values:
  - DOCUMENT: Source document in RAG system
  - ORGANIZATION: Companies, agencies, institutions
  - PERSON: Named individuals (executives, analysts)
  - LOCATION: Countries, cities, regions (GPE)
  - REGULATION: Laws, regulatory bodies (SEC, FINRA)
  - CONCEPT: Financial terms and concepts
  - PRODUCT: Financial products and services
  - DATE: Dates and time periods
  - MONEY: Monetary values
  - PERCENT: Percentages

- RelationType enum with values:
  - MENTIONS: Document mentions an entity
  - DEFINES: Document defines a concept
  - GOVERNED_BY: Entity governed by regulation
  - LOCATED_IN: Entity located in geography
  - RELATED_TO: Generic relationship
  - WORKS_FOR: Person works for organization
  - COMPETES_WITH: Organization competes with organization

- SPACY_TO_ENTITY_TYPE: dict mapping spaCy labels to EntityType
  {
    "ORG": EntityType.ORGANIZATION,
    "PERSON": EntityType.PERSON,
    "GPE": EntityType.LOCATION,
    "DATE": EntityType.DATE,
    "MONEY": EntityType.MONEY,
    "PERCENT": EntityType.PERCENT,
    "LAW": EntityType.REGULATION,
    "PRODUCT": EntityType.PRODUCT,
  }

- FINANCIAL_PATTERNS: list of spaCy EntityRuler patterns for custom entities
  - REGULATION patterns: SEC, FINRA, FDIC, OCC, CFPB, GAAP, IFRS
  - CONCEPT patterns: APR, APY, EPS, P/E, ROE, ROA, EBITDA
  - PRODUCT patterns: "credit card", "checking account", "savings account"

Reference:
- PHASE_2_REQUIREMENTS.md Knowledge Graph section
- spaCy EntityRuler documentation
- [backend.mdc] for Python patterns

Verify: docker-compose exec backend python -c "from src.knowledge_graph.ontology import EntityType, RelationType; print('OK')"
```

### 2.3 Update Package Init with Ontology

**Agent Prompt:**
```
Update `backend/src/knowledge_graph/__init__.py`

Add imports and exports for ontology module:
1. from src.knowledge_graph.ontology import EntityType, RelationType, SPACY_TO_ENTITY_TYPE, FINANCIAL_PATTERNS
2. Add to __all__: ["EntityType", "RelationType", "SPACY_TO_ENTITY_TYPE", "FINANCIAL_PATTERNS"]

Reference:
- Ontology module just created
- Standard Python package patterns

Verify: docker-compose exec backend python -c "from src.knowledge_graph import EntityType, RelationType; print('OK')"
```

### 2.4 Knowledge Graph Ontology Checklist

- [ ] knowledge_graph package created
- [ ] ontology.py defines EntityType enum
- [ ] ontology.py defines RelationType enum
- [ ] SPACY_TO_ENTITY_TYPE mapping defined
- [ ] FINANCIAL_PATTERNS list defined
- [ ] Package __init__.py exports ontology classes

---

## 3. Entity Extraction

### What We're Doing
Implementing entity extraction using spaCy NER with custom financial domain patterns. This extracts entities from document text for Knowledge Graph storage.

### Why This Matters
- **Cost Efficiency:** spaCy is ~95% cheaper than LLM extraction
- **Speed:** Local NER is much faster than API calls
- **Customization:** Financial patterns catch domain-specific entities

### 3.1 Create Entity Extractor Module

**Agent Prompt:**
```
Create `backend/src/knowledge_graph/extractor.py`

Requirements:
1. Load spaCy model with custom EntityRuler patterns
2. Extract entities from text with deduplication
3. Map spaCy labels to our EntityType enum
4. Return structured entity objects

Structure:
- Entity dataclass:
  - text: str (the entity text)
  - entity_type: EntityType
  - start_char: int (position in text)
  - end_char: int
  - confidence: float (spaCy score if available)
  - source_document_id: str | None
  - source_page: int | None

- EntityExtractor class:
  - __init__(self, model_name: str = "en_core_web_sm")
  - _load_model(self) -> spacy.Language
  - _add_financial_patterns(self, nlp: spacy.Language) -> None
  - extract_entities(self, text: str, document_id: str = None, page: int = None) -> list[Entity]
  - extract_from_document(self, extraction_json: dict) -> list[Entity]

Key Features:
- Load spaCy model once, reuse for all extractions
- Add FINANCIAL_PATTERNS from ontology as EntityRuler
- Filter entities by SPACY_TO_ENTITY_TYPE (ignore unmapped labels)
- Deduplicate entities with same text (keep first occurrence)
- Normalize entity text (strip whitespace, consistent casing for acronyms)

Deduplication Logic:
- Group entities by normalized text
- Keep entity with highest confidence
- Merge source locations if same entity appears multiple times

Entity Normalization:
- Strip leading/trailing whitespace
- For acronyms (all caps, 2-5 chars): keep uppercase
- For names: title case
- For everything else: preserve original

Reference:
- ontology.py EntityType and FINANCIAL_PATTERNS
- spaCy documentation: https://spacy.io/
- [backend.mdc] for Python patterns

Verify: docker-compose exec backend python -c "from src.knowledge_graph.extractor import EntityExtractor, Entity; print('OK')"
```

### 3.2 Test Entity Extraction

**Command:**
```bash
docker-compose exec backend python -c "
from src.knowledge_graph.extractor import EntityExtractor

extractor = EntityExtractor()

# Test text
text = '''
Apple Inc. reported revenue of \$394 billion in fiscal 2024.
Tim Cook, the CEO, discussed supply chain risks in China.
The SEC requires disclosure of material risks.
The company's iPhone segment grew 5% year-over-year.
'''

entities = extractor.extract_entities(text)
print(f'Extracted {len(entities)} entities:')
for e in entities:
    print(f'  {e.entity_type.name}: \"{e.text}\"')
"
```

**Expected Output:**
```
Extracted 8+ entities:
  ORGANIZATION: "Apple Inc."
  MONEY: "$394 billion"
  DATE: "fiscal 2024"
  PERSON: "Tim Cook"
  LOCATION: "China"
  REGULATION: "SEC"
  PRODUCT: "iPhone"
  PERCENT: "5%"
```

### 3.3 Update Package Init with Extractor

**Agent Prompt:**
```
Update `backend/src/knowledge_graph/__init__.py`

Add imports and exports for extractor module:
1. from src.knowledge_graph.extractor import EntityExtractor, Entity
2. Add to __all__: "EntityExtractor", "Entity"

Reference:
- Extractor module just created

Verify: docker-compose exec backend python -c "from src.knowledge_graph import EntityExtractor; print('OK')"
```

### 3.4 Entity Extraction Checklist

- [ ] extractor.py created with EntityExtractor class
- [ ] Entity dataclass defined with all fields
- [ ] spaCy model loads successfully
- [ ] Financial patterns added via EntityRuler
- [ ] Test extraction returns expected entities
- [ ] Package __init__.py exports EntityExtractor

---

## 4. Neo4j Graph Store

### What We're Doing
Implementing the Neo4j connection and CRUD operations for storing entities and relationships.

### Why This Matters
- **Persistence:** Entities stored in graph database for queries
- **Relationships:** Graph structure enables traversal queries
- **Integration:** Store connects extraction to query pipeline

### 4.1 Create Graph Store Module

**Agent Prompt:**
```
Create `backend/src/knowledge_graph/store.py`

Requirements:
1. Neo4j connection management with connection pooling
2. CRUD operations for entities and relationships
3. Batch operations for efficient bulk loading
4. Query helpers for common patterns

Required Imports:
from neo4j import GraphDatabase
from src.knowledge_graph.ontology import EntityType, RelationType
from src.knowledge_graph.extractor import Entity

Structure:
- Neo4jStore class:
  - __init__(self, uri: str, user: str, password: str)
  - _get_driver(self) -> neo4j.Driver
  - close(self) -> None
  - create_entity(self, entity: Entity) -> str (returns node ID)
  - create_relationship(self, from_id: str, to_id: str, rel_type: RelationType, properties: dict = None) -> None
  - batch_create_entities(self, entities: list[Entity]) -> list[str]
  - batch_create_relationships(self, relationships: list[tuple]) -> None
  - find_entity_by_text(self, text: str, entity_type: EntityType = None) -> dict | None
  - find_entities_by_document(self, document_id: str) -> list[dict]
  - delete_document_entities(self, document_id: str) -> int (returns count deleted)
  - get_stats(self) -> dict

Cypher Queries:
- Create entity:
  MERGE (e:{entity_type} {text: $text})
  ON CREATE SET e.created_at = datetime(), e.source_document = $doc_id
  ON MATCH SET e.mention_count = coalesce(e.mention_count, 0) + 1
  RETURN elementId(e) as id

- Create relationship:
  MATCH (a), (b)
  WHERE elementId(a) = $from_id AND elementId(b) = $to_id
  MERGE (a)-[r:{rel_type}]->(b)
  SET r.created_at = datetime()

- Create MENTIONS relationship (document to entity):
  MATCH (d:Document {document_id: $doc_id})
  MATCH (e {text: $entity_text})
  MERGE (d)-[r:MENTIONS {page: $page}]->(e)

Key Features:
- Use MERGE to avoid duplicate entities
- Track mention_count for entity importance
- Support batch operations with UNWIND
- Connection pooling for performance
- Graceful error handling with logging

Entity Node Labels:
- Use EntityType.name as Neo4j label: Organization, Person, Location, etc.
- Add secondary label "Entity" for generic queries

Reference:
- neo4j Python driver documentation: https://neo4j.com/docs/python-manual/current/
- ontology.py EntityType and RelationType
- [backend.mdc] for Python patterns

Verify: docker-compose exec backend python -c "from src.knowledge_graph.store import Neo4jStore; print('OK')"
```

### 4.2 Create Document Node for Each Extracted Document

**Agent Prompt:**
```
Update `backend/src/knowledge_graph/store.py` to add document node creation

Add method to Neo4jStore:
- create_document_node(self, document_id: str, metadata: dict) -> str

Cypher:
MERGE (d:Document {document_id: $document_id})
ON CREATE SET 
  d.created_at = datetime(),
  d.document_type = $document_type,
  d.company = $company,
  d.ticker = $ticker,
  d.title = $title
RETURN elementId(d) as id

This creates a Document node that will be the hub for MENTIONS relationships.

Reference:
- VLM extraction JSON metadata structure from Phase 2a
- Neo4j MERGE pattern
- [backend.mdc] for Python patterns

Verify: docker-compose exec backend python -c "from src.knowledge_graph.store import Neo4jStore; print('OK')"
```

### 4.3 Test Neo4j Connection

**Command:**
```bash
docker-compose exec backend python -c "
from src.knowledge_graph.store import Neo4jStore
from src.config.settings import get_settings

settings = get_settings()
store = Neo4jStore(
    uri=settings.neo4j_uri,
    user=settings.neo4j_user,
    password=settings.neo4j_password
)

# Test connection
stats = store.get_stats()
print(f'Neo4j connected. Node count: {stats.get(\"node_count\", 0)}')
store.close()
"
```

**Expected Output:** `Neo4j connected. Node count: 0` (empty initially)

### 4.4 Update Package Init with Store

**Agent Prompt:**
```
Update `backend/src/knowledge_graph/__init__.py`

Add imports and exports for store module:
1. from src.knowledge_graph.store import Neo4jStore
2. Add to __all__: "Neo4jStore"

Reference:
- Store module just created

Verify: docker-compose exec backend python -c "from src.knowledge_graph import Neo4jStore; print('OK')"
```

### 4.5 Create Neo4j Indexes for Query Performance

**⚠️ Important:** Create indexes BEFORE bulk entity indexing for much better performance.

**Command:**
```bash
# Create indexes for frequently queried fields
docker-compose exec neo4j cypher-shell -u neo4j -p localdevpassword "
CREATE INDEX entity_text IF NOT EXISTS FOR (n:Entity) ON (n.text);
CREATE INDEX document_id IF NOT EXISTS FOR (n:Document) ON (n.document_id);
CREATE INDEX entity_mention_count IF NOT EXISTS FOR (n:Entity) ON (n.mention_count);
"

# Verify indexes created
docker-compose exec neo4j cypher-shell -u neo4j -p localdevpassword "SHOW INDEXES"
```

**Expected Output:**
```
+------------------+-------+----------+
| name             | state | type     |
+------------------+-------+----------+
| entity_text      | ONLINE| BTREE    |
| document_id      | ONLINE| BTREE    |
| entity_mention_count | ONLINE| BTREE |
+------------------+-------+----------+
```

### 4.6 Neo4j Graph Store Checklist

- [ ] store.py created with Neo4jStore class
- [ ] Connection to local Neo4j works
- [ ] create_entity method implemented
- [ ] create_relationship method implemented
- [ ] batch_create_entities for bulk loading
- [ ] create_document_node for document hubs
- [ ] Package __init__.py exports Neo4jStore
- [ ] **Neo4j indexes created for entity_text, document_id**

---

## 5. Entity Indexing Pipeline

### What We're Doing
Building a pipeline to extract entities from all documents and store them in Neo4j with MENTIONS relationships.

### Why This Matters
- **Knowledge Base:** Populates the Knowledge Graph with real entities
- **Relationships:** Creates document→entity relationships for queries
- **Foundation:** Enables entity-based retrieval in hybrid search

### 5.1 Verify Phase 2A Prerequisites for Entity Indexing

**⚠️ Important:** Entity indexing depends on extracted JSON from Phase 2A. Verify before proceeding.

**Command:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Verify extracted JSON files exist
docker-compose exec backend python -c "
from pathlib import Path
import json

extracted_dir = Path('documents/extracted')
json_files = list(extracted_dir.glob('*.json'))

if not json_files:
    print('✗ No extracted JSON files found!')
    print('  Complete Phase 2a Section 5 (VLM Extraction) first.')
    exit(1)

print(f'Found {len(json_files)} extracted documents:')
total_pages = 0
for f in sorted(json_files):
    with open(f) as fp:
        data = json.load(fp)
        pages = len(data.get('pages', []))
        total_pages += pages
        print(f'  {f.name}: {pages} pages')

print(f'\\nTotal pages available: {total_pages}')
print('✓ Phase 2a extraction output verified. Ready for entity indexing.')
"
```

**Expected Output:**
```
Found 11 extracted documents:
  AAPL_10K_2024.json: 85 pages
  MSFT_10K_2024.json: 100 pages
  ...

Total pages available: 782
✓ Phase 2a extraction output verified. Ready for entity indexing.
```

### 5.2 Create Entity Indexing Script

**Agent Prompt:**
```
Create `scripts/index_entities.py`

Requirements:
1. Load all extracted JSON files from Phase 2a
2. Extract entities from each document using EntityExtractor
3. Store entities and relationships in Neo4j
4. Provide CLI with progress tracking

Structure:
- main() function with argparse:
  - --extracted-dir: Path to extracted JSON (default: documents/extracted)
  - --neo4j-uri: Override NEO4J_URI
  - --force: Re-index even if document exists
  - --dry-run: Extract entities without storing

Pipeline Per Document:
1. Load JSON extraction from Phase 2a
2. Create Document node in Neo4j
3. For each page in extraction:
   a. Extract entities using EntityExtractor
   b. Create entity nodes (MERGE to deduplicate)
   c. Create MENTIONS relationships (Document→Entity)
4. Log progress and stats

Entity Deduplication:
- Use entity text + type as unique key
- MERGE in Neo4j handles duplicates automatically
- Track mention_count for importance ranking

Progress Output:
"Processing AAPL_10K_2024.json..."
"  Created Document node"
"  Extracted 847 entity mentions"
"  Unique entities: 234"
"  Created 234 entity nodes, 847 MENTIONS relationships"
"Processing MSFT_10K_2024.json..."
...
"Summary:
  Documents processed: 11
  Total entity mentions: 4,523
  Unique entities: 1,247
  Relationships created: 4,523
  Neo4j stats: 1,258 nodes, 4,523 relationships"

Reference:
- EntityExtractor from Section 3
- Neo4jStore from Section 4
- VLM extraction JSON structure from Phase 2a
- [backend.mdc] for Python patterns

Verify: docker-compose exec backend python scripts/index_entities.py --help
```

### 5.3 Run Entity Indexing

**Command (dry run first):**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Dry run validates spaCy extraction without writing to Neo4j
docker-compose exec backend python scripts/index_entities.py --dry-run
```

**Expected Dry Run Output:**
```
Dry run mode - extracting entities without storing
Processing AAPL_10K_2024.json...
  Extracted 847 entity mentions, 234 unique
Processing MSFT_10K_2024.json...
  ...
Dry run complete: 4,523 total mentions, 1,247 unique entities from 11 documents
```

**If spaCy model error:** `docker-compose exec backend python -m spacy download en_core_web_sm`

**Command (full indexing):**
```bash
# Full indexing to Neo4j
docker-compose exec backend python scripts/index_entities.py
```

### 5.4 Verify Entity Indexing Results

**⚠️ Important:** Verify entities stored correctly before proceeding to graph queries.

**Command:**
```bash
# Check entity counts by type
docker-compose exec neo4j cypher-shell -u neo4j -p localdevpassword \
  "MATCH (n) RETURN labels(n)[0] as type, count(*) as count ORDER BY count DESC"
```

**Expected Output:**
```
+----------------+-------+
| type           | count |
+----------------+-------+
| "Organization" | 450   |
| "Person"       | 280   |
| "Location"     | 180   |
| "Money"        | 320   |
| "Document"     | 11    |
...
```

**Command (verify minimum expected counts):**
```bash
docker-compose exec backend python -c "
from src.knowledge_graph.store import Neo4jStore
from src.config.settings import get_settings

settings = get_settings()
store = Neo4jStore(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
stats = store.get_stats()

node_count = stats.get('node_count', 0)
rel_count = stats.get('relationship_count', 0)

print(f'Neo4j Statistics:')
print(f'  Total nodes: {node_count}')
print(f'  Total relationships: {rel_count}')

# Validation thresholds
min_nodes = 1000
min_rels = 3000

if node_count < min_nodes:
    print(f'\\n⚠️ Warning: Expected {min_nodes}+ nodes, found {node_count}')
    print('  Entity extraction may have failed for some documents.')
elif rel_count < min_rels:
    print(f'\\n⚠️ Warning: Expected {min_rels}+ relationships, found {rel_count}')
    print('  MENTIONS relationships may not have been created properly.')
else:
    print(f'\\n✓ Entity indexing verified: {node_count} nodes, {rel_count} relationships')

store.close()
"
```

**Expected Output:**
```
Neo4j Statistics:
  Total nodes: 1258
  Total relationships: 4523

✓ Entity indexing verified: 1258 nodes, 4523 relationships
```

### 5.5 Verify Graph Structure

**Command:**
```bash
# Check relationships by type
docker-compose exec neo4j cypher-shell -u neo4j -p localdevpassword \
  "MATCH ()-[r]->() RETURN type(r) as relationship, count(*) as count"

# Check Apple-related entities (validates document-entity links)
docker-compose exec neo4j cypher-shell -u neo4j -p localdevpassword \
  "MATCH (d:Document {ticker: 'AAPL'})-[:MENTIONS]->(e) 
   RETURN labels(e)[0] as type, count(*) as mentions 
   ORDER BY mentions DESC LIMIT 5"
```

**Expected Output:**
```
+---------------+-------+
| relationship  | count |
+---------------+-------+
| "MENTIONS"    | 4523  |
+---------------+-------+

+---------------+---------+
| type          | mentions|
+---------------+---------+
| "Organization"| 85      |
| "Money"       | 67      |
| "Location"    | 42      |
...
```

### 5.6 Entity Indexing Pipeline Checklist

- [ ] index_entities.py script created
- [ ] Dry run extracts entities correctly
- [ ] Full indexing completes without errors
- [ ] Document nodes created for all documents
- [ ] Entity nodes created with correct labels
- [ ] MENTIONS relationships connect documents to entities
- [ ] Neo4j shows 1000+ nodes

---

## 6. Graph Query Implementation

### What We're Doing
Implementing graph traversal queries for 1-hop and 2-hop entity lookups that will enhance RAG retrieval.

### Why This Matters
- **Entity-Based Retrieval:** Find documents mentioning specific entities
- **Related Entities:** Discover connections between entities
- **Query Enhancement:** Graph context improves retrieval relevance

### 6.1 Create Graph Queries Module

**Agent Prompt:**
```
Create `backend/src/knowledge_graph/queries.py`

Requirements:
1. Query functions for common graph traversals
2. Return document IDs for RAG integration
3. Support filtering by entity type and relationship type

Structure:
- GraphQueries class:
  - __init__(self, store: Neo4jStore)
  - find_documents_mentioning(self, entity_text: str, entity_type: EntityType = None) -> list[str]
  - find_related_entities(self, entity_text: str, hops: int = 1) -> list[dict]
  - find_entities_in_document(self, document_id: str) -> list[dict]
  - find_co_occurring_entities(self, entity_text: str) -> list[dict]
  - find_path_between_entities(self, entity1: str, entity2: str, max_hops: int = 3) -> list[dict]
  - entity_search(self, query: str) -> list[str] (fuzzy search for entity names)

Key Queries:

1. find_documents_mentioning (1-hop):
   "Find all documents that mention Apple"
   MATCH (d:Document)-[:MENTIONS]->(e {text: $entity_text})
   RETURN d.document_id as document_id, d.ticker as ticker

2. find_related_entities (2-hop):
   "Find entities related to Apple through shared documents"
   MATCH (e1 {text: $entity_text})<-[:MENTIONS]-(d:Document)-[:MENTIONS]->(e2)
   WHERE e1 <> e2
   RETURN e2.text as entity, labels(e2)[0] as type, count(d) as shared_docs
   ORDER BY shared_docs DESC

3. find_co_occurring_entities:
   "Find entities that frequently appear with China"
   MATCH (e1 {text: $entity_text})<-[:MENTIONS]-(d:Document)-[:MENTIONS]->(e2)
   WHERE e1 <> e2
   WITH e2, count(d) as co_occurrences
   WHERE co_occurrences > 2
   RETURN e2.text as entity, labels(e2)[0] as type, co_occurrences
   ORDER BY co_occurrences DESC

4. entity_search (fuzzy):
   "Find entities matching 'apple'" (case-insensitive, partial match)
   MATCH (e)
   WHERE toLower(e.text) CONTAINS toLower($query)
   RETURN e.text as entity, labels(e)[0] as type
   LIMIT 10

Return Format:
- Document queries return list of document_id strings (for RAG integration)
- Entity queries return list of dicts with entity info

Reference:
- Neo4jStore from Section 4
- Neo4j Cypher documentation
- [backend.mdc] for Python patterns

Verify: docker-compose exec backend python -c "from src.knowledge_graph.queries import GraphQueries; print('OK')"
```

### 6.2 Test Graph Queries

**Command:**
```bash
docker-compose exec backend python -c "
from src.knowledge_graph.store import Neo4jStore
from src.knowledge_graph.queries import GraphQueries
from src.config.settings import get_settings

settings = get_settings()
store = Neo4jStore(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
queries = GraphQueries(store)

# Test 1: Find documents mentioning China
print('Documents mentioning China:')
docs = queries.find_documents_mentioning('China')
for doc in docs[:5]:
    print(f'  {doc}')

# Test 2: Find entities related to Apple
print('\\nEntities related to Apple:')
related = queries.find_related_entities('Apple', hops=1)
for e in related[:5]:
    print(f'  {e[\"type\"]}: {e[\"entity\"]} (shared docs: {e[\"shared_docs\"]})')

store.close()
"
```

**Expected Output:**
```
Documents mentioning China:
  AAPL_10K_2024
  TSLA_10K_2024
  NVDA_10K_2024
  ...

Entities related to Apple:
  Organization: iPhone (shared docs: 45)
  Location: China (shared docs: 32)
  Person: Tim Cook (shared docs: 28)
  ...
```

### 6.3 Update Package Init with Queries

**Agent Prompt:**
```
Update `backend/src/knowledge_graph/__init__.py`

Add imports and exports for queries module:
1. from src.knowledge_graph.queries import GraphQueries
2. Add to __all__: "GraphQueries"

Reference:
- Queries module just created

Verify: docker-compose exec backend python -c "from src.knowledge_graph import GraphQueries; print('OK')"
```

### 6.4 Graph Query Implementation Checklist

- [ ] queries.py created with GraphQueries class
- [ ] find_documents_mentioning returns document IDs
- [ ] find_related_entities finds 2-hop connections
- [ ] find_co_occurring_entities works
- [ ] entity_search provides fuzzy matching
- [ ] Test queries return expected results
- [ ] Package __init__.py exports GraphQueries

---

## 7. BM25 Sparse Vectors

### What We're Doing
Adding BM25 sparse vectors to Pinecone to enable keyword-based matching alongside semantic search.

### Why This Matters
- **Keyword Matching:** BM25 catches exact term matches that dense search might miss
- **Hybrid Search:** Combining dense + sparse improves recall by 20-30%
- **Technical Terms:** Financial acronyms (EPS, P/E) match better with BM25

### 7.1 Create BM25 Encoder Module

**Agent Prompt:**
```
Create `backend/src/utils/bm25_encoder.py`

Requirements:
1. BM25 sparse vector generation for Pinecone hybrid search
2. Tokenization and term frequency calculation
3. Compatible with Pinecone sparse vector format

Structure:
- BM25Encoder class:
  - __init__(self)
  - _tokenize(self, text: str) -> list[str]
  - _compute_tf(self, tokens: list[str]) -> dict[str, float]
  - encode(self, text: str) -> dict (Pinecone sparse format)
  - fit(self, documents: list[str]) -> None (optional: compute IDF)

Pinecone Sparse Vector Format:
{
  "indices": [token_hash_1, token_hash_2, ...],
  "values": [weight_1, weight_2, ...]
}

Key Features:
- Simple tokenization: lowercase, split on whitespace/punctuation
- Remove stopwords (basic list: the, a, an, is, are, etc.)
- Use hash of token as index (consistent across documents)
- TF weighting: log(1 + count)
- Optional IDF if corpus available

Token Hashing:
- Use Python hash() mod 2^31 for consistent indices
- Or use xxhash for faster hashing

Simplified BM25 (without full corpus IDF):
- Just use TF weights: log(1 + term_frequency)
- This is "TF-only" sparse encoding, works well for Pinecone hybrid

Token Hashing (ensure positive indices):
def hash_token(token: str) -> int:
    return abs(hash(token)) % (2**31)

Reference:
- Pinecone hybrid search documentation: https://docs.pinecone.io/docs/hybrid-search
- BM25 algorithm reference
- [backend.mdc] for Python patterns

Verify: docker-compose exec backend python -c "from src.utils.bm25_encoder import BM25Encoder; print('OK')"
```

### 7.2 Update Utils Package Init

**Agent Prompt:**
```
Update `backend/src/utils/__init__.py`

Add imports and exports for BM25 encoder:
1. from src.utils.bm25_encoder import BM25Encoder
2. Add to __all__: "BM25Encoder"

Reference:
- BM25Encoder module just created

Verify: docker-compose exec backend python -c "from src.utils import BM25Encoder; print('OK')"
```

### 7.3 Update Indexing to Include Sparse Vectors

**Agent Prompt:**
```
Update `scripts/extract_and_index.py` to add sparse vectors during indexing

Requirements:
1. Import BM25Encoder from src.utils.bm25_encoder
2. Generate sparse vector for each chunk alongside dense vector
3. Update Pinecone upsert to include sparse_values
4. Add CLI flag for upgrading existing index

Changes to index_document() function:
- After generating dense embedding, also generate sparse vector
- Include both in Pinecone upsert

Updated Vector Format for Upsert:
{
  "id": "AAPL_10K_2024_chunk_42",
  "values": [0.1, 0.2, ...],  # Dense vector (1536 floats)
  "sparse_values": {
    "indices": [12345, 67890, ...],
    "values": [0.5, 0.3, ...]
  },
  "metadata": {...}
}

CLI Updates:
- --add-sparse: Add sparse vectors to existing index (for upgrading Phase 2a index)
- When --add-sparse is used, fetch existing vectors by ID and update with sparse_values

Reference:
- BM25Encoder from Section 7.1
- Existing extract_and_index.py structure from Phase 2a
- Pinecone hybrid search documentation
- [backend.mdc] for Python patterns

Verify: docker-compose exec backend python scripts/extract_and_index.py --help (should show --add-sparse)
```

### 7.4 Verify Pinecone Has Dense Vectors (Prerequisite)

**⚠️ Important:** BM25 sparse vectors are ADDED to existing dense vectors from Phase 2a. Verify dense vectors exist first.

**Command:**
```bash
docker-compose exec backend python -c "
from src.utils.pinecone_client import PineconeClient
from src.config.settings import get_settings

settings = get_settings()
client = PineconeClient(settings.pinecone_api_key, settings.pinecone_index_name)
stats = client.get_stats()

vector_count = stats.get('total_vector_count', 0)
print(f'Current vectors in Pinecone: {vector_count}')

if vector_count < 1000:
    print('\\n✗ Error: Expected 1000+ vectors from Phase 2a')
    print('  Complete Phase 2a Section 9 (RAG Indexing) before adding sparse vectors.')
    exit(1)
else:
    print(f'\\n✓ Phase 2a vectors verified ({vector_count}). Ready to add sparse vectors.')
"
```

**Expected Output:**
```
Current vectors in Pinecone: 1423
✓ Phase 2a vectors verified (1423). Ready to add sparse vectors.
```

### 7.5 Add Sparse Vectors to Existing Index

**Command:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Add sparse vectors to existing Pinecone index (run inside Docker)
docker-compose exec backend python scripts/extract_and_index.py --add-sparse
```

**Expected Output:**
```
Adding sparse vectors to existing index...
Processing AAPL_10K_2024: 127 vectors updated with sparse
Processing MSFT_10K_2024: 142 vectors updated with sparse
...
Summary:
  Vectors updated: 1,423
  Sparse vectors added: 1,423
  Index ready for hybrid search
```

### 7.6 Verify Sparse Vectors Added

**⚠️ Important:** Verify sparse vectors work before proceeding to hybrid search.

**Command:**
```bash
docker-compose exec backend python -c "
from src.utils.pinecone_client import PineconeClient
from src.utils.bm25_encoder import BM25Encoder
from src.utils.embeddings import BedrockEmbeddings
from src.config.settings import get_settings

settings = get_settings()
client = PineconeClient(settings.pinecone_api_key, settings.pinecone_index_name)
bm25 = BM25Encoder()
embeddings = BedrockEmbeddings()

# Test hybrid query
test_query = 'supply chain risks China'
print(f'Test query: \"{test_query}\"')

# Generate both dense and sparse vectors
dense_vector = embeddings.embed_text(test_query)
sparse_vector = bm25.encode(test_query)

print(f'Dense vector dimension: {len(dense_vector)}')
print(f'Sparse vector indices: {len(sparse_vector[\"indices\"])}')

# Query with hybrid (dense + sparse)
results = client.query(
    vector=dense_vector,
    sparse_vector=sparse_vector,
    top_k=3
)

if results:
    print(f'\\n✓ Hybrid search works! Top {len(results)} results:')
    for i, r in enumerate(results):
        ticker = r.get('metadata', {}).get('ticker', 'N/A')
        section = r.get('metadata', {}).get('section', 'N/A')[:50]
        print(f'  {i+1}. [{ticker}] {section}...')
else:
    print('\\n⚠️ Warning: No results returned. Check Pinecone configuration.')
"
```

**Expected Output:**
```
Test query: "supply chain risks China"
Dense vector dimension: 1536
Sparse vector indices: 4

✓ Hybrid search works! Top 3 results:
  1. [AAPL] Item 1A: Risk Factors...
  2. [NVDA] Item 1A: Risk Factors...
  3. [TSLA] Item 1A: Risk Factors...
```

### 7.7 BM25 Sparse Vectors Checklist

- [ ] Phase 2a vectors verified (1400+ in Pinecone)
- [ ] bm25_encoder.py created with BM25Encoder class
- [ ] Tokenization handles financial text correctly
- [ ] Stopwords list defined and applied
- [ ] Token hashing produces positive indices
- [ ] encode() returns Pinecone sparse format
- [ ] Utils __init__.py exports BM25Encoder
- [ ] extract_and_index.py updated with --add-sparse flag
- [ ] Sparse vectors added to all existing vectors
- [ ] Hybrid search test returns results

---

## 8. Query Expansion

### What We're Doing
Implementing query expansion using Nova Lite to generate alternative phrasings that improve recall.

### Why This Matters
- **Vocabulary Gap:** Users may phrase queries differently than document text
- **Recall Improvement:** 3 query variants find more relevant documents (+20-30%)
- **Cost Effective:** Nova Lite is cheaper than main model for this task

### 8.1 Create Query Expansion Module

**Agent Prompt:**
```
Create `backend/src/ingestion/query_expansion.py`

Requirements:
1. Generate 3 alternative phrasings of user query using Nova Lite
2. Return original + variants for parallel search
3. Cache results for repeated queries (optional)

Structure:
- QueryExpander class:
  - __init__(self, model_id: str = "amazon.nova-lite-v1:0")
    > **Note:** Use Nova Lite model ID from DEVELOPMENT_REFERENCE.md: `amazon.nova-lite-v1:0`
  - expand(self, query: str, num_variants: int = 3) -> list[str]
  - _call_nova_lite(self, prompt: str) -> str

Expansion Prompt:
"Generate {num_variants} alternative phrasings of this search query.
Each variant should capture the same intent but use different words.
Return only the variants, one per line, no numbering.

Original query: {query}

Alternative phrasings:"

Example:
Input: "What are Apple's supply chain risks?"
Output:
- "What are Apple's supply chain risks?"  (original)
- "Apple Inc supply chain vulnerabilities"
- "AAPL supplier and manufacturing risks"
- "Apple supply chain risk factors 10-K"

Key Features:
- Always include original query in output
- Parse Nova Lite response to extract variants
- Handle edge cases: short queries, junk output
- Limit query length to prevent abuse
- **Deduplicate variants** (Nova Lite sometimes returns similar/identical variants)
- **Timeout handling** (30s default, fail gracefully to original query only)

**Reliability Requirements (Important):**

```python
from functools import lru_cache
import asyncio

class QueryExpander:
    def __init__(self, model_id: str = "amazon.nova-lite-v1:0", timeout: float = 30.0):
        self.model_id = model_id
        self.timeout = timeout
    
    @lru_cache(maxsize=100)  # Cache for repeated queries
    def expand(self, query: str, num_variants: int = 3) -> tuple[str, ...]:
        """Expand query with caching and timeout handling."""
        try:
            variants = self._expand_with_timeout(query, num_variants)
            # Deduplicate
            seen = {query.lower().strip()}
            unique = [query]
            for v in variants:
                if v.lower().strip() not in seen:
                    seen.add(v.lower().strip())
                    unique.append(v)
            return tuple(unique[:num_variants + 1])
        except asyncio.TimeoutError:
            logger.warning("query_expansion_timeout", query=query[:50])
            return (query,)  # Fall back to original only
        except Exception as e:
            logger.error("query_expansion_failed", error=str(e))
            return (query,)  # Graceful degradation
```

Cost Note:
- Nova Lite: ~$0.0003/1K input tokens, $0.0012/1K output tokens
- ~$0.002-0.005 per expansion call
- Consider caching frequent queries

Reference:
- Bedrock Nova Lite documentation
- [backend.mdc] for Python patterns
- [agent.mdc] for Bedrock integration

Verify: docker-compose exec backend python -c "from src.ingestion.query_expansion import QueryExpander; print('OK')"
```

### 8.2 Test Query Expansion

**Command:**
```bash
docker-compose exec backend python -c "
from src.ingestion.query_expansion import QueryExpander

expander = QueryExpander()

query = 'What are the main risks for Tesla?'
variants = expander.expand(query)

print(f'Original: {query}')
print(f'\\nExpanded to {len(variants)} variants:')
for i, v in enumerate(variants):
    print(f'  {i+1}. {v}')
"
```

**Expected Output:**
```
Original: What are the main risks for Tesla?

Expanded to 4 variants:
  1. What are the main risks for Tesla?
  2. Tesla Inc risk factors and challenges
  3. TSLA business risks disclosed in 10-K
  4. Tesla company risks and uncertainties
```

### 8.3 Update Ingestion Package Init

**Agent Prompt:**
```
Update `backend/src/ingestion/__init__.py`

Add imports and exports for query expansion:
1. from src.ingestion.query_expansion import QueryExpander
2. Add to __all__: "QueryExpander"

Reference:
- QueryExpander module just created

Verify: docker-compose exec backend python -c "from src.ingestion import QueryExpander; print('OK')"
```

### 8.4 Query Expansion Checklist

- [ ] query_expansion.py created with QueryExpander class
- [ ] Nova Lite model ID correct: amazon.nova-lite-v1:0
- [ ] expand() returns original + 3 variants
- [ ] Variants are meaningfully different
- [ ] Edge cases handled (short queries, errors)
- [ ] Ingestion __init__.py exports QueryExpander

---

## 9. RRF Fusion

### What We're Doing
Implementing Reciprocal Rank Fusion to merge results from dense search, BM25 search, and Knowledge Graph lookups.

### Why This Matters
- **Multi-Source Fusion:** Combines semantic, keyword, and entity results
- **Rank-Based:** Doesn't require score normalization across sources
- **Proven Effective:** Standard technique in hybrid retrieval systems

### 9.1 Create RRF Module

**Agent Prompt:**
```
Create `backend/src/utils/rrf.py`

Requirements:
1. Implement Reciprocal Rank Fusion algorithm
2. Support merging arbitrary number of result lists
3. Return fused ranking with combined scores

Structure:
- rrf_fusion(result_lists: list[list[dict]], k: int = 60) -> list[dict]

RRF Algorithm:
For each document d:
  score(d) = Σ 1/(k + rank(d, list_i)) for all lists containing d

Parameters:
- result_lists: List of result lists, each containing dicts with "id" and optional "score"
- k: Constant (default 60, standard in literature)

Input Format:
[
  # Dense search results
  [{"id": "doc1", "score": 0.95}, {"id": "doc2", "score": 0.87}, ...],
  # BM25 results
  [{"id": "doc2", "score": 12.5}, {"id": "doc3", "score": 11.2}, ...],
  # KG results
  [{"id": "doc1"}, {"id": "doc4"}, ...]
]

Output Format:
[
  {"id": "doc1", "rrf_score": 0.032, "sources": ["dense", "kg"]},
  {"id": "doc2", "rrf_score": 0.031, "sources": ["dense", "bm25"]},
  ...
]

Key Features:
- Identify documents by "id" field
- Track which sources contributed to each result
- Sort by RRF score descending
- Handle missing documents gracefully (only score lists that contain them)

Reference:
- RRF paper: "Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods"
- [backend.mdc] for Python patterns

Verify: docker-compose exec backend python -c "from src.utils.rrf import rrf_fusion; print('OK')"
```

### 9.2 Test RRF Fusion

**Command:**
```bash
docker-compose exec backend python -c "
from src.utils.rrf import rrf_fusion

# Simulate results from different sources
dense_results = [
    {'id': 'doc1', 'score': 0.95},
    {'id': 'doc2', 'score': 0.87},
    {'id': 'doc3', 'score': 0.82},
]

bm25_results = [
    {'id': 'doc2', 'score': 15.2},
    {'id': 'doc4', 'score': 12.1},
    {'id': 'doc1', 'score': 10.5},
]

kg_results = [
    {'id': 'doc1'},
    {'id': 'doc5'},
]

fused = rrf_fusion([dense_results, bm25_results, kg_results])

print('Fused results:')
for r in fused[:5]:
    print(f'  {r[\"id\"]}: score={r[\"rrf_score\"]:.4f}, sources={r[\"sources\"]}')
"
```

**Expected Output:**
```
Fused results:
  doc1: score=0.0492, sources=['dense', 'bm25', 'kg']
  doc2: score=0.0328, sources=['dense', 'bm25']
  doc3: score=0.0161, sources=['dense']
  doc4: score=0.0161, sources=['bm25']
  doc5: score=0.0161, sources=['kg']
```

### 9.3 Update Utils Package Init with RRF

**Agent Prompt:**
```
Update `backend/src/utils/__init__.py`

Add imports and exports for RRF fusion:
1. from src.utils.rrf import rrf_fusion
2. Add to __all__: "rrf_fusion"

Reference:
- rrf.py module just created

Verify: docker-compose exec backend python -c "from src.utils import rrf_fusion; print('OK')"
```

### 9.4 RRF Fusion Checklist

- [ ] rrf.py created with rrf_fusion function
- [ ] Handles multiple result lists
- [ ] Correctly computes RRF scores
- [ ] Tracks source contributions in output
- [ ] Returns sorted results by rrf_score
- [ ] Utils __init__.py exports rrf_fusion

---

## 10. Cross-Encoder Reranking

### What We're Doing
Implementing LLM-based relevance scoring to rerank the top results from RRF fusion.

### Why This Matters
- **Precision Improvement:** Reranking improves precision by 20-25%
- **Semantic Understanding:** LLM understands query-document relevance better
- **Quality Filter:** Removes false positives from initial retrieval

### 10.1 Create Reranker Module

**Agent Prompt:**
```
Create `backend/src/utils/reranker.py`

Requirements:
1. Score query-document relevance using Nova Lite
2. Rerank top-N results by relevance score
3. Return top-K highest scoring results

Structure:
- CrossEncoderReranker class:
  - __init__(self, model_id: str = "amazon.nova-lite-v1:0")
    > **Note:** Use Nova Lite model ID from DEVELOPMENT_REFERENCE.md: `amazon.nova-lite-v1:0`
  - score_relevance(self, query: str, document: str) -> float
  - rerank(self, query: str, results: list[dict], top_k: int = 5) -> list[dict]
  - _batch_score(self, query: str, documents: list[str]) -> list[float]

Relevance Scoring Prompt:
"Rate the relevance of this document to the query on a scale of 1-10.
Only respond with a single number.

Query: {query}

Document: {document}

Relevance score (1-10):"

Reranking Process:
1. Take top-N results from RRF (e.g., top 15)
2. Score each result's relevance to query
3. Sort by relevance score
4. Return top-K (e.g., top 5)

Key Features:
- Parse numeric score from LLM response
- Handle non-numeric responses (default to 5)
- Batch scoring for efficiency (if model supports)
- Include original scores in output for debugging

Output Format:
[
  {"id": "doc1", "relevance_score": 9, "rrf_score": 0.032, "text": "..."},
  {"id": "doc2", "relevance_score": 8, "rrf_score": 0.031, "text": "..."},
  ...
]

Cost Note:
- ~15 LLM calls per query (one per candidate)
- Nova Lite: ~$0.01-0.02 per reranking operation
- Consider truncating long documents to 500 tokens

Reference:
- Cross-encoder reranking papers
- Bedrock Nova Lite documentation
- [backend.mdc] for Python patterns

Verify: docker-compose exec backend python -c "from src.utils.reranker import CrossEncoderReranker; print('OK')"
```

### 10.2 Test Reranking

**Command:**
```bash
docker-compose exec backend python -c "
from src.utils.reranker import CrossEncoderReranker

reranker = CrossEncoderReranker()

query = 'What are Apple supply chain risks?'
candidates = [
    {'id': 'doc1', 'text': 'Apple faces significant supply chain risks due to concentration in China...'},
    {'id': 'doc2', 'text': 'The iPhone 15 features a new titanium design...'},
    {'id': 'doc3', 'text': 'Supply chain disruptions could adversely affect manufacturing...'},
]

reranked = reranker.rerank(query, candidates, top_k=2)

print(f'Query: {query}')
print(f'\\nReranked results:')
for r in reranked:
    print(f'  {r[\"id\"]}: relevance={r[\"relevance_score\"]}/10')
    print(f'    {r[\"text\"][:60]}...')
"
```

**Expected Output:**
```
Query: What are Apple supply chain risks?

Reranked results:
  doc1: relevance=9/10
    Apple faces significant supply chain risks due to concentratio...
  doc3: relevance=8/10
    Supply chain disruptions could adversely affect manufacturing...
```

### 10.3 Update Utils Package Init with Reranker

**Agent Prompt:**
```
Update `backend/src/utils/__init__.py`

Add imports and exports for reranker:
1. from src.utils.reranker import CrossEncoderReranker
2. Add to __all__: "CrossEncoderReranker"

Reference:
- reranker.py module just created

Verify: docker-compose exec backend python -c "from src.utils import CrossEncoderReranker; print('OK')"
```

### 10.4 Cross-Encoder Reranking Checklist

- [ ] reranker.py created with CrossEncoderReranker class
- [ ] Nova Lite model ID correct: amazon.nova-lite-v1:0
- [ ] score_relevance returns numeric score (1-10)
- [ ] rerank sorts by relevance score descending
- [ ] Handles edge cases (non-numeric responses default to 5)
- [ ] Utils __init__.py exports CrossEncoderReranker
- [ ] Test reranking improves result ordering

---

## 10b. Contextual Compression

### What We're Doing
Implementing contextual compression to extract only relevant sentences from each passage, reducing noise and context length for final synthesis.

### Why This Matters
- **Noise Reduction:** Removes tangential information from retrieved passages
- **Focused Context:** LLM sees only relevant sentences
- **Token Efficiency:** Reduces token usage in final synthesis step
- **Quality:** Cited text directly supports the answer

> **Reference:** This is Step 5 in the RAG_README.md query pipeline, between reranking and answer synthesis.

### 10b.1 Create Contextual Compressor Module

**Agent Prompt:**
```
Create `backend/src/utils/compressor.py`

Requirements:
1. Extract only query-relevant sentences from each passage
2. Use Nova Lite for efficient compression
3. Preserve source citations through compression

Structure:
- ContextualCompressor class:
  - __init__(self, model_id: str = "amazon.nova-lite-v1:0")
  - compress(self, query: str, passage: str) -> str
  - compress_results(self, query: str, results: list[dict]) -> list[dict]

Compression Prompt:
"Extract only the sentences from this passage that are directly relevant to answering the question.
Return only the relevant sentences, nothing else. If no sentences are relevant, return 'NOT_RELEVANT'.

Question: {query}

Passage: {passage}

Relevant sentences:"

Key Features:
- Preserve sentence boundaries
- Keep source metadata (document, page, section) unchanged
- Filter out passages that return "NOT_RELEVANT"
- Handle edge cases: very short passages, no relevant content

**Parent/Child Integration (Important):**
- Compress the `parent_text` field (1024 tokens) - this is the full context sent to the LLM
- Do NOT modify `child_text_raw` - preserve this for citation match preview
- Store compressed result in new `compressed_text` field
- Short passages (<100 tokens in parent_text) can skip compression

compress_results() should handle parent/child structure:
```python
def compress_results(self, query: str, results: list[dict]) -> list[dict]:
    """Compress parent_text while preserving child_text_raw for citations."""
    compressed_results = []
    for result in results:
        metadata = result.get("metadata", {})
        parent_text = metadata.get("parent_text", metadata.get("text", ""))
        
        # Skip compression for short passages
        if len(parent_text) < 400:  # ~100 tokens
            result["compressed_text"] = parent_text
            compressed_results.append(result)
            continue
        
        compressed = self.compress(query, parent_text)
        if compressed != "NOT_RELEVANT":
            result["compressed_text"] = compressed
            # Preserve child_text_raw for citation preview
            compressed_results.append(result)
    
    return compressed_results
```

Example:
Input passage: "Apple Inc. reported revenue of $394B in fiscal 2024. 
               The company's new titanium design was well-received.
               Supply chain risks remain concentrated in Greater China."

Query: "What are Apple's supply chain risks?"

Output: "Supply chain risks remain concentrated in Greater China."

Cost Note:
- ~$0.002 per compression call (Nova Lite)
- ~5 calls per query (one per reranked result)
- Consider skipping for very short passages (<100 tokens)

Reference:
- RAG_README.md Query Pipeline Step 5
- [backend.mdc] for Python patterns

Verify: docker-compose exec backend python -c "from src.utils.compressor import ContextualCompressor; print('OK')"
```

### 10b.2 Test Contextual Compression

**Command:**
```bash
docker-compose exec backend python -c "
from src.utils.compressor import ContextualCompressor

compressor = ContextualCompressor()

query = 'What are Apple supply chain risks?'
passage = '''Apple Inc. reported revenue of \$394B in fiscal 2024.
The company introduced the iPhone 15 with a new titanium design.
Supply chain risks remain concentrated in Greater China.
Manufacturing partners in Taiwan and Vietnam provide key components.
The new Apple Watch features improved health sensors.'''

compressed = compressor.compress(query, passage)
print(f'Query: {query}')
print(f'\\nOriginal ({len(passage)} chars):\\n{passage[:200]}...')
print(f'\\nCompressed ({len(compressed)} chars):\\n{compressed}')
"
```

**Expected Output:**
```
Query: What are Apple supply chain risks?

Original (312 chars):
Apple Inc. reported revenue of $394B in fiscal 2024.
The company introduced the iPhone 15 with a new titanium design.
Supply chain risks remain concentrated in Greater China.
Manufacturing partners...

Compressed (128 chars):
Supply chain risks remain concentrated in Greater China.
Manufacturing partners in Taiwan and Vietnam provide key components.
```

### 10b.3 Update Utils Package Init with Compressor

**Agent Prompt:**
```
Update `backend/src/utils/__init__.py`

Add imports and exports for compressor:
1. from src.utils.compressor import ContextualCompressor
2. Add to __all__: "ContextualCompressor"

Reference:
- compressor.py module just created

Verify: docker-compose exec backend python -c "from src.utils import ContextualCompressor; print('OK')"
```

### 10b.4 Contextual Compression Checklist

- [ ] compressor.py created with ContextualCompressor class
- [ ] compress() extracts relevant sentences
- [ ] compress_results() handles batch processing with parent/child structure
- [ ] Compresses `parent_text` field (1024 tokens)
- [ ] Preserves `child_text_raw` for citation preview
- [ ] Stores result in `compressed_text` field
- [ ] NOT_RELEVANT passages filtered out
- [ ] Source metadata preserved
- [ ] Utils __init__.py exports ContextualCompressor
- [ ] Test compression reduces passage length

---

## 11. Hybrid RAG Integration

### What We're Doing
Integrating all retrieval components (dense, BM25, KG, query expansion, RRF, reranking) into a unified hybrid RAG pipeline.

### Why This Matters
- **Full Pipeline:** Combines all Phase 2b improvements
- **Quality Improvement:** Each component adds retrieval quality
- **Unified Interface:** Single function for all retrieval needs

> **⚠️ Phase 2a Parent/Child Architecture Dependency**
> 
> Phase 2a implemented parent/child chunking where:
> - **Child chunks (256 tokens)** are embedded and stored in Pinecone
> - **Parent text (1024 tokens)** is stored in metadata for full LLM context
> - Key fields: `parent_id`, `parent_text`, `child_text`, `child_text_raw`
> 
> The HybridRetriever MUST preserve this structure:
> 1. Results are deduplicated by `parent_id` (not just chunk ID)
> 2. `parent_text` is used for LLM context and compression
> 3. `child_text_raw` is preserved for citation "Matched:" previews
> 
> See Phase 2a Section 8.2 (Parent/Child Chunking) and Section 10 (RAG Tool) for full details.

### 11.1 Create Hybrid Retriever Module

**Agent Prompt:**
```
Create `backend/src/ingestion/hybrid_retriever.py`

Requirements:
1. Orchestrate full hybrid retrieval pipeline
2. Combine dense search, BM25, Knowledge Graph
3. Apply query expansion, RRF fusion, reranking, and compression

Structure:
- HybridRetriever class:
  - __init__(self, pinecone_client, neo4j_store, embeddings, bm25_encoder, query_expander, reranker, compressor)
  - retrieve(self, query: str, top_k: int = 5, use_kg: bool = True, compress: bool = True) -> list[dict]
  - _dense_search(self, query: str, top_k: int) -> list[dict]
  - _bm25_search(self, query: str, top_k: int) -> list[dict]
  - _kg_search(self, query: str) -> list[dict]

Full Pipeline (6 steps from RAG_README):
1. Query Expansion: Generate 3 variants (Nova Lite)
2. Parallel Retrieval: For each variant:
   a. Dense search (Pinecone)
   b. BM25 search (Pinecone sparse)
3. Knowledge Graph lookup (extract entities, find documents)
4. RRF Fusion: Merge all results (in-memory)
5. Cross-Encoder Reranking: Score top 15 (Nova Lite)
6. Contextual Compression: Extract relevant sentences from top 5 (Nova Lite)
7. Return with source citations

Pipeline Parameters:
- dense_top_k: 15 (per variant)
- bm25_top_k: 15 (per variant)
- rrf_k: 60 (standard)
- rerank_candidates: 15
- final_top_k: 5 (configurable)

Output Format (Parent/Child Compatible):
[
  {
    "id": "AAPL_10K_2024_child_42",
    "parent_id": "AAPL_10K_2024_parent_5",
    "parent_text": "The full 1024-token parent context for LLM...",
    "child_text_raw": "The 256-token matched child text for citation preview...",
    "compressed_text": "Relevant sentences extracted by compressor (if enabled)...",
    "relevance_score": 9,
    "rrf_score": 0.032,
    "sources": ["dense", "bm25", "kg"],
    "metadata": {
      "document_id": "AAPL_10K_2024",
      "ticker": "AAPL",
      "section": "Item 1A: Risk Factors",
      "page": 15,
      "fiscal_year": 2024
    }
  },
  ...
]

**Field Descriptions (Parent/Child Architecture from Phase 2a):**
- `id`: Child chunk ID (what was embedded and matched)
- `parent_id`: Parent chunk ID (groups related children)
- `parent_text`: Full 1024-token context (used for LLM synthesis)
- `child_text_raw`: Original 256-token text without enrichment (used for citation preview)
- `compressed_text`: Query-relevant sentences from parent_text (if compression enabled)
- `relevance_score`: Cross-encoder reranking score (1-10)
- `rrf_score`: RRF fusion score before reranking
- `sources`: Which retrieval methods found this result

Key Features:
- Parallel queries for dense and BM25 (use asyncio if possible)
- Entity extraction from query for KG lookup
- Deduplication by chunk ID before RRF (same chunk from multiple sources)
- **Parent deduplication after RRF** (multiple children from same parent → keep highest scoring)
- Include retrieval stats in response (optional)

**Parent/Child Deduplication (Critical):**

Multiple child chunks from the same parent may rank highly after RRF fusion.
Deduplicate by `parent_id` BEFORE reranking to avoid sending duplicate context:

```python
def _deduplicate_by_parent(self, results: list[dict]) -> list[dict]:
    """
    Keep only the highest-scoring child per parent.
    This prevents duplicate parent context in final results.
    """
    parent_best: dict[str, dict] = {}
    
    for result in results:
        metadata = result.get("metadata", {})
        parent_id = metadata.get("parent_id", result.get("id", "unknown"))
        score = result.get("rrf_score", 0.0)
        
        if parent_id not in parent_best or score > parent_best[parent_id]["rrf_score"]:
            parent_best[parent_id] = result
    
    # Sort by RRF score descending
    return sorted(parent_best.values(), key=lambda x: x.get("rrf_score", 0), reverse=True)
```

**Integration with Phase 2a RAG Tool:**

The existing `rag.py` from Phase 2a has helper functions for parent/child handling.
HybridRetriever should use compatible output format so `rag.py` functions work seamlessly:
- `_deduplicate_by_parent()` - works with `parent_id` in metadata
- `_get_result_text()` - prefers `parent_text`, falls back to `text`/`child_text`
- `_format_citation()` - uses `child_text_raw` for match preview

**Graceful Degradation (Important):**

The HybridRetriever should handle component failures gracefully:

def retrieve(self, query: str, top_k: int = 5, ...) -> list[dict]:
    results_by_source = {}
    errors = []
    
    # Dense search (required - if this fails, fall back to dense-only)
    try:
        results_by_source["dense"] = self._dense_search(query, top_k=15)
    except Exception as e:
        logger.error(f"Dense search failed: {e}")
        raise  # Dense is required, cannot continue without it
    
    # BM25 search (optional - continue without if fails)
    try:
        results_by_source["bm25"] = self._bm25_search(query, top_k=15)
    except Exception as e:
        logger.warning(f"BM25 search failed, continuing with dense only: {e}")
        errors.append("bm25")
    
    # KG search (optional - continue without if fails)
    try:
        results_by_source["kg"] = self._kg_search(query)
    except Exception as e:
        logger.warning(f"KG search failed, continuing without: {e}")
        errors.append("kg")
    
    # Continue with available results...
    # Include errors in response metadata for debugging:
    return {
        "results": final_results,
        "retrieval_sources": list(results_by_source.keys()),
        "failed_sources": errors
    }

**Priority Order for Degradation:**
1. Dense search is REQUIRED - if Pinecone is down, fail the request
2. BM25 search is OPTIONAL - continue with dense-only if sparse fails
3. KG search is OPTIONAL - continue without entity-based results if Neo4j is down
4. Query expansion is OPTIONAL - use original query only if Nova Lite is down
5. Reranking is OPTIONAL - use RRF scores directly if Nova Lite quota exceeded
6. Compression is OPTIONAL - return full passages if compression fails

Reference:
- All components from Sections 3-10
- PHASE_2_REQUIREMENTS.md query pipeline architecture
- [backend.mdc] for Python patterns

Verify: docker-compose exec backend python -c "from src.ingestion.hybrid_retriever import HybridRetriever; print('OK')"
```

### 11.2 Update Ingestion Package Init with HybridRetriever

**Agent Prompt:**
```
Update `backend/src/ingestion/__init__.py`

Add imports and exports for hybrid retriever:
1. from src.ingestion.hybrid_retriever import HybridRetriever
2. Add to __all__: "HybridRetriever"

Reference:
- HybridRetriever module just created

Verify: docker-compose exec backend python -c "from src.ingestion import HybridRetriever; print('OK')"
```

### 11.3 Update RAG Tool with Hybrid Retrieval

**Agent Prompt:**
```
Update `backend/src/agent/tools/rag.py` to use HybridRetriever

Requirements:
1. Replace basic dense-only retrieval with HybridRetriever
2. Update retrieve_documents function to use full pipeline
3. Add option to disable hybrid features for simpler queries
4. Update tool description for better agent selection
5. Format response with retrieval stats and citations
6. **PRESERVE existing parent/child handling functions from Phase 2a**

Updated Function Signature:
- retrieve_documents(query: str, top_k: int = 5, hybrid: bool = True) -> str

**Parent/Child Functions to PRESERVE (from Phase 2a):**

The existing rag.py has critical parent/child handling that MUST be preserved:

1. `_deduplicate_by_parent(results)` - Deduplicates by parent_id, keeps highest score
2. `_get_result_text(metadata, warn_missing)` - Gets parent_text with fallback
3. `_format_citation(metadata)` - Formats citation with child_text_raw preview

These functions work with both:
- Phase 2a dense-only results (has parent_text, child_text_raw in metadata)
- Phase 2b hybrid results (same structure from HybridRetriever)

Key Features:
- If hybrid=True: Use full pipeline (expansion, dense+BM25+KG, RRF, reranking)
- If hybrid=False: Use basic dense search only (Phase 2a behavior, fallback)
- Include relevance scores in citations
- Track which retrieval sources contributed
- **Use parent_text for LLM context (1024 tokens)**
- **Use child_text_raw for "Matched:" citation preview (256 tokens)**
- **Use compressed_text if available (after contextual compression)**

Updated Tool Description:
"Search 10-K document text for information. Use for:
 - Risk factors and challenges
 - Business descriptions and strategy
 - Qualitative questions about company operations
 - Context around numbers from SQL queries"

Response Format (uses parent/child structure):
"Found 5 relevant passages (hybrid retrieval: dense+BM25+KG, reranked):

[1] Source: Apple 10-K 2024, Item 1A, Page 15 (Relevance: 9/10)
{parent_text or compressed_text - full context for LLM}
Matched: {first 100 chars of child_text_raw}...

[2] Source: NVIDIA 10-K 2024, Item 1A, Page 22 (Relevance: 8/10)
{parent_text or compressed_text - full context for LLM}
Matched: {first 100 chars of child_text_raw}...
..."

**Integration Pattern:**

```python
async def _retrieve_hybrid(query: str, top_k: int, filters: dict | None) -> str:
    """Use HybridRetriever with parent/child compatible output."""
    retriever = _get_hybrid_retriever()
    
    # HybridRetriever returns results with parent_text, child_text_raw
    results = await retriever.retrieve(
        query=query,
        top_k=top_k * 3,  # Request more for parent deduplication
        use_kg=True,
        compress=True
    )
    
    # Results already deduplicated by parent_id in HybridRetriever
    # Use existing _format_results() which handles parent/child structure
    return _format_results(results[:top_k], query)
```

Reference:
- HybridRetriever from Section 11.1
- Existing rag.py structure from Phase 2a (preserve parent/child functions)
- [agent.mdc] for tool patterns
- [backend.mdc] for Python patterns

Verify: docker-compose exec backend python -c "from src.agent.tools.rag import retrieve_documents; print('OK')"
```

### 11.4 Test Hybrid Retrieval

**Command:**
```bash
docker-compose exec backend python -c "
from src.agent.tools.rag import retrieve_documents

# Test with hybrid retrieval
result = retrieve_documents('What are the supply chain risks for tech companies?', hybrid=True)
print(result)
"
```

**Expected Output:**
```
Found 5 relevant passages (hybrid retrieval: dense+BM25+KG, reranked):

[1] Source: Apple 10-K 2024, Item 1A: Risk Factors, Page 15 (Relevance: 9/10)
The Company's business, results of operations, and financial condition depend on its 
ability to source adequate supplies of components...

[2] Source: NVIDIA 10-K 2024, Item 1A: Risk Factors, Page 22 (Relevance: 9/10)
Our supply chain and manufacturing operations are global and complex...

...
```

### 11.5 Hybrid RAG Integration Checklist

- [ ] hybrid_retriever.py created with HybridRetriever class
- [ ] All 6 pipeline steps integrated:
  - [ ] Query expansion (Section 8)
  - [ ] Dense search (Phase 2a)
  - [ ] BM25 search (Section 7)
  - [ ] KG search (Section 6)
  - [ ] RRF fusion (Section 9)
  - [ ] Cross-encoder reranking (Section 10)
  - [ ] Contextual compression (Section 10b)
- [ ] **Parent/Child Architecture (Phase 2a compatibility):**
  - [ ] Output includes `parent_id`, `parent_text`, `child_text_raw` fields
  - [ ] `_deduplicate_by_parent()` deduplicates by parent_id after RRF
  - [ ] Compression operates on `parent_text` (1024 tokens)
  - [ ] `child_text_raw` preserved for citation "Matched:" preview
- [ ] Ingestion __init__.py exports HybridRetriever
- [ ] rag.py updated to use HybridRetriever
- [ ] **Existing rag.py parent/child functions preserved:**
  - [ ] `_deduplicate_by_parent()` still works
  - [ ] `_get_result_text()` prefers parent_text
  - [ ] `_format_citation()` uses child_text_raw for match preview
- [ ] Tool description updated for better agent selection
- [ ] hybrid=True uses full pipeline
- [ ] hybrid=False falls back to basic dense search
- [ ] Test shows improved retrieval quality

---

## 12. Multi-Tool Orchestration

### What We're Doing
Enabling complex queries that combine SQL (for structured data), RAG (for document context), and Tavily (for current news) in a single response. This involves updating tool descriptions to help the agent select the right tool(s) for each query type.

### Why This Matters
- **Complete Answers:** Some questions need numbers, context, AND current events
- **Seamless Experience:** User doesn't specify which tool to use
- **Demo Value:** Shows agent intelligence in tool selection
- **Cross-Source Analysis:** Enables comparing news claims to 10-K disclosures

### 12.1 Tool Selection Matrix

Understanding which tool to use for which query type:

| Query Type | SQL | RAG | Tavily | Example |
|------------|-----|-----|--------|---------|
| Specific numbers | ✓ | - | - | "What is Apple's revenue?" |
| Comparisons | ✓ | - | - | "Which company has highest margin?" |
| Risk factors | - | ✓ | - | "What risks does Tesla mention?" |
| Business strategy | - | ✓ | - | "How does Apple describe their services strategy?" |
| Current news | - | - | ✓ | "What's the latest news on NVIDIA?" |
| Numbers + context | ✓ | ✓ | - | "What is Apple's China revenue and what risks do they mention?" |
| News vs 10-K | - | ✓ | ✓ | "Does recent Apple news align with their 10-K?" |
| Full analysis | ✓ | ✓ | ✓ | "Analyze Apple's China situation with current news" |

### 12.2 Verify Agent Tool Selection

**Command:**
```bash
docker-compose exec backend python -c "
from src.agent.graph import graph

# Test query that should use both SQL and RAG
result = graph.invoke({
    'messages': [{
        'role': 'user', 
        'content': 'What is Apple\\'s revenue from China, and what risks do they mention about their China operations?'
    }]
})

# Check which tools were called
print('Response:')
print(result['messages'][-1].content)
"
```

**Expected Behavior:**
1. Agent recognizes this needs SQL (for China revenue numbers)
2. Agent recognizes this needs RAG (for risk narrative)
3. Agent calls both tools and combines results

### 12.3 Test Multi-Tool Queries

**Test Queries:**

```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Test 1: Numbers + Context (SQL + RAG)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Compare Microsoft and Google cloud revenue, and what competitive risks do they each mention?"}'

# Test 2: Quantitative analysis with qualitative context (SQL + RAG)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Which company has the highest gross margin, and what does their 10-K say about margin sustainability?"}'

# Test 3: Entity-based with numbers (SQL + RAG)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is NVIDIA total revenue, and what do they say about AI chip demand?"}'

# Test 4: Full analysis with current context (SQL + RAG + Tavily)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Analyze Apple China situation: their revenue there, disclosed risks, and any recent news developments."}'
```

### 12.4 Enhance Tool Descriptions for Better Selection

**Agent Prompt:**
```
Update tool descriptions in `backend/src/agent/tools/` for optimal selection

Requirements:
1. Each tool must have DISTINCT, NON-OVERLAPPING descriptions
2. Include explicit "USE THIS FOR" and "DO NOT USE FOR" sections
3. Help agent understand when to combine multiple tools

**Updated sql_query Description:**

@tool("sql_query", args_schema=SQLQueryInput)
async def sql_query(query: str) -> Dict[str, Any]:
    """
    Query STRUCTURED financial data from 10-K SEC filings stored in PostgreSQL.
    
    USE THIS TOOL FOR:
    - Specific NUMBERS: revenue, net income, margins, EPS, growth rates
    - COMPARISONS across companies: "which company has highest X"
    - SEGMENT revenue breakdowns: iPhone, Services, Cloud, etc.
    - GEOGRAPHIC revenue: Americas, Europe, Greater China
    - Year-over-year CALCULATIONS: growth rates, changes
    
    DO NOT USE FOR:
    - Qualitative questions about risks, strategy, or outlook (use RAG)
    - Current news or market information (use Tavily)
    - Questions about WHY numbers changed (use RAG for context)
    
    AVAILABLE DATA:
    - 7 companies: AAPL, MSFT, AMZN, GOOGL, TSLA, JPM, NVDA
    - Fiscal years: 2023, 2024
    - Tables: companies, financial_metrics, segment_revenue, geographic_revenue, risk_factors
    
    Returns: Formatted results with SQL query shown for transparency.
    """

**Updated retrieve_documents (RAG) Description:**

@tool("rag_retrieval", args_schema=RAGQueryInput)
async def rag_retrieval(query: str) -> Dict[str, Any]:
    """
    Search 10-K document TEXT and reference documents for qualitative information.
    
    USE THIS TOOL FOR:
    - RISK FACTORS: supply chain, regulatory, competition, macroeconomic
    - BUSINESS DESCRIPTIONS: strategy, competitive advantages, operations
    - MANAGEMENT DISCUSSION: outlook, challenges, opportunities
    - CONTEXT for numbers: "why did revenue change", "what affects margins"
    - Cross-referencing claims from news articles against official disclosures
    
    DO NOT USE FOR:
    - Specific numbers like revenue or margins (use SQL)
    - Current news or real-time information (use Tavily)
    - Calculations or comparisons across companies (use SQL)
    
    AVAILABLE DOCUMENTS:
    - 10-K filings: 7 companies (AAPL, MSFT, AMZN, GOOGL, TSLA, JPM, NVDA)
    - Reference documents: news articles, research reports, industry analysis
    
    Returns: Relevant passages with source citations (document, page, section).
    """

**Updated tavily_search Description:**

@tool("tavily_search", args_schema=SearchInput)
async def tavily_search(query: str) -> Dict[str, Any]:
    """
    Search the web for CURRENT and RECENT information not in 10-K filings.
    
    USE THIS TOOL FOR:
    - BREAKING NEWS: recent announcements, earnings, events
    - CURRENT market conditions: stock prices, analyst ratings
    - RECENT developments: regulatory actions, lawsuits, partnerships
    - Information NEWER than the 10-K filing dates
    - Context for comparing news claims to official disclosures
    
    DO NOT USE FOR:
    - Historical 10-K data (use SQL or RAG)
    - Official company disclosures (use RAG for 10-K text)
    - Precise financial numbers (use SQL)
    
    Returns: Web search results with titles, snippets, and URLs.
    """

Key Principles for Multi-Tool Selection:
- SQL = NUMBERS, comparisons, calculations (structured data)
- RAG = NARRATIVE, context, qualitative (document text)  
- Tavily = CURRENT events, news, real-time (web search)

When query needs multiple perspectives:
1. Use SQL for any specific numbers mentioned
2. Use RAG for context, risks, or qualitative aspects
3. Use Tavily for current/recent news context
4. Synthesize all results into a coherent answer

Reference:
- Existing tool function docstrings
- [agent.mdc] for tool description patterns
- [backend.mdc] for Python docstring format

Verify: docker-compose exec backend python -c "
from src.agent.tools.sql import sql_query
from src.agent.tools.rag import rag_retrieval
from src.agent.tools.search import tavily_search
print('SQL:', sql_query.__doc__[:150])
print('RAG:', rag_retrieval.__doc__[:150])
print('Tavily:', tavily_search.__doc__[:150])
"
```

### 12.5 Cross-Document Analysis Queries

These queries demonstrate the sophisticated analysis capability:

**Test: News vs 10-K Comparison**
```bash
# This should use RAG (for 10-K risks) + Tavily (for current news)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Search for recent news about Apple China concerns, and compare what you find to the risks Apple disclosed in their 10-K filing."}'
```

**Expected Agent Behavior:**
1. Use Tavily to search for "Apple China news"
2. Use RAG to search 10-K for "China risks" or "Greater China"
3. Synthesize: "Recent news reports X, which aligns with/adds to the 10-K disclosure that..."

**Test: Full Financial Analysis**
```bash
# This should use SQL + RAG + Tavily
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Give me a complete analysis of NVIDIA: their revenue and margins, key risks they disclose, and any recent news about AI chip demand."}'
```

**Expected Agent Behavior:**
1. SQL: Get NVDA revenue, margins, segment breakdown
2. RAG: Find risk factors related to AI chips, supply chain
3. Tavily: Search for recent NVIDIA AI chip news
4. Synthesize into comprehensive analysis with citations

### 12.6 Multi-Tool Orchestration Checklist

- [ ] Agent correctly identifies multi-tool queries
- [ ] SQL tool called for quantitative parts
- [ ] RAG tool called for qualitative parts
- [ ] Tavily tool called for current news context
- [ ] Tool descriptions updated with USE/DO NOT USE sections
- [ ] Cross-document analysis queries work (news vs 10-K)
- [ ] Full analysis queries combine all three tools
- [ ] Response synthesizes data from all sources with proper citations

---

## 12b. Cross-Document Analysis Workflow

### What We're Doing
Implementing sophisticated analysis that compares information across different source types: 10-K official disclosures, reference documents (news/research), and live web search. This is the key differentiator for the demo experience.

### Why This Matters
- **Verification:** Compare news claims against official disclosures
- **Context:** Understand how current events relate to disclosed risks
- **Analysis:** Provide comprehensive answers that synthesize multiple sources
- **Demo Impact:** Shows the power of multi-source agentic AI

### 12b.1 Source Types and Authority Levels

The system distinguishes between source types for proper analysis:

| Source Type | Authority | Examples | Use Case |
|-------------|-----------|----------|----------|
| `official` | High | 10-K filings | Authoritative company disclosures |
| `news` | Medium | Reuters, Bloomberg, FT | Third-party reporting on events |
| `research` | Medium | Analyst reports, Seeking Alpha | Expert analysis and opinions |
| `policy` | High | Regulatory announcements | Official policy positions |
| `live` | Current | Tavily search results | Real-time web information |

### 12b.2 Analysis Patterns

**Pattern 1: Claim Verification (News → 10-K)**

User: "I read that Apple's services hit a record. Is that accurate?"

Agent workflow:
1. **Tavily/RAG**: Find the claim in news sources
2. **SQL**: Query actual services revenue by year
3. **RAG**: Find 10-K disclosure about services
4. **Synthesize**: "The claim is ACCURATE. Apple's services revenue was $96.2B in FY2024, up from $85.2B in FY2023. The 10-K confirms this growth in Item 7 (MD&A)."

**Pattern 2: Risk Context (News → 10-K Risks)**

User: "There's news about new China tariffs. How might this affect Apple?"

Agent workflow:
1. **Tavily**: Search for recent China tariff news
2. **RAG**: Search 10-K for China-related risk factors
3. **SQL**: Get Apple's Greater China revenue exposure
4. **Synthesize**: "Recent news reports potential tariffs on X. Apple disclosed China risks in Item 1A (page 15-18) including supply chain concentration and trade tensions. Greater China represents 17.4% of revenue ($66.7B). Key disclosed risks align with this news..."

**Pattern 3: Competitive Analysis (Multiple 10-Ks + News)**

User: "Compare how Apple and Microsoft are positioning for AI."

Agent workflow:
1. **RAG**: Search both companies' 10-Ks for AI mentions
2. **SQL**: Get R&D spending for both companies
3. **Tavily**: Search for recent AI strategy news
4. **Synthesize**: Compare strategies with numbers and current context

### 12b.3 Implement Analysis Hints in Chat Node

**Agent Prompt:**
```
Update `backend/src/agent/nodes/chat.py` to enhance SYSTEM_PROMPT for multi-source synthesis

Changes:
1. Expand the existing SYSTEM_PROMPT constant with synthesis guidance
2. Keep the existing capabilities list
3. Add new sections for citation format and synthesis

Updated SYSTEM_PROMPT (replace existing):

SYSTEM_PROMPT = """You are an Enterprise Agentic AI Assistant with persistent conversation memory.

CAPABILITIES:
- You HAVE memory of this conversation. You can recall what the user said earlier.
- You have access to tools: SQL queries (financial metrics), RAG retrieval (10-K document text), Tavily search (current news), and market data.
- You provide helpful, accurate, and contextual responses.

TOOL USAGE:
When answering questions, select tools based on need:
- SQL: Numbers, metrics, comparisons (revenue, margins, EPS)
- RAG: Qualitative text from 10-Ks (risk factors, strategy, MD&A)
- Tavily: Current news, recent events not in 10-K filings
- Market Data: Current stock prices and market information

CITATION FORMAT (IMPORTANT):
Always cite your sources clearly:
- SQL data: "According to FY2024 financial data..."
- 10-K documents: "[Company] 10-K 2024, Item [X], Page [Y] states..."
- Reference documents: "Per [source] dated [date]..."
- Live search: "Recent news from [source] reports..."

SYNTHESIS GUIDELINES:
For complex questions using multiple tools:
1. Provide a direct answer first
2. Support with evidence from each source
3. Note any discrepancies between sources
4. Indicate confidence level if information is incomplete
5. If news claims differ from 10-K disclosures, explain possible reasons

VERIFICATION PATTERN:
When asked to verify claims or compare sources:
- First find the claim (search news or documents)
- Then verify against official source (SQL for numbers, RAG for disclosures)
- State clearly: CONFIRMED, CONTRADICTED, or PARTIALLY_SUPPORTED

IMPORTANT:
- DO NOT say you cannot remember past interactions - you CAN see conversation history.
- Reference previous messages naturally when relevant.
- Be concise but thorough."""

Reference:
- Existing chat.py SYSTEM_PROMPT location
- Section 12b analysis patterns
- [backend.mdc] for Python patterns

Verify: docker-compose exec backend python -c "from src.agent.nodes.chat import SYSTEM_PROMPT; print(len(SYSTEM_PROMPT))"
```

### 12b.4 Test Cross-Document Analysis

**Test 1: Numerical Claim Verification**
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "News reports say Apple services revenue hit a record in 2024. Can you verify this against their 10-K filing?"}'
```

**Expected Response Pattern:**
```
Based on my analysis across multiple sources:

**CLAIM VERIFICATION: CONFIRMED**

The claim that Apple services revenue hit a record is accurate.

**Evidence:**

1. **From 10-K Financial Data (FY2024):**
   - Services Revenue: $96.2 billion
   - Year-over-Year Growth: +12.9% (from $85.2B in FY2023)
   - Source: Apple 10-K 2024, Consolidated Financial Statements

2. **From 10-K Narrative (Item 7: MD&A):**
   "Services revenue increased 13 percent during 2024 compared to 2023 
   due primarily to higher revenue from advertising, the App Store and 
   cloud services."
   - Source: Apple 10-K 2024, Item 7, Page 32

**Conclusion:** The FY2024 services revenue of $96.2B is indeed the 
highest on record, confirming the news report.
```

**Test 2: Risk Alignment Analysis**
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Search for recent news about semiconductor supply issues, then tell me which companies in the database disclosed supply chain risks and how exposed they are."}'
```

**Test 3: Full Company Deep Dive**
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Give me a comprehensive analysis of Tesla: key financials, major disclosed risks, and how recent news might relate to those risks."}'
```

### 12b.5 Cross-Document Analysis Checklist

- [ ] Agent can verify numerical claims against SQL data
- [ ] Agent can find relevant 10-K disclosures for news topics
- [ ] Agent properly cites sources by type (10-K, news, live search)
- [ ] Agent handles discrepancies between sources appropriately
- [ ] Agent synthesizes multi-source answers coherently
- [ ] Analysis guidance added to chat node system prompt
- [ ] Test queries produce well-structured multi-source responses

---

## 13. End-to-End Verification

### What We're Doing
Testing all Phase 2b features together to verify the intelligence layer works correctly. This includes comparing hybrid search vs dense-only, testing multi-tool queries, and deploying to AWS.

### Why This Matters
- **Integration:** Verify all components work together
- **Quality:** Confirm hybrid retrieval improves results
- **Readiness:** Confirm Phase 2b exit criteria met
- **Production:** Validate AWS deployment with new features

### 13.1 Knowledge Graph Verification

**Commands:**
```bash
# Check entity counts
docker-compose exec neo4j cypher-shell -u neo4j -p localdevpassword \
  "MATCH (n) RETURN labels(n)[0] as type, count(*) as count ORDER BY count DESC LIMIT 10"

# Check relationship counts
docker-compose exec neo4j cypher-shell -u neo4j -p localdevpassword \
  "MATCH ()-[r]->() RETURN type(r) as rel, count(*) as count"

# Test entity query
docker-compose exec backend python -c "
from src.knowledge_graph import Neo4jStore, GraphQueries
from src.config.settings import get_settings

settings = get_settings()
store = Neo4jStore(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
queries = GraphQueries(store)

docs = queries.find_documents_mentioning('Tim Cook')
print(f'Documents mentioning Tim Cook: {docs}')
store.close()
"
```

### 13.2 Hybrid Search Quality Comparison

**Command:**
```bash
docker-compose exec backend python -c "
from src.agent.tools.rag import retrieve_documents

query = 'What are the supply chain risks related to China?'

# Basic dense search
print('=== Basic Dense Search ===')
basic = retrieve_documents(query, top_k=3, hybrid=False)
print(basic)

print('\\n=== Hybrid Search (Dense + BM25 + KG + Reranking) ===')
hybrid = retrieve_documents(query, top_k=3, hybrid=True)
print(hybrid)
"
```

**Expected:** Hybrid results should be more relevant and diverse.

### 13.3 Phase 2b Exit Test Queries

**Test 1: Multi-source hybrid retrieval**
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What are the main regulatory risks mentioned by tech companies?"}'
```

**Test 2: SQL + RAG combined**
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is Apple China revenue and what risks do they disclose about China?"}'
```

**Test 3: Entity-based query (tests KG)**
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Find all documents that mention Tim Cook and summarize what they say about him."}'
```

### 13.4 Deploy and Test on AWS

**Commands:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Build and push updated backend
docker build -t backend -f backend/Dockerfile backend/
docker tag backend:latest YOUR_ECR_URL:latest
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ECR_URL
docker push YOUR_ECR_URL:latest

# Trigger App Runner deployment
aws apprunner start-deployment --service-arn YOUR_SERVICE_ARN

# Wait for deployment
sleep 180

# Test on AWS
curl -X POST https://yhvmf3inyx.us-east-1.awsapprunner.com/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Compare gross margins across tech companies and explain what affects margins."}'
```

### 13.5 Verify Parent/Child Structure in Hybrid Pipeline

**Command (verify parent/child fields preserved through hybrid pipeline):**
```bash
docker-compose exec backend python -c "
from src.ingestion.hybrid_retriever import HybridRetriever
from src.config.settings import get_settings

# Initialize retriever (uses cached clients)
retriever = HybridRetriever()

# Test query
results = retriever.retrieve('What are supply chain risks?', top_k=3)

print('Verifying parent/child structure in hybrid results:')
for i, r in enumerate(results):
    metadata = r.get('metadata', {})
    print(f'\\nResult {i+1}:')
    print(f'  id: {r.get(\"id\", \"N/A\")}')
    print(f'  parent_id: {metadata.get(\"parent_id\", \"MISSING\")}')
    print(f'  parent_text: {len(metadata.get(\"parent_text\", \"\"))} chars')
    print(f'  child_text_raw: {len(metadata.get(\"child_text_raw\", \"\"))} chars')
    print(f'  compressed_text: {len(r.get(\"compressed_text\", \"\"))} chars')
    print(f'  relevance_score: {r.get(\"relevance_score\", \"N/A\")}')
    print(f'  sources: {r.get(\"sources\", [])}')

# Verify all required fields present
required_fields = ['parent_id', 'parent_text', 'child_text_raw']
missing = []
for r in results:
    m = r.get('metadata', {})
    for field in required_fields:
        if not m.get(field):
            missing.append(f'{r.get(\"id\")}: {field}')

if missing:
    print(f'\\n⚠️ Missing parent/child fields: {missing}')
else:
    print(f'\\n✓ All {len(results)} results have parent/child structure')
"
```

**Expected Output:**
```
Verifying parent/child structure in hybrid results:

Result 1:
  id: AAPL_10K_2024_child_42
  parent_id: AAPL_10K_2024_parent_5
  parent_text: 1024 chars
  child_text_raw: 256 chars
  compressed_text: 312 chars
  relevance_score: 9
  sources: ['dense', 'bm25']

...

✓ All 3 results have parent/child structure
```

### 13.6 End-to-End Verification Checklist

- [ ] Knowledge Graph has 1000+ entities
- [ ] Entity queries return relevant documents
- [ ] Hybrid search returns better results than dense-only
- [ ] Query expansion generates meaningful variants
- [ ] Reranking improves result ordering
- [ ] **Parent/child structure preserved through hybrid pipeline**
- [ ] **Compression operates on parent_text, preserves child_text_raw**
- [ ] Multi-tool queries work (SQL + RAG)
- [ ] AWS deployment successful with new features

---

## Phase 2b Completion Checklist

### Knowledge Graph
- [ ] Ontology defined (EntityType, RelationType)
- [ ] Entity extraction working (spaCy + financial patterns)
- [ ] Neo4j store operations working
- [ ] Entities indexed from all documents
- [ ] Graph queries return relevant results (1-hop, 2-hop)

### Advanced RAG
- [ ] BM25 sparse vectors added to Pinecone
- [ ] Query expansion generates 3 variants (Nova Lite)
- [ ] RRF fusion merges results correctly
- [ ] Cross-encoder reranking improves precision (Nova Lite)
- [ ] Contextual compression extracts relevant sentences (Nova Lite)
- [ ] Hybrid retriever integrates all 6 pipeline steps
- [ ] Utils __init__.py exports: BM25Encoder, rrf_fusion, CrossEncoderReranker, ContextualCompressor
- [ ] Ingestion __init__.py exports: QueryExpander, HybridRetriever

### Parent/Child Architecture Compatibility (Phase 2a Integration)
- [ ] HybridRetriever output includes: `parent_id`, `parent_text`, `child_text_raw`
- [ ] Parent deduplication (`_deduplicate_by_parent`) works after RRF fusion
- [ ] Compression operates on `parent_text` (1024 tokens), stores in `compressed_text`
- [ ] `child_text_raw` preserved unchanged for citation "Matched:" preview
- [ ] Existing `rag.py` helper functions work with hybrid results:
  - [ ] `_deduplicate_by_parent()` - deduplicates by parent_id
  - [ ] `_get_result_text()` - prefers parent_text, falls back gracefully
  - [ ] `_format_citation()` - uses child_text_raw for match preview
- [ ] Backwards compatible with Phase 2a dense-only results

### Integration
- [ ] RAG tool uses hybrid retrieval by default
- [ ] RAG tool preserves parent/child handling from Phase 2a
- [ ] SQL tool description updated with USE/DO NOT USE sections
- [ ] RAG tool description updated with USE/DO NOT USE sections
- [ ] Tavily tool description updated with USE/DO NOT USE sections
- [ ] Multi-tool queries work (SQL + RAG + Tavily combined)
- [ ] Agent selects appropriate tools based on query type
- [ ] Streaming responses work with tools
- [ ] Error handling graceful

### Cross-Document Analysis
- [ ] Agent can verify numerical claims against SQL data
- [ ] Agent can compare news to 10-K disclosures
- [ ] Source citations include type (official, news, live)
- [ ] Multi-source synthesis produces coherent responses
- [ ] Analysis guidance added to chat node system prompt

### Quality Verification
- [ ] Hybrid search outperforms dense-only
- [ ] Entity queries find relevant documents
- [ ] Complex queries get complete answers
- [ ] Response latency acceptable (<10s for complex queries)

### Documentation
- [ ] REPO_STATE.md updated with new files
- [ ] All new modules have docstrings

---

## Common Issues and Solutions

### Issue: Neo4j connection timeout

**Symptoms:**
- "ServiceUnavailable" error
- Connection hangs

**Solution:**
```bash
# Check Neo4j is running
docker-compose ps neo4j

# Restart if needed
docker-compose restart neo4j

# Wait for healthy status
docker-compose logs neo4j | tail -20
```

### Issue: Entity extraction returns few entities

**Symptoms:**
- Less than expected entities per document
- Financial terms not extracted

**Solution:**
```bash
# Verify EntityRuler patterns are loaded
docker-compose exec backend python -c "
from src.knowledge_graph.extractor import EntityExtractor
e = EntityExtractor()
# Check that financial patterns are in pipeline
print([pipe[0] for pipe in e._nlp.pipeline])
"
# Should include 'entity_ruler'
```

### Issue: Hybrid search slower than expected

**Symptoms:**
- >5 second retrieval time
- Timeouts on complex queries

**Root Cause:**
Full hybrid search runs 6+ searches per query (3 variants × 2 search types: dense + BM25) plus KG lookup and reranking.

**Solution:**
- Reduce query expansion variants from 3 to 2 (reduces searches from 6 to 4)
- Reduce reranking candidates from 15 to 10
- Add caching for repeated queries (QueryExpander cache)
- Run dense and BM25 searches in parallel (asyncio.gather)
- Check Pinecone latency in dashboard

### Issue: Reranking returns unexpected scores

**Symptoms:**
- All scores are 5 (default)
- Scores don't correlate with relevance

**Solution:**
```bash
# Test reranker directly
docker-compose exec backend python -c "
from src.utils.reranker import CrossEncoderReranker
r = CrossEncoderReranker()
score = r.score_relevance('Apple risks', 'Apple faces supply chain risks in China')
print(f'Score: {score}')
"
# If always 5, check Nova Lite API response parsing
```

### Issue: Multi-tool query only uses one tool

**Symptoms:**
- SQL-worthy query only uses RAG
- RAG-worthy query only uses SQL

**Solution:**
- Review tool descriptions for clarity
- Check agent prompt includes tool selection guidance
- Test with explicit "use SQL for numbers, RAG for context" in query

### Issue: Bedrock rate limiting (ThrottlingException)

**Symptoms:**
- "ThrottlingException" errors during query expansion or reranking
- Intermittent failures on high-traffic queries

**Root Cause:**
Nova Lite has per-second rate limits. Full hybrid pipeline makes 4+ LLM calls per query (expansion + reranking + compression).

**Solution:**
Use the same exponential backoff pattern from Phase 2A VLM extraction. See `backend/src/ingestion/vlm_extractor.py` and `backend/src/utils/embeddings.py` for the retry implementation.

Also consider:
- Add LRU caching for query expansion (same queries return same variants)
- Reduce reranking candidates from 15 to 10
- Request quota increase via AWS Support if needed

### Issue: Pinecone hybrid search returns no results

**Symptoms:**
- Dense-only search works, hybrid returns nothing
- "sparse_values" errors

**Root Cause:**
Pinecone index must be configured for hybrid search at creation time.

**Solution:**
```bash
# Check index configuration
docker-compose exec backend python -c "
from pinecone import Pinecone
from src.config.settings import get_settings

settings = get_settings()
pc = Pinecone(api_key=settings.pinecone_api_key)
index = pc.Index(settings.pinecone_index_name)
print(index.describe_index_stats())
"

# If index doesn't support sparse, you need to:
# 1. Create new index with metric='dotproduct' and sparse_values enabled
# 2. Re-index all documents with both dense and sparse vectors
```

### Issue: Query expansion returns duplicate variants

**Symptoms:**
- Nova Lite returns same text for multiple variants
- Redundant searches waste time

**Solution:**
```python
def expand(self, query: str, num_variants: int = 3) -> list[str]:
    variants = [query]  # Always include original
    raw_variants = self._call_nova_lite(prompt)
    
    # Deduplicate and filter
    seen = {query.lower().strip()}
    for v in raw_variants:
        normalized = v.lower().strip()
        if normalized not in seen and len(v) > 10:
            seen.add(normalized)
            variants.append(v)
    
    # If not enough unique variants, return what we have
    return variants[:num_variants + 1]
```

### Issue: Neo4j memory exhaustion during entity indexing

**Symptoms:**
- Neo4j crashes during large document indexing
- "Java heap space" errors

**Solution:**
```yaml
# docker-compose.yml - increase Neo4j memory
neo4j:
  environment:
    - NEO4J_dbms_memory_heap_initial__size=512m
    - NEO4J_dbms_memory_heap_max__size=1G
    - NEO4J_dbms_memory_pagecache_size=512m
```

Also batch entity creation:
```python
# Process documents in batches of 100 entities
BATCH_SIZE = 100
for i in range(0, len(entities), BATCH_SIZE):
    batch = entities[i:i+BATCH_SIZE]
    store.batch_create_entities(batch)
```

### Issue: BM25 token hash collisions

**Symptoms:**
- Unrelated terms match unexpectedly
- Sparse search returns irrelevant results

**Root Cause:**
Python hash() can produce collisions when modded to 2^31.

**Solution:**
Use a better hash function:
```python
import hashlib

def hash_token(token: str) -> int:
    """Use SHA256 for collision-resistant hashing."""
    h = hashlib.sha256(token.encode()).hexdigest()
    return int(h[:8], 16)  # First 8 hex chars = 32 bits
```

---

## Best Practices & Performance Optimization

### 1. Async Patterns for Parallel Retrieval

The hybrid pipeline should run dense and BM25 searches in parallel:

```python
import asyncio

async def _parallel_search(self, query_variants: list[str]) -> dict:
    """Run dense and BM25 searches in parallel for all variants."""
    tasks = []
    
    for variant in query_variants:
        tasks.append(self._dense_search(variant, top_k=15))
        tasks.append(self._bm25_search(variant, top_k=15))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle any exceptions gracefully
    valid_results = [r for r in results if not isinstance(r, Exception)]
    return valid_results
```

### 2. Caching for Repeated Queries

Add LRU caching for expensive operations:

```python
from functools import lru_cache

class QueryExpander:
    @lru_cache(maxsize=100)
    def expand(self, query: str) -> tuple[str, ...]:
        """Cache query expansions (return tuple for hashability)."""
        variants = self._generate_variants(query)
        return tuple(variants)
```

### 3. Timeout Configuration

All external service calls should have configurable timeouts:

```python
# config/settings.py
class Settings(BaseSettings):
    # Timeouts (seconds)
    pinecone_timeout: float = 10.0
    neo4j_timeout: float = 5.0
    bedrock_timeout: float = 30.0
    
    # Retry configuration
    max_retries: int = 3
    retry_backoff_base: float = 2.0
```

### 4. Memory-Efficient Entity Extraction

For large documents, process pages in batches:

```python
def extract_from_document(self, extraction_json: dict, batch_size: int = 10) -> list[Entity]:
    """Extract entities with memory-efficient batching."""
    all_entities = []
    pages = extraction_json.get("pages", [])
    
    for i in range(0, len(pages), batch_size):
        batch = pages[i:i+batch_size]
        for page in batch:
            entities = self.extract_entities(
                page.get("text", ""),
                document_id=extraction_json.get("document_id"),
                page=page.get("page_number")
            )
            all_entities.extend(entities)
        
        # Allow garbage collection between batches
        import gc
        gc.collect()
    
    return all_entities
```

### 5. Graceful Fallback Chain

Implement fallback at each pipeline stage:

```
Full Pipeline → Dense+BM25 → Dense Only → Cached Results → Error Response

Priority order:
1. Try full hybrid (dense + BM25 + KG + reranking + compression)
2. If KG fails → continue with dense + BM25
3. If BM25 fails → continue with dense only
4. If reranking fails → use RRF scores directly
5. If compression fails → return full passages
6. If dense fails → return error (core requirement)
```

---

## Files Created/Modified in Phase 2b

### New Files Created

| File | Purpose |
|------|---------|
| `backend/src/knowledge_graph/__init__.py` | Knowledge Graph package |
| `backend/src/knowledge_graph/ontology.py` | Entity and relationship types |
| `backend/src/knowledge_graph/extractor.py` | spaCy entity extraction |
| `backend/src/knowledge_graph/store.py` | Neo4j connection and CRUD |
| `backend/src/knowledge_graph/queries.py` | Graph traversal queries |
| `backend/src/utils/bm25_encoder.py` | BM25 sparse vector encoding |
| `backend/src/utils/rrf.py` | Reciprocal Rank Fusion |
| `backend/src/utils/reranker.py` | Cross-encoder reranking |
| `backend/src/utils/compressor.py` | Contextual compression |
| `backend/src/ingestion/query_expansion.py` | Query expansion via Nova Lite |
| `backend/src/ingestion/hybrid_retriever.py` | Full hybrid retrieval pipeline |
| `scripts/index_entities.py` | Entity indexing script |

### Files Modified

| File | Changes |
|------|---------|
| `backend/src/agent/tools/rag.py` | Updated to use HybridRetriever, updated tool description |
| `backend/src/agent/tools/sql.py` | Updated tool description for better agent selection |
| `backend/src/utils/__init__.py` | Added exports: BM25Encoder, rrf_fusion, CrossEncoderReranker, ContextualCompressor |
| `backend/src/ingestion/__init__.py` | Added exports: QueryExpander, HybridRetriever |
| `scripts/extract_and_index.py` | Added --add-sparse flag for BM25 vectors |
| `REPO_STATE.md` | Updated file inventory |

### Neo4j Data Created

| Data Type | Approximate Count |
|-----------|-------------------|
| Entity nodes | 1,200+ |
| Document nodes | 11 |
| MENTIONS relationships | 4,500+ |

---

## Branch Management and Next Steps

### Save Phase 2b Work

**Commands:**
```bash
cd ~/Projects/aws-enterprise-agentic-ai

# Stage all changes
git add .

# Commit with descriptive message
git commit -m "Complete Phase 2b: Intelligence layer with Knowledge Graph and hybrid RAG

- Knowledge Graph with spaCy entity extraction
- Neo4j storage with 1200+ entities
- BM25 sparse vectors for hybrid search
- Query expansion via Nova Lite
- RRF fusion for multi-source results
- Cross-encoder reranking for precision
- Contextual compression for focused context
- Multi-tool orchestration (SQL + RAG)"

# Tag Phase 2b completion
git tag -a v0.5.0-phase2b -m "Phase 2b complete - Intelligence Layer"

# Push to remote
git push origin main
git push origin v0.5.0-phase2b
```

### Archive Phase 2 Guides

**Commands:**
```bash
# Move completed guides to archive
mv docs/PHASE_2B_HOW_TO_GUIDE.md docs/completed-phases/

git add docs/
git commit -m "Archive Phase 2 guides to completed-phases"
```

### Prepare for Phase 3

Phase 3 adds:
- **Arize Phoenix Tracing:** Observability for LLM calls
- **Trace Dashboard:** Visualize agent decisions
- **Performance Monitoring:** Track latency and token usage

**Create Phase 3 branch:**
```bash
git checkout -b phase-3-observability
```

---

## Summary

Phase 2b establishes the intelligence layer with:
- ✅ Knowledge Graph with spaCy entity extraction and Neo4j storage
- ✅ Advanced RAG with hybrid search (dense + BM25)
- ✅ Query expansion for improved recall
- ✅ RRF fusion for multi-source result merging
- ✅ Cross-encoder reranking for precision
- ✅ Contextual compression for focused context
- ✅ Multi-tool orchestration (SQL + RAG combined)

**Key Achievements:**
- Entity-based queries: "Find documents mentioning Tim Cook"
- Hybrid retrieval: 20-30% recall improvement over dense-only
- Reranking: 20-25% precision improvement
- Complex queries: "Apple's China revenue and risks" uses both tools

**Quality Improvements (Phase 2a → 2b):**
| Metric | Phase 2a (Dense) | Phase 2b (Hybrid) |
|--------|------------------|-------------------|
| Recall | Baseline | +20-30% |
| Precision | Baseline | +20-25% |
| Entity queries | Not supported | ✅ Supported |
| Multi-tool | Manual | ✅ Automatic |

**Next Phase (3):** Add observability:
- Arize Phoenix tracing
- LLM call visualization
- Performance dashboards

**Estimated Time for Phase 2b:** 6-10 hours

**Success Criteria:** ✅ Hybrid search returns better results than dense-only, Knowledge Graph enhances entity queries, multi-tool queries combine SQL and RAG seamlessly.
