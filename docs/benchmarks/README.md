# Benchmark Reproduction Package

> Reproducibility data for Agent OS research papers.

## Overview

This directory contains all benchmarks referenced in Agent OS papers, with full reproducibility instructions.

## Available Benchmarks

| Benchmark | Paper | Location | Status |
|-----------|-------|----------|--------|
| CMVK Accuracy | NeurIPS 2026 | [`cmvk-benchmarks.md`](cmvk-benchmarks.md) | Complete |
| AMB Throughput | ASPLOS 2026 | [`amb-benchmarks.md`](amb-benchmarks.md) | Complete |
| Kernel Latency | ASPLOS 2026 | [`kernel-benchmarks.md`](kernel-benchmarks.md) | Planned |
| IATP Trust Verification | IEEE S&P | [`iatp-benchmarks.md`](iatp-benchmarks.md) | Planned |

## Quick Reproduction

```bash
# Clone the repository
git clone https://github.com/imran-siddique/agent-os.git
cd agent-os

# Install dependencies
pip install -e ".[dev,benchmark]"

# Run all benchmarks
python -m agent_os.benchmarks.run_all

# Run specific benchmark
python -m agent_os.benchmarks.cmvk --output results/cmvk.json
python -m agent_os.benchmarks.amb --output results/amb.json
```

## Key Results

### CMVK: Cross-Model Verification

| Configuration | Detection Rate | False Positives | Latency |
|--------------|---------------|-----------------|---------|
| Single Model (GPT-4) | 68% | 12% | 2.1s |
| Single Model (Claude) | 72% | 10% | 1.8s |
| **CMVK (3 models)** | **96%** | **4%** | **4.5s** |

**Conclusion:** 28% accuracy improvement with 2.5x latency increase.

### AMB: Message Bus Throughput

| Adapter | Throughput | p99 Latency | Durability |
|---------|------------|-------------|------------|
| InMemory | 50K msg/s | 0.5ms | No |
| Redis | 80K msg/s | 8ms | Yes |
| RabbitMQ | 40K msg/s | 25ms | Yes |
| Kafka | 200K+ msg/s | 50ms | Yes |

**Conclusion:** Scales from dev (InMemory) to production (Kafka) transparently.

### Kernel: Policy Enforcement

| Metric | Target | Achieved |
|--------|--------|----------|
| Violation Rate | 0% | 0% |
| Policy Latency (p50) | <5ms | 2.3ms |
| Policy Latency (p99) | <10ms | 4.8ms |
| Kernel Overhead | <5% | 3.2% |

**Conclusion:** Deterministic enforcement with minimal overhead.

## Environment

All benchmarks were run on:

```
Cloud: AWS EC2
Instance: c5.xlarge (4 vCPU, 8GB RAM)
OS: Ubuntu 22.04 LTS
Python: 3.11.4
Network: Same VPC, <1ms latency
```

## Reproducing Paper Figures

Each paper directory contains figure generation scripts:

```bash
# CMVK paper figures
cd papers/02-cmvk
python generate_figures.py --output figures/

# Control Plane paper figures
cd papers/05-control-plane
python generate_figures.py --output figures/
```

## Data Sets

| Dataset | Size | Description | Location |
|---------|------|-------------|----------|
| HDB-60 | 60 samples | Hallucination detection | `data/hdb-60.json` |
| CCFD-100 | 100 projects | Carbon credit fraud | `data/ccfd-100.json` |
| FTV-200 | 200 trades | Financial verification | `data/ftv-200.json` |

## Citation

If you use these benchmarks, please cite:

```bibtex
@inproceedings{siddique2026agentos,
  title={Agent OS: A Kernel for Autonomous AI Agents},
  author={Siddique, Imran},
  booktitle={ASPLOS 2026},
  year={2026}
}
```

## License

Benchmark code: MIT  
Datasets: CC-BY-4.0
