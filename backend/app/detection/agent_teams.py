"""Agent Teams Coordination Failure Detection.

Detects failures in Claude Agent Teams (Feb 2026): team lead + parallel
teammates with shared task list.

Failure modes: task desync, duplicate work, off-task messages, communication loops.
"""

from collections import defaultdict
from typing import Any, Dict, List, Tuple

def detect(
    task_list: List[Dict[str, Any]] = None,
    messages: List[Dict[str, Any]] = None,
    team_size: int = 0,
) -> Tuple[bool, float]:
    tasks = task_list or []
    msgs = messages or []
    if not tasks and not msgs:
        return False, 0.0

    scores = []

    # 1. Duplicate assignment: same task to 2+ teammates
    if tasks:
        task_assignees = defaultdict(set)
        for t in tasks:
            tid = t.get("id", "")
            assignee = t.get("assigned_to", "")
            if tid and assignee:
                task_assignees[tid].add(assignee)
        duplicates = sum(1 for aids in task_assignees.values() if len(aids) > 1)
        if duplicates > 0:
            scores.append(min(1.0, duplicates * 0.3))

    # 2. Task desync: done by one party but not the other
    if tasks:
        desync = 0
        for t in tasks:
            status = t.get("status", "")
            if status in ("done_by_lead_only", "done_by_teammate_only", "conflict"):
                desync += 1
        if desync > 0:
            scores.append(min(1.0, desync * 0.25))

    # 3. Communication loop: >5 messages between same pair without task progress
    if msgs:
        pair_counts = defaultdict(int)
        for m in msgs:
            pair = tuple(sorted([m.get("from", ""), m.get("to", "")]))
            pair_counts[pair] += 1
        chatty_pairs = sum(1 for c in pair_counts.values() if c > 5)
        if chatty_pairs > 0:
            # Check if tasks made progress during chatty exchanges
            completed = sum(1 for t in tasks if t.get("status") in ("done", "completed"))
            if completed < len(tasks) * 0.5:
                scores.append(min(1.0, chatty_pairs * 0.3))

    # 4. Off-task messages: messages not referencing any task
    if msgs and tasks:
        task_keywords = set()
        for t in tasks:
            desc = str(t.get("description", t.get("id", "")))
            task_keywords.update(w.lower() for w in desc.split() if len(w) > 4)
        if task_keywords:
            off_task = 0
            for m in msgs:
                content_words = set(m.get("content", "").lower().split())
                if not (task_keywords & content_words):
                    off_task += 1
            off_task_rate = off_task / len(msgs) if msgs else 0
            if off_task_rate > 0.5:
                scores.append(min(1.0, off_task_rate))

    if not scores:
        return False, 0.0
    return True, round(max(scores), 4)
