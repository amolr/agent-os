# arXiv Submission Guide for EMK Paper

## Quick Start

The paper is **ready for arXiv submission**. All files are in:
```
/papers/arxiv_submissions/01-emk/
```

## Files to Upload

Upload these files to arXiv:

1. ✅ `main.tex` (LaTeX source, 18 KB)
2. ✅ `references.bib` (Bibliography, 4.9 KB)
3. ✅ `fig1_architecture.pdf` (13 KB)
4. ✅ `fig2_benchmarks.pdf` (28 KB)
5. ✅ `fig3_throughput.pdf` (24 KB)
6. ✅ `fig4_baseline_comparison.pdf` (24 KB)
7. ✅ `fig5_schema.pdf` (27 KB)

**Total**: ~140 KB (well under arXiv limits)

## Submission Metadata

Copy this information when submitting to arXiv:

### Title
```
EMK: Episodic Memory Kernel - A Minimalist Storage Primitive for AI Agent Experience
```

### Authors
```
Imran Siddique (Microsoft)
```

### Abstract
```
We present EMK (Episodic Memory Kernel), a lightweight, immutable storage layer for AI agent experiences. As autonomous agents become increasingly prevalent, the need for structured, queryable memory of past actions and outcomes becomes critical. EMK provides a minimalist yet powerful primitive that captures the complete agent experience cycle—Goal → Action → Result → Reflection—in an append-only ledger with O(1) write complexity and O(n) retrieval with optional vector similarity search. We demonstrate that EMK achieves 0.036ms episode creation latency (27,694 ops/sec) and 652 write ops/sec throughput while maintaining full audit trails, making it suitable for production agent systems. Unlike existing agent memory systems that conflate storage with summarization, EMK provides a clean separation of concerns, enabling higher-level memory architectures to be built on a solid foundation.
```

### Primary Category
```
cs.AI (Artificial Intelligence)
```

### Cross-list Categories
```
cs.SE (Software Engineering)
cs.DB (Databases)
```

### Comments
```
Part of the Agent OS project: https://github.com/imran-siddique/agent-os. Code available at: https://github.com/imran-siddique/emk. 10 pages, 5 figures.
```

### License
```
CC BY 4.0
```

### MSC/ACM Classes (optional)
```
I.2.11 Distributed Artificial Intelligence
H.3.4 Systems and Software
D.2.11 Software Architectures
```

## Step-by-Step Submission

1. **Go to** https://arxiv.org/submit

2. **Select "New Submission"**

3. **Upload files**:
   - Either upload a .tar.gz of the directory
   - Or upload individual files (main.tex, references.bib, all PDFs)

4. **Process files**:
   - arXiv will compile the LaTeX
   - Verify the generated PDF looks correct

5. **Enter metadata**:
   - Copy the title, authors, abstract from above
   - Select cs.AI as primary category
   - Add cs.SE and cs.DB as cross-lists

6. **Add comments**:
   - Include the GitHub links
   - Mention "Part of Agent OS project"

7. **Select license**: CC BY 4.0

8. **Preview**:
   - Download and review the generated PDF
   - Should be ~10 pages with 5 figures

9. **Submit**:
   - If everything looks good, submit!
   - You'll get an arXiv ID (e.g., arXiv:2602.XXXXX)

## After Submission

1. **Update papers**: Once you get the arXiv ID, update references in other Agent OS papers to cite this one

2. **Share**: 
   - Tweet/post about the paper
   - Add to Agent OS README
   - Link from EMK documentation

3. **Conference submission**: Consider submitting to:
   - NeurIPS 2026 (Datasets & Benchmarks Track)
   - EMNLP 2026 (System Demonstrations)
   - ICLR 2027
   - ACL 2026

## Common Issues & Solutions

### LaTeX Compilation Fails
- arXiv sometimes has different package versions
- If it fails, check the log and remove problematic packages
- We've used standard packages that should work

### Figures Not Showing
- All figures are PDFs (arXiv-friendly format)
- Figures are in root directory (no subdirectories)
- Should work fine

### Bibliography Issues
- We use natbib (standard for arXiv)
- All references are real and verifiable
- Should compile cleanly

## Contact

If you have issues, the arXiv help is very responsive:
- help@arxiv.org

## Alternative: Create Tarball

If you prefer to upload a single file:

```bash
cd /home/runner/work/agent-os/agent-os/papers/arxiv_submissions/01-emk
tar -czf emk-submission.tar.gz *.tex *.bib *.pdf
```

Then upload `emk-submission.tar.gz` to arXiv.

## Verification Checklist

Before submitting, verify:

- [x] Title is correct and professional
- [x] Author name and affiliation are correct
- [x] Abstract is clear and compelling
- [x] All figures appear in the PDF
- [x] All references are properly formatted
- [x] No typos in key equations or code
- [x] GitHub links work
- [x] License is CC BY 4.0
- [x] No confidential or sensitive information

## Expected Timeline

- **Submission**: Immediate (ready now)
- **Processing**: 1-2 business days
- **Announcement**: Next Monday (if submitted by Thursday)
- **Public**: Immediately after announcement

Good luck with the submission! 🎉
