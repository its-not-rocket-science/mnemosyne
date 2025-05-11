# Mnemosyne Project - Next Steps

This document outlines the suggested next actions to move from planning to working prototype.

## ✅ Phase 0: Environment Setup

- Set up GitHub repository and push starter package
- Set up shared `.env` file per node
- Install Python 3.9+ and all packages from `requirements.txt` on all nodes
- Test cluster networking between CPU nodes and GPU node

## ✅ Phase 1: Data Ingestion + Parsing

- Download Wikipedia dump from https://dumps.wikimedia.org
- Extract articles using `wikiextractor`
- Distribute dataset across CPU nodes
- Write document parsing + cleaning scripts

## ✅ Phase 2: LLM Knowledge Extraction

- Install `llama.cpp` and/or `Ollama` on GPU node
- Download + convert quantized Mistral 7B or LLaMA 3 8B model to gguf format
- Write script to send document chunks to LLM and extract (subject, relation, object) triples
- Test batch inference performance

## ✅ Phase 3: Knowledge Graph Construction

- Install Neo4j Community Edition on CPU Node 3 (or central server)
- Write graph builder module to insert triples into Neo4j
- Visualize initial knowledge graph with Neo4j Bloom or Cypher queries

## ✅ Phase 4: Reasoning + Gap Detection

- Implement LangChain or LangGraph agent to query Neo4j
- Identify disconnected nodes, missing links, or contradictions
- Generate next information needs list

## ✅ Phase 5: Iterative Autonomous Learning Loop

- Automate document retrieval based on hypotheses
- Feed documents into pipeline → extract → update graph
- Create fully autonomous continual knowledge agent

## 🎯 Stretch Goals

- Experiment with TinyLLaMA and Phi-3 on CPU nodes
- Test inference acceleration with vLLM on GPU node
- Add Ray or multiprocessing for workload distribution
- Containerize with Docker for easy deployment

## 🚀 Your Outcome

By following these steps, you will create a fully local, autonomous knowledge extraction system using:
- Distributed CPU cluster for preprocessing + graph management
- GPU node for high-quality local LLM inference
- Neo4j knowledge graph + reasoning agent for autonomous learning

---

You are building one of the world's first open-source autonomous knowledge discovery clusters on low-power hardware. 🚀