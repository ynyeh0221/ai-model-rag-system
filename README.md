# AI Model Management RAG System

This repository contains a modular Retrieval-Augmented Generation (RAG) system for managing AI model scripts, associated metadata, and generated images. The system supports schema-based validation, vector-based retrieval, multi-modal querying, side-by-side model comparison, and Colab notebook generation.

## Features

- **Schema-Validated Document Processing**
  - Structured ingestion of code, image, and metadata documents
  - Multi-framework support (PyTorch, TensorFlow, etc.)

- **Vector-Based Retrieval**
  - Embedding generation for code, text, and images
  - Fast similarity search via Chroma and FAISS

- **Query Engine**
  - Natural language understanding using LangChain
  - Supports hybrid search (vector + keyword)
  - Intent classification and custom ranking strategies

- **Image Gallery and Search**
  - Searchable and filterable views of generated images
  - Supports tag-based filtering and generation parameter overlays

- **Model Comparison Tools**
  - Compare model architecture, training configs, and performance
  - Timeline view for model evolution

- **Notebook Generator**
  - Create and execute Colab notebooks for model inspection
  - Includes reproducibility tracking and resource usage logs

- **Prompt Studio**
  - Prompt template management with versioning and A/B testing
  - Git-style diffing and template performance analytics

- **User Interface**
  - Start from command line interface 
  - Built with React and Tailwind CSS
  - Monaco-based editor for code and prompts
  - Access control via JWT and RBAC

- **Monitoring and Analytics**
  - System performance tracking with Prometheus and Grafana
  - Query logging and analysis with Elasticsearch and Kibana

## Architecture Overview

The system is composed of the following components:

1. Document Processor
2. Vector Database Manager
3. Query Engine
4. Response Generator
5. Notebook Generator
6. Frontend UI
7. Monitoring & Analytics

## Technology Stack

| Category          | Tools / Libraries |
|-------------------|------------------|
| Language          | Python 3.9+, JavaScript (React) |
| Backend           | FastAPI / Flask |
| Frontend          | React, Tailwind CSS, Zustand |
| Vector Search     | ChromaDB, FAISS, SQLite |
| Embeddings        | SentenceTransformers, OpenCLIP |
| LLM Integration   | LangChain, LLaMA, Deepseek-r1 |
| Image Processing  | Pillow, OpenCLIP |
| Notebooks         | nbformat, Papermill, Google Colab API |
| Visualization     | Matplotlib, Plotly |
| Monitoring        | Prometheus, Grafana, OpenTelemetry |
| Logging           | Elasticsearch, Kibana |
| Access Control    | JWT, Role-Based Access Control (RBAC) |

## Getting Started

### Clone the Repository

```bash
git clone https://github.com/your-org/ai-model-management-rag.git
cd ai-model-management-rag
```

### Set Up the Backend Environment

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Start the Backend Server

```bash
uvicorn app.main:app --reload
```

### Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

## Repository Structure

- `document_processor/` – Code and image parsing, metadata extraction
- `schemas/` – Pydantic and JSON schema definitions
- `vector_db/` – Embedding generation, vector storage, hybrid search
- `query_engine/` – Query parsing, intent classification, result ranking
- `notebook_generator/` – Colab notebook creation and management
- `prompt_studio/` – Prompt templates, A/B testing, version control
- `ui/` – React-based user interface
- `monitoring/` – System metrics, logs, dashboards

## Example Use Cases

- Search: "Find all Transformer models trained on wikitext-103"
- Compare: "Compare Transformer V1 and V2 on accuracy and training parameters"
- Browse: "List all photorealistic images generated by Stable Diffusion V2"
- Generate: "Create a Colab notebook to evaluate Transformer V2"

## Evaluation Metrics

- Retrieval precision and recall
- Query latency and throughput
- Prompt effectiveness (conversion rates, response quality)
- Image search relevance
- System scalability and resource efficiency

## Security and Access

- Authentication via JWT
- Role-based access control (RBAC)
- Access logs and query tracking

## Roadmap Highlights

- Auto-generated model cards
- MLflow and Weights & Biases integration
- Model architecture visualization
- Federated search across repositories
- Prompt explainability and optimization tools

## Contributing

Contributions are welcome. Please ensure your changes include relevant tests and follow the existing code style.

```bash
# Run tests
pytest

# Format code
black . && isort .
```

Refer to [CONTRIBUTING.md](CONTRIBUTING.md) for full guidelines.

## License

This project is licensed under the MIT License.

## Contact

For questions, issues, or feature requests, please open an issue or contact the maintainers at [ynyeh0221@gmail.com](mailto:ynyeh0221@gmail.com).
```
