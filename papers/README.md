# Agent OS Research Papers

> Academic research supporting the Agent OS kernel architecture.

## Quick Links

| Document | Description | Status |
|----------|-------------|--------|
| [EMK Paper](01-emk/) | **NEW** Episodic Memory Kernel | ✅ arXiv Ready |
| [ASPLOS 2026 Submission](05-control-plane/) | Main kernel paper | arXiv Ready |
| [RFC-001: IATP](../docs/rfcs/RFC-001-IATP.md) | Trust protocol spec | Draft |
| [RFC-002: Agent VFS](../docs/rfcs/RFC-002-Agent-VFS.md) | Filesystem spec | Draft |
| [Benchmarks](../docs/benchmarks/) | Reproducibility data | Complete |

## Paper Portfolio

The papers form a coherent research narrative, building from primitives to a complete kernel:

| # | Paper | Component | Target Venue | Status |
|---|-------|-----------|--------------|--------|
| 0 | **EMK** | Episodic Memory Kernel | NeurIPS 2026 / EMNLP 2026 | ✅ arXiv Ready |
| 1 | **Agent Primitives** | Base failure types | Technical Report | Draft |
| 2 | **CMVK** | Cross-Model Verification Kernel | NeurIPS 2026 | arXiv Ready |
| 3 | **CaaS** | Context-as-a-Service | EMNLP 2026 | arXiv Ready |
| 4 | **IATP** | Inter-Agent Trust Protocol | IEEE S&P | arXiv Ready |
| 5 | **Control Plane** | Deterministic Governance Kernel | ASPLOS 2026 | arXiv Ready |
| 6 | **SCAK** | Self-Correcting Agent Kernel | NeurIPS 2026 | arXiv Ready |

## Dependency Graph

```
                    ┌──────────────┐
                    │ 01-Primitives│
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┬────────────┐
              │            │            │            │
              ▼            ▼            ▼            ▼
        ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
        │ 00-EMK  │  │ 02-CMVK │  │ 03-CaaS │  │ 04-IATP │
        │(Storage)│  │         │  │  (uses  │  │         │
        └────┬────┘  └────┬────┘  │   EMK)  │  └────┬────┘
             │            │        └────┬────┘       │
             │            │             │            │
             └────────────┴─────────────┼────────────┘
                                        │
                                        ▼
                              ┌─────────────────┐
                              │05-Control Plane │
                              └────────┬────────┘
                                       │
                                       ▼
                                 ┌──────────┐
                                 │ 06-SCAK  │
                                 └──────────┘
```

## Cross-References

Each paper cites and builds upon the previous work:

- **EMK** provides immutable storage primitive → used by **CaaS** for episodic memory
- **CMVK** introduces adversarial verification → used by **Control Plane** for policy checks
- **CaaS** provides context management (built on EMK) → used by **SCAK** for semantic memory
- **IATP** defines trust protocols → used by **Control Plane** for inter-agent governance
- **Control Plane** provides the kernel → extended by **SCAK** for self-correction

## Author Information

**Imran Siddique**  
Principal Group Engineering Manager  
Microsoft  
Email: imran.siddique@microsoft.com

## Building Papers

Each paper has its own build script:

```bash
# Build all papers
for dir in papers/*/; do
    if [ -f "$dir/build.sh" ]; then
        (cd "$dir" && ./build.sh)
    fi
done

# Or build individually
cd papers/06-scak
pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex
```

## arXiv Submission

All papers are prepared for arXiv submission:

1. Non-anonymous author information
2. Correct citations to real, published work
3. Reproducible experiments with code links
4. Proper acknowledgments

## License

All papers are released under CC-BY-4.0 for academic use.
