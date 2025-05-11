
# Mnemosyne

**Mnemosyne** is an autonomous knowledge extraction and continual learning system inspired by the Greek goddess of memory. The project uses large language models (LLMs) and knowledge graphs to analyze text, build structured ontologies, identify testable hypotheses, and iteratively evolve its understanding as new information arrives.

## 🌟 Project Vision

- **Text to Knowledge**: Automatically extract facts, entities, and relationships from text corpora.
- **Knowledge Graph Construction**: Store information in a structured, queryable format.
- **Hypothesis Generation**: Suggest missing links or contradictions for verification.
- **Autonomous Learning Loop**: Use new documents to verify hypotheses and expand the graph.

## 💻 Current Status

- Building prototype cluster using low-power motherboards (Intel i5-7400T, 16GB RAM per node)
- Wikipedia dump as primary data source
- LLM-based triple extraction to Neo4j
- Roadmap for distributed agent system

## 🚧 Roadmap

### Phase 1: Foundation
- Download Wikipedia dump
- Extract article content with `wikiextractor`
- Chunk and preprocess documents
- Extract (subject, relation, object) triples using GPT-4 Turbo

### Phase 2: Ontology Building + Gap Detection
- Store triples in Neo4j
- Apply reasoning queries to detect gaps and conflicts
- Identify unverified relationships

### Phase 3: Hypothesis Generation
- Use LLM to propose testable hypotheses
- Rank hypotheses for document retrieval

### Phase 4: Iterative Learning
- Retrieve documents for hypothesis verification
- Continually update knowledge graph

### Phase 5: Scale and Optimize
- Add local small model inference (e.g., LLaMA 3, Mistral)
- Parallel agent-based processing across cluster nodes

## 🔧 Tools

- Python + LangChain
- Neo4j Graph Database
- OpenAI GPT-4 Turbo (API)
- Wikipedia dataset + wikiextractor
- Cluster deployment for parallelism

## 🪄 Logo & Branding Ideas

- Stylized Greek column + neural network motif
- Mnemosyne name in ancient script font
- Knowledge tree with nodes resembling neural connections

## 🤖 Project Slogan

*"Memory. Knowledge. Continuity."*

---
