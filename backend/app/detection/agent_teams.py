"""Agent Teams Coordination Failure Detection.

Detects failures in Claude Agent Teams (Feb 2026): team lead + parallel
teammates with shared task list.

Detection signals (from research + real Claude Code data):
1. Duplicate task assignment (original)
2. Task desync between lead and teammates (original)
3. Communication loop without progress (original)
4. Output overlap: agents producing redundant work (NEW — from real data analysis)
5. Silent agent: assigned but near-zero output (NEW — from Issue #23620 context loss)
6. Lead hoarding: one agent does >60% of all work (NEW — from real team patterns)

EXPERIMENTAL: Calibrated against 84 real multi-agent sessions from Claude Code.
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

    # ── 1. Duplicate assignment: same task to 2+ teammates ──
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

    # ── 2. Task desync ──
    if tasks:
        desync = sum(1 for t in tasks
                     if t.get("status") in ("done_by_lead_only", "done_by_teammate_only", "conflict"))
        if desync > 0:
            scores.append(min(1.0, desync * 0.25))

    # ── 3. Communication loop: many messages, few completions ──
    if msgs and tasks:
        pair_counts = defaultdict(int)
        for m in msgs:
            pair = tuple(sorted([m.get("from", ""), m.get("to", "")]))
            pair_counts[pair] += 1
        chatty_pairs = sum(1 for c in pair_counts.values() if c > 5)
        completed = sum(1 for t in tasks if t.get("status") in ("done", "completed"))
        if chatty_pairs > 0 and completed < len(tasks) * 0.5:
            scores.append(min(1.0, chatty_pairs * 0.3))

    # ── 4. NEW: Silent agent — assigned but near-zero output ──
    # Based on Issue #23620 (context loss: agent vanishes mid-session)
    if tasks:
        agents_with_tasks = {t.get("assigned_to") for t in tasks if t.get("assigned_to")}
        agents_with_output = set()
        for m in msgs:
            sender = m.get("from", "")
            content = m.get("content", "")
            if sender in agents_with_tasks and len(content) > 20:
                agents_with_output.add(sender)
        silent = agents_with_tasks - agents_with_output - {"lead", "system"}
        if silent and len(agents_with_tasks) > 1:
            silent_ratio = len(silent) / len(agents_with_tasks)
            if silent_ratio > 0.3:
                scores.append(min(1.0, silent_ratio + 0.2))

    # ── 5. NEW: Output overlap — agents producing redundant work ──
    if msgs:
        agent_outputs = defaultdict(list)
        for m in msgs:
            sender = m.get("from", "")
            content = m.get("content", "")
            if sender and sender not in ("lead", "system") and len(content) > 30:
                agent_outputs[sender].append(content)

        agents = list(agent_outputs.keys())
        for i in range(len(agents)):
            for j in range(i + 1, len(agents)):
                a_words = set()
                for text in agent_outputs[agents[i]]:
                    a_words.update(w.lower() for w in text.split() if len(w) > 4)
                b_words = set()
                for text in agent_outputs[agents[j]]:
                    b_words.update(w.lower() for w in text.split() if len(w) > 4)
                if a_words and b_words:
                    overlap = len(a_words & b_words) / max(min(len(a_words), len(b_words)), 1)
                    if overlap > 0.6:
                        scores.append(min(1.0, overlap))

    # ── 6. NEW: Lead hoarding — one agent does most work ──
    if msgs and team_size >= 2:
        agent_msg_counts = defaultdict(int)
        for m in msgs:
            sender = m.get("from", "")
            if sender:
                agent_msg_counts[sender] += 1
        if agent_msg_counts:
            total_msgs = sum(agent_msg_counts.values())
            max_msgs = max(agent_msg_counts.values())
            if total_msgs > 5 and max_msgs / total_msgs > 0.6:
                scores.append(min(1.0, (max_msgs / total_msgs - 0.5) * 2))

    # ── 7. Off-task messages ──
    if msgs and tasks:
        task_keywords = set()
        for t in tasks:
            desc = str(t.get("description", t.get("id", "")))
            task_keywords.update(w.lower() for w in desc.split() if len(w) > 4)
        if task_keywords:
            off_task = sum(1 for m in msgs if not (task_keywords & set(m.get("content", "").lower().split())))
            off_task_rate = off_task / len(msgs) if msgs else 0
            if off_task_rate > 0.5:
                scores.append(min(1.0, off_task_rate))

    if not scores:
        return False, 0.0
    return True, round(max(scores), 4)
