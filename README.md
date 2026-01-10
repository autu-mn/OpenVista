<div align="center">

# 🔮 OpenVista

### Multimodal Time-Series Prediction Platform for GitHub Repository Health

<img src="image/首页.png" alt="OpenVista Dashboard" width="800"/>

<br/>

[![Python](https://img.shields.io/badge/Python-3.8+-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18+-61dafb?style=for-the-badge&logo=react&logoColor=black)](https://reactjs.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-ee4c2c?style=for-the-badge&logo=pytorch&logoColor=white)](https://pytorch.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178c6?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)](LICENSE)

**[English](README.md)** · **[中文文档](README_CN.md)** · **[User Guide](使用指南（Q&A）.md)**

</div>

---

## 🌟 Overview

**OpenVista** is a next-generation platform for analyzing and predicting the health of open-source GitHub repositories. The platform integrates two core capabilities:

1. **🤖 MaxKB Intelligent Q&A System** — RAG-based knowledge base for project documentation
2. **🔮 GitPulse Multimodal Prediction Model** — Intelligent forecasting combining time-series and text

Together, these modules provide comprehensive analysis of open-source projects: past, present, and future.

### ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🤖 **MaxKB AI Q&A** | RAG-powered knowledge base Q&A for project documentation |
| 🔮 **GitPulse Prediction** | Time-series + text embeddings, forecasting up to 24 months |
| 📊 **CHAOSS Evaluation** | Community health assessment with 6-dimension radar visualization |
| 🔍 **Similar Repo Discovery** | Find related projects via GitHub API-based similarity matching |
| 📈 **Interactive Visualization** | Beautiful charts with 60+ months historical data comparison |
| ⚡ **Real-time Crawling** | Fetch any GitHub repository data on demand |

---

## 🤖 MaxKB Intelligent Q&A System

<div align="center">
<img src="image/MaxKB知识库.png" alt="MaxKB Knowledge Base" width="700"/>
</div>

### System Architecture

MaxKB is the **AI Q&A core** of OpenVista, using **RAG (Retrieval-Augmented Generation)** technology to enable natural language questions about any analyzed repository.

```
User Question → MaxKB Retrieves from Knowledge Base → LLM Generates Answer → Response
```

### Knowledge Base Contents

The system automatically builds a knowledge base for each analyzed repository:

| Document Type | Description |
|---------------|-------------|
| 📄 **README** | Project introduction, installation guide, usage instructions |
| 📜 **LICENSE** | Open source license information |
| 📁 **docs/** | All documents in the project's docs directory |
| 📊 **Project Summary** | AI-generated project analysis report |
| 🐛 **Issue Summary** | Aggregated issue data and classifications |

### Tech Stack & Tools

| Component | Tool/Technology | Description |
|-----------|-----------------|-------------|
| **Knowledge Base Platform** | [MaxKB](https://github.com/1Panel-dev/MaxKB) | Open-source RAG knowledge base system |
| **Deployment** | Docker Compose | One-click deployment with data persistence |
| **Vector Database** | PostgreSQL + pgvector | Efficient vector similarity search |
| **LLM Backend** | Configurable (DeepSeek/OpenAI etc.) | Supports multiple LLM providers |

### Deployment & Configuration

#### Option 1: Use Pre-configured Knowledge Base (Recommended)

```bash
cd maxkb-export

# One-click install (includes database backup restoration)
chmod +x install.sh
./install.sh
```

The installation script will automatically:
- Pull MaxKB Docker image
- Create data volumes and restore pre-configured data
- Start service at `http://localhost:8080`

#### Option 2: Fresh Installation

```bash
# Start with Docker Compose
docker-compose -f docker-compose.maxkb.yml up -d
```

#### Configure .env File

```env
# MaxKB Service Configuration
MAXKB_URL=http://localhost:8080
MAXKB_USERNAME=admin
MAXKB_PASSWORD=your_password
MAXKB_KNOWLEDGE_ID=your_knowledge_id

# MaxKB AI API (for Q&A)
MAXKB_AI_URL=http://localhost:8080/api/application/{app_id}/chat/completions
MAXKB_API_KEY=your_maxkb_api_key
```

### Usage

1. **Automatic Document Upload**: Documents are automatically uploaded to MaxKB during repository crawling
2. **Intelligent Q&A**: Ask questions in the platform's AI Q&A module
3. **Prediction Explanations**: MaxKB generates interpretability analysis for predictions

<div align="center">
<img src="image/Agent.png" alt="AI Agent" width="600"/>
</div>

---

## 🔬 GitPulse Prediction Model

<div align="center">
<img src="image/时序与文本的结合效果.png" alt="GitPulse Model Effect" width="700"/>
</div>

### Model Overview

**GitPulse** is OpenVista's core multimodal time-series prediction model, capable of simultaneously forecasting 16 OpenDigger metrics.

### Model Performance

<div align="center">

| Metric | Value | Description |
|:------:|:-----:|:------------|
| **MSE** | 0.0886 | Mean Squared Error (lower is better) |
| **R²** | 0.70 | Coefficient of Determination |
| **DA** | 67.28% | Directional Accuracy |

</div>

<details>
<summary>📊 Click to see performance comparison chart</summary>

<div align="center">
<img src="image/不同方法在测试集上的性能对比.png" alt="Performance Comparison" width="700"/>
</div>

</details>

### Architecture Highlights

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Time-Series Encoder** | Conditional GRU | Captures temporal patterns across 16 metrics |
| **Text Encoder** | DistilBERT | Extracts features from project descriptions, issues |
| **Fusion Layer** | Multimodal Fusion | Combines time-series and text information |
| **Prediction Head** | MLP | Outputs predictions for 12-24 months ahead |

### Why Multimodal?

Text information (Issues, README, Commits) provides context that pure time-series models miss:
- 📢 Upcoming features or breaking changes
- 💬 Community discussions and sentiment
- 🗺️ Project roadmap and priorities

### Supported Metrics (16 total)

| Category | Metrics |
|----------|---------|
| **Popularity** | OpenRank, Stars, Forks, Attention |
| **Activity** | Activity, Participants, New Contributors |
| **Contributors** | Contributors, Inactive Contributors, Bus Factor |
| **Issues** | New Issues, Closed Issues, Issue Comments |
| **Pull Requests** | Change Requests, PR Accepted, PR Reviews |

### Training Your Own Model

```bash
cd get-dataset

# Generate dataset (default: 10,000 repos)
python generate_training_dataset.py --count 10000

# Resume from interruption
python generate_training_dataset.py --resume
```

See [get-dataset/README.md](get-dataset/README.md) for detailed options.

---

## 🛠️ Tech Stack

<div align="center">
<img src="image/技术架构.png" alt="Tech Architecture" width="700"/>
</div>

<table>
<tr>
<td width="50%">

### Backend
- **Framework**: Flask (Python)
- **Deep Learning**: PyTorch 2.0+
- **NLP**: Transformers (DistilBERT)
- **Data Processing**: Pandas, NumPy

</td>
<td width="50%">

### Frontend
- **Framework**: React 18+ with TypeScript
- **Styling**: Tailwind CSS
- **Charts**: Recharts + Custom SVG
- **Animation**: Framer Motion

</td>
</tr>
<tr>
<td>

### AI & Knowledge Base
- **RAG System**: MaxKB
- **LLM Backup**: DeepSeek API
- **Text Encoding**: DistilBERT

</td>
<td>

### Data Sources
- **GitHub API**: Issues, PRs, Commits
- **OpenDigger**: 16 time-series metrics

</td>
</tr>
</table>

---

## 📁 Project Structure

```
OpenVista/
├── 🔧 backend/                     # Flask Backend
│   ├── Agent/                      # AI & MaxKB Integration
│   │   ├── maxkb_client.py         # MaxKB Knowledge Base Client
│   │   ├── prediction_explainer.py # AI Prediction Explainer
│   │   └── qa_agent.py             # Intelligent Q&A Agent
│   │
│   ├── DataProcessor/              # Data Crawling & Processing
│   │   ├── crawl_monthly_data.py   # Main Crawler Entry
│   │   ├── github_text_crawler.py  # GitHub Text Crawler
│   │   ├── maxkb_uploader.py       # MaxKB Document Uploader
│   │   └── monthly_crawler.py      # OpenDigger Data Crawler
│   │
│   ├── GitPulse/                   # GitPulse Prediction Model
│   │   ├── model.py                # Model Architecture
│   │   ├── prediction_service.py   # Prediction Service
│   │   └── gitpulse_weights.pt     # Trained Model Weights (LFS)
│   │
│   ├── CHAOSSEvaluation/           # Community Health Scoring
│   │   └── chaoss_calculator.py    # CHAOSS Metric Calculator
│   │
│   └── app.py                      # Flask API Entry Point
│
├── 🎨 frontend/                    # React Frontend
│
├── 📊 get-dataset/                 # Training Dataset Generator
│
├── 🐳 maxkb-export/                # MaxKB Deployment Config
│   ├── install.sh                  # One-click Install Script
│   ├── docker-compose.yml          # Docker Compose File
│   └── db/                         # Database Backup
│
└── 📄 README.md
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Node.js 16+
- Docker (for MaxKB)
- Git LFS (for model weights)

### 1️⃣ Clone & Setup

```bash
# Clone the repository
git clone https://github.com/your-username/OpenVista.git
cd OpenVista

# Initialize Git LFS and pull model weights
# Windows:
setup.bat
# Linux/Mac:
chmod +x setup.sh && ./setup.sh
```

### 2️⃣ Deploy MaxKB (Optional but Recommended)

```bash
cd maxkb-export
chmod +x install.sh
./install.sh
```

Visit `http://localhost:8080` to verify MaxKB is running.

### 3️⃣ Environment Configuration

Create a `.env` file in the project root:

```env
# Required: GitHub API Token
GITHUB_TOKEN=your_github_token

# MaxKB Configuration (if deployed)
MAXKB_URL=http://localhost:8080
MAXKB_USERNAME=admin
MAXKB_PASSWORD=your_password
MAXKB_KNOWLEDGE_ID=your_knowledge_id
MAXKB_AI_URL=http://localhost:8080/api/application/{app_id}/chat/completions
MAXKB_API_KEY=your_maxkb_api_key

# Optional: DeepSeek as LLM backup
DEEPSEEK_API_KEY=your_deepseek_key
```

### 4️⃣ Install Dependencies

```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### 5️⃣ Launch Services

```bash
# Terminal 1: Start Backend (port 5000)
cd backend
python app.py

# Terminal 2: Start Frontend (port 3000)
cd frontend
npm run dev
```

### 6️⃣ Access the Platform

Open your browser and navigate to **http://localhost:3000**

---

## 📖 Usage Guide

### Basic Workflow

1. **🔍 Search Repository** — Enter `owner/repo` (e.g., `facebook/react`)
2. **⏳ Wait for Crawling** — Data fetched from GitHub API & OpenDigger
3. **📊 Explore Analytics** — View time-series charts, Issue analysis
4. **🔮 Check Predictions** — See 12-month forecasts with AI explanations
5. **📈 CHAOSS Evaluation** — Assess community health scores
6. **🤖 AI Q&A** — Use MaxKB to ask questions about the repository

---

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- [MaxKB](https://github.com/1Panel-dev/MaxKB) — RAG Knowledge Base System
- [OpenDigger](https://github.com/X-lab2017/open-digger) — Time-series metrics data
- [CHAOSS](https://chaoss.community/) — Community health metrics framework
- [GitHub API](https://docs.github.com/en/rest) — Repository data source

---

<div align="center">

### ⭐ Star this repo if you find it useful! ⭐

<br/>

**Made with ❤️ by the OpenVista Team**

*Empowering open-source with predictive intelligence*

</div>
