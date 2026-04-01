# Contributing to Pisama

Thanks for your interest in contributing. This guide covers the essentials to get started.

For the full development setup, see [docs-site/docs/contributing/development.md](docs-site/docs/contributing/development.md).

## Quick Start

```bash
# Clone the repo
git clone https://github.com/tn-pisama/mao-testing-research.git
cd mao-testing-research

# Start infrastructure
docker compose up -d

# Install backend dependencies
cd backend
pip install -r requirements.txt

# Run tests
pytest tests/
```

## Development Workflow

1. Create a branch from `main`.
2. Make your changes, keeping commits focused.
3. Run `pytest` to verify nothing is broken.
4. Open a pull request against `main`.

## Guidelines

- No mock or simulated data -- use real traces and golden datasets.
- Prefer editing existing files over creating new ones.
- Choose the simplest implementation that solves the problem.
- All LLM calls must use Claude/Anthropic models (no OpenAI).

## Reporting Issues

Open an issue at [github.com/tn-pisama/mao-testing-research/issues](https://github.com/tn-pisama/mao-testing-research/issues) with steps to reproduce.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
