#!/usr/bin/env python3
"""
Import all MAST workflows to n8n Cloud.
Transforms workflow JSON to n8n API format.
"""

import json
import os
import time
from pathlib import Path
import urllib.request
import urllib.error

# Configuration
N8N_API_KEY = os.environ.get('N8N_API_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzOWViMTllYi02MDUxLTRhN2YtODNjYS1mOWUwNWMyNWRlNmEiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY4MjY0NjMzfQ.-SiJrQlkR5faMc693agWdpKUGTm7Wi4CcMXR9EY3dc8')
N8N_HOST = os.environ.get('N8N_HOST', 'https://pisama.app.n8n.cloud')


def get_existing_workflows():
    """Get list of existing workflow names to avoid duplicates."""
    url = f"{N8N_HOST}/api/v1/workflows"
    req = urllib.request.Request(url, headers={'x-n8n-api-key': N8N_API_KEY})

    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read())
            return {wf['name']: wf['id'] for wf in data.get('data', [])}
    except Exception as e:
        print(f"Warning: Could not fetch existing workflows: {e}")
        return {}


def import_workflow(file_path: Path, existing: dict) -> tuple[bool, str]:
    """Import a single workflow to n8n Cloud."""

    with open(file_path, 'r') as f:
        workflow = json.load(f)

    name = workflow.get('name', file_path.stem)

    # Check if workflow already exists
    if name in existing:
        # Update existing workflow (n8n uses PUT, not PATCH)
        workflow_id = existing[name]
        url = f"{N8N_HOST}/api/v1/workflows/{workflow_id}"
        method = 'PUT'
    else:
        # Create new workflow
        url = f"{N8N_HOST}/api/v1/workflows"
        method = 'POST'

    # Transform to n8n API format (ONLY these 4 fields are allowed for creation)
    api_payload = {
        'name': name,
        'nodes': workflow.get('nodes', []),
        'connections': workflow.get('connections', {}),
        'settings': workflow.get('settings', {}),
    }

    data = json.dumps(api_payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            'x-n8n-api-key': N8N_API_KEY,
            'Content-Type': 'application/json'
        },
        method=method
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read())
            return True, result.get('id', 'OK')
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        return False, f"{e.code}: {error_body[:100]}"
    except Exception as e:
        return False, str(e)


def activate_workflow(workflow_id: str) -> bool:
    """Activate a workflow by ID."""
    url = f"{N8N_HOST}/api/v1/workflows/{workflow_id}/activate"
    req = urllib.request.Request(
        url,
        data=b'{}',
        headers={
            'x-n8n-api-key': N8N_API_KEY,
            'Content-Type': 'application/json'
        },
        method='POST'
    )

    try:
        with urllib.request.urlopen(req):
            return True
    except Exception:
        return False


def main():
    """Import all workflow JSON files to n8n Cloud."""

    base_dir = Path(__file__).parent.parent / 'n8n-workflows'
    categories = ['loop', 'state', 'persona', 'coordination', 'resource']

    print("Fetching existing workflows...")
    existing = get_existing_workflows()
    print(f"Found {len(existing)} existing workflows\n")

    print("Importing MAST workflows to n8n Cloud...")
    print("=" * 50)

    total = 0
    success = 0
    failed = 0
    workflow_ids = []

    for category in categories:
        category_dir = base_dir / category
        if not category_dir.exists():
            print(f"Warning: {category_dir} does not exist")
            continue

        print(f"\n{category.upper()}/")
        print("-" * 30)

        json_files = sorted(category_dir.glob('*.json'))
        for json_file in json_files:
            total += 1
            print(f"  [{total:2d}] {json_file.stem}... ", end='', flush=True)

            ok, result = import_workflow(json_file, existing)

            if ok:
                print(f"OK ({result})")
                success += 1
                workflow_ids.append(result)
            else:
                print(f"FAILED ({result})")
                failed += 1

            time.sleep(0.3)  # Rate limiting

    print("\n" + "=" * 50)
    print(f"Total:   {total}")
    print(f"Success: {success}")
    print(f"Failed:  {failed}")
    print("=" * 50)

    # Activate successful workflows
    if workflow_ids:
        print(f"\nActivating {len(workflow_ids)} workflows...")
        activated = 0
        for wf_id in workflow_ids:
            if activate_workflow(wf_id):
                activated += 1
            time.sleep(0.1)
        print(f"Activated: {activated}/{len(workflow_ids)}")


if __name__ == '__main__':
    main()
