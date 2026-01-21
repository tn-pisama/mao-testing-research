#!/usr/bin/env python3
"""
Fix MAO webhook format in all n8n workflow JSON files.
- Changes header from X-N8N-Api-Key to X-MAO-API-Key
- Updates payload format to match MAO API expectations
"""

import json
from pathlib import Path


def fix_workflow(file_path: Path) -> bool:
    """Fix the Send to MAO node in a workflow."""

    with open(file_path, 'r') as f:
        workflow = json.load(f)

    modified = False
    workflow_name = workflow.get('name', file_path.stem)
    meta = workflow.get('meta', {})
    failure_mode = meta.get('mast_failure_mode', 'UNKNOWN')
    complexity = meta.get('complexity', 'simple')

    for node in workflow.get('nodes', []):
        if node.get('name') == 'Send to MAO' and node.get('type') == 'n8n-nodes-base.httpRequest':
            params = node.get('parameters', {})

            # Fix header name
            header_params = params.get('headerParameters', {}).get('parameters', [])
            for header in header_params:
                if header.get('name') == 'X-N8N-Api-Key':
                    header['name'] = 'X-MAO-API-Key'
                    modified = True

            # Fix JSON body format - convert to MAO API format
            # MAO expects: executionId, workflowId, startedAt, data
            # Use simpler expressions to avoid JSON parsing issues
            new_json_body = '''={
  "executionId": "{{ $runIndex }}-{{ $now.toMillis() }}",
  "workflowId": "''' + failure_mode.lower().replace('-', '_') + '''",
  "workflowName": "''' + workflow_name + '''",
  "startedAt": "{{ $now.minus({minutes: 1}).toISO() }}",
  "finishedAt": "{{ $now.toISO() }}",
  "status": "success",
  "mode": "webhook",
  "data": {
    "failure_mode": "''' + failure_mode + '''",
    "complexity": "''' + complexity + '''",
    "session_id": "{{ $('Initialize').item.json.session_id }}"
  }
}'''
            params['jsonBody'] = new_json_body
            modified = True

    if modified:
        with open(file_path, 'w') as f:
            json.dump(workflow, f, indent=2)

    return modified


def main():
    base_dir = Path(__file__).parent.parent / 'n8n-workflows'
    categories = ['loop', 'state', 'persona', 'coordination', 'resource']

    total = 0
    modified = 0

    for category in categories:
        category_dir = base_dir / category
        if not category_dir.exists():
            continue

        print(f"\n{category.upper()}/")

        for json_file in sorted(category_dir.glob('*.json')):
            total += 1
            if fix_workflow(json_file):
                print(f"  Fixed: {json_file.name}")
                modified += 1
            else:
                print(f"  Skip:  {json_file.name}")

    print(f"\n{'='*40}")
    print(f"Total: {total}, Modified: {modified}")


if __name__ == '__main__':
    main()
