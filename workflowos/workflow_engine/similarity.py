# workflowos/workflow_engine/similarity.py
"""Utility functions for measuring similarity and extracting patterns between action sequences."""

from typing import List, Tuple, Optional
from workflowos.activity_agent.normalizer import EventNormalizer

# Environmental noise actions to filter out during macro workflow pattern detection
NOISE_ACTIONS = {"MODIFY_FILE", "CLIPBOARD_COPY"}


def normalize_sequence(seq: List[str], filter_noise: bool = True) -> List[str]:
    """Normalize action names, compress duplicate sequences, and filter noise."""
    normalized = []
    i = 0
    while i < len(seq):
        act = seq[i]
        norm = EventNormalizer.normalize_action(act)

        # Detect DELETE_FILE followed immediately by CREATE_FILE (standard OS move across folders)
        if norm == "DELETE_FILE" and i + 1 < len(seq):
            next_norm = EventNormalizer.normalize_action(seq[i + 1])
            if next_norm == "CREATE_FILE":
                norm = "MOVE_FILE"
                i += 1  # consume both

        if filter_noise and norm in NOISE_ACTIONS and len(seq) > 2:
            i += 1
            continue

        # Compress immediate identical duplicates
        if not normalized or normalized[-1] != norm:
            normalized.append(norm)
        i += 1

    return normalized


def _lcs_length(seq1: List[str], seq2: List[str]) -> int:
    """Dynamic programming computation of Longest Common Subsequence."""
    m, n = len(seq1), len(seq2)
    if m == 0 or n == 0:
        return 0
    prev = [0] * (n + 1)
    for i in range(1, m + 1):
        cur = [0] * (n + 1)
        for j in range(1, n + 1):
            if seq1[i - 1] == seq2[j - 1]:
                cur[j] = prev[j - 1] + 1
            else:
                cur[j] = max(prev[j], cur[j - 1])
        prev = cur
    return prev[-1]


def _levenshtein_distance(seq1: List[str], seq2: List[str]) -> int:
    """Compute Levenshtein edit distance between two sequences of strings."""
    m, n = len(seq1), len(seq2)
    if m == 0:
        return n
    if n == 0:
        return m
    previous_row = list(range(n + 1))
    for i, c1 in enumerate(seq1, start=1):
        current_row = [i] + [0] * n
        for j, c2 in enumerate(seq2, start=1):
            insertions = previous_row[j] + 1
            deletions = current_row[j - 1] + 1
            substitutions = previous_row[j - 1] + (0 if c1 == c2 else 1)
            current_row[j] = min(insertions, deletions, substitutions)
        previous_row = current_row
    return previous_row[-1]


def similarity_score(seq1: List[str], seq2: List[str]) -> float:
    """Return similarity score in range [0.0, 1.0]."""
    norm1 = normalize_sequence(seq1)
    norm2 = normalize_sequence(seq2)

    if not norm1 and not norm2:
        return 1.0
    max_len = max(len(norm1), len(norm2))
    if max_len == 0:
        return 1.0

    lcs_len = _lcs_length(norm1, norm2)
    lcs_score = lcs_len / max_len

    lev_dist = _levenshtein_distance(norm1, norm2)
    lev_score = max(0.0, 1.0 - (lev_dist / max_len))

    score = round(0.7 * lcs_score + 0.3 * lev_score, 4)
    return max(0.0, min(1.0, score))


def find_common_subsequence(seq1: List[str], seq2: List[str]) -> List[str]:
    """Extract the longest common subsequence of actions between two sequences."""
    norm1 = normalize_sequence(seq1)
    norm2 = normalize_sequence(seq2)
    m, n = len(norm1), len(norm2)

    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if norm1[i - 1] == norm2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    subseq = []
    i, j = m, n
    while i > 0 and j > 0:
        if norm1[i - 1] == norm2[j - 1]:
            subseq.append(norm1[i - 1])
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    subseq.reverse()
    return subseq


def count_non_overlapping_occurrences(seq: List[str], sub: List[str]) -> int:
    """Count strictly non-overlapping occurrences of sub within seq."""
    if not sub or len(sub) > len(seq):
        return 0
    count = 0
    i = 0
    m = len(sub)
    n = len(seq)
    while i <= n - m:
        if seq[i:i + m] == sub:
            count += 1
            i += m
        else:
            i += 1
    return count


def extract_repeating_patterns(seq: List[str], min_pattern_len: int = 2, max_pattern_len: int = 6) -> List[Tuple[List[str], int]]:
    """Detect repetitive action subsequences occurring within a single stream.

    Uses strictly non-overlapping count so that periodic motifs like (A, B, C)
    are prioritized over spurious overlapping extensions (A, B, C, A).
    """
    norm = normalize_sequence(seq)
    n = len(norm)
    if n < min_pattern_len * 2:
        return []

    pattern_counts = {}
    for length in range(min_pattern_len, min(max_pattern_len + 1, n // 2 + 1)):
        for start in range(n - length + 1):
            sub = norm[start:start + length]
            sub_tuple = tuple(sub)
            if sub_tuple not in pattern_counts:
                occ = count_non_overlapping_occurrences(norm, sub)
                if occ >= 2:
                    pattern_counts[sub_tuple] = occ

    repeating = [
        (list(pat), count)
        for pat, count in pattern_counts.items()
    ]
    # Prioritize higher occurrence counts, then length
    repeating.sort(key=lambda x: (x[1], len(x[0])), reverse=True)
    return repeating
