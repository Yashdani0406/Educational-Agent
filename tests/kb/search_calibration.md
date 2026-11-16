
# Search calibration (live)

Fixtures: 12-slide Decision Trees deck (module) and a 40-page Statistical Learning book (reference).
RERANK_RELEVANT_MIN in force: 0.0

## 'What stopping rules decide when to stop splitting a node?' (module)

slots {'module': 4, 'reference': 6} | ms {'embed': 136.0, 'dense': 9.6, 'keyword': 5.8, 'fusion': 4.2, 'rerank': 358.7, 'total': 514.4}

| # | chunk | origin | dense | keyword | fused | rerank |
|---|---|---|---|---|---|---|
| 1 | slide-6 | module | 0.885 | 19.686 | 1.0 | 8.821 |
| 2 | slide-2 | module | 0.731 | 5.785 | 0.669 | -1.695 |
| 3 | slide-12 | module | 0.696 | 10.568 | 0.754 | -1.909 |
| 4 | slide-9 | module | 0.639 | 1.448 | 0.551 | -9.589 |
| 5 | book-Cross-validation | reference | 0.576 | 1.58 | 0.726 | -11.111 |
| 6 | book-Bias-variance tradeoff | reference | 0.518 | 1.639 | 0.71 | -11.301 |
| 7 | book-Clustering | reference | 0.556 | 1.317 | 0.695 | -11.33 |
| 8 | book-Clustering | reference | 0.596 | 0.0 | 0.591 | -11.343 |
| 9 | book-Clustering | reference | 0.59 | 0.0 | 0.589 | -11.346 |
| 10 | book-Cross-validation | reference | 0.539 | 0.0 | 0.57 | -11.354 |

Calibration: relevant chunks score 8.82..8.82; all other chunks score up to -1.69

## 'How do we prune a tree and how is alpha chosen?' (module)

slots {'module': 4, 'reference': 6} | ms {'embed': 61.0, 'dense': 16.1, 'keyword': 11.3, 'fusion': 7.2, 'rerank': 413.5, 'total': 509.4}

| # | chunk | origin | dense | keyword | fused | rerank |
|---|---|---|---|---|---|---|
| 1 | slide-8 | module | 0.772 | 10.445 | 1.0 | 0.646 |
| 2 | slide-12 | module | 0.673 | 5.226 | 0.767 | -3.952 |
| 3 | slide-10 | module | 0.642 | 2.948 | 0.669 | -10.214 |
| 4 | slide-1 | module | 0.631 | 2.729 | 0.657 | -10.611 |
| 5 | book-Ridge regression | reference | 0.57 | 4.967 | 0.851 | -11.158 |
| 6 | book-Bootstrap and bagging | reference | 0.612 | 2.407 | 0.729 | -11.205 |
| 7 | book-Clustering | reference | 0.583 | 0.0 | 0.589 | -11.212 |
| 8 | book-Clustering | reference | 0.571 | 0.0 | 0.585 | -11.279 |
| 9 | book-Ridge regression | reference | 0.529 | 0.0 | 0.569 | -11.304 |
| 10 | book-Clustering | reference | 0.542 | 0.296 | 0.59 | -11.31 |

Calibration: relevant chunks score 0.65..0.65; all other chunks score up to -3.95

## 'What is the bias-variance tradeoff?' (book)

slots {'module': 0, 'reference': 10} | ms {'embed': 56.4, 'dense': 16.2, 'keyword': 15.7, 'fusion': 13.5, 'rerank': 434.4, 'total': 536.5}

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

slots {'module': 0, 'reference': 10} | ms {'embed': 53.7, 'dense': 15.7, 'keyword': 14.2, 'fusion': 9.5, 'rerank': 353.5, 'total': 446.7}

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

slots {'module': 4, 'reference': 6} | ms {'embed': 45.9, 'dense': 14.6, 'keyword': 6.8, 'fusion': 6.1, 'rerank': 413.7, 'total': 487.3}

| # | chunk | origin | dense | keyword | fused | rerank |
|---|---|---|---|---|---|---|
| 1 | slide-9 | module | 0.76 | 3.093 | 1.0 | 7.868 |
| 2 | slide-10 | module | 0.509 | 0.0 | 0.514 | -3.386 |
| 3 | slide-6 | module | 0.579 | 0.0 | 0.538 | -4.747 |
| 4 | book-Bias-variance tradeoff | reference | 0.535 | 0.0 | 0.6 | -7.176 |
| 5 | slide-2 | module | 0.595 | 0.0 | 0.544 | -7.957 |
| 6 | book-Cross-validation | reference | 0.522 | 0.0 | 0.595 | -8.324 |
| 7 | book-Linear regression | reference | 0.487 | 0.0 | 0.582 | -10.561 |
| 8 | book-Bias-variance tradeoff | reference | 0.498 | 0.0 | 0.586 | -10.809 |
| 9 | book-Bias-variance tradeoff | reference | 0.506 | 0.0 | 0.589 | -11.086 |
| 10 | book-Bootstrap and bagging | reference | 0.48 | 0.0 | 0.579 | -11.111 |

Calibration: relevant chunks score 7.87..7.87; all other chunks score up to -3.39

## 'Gini index' (term)

slots {'module': 4, 'reference': 6} | ms {'embed': 36.5, 'dense': 17.5, 'keyword': 14.9, 'fusion': 10.9, 'rerank': 413.9, 'total': 494.0}

| # | chunk | origin | dense | keyword | fused | rerank |
|---|---|---|---|---|---|---|
| 1 | slide-3 | module | 0.791 | 10.243 | 1.0 | 9.202 |
| 2 | slide-4 | module | 0.429 | 0.0 | 0.479 | -11.298 |
| 3 | book-Logistic regression | reference | 0.424 | 0.0 | 0.575 | -11.341 |
| 4 | book-Logistic regression | reference | 0.417 | 0.0 | 0.572 | -11.351 |
| 5 | book-Ridge regression | reference | 0.448 | 0.0 | 0.585 | -11.362 |
| 6 | book-Ridge regression | reference | 0.438 | 0.0 | 0.581 | -11.366 |
| 7 | book-Bias-variance tradeoff | reference | 0.46 | 0.0 | 0.59 | -11.368 |
| 8 | book-Logistic regression | reference | 0.431 | 0.0 | 0.578 | -11.37 |
| 9 | slide-10 | module | 0.428 | 0.0 | 0.479 | -11.404 |
| 10 | slide-9 | module | 0.414 | 0.0 | 0.474 | -11.406 |

Calibration: relevant chunks score 9.20..9.20; all other chunks score up to -11.30

## Calibration summary (RERANK_RELEVANT_MIN)

Lowest relevant rerank score: -2.20 (book-Ridge regression)
Highest other rerank score: -1.69 (slide-2 for 'What stopping rules decide when to stop splitting a node?')

## Outcomes

- OK: 'What stopping rules decide when to stop splitting a node?': first hit origin module
- OK: 'How do we prune a tree and how is alpha chosen?': first hit origin module
- OK: 'What is the bias-variance tradeoff?': 10 book chunks
- OK: 'How does ridge regression shrink the coefficients?': 10 book chunks
- OK: 'train_test_split': top 3 ['slide-9', 'slide-10', 'slide-6']
- OK: 'Gini index': top 3 ['slide-3', 'slide-4', 'book-Logistic regression']

## How RERANK_RELEVANT_MIN = 0.0 was chosen

The best chunk for every question scored between 0.65 and 9.20 (the lowest is the pruning slide at 0.65). Chunks that do not answer the question scored at most -1.69; unrelated ones sit at -3 to -11. A threshold of 0.0 therefore sits above every non-answer with a margin of 1.69 and below every best answer with a margin of 0.65. Two supporting chunks that a reader would still call relevant score lower (one ridge-regression page at -2.20); with 0.0 they count as not relevant, which only means their group may hand a slot over, and they still appear while their group has slots. The floor never removes a result, so a slightly high floor costs little. Values below -2.2 were rejected because they would start counting adjacent but unhelpful slides (stopping-rule question: "Splitting a Node" -1.69) as relevant. The fixture set is small (6 questions), so the margin is evidence for the value, not proof; it should be revisited on real course material.

Observation: for the two slide-only questions the module has only 1 relevant chunk, so by the specified slot rule the other 6 slots go to the book and fill with book chunks scoring about -11 (listed after the module chunks because the merged list is sorted by rerank score). Callers that want only useful passages can drop hits with rerank below RERANK_RELEVANT_MIN.
