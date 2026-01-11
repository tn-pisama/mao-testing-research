"""Git backup service for workflow state preservation.

Creates Git commits before applying fixes, enabling rollback on failure.
Designed for solo developers who want safe, automatic fix application.
"""

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class GitBackupConfig:
    """Configuration for Git backup service."""
    repo_path: str = "~/n8n-workflows-backup"
    auto_create_repo: bool = True
    commit_message_prefix: str = "[mao-healer]"
    max_backups_per_workflow: int = 50


@dataclass
class BackupRecord:
    """Record of a backup operation."""
    commit_sha: str
    workflow_id: str
    workflow_name: str
    backed_up_at: datetime
    file_path: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "commit_sha": self.commit_sha,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "backed_up_at": self.backed_up_at.isoformat(),
            "file_path": self.file_path,
            "message": self.message,
        }


class GitBackupService:
    """
    Service for backing up n8n workflows to a local Git repository.

    Creates a commit before each fix application, enabling:
    - Easy rollback to pre-fix state
    - History of all workflow changes
    - Diff viewing for fix analysis

    Usage:
        config = GitBackupConfig(repo_path="~/n8n-backup")
        service = GitBackupService(config)

        # Backup before fix
        sha = await service.backup_workflow("workflow_123", n8n_client)

        # Apply fix...

        # Rollback if needed
        await service.rollback_to(sha, "workflow_123", n8n_client)
    """

    def __init__(self, config: Optional[GitBackupConfig] = None):
        self.config = config or GitBackupConfig()
        self._repo_path = Path(self.config.repo_path).expanduser()
        self._backup_history: List[BackupRecord] = []
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize the Git repository if needed."""
        if self._initialized:
            return True

        try:
            if not self._repo_path.exists():
                if not self.config.auto_create_repo:
                    logger.error(f"Backup repo does not exist: {self._repo_path}")
                    return False

                self._repo_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created backup directory: {self._repo_path}")

            # Initialize git repo if not already initialized
            git_dir = self._repo_path / ".git"
            if not git_dir.exists():
                self._run_git("init")
                self._run_git("config", "user.email", "mao-healer@local")
                self._run_git("config", "user.name", "MAO Healer")
                logger.info(f"Initialized Git repo at {self._repo_path}")

            self._initialized = True
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Git repo: {e}")
            return False

    async def backup_workflow(
        self,
        workflow_id: str,
        n8n_client: Any,
        reason: str = "pre-fix backup",
    ) -> str:
        """
        Export workflow from n8n and commit to Git.

        Args:
            workflow_id: The n8n workflow ID
            n8n_client: n8n API client
            reason: Reason for backup (included in commit message)

        Returns:
            Git commit SHA

        Raises:
            Exception if backup fails
        """
        await self.initialize()

        # Export workflow from n8n
        workflow = await n8n_client.get_workflow(workflow_id)
        workflow_name = workflow.get("name", f"workflow_{workflow_id}")

        # Create workflow directory
        workflow_dir = self._repo_path / "workflows"
        workflow_dir.mkdir(exist_ok=True)

        # Write workflow to file
        safe_name = self._safe_filename(workflow_name)
        file_path = workflow_dir / f"{safe_name}_{workflow_id}.json"

        with open(file_path, "w") as f:
            json.dump(workflow, f, indent=2, default=str)

        # Stage and commit
        relative_path = file_path.relative_to(self._repo_path)
        self._run_git("add", str(relative_path))

        commit_message = f"{self.config.commit_message_prefix} {reason}: {workflow_name}"
        self._run_git("commit", "-m", commit_message)

        # Get commit SHA
        sha = self._run_git("rev-parse", "HEAD").strip()

        # Record backup
        record = BackupRecord(
            commit_sha=sha,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            backed_up_at=datetime.now(timezone.utc),
            file_path=str(file_path),
            message=commit_message,
        )
        self._backup_history.append(record)

        # Cleanup old backups
        await self._cleanup_old_backups(workflow_id)

        logger.info(f"Backed up workflow {workflow_name} at {sha[:8]}")
        return sha

    async def rollback_to(
        self,
        commit_sha: str,
        workflow_id: str,
        n8n_client: Any,
    ) -> bool:
        """
        Rollback a workflow to a previous Git commit state.

        Args:
            commit_sha: The commit SHA to rollback to
            workflow_id: The workflow ID
            n8n_client: n8n API client

        Returns:
            True if rollback succeeded
        """
        await self.initialize()

        try:
            # Find the backup record
            record = self._find_backup(commit_sha, workflow_id)
            if not record:
                logger.error(f"Backup record not found for {commit_sha}")
                return False

            # Get the workflow file content from that commit
            relative_path = Path(record.file_path).relative_to(self._repo_path)
            file_content = self._run_git("show", f"{commit_sha}:{relative_path}")

            # Parse workflow JSON
            workflow = json.loads(file_content)

            # Update workflow in n8n
            await n8n_client.update_workflow(workflow_id, workflow)

            logger.info(f"Rolled back workflow {workflow_id} to {commit_sha[:8]}")
            return True

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

    async def get_backup_history(
        self,
        workflow_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[BackupRecord]:
        """Get backup history, optionally filtered by workflow."""
        records = self._backup_history[-limit:]
        if workflow_id:
            records = [r for r in records if r.workflow_id == workflow_id]
        return records

    async def get_diff(
        self,
        commit_sha1: str,
        commit_sha2: str,
        workflow_id: str,
    ) -> str:
        """Get diff between two commits for a workflow."""
        await self.initialize()

        record = self._find_backup(commit_sha1, workflow_id)
        if not record:
            return ""

        relative_path = Path(record.file_path).relative_to(self._repo_path)

        try:
            diff = self._run_git("diff", commit_sha1, commit_sha2, "--", str(relative_path))
            return diff
        except Exception as e:
            logger.error(f"Failed to get diff: {e}")
            return ""

    async def list_backups(
        self,
        workflow_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """List available backups for a workflow from Git log."""
        await self.initialize()

        try:
            # Find workflow file
            workflow_dir = self._repo_path / "workflows"
            matching_files = list(workflow_dir.glob(f"*_{workflow_id}.json"))

            if not matching_files:
                return []

            file_path = matching_files[0]
            relative_path = file_path.relative_to(self._repo_path)

            # Get Git log for this file
            log_output = self._run_git(
                "log",
                f"--max-count={limit}",
                "--format=%H|%ci|%s",
                "--",
                str(relative_path),
            )

            backups = []
            for line in log_output.strip().split("\n"):
                if line:
                    parts = line.split("|", 2)
                    if len(parts) >= 3:
                        backups.append({
                            "commit_sha": parts[0],
                            "date": parts[1],
                            "message": parts[2],
                        })

            return backups

        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []

    async def _cleanup_old_backups(self, workflow_id: str) -> None:
        """Remove old backup commits to prevent repo bloat."""
        # For simplicity, we don't actually remove Git history
        # (that would require rewriting history which is complex)
        # Instead, we just limit the in-memory history
        workflow_backups = [
            r for r in self._backup_history
            if r.workflow_id == workflow_id
        ]

        if len(workflow_backups) > self.config.max_backups_per_workflow:
            # Keep only recent ones in memory
            self._backup_history = [
                r for r in self._backup_history
                if r.workflow_id != workflow_id
            ] + workflow_backups[-self.config.max_backups_per_workflow:]

    def _find_backup(self, commit_sha: str, workflow_id: str) -> Optional[BackupRecord]:
        """Find a backup record by commit SHA and workflow ID."""
        for record in reversed(self._backup_history):
            if record.commit_sha.startswith(commit_sha) and record.workflow_id == workflow_id:
                return record
        return None

    def _run_git(self, *args: str) -> str:
        """Run a Git command in the repo directory."""
        try:
            result = subprocess.run(
                ["git"] + list(args),
                cwd=str(self._repo_path),
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"Git command failed: git {' '.join(args)}")
            logger.error(f"stderr: {e.stderr}")
            raise

    def _safe_filename(self, name: str) -> str:
        """Convert a workflow name to a safe filename."""
        # Replace unsafe characters
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        # Limit length
        return safe[:50]


async def create_git_backup_service(
    repo_path: Optional[str] = None,
) -> GitBackupService:
    """Factory function to create a configured Git backup service."""
    config = GitBackupConfig()
    if repo_path:
        config.repo_path = repo_path

    service = GitBackupService(config)
    await service.initialize()
    return service
