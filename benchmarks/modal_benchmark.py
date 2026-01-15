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
    )
    .add_local_dir("backend", remote_path="/app/backend", copy=True)
    .add_local_dir("benchmarks", remote_path="/app/benchmarks", copy=True)
    .add_local_dir("data", remote_path="/app/data", copy=True)
)


@app.function(
    image=image,
    gpu="A10G",  # NVIDIA A10G - good balance of cost/performance
    timeout=3600,  # 1 hour max
)
def run_benchmark(sample_size: int = 50, mode: str = None, hybrid: bool = False):
    """Run MAST benchmark on GPU."""
    import subprocess
    import os
    import sys

    # Set up environment
    os.chdir("/app")
    sys.path.insert(0, "/app/backend")
    sys.path.insert(0, "/app/benchmarks")

    # Set required env vars with secure random values
    import secrets
    os.environ["JWT_SECRET"] = secrets.token_urlsafe(64)
    os.environ["DATABASE_URL"] = "postgresql://localhost:5432/mao"  # Not used for benchmark

    # Build command
    cmd = [
        "python", "-u", "-m", "benchmarks.evaluation.test_mast_conversation",
        "--data-dir", "data",
        "--sample", str(sample_size),
    ]

    if mode:
        cmd.extend(["--mode", mode])

    if hybrid:
        cmd.append("--hybrid")

    print(f"Running: {' '.join(cmd)}")
    print("=" * 60)

    # Run benchmark
    result = subprocess.run(cmd, capture_output=False, text=True)

    return result.returncode


@app.local_entrypoint()
def main(sample: int = 50, mode: str = None, hybrid: bool = False):
    """Local entrypoint for running the benchmark."""
    print(f"Starting MAST benchmark on Modal A10G GPU")
    print(f"  Sample size: {sample}")
    print(f"  Mode: {mode or 'all'}")
    print(f"  Hybrid: {hybrid}")
    print()

    exit_code = run_benchmark.remote(sample_size=sample, mode=mode, hybrid=hybrid)

    if exit_code == 0:
        print("\n✅ Benchmark completed successfully!")
    else:
        print(f"\n❌ Benchmark failed with exit code {exit_code}")
