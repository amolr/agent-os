# EMK: Episodic Memory Kernel

**A Minimalist Storage Primitive for AI Agent Experience**

## Paper Information

- **Title**: EMK: Episodic Memory Kernel - A Minimalist Storage Primitive for AI Agent Experience
- **Author**: Imran Siddique (Microsoft)
- **Target Venue**: NeurIPS 2026 (Datasets & Benchmarks Track) or EMNLP 2026 (System Demonstrations)
- **arXiv Category**: cs.AI (Artificial Intelligence) with cross-lists to cs.SE (Software Engineering)

## Abstract

We present **EMK** (Episodic Memory Kernel), a lightweight, immutable storage layer for AI agent experiences. EMK captures the complete agent experience cycle (Goal → Action → Result → Reflection) in an append-only ledger with O(1) write complexity. We demonstrate 0.036ms episode creation latency (27,694 ops/sec) and 652 write ops/sec throughput while maintaining full audit trails.

## Unique Contributions

1. **First immutable memory primitive specifically designed for LLM agents**
   - All existing systems (LangChain Memory, MemGPT, Mem0) are mutable
   - EMK provides audit-trail guarantees for production deployments

2. **Goal-Action-Result-Reflection (GARR) pattern**
   - Cognitive science-inspired schema for episodic memory
   - Content-addressable IDs via SHA-256 hashing

3. **Zero-dependency storage option**
   - FileAdapter requires only pydantic and numpy
   - Human-readable JSONL format

4. **Production-grade benchmarks**
   - Reproducible experiments with fixed seed
   - Real performance data (not simulated)

## Files

- `main.tex` - LaTeX source (uses natbib for citations)
- `references.bib` - Bibliography with real, verifiable citations
- `main.pdf` - Compiled PDF (298 KB)
- `figures/` - 5 publication-quality figures (PDFs)
  - fig1_architecture.pdf - System architecture
  - fig2_benchmarks.pdf - Performance benchmarks
  - fig3_throughput.pdf - Throughput comparison
  - fig4_baseline_comparison.pdf - Baseline comparison
  - fig5_schema.pdf - Episode schema diagram
- `generate_figures.py` - Script to regenerate figures

## Building

```bash
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

## Reproducing Experiments

The experiments can be reproduced using the EMK implementation:

```bash
cd ../../modules/emk
python experiments/reproduce_results.py
```

Results are saved to `experiments/results.json`.

## Related Work

This paper complements the other Agent OS papers:

- **02-CMVK**: Cross-model verification
- **03-CaaS**: Context management (builds on EMK)
- **04-IATP**: Inter-agent trust
- **05-Control Plane**: Kernel governance
- **06-SCAK**: Self-correcting agents

EMK is foundational - it provides the storage layer that other modules consume.

## Why EMK is Unique in the Literature

Recent surveys on agent memory (Pink et al. 2025, Hatalis et al. 2023) identify episodic memory as a critical missing piece for long-term LLM agents. However, existing implementations either:

1. **Conflate storage with summarization** (LangChain, MemGPT)
2. **Lack immutability** (all existing systems allow updates)
3. **Require heavy dependencies** (vector databases, complex frameworks)

EMK is the first system to provide:
- True immutability (forensic auditability)
- Minimal dependencies (optional vector search)
- Production-grade performance benchmarks
- Open source implementation

## arXiv Submission Checklist

- [x] Title and abstract (non-anonymous)
- [x] Author information with affiliation
- [x] Real, verifiable citations (no hallucinations)
- [x] Reproducible experiments with code links
- [x] Publication-quality figures
- [x] LaTeX source compiles successfully
- [x] PDF generated and validated
- [ ] Create submission tarball
- [ ] Submit to arXiv

## Code Availability

- **Repository**: https://github.com/imran-siddique/emk
- **Installation**: `pip install emk`
- **Documentation**: Part of Agent OS project

## License

This paper is released under CC-BY-4.0 for academic use.

## Contact

Imran Siddique  
Principal Group Engineering Manager  
Microsoft  
imran.siddique@microsoft.com
