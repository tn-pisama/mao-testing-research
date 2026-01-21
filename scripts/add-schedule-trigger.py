#!/usr/bin/env python3
"""
Add Schedule Trigger to all n8n workflow JSON files.
Schedules workflows to run every 3 hours for MAST failure mode testing.
"""

import json
import os
from pathlib import Path


def add_schedule_trigger(workflow_path: Path) -> bool:
    """Add a schedule trigger node to a workflow JSON file."""

    with open(workflow_path, 'r') as f:
        workflow = json.load(f)

    # Check if schedule trigger already exists
    nodes = workflow.get('nodes', [])
    if any(n.get('type') == 'n8n-nodes-base.scheduleTrigger' for n in nodes):
        print(f"  Skipping {workflow_path.name} - already has schedule trigger")
        return False

    # Create schedule trigger node
    schedule_node = {
        "parameters": {
            "rule": {
                "interval": [{"field": "hours", "hoursInterval": 3}]
            }
        },
        "id": "schedule",
        "name": "Schedule Trigger",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [0, -200]
    }

    # Add schedule node to nodes array
    workflow['nodes'].insert(0, schedule_node)

    # Add connection from Schedule Trigger to Initialize node
    connections = workflow.get('connections', {})
    connections['Schedule Trigger'] = {
        "main": [[{"node": "Initialize", "type": "main", "index": 0}]]
    }
    workflow['connections'] = connections

    # Write back
    with open(workflow_path, 'w') as f:
        json.dump(workflow, f, indent=2)

    print(f"  Added schedule trigger to {workflow_path.name}")
    return True


def main():
    """Process all workflow JSON files in n8n-workflows directory."""

    base_dir = Path(__file__).parent.parent / 'n8n-workflows'

    categories = ['loop', 'state', 'persona', 'coordination', 'resource']

    total_modified = 0
    total_skipped = 0

    for category in categories:
        category_dir = base_dir / category
        if not category_dir.exists():
            print(f"Warning: {category_dir} does not exist")
            continue

        print(f"\nProcessing {category}/")

        json_files = sorted(category_dir.glob('*.json'))
        for json_file in json_files:
            if add_schedule_trigger(json_file):
                total_modified += 1
            else:
                total_skipped += 1

    print(f"\n{'='*50}")
    print(f"Total modified: {total_modified}")
    print(f"Total skipped:  {total_skipped}")
    print(f"{'='*50}")


if __name__ == '__main__':
    main()
