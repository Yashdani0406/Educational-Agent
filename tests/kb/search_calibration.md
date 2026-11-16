
# Search calibration (live)

Fixtures: 12-slide Decision Trees deck (module) and a 40-page Statistical Learning book (reference).
RERANK_RELEVANT_MIN in force: -2.8

## 'What stopping rules decide when to stop splitting a node?' (module)

slots {'module': 7, 'reference': 3} | ms {'embed': 164.0, 'dense': 9.5, 'keyword': 7.6, 'fusion': 0.1, 'rerank': 291.0, 'total': 478.1}

| # | chunk | origin | dense | keyword | fused | rerank |
|---|---|---|---|---|---|---|
| 1 | slide-6 | module | 0.885 | 19.686 | 1.0 | 8.821 |
| 2 | slide-2 | module | 0.731 | 5.785 | 0.669 | -1.695 |
| 3 | slide-12 | module | 0.696 | 10.568 | 0.754 | -1.909 |

Calibration: relevant chunks score 8.82..8.82; all other chunks score up to -1.69

Cut below the floor: 7; weak fallback fired: False; returned: 3

## 'How do we prune a tree and how is alpha chosen?' (module)

slots {'module': 7, 'reference': 3} | ms {'embed': 113.8, 'dense': 10.1, 'keyword': 6.3, 'fusion': 0.1, 'rerank': 342.4, 'total': 477.8}

| # | chunk | origin | dense | keyword | fused | rerank |
|---|---|---|---|---|---|---|
| 1 | slide-8 | module | 0.772 | 10.445 | 1.0 | 0.646 |

Calibration: relevant chunks score 0.65..0.65; all other chunks score up to -3.95

Cut below the floor: 9; weak fallback fired: False; returned: 1

## 'What is the bias-variance tradeoff?' (book)

slots {'module': 0, 'reference': 10} | ms {'embed': 164.1, 'dense': 21.0, 'keyword': 8.1, 'fusion': 0.1, 'rerank': 366.3, 'total': 565.8}

| # | chunk | origin | dense | keyword | fused | rerank |
|---|---|---|---|---|---|---|
| 1 | book-Bias-variance tradeoff | reference | 0.851 | 8.329 | 0.999 | 8.662 |
| 2 | book-Bias-variance tradeoff | reference | 0.823 | 8.238 | 0.986 | 8.48 |
| 3 | book-Bias-variance tradeoff | reference | 0.853 | 7.975 | 0.983 | 8.356 |
| 4 | book-Bias-variance tradeoff | reference | 0.849 | 7.975 | 0.982 | 8.044 |

Calibration: relevant chunks score 8.04..8.66; all other chunks score up to -3.51

Cut below the floor: 6; weak fallback fired: False; returned: 4

## 'How does ridge regression shrink the coefficients?' (book)

slots {'module': 0, 'reference': 10} | ms {'embed': 90.3, 'dense': 16.7, 'keyword': 11.3, 'fusion': 0.1, 'rerank': 397.7, 'total': 525.6}

| # | chunk | origin | dense | keyword | fused | rerank |
|---|---|---|---|---|---|---|
| 1 | book-Ridge regression | reference | 0.845 | 10.801 | 1.0 | 7.648 |
| 2 | book-Ridge regression | reference | 0.805 | 7.275 | 0.857 | 4.681 |
| 3 | book-Ridge regression | reference | 0.794 | 4.837 | 0.763 | 2.275 |
| 4 | book-Ridge regression | reference | 0.745 | 5.204 | 0.76 | -2.201 |

Calibration: relevant chunks score -2.20..7.65; all other chunks score up to -5.37

Cut below the floor: 6; weak fallback fired: False; returned: 4

## 'train_test_split' (term)

slots {'module': 7, 'reference': 3} | ms {'embed': 141.4, 'dense': 16.6, 'keyword': 11.2, 'fusion': 0.1, 'rerank': 334.3, 'total': 513.4}

| # | chunk | origin | dense | keyword | fused | rerank |
|---|---|---|---|---|---|---|
| 1 | slide-9 | module | 0.76 | 3.093 | 1.0 | 7.868 |

Calibration: relevant chunks score 7.87..7.87; all other chunks score up to -3.39

Cut below the floor: 9; weak fallback fired: False; returned: 1

## 'Gini index' (term)

slots {'module': 7, 'reference': 3} | ms {'embed': 79.6, 'dense': 15.3, 'keyword': 6.9, 'fusion': 0.1, 'rerank': 367.7, 'total': 475.8}

| # | chunk | origin | dense | keyword | fused | rerank |
|---|---|---|---|---|---|---|
| 1 | slide-3 | module | 0.791 | 10.243 | 1.0 | 9.202 |

Calibration: relevant chunks score 9.20..9.20; all other chunks score up to -11.30

Cut below the floor: 9; weak fallback fired: False; returned: 1

## Calibration summary

The threshold is chosen on two numbers per question: the score of the best answer (the highest-scoring chunk labelled
relevant) and the highest score of any chunk not labelled relevant. Every chunk of both groups was scored for this.

| question | best answer | highest non-answer |
|---|---|---|
| 'What stopping rules decide when to stop splitting a node?' | 8.82 | -1.69 |
| 'How do we prune a tree and how is alpha chosen?' | 0.65 | -3.95 |
| 'What is the bias-variance tradeoff?' | 8.66 | -3.51 |
| 'How does ridge regression shrink the coefficients?' | 7.65 | -5.37 |
| 'train_test_split' | 7.87 | -3.39 |
| 'Gini index' | 9.20 | -11.30 |

Lowest best answer: 0.65. Highest non-answer: -1.69. Gap: 2.34.

Overlap: the labels are partly subjective. The lowest chunk labelled relevant scores -2.20 (book-Ridge regression), below the highest unlabelled chunk at -1.69. Supporting and adjacent chunks therefore cannot be separated by any threshold; the floor only has to separate best answers from noise.

## Outcomes

- OK: 'What stopping rules decide when to stop splitting a node?': no below-floor chunk unless weak
- OK: 'What stopping rules decide when to stop splitting a node?': first hit origin module
- OK: 'How do we prune a tree and how is alpha chosen?': no below-floor chunk unless weak
- OK: 'How do we prune a tree and how is alpha chosen?': first hit origin module
- OK: 'What is the bias-variance tradeoff?': no below-floor chunk unless weak
- OK: 'What is the bias-variance tradeoff?': first hit origin reference, 4 book chunks
- OK: 'How does ridge regression shrink the coefficients?': no below-floor chunk unless weak
- OK: 'How does ridge regression shrink the coefficients?': first hit origin reference, 4 book chunks
- OK: 'train_test_split': no below-floor chunk unless weak
- OK: 'train_test_split': top 3 ['slide-9']
- OK: 'Gini index': no below-floor chunk unless weak
- OK: 'Gini index': top 3 ['slide-3']
.
1 passed in 15.29s
