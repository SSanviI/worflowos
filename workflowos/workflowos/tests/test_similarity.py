# workflowos/tests/test_similarity.py
from workflowos.workflow_engine.similarity import (
    similarity_score,
    normalize_sequence,
    find_common_subsequence,
)


def test_similarity_identical():
    seq = ["CREATE_FILE", "RENAME_FILE", "MOVE_FILE"]
    assert similarity_score(seq, seq) == 1.0


def test_similarity_high_with_minor_difference():
    seq1 = ["CREATE_FILE", "RENAME_FILE", "MOVE_FILE"]
    seq2 = ["created", "RENAME_FILE", "MOVE_FILE"]
    assert similarity_score(seq1, seq2) == 1.0


def test_similarity_low_for_different_sequences():
    seq1 = ["CREATE_FILE", "RENAME_FILE", "MOVE_FILE"]
    seq2 = ["OPEN_SPREADSHEET", "TRANSFORM_DATA", "EXPORT_DATA"]
    assert similarity_score(seq1, seq2) < 0.4


def test_find_common_subsequence():
    seq1 = ["ACTIVE_WINDOW", "CREATE_FILE", "RENAME_FILE", "MOVE_FILE"]
    seq2 = ["CREATE_FILE", "MODIFY_FILE", "RENAME_FILE", "MOVE_FILE"]
    common = find_common_subsequence(seq1, seq2)
    assert common == ["CREATE_FILE", "RENAME_FILE", "MOVE_FILE"]
