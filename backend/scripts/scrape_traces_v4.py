#!/usr/bin/env python3
"""
AI Agent Trace Scraper v4

Expanded scraper with Reddit, Firecrawl, Kaggle, and more sources.

Sources:
- GitHub (queries + known repos)
- HuggingFace (expanded datasets)
- Reddit (r/LangChain, r/LocalLLaMA, etc.)
- Firecrawl (documentation sites)
- Kaggle datasets
- Blog posts (Medium, dev.to)
- Langfuse public traces
- OpenAI Evals

Usage:
    python scripts/scrape_traces_v4.py --all --output traces/raw

Environment variables:
    GITHUB_TOKEN - GitHub API token
    FIRECRAWL_API_KEY - Firecrawl API key
    REDDIT_CLIENT_ID - Reddit API client ID
    REDDIT_CLIENT_SECRET - Reddit API secret
"""

import os
import json
import asyncio
import hashlib
import re
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Set
from dataclasses import dataclass, asdict
import time

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
    trace_type: str = "unknown"


class RateLimiter:
    def __init__(self, calls_per_second: float = 1.0):
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0

    async def wait(self):
        now = time.time()
        elapsed = now - self.last_call
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
        self.last_call = time.time()


class FirecrawlScraper:
    """Scrape documentation sites using Firecrawl API."""

    URLS = [
        # LangChain
        "https://python.langchain.com/docs/how_to/debugging",
        "https://python.langchain.com/docs/how_to/agent_executor",
        "https://python.langchain.com/docs/how_to/tool_calling",
        "https://python.langchain.com/docs/tutorials/agents",
        "https://python.langchain.com/docs/concepts/tracing",

        # LangGraph
        "https://langchain-ai.github.io/langgraph/tutorials/introduction",
        "https://langchain-ai.github.io/langgraph/how-tos/streaming-tokens",
        "https://langchain-ai.github.io/langgraph/concepts/agentic_concepts",

        # LangSmith
        "https://docs.smith.langchain.com/how_to_guides/tracing/trace_with_langchain",
        "https://docs.smith.langchain.com/evaluation",

        # AutoGen
        "https://microsoft.github.io/autogen/docs/tutorial/introduction",
        "https://microsoft.github.io/autogen/docs/tutorial/conversation-patterns",
        "https://microsoft.github.io/autogen/docs/topics/groupchat",

        # CrewAI
        "https://docs.crewai.com/concepts/agents",
        "https://docs.crewai.com/concepts/tasks",
        "https://docs.crewai.com/concepts/crews",

        # Langfuse
        "https://langfuse.com/docs/tracing",
        "https://langfuse.com/guides/cookbook/example_langgraph_agents",

        # OpenAI
        "https://platform.openai.com/docs/guides/function-calling",
        "https://platform.openai.com/docs/guides/agents",

        # Anthropic
        "https://docs.anthropic.com/en/docs/build-with-claude/tool-use",
        "https://docs.anthropic.com/en/docs/agents-and-tools",
    ]

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FIRECRAWL_API_KEY")
        self.available = bool(self.api_key)
        self.session = None
        self.rate_limiter = RateLimiter(calls_per_second=0.5)

    def detect_framework(self, url: str) -> str:
        url_lower = url.lower()
        if "langsmith" in url_lower or "smith.langchain" in url_lower:
            return "langsmith"
        if "langgraph" in url_lower:
            return "langgraph"
        if "langchain" in url_lower:
            return "langchain"
        if "autogen" in url_lower:
            return "autogen"
        if "crewai" in url_lower:
            return "crewai"
        if "langfuse" in url_lower:
            return "langfuse"
        if "openai" in url_lower:
            return "openai"
        if "anthropic" in url_lower:
            return "anthropic"
        return "unknown"

    def extract_json_blocks(self, text: str) -> list:
        """Extract JSON code blocks from markdown/text."""
        patterns = [
            r'```json\s*([\s\S]*?)```',
            r'```\s*([\s\S]*?)```',
            r'\{[\s\S]*?"(?:role|messages|tool_calls|function_call)"[\s\S]*?\}',
        ]

        blocks = []
        for pattern in patterns[:2]:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    parsed = json.loads(match.strip())
                    if isinstance(parsed, (dict, list)):
                        blocks.append(parsed)
                except:
                    pass

        return blocks

    def is_trace_like(self, data: dict) -> bool:
        """Check if data looks like an agent trace."""
        text = json.dumps(data).lower()
        indicators = ["tool_call", "function_call", "messages", "role", "agent",
                     "observation", "thought", "action", "output", "result"]
        return sum(1 for ind in indicators if ind in text) >= 2

    async def scrape_url(self, url: str) -> Optional[dict]:
        """Scrape a URL using Firecrawl API."""
        await self.rate_limiter.wait()

        try:
            async with self.session.post(
                "https://api.firecrawl.dev/v1/scrape",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "url": url,
                    "formats": ["markdown"]
                }
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("data", {})
        except Exception as e:
            print(f"Firecrawl error for {url}: {e}")

        return None

    async def scrape(self, output_dir: Path) -> list:
        if not self.available:
            print("Firecrawl API key not set. Skipping.")
            return []

        traces = []

        async with aiohttp.ClientSession() as session:
            self.session = session

            for url in tqdm(self.URLS, desc="Firecrawl"):
                result = await self.scrape_url(url)
                if not result:
                    continue

                markdown = result.get("markdown", "")
                json_blocks = self.extract_json_blocks(markdown)

                for i, block in enumerate(json_blocks):
                    if not self.is_trace_like(block):
                        continue

                    traces.append(ScrapedTrace(
                        source="firecrawl",
                        source_url=url,
                        framework=self.detect_framework(url),
                        content=block,
                        content_hash=hashlib.md5(json.dumps(block).encode()).hexdigest(),
                        scraped_at=datetime.now(timezone.utc).isoformat(),
                        metadata={
                            "page_title": result.get("metadata", {}).get("title", ""),
                            "block_index": i
                        },
                        trace_type="documentation_example"
                    ))

        return traces


class RedditScraper:
    """Scrape Reddit for agent traces shared in posts/comments."""

    SUBREDDITS = [
        "LangChain",
        "LocalLLaMA",
        "MachineLearning",
        "artificial",
        "ChatGPT",
        "ClaudeAI",
        "OpenAI",
    ]

    SEARCH_TERMS = [
        "agent trace",
        "function calling output",
        "tool_calls",
        "langchain debug",
        "autogen conversation",
        "agent execution log",
    ]

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        self.client_id = client_id or os.getenv("REDDIT_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("REDDIT_CLIENT_SECRET")
        self.available = bool(self.client_id and self.client_secret)
        self.session = None
        self.access_token = None
        self.rate_limiter = RateLimiter(calls_per_second=1)

    async def get_access_token(self) -> Optional[str]:
        """Get Reddit OAuth access token."""
        auth = aiohttp.BasicAuth(self.client_id, self.client_secret)

        try:
            async with self.session.post(
                "https://www.reddit.com/api/v1/access_token",
                auth=auth,
                data={"grant_type": "client_credentials"},
                headers={"User-Agent": "TraceScraperBot/1.0"}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("access_token")
        except Exception as e:
            print(f"Reddit auth error: {e}")

        return None

    def extract_json_from_text(self, text: str) -> list:
        """Extract JSON blocks from Reddit post/comment text."""
        blocks = []

        # Look for code blocks
        code_pattern = r'```(?:json)?\s*([\s\S]*?)```'
        matches = re.findall(code_pattern, text)

        for match in matches:
            try:
                parsed = json.loads(match.strip())
                blocks.append(parsed)
            except:
                pass

        # Look for inline JSON-like structures
        json_pattern = r'\{[^{}]*"(?:role|messages|tool_calls)"[^{}]*\}'
        inline_matches = re.findall(json_pattern, text)

        for match in inline_matches:
            try:
                parsed = json.loads(match)
                blocks.append(parsed)
            except:
                pass

        return blocks

    async def search_subreddit(self, subreddit: str, query: str, limit: int = 25) -> list:
        """Search a subreddit for posts."""
        await self.rate_limiter.wait()

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": "TraceScraperBot/1.0"
        }

        try:
            async with self.session.get(
                f"https://oauth.reddit.com/r/{subreddit}/search",
                headers=headers,
                params={"q": query, "limit": limit, "sort": "relevance", "restrict_sr": "true"}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("data", {}).get("children", [])
        except Exception as e:
            print(f"Reddit search error: {e}")

        return []

    async def scrape(self, output_dir: Path) -> list:
        if not self.available:
            print("Reddit API credentials not set. Skipping.")
            return []

        traces = []

        async with aiohttp.ClientSession() as session:
            self.session = session

            self.access_token = await self.get_access_token()
            if not self.access_token:
                print("Failed to get Reddit access token")
                return []

            for subreddit in tqdm(self.SUBREDDITS, desc="Reddit"):
                for term in self.SEARCH_TERMS:
                    posts = await self.search_subreddit(subreddit, term, limit=10)

                    for post in posts:
                        post_data = post.get("data", {})
                        selftext = post_data.get("selftext", "")
                        title = post_data.get("title", "")

                        json_blocks = self.extract_json_from_text(selftext)

                        for i, block in enumerate(json_blocks):
                            traces.append(ScrapedTrace(
                                source="reddit",
                                source_url=f"https://reddit.com{post_data.get('permalink', '')}",
                                framework=self.detect_framework(title + selftext),
                                content=block,
                                content_hash=hashlib.md5(json.dumps(block).encode()).hexdigest(),
                                scraped_at=datetime.now(timezone.utc).isoformat(),
                                metadata={
                                    "subreddit": subreddit,
                                    "title": title[:100],
                                    "search_term": term,
                                    "block_index": i
                                },
                                trace_type="user_shared"
                            ))

                    await asyncio.sleep(1)  # Rate limiting

        return traces

    def detect_framework(self, text: str) -> str:
        text_lower = text.lower()
        if "langchain" in text_lower:
            return "langchain"
        if "langgraph" in text_lower:
            return "langgraph"
        if "autogen" in text_lower:
            return "autogen"
        if "crewai" in text_lower:
            return "crewai"
        if "openai" in text_lower:
            return "openai"
        if "anthropic" in text_lower or "claude" in text_lower:
            return "anthropic"
        return "unknown"


class KaggleScraper:
    """Scrape Kaggle for agent-related datasets."""

    DATASETS = [
        "thedevastator/chatgpt-conversations",
        "polartech/llm-agent-executions",
        "paultimothymooney/openai-chatgpt-playground-generated-data",
    ]

    def __init__(self):
        try:
            import kaggle
            self.kaggle = kaggle
            self.available = True
        except ImportError:
            print("kaggle not installed. Run: pip install kaggle")
            self.available = False

    async def scrape(self, output_dir: Path, samples_per_dataset: int = 50) -> list:
        if not self.available:
            return []

        traces = []

        for dataset in tqdm(self.DATASETS, desc="Kaggle"):
            try:
                # Download dataset
                download_path = output_dir / "kaggle_temp"
                download_path.mkdir(exist_ok=True)

                self.kaggle.api.dataset_download_files(
                    dataset,
                    path=str(download_path),
                    unzip=True
                )

                # Process downloaded files
                for json_file in download_path.glob("**/*.json"):
                    try:
                        with open(json_file) as f:
                            data = json.load(f)

                        items = data if isinstance(data, list) else [data]

                        for i, item in enumerate(items[:samples_per_dataset]):
                            traces.append(ScrapedTrace(
                                source="kaggle",
                                source_url=f"https://www.kaggle.com/datasets/{dataset}",
                                framework="unknown",
                                content=item,
                                content_hash=hashlib.md5(json.dumps(item, default=str).encode()).hexdigest(),
                                scraped_at=datetime.now(timezone.utc).isoformat(),
                                metadata={
                                    "dataset": dataset,
                                    "file": json_file.name,
                                    "index": i
                                },
                                trace_type="kaggle_dataset"
                            ))
                    except:
                        continue

                # Cleanup
                import shutil
                shutil.rmtree(download_path, ignore_errors=True)

            except Exception as e:
                print(f"Kaggle error for {dataset}: {e}")
                continue

        return traces


class HuggingFaceExpandedScraper:
    """Expanded HuggingFace scraper with more function calling datasets."""

    DATASETS = [
        # Function calling - Core
        ("glaiveai/glaive-function-calling-v2", "function_calling", "train"),
        ("NousResearch/hermes-function-calling-v1", "function_calling", "train"),
        ("Salesforce/xlam-function-calling-60k", "function_calling", "train"),
        ("Locutusque/function-calling-chatml", "function_calling", "train"),

        # More function calling
        ("hiyouga/glaive-function-calling-v2-sharegpt", "function_calling", "train"),
        ("Trelis/function_calling_extended", "function_calling", "train"),

        # Agent conversations
        ("Open-Orca/OpenOrca", "conversation", "train"),
        ("teknium/GPTeacher-General-Instruct", "conversation", "train"),
        ("WizardLM/WizardLM_evol_instruct_V2_196k", "conversation", "train"),

        # ReAct / reasoning
        ("TIGER-Lab/MathInstruct", "react", "train"),
        ("gsm8k:main", "reasoning", "train"),  # Fixed: specify config

        # Code execution
        ("bigcode/self-oss-instruct-sc2-exec-filter-50k", "code_agent", "train"),
        ("m-a-p/CodeFeedback-Filtered-Instruction", "code_agent", "train"),
        ("sahil2801/CodeAlpaca-20k", "code_agent", "train"),

        # NEW: Agent Trajectory Datasets (2025)
        ("hkust-nlp/Toolathlon-Trajectories", "agent_trajectory", "train"),  # 17 model trajectories
        ("Agent-Ark/Toucan-1.5M", "agent_trajectory", "train"),  # 1.5M trajectories from MCPs!
        ("DeepNLP/Coding-Agent-Github-2025-Feb", "code_agent", "train"),  # Coding agent data

        # Tool use benchmarks
        ("gorilla-llm/Berkeley-Function-Calling-Leaderboard", "benchmark", "train"),  # Fixed dataset name
    ]

    def __init__(self):
        try:
            from datasets import load_dataset
            self.load_dataset = load_dataset
            self.available = True
        except ImportError:
            self.available = False

    def is_agent_trace(self, example: dict) -> bool:
        text = json.dumps(example, default=str).lower()
        indicators = ["tool_call", "function_call", "observation", "action",
                     "tool", "function", "agent", "result"]
        return sum(1 for ind in indicators if ind in text) >= 2

    def classify_trace(self, example: dict) -> str:
        text = json.dumps(example, default=str).lower()
        if "function_call" in text or "tool_call" in text:
            return "function_call"
        if "observation" in text and "thought" in text:
            return "react"
        if "code" in text and "output" in text:
            return "code_execution"
        return "conversation"

    async def scrape(self, output_dir: Path, samples_per_dataset: int = 100) -> list:
        if not self.available:
            return []

        traces = []

        for dataset_name, category, split in tqdm(self.DATASETS, desc="HuggingFace"):
            try:
                # Handle config specification (e.g., "gsm8k:main")
                if ":" in dataset_name:
                    name, config = dataset_name.split(":", 1)
                    ds = self.load_dataset(name, config, split=split, streaming=True)
                else:
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
                print(f"HuggingFace error for {dataset_name}: {e}")
                continue

        return traces


class GitHubEnhancedScraper:
    """Enhanced GitHub scraper with more sources."""

    SEARCH_QUERIES = [
        # Execution traces
        '"run_id" "start_time" extension:json',
        '"trace_id" "spans" extension:json',
        '"tool_calls" "messages" extension:json',

        # LangSmith
        '"dotted_order" extension:json',
        'langsmith "run_type" extension:json',

        # Function calling
        '"function_call" "arguments" extension:json',
        '"choices" "tool_calls" extension:json',

        # Framework specific
        'autogen "sender" "receiver" extension:json',
        'crewai "task_output" extension:json',
        'langgraph "checkpoint" extension:json',

        # ReAct
        '"observation" "thought" "action" extension:json',
        '"intermediate_steps" extension:json',

        # File paths
        'path:traces/ extension:jsonl',
        'path:logs/ agent extension:json',
    ]

    KNOWN_TRACE_REPOS = [
        ("langchain-ai/langsmith-cookbook", "tracing-examples"),
        ("langchain-ai/langgraph", "examples"),
        ("microsoft/autogen", "samples"),
        ("langfuse/langfuse-docs", "cookbook"),
    ]

    EXECUTION_PATTERNS = [
        r'"run_id":\s*"[a-f0-9-]+"',
        r'"trace_id":\s*"[a-f0-9-]+"',
        r'"tool_calls":\s*\[',
        r'"function_call":\s*\{',
        r'"observation":\s*"',
        r'"messages":\s*\[.*"role"',
    ]

    EXCLUDE_PATTERNS = [
        r'"openapi":\s*"3\.',
        r'"\$schema"',
        r'package\.json',
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
                    print("Rate limited. Waiting...")
                    await asyncio.sleep(60)
                    return []
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("items", [])
        except:
            pass
        return []

    async def download_file(self, url: str) -> Optional[str]:
        try:
            async with self.session.get(url, headers=self.headers) as resp:
                if resp.status == 200:
                    content = await resp.text()
                    if len(content) < 5_000_000:
                        return content
        except:
            pass
        return None

    def is_execution_trace(self, content: str) -> bool:
        for pattern in self.EXCLUDE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return False
        matches = sum(1 for p in self.EXECUTION_PATTERNS if re.search(p, content))
        return matches >= 2

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
        if "langfuse" in content_lower:
            return "langfuse"
        if "observation" in content_lower and "thought" in content_lower:
            return "react"
        if "tool_calls" in content_lower:
            return "openai"
        return "unknown"

    def classify_trace_type(self, content: str) -> str:
        content_lower = content.lower()
        if "tool_calls" in content_lower or "function_call" in content_lower:
            return "function_call"
        if "observation" in content_lower and "thought" in content_lower:
            return "react_trace"
        if "spans" in content_lower:
            return "otel_trace"
        if "checkpoint" in content_lower:
            return "state_trace"
        if '"messages"' in content_lower:
            return "conversation"
        return "execution"

    async def scrape(self, output_dir: Path, max_per_query: int = 30) -> list:
        traces = []

        async with aiohttp.ClientSession() as session:
            self.session = session

            for query in tqdm(self.SEARCH_QUERIES, desc="GitHub"):
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

        return traces


class OpenAIEvalsScraper:
    """Scrape OpenAI Evals with recursive directory traversal."""

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
                if resp.status == 200:
                    return await resp.json()
        except:
            pass
        return []

    async def scrape_recursive(self, path: str, max_files: int, current_count: int = 0) -> list:
        """Recursively scrape directories."""
        traces = []
        if current_count >= max_files:
            return traces

        items = await self.list_directory(path)

        for item in items:
            if current_count + len(traces) >= max_files:
                break

            if item.get("type") == "dir":
                subtraces = await self.scrape_recursive(
                    item["path"],
                    max_files,
                    current_count + len(traces)
                )
                traces.extend(subtraces)

            elif item.get("type") == "file" and item.get("name", "").endswith(".jsonl"):
                download_url = item.get("download_url")
                if not download_url:
                    continue

                try:
                    async with self.session.get(download_url) as resp:
                        if resp.status != 200:
                            continue
                        content = await resp.text()

                    lines = [json.loads(l) for l in content.strip().split("\n") if l.strip()]

                    for i, line in enumerate(lines[:5]):
                        traces.append(ScrapedTrace(
                            source="openai_evals",
                            source_url=item.get("html_url", ""),
                            framework="openai",
                            content=line,
                            content_hash=hashlib.md5(json.dumps(line).encode()).hexdigest(),
                            scraped_at=datetime.now(timezone.utc).isoformat(),
                            metadata={
                                "eval_name": item.get("name", ""),
                                "path": item.get("path", ""),
                                "index": i
                            },
                            trace_type="eval"
                        ))
                except:
                    continue

        return traces

    async def scrape(self, output_dir: Path, max_evals: int = 100) -> list:
        async with aiohttp.ClientSession() as session:
            self.session = session
            print("Scraping OpenAI Evals recursively...")
            return await self.scrape_recursive("evals/registry/data", max_evals)


async def main():
    parser = argparse.ArgumentParser(description="AI Agent Trace Scraper v4")
    parser.add_argument("--output", "-o", default="traces/raw")
    parser.add_argument("--github", action="store_true")
    parser.add_argument("--huggingface", action="store_true")
    parser.add_argument("--firecrawl", action="store_true")
    parser.add_argument("--reddit", action="store_true")
    parser.add_argument("--kaggle", action="store_true")
    parser.add_argument("--openai-evals", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--max-per-query", type=int, default=30)
    parser.add_argument("--samples-per-dataset", type=int, default=100)

    args = parser.parse_args()

    if args.all:
        args.github = args.huggingface = args.firecrawl = True
        args.reddit = args.openai_evals = True
        # Kaggle requires setup, skip by default

    sources = [args.github, args.huggingface, args.firecrawl,
               args.reddit, args.kaggle, args.openai_evals]

    if not any(sources):
        print("No sources. Use --all or specific flags.")
        return

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_traces = []

    if args.github:
        print("\n=== GitHub ===")
        scraper = GitHubEnhancedScraper()
        traces = await scraper.scrape(output_dir, max_per_query=args.max_per_query)
        print(f"Found {len(traces)} traces")
        all_traces.extend(traces)

    if args.huggingface:
        print("\n=== HuggingFace ===")
        scraper = HuggingFaceExpandedScraper()
        traces = await scraper.scrape(output_dir, samples_per_dataset=args.samples_per_dataset)
        print(f"Found {len(traces)} traces")
        all_traces.extend(traces)

    if args.firecrawl:
        print("\n=== Firecrawl ===")
        scraper = FirecrawlScraper()
        traces = await scraper.scrape(output_dir)
        print(f"Found {len(traces)} traces")
        all_traces.extend(traces)

    if args.reddit:
        print("\n=== Reddit ===")
        scraper = RedditScraper()
        traces = await scraper.scrape(output_dir)
        print(f"Found {len(traces)} traces")
        all_traces.extend(traces)

    if args.kaggle:
        print("\n=== Kaggle ===")
        scraper = KaggleScraper()
        traces = await scraper.scrape(output_dir)
        print(f"Found {len(traces)} traces")
        all_traces.extend(traces)

    if args.openai_evals:
        print("\n=== OpenAI Evals ===")
        scraper = OpenAIEvalsScraper()
        traces = await scraper.scrape(output_dir, max_evals=50)
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

    for t in unique:
        by_source[t.source] = by_source.get(t.source, 0) + 1
        by_framework[t.framework] = by_framework.get(t.framework, 0) + 1

    print("\nBy source:")
    for k, v in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    print("\nBy framework:")
    for k, v in sorted(by_framework.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    asyncio.run(main())
