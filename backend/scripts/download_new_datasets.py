"""Download Tier 1 external datasets for Pisama detector validation.

Datasets:
- HaluEval (flowaicom/HaluEval): 35K hallucination samples with knowledge/question/answer
- Open-Prompt-Injection (GitHub): Prompt injection attack and benign examples
- AgentDebug (GitHub): 200 failed agent trajectories with step-level error annotations
- MemGPT function-call-traces (HuggingFace): Real agent conversations with function calls
"""
import os
import subprocess
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.makedirs("data/external", exist_ok=True)

results = {}

# 1. HaluEval - hallucination evaluation dataset
print("=" * 60)
print("1. Downloading HaluEval...")
print("=" * 60)
try:
    if os.path.exists("data/external/halueval"):
        from datasets import Dataset
        ds = Dataset.load_from_disk("data/external/halueval")
        results["halueval"] = ds
        print(f"  HaluEval (cached): {ds}")
    else:
        from datasets import load_dataset
        halueval = load_dataset("flowaicom/HaluEval")
        halueval.save_to_disk("data/external/halueval")
        results["halueval"] = halueval
        print(f"  HaluEval: {halueval}")
except Exception as e:
    print(f"  HaluEval failed: {e}")

# 2. Open-Prompt-Injection - prompt injection dataset
print("\n" + "=" * 60)
print("2. Downloading Open-Prompt-Injection...")
print("=" * 60)
try:
    opi_path = "data/external/Open-Prompt-Injection"
    if os.path.exists(opi_path):
        print(f"  Open-Prompt-Injection (cached): {opi_path}")
        results["openpromptinjection"] = opi_path
    else:
        subprocess.run(
            ["git", "clone", "--depth", "1",
             "https://github.com/liu00222/Open-Prompt-Injection.git",
             opi_path],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        results["openpromptinjection"] = opi_path
        print(f"  Open-Prompt-Injection: cloned to {opi_path}")
except Exception as e:
    print(f"  Open-Prompt-Injection failed: {e}")

# 3. AgentDebug (AgentErrorBench) - agent error trajectories
print("\n" + "=" * 60)
print("3. Downloading AgentDebug...")
print("=" * 60)
try:
    agentdebug_path = "data/external/AgentDebug"
    if os.path.exists(agentdebug_path):
        print(f"  AgentDebug (cached): {agentdebug_path}")
        results["agentdebug"] = agentdebug_path
    else:
        subprocess.run(
            ["git", "clone", "--depth", "1",
             "https://github.com/ulab-uiuc/AgentDebug.git",
             agentdebug_path],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        results["agentdebug"] = agentdebug_path
        print(f"  AgentDebug: cloned to {agentdebug_path}")
except Exception as e:
    print(f"  AgentDebug failed: {e}")

# 3b. Download AgentErrorBench dataset from Google Drive (labels + trajectories)
print("\n  Downloading AgentErrorBench dataset from Google Drive...")
try:
    bench_path = "data/external/AgentErrorBench"
    if os.path.exists(os.path.join(bench_path, "AgentErrorBench", "Label")):
        print(f"  AgentErrorBench dataset (cached)")
    else:
        import gdown
        os.makedirs(bench_path, exist_ok=True)
        folder_url = "https://drive.google.com/drive/folders/1bQe6dQA85pktT63YnKIKJDTVaH3O3Vpu"
        gdown.download_folder(folder_url, output=bench_path, quiet=False, remaining_ok=True)
        print(f"  AgentErrorBench dataset: downloaded to {bench_path}")
except Exception as e:
    print(f"  AgentErrorBench dataset download failed (may need manual download): {e}")

# 4. MemGPT function-call-traces
# Note: load_dataset() fails due to deprecated loading script.
# Download JSONL files directly via huggingface_hub.
print("\n" + "=" * 60)
print("4. Downloading MemGPT function-call-traces...")
print("=" * 60)
try:
    memgpt_dir = "data/external/memgpt"
    memgpt_files = ["msc_full.jsonl", "docqa_full.jsonl"]
    if all(os.path.exists(os.path.join(memgpt_dir, f)) for f in memgpt_files):
        results["memgpt"] = memgpt_dir
        print(f"  MemGPT (cached): {memgpt_dir}")
    else:
        from huggingface_hub import hf_hub_download
        os.makedirs(memgpt_dir, exist_ok=True)
        for fname in memgpt_files:
            hf_hub_download(
                repo_id="MemGPT/function-call-traces",
                filename=fname,
                repo_type="dataset",
                local_dir=memgpt_dir,
            )
            print(f"  Downloaded {fname}")
        results["memgpt"] = memgpt_dir
        print(f"  MemGPT: downloaded to {memgpt_dir}")
except Exception as e:
    print(f"  MemGPT failed: {e}")

print("\n" + "=" * 60)
print(f"Done! Successfully downloaded: {list(results.keys())}")
print(f"Failed: {[d for d in ['halueval', 'openpromptinjection', 'agentdebug', 'memgpt'] if d not in results]}")
print("=" * 60)
