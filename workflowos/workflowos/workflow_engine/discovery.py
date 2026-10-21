# workflowos/workflow_engine/discovery.py
"""Generic Workflow Discovery Service.

Scans activity events, groups events into logical sessions, normalizes actions,
detects repetitive patterns across distinct sessions as well as within continuous
activity streams, and generates candidate Workflow records in PENDING_APPROVAL state.
"""

from collections import defaultdict
from typing import List, Tuple, Dict, Any, Optional
import os
import logging
from sqlalchemy.orm import Session

from ..backend.models.activity import ActivityEvent
from ..backend.models.workflow import Workflow
from ..activity_agent.sessionizer import ActivitySessionizer
from ..activity_agent.normalizer import EventNormalizer
from .similarity import (
    similarity_score,
    normalize_sequence,
    find_common_subsequence,
    extract_repeating_patterns,
)

logger = logging.getLogger("workflowos.workflow_engine.discovery")

# Configurable thresholds
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.75"))
MIN_OCCURRENCES = int(os.getenv("MIN_OCCURRENCES", "2"))


def _canonical_sequence_from_events(events: List[ActivityEvent]) -> List[str]:
    """Extract ordered canonical action names from a list of session events."""
    sorted_evs = sorted(events, key=lambda x: x.timestamp)
    raw_actions = [e.action for e in sorted_evs if e.action]
    return normalize_sequence(raw_actions)


def _cluster_sessions(
    session_sequences: Dict[str, List[str]],
    threshold: float = SIMILARITY_THRESHOLD,
) -> List[Tuple[List[str], float, List[str]]]:
    """Cluster session IDs based on action sequence similarity."""
    unassigned = [sid for sid, seq in session_sequences.items() if len(seq) >= 2]
    clusters: List[Tuple[List[str], float, List[str]]] = []
    visited = set()

    for i, seed_id in enumerate(unassigned):
        if seed_id in visited:
            continue

        seed_seq = session_sequences[seed_id]
        cluster = [seed_id]
        similarities = [1.0]
        visited.add(seed_id)

        for other_id in unassigned[i + 1:]:
            if other_id in visited:
                continue
            other_seq = session_sequences[other_id]
            sim = similarity_score(seed_seq, other_seq)
            if sim >= threshold:
                cluster.append(other_id)
                similarities.append(sim)
                visited.add(other_id)

        avg_confidence = round(sum(similarities) / len(similarities), 4) if similarities else 1.0

        rep_seq = seed_seq
        if len(cluster) > 1:
            common = find_common_subsequence(seed_seq, session_sequences[cluster[1]])
            if len(common) >= 2:
                rep_seq = common

        clusters.append((cluster, avg_confidence, rep_seq))

    return clusters


def analyze_and_discover_workflows(db: Session) -> Dict[str, Any]:
    """Execute repetition detection over all recorded activity events and generate candidate workflows.

    Returns comprehensive analysis diagnostics:
    - events_observed: total events count
    - sessions_analyzed: total sessions count
    - occurrences: number of times the sequence repeated
    - detected_pattern: the canonical sequence of actions
    - confidence: float score [0.0 - 1.0]
    - repetition_reason: explanation of why pattern is considered repetitive
    - candidate_workflows: list of generated Workflow ORM objects
    """
    events = db.query(ActivityEvent).order_by(ActivityEvent.timestamp).all()
    if not events:
        return {
            "events_observed": 0,
            "sessions_analyzed": 0,
            "occurrences": 0,
            "detected_pattern": [],
            "confidence": 0.0,
            "repetition_reason": "No activity events found in database to analyze.",
            "candidate_workflows": [],
        }

    # 1. Group events by session
    sessions: Dict[str, List[ActivityEvent]] = defaultdict(list)
    sessionizer = ActivitySessionizer(inactivity_timeout_seconds=5.0)

    needs_commit = False
    for ev in events:
        if not ev.session_id:
            ev.session_id = sessionizer.get_or_create_session(
                event_time=ev.timestamp,
                application=ev.application,
            )
            needs_commit = True
        sessions[ev.session_id].append(ev)

    if needs_commit:
        db.commit()

    # 2. Build canonical sequences per session
    session_seqs = {
        sid: _canonical_sequence_from_events(evlist)
        for sid, evlist in sessions.items()
    }

    # 3. First attempt: Cluster distinct sessions
    valid_sessions = {sid: seq for sid, seq in session_seqs.items() if len(seq) >= 2}
    clusters = _cluster_sessions(valid_sessions, threshold=SIMILARITY_THRESHOLD)

    discovered_candidates: List[Tuple[List[str], float, int]] = []

    for session_ids, confidence, rep_seq in clusters:
        if len(session_ids) >= MIN_OCCURRENCES and len(rep_seq) >= 2:
            discovered_candidates.append((rep_seq, confidence, len(session_ids)))

    # 4. Second attempt: Detect repeated patterns within continuous event streams
    if not discovered_candidates:
        all_actions = [e.action for e in events if e.action]
        normalized_all = normalize_sequence(all_actions)
        intra_patterns = extract_repeating_patterns(normalized_all, min_pattern_len=2, max_pattern_len=6)
        if intra_patterns:
            best_pattern, count = intra_patterns[0]
            confidence = 0.90
            discovered_candidates.append((best_pattern, confidence, count))

    discovered: List[Workflow] = []
    detected_pattern: List[str] = []
    occurrences = 0
    confidence = 0.0
    repetition_reason = ""

    for rep_seq, conf, occ in discovered_candidates:
        if len(rep_seq) < 2:
            continue

        detected_pattern = rep_seq
        occurrences = occ
        confidence = conf
        repetition_reason = (
            f"Action sequence [{' → '.join(rep_seq)}] was observed {occurrences} times across "
            f"{len(sessions)} distinct activity sessions with a pattern similarity score of "
            f"{confidence*100:.1f}% (detection threshold: {SIMILARITY_THRESHOLD*100:.0f}%). "
            f"The repetition frequency and sequential ordering confirm an automatable workflow motif."
        )

        actions = []
        for i, act in enumerate(rep_seq):
            action_id = f"a{i+1}"
            action_type = act.lower()
            actions.append({
                "id": action_id,
                "type": action_type,
                "parameters": {},
            })

        # Check existing workflow
        existing_wf = None
        for wf in db.query(Workflow).all():
            wf_actions = [a.get("type", "").lower() for a in (wf.actions or [])]
            curr_actions = [a.get("type", "").lower() for a in actions]
            if wf_actions == curr_actions:
                existing_wf = wf
                break

        if not existing_wf:
            wf = Workflow(
                name="Discovered Candidate Workflow",
                description="Repetitive activity pattern detected from desktop activity.",
                trigger={"type": "manual_or_event", "source": "desktop"},
                variables=[],
                actions=actions,
                conditions=[],
                failure_policy={"type": "stop_and_notify"},
                confidence=confidence,
                occurrences=occurrences,
                approved=False,
                rejected=False,
            )
            db.add(wf)
            db.flush()
            discovered.append(wf)
        else:
            existing_wf.occurrences = max(existing_wf.occurrences or 0, occurrences)
            existing_wf.confidence = max(existing_wf.confidence or 0.0, confidence)
            discovered.append(existing_wf)

    db.commit()

    return {
        "events_observed": len(events),
        "sessions_analyzed": len(sessions),
        "occurrences": occurrences,
        "detected_pattern": detected_pattern,
        "confidence": confidence,
        "repetition_reason": repetition_reason or "No repeating pattern exceeded detection threshold.",
        "candidate_workflows": discovered,
    }


def discover_workflows(db: Session) -> List[Workflow]:
    """Discover repetitive workflows from observed activity events."""
    result = analyze_and_discover_workflows(db)
    return result["candidate_workflows"]

