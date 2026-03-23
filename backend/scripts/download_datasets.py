"""Download open-source agent trace datasets from HuggingFace.

Datasets:
- MAST-Data (UC Berkeley): Multi-agent failure traces with F1-F14 annotations
- TRAIL (PatronusAI): Agent reasoning traces (gated - requires auth)
- SWE-bench Verified (Princeton NLP): Software engineering agent tasks
- GAIA (Meta): General AI assistant benchmark (gated - requires auth)
"""
import os
import sys

os.makedirs("data/external", exist_ok=True)

from datasets import load_dataset

results = {}

# 1. MAST-Data - load each JSON file separately due to schema mismatch
print("Downloading MAST-Data...")
try:
    # The full dataset has mast_annotation/llm_name columns
    mast_full = load_dataset(
        "mcemri/MAST-Data",
        data_files="MAD_full_dataset.json",
        split="train",
    )
    mast_full.save_to_disk("data/external/mast_full")
    results["mast_full"] = mast_full
    print(f"  MAST full: {mast_full}")
except Exception as e:
    print(f"  MAST full failed: {e}")

try:
    # The human-labelled dataset has annotations/round columns
    mast_human = load_dataset(
        "mcemri/MAST-Data",
        data_files="MAD_human_labelled_dataset.json",
        split="train",
    )
    mast_human.save_to_disk("data/external/mast_human")
    results["mast_human"] = mast_human
    print(f"  MAST human-labelled: {mast_human}")
except Exception as e:
    print(f"  MAST human-labelled failed: {e}")

# 2. TRAIL (gated - will fail without auth, skip gracefully)
print("Downloading TRAIL...")
try:
    trail = load_dataset("PatronusAI/TRAIL")
    trail.save_to_disk("data/external/trail")
    results["trail"] = trail
    print(f"  TRAIL: {trail}")
except Exception as e:
    print(f"  TRAIL skipped (gated): {type(e).__name__}")

# 3. SWE-bench Verified (already downloaded)
print("Downloading SWE-bench Verified...")
try:
    if os.path.exists("data/external/swebench"):
        from datasets import Dataset
        swe = Dataset.load_from_disk("data/external/swebench")
        results["swebench"] = swe
        print(f"  SWE-bench (cached): {swe}")
    else:
        swe = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")
        swe.save_to_disk("data/external/swebench")
        results["swebench"] = swe
        print(f"  SWE-bench: {swe}")
except Exception as e:
    print(f"  SWE-bench failed: {e}")

# 4. GAIA (gated - will fail without auth, skip gracefully)
print("Downloading GAIA...")
try:
    gaia = load_dataset("gaia-benchmark/GAIA", "2023_all")
    gaia.save_to_disk("data/external/gaia")
    results["gaia"] = gaia
    print(f"  GAIA: {gaia}")
except Exception as e:
    print(f"  GAIA skipped (gated): {type(e).__name__}")

print(f"\nDone! Successfully downloaded: {list(results.keys())}")
