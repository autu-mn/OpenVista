---
license: apache-2.0
language:
- en
library_name: pytorch
tags:
- time-series
- multimodal
- transformer
- github
- forecasting
datasets:
- custom
metrics:
- mse
- mae
- r_squared
pipeline_tag: time-series-forecasting
---

# GitPulse: Multimodal Time Series Prediction for GitHub Project Health

GitPulse is a multimodal Transformer-based model that combines project text descriptions with historical activity data to predict GitHub project health metrics.

## Model Description

GitPulse leverages both **textual metadata** (project descriptions, topics) and **historical time series** (commits, issues, stars, etc.) to forecast future project activity. The key innovation is the adaptive fusion mechanism that dynamically balances text and time-series features.

### Architecture

- **Text Encoder**: DistilBERT-based encoder with attention pooling
- **Time Series Encoder**: Transformer encoder with positional embeddings  
- **Adaptive Fusion**: Dynamic gating mechanism for multimodal fusion
- **Prediction Head**: MLP for generating future predictions

### Model Parameters

| Parameter | Value |
|-----------|-------|
| d_model | 128 |
| n_heads | 4 |
| n_layers | 2 |
| hist_len | 128 |
| pred_len | 32 |
| n_vars | 16 |

## Performance

Evaluated on 636 test samples from 4,232 GitHub projects:

| Model | MSE ↓ | MAE ↓ | R² ↑ | DA ↑ | TA@0.2 ↑ |
|-------|-------|-------|------|------|----------|
| **GitPulse** | **0.0755** | **0.1094** | **0.7559** | **86.68%** | **81.60%** |
| CondGRU+Text | 0.0915 | 0.1204 | 0.7043 | 84.05% | 80.14% |
| Transformer | 0.1142 | 0.1342 | 0.6312 | 84.02% | 78.87% |
| LSTM | 0.2142 | 0.1914 | 0.3800 | 56.00% | 75.00% |

### Text Contribution

| Architecture | TS-Only R² | +Text R² | Improvement |
|--------------|-----------|----------|-------------|
| Transformer → GitPulse | 0.6312 | 0.7559 | **+19.8%** |
| CondGRU → CondGRU+Text | 0.3328 | 0.7043 | **+111.6%** |

## Usage

### Installation

```bash
pip install torch transformers
```

### Quick Start

```python
import torch
from transformers import DistilBertTokenizer

# Load model
from model import GitPulseModel
model = GitPulseModel.from_pretrained('./')

# Prepare inputs
tokenizer = DistilBertTokenizer.from_pretrained('distilbert-base-uncased')
text = "A Python library for machine learning"
encoded = tokenizer(text, padding='max_length', truncation=True, 
                    max_length=128, return_tensors='pt')

# Time series: [batch, hist_len, n_vars]
time_series = torch.randn(1, 128, 16)

# Predict
model.eval()
with torch.no_grad():
    predictions = model(
        time_series,
        input_ids=encoded['input_ids'],
        attention_mask=encoded['attention_mask']
    )
# predictions shape: [1, 32, 16]
```

### Inference API

```python
# Simple prediction interface
predictions = model.predict(
    time_series=history_data,  # [batch, 128, 16]
    text="Project description...",
    tokenizer=tokenizer
)
```

## Training Details

- **Dataset**: GitHub project activity data (4,232 projects)
- **Train/Val/Test Split**: 70% / 15% / 15%
- **Optimizer**: AdamW (lr=1e-5, weight_decay=0.01)
- **Fine-tuning Strategy**: Freeze encoder, train prediction head
- **Hardware**: NVIDIA RTX GPU

## Input Features (16 variables)

1. Commits count
2. Issues opened
3. Issues closed  
4. Pull requests opened
5. Pull requests merged
6. Stars gained
7. Forks count
8. Contributors count
9. Code additions
10. Code deletions
11. Comments count
12. Releases count
13. Wiki updates
14. Discussions count
15. Sponsors count
16. Watchers count

## Limitations

- Trained on English project descriptions only
- Best suited for projects with at least 128 months of history
- Performance may vary for niche domains not well represented in training

## Citation

```bibtex
@article{gitpulse2024,
  title={GitPulse: Multimodal Time Series Prediction for GitHub Project Health},
  author={Anonymous},
  journal={arXiv preprint},
  year={2024}
}
```

## License

Apache 2.0
