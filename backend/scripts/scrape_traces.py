#!/usr/bin/env python3
"""
AI Agent Trace Scraper v2

Collects AI agent execution traces from multiple public sources:
- GitHub repositories (refined queries for actual traces)
- Hugging Face datasets (expanded)
- LangSmith public traces
- Weights & Biases public runs
- OpenAI Evals dataset
- Research paper datasets
- Documentation sites (via Firecrawl)

Usage:
    python scripts/scrape_traces.py --all --output traces/
    python scripts/scrape_traces.py --github --huggingface --output traces/

Requirements:
    pip install requests aiohttp aiofiles tqdm

Optional:
    pip install firecrawl-py datasets wandb
"""

import os
import json
import asyncio
import hashlib
import re
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict

import requests
import aiohttp
import aiofiles
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
    trace_type: str = "unknown"  # execution, conversation, function_call, etc.


class GitHubScraper:
    """Scrape actual execution trace files from GitHub repositories."""

    # Refined queries targeting actual execution logs, not configs
    SEARCH_QUERIES = [
        # Actual execution traces with specific patterns
        '"run_id" "start_time" "end_time" extension:json',
        '"trace_id" "spans" extension:json',
        '"execution_order" "tool_calls" extension:json',

        # LangSmith/LangChain traces
        '"dotted_order" "trace_id" extension:json',
        'langsmith "run_type" "outputs" extension:json',
        '"parent_run_id" "child_runs" extension:json',

        # OpenAI function calling traces
        '"role": "assistant" "tool_calls" "id" extension:json',
        '"function_call" "arguments" "name" extension:json',
        '"choices" "message" "tool_calls" extension:json',

        # AutoGen conversation logs
        'autogen "sender" "receiver" "content" extension:json',
        '"chat_history" "agent" "message" extension:json',

        # CrewAI task execution
        'crewai "task_output" "agent" extension:json',
        '"crew" "tasks" "agents" "result" extension:json',

        # LangGraph state traces
        'langgraph "checkpoint" "channel_values" extension:json',
        '"state" "next" "values" extension:json',

        # Generic agent execution patterns
        '"agent_response" "tool_result" extension:json',
        '"observation" "thought" "action" extension:json',  # ReAct
        '"intermediate_steps" "agent_outcome" extension:json',

        # Specific trace file patterns
        'filename:trace.json "messages"',
        'filename:execution_log.json',
        'filename:run_output.json',
        'path:traces/ extension:json',
        'path:logs/ "agent" extension:json',
    ]

    # Patterns that indicate actual execution (not config/schema)
    EXECUTION_PATTERNS = [
        r'"run_id":\s*"[a-f0-9-]+"',
        r'"trace_id":\s*"[a-f0-9-]+"',
        r'"start_time":\s*"?\d',
        r'"timestamp":\s*"?\d',
        r'"execution_order":\s*\d',
        r'"tool_calls":\s*\[',
        r'"function_call":\s*\{',
        r'"outputs?":\s*[\{\[]',
        r'"result":\s*[\{\[]',
        r'"observation":\s*"',
        r'"thought":\s*"',
    ]

    # Patterns that indicate config/schema (not execution)
    EXCLUDE_PATTERNS = [
        r'"openapi":\s*"3\.',
        r'"swagger":\s*"2\.',
        r'"$schema"',
        r'"definitions":\s*\{',
        r'"components":\s*\{.*"schemas"',
        r'package\.json',
        r'tsconfig\.json',
        r'"scripts":\s*\{.*"build"',
    ]

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.headers = {}
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"
        self.headers["Accept"] = "application/vnd.github.v3+json"
        self.session = None

    async def search_code(self, query: str, per_page: int = 30) -> list:
        """Search GitHub code for trace files."""
        url = "https://api.github.com/search/code"
        params = {"q": query, "per_page": per_page}

        async with self.session.get(url, headers=self.headers, params=params) as resp:
            if resp.status == 403:
                print("Rate limited. Waiting 60s...")
                await asyncio.sleep(60)
                return []
            if resp.status != 200:
                print(f"GitHub search failed: {resp.status}")
                return []

            data = await resp.json()
            return data.get("items", [])

    async def download_file(self, item: dict) -> Optional[str]:
        """Download raw file content from GitHub."""
        html_url = item.get("html_url", "")
        if not html_url:
            return None

        raw_url = html_url.replace(
            "github.com", "raw.githubusercontent.com"
        ).replace("/blob/", "/")

        try:
            async with self.session.get(raw_url, headers=self.headers) as resp:
                if resp.status == 200:
                    content = await resp.text()
                    # Skip very large files
                    if len(content) > 5_000_000:
                        return None
                    return content
        except Exception as e:
            print(f"Failed to download {raw_url}: {e}")

        return None

    def detect_framework(self, content: str, url: str) -> str:
        """Detect which framework the trace is from."""
        content_lower = content.lower()
        url_lower = url.lower()

        if "langsmith" in content_lower or "dotted_order" in content_lower:
            return "langsmith"
        if "langgraph" in url_lower or "langgraph" in content_lower or "checkpoint" in content_lower:
            return "langgraph"
        if "langchain" in url_lower or "langchain" in content_lower:
            return "langchain"
        if "autogen" in url_lower or "autogen" in content_lower:
            return "autogen"
        if "crewai" in url_lower or "crewai" in content_lower:
            return "crewai"
        if "openai" in content_lower and ("tool_calls" in content_lower or "function_call" in content_lower):
            return "openai"
        if "anthropic" in content_lower or "claude" in content_lower:
            return "anthropic"
        if "observation" in content_lower and "thought" in content_lower:
            return "react"

        return "unknown"

    def classify_trace_type(self, content: str) -> str:
        """Classify the type of trace."""
        content_lower = content.lower()

        if "tool_calls" in content_lower or "function_call" in content_lower:
            return "function_call"
        if "observation" in content_lower and "thought" in content_lower:
            return "react_trace"
        if "spans" in content_lower or "trace_id" in content_lower:
            return "otel_trace"
        if "chat_history" in content_lower or "messages" in content_lower:
            return "conversation"
        if "task_output" in content_lower:
            return "task_execution"
        if "checkpoint" in content_lower or "state" in content_lower:
            return "state_trace"

        return "execution"

    def is_execution_trace(self, content: str) -> bool:
        """Check if content is an actual execution trace (not config/schema)."""
        # Check for exclusion patterns first
        for pattern in self.EXCLUDE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return False

        # Count execution pattern matches
        matches = sum(1 for p in self.EXECUTION_PATTERNS if re.search(p, content))

        # Require at least 2 execution patterns
        return matches >= 2

    async def scrape(self, output_dir: Path, max_per_query: int = 30) -> list:
        """Run the GitHub scraper."""
        traces = []

        async with aiohttp.ClientSession() as session:
            self.session = session

            for query in tqdm(self.SEARCH_QUERIES, desc="GitHub queries"):
                items = await self.search_code(query, per_page=max_per_query)

                for item in items:
                    content = await self.download_file(item)
                    if not content:
                        continue

                    if not self.is_execution_trace(content):
                        continue

                    try:
                        parsed = json.loads(content)
                    except json.JSONDecodeError:
                        try:
                            lines = [json.loads(l) for l in content.strip().split("\n") if l.strip()]
                            if not lines:
                                continue
                            parsed = {"entries": lines}
                        except:
                            continue

                    trace = ScrapedTrace(
                        source="github",
                        source_url=item.get("html_url", ""),
                        framework=self.detect_framework(content, item.get("html_url", "")),
                        content=parsed,
                        content_hash=hashlib.md5(content.encode()).hexdigest(),
                        scraped_at=datetime.now(timezone.utc).isoformat(),
                        metadata={
                            "repo": item.get("repository", {}).get("full_name", ""),
                            "path": item.get("path", ""),
                            "query": query,
                        },
                        trace_type=self.classify_trace_type(content)
                    )
                    traces.append(trace)

                await asyncio.sleep(2)

        return traces


class HuggingFaceScraper:
    """Scrape traces from Hugging Face datasets - expanded list."""

    DATASETS = [
        # Function calling / Tool use
        ("glaiveai/glaive-function-calling-v2", "function_calling", "train"),
        ("NousResearch/hermes-function-calling-v1", "function_calling", "train"),
        ("gorilla-llm/Berkeley-Function-Calling-Leaderboard", "function_calling", "train"),

        # Agent conversations
        ("Open-Orca/OpenOrca", "conversation", "train"),
        ("teknium/GPTeacher-General-Instruct", "conversation", "train"),
        ("WizardLM/WizardLM_evol_instruct_V2_196k", "conversation", "train"),

        # ReAct / Chain of thought
        ("kaist-ai/CoT-Collection", "react", "train"),
        ("TIGER-Lab/MathInstruct", "react", "train"),

        # Code agents
        ("bigcode/self-oss-instruct-sc2-exec-filter-50k", "code_agent", "train"),
        ("m-a-p/CodeFeedback-Filtered-Instruction", "code_agent", "train"),

        # Multi-turn tool use
        ("Salesforce/dialogstudio", "multi_turn", "train"),

        # Agent benchmarks
        ("AgentBench/os_interaction", "agent_benchmark", "train"),
    ]

    def __init__(self):
        try:
            from datasets import load_dataset
            self.load_dataset = load_dataset
            self.available = True
        except ImportError:
            print("datasets library not installed. Run: pip install datasets")
            self.available = False

    def is_agent_trace(self, example: dict) -> bool:
        """Check if example looks like an agent trace."""
        text = json.dumps(example).lower()

        strong_indicators = ["tool_call", "function_call", "observation", "action"]
        weak_indicators = ["tool", "function", "agent", "execute", "result"]

        strong_matches = sum(1 for ind in strong_indicators if ind in text)
        weak_matches = sum(1 for ind in weak_indicators if ind in text)

        return strong_matches >= 1 or weak_matches >= 3

    def classify_trace(self, example: dict) -> str:
        """Classify the type of trace."""
        text = json.dumps(example).lower()

        if "function_call" in text or "tool_call" in text:
            return "function_call"
        if "observation" in text and "thought" in text:
            return "react"
        if "code" in text and ("execute" in text or "output" in text):
            return "code_execution"
        return "conversation"

    async def scrape(self, output_dir: Path, samples_per_dataset: int = 100) -> list:
        """Scrape traces from HuggingFace datasets."""
        if not self.available:
            return []

        traces = []

        for dataset_info in tqdm(self.DATASETS, desc="HuggingFace datasets"):
            dataset_name, category, split = dataset_info[:3]

            try:
                ds = self.load_dataset(dataset_name, split=split, streaming=True, trust_remote_code=True)

                count = 0
                for example in ds:
                    if count >= samples_per_dataset:
                        break

                    if not self.is_agent_trace(example):
                        continue

                    content_str = json.dumps(example)

                    trace = ScrapedTrace(
                        source="huggingface",
                        source_url=f"https://huggingface.co/datasets/{dataset_name}",
                        framework=category,
                        content=example,
                        content_hash=hashlib.md5(content_str.encode()).hexdigest(),
                        scraped_at=datetime.now(timezone.utc).isoformat(),
                        metadata={
                            "dataset": dataset_name,
                            "category": category,
                        },
                        trace_type=self.classify_trace(example)
                    )
                    traces.append(trace)
                    count += 1

            except Exception as e:
                print(f"Failed to load {dataset_name}: {e}")
                continue

        return traces


class OpenAIEvalsScraper:
    """Scrape from OpenAI Evals repository."""

    EVALS_BASE = "https://api.github.com/repos/openai/evals/contents"

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"
        self.session = None

    async def list_eval_files(self, path: str = "evals/registry/data") -> List[dict]:
        """List eval data files."""
        url = f"{self.EVALS_BASE}/{path}"

        async with self.session.get(url, headers=self.headers) as resp:
            if resp.status != 200:
                return []
            return await resp.json()

    async def download_eval(self, file_info: dict) -> Optional[str]:
        """Download an eval file."""
        if file_info.get("type") != "file":
            return None

        download_url = file_info.get("download_url")
        if not download_url:
            return None

        try:
            async with self.session.get(download_url) as resp:
                if resp.status == 200:
                    return await resp.text()
        except Exception as e:
            print(f"Failed to download eval: {e}")

        return None

    async def scrape(self, output_dir: Path, max_evals: int = 50) -> list:
        """Scrape OpenAI evals."""
        traces = []

        async with aiohttp.ClientSession() as session:
            self.session = session

            files = await self.list_eval_files()

            for file_info in tqdm(files[:max_evals], desc="OpenAI Evals"):
                if not file_info.get("name", "").endswith(".jsonl"):
                    continue

                content = await self.download_eval(file_info)
                if not content:
                    continue

                try:
                    lines = [json.loads(l) for l in content.strip().split("\n") if l.strip()]

                    for i, line in enumerate(lines[:10]):  # Sample 10 per file
                        trace = ScrapedTrace(
                            source="openai_evals",
                            source_url=file_info.get("html_url", ""),
                            framework="openai",
                            content=line,
                            content_hash=hashlib.md5(json.dumps(line).encode()).hexdigest(),
                            scraped_at=datetime.now(timezone.utc).isoformat(),
                            metadata={
                                "eval_name": file_info.get("name", ""),
                                "line_index": i,
                            },
                            trace_type="eval"
                        )
                        traces.append(trace)

                except Exception as e:
                    print(f"Failed to parse eval {file_info.get('name')}: {e}")
                    continue

                await asyncio.sleep(0.5)

        return traces


class WandBScraper:
    """Scrape from Weights & Biases public projects."""

    PUBLIC_PROJECTS = [
        "langchain-ai/langchain-benchmarks",
        "huggingface/evaluate",
        "openai/evals",
    ]

    def __init__(self):
        try:
            import wandb
            self.wandb = wandb
            self.available = True
        except ImportError:
            print("wandb not installed. Run: pip install wandb")
            self.available = False

    async def scrape(self, output_dir: Path, runs_per_project: int = 20) -> list:
        """Scrape W&B public runs."""
        if not self.available:
            return []

        traces = []

        # Note: W&B API is synchronous, wrapping for consistency
        for project in tqdm(self.PUBLIC_PROJECTS, desc="W&B projects"):
            try:
                api = self.wandb.Api()
                runs = api.runs(project, per_page=runs_per_project)

                for run in runs:
                    try:
                        summary = dict(run.summary)
                        config = dict(run.config)

                        trace = ScrapedTrace(
                            source="wandb",
                            source_url=run.url,
                            framework="wandb",
                            content={
                                "summary": summary,
                                "config": config,
                                "name": run.name,
                                "state": run.state,
                            },
                            content_hash=hashlib.md5(json.dumps(summary, default=str).encode()).hexdigest(),
                            scraped_at=datetime.now(timezone.utc).isoformat(),
                            metadata={
                                "project": project,
                                "run_id": run.id,
                            },
                            trace_type="ml_run"
                        )
                        traces.append(trace)
                    except Exception as e:
                        continue

            except Exception as e:
                print(f"Failed to access W&B project {project}: {e}")
                continue

        return traces


class ResearchDatasetScraper:
    """Scrape agent traces from research paper repositories."""

    KNOWN_DATASETS = [
        # AgentBench
        {
            "name": "AgentBench",
            "url": "https://raw.githubusercontent.com/THUDM/AgentBench/main/data",
            "files": ["os_dev.json", "webshop_dev.json", "mind2web_dev.json"],
            "framework": "agent_benchmark"
        },
        # ToolBench
        {
            "name": "ToolBench",
            "url": "https://raw.githubusercontent.com/OpenBMB/ToolBench/main/data",
            "files": ["test_data.json"],
            "framework": "toolbench"
        },
        # API-Bank
        {
            "name": "API-Bank",
            "url": "https://raw.githubusercontent.com/AlibabaResearch/DAMO-ConvAI/main/api-bank/data",
            "files": ["test.jsonl"],
            "framework": "api_bank"
        },
    ]

    def __init__(self):
        self.session = None

    async def download_file(self, url: str) -> Optional[str]:
        """Download a file from URL."""
        try:
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    return await resp.text()
        except Exception as e:
            print(f"Failed to download {url}: {e}")
        return None

    async def scrape(self, output_dir: Path) -> list:
        """Scrape research datasets."""
        traces = []

        async with aiohttp.ClientSession() as session:
            self.session = session

            for dataset in tqdm(self.KNOWN_DATASETS, desc="Research datasets"):
                for filename in dataset["files"]:
                    url = f"{dataset['url']}/{filename}"
                    content = await self.download_file(url)

                    if not content:
                        continue

                    try:
                        if filename.endswith(".jsonl"):
                            items = [json.loads(l) for l in content.strip().split("\n") if l.strip()]
                        else:
                            items = json.loads(content)
                            if not isinstance(items, list):
                                items = [items]

                        for i, item in enumerate(items[:50]):  # Sample 50 per file
                            trace = ScrapedTrace(
                                source="research",
                                source_url=url,
                                framework=dataset["framework"],
                                content=item,
                                content_hash=hashlib.md5(json.dumps(item).encode()).hexdigest(),
                                scraped_at=datetime.now(timezone.utc).isoformat(),
                                metadata={
                                    "dataset": dataset["name"],
                                    "file": filename,
                                    "index": i,
                                },
                                trace_type="benchmark"
                            )
                            traces.append(trace)

                    except Exception as e:
                        print(f"Failed to parse {url}: {e}")
                        continue

                    await asyncio.sleep(0.5)

        return traces


class FirecrawlScraper:
    """Scrape trace examples from documentation sites."""

    URLS = [
        # LangChain docs
        "https://python.langchain.com/docs/how_to/debugging",
        "https://python.langchain.com/docs/how_to/callbacks_runtime",
        "https://python.langchain.com/docs/concepts/tracing",

        # LangGraph docs
        "https://langchain-ai.github.io/langgraph/concepts/low_level",
        "https://langchain-ai.github.io/langgraph/how-tos/streaming-tokens",

        # AutoGen docs
        "https://microsoft.github.io/autogen/docs/topics/groupchat/",
        "https://microsoft.github.io/autogen/docs/tutorial/conversation-patterns",

        # CrewAI docs
        "https://docs.crewai.com/concepts/agents",
        "https://docs.crewai.com/concepts/tasks",

        # LangSmith docs
        "https://docs.smith.langchain.com/old/tracing/faq/logging_and_viewing",
    ]

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FIRECRAWL_API_KEY")
        self.available = False

        if self.api_key:
            try:
                from firecrawl import FirecrawlApp
                self.app = FirecrawlApp(api_key=self.api_key)
                self.available = True
            except ImportError:
                print("firecrawl-py not installed. Run: pip install firecrawl-py")

    def extract_json_blocks(self, markdown: str) -> list:
        """Extract JSON code blocks from markdown."""
        pattern = r'```(?:json)?\s*([\s\S]*?)```'
        matches = re.findall(pattern, markdown)

        json_blocks = []
        for match in matches:
            try:
                parsed = json.loads(match.strip())
                json_blocks.append(parsed)
            except json.JSONDecodeError:
                continue

        return json_blocks

    async def scrape(self, output_dir: Path) -> list:
        """Scrape documentation sites for trace examples."""
        if not self.available:
            print("Firecrawl not available. Skipping doc scraping.")
            return []

        traces = []

        for url in tqdm(self.URLS, desc="Documentation sites"):
            try:
                result = self.app.scrape_url(
                    url,
                    params={"formats": ["markdown"]}
                )

                markdown = result.get("markdown", "")
                json_blocks = self.extract_json_blocks(markdown)

                for i, block in enumerate(json_blocks):
                    block_str = json.dumps(block).lower()
                    if not any(k in block_str for k in ["message", "tool", "agent", "run", "trace"]):
                        continue

                    trace = ScrapedTrace(
                        source="documentation",
                        source_url=url,
                        framework=self.detect_framework_from_url(url),
                        content=block,
                        content_hash=hashlib.md5(json.dumps(block).encode()).hexdigest(),
                        scraped_at=datetime.now(timezone.utc).isoformat(),
                        metadata={
                            "block_index": i,
                            "page_title": result.get("metadata", {}).get("title", ""),
                        },
                        trace_type="documentation_example"
                    )
                    traces.append(trace)

            except Exception as e:
                print(f"Failed to scrape {url}: {e}")
                continue

            await asyncio.sleep(1)

        return traces

    def detect_framework_from_url(self, url: str) -> str:
        """Detect framework from URL."""
        url_lower = url.lower()
        if "langsmith" in url_lower or "smith.langchain" in url_lower:
            return "langsmith"
        if "langchain" in url_lower:
            return "langchain"
        if "langgraph" in url_lower:
            return "langgraph"
        if "autogen" in url_lower:
            return "autogen"
        if "crewai" in url_lower:
            return "crewai"
        return "unknown"


async def main():
    parser = argparse.ArgumentParser(description="Scrape AI agent traces from public sources")
    parser.add_argument("--output", "-o", default="traces/raw", help="Output directory")
    parser.add_argument("--github", action="store_true", help="Scrape GitHub")
    parser.add_argument("--huggingface", action="store_true", help="Scrape HuggingFace")
    parser.add_argument("--openai-evals", action="store_true", help="Scrape OpenAI Evals")
    parser.add_argument("--wandb", action="store_true", help="Scrape W&B")
    parser.add_argument("--research", action="store_true", help="Scrape research datasets")
    parser.add_argument("--firecrawl", action="store_true", help="Scrape docs via Firecrawl")
    parser.add_argument("--all", action="store_true", help="Scrape all sources")
    parser.add_argument("--max-per-query", type=int, default=30, help="Max results per query")
    parser.add_argument("--samples-per-dataset", type=int, default=100, help="Samples per HF dataset")

    args = parser.parse_args()

    if args.all:
        args.github = args.huggingface = args.openai_evals = args.research = args.firecrawl = True
        # W&B requires auth, so skip by default

    sources_selected = any([
        args.github, args.huggingface, args.openai_evals,
        args.wandb, args.research, args.firecrawl
    ])

    if not sources_selected:
        print("No sources specified. Use --github, --huggingface, --openai-evals, --research, --firecrawl, or --all")
        return

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_traces = []

    # GitHub
    if args.github:
        print("\n=== Scraping GitHub (refined queries) ===")
        scraper = GitHubScraper()
        traces = await scraper.scrape(output_dir, max_per_query=args.max_per_query)
        print(f"Found {len(traces)} execution traces from GitHub")
        all_traces.extend(traces)

    # HuggingFace
    if args.huggingface:
        print("\n=== Scraping HuggingFace (expanded) ===")
        scraper = HuggingFaceScraper()
        traces = await scraper.scrape(output_dir, samples_per_dataset=args.samples_per_dataset)
        print(f"Found {len(traces)} traces from HuggingFace")
        all_traces.extend(traces)

    # OpenAI Evals
    if args.openai_evals:
        print("\n=== Scraping OpenAI Evals ===")
        scraper = OpenAIEvalsScraper()
        traces = await scraper.scrape(output_dir)
        print(f"Found {len(traces)} traces from OpenAI Evals")
        all_traces.extend(traces)

    # W&B
    if args.wandb:
        print("\n=== Scraping Weights & Biases ===")
        scraper = WandBScraper()
        traces = await scraper.scrape(output_dir)
        print(f"Found {len(traces)} traces from W&B")
        all_traces.extend(traces)

    # Research datasets
    if args.research:
        print("\n=== Scraping Research Datasets ===")
        scraper = ResearchDatasetScraper()
        traces = await scraper.scrape(output_dir)
        print(f"Found {len(traces)} traces from research datasets")
        all_traces.extend(traces)

    # Firecrawl
    if args.firecrawl:
        print("\n=== Scraping Documentation ===")
        scraper = FirecrawlScraper()
        traces = await scraper.scrape(output_dir)
        print(f"Found {len(traces)} traces from documentation")
        all_traces.extend(traces)

    # Deduplicate by content hash
    seen_hashes = set()
    unique_traces = []
    for trace in all_traces:
        if trace.content_hash not in seen_hashes:
            seen_hashes.add(trace.content_hash)
            unique_traces.append(trace)

    print(f"\n=== Total: {len(unique_traces)} unique traces ===")

    # Save traces
    output_file = output_dir / f"traces_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    async with aiofiles.open(output_file, "w") as f:
        for trace in unique_traces:
            await f.write(json.dumps(asdict(trace)) + "\n")

    print(f"Saved to: {output_file}")

    # Summary by source
    by_source = {}
    for trace in unique_traces:
        src = trace.source
        by_source[src] = by_source.get(src, 0) + 1

    print("\nBy source:")
    for src, count in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"  {src}: {count}")

    # Summary by framework
    by_framework = {}
    for trace in unique_traces:
        fw = trace.framework
        by_framework[fw] = by_framework.get(fw, 0) + 1

    print("\nBy framework:")
    for fw, count in sorted(by_framework.items(), key=lambda x: -x[1]):
        print(f"  {fw}: {count}")

    # Summary by trace type
    by_type = {}
    for trace in unique_traces:
        tt = trace.trace_type
        by_type[tt] = by_type.get(tt, 0) + 1

    print("\nBy trace type:")
    for tt, count in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {tt}: {count}")


if __name__ == "__main__":
    asyncio.run(main())
