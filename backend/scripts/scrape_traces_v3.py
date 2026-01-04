#!/usr/bin/env python3
"""
AI Agent Trace Scraper v3

Enhanced scraper with more sources and parallel processing.

Sources:
- GitHub (refined queries + known repos)
- HuggingFace (expanded datasets)
- OpenAI Evals (recursive navigation)
- Known agent trace repositories
- Kaggle datasets
- ArXiv paper data

Usage:
    python scripts/scrape_traces_v3.py --all --output traces/raw
"""

import os
import json
import asyncio
import hashlib
import re
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import time

import aiohttp
import aiofiles
from tqdm.asyncio import tqdm as atqdm
from tqdm import tqdm


@dataclass
class ScrapedTrace:
    source: str
    source_url: str
    framework: str
    content: dict
    content_hash: str
    scraped_at: str
    metadata: dict
    trace_type: str = "unknown"


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, calls_per_second: float = 1.0):
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0

    async def wait(self):
        now = time.time()
        elapsed = now - self.last_call
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
        self.last_call = time.time()


class GitHubScraper:
    """Enhanced GitHub scraper with known repos and better filtering."""

    SEARCH_QUERIES = [
        # Execution traces with timestamps/IDs
        '"run_id" "start_time" "end_time" extension:json',
        '"trace_id" "spans" extension:json',
        '"execution_order" "tool_calls" extension:json',

        # LangSmith/LangChain
        '"dotted_order" "trace_id" extension:json',
        'langsmith "run_type" "outputs" extension:json',
        '"parent_run_id" "child_runs" extension:json',

        # Function calling
        '"role": "assistant" "tool_calls" "id" extension:json',
        '"function_call" "arguments" "name" extension:json',
        '"choices" "message" "tool_calls" extension:json',

        # Framework-specific
        'autogen "sender" "receiver" "content" extension:json',
        'crewai "task_output" "agent" extension:json',
        'langgraph "checkpoint" "channel_values" extension:json',

        # ReAct patterns
        '"observation" "thought" "action" extension:json',
        '"intermediate_steps" "agent_outcome" extension:json',

        # File patterns
        'path:traces/ extension:json',
        'path:logs/ "agent" extension:jsonl',
        'filename:run_output extension:json',
    ]

    # Known repos with agent traces
    KNOWN_REPOS = [
        ("langchain-ai/langchain", "docs/docs/how_to"),
        ("langchain-ai/langgraph", "examples"),
        ("microsoft/autogen", "notebook"),
        ("joaomdmoura/crewAI", "docs"),
        ("run-llama/llama_index", "docs/docs/examples"),
        ("Significant-Gravitas/AutoGPT", "autogpts"),
        ("geekan/MetaGPT", "examples"),
        ("OpenBMB/AgentVerse", "agentverse"),
    ]

    EXECUTION_PATTERNS = [
        r'"run_id":\s*"[a-f0-9-]+"',
        r'"trace_id":\s*"[a-f0-9-]+"',
        r'"start_time":\s*"?\d',
        r'"timestamp":\s*"?\d',
        r'"tool_calls":\s*\[',
        r'"function_call":\s*\{',
        r'"outputs?":\s*[\{\[]',
        r'"observation":\s*"',
        r'"thought":\s*"',
        r'"messages":\s*\[.*"role"',
    ]

    EXCLUDE_PATTERNS = [
        r'"openapi":\s*"3\.',
        r'"swagger":\s*"2\.',
        r'"\$schema"',
        r'"definitions":\s*\{',
        r'package\.json',
        r'tsconfig\.json',
        r'"devDependencies"',
    ]

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"
        self.session = None
        self.rate_limiter = RateLimiter(calls_per_second=0.5)
        self.seen_hashes: Set[str] = set()

    async def search_code(self, query: str, per_page: int = 30) -> list:
        await self.rate_limiter.wait()
        url = "https://api.github.com/search/code"
        params = {"q": query, "per_page": per_page}

        try:
            async with self.session.get(url, headers=self.headers, params=params) as resp:
                if resp.status == 403:
                    print("Rate limited. Waiting 60s...")
                    await asyncio.sleep(60)
                    return []
                if resp.status != 200:
                    return []
                data = await resp.json()
                return data.get("items", [])
        except Exception as e:
            print(f"Search error: {e}")
            return []

    async def get_repo_contents(self, repo: str, path: str) -> list:
        """Get contents of a repo directory."""
        await self.rate_limiter.wait()
        url = f"https://api.github.com/repos/{repo}/contents/{path}"

        try:
            async with self.session.get(url, headers=self.headers) as resp:
                if resp.status != 200:
                    return []
                return await resp.json()
        except:
            return []

    async def download_file(self, url: str) -> Optional[str]:
        try:
            async with self.session.get(url, headers=self.headers) as resp:
                if resp.status == 200:
                    content = await resp.text()
                    if len(content) > 5_000_000:
                        return None
                    return content
        except:
            pass
        return None

    def detect_framework(self, content: str, url: str) -> str:
        content_lower = content.lower()
        url_lower = url.lower()

        if "langsmith" in content_lower or "dotted_order" in content_lower:
            return "langsmith"
        if "langgraph" in url_lower or "langgraph" in content_lower:
            return "langgraph"
        if "langchain" in url_lower or "langchain" in content_lower:
            return "langchain"
        if "autogen" in url_lower or "autogen" in content_lower:
            return "autogen"
        if "crewai" in url_lower or "crewai" in content_lower:
            return "crewai"
        if "llamaindex" in url_lower or "llama_index" in content_lower:
            return "llamaindex"
        if "metagpt" in url_lower or "metagpt" in content_lower:
            return "metagpt"
        if "autogpt" in url_lower:
            return "autogpt"
        if "observation" in content_lower and "thought" in content_lower:
            return "react"
        if "tool_calls" in content_lower or "function_call" in content_lower:
            return "openai"
        if "anthropic" in content_lower or "claude" in content_lower:
            return "anthropic"
        return "unknown"

    def classify_trace_type(self, content: str) -> str:
        content_lower = content.lower()

        if "tool_calls" in content_lower or "function_call" in content_lower:
            return "function_call"
        if "observation" in content_lower and "thought" in content_lower:
            return "react_trace"
        if "spans" in content_lower and "trace_id" in content_lower:
            return "otel_trace"
        if "checkpoint" in content_lower:
            return "state_trace"
        if "task_output" in content_lower:
            return "task_execution"
        if '"messages"' in content_lower and '"role"' in content_lower:
            return "conversation"
        return "execution"

    def is_execution_trace(self, content: str) -> bool:
        for pattern in self.EXCLUDE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return False
        matches = sum(1 for p in self.EXECUTION_PATTERNS if re.search(p, content))
        return matches >= 2

    async def scrape_known_repos(self) -> list:
        """Scrape known repos with agent examples."""
        traces = []

        for repo, path in tqdm(self.KNOWN_REPOS, desc="Known repos"):
            contents = await self.get_repo_contents(repo, path)

            for item in contents:
                if item.get("type") != "file":
                    continue
                name = item.get("name", "")
                if not (name.endswith(".json") or name.endswith(".jsonl")):
                    continue

                download_url = item.get("download_url")
                if not download_url:
                    continue

                content = await self.download_file(download_url)
                if not content or not self.is_execution_trace(content):
                    continue

                content_hash = hashlib.md5(content.encode()).hexdigest()
                if content_hash in self.seen_hashes:
                    continue
                self.seen_hashes.add(content_hash)

                try:
                    if name.endswith(".jsonl"):
                        lines = [json.loads(l) for l in content.strip().split("\n") if l.strip()]
                        parsed = {"entries": lines}
                    else:
                        parsed = json.loads(content)
                except:
                    continue

                traces.append(ScrapedTrace(
                    source="github_repo",
                    source_url=item.get("html_url", ""),
                    framework=self.detect_framework(content, item.get("html_url", "")),
                    content=parsed,
                    content_hash=content_hash,
                    scraped_at=datetime.now(timezone.utc).isoformat(),
                    metadata={"repo": repo, "path": item.get("path", "")},
                    trace_type=self.classify_trace_type(content)
                ))

        return traces

    async def scrape(self, output_dir: Path, max_per_query: int = 30) -> list:
        traces = []

        async with aiohttp.ClientSession() as session:
            self.session = session

            # Search queries
            for query in tqdm(self.SEARCH_QUERIES, desc="GitHub queries"):
                items = await self.search_code(query, per_page=max_per_query)

                for item in items:
                    html_url = item.get("html_url", "")
                    raw_url = html_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

                    content = await self.download_file(raw_url)
                    if not content or not self.is_execution_trace(content):
                        continue

                    content_hash = hashlib.md5(content.encode()).hexdigest()
                    if content_hash in self.seen_hashes:
                        continue
                    self.seen_hashes.add(content_hash)

                    try:
                        parsed = json.loads(content)
                    except:
                        try:
                            lines = [json.loads(l) for l in content.strip().split("\n") if l.strip()]
                            parsed = {"entries": lines}
                        except:
                            continue

                    traces.append(ScrapedTrace(
                        source="github",
                        source_url=html_url,
                        framework=self.detect_framework(content, html_url),
                        content=parsed,
                        content_hash=content_hash,
                        scraped_at=datetime.now(timezone.utc).isoformat(),
                        metadata={
                            "repo": item.get("repository", {}).get("full_name", ""),
                            "path": item.get("path", ""),
                            "query": query
                        },
                        trace_type=self.classify_trace_type(content)
                    ))

            # Known repos
            repo_traces = await self.scrape_known_repos()
            traces.extend(repo_traces)

        return traces


class HuggingFaceScraper:
    """Expanded HuggingFace scraper with more datasets."""

    DATASETS = [
        # Function calling
        ("glaiveai/glaive-function-calling-v2", "function_calling", "train"),
        ("NousResearch/hermes-function-calling-v1", "function_calling", "train"),
        ("Locutusque/function-calling-chatml", "function_calling", "train"),

        # Agent conversations
        ("Open-Orca/OpenOrca", "conversation", "train"),
        ("teknium/GPTeacher-General-Instruct", "conversation", "train"),
        ("WizardLM/WizardLM_evol_instruct_V2_196k", "conversation", "train"),
        ("cognitivecomputations/dolphin", "conversation", "train"),

        # ReAct / reasoning
        ("TIGER-Lab/MathInstruct", "react", "train"),
        ("lighteval/mmlu", "reasoning", "test"),

        # Code execution
        ("bigcode/self-oss-instruct-sc2-exec-filter-50k", "code_agent", "train"),
        ("m-a-p/CodeFeedback-Filtered-Instruction", "code_agent", "train"),
        ("sahil2801/CodeAlpaca-20k", "code_agent", "train"),

        # Tool use specific
        ("toolbench/ToolBench", "toolbench", "train"),
        ("hiyouga/glaive-function-calling-v2-sharegpt", "function_calling", "train"),

        # Multi-turn
        ("lmsys/lmsys-chat-1m", "multi_turn", "train"),
    ]

    def __init__(self):
        try:
            from datasets import load_dataset
            self.load_dataset = load_dataset
            self.available = True
        except ImportError:
            self.available = False

    def is_agent_trace(self, example: dict) -> bool:
        text = json.dumps(example).lower()
        strong = ["tool_call", "function_call", "observation", "action", "execute"]
        weak = ["tool", "function", "agent", "result", "output"]
        return sum(1 for s in strong if s in text) >= 1 or sum(1 for w in weak if w in text) >= 3

    def classify_trace(self, example: dict) -> str:
        text = json.dumps(example).lower()
        if "function_call" in text or "tool_call" in text:
            return "function_call"
        if "observation" in text and ("thought" in text or "action" in text):
            return "react"
        if "code" in text and ("execute" in text or "output" in text):
            return "code_execution"
        return "conversation"

    async def scrape(self, output_dir: Path, samples_per_dataset: int = 100) -> list:
        if not self.available:
            return []

        traces = []

        for dataset_name, category, split in tqdm(self.DATASETS, desc="HuggingFace"):
            try:
                ds = self.load_dataset(dataset_name, split=split, streaming=True)

                count = 0
                for example in ds:
                    if count >= samples_per_dataset:
                        break
                    if not self.is_agent_trace(example):
                        continue

                    content_str = json.dumps(example, default=str)
                    traces.append(ScrapedTrace(
                        source="huggingface",
                        source_url=f"https://huggingface.co/datasets/{dataset_name}",
                        framework=category,
                        content=example,
                        content_hash=hashlib.md5(content_str.encode()).hexdigest(),
                        scraped_at=datetime.now(timezone.utc).isoformat(),
                        metadata={"dataset": dataset_name, "category": category},
                        trace_type=self.classify_trace(example)
                    ))
                    count += 1

            except Exception as e:
                print(f"Failed: {dataset_name}: {e}")
                continue

        return traces


class OpenAIEvalsScraper:
    """Fixed OpenAI Evals scraper with recursive navigation."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"
        self.session = None
        self.rate_limiter = RateLimiter(calls_per_second=2)

    async def list_directory(self, path: str) -> list:
        await self.rate_limiter.wait()
        url = f"https://api.github.com/repos/openai/evals/contents/{path}"

        try:
            async with self.session.get(url, headers=self.headers) as resp:
                if resp.status != 200:
                    return []
                return await resp.json()
        except:
            return []

    async def download_file(self, url: str) -> Optional[str]:
        try:
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    return await resp.text()
        except:
            pass
        return None

    async def scrape_directory(self, path: str, max_files: int = 100) -> list:
        """Recursively scrape a directory for JSONL files."""
        traces = []
        files_found = 0

        items = await self.list_directory(path)

        for item in items:
            if files_found >= max_files:
                break

            if item.get("type") == "dir":
                # Recursively scrape subdirectories
                subtraces = await self.scrape_directory(item["path"], max_files - files_found)
                traces.extend(subtraces)
                files_found += len(subtraces)

            elif item.get("type") == "file" and item.get("name", "").endswith(".jsonl"):
                download_url = item.get("download_url")
                if not download_url:
                    continue

                content = await self.download_file(download_url)
                if not content:
                    continue

                try:
                    lines = [json.loads(l) for l in content.strip().split("\n") if l.strip()]

                    # Sample up to 5 per file
                    for i, line in enumerate(lines[:5]):
                        traces.append(ScrapedTrace(
                            source="openai_evals",
                            source_url=item.get("html_url", ""),
                            framework="openai",
                            content=line,
                            content_hash=hashlib.md5(json.dumps(line).encode()).hexdigest(),
                            scraped_at=datetime.now(timezone.utc).isoformat(),
                            metadata={"eval_name": item.get("name", ""), "index": i},
                            trace_type="eval"
                        ))
                    files_found += 1
                except:
                    continue

        return traces

    async def scrape(self, output_dir: Path, max_evals: int = 100) -> list:
        async with aiohttp.ClientSession() as session:
            self.session = session
            print("Scraping OpenAI Evals (recursive)...")
            traces = await self.scrape_directory("evals/registry/data", max_files=max_evals)
        return traces


class KnownReposScraper:
    """Scrape specific files from known agent repos."""

    TRACE_FILES = [
        # LangChain examples
        ("langchain-ai/langchain", "docs/docs/how_to/tool_calling.ipynb"),
        ("langchain-ai/langchain", "docs/docs/how_to/agent_executor.ipynb"),

        # LangGraph examples
        ("langchain-ai/langgraph", "docs/docs/tutorials/rag/langgraph_agentic_rag.ipynb"),

        # AutoGen examples
        ("microsoft/autogen", "notebook/agentchat_auto_feedback_from_code_execution.ipynb"),

        # CrewAI examples
        ("joaomdmoura/crewAI-examples", "landing_page_generator/main.py"),
    ]

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.headers = {"Accept": "application/vnd.github.v3.raw"}
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"
        self.session = None

    async def download_file(self, repo: str, path: str) -> Optional[str]:
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        try:
            async with self.session.get(url, headers=self.headers) as resp:
                if resp.status == 200:
                    return await resp.text()
        except:
            pass
        return None

    def extract_json_from_notebook(self, content: str) -> list:
        """Extract JSON blocks from Jupyter notebook."""
        try:
            nb = json.loads(content)
            json_blocks = []

            for cell in nb.get("cells", []):
                if cell.get("cell_type") == "code":
                    source = "".join(cell.get("source", []))
                    # Look for JSON in outputs
                    for output in cell.get("outputs", []):
                        if "text" in output:
                            text = "".join(output.get("text", []))
                            try:
                                parsed = json.loads(text)
                                json_blocks.append(parsed)
                            except:
                                pass
            return json_blocks
        except:
            return []

    async def scrape(self, output_dir: Path) -> list:
        traces = []

        async with aiohttp.ClientSession() as session:
            self.session = session

            for repo, path in tqdm(self.TRACE_FILES, desc="Known files"):
                content = await self.download_file(repo, path)
                if not content:
                    continue

                if path.endswith(".ipynb"):
                    json_blocks = self.extract_json_from_notebook(content)
                    for i, block in enumerate(json_blocks):
                        traces.append(ScrapedTrace(
                            source="notebook",
                            source_url=f"https://github.com/{repo}/blob/main/{path}",
                            framework=repo.split("/")[0],
                            content=block,
                            content_hash=hashlib.md5(json.dumps(block).encode()).hexdigest(),
                            scraped_at=datetime.now(timezone.utc).isoformat(),
                            metadata={"repo": repo, "path": path, "block": i},
                            trace_type="notebook_output"
                        ))

                await asyncio.sleep(0.5)

        return traces


class AnthropicDataScraper:
    """Scrape Anthropic's public datasets and examples."""

    REPOS = [
        ("anthropics/anthropic-cookbook", "misc"),
        ("anthropics/courses", "tool_use"),
    ]

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"
        self.session = None

    async def get_contents(self, repo: str, path: str) -> list:
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        try:
            async with self.session.get(url, headers=self.headers) as resp:
                if resp.status == 200:
                    return await resp.json()
        except:
            pass
        return []

    async def download_file(self, url: str) -> Optional[str]:
        try:
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    return await resp.text()
        except:
            pass
        return None

    async def scrape(self, output_dir: Path) -> list:
        traces = []

        async with aiohttp.ClientSession() as session:
            self.session = session

            for repo, path in tqdm(self.REPOS, desc="Anthropic repos"):
                contents = await self.get_contents(repo, path)

                for item in contents:
                    if item.get("type") != "file":
                        continue
                    name = item.get("name", "")
                    if not name.endswith((".json", ".jsonl", ".ipynb")):
                        continue

                    download_url = item.get("download_url")
                    if not download_url:
                        continue

                    content = await self.download_file(download_url)
                    if not content:
                        continue

                    try:
                        if name.endswith(".ipynb"):
                            # Parse notebook
                            nb = json.loads(content)
                            for cell in nb.get("cells", []):
                                outputs = cell.get("outputs", [])
                                for output in outputs:
                                    if "text" in output:
                                        text = "".join(output.get("text", []))
                                        try:
                                            parsed = json.loads(text)
                                            traces.append(ScrapedTrace(
                                                source="anthropic",
                                                source_url=item.get("html_url", ""),
                                                framework="anthropic",
                                                content=parsed,
                                                content_hash=hashlib.md5(json.dumps(parsed).encode()).hexdigest(),
                                                scraped_at=datetime.now(timezone.utc).isoformat(),
                                                metadata={"repo": repo, "file": name},
                                                trace_type="notebook_output"
                                            ))
                                        except:
                                            pass
                        else:
                            parsed = json.loads(content)
                            traces.append(ScrapedTrace(
                                source="anthropic",
                                source_url=item.get("html_url", ""),
                                framework="anthropic",
                                content=parsed,
                                content_hash=hashlib.md5(content.encode()).hexdigest(),
                                scraped_at=datetime.now(timezone.utc).isoformat(),
                                metadata={"repo": repo, "file": name},
                                trace_type="example"
                            ))
                    except:
                        continue

                    await asyncio.sleep(0.3)

        return traces


class ResearchDatasetScraper:
    """Scrape agent traces from research repositories."""

    DATASETS = [
        {
            "name": "AgentBench",
            "repo": "THUDM/AgentBench",
            "paths": ["data/os_interaction", "data/webshop", "data/alfworld"],
        },
        {
            "name": "ToolBench",
            "repo": "OpenBMB/ToolBench",
            "paths": ["data/instruction", "data/answer"],
        },
        {
            "name": "APIBank",
            "repo": "AlibabaResearch/DAMO-ConvAI",
            "paths": ["api-bank/data"],
        },
        {
            "name": "AgentInstruct",
            "repo": "THUDM/AgentTuning",
            "paths": ["data"],
        },
    ]

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"
        self.session = None
        self.rate_limiter = RateLimiter(calls_per_second=1)

    async def get_contents(self, repo: str, path: str) -> list:
        await self.rate_limiter.wait()
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        try:
            async with self.session.get(url, headers=self.headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data if isinstance(data, list) else []
        except:
            pass
        return []

    async def download_file(self, url: str) -> Optional[str]:
        try:
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    content = await resp.text()
                    if len(content) < 10_000_000:
                        return content
        except:
            pass
        return None

    async def scrape(self, output_dir: Path, samples_per_file: int = 20) -> list:
        traces = []

        async with aiohttp.ClientSession() as session:
            self.session = session

            for dataset in tqdm(self.DATASETS, desc="Research datasets"):
                for path in dataset["paths"]:
                    contents = await self.get_contents(dataset["repo"], path)

                    for item in contents[:10]:  # Limit files per path
                        if item.get("type") != "file":
                            continue
                        name = item.get("name", "")
                        if not name.endswith((".json", ".jsonl")):
                            continue

                        download_url = item.get("download_url")
                        if not download_url:
                            continue

                        content = await self.download_file(download_url)
                        if not content:
                            continue

                        try:
                            if name.endswith(".jsonl"):
                                lines = [json.loads(l) for l in content.strip().split("\n") if l.strip()]
                                items = lines[:samples_per_file]
                            else:
                                parsed = json.loads(content)
                                items = parsed if isinstance(parsed, list) else [parsed]
                                items = items[:samples_per_file]

                            for i, item_data in enumerate(items):
                                traces.append(ScrapedTrace(
                                    source="research",
                                    source_url=item.get("html_url", ""),
                                    framework=dataset["name"].lower(),
                                    content=item_data,
                                    content_hash=hashlib.md5(json.dumps(item_data, default=str).encode()).hexdigest(),
                                    scraped_at=datetime.now(timezone.utc).isoformat(),
                                    metadata={
                                        "dataset": dataset["name"],
                                        "file": name,
                                        "index": i
                                    },
                                    trace_type="benchmark"
                                ))
                        except Exception as e:
                            continue

        return traces


async def main():
    parser = argparse.ArgumentParser(description="AI Agent Trace Scraper v3")
    parser.add_argument("--output", "-o", default="traces/raw", help="Output directory")
    parser.add_argument("--github", action="store_true", help="Scrape GitHub")
    parser.add_argument("--huggingface", action="store_true", help="Scrape HuggingFace")
    parser.add_argument("--openai-evals", action="store_true", help="Scrape OpenAI Evals")
    parser.add_argument("--anthropic", action="store_true", help="Scrape Anthropic repos")
    parser.add_argument("--research", action="store_true", help="Scrape research datasets")
    parser.add_argument("--notebooks", action="store_true", help="Scrape known notebooks")
    parser.add_argument("--all", action="store_true", help="Scrape all sources")
    parser.add_argument("--max-per-query", type=int, default=30)
    parser.add_argument("--samples-per-dataset", type=int, default=100)

    args = parser.parse_args()

    if args.all:
        args.github = args.huggingface = args.openai_evals = True
        args.anthropic = args.research = args.notebooks = True

    sources = [args.github, args.huggingface, args.openai_evals,
               args.anthropic, args.research, args.notebooks]

    if not any(sources):
        print("No sources specified. Use --all or specific flags.")
        return

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_traces = []

    if args.github:
        print("\n=== GitHub (enhanced) ===")
        scraper = GitHubScraper()
        traces = await scraper.scrape(output_dir, max_per_query=args.max_per_query)
        print(f"Found {len(traces)} traces")
        all_traces.extend(traces)

    if args.huggingface:
        print("\n=== HuggingFace (expanded) ===")
        scraper = HuggingFaceScraper()
        traces = await scraper.scrape(output_dir, samples_per_dataset=args.samples_per_dataset)
        print(f"Found {len(traces)} traces")
        all_traces.extend(traces)

    if args.openai_evals:
        print("\n=== OpenAI Evals (recursive) ===")
        scraper = OpenAIEvalsScraper()
        traces = await scraper.scrape(output_dir, max_evals=50)
        print(f"Found {len(traces)} traces")
        all_traces.extend(traces)

    if args.anthropic:
        print("\n=== Anthropic ===")
        scraper = AnthropicDataScraper()
        traces = await scraper.scrape(output_dir)
        print(f"Found {len(traces)} traces")
        all_traces.extend(traces)

    if args.research:
        print("\n=== Research Datasets ===")
        scraper = ResearchDatasetScraper()
        traces = await scraper.scrape(output_dir)
        print(f"Found {len(traces)} traces")
        all_traces.extend(traces)

    if args.notebooks:
        print("\n=== Known Notebooks ===")
        scraper = KnownReposScraper()
        traces = await scraper.scrape(output_dir)
        print(f"Found {len(traces)} traces")
        all_traces.extend(traces)

    # Deduplicate
    seen = set()
    unique = []
    for t in all_traces:
        if t.content_hash not in seen:
            seen.add(t.content_hash)
            unique.append(t)

    print(f"\n=== Total: {len(unique)} unique traces ===")

    # Save
    output_file = output_dir / f"traces_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    async with aiofiles.open(output_file, "w") as f:
        for trace in unique:
            await f.write(json.dumps(asdict(trace)) + "\n")

    print(f"Saved to: {output_file}")

    # Summary
    by_source = {}
    by_framework = {}
    by_type = {}

    for t in unique:
        by_source[t.source] = by_source.get(t.source, 0) + 1
        by_framework[t.framework] = by_framework.get(t.framework, 0) + 1
        by_type[t.trace_type] = by_type.get(t.trace_type, 0) + 1

    print("\nBy source:")
    for k, v in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    print("\nBy framework:")
    for k, v in sorted(by_framework.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    print("\nBy type:")
    for k, v in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    asyncio.run(main())
