from eduagent.ui.mermaid import WHAT_IT_DOES, quote_mermaid_labels

TRACE_BLOCK = """graph TD
    A[Start with initial model parameters] --> B[Calculate the loss (error)]
    B --> C[Compute gradient (slope) of loss function]
    C --> D[Take a small step in the opposite direction of the gradient]
    D --> E[Update model parameters]
    E --> F[Repeat until loss is minimized or steps become very small]
    
    style A fill:#e0f7fa,stroke:#00695c
"""


def fenced(body: str, lang: str = "mermaid") -> str:
    return f"Intro text\n```{lang}\n{body}```\nOutro\n"


def test_what_it_does():
    assert WHAT_IT_DOES


def test_trace_block_labels_with_parentheses_are_quoted():
    out = quote_mermaid_labels(fenced(TRACE_BLOCK))
    assert 'B["Calculate the loss (error)"]' in out
    assert 'C["Compute gradient (slope) of loss function"]' in out
    # labels without brackets, the style line and the blank line stay as they were
    assert "A[Start with initial model parameters]" in out
    assert "    style A fill:#e0f7fa,stroke:#00695c\n" in out
    assert "    \n" in out
    assert out.startswith("Intro text\n```mermaid\ngraph TD\n") and out.endswith("```\nOutro\n")


def test_decision_shape():
    out = quote_mermaid_labels(fenced("flowchart TD\n    E{Is it done (yet)?}\n"))
    assert 'E{"Is it done (yet)?"}' in out


def test_round_shape_with_nested_brackets():
    out = quote_mermaid_labels(fenced("graph TD\n    E(call f[0] now)\n"))
    assert 'E("call f[0] now")' in out


def test_already_quoted_and_plain_unchanged():
    text = fenced('graph TD\n    A["x (y)"] --> B[Start]\n')
    assert quote_mermaid_labels(text) == text


def test_other_code_blocks_and_prose_unchanged():
    text = "see a[b(c)]\n```python\nx[f(1)]\n```\nand a[b(c)] again\n"
    assert quote_mermaid_labels(text) == text


def test_edge_labels_unchanged():
    text = fenced("graph TD\n    A -->|yes (1)| B\n    A -->|yes(1)| B\n    A -- why(x) --> B\n")
    assert quote_mermaid_labels(text) == text


def test_multi_character_shapes_unchanged():
    text = fenced("graph TD\n    A((circle (x))) --> B[(db (x))]\n    C{{hex (x)}} --> D[[sub (x)]]\n")
    assert quote_mermaid_labels(text) == text


def test_non_flowchart_diagrams_unchanged():
    text = fenced("sequenceDiagram\n    Alice->>John: call(f(x))\n")
    assert quote_mermaid_labels(text) == text


def test_idempotent():
    once = quote_mermaid_labels(fenced(TRACE_BLOCK))
    assert quote_mermaid_labels(once) == once


def test_inner_double_quote_escaped():
    out = quote_mermaid_labels(fenced('graph TD\n    A[say "hi" (loud)]\n'))
    assert 'A["say #quot;hi#quot; (loud)"]' in out


def test_crlf_preserved():
    out = quote_mermaid_labels("```mermaid\r\ngraph TD\r\n  A[x (y)]\r\n```\r\n")
    assert out == '```mermaid\r\ngraph TD\r\n  A["x (y)"]\r\n```\r\n'
