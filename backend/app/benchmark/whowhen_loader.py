"""Who&When Dataset Loader for benchmarking.

Downloads and parses the Who&When multi-agent failure attribution
benchmark from the ICML 2025 Spotlight paper.

Data source: https://github.com/ag2ai/Agents_Failure_Attribution
Contains 127 hand-crafted + 126 algorithm-generated failure logs
with ground-truth failure attribution (which agent, which step).
"""

import json
import logging
import os
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pisama detectors applicable to Who&When multi-agent conversations
# ---------------------------------------------------------------------------

WHOWHEN_DETECTORS = [
    "coordination",
    "communication",
    "derailment",
    "loop",
    "context",
    "hallucination",
]

# Paper baselines (o1 all-at-once, Table 2)
PAPER_BASELINES = {
    "o1_all_at_once": {"agent_accuracy": 0.535, "step_accuracy": 0.142},
    "o1_step_by_step": {"agent_accuracy": 0.437, "step_accuracy": 0.091},
    "o1_binary_search": {"agent_accuracy": 0.480, "step_accuracy": 0.114},
    "gpt4o_all_at_once": {"agent_accuracy": 0.449, "step_accuracy": 0.087},
    "claude_sonnet_all_at_once": {"agent_accuracy": 0.421, "step_accuracy": 0.079},
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class WhoWhenMessage:
    """Single message in a Who&When conversation history."""

    content: str
    role: str  # agent name or "human"
    step_index: int


@dataclass
class WhoWhenCase:
    """A single Who&When benchmark case with ground-truth attribution."""

    case_id: str
    history: List[WhoWhenMessage]
    question: str
    ground_truth: str
    is_corrected: bool
    mistake_agent: str
    mistake_step: int
    mistake_reason: str
    source: str  # "hand-crafted" or "algorithm-generated"


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class WhoWhenDataLoader:
    """Download and load the Who&When benchmark dataset from GitHub."""

    REPO = "ag2ai/Agents_Failure_Attribution"
    CACHE_DIR = Path("data/whowhen")

    # GitHub raw content base URL
    RAW_BASE = "https://raw.githubusercontent.com/ag2ai/Agents_Failure_Attribution/main"

    # API URL for listing directory contents
    API_BASE = "https://api.github.com/repos/ag2ai/Agents_Failure_Attribution/contents"

    # Subdirectories in the repo
    SUBDIRS = {
        "hand-crafted": "Who%26When/Hand-Crafted",
        "algorithm-generated": "Who%26When/Algorithm-Generated",
    }

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = Path(cache_dir) if cache_dir else self.CACHE_DIR
        self._cases: List[WhoWhenCase] = []
        self._loaded = False

    def download(self) -> Path:
        """Download Who&When JSON files from GitHub.

        Returns:
            Path to the downloaded data directory.
        """
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        for source_name, subdir in self.SUBDIRS.items():
            dest_dir = self.cache_dir / source_name
            dest_dir.mkdir(parents=True, exist_ok=True)

            logger.info("Downloading %s cases...", source_name)
            files = self._list_github_files(subdir)
            downloaded = 0

            for filename, download_url in files:
                if not filename.endswith(".json"):
                    continue
                dest_path = dest_dir / filename
                if dest_path.exists():
                    logger.debug("Already cached: %s", dest_path)
                    downloaded += 1
                    continue

                try:
                    self._download_file(download_url, dest_path)
                    downloaded += 1
                except Exception as exc:
                    logger.warning(
                        "Failed to download %s: %s", filename, exc
                    )

            logger.info(
                "Downloaded %d %s files to %s",
                downloaded, source_name, dest_dir,
            )

        return self.cache_dir

    def _list_github_files(self, subdir: str) -> List[tuple]:
        """List JSON files in a GitHub repo subdirectory.

        Returns list of (filename, download_url) tuples.
        """
        url = f"{self.API_BASE}/{subdir}"
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github.v3+json")
        req.add_header("User-Agent", "Pisama-Benchmark/1.0")

        # Use GitHub token if available for rate limit
        gh_token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
        if gh_token:
            req.add_header("Authorization", f"token {gh_token}")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                entries = json.loads(resp.read())
        except Exception as exc:
            logger.warning(
                "GitHub API failed for %s (%s), trying raw URLs", subdir, exc
            )
            return self._fallback_file_list(subdir)

        files = []
        for entry in entries:
            if isinstance(entry, dict) and entry.get("name", "").endswith(".json"):
                files.append((
                    entry["name"],
                    entry.get("download_url", ""),
                ))

        return files

    def _fallback_file_list(self, subdir: str) -> List[tuple]:
        """Fallback: generate URLs for known file patterns.

        Who&When files use hash-based names, so we can't easily guess them.
        This fallback tries cloning via git if available.
        """
        import subprocess

        clone_dir = self.cache_dir / "_repo"
        if not clone_dir.exists():
            logger.info("Cloning repository for file listing...")
            try:
                subprocess.run(
                    [
                        "git", "clone", "--depth", "1", "--filter=blob:none",
                        "--sparse", f"https://github.com/{self.REPO}.git",
                        str(clone_dir),
                    ],
                    check=True, capture_output=True, timeout=120,
                )
                # Sparse checkout the Who&When directory
                subprocess.run(
                    ["git", "sparse-checkout", "set", "Who&When"],
                    cwd=str(clone_dir),
                    check=True, capture_output=True, timeout=30,
                )
            except (subprocess.CalledProcessError, FileNotFoundError) as exc:
                logger.error("Git clone failed: %s", exc)
                return []

        # Decode subdir (URL-encoded)
        decoded_subdir = subdir.replace("%26", "&")
        repo_subdir = clone_dir / decoded_subdir
        if not repo_subdir.exists():
            return []

        files = []
        for p in repo_subdir.glob("*.json"):
            raw_url = (
                f"{self.RAW_BASE}/{decoded_subdir}/{p.name}"
            )
            files.append((p.name, raw_url))

        return files

    def _download_file(self, url: str, dest: Path) -> None:
        """Download a single file."""
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Pisama-Benchmark/1.0")

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()

        with open(dest, "wb") as f:
            f.write(data)

    def load(self, data_path: Optional[Path] = None) -> int:
        """Load cases from downloaded Who&When JSON files.

        Args:
            data_path: Override path (directory). Defaults to cache_dir.

        Returns:
            Number of cases loaded.
        """
        path = Path(data_path) if data_path else self.cache_dir
        if not path.exists():
            raise FileNotFoundError(
                f"Who&When data not found at {path}. Run download() first."
            )

        self._cases = []

        for source_name in ["hand-crafted", "algorithm-generated"]:
            source_dir = path / source_name
            if not source_dir.exists():
                logger.warning("Source directory not found: %s", source_dir)
                continue

            for json_file in sorted(source_dir.glob("*.json")):
                try:
                    case = self._parse_case(json_file, source_name)
                    if case:
                        self._cases.append(case)
                except Exception as exc:
                    logger.warning(
                        "Failed to parse %s: %s", json_file.name, exc
                    )

        self._loaded = True
        logger.info("Loaded %d Who&When cases from %s", len(self._cases), path)
        return len(self._cases)

    def _parse_case(self, path: Path, source: str) -> Optional[WhoWhenCase]:
        """Parse a single Who&When JSON file into a WhoWhenCase."""
        with open(path) as f:
            raw = json.load(f)

        # Validate required fields
        history_raw = raw.get("history", [])
        if not history_raw:
            logger.debug("Skipping %s: empty history", path.name)
            return None

        mistake_agent = raw.get("mistake_agent", "")
        mistake_step = raw.get("mistake_step")
        if not mistake_agent or mistake_step is None:
            logger.debug("Skipping %s: missing attribution", path.name)
            return None

        # Parse history messages
        history = []
        for i, msg in enumerate(history_raw):
            if not isinstance(msg, dict):
                continue
            history.append(WhoWhenMessage(
                content=str(msg.get("content", "")),
                role=str(msg.get("role", "unknown")),
                step_index=i,
            ))

        case_id = raw.get("question_ID", path.stem)

        return WhoWhenCase(
            case_id=str(case_id),
            history=history,
            question=str(raw.get("question", "")),
            ground_truth=str(raw.get("ground_truth", "")),
            is_corrected=bool(raw.get("is_corrected", False)),
            mistake_agent=str(mistake_agent),
            mistake_step=int(mistake_step),
            mistake_reason=str(raw.get("mistake_reason", "")),
            source=source,
        )

    @property
    def cases(self) -> List[WhoWhenCase]:
        return self._cases

    def __iter__(self) -> Iterator[WhoWhenCase]:
        if not self._loaded:
            self.load()
        return iter(self._cases)

    def __len__(self) -> int:
        return len(self._cases)

    def filter_by_source(self, source: str) -> List[WhoWhenCase]:
        """Filter cases by source (hand-crafted or algorithm-generated)."""
        return [c for c in self._cases if c.source == source]

    def get_agents(self) -> Dict[str, int]:
        """Get frequency count of agent roles across all cases."""
        counts: Dict[str, int] = {}
        for case in self._cases:
            for msg in case.history:
                counts[msg.role] = counts.get(msg.role, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: -x[1]))

    def get_mistake_agents(self) -> Dict[str, int]:
        """Get frequency count of mistake agents across all cases."""
        counts: Dict[str, int] = {}
        for case in self._cases:
            counts[case.mistake_agent] = counts.get(case.mistake_agent, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: -x[1]))

    def get_statistics(self) -> Dict[str, Any]:
        """Get dataset statistics."""
        if not self._cases:
            return {"total": 0}

        by_source: Dict[str, int] = {}
        step_positions: List[int] = []
        history_lengths: List[int] = []

        for case in self._cases:
            by_source[case.source] = by_source.get(case.source, 0) + 1
            step_positions.append(case.mistake_step)
            history_lengths.append(len(case.history))

        return {
            "total_cases": len(self._cases),
            "by_source": by_source,
            "mistake_agents": self.get_mistake_agents(),
            "agent_roles": self.get_agents(),
            "avg_history_length": (
                sum(history_lengths) / len(history_lengths)
                if history_lengths else 0
            ),
            "avg_mistake_step": (
                sum(step_positions) / len(step_positions)
                if step_positions else 0
            ),
            "corrected_count": sum(
                1 for c in self._cases if c.is_corrected
            ),
        }
