#!/usr/bin/env python3
"""
Update PISAMA Launch Tracker Google Sheet with completed tasks.

Sheet: https://docs.google.com/spreadsheets/d/1L4XyGBMk50mz_D4fZJbb6_sMWikfWClEIEd9DFjrOto
"""

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os

# Google Sheets configuration
SHEET_ID = "1L4XyGBMk50mz_D4fZJbb6_sMWikfWClEIEd9DFjrOto"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Service account email: github-actions@ai-discovery-469923.iam.gserviceaccount.com
# Credentials should be at: ~/github-actions-key.json or ~/.gcp/ or ~/gcp-backup/


def get_credentials():
    """Load service account credentials."""
    possible_paths = [
        os.path.expanduser("~/.gcp/ai-discovery-key.json"),
        os.path.expanduser("~/gcp-backup/ai-discovery-key.json"),
        os.path.expanduser("~/github-actions-key.json"),
    ]

    for path in possible_paths:
        if os.path.exists(path):
            print(f"✓ Found credentials at: {path}")
            return Credentials.from_service_account_file(path, scopes=SCOPES)

    raise FileNotFoundError(
        f"Service account credentials not found. Tried:\n" +
        "\n".join(f"  - {p}" for p in possible_paths)
    )


def update_tasks(dry_run=False):
    """Update completed tasks in Google Sheet."""

    # Tasks to mark as complete
    completed_tasks = [
        {
            "id": "PIS-W3-4-G-017",
            "status": "Done",
            "notes": "Hero section expanded, social proof added, demo video component created. Files: HeroSection.tsx, SocialProof.tsx, DemoVideo.tsx"
        },
        {
            "id": "PIS-W3-4-G-018",
            "status": "Done",
            "notes": "Full comparison table vs LangSmith, Langfuse, AgentOps. 4 categories: Detection, Remediation, Frameworks, Deployment. File: ComparisonTable.tsx"
        },
        {
            "id": "PIS-W3-4-G-019",
            "status": "Done",
            "notes": "8 FAQ questions with accordion UI. Topics: competitors, frameworks, overhead, privacy, limits. File: FAQSection.tsx"
        },
        {
            "id": "PIS-W3-4-G-020",
            "status": "Done",
            "notes": "Resend API integration complete. Files: /api/subscribe/route.ts, EmailCapture.tsx, WaitlistModal.tsx. Welcome email automation added."
        },
    ]

    if dry_run:
        print("\n🔍 DRY RUN - Would update these tasks:\n")
        for task in completed_tasks:
            print(f"  {task['id']}: {task['status']}")
            print(f"  └─ {task['notes']}\n")
        return

    # Connect to Google Sheets
    print("Connecting to Google Sheets...")
    creds = get_credentials()
    client = gspread.authorize(creds)

    # Open the sheet
    sheet = client.open_by_key(SHEET_ID)
    tasks_worksheet = sheet.worksheet("Tasks")

    # Get all task data
    print("Reading task data...")
    all_rows = tasks_worksheet.get_all_values()
    header = all_rows[0]

    # Find column indices
    id_col = header.index("Task ID") if "Task ID" in header else 0
    status_col = header.index("Status") if "Status" in header else 5
    notes_col = header.index("Notes") if "Notes" in header else 7

    print(f"Columns: ID={id_col}, Status={status_col}, Notes={notes_col}")

    # Update each completed task
    updates = []
    for task in completed_tasks:
        task_id = task["id"]

        # Find the row for this task
        for row_idx, row in enumerate(all_rows[1:], start=2):  # Start from row 2 (skip header)
            if row[id_col] == task_id:
                print(f"\n✓ Found {task_id} at row {row_idx}")
                print(f"  Current status: {row[status_col]}")
                print(f"  New status: {task['status']}")

                # Update status
                tasks_worksheet.update_cell(row_idx, status_col + 1, task["status"])

                # Update notes
                tasks_worksheet.update_cell(row_idx, notes_col + 1, task["notes"])

                updates.append(task_id)
                break
        else:
            print(f"⚠️  Warning: Task {task_id} not found in sheet")

    print(f"\n✅ Updated {len(updates)} tasks: {', '.join(updates)}")
    print(f"\n📊 View updated sheet: https://docs.google.com/spreadsheets/d/{SHEET_ID}")


if __name__ == "__main__":
    import sys

    dry_run = "--dry-run" in sys.argv

    try:
        update_tasks(dry_run=dry_run)
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        print("\nTo fix this, ensure you have service account credentials at one of:")
        print("  - ~/.gcp/ai-discovery-key.json")
        print("  - ~/gcp-backup/ai-discovery-key.json")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error updating sheet: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
