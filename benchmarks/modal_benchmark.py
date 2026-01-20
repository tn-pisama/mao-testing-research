"""
Modal GPU Benchmark for MAST Detection

Run with:
    modal run benchmarks/modal_benchmark.py

Cost: ~$0.14 for 50 traces on A10G GPU
"""

import modal

# Create Modal app
app = modal.App("mast-benchmark")

# Define the image with all dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "sentence-transformers",
        "torch",
        "numpy",
        "pydantic",
        "pydantic-settings",
        "sqlalchemy",
        "anthropic",
        "fastapi",
        "python-jose[cryptography]",
        "passlib[bcrypt]",
        "aiohttp",
        "tiktoken",
        "click",  # CLI framework
        "tabulate",  # Table formatting
    )
    .add_local_dir("backend", remote_path="/app/backend", copy=True)
    .add_local_dir("benchmarks", remote_path="/app/benchmarks", copy=True)
    .add_local_dir("data", remote_path="/app/data", copy=True)
)


@app.function(
    image=image,
    gpu="A10G",  # NVIDIA A10G - good balance of cost/performance
    timeout=7200,  # 2 hour max for full dataset with LLM escalation
    secrets=[
        modal.Secret.from_name("anthropic-api-key"),
        modal.Secret.from_name("anthropic-api-key-2"),
        modal.Secret.from_name("anthropic-api-key-3"),
        modal.Secret.from_name("anthropic-api-key-4"),
    ],  # 4 API keys for 4x throughput via round-robin
)
def run_benchmark(sample_size: int = None, mode: str = None, hybrid: bool = True):
    """Run MAST benchmark on GPU with optional hybrid LLM detection."""
    import subprocess
    import os
    import sys

    # Set up environment
    os.chdir("/app/backend")  # Run from backend directory
    sys.path.insert(0, "/app/backend")
    sys.path.insert(0, "/app/benchmarks")

    # Set required env vars with secure random values
    import secrets as secrets_mod
    os.environ["JWT_SECRET"] = secrets_mod.token_urlsafe(64)
    os.environ["DATABASE_URL"] = "postgresql://localhost:5432/mao"  # Not used for benchmark
    os.environ["PYTHONPATH"] = "/app/backend:/app/benchmarks"  # For subprocess

    # Map Modal secret env vars to expected format for runner.py
    # Modal sets: ANTHROPIC_API_KEY, ANTHROPIC_API_KEY_2, ANTHROPIC_API_KEY_3, ANTHROPIC_API_KEY_4
    # Count available keys
    key_count = sum(1 for i in ['', '_2', '_3', '_4'] if f"ANTHROPIC_API_KEY{i}" in os.environ)
    print(f"Loaded {key_count} API keys for round-robin")

    # Build command using app.benchmark.cli (same as local)
    cmd = [
        "python", "-u", "-m", "app.benchmark.cli", "run",
        "/app/data/mast/MAD_full_dataset.json",
        "--no-ml",  # Skip ML models, use rule-based + LLM
        "-o", "/tmp/modal_hybrid_report.md",
    ]

    if mode:
        cmd.extend(["--modes", mode])

    if sample_size:
        cmd.extend(["--sample", str(sample_size)])

    if hybrid:
        cmd.append("--hybrid")

    print(f"Running: {' '.join(cmd)}")
    print(f"API keys available: {key_count}")
    print("=" * 60)

    # Run benchmark
    result = subprocess.run(cmd, capture_output=False, text=True)

    # Print the report if successful
    if result.returncode == 0:
        try:
            with open("/tmp/modal_hybrid_report.md", "r") as f:
                print("\n" + "=" * 60)
                print("BENCHMARK REPORT:")
                print("=" * 60)
                print(f.read())
        except FileNotFoundError:
            print("Report file not found")

    return result.returncode


@app.local_entrypoint()
def main(sample: int = None, mode: str = None, hybrid: bool = True):
    """Local entrypoint for running the benchmark."""
    print(f"Starting MAST benchmark on Modal A10G GPU")
    print(f"  Sample size: {sample or 'full dataset'}")
    print(f"  Mode: {mode or 'all'}")
    print(f"  Hybrid (LLM escalation): {hybrid}")
    print()

    exit_code = run_benchmark.remote(sample_size=sample, mode=mode, hybrid=hybrid)

    if exit_code == 0:
        print("\n✅ Benchmark completed successfully!")
    else:
        print(f"\n❌ Benchmark failed with exit code {exit_code}")
