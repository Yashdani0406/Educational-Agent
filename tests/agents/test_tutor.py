from eduagent.agents.tutor import TUTOR_INSTRUCTION


def test_instruction_tells_model_to_quote_mermaid_labels():
    assert 'wrap every node label in double quotes' in TUTOR_INSTRUCTION
    assert 'A["Compute the loss (error)"]' in TUTOR_INSTRUCTION
