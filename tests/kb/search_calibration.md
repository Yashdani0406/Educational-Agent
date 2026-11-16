
# Search calibration (live)

Fixtures: 12-slide Decision Trees deck (module) and a 40-page Statistical Learning book (reference).
RERANK_RELEVANT_MIN in force: -2.8

## 'What stopping rules decide when to stop splitting a node?' (module)

slots {'module': 7, 'reference': 3} | ms {'embed': 128.8, 'dense': 13.2, 'keyword': 7.4, 'fusion': 0.1, 'rerank': 554.0, 'total': 708.9}

| # | chunk | origin | dense | keyword | fused | rerank |
|---|---|---|---|---|---|---|
| 1 | slide-6 | module | 0.885 | 19.686 | 1.0 | 8.821 |
| 2 | slide-2 | module | 0.731 | 5.785 | 0.669 | -1.695 |
| 3 | slide-12 | module | 0.696 | 10.568 | 0.754 | -1.909 |
| 4 | slide-9 | module | 0.639 | 1.448 | 0.551 | -9.589 |
| 5 | slide-4 | module | 0.486 | 2.189 | 0.517 | -9.984 |
| 6 | slide-10 | module | 0.589 | 1.609 | 0.538 | -10.087 |
| 7 | slide-5 | module | 0.66 | 2.123 | 0.572 | -10.588 |
| 8 | book-Cross-validation | reference | 0.576 | 1.58 | 0.726 | -11.111 |
| 9 | book-Bias-variance tradeoff | reference | 0.518 | 1.639 | 0.71 | -11.301 |
| 10 | book-Clustering | reference | 0.556 | 1.317 | 0.695 | -11.33 |

Calibration: relevant chunks score 8.82..8.82; all other chunks score up to -1.69

## 'How do we prune a tree and how is alpha chosen?' (module)

slots {'module': 7, 'reference': 3} | ms {'embed': 229.9, 'dense': 14.8, 'keyword': 8.2, 'fusion': 0.1, 'rerank': 398.6, 'total': 657.3}

| # | chunk | origin | dense | keyword | fused | rerank |
|---|---|---|---|---|---|---|
| 1 | slide-8 | module | 0.772 | 10.445 | 1.0 | 0.646 |
| 2 | slide-12 | module | 0.673 | 5.226 | 0.767 | -3.952 |
| 3 | slide-10 | module | 0.642 | 2.948 | 0.669 | -10.214 |
| 4 | slide-1 | module | 0.631 | 2.729 | 0.657 | -10.611 |
| 5 | slide-11 | module | 0.621 | 2.986 | 0.663 | -10.682 |
| 6 | slide-7 | module | 0.608 | 4.216 | 0.706 | -10.879 |
| 7 | book-Ridge regression | reference | 0.57 | 4.967 | 0.851 | -11.158 |
| 8 | slide-5 | module | 0.584 | 2.056 | 0.615 | -11.177 |
| 9 | book-Bootstrap and bagging | reference | 0.612 | 2.407 | 0.729 | -11.205 |
| 10 | book-Clustering | reference | 0.583 | 0.0 | 0.589 | -11.212 |

Calibration: relevant chunks score 0.65..0.65; all other chunks score up to -3.95

## 'What is the bias-variance tradeoff?' (book)

slots {'module': 0, 'reference': 10} | ms {'embed': 95.9, 'dense': 15.4, 'keyword': 7.7, 'fusion': 0.1, 'rerank': 451.4, 'total': 576.1}

| # | chunk | origin | dense | keyword | fused | rerank |
|---|---|---|---|---|---|---|
| 1 | book-Bias-variance tradeoff | reference | 0.851 | 8.329 | 0.999 | 8.662 |
| 2 | book-Bias-variance tradeoff | reference | 0.823 | 8.238 | 0.986 | 8.48 |
| 3 | book-Bias-variance tradeoff | reference | 0.853 | 7.975 | 0.983 | 8.356 |
| 4 | book-Bias-variance tradeoff | reference | 0.849 | 7.975 | 0.982 | 8.044 |
| 5 | book-Cross-validation | reference | 0.639 | 3.281 | 0.688 | -3.508 |
| 6 | book-Ridge regression | reference | 0.623 | 4.383 | 0.736 | -6.316 |
| 7 | book-Linear regression | reference | 0.578 | 2.53 | 0.632 | -9.304 |
| 8 | book-Principal components | reference | 0.548 | 2.53 | 0.623 | -9.967 |
| 9 | book-Bootstrap and bagging | reference | 0.623 | 1.776 | 0.611 | -10.595 |
| 10 | book-Principal components | reference | 0.547 | 1.247 | 0.561 | -10.722 |

Calibration: relevant chunks score 8.04..8.66; all other chunks score up to -3.51

## 'How does ridge regression shrink the coefficients?' (book)

slots {'module': 0, 'reference': 10} | ms {'embed': 124.4, 'dense': 15.5, 'keyword': 8.0, 'fusion': 0.1, 'rerank': 478.0, 'total': 632.6}

| # | chunk | origin | dense | keyword | fused | rerank |
|---|---|---|---|---|---|---|
| 1 | book-Ridge regression | reference | 0.845 | 10.801 | 1.0 | 7.648 |
| 2 | book-Ridge regression | reference | 0.805 | 7.275 | 0.857 | 4.681 |
| 3 | book-Ridge regression | reference | 0.794 | 4.837 | 0.763 | 2.275 |
| 4 | book-Ridge regression | reference | 0.745 | 5.204 | 0.76 | -2.201 |
| 5 | book-Logistic regression | reference | 0.61 | 3.998 | 0.672 | -5.37 |
| 6 | book-Linear regression | reference | 0.623 | 1.59 | 0.587 | -6.942 |
| 7 | book-Linear regression | reference | 0.593 | 6.335 | 0.753 | -7.289 |
| 8 | book-Linear regression | reference | 0.601 | 1.712 | 0.584 | -9.109 |
| 9 | book-Linear regression | reference | 0.612 | 1.505 | 0.58 | -9.351 |
| 10 | book-Logistic regression | reference | 0.56 | 1.568 | 0.565 | -9.924 |

Calibration: relevant chunks score -2.20..7.65; all other chunks score up to -5.37

## 'train_test_split' (term)

slots {'module': 7, 'reference': 3} | ms {'embed': 124.2, 'dense': 16.2, 'keyword': 6.9, 'fusion': 0.1, 'rerank': 368.2, 'total': 521.3}

| # | chunk | origin | dense | keyword | fused | rerank |
|---|---|---|---|---|---|---|
| 1 | slide-9 | module | 0.76 | 3.093 | 1.0 | 7.868 |
| 2 | slide-10 | module | 0.509 | 0.0 | 0.514 | -3.386 |
| 3 | slide-6 | module | 0.579 | 0.0 | 0.538 | -4.747 |
| 4 | book-Bias-variance tradeoff | reference | 0.535 | 0.0 | 0.6 | -7.176 |
| 5 | slide-2 | module | 0.595 | 0.0 | 0.544 | -7.957 |
| 6 | slide-5 | module | 0.592 | 0.0 | 0.543 | -8.093 |
| 7 | book-Cross-validation | reference | 0.522 | 0.0 | 0.595 | -8.324 |
| 8 | slide-12 | module | 0.502 | 0.0 | 0.512 | -10.525 |
| 9 | book-Linear regression | reference | 0.487 | 0.0 | 0.582 | -10.561 |
| 10 | slide-7 | module | 0.459 | 0.0 | 0.497 | -11.071 |

Calibration: relevant chunks score 7.87..7.87; all other chunks score up to -3.39

## 'Gini index' (term)

slots {'module': 7, 'reference': 3} | ms {'embed': 179.1, 'dense': 14.8, 'keyword': 7.4, 'fusion': 0.1, 'rerank': 397.8, 'total': 605.0}

| # | chunk | origin | dense | keyword | fused | rerank |
|---|---|---|---|---|---|---|
| 1 | slide-3 | module | 0.791 | 10.243 | 1.0 | 9.202 |
| 2 | slide-4 | module | 0.429 | 0.0 | 0.479 | -11.298 |
| 3 | book-Logistic regression | reference | 0.424 | 0.0 | 0.575 | -11.341 |
| 4 | book-Logistic regression | reference | 0.417 | 0.0 | 0.572 | -11.351 |
| 5 | book-Ridge regression | reference | 0.448 | 0.0 | 0.585 | -11.362 |
| 6 | slide-10 | module | 0.428 | 0.0 | 0.479 | -11.404 |
| 7 | slide-9 | module | 0.414 | 0.0 | 0.474 | -11.406 |
| 8 | slide-12 | module | 0.406 | 0.0 | 0.471 | -11.416 |
| 9 | slide-8 | module | 0.371 | 0.0 | 0.459 | -11.416 |
| 10 | slide-2 | module | 0.387 | 0.0 | 0.465 | -11.43 |

Calibration: relevant chunks score 9.20..9.20; all other chunks score up to -11.30

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

- OK: 'What stopping rules decide when to stop splitting a node?': first hit origin module
- OK: 'How do we prune a tree and how is alpha chosen?': first hit origin module
- OK: 'What is the bias-variance tradeoff?': 10 book chunks
- OK: 'How does ridge regression shrink the coefficients?': 10 book chunks
- OK: 'train_test_split': top 3 ['slide-9', 'slide-10', 'slide-6']
- OK: 'Gini index': top 3 ['slide-3', 'slide-4', 'book-Logistic regression']
.
1 passed in 15.69s
