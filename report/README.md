# Report

B.Tech Project report for MPCS and LocalKG (Aurindum Banerjee, B23CS1006; Lokesh Motwani, B23CS1033).

```
report/
  BTP_Report.tex        Report source (single column, A4, 12 pt, TeX Gyre Pagella)
  BTP_Report.pdf        Compiled report
  figures/
    ui_pipeline.png     Interface screenshot used in Chapter 8
    legacy/             Figures from the earlier technical report (reference only)
  legacy/               Earlier two-column technical report (tex, md)
```

All diagrams and charts are drawn in the .tex file with TikZ and pgfplots, so the
numbers in the charts come straight from the tables. Benchmark values are taken
from `docs/benchmark_indexing_tide.json`.

Build (run twice for the table of contents):

```
pdflatex BTP_Report.tex
pdflatex BTP_Report.tex
```
