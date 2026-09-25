# Demo data for the case-study screenshots

**Both papers in this folder are fictional.** Every author, institution, participant, number,
result and reference in them was invented to demonstrate the ResearchForge interface. Each
paper says so in a banner on its first line. The model's output quotes that banner back.

| File | Uploaded as | Pages / characters extracted |
|---|---|---|
| `fictional_paper_1_spaced_retrieval.html` | `Voss_Okafor_Spaced_Retrieval_DEMO.pdf` | 3 / 7,393 |
| `fictional_paper_2_peer_circles.html` | `ReyesLind_Peer_Circles_DEMO.pdf` | 3 / 6,057 |

The two papers share a topic (revising for introductory statistics) and one invented citation.
That overlap gives the cross-paper review something to connect.

## Rebuilding the PDFs

```bash
python docs/screenshots/case-study/demo-data/make_demo_pdf.py \
    docs/screenshots/case-study/demo-data/fictional_paper_1_spaced_retrieval.html \
    Voss_Okafor_Spaced_Retrieval_DEMO.pdf
```

The output matches the uploaded file byte for byte (checked on 2026-09-25). The PDFs are not
committed, because CLAUDE.md §8 keeps uploaded PDFs out of Git.

## What these are not

- **Not sample papers.** `data/samples/` is for real, openly licensed papers (CLAUDE.md §5).
- **Not evaluation input.** Nothing in `results/` came from these files.
- **Not evidence of accuracy.** They only show what the interface does with a paper.
