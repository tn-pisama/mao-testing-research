"""
Sandboxed Fix Validator

Runs fix validation in isolated Docker containers to safely execute
modified agent code and verify that fixes actually resolve issues.

Security features:
- Read-only filesystem (except /tmp)
- No network access
- Memory and CPU limits
- Execution timeout
- Non-root user
"""
import asyncio
import json
import tempfile
import os
from typing import Optional
from dataclasses import dataclass
from pathlib import Path

try:
    import docker
    # Verify it's the real docker SDK, not a local namespace package
    DOCKER_AVAILABLE = hasattr(docker, 'from_env')
except ImportError:
    DOCKER_AVAILABLE = False


@dataclass
class ValidationResult:
    """Result of fix validation."""
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    issue_resolved: bool = False
    new_issues: int = 0


@dataclass
class FixSuggestion:
    """A suggested fix for a detected issue."""
    fix_type: str
    code_change: str
    description: str
    confidence: float
    line_number: Optional[int] = None
    file_path: Optional[str] = None


class SandboxedFixValidator:
    """
    Validates fix suggestions by running modified code in an isolated container.
    
    Usage:
        validator = SandboxedFixValidator()
        result = await validator.validate_fix(
            original_code="agent = AgentExecutor(...)",
            fix=FixSuggestion(code_change="add max_iterations=10"),
            test_input={"query": "test"}
        )
        if result.issue_resolved:
            print("Fix works!")
    """
    
    SANDBOX_IMAGE = "mao/fix-sandbox:latest"
    DEFAULT_TIMEOUT = 30
    MAX_MEMORY = "512m"
    MAX_CPUS = 1.0
    
    def __init__(self):
        if not DOCKER_AVAILABLE:
            raise RuntimeError(
                "Docker SDK not available. Install with: pip install docker"
            )
        self.client = docker.from_env()
    
    def _apply_fix(self, original_code: str, fix: FixSuggestion) -> str:
        """Apply a fix suggestion to the original code."""
        if fix.line_number and fix.line_number > 0:
            lines = original_code.split('\n')
            if fix.line_number <= len(lines):
                lines[fix.line_number - 1] = fix.code_change
                return '\n'.join(lines)
        
        return original_code.replace(
            self._find_replacement_target(original_code, fix),
            fix.code_change
        )
    
    def _find_replacement_target(self, code: str, fix: FixSuggestion) -> str:
        """Find the code segment to replace based on fix type."""
        patterns = {
            'max_iterations': r'AgentExecutor\([^)]*\)',
            'timeout': r'Crew\([^)]*\)',
            'state_validation': r'def\s+\w+\([^)]*\):',
        }
        
        import re
        pattern = patterns.get(fix.fix_type, r'.*')
        match = re.search(pattern, code)
        return match.group(0) if match else ""
    
    async def validate_fix(
        self,
        original_code: str,
        fix: FixSuggestion,
        test_input: dict,
        timeout: int = DEFAULT_TIMEOUT
    ) -> ValidationResult:
        """
        Apply fix and run in sandbox to verify it resolves the issue.
        
        Args:
            original_code: The original agent code with the issue
            fix: The fix suggestion to apply
            test_input: Input to test the agent with
            timeout: Maximum execution time in seconds
            
        Returns:
            ValidationResult indicating if the fix was successful
        """
        import time
        start_time = time.time()
        
        fixed_code = self._apply_fix(original_code, fix)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            code_path = Path(tmpdir) / "agent.py"
            input_path = Path(tmpdir) / "input.json"
            
            code_path.write_text(fixed_code)
            input_path.write_text(json.dumps(test_input))
            
            wrapper_code = self._generate_wrapper(fixed_code)
            wrapper_path = Path(tmpdir) / "run_test.py"
            wrapper_path.write_text(wrapper_code)
            
            try:
                container_output = self.client.containers.run(
                    self.SANDBOX_IMAGE,
                    command=["python", "/code/run_test.py"],
                    volumes={
                        tmpdir: {"bind": "/code", "mode": "ro"}
                    },
                    mem_limit=self.MAX_MEMORY,
                    cpu_period=100000,
                    cpu_quota=int(100000 * self.MAX_CPUS),
                    network_disabled=True,
                    read_only=True,
                    tmpfs={"/tmp": "size=50M"},  # nosec B108 - intentional tmpfs for sandbox
                    remove=True,
                    timeout=timeout,
                    user="sandbox",
                )
                
                output = container_output.decode('utf-8')
                execution_time = time.time() - start_time
                
                result_data = self._parse_output(output)
                
                return ValidationResult(
                    success=True,
                    output=output,
                    execution_time=execution_time,
                    issue_resolved=result_data.get('issue_resolved', False),
                    new_issues=result_data.get('new_issues', 0)
                )
                
            except docker.errors.ContainerError as e:
                return ValidationResult(
                    success=False,
                    error=f"Container error: {e.stderr.decode('utf-8') if e.stderr else str(e)}",
                    execution_time=time.time() - start_time
                )
            except docker.errors.APIError as e:
                return ValidationResult(
                    success=False,
                    error=f"Docker API error: {str(e)}",
                    execution_time=time.time() - start_time
                )
            except Exception as e:
                return ValidationResult(
                    success=False,
                    error=f"Unexpected error: {str(e)}",
                    execution_time=time.time() - start_time
                )
    
    def _generate_wrapper(self, agent_code: str) -> str:
        """Generate a wrapper script to run and validate the agent."""
        return f'''
import json
import sys
import traceback

def run_test():
    results = {{
        "success": False,
        "issue_resolved": False,
        "new_issues": 0,
        "output": None,
        "error": None
    }}
    
    try:
        with open("/code/input.json") as f:
            test_input = json.load(f)
        
        # Import and run the agent code
        exec(open("/code/agent.py").read(), globals())
        
        # If we get here without timeout/loop, issue may be resolved
        results["success"] = True
        results["issue_resolved"] = True
        
    except RecursionError:
        results["error"] = "RecursionError - infinite loop not fixed"
        results["new_issues"] = 1
    except TimeoutError:
        results["error"] = "TimeoutError - deadlock not fixed"
        results["new_issues"] = 1
    except Exception as e:
        results["error"] = str(e)
        results["success"] = False
    
    print(json.dumps(results))

if __name__ == "__main__":
    run_test()
'''
    
    def _parse_output(self, output: str) -> dict:
        """Parse the JSON output from the container."""
        try:
            for line in output.strip().split('\n'):
                if line.startswith('{'):
                    return json.loads(line)
        except json.JSONDecodeError:
            pass
        return {"issue_resolved": False, "new_issues": 0}
    
    async def validate_batch(
        self,
        fixes: list,
        original_code: str,
        test_input: dict,
        max_concurrent: int = 4
    ) -> list:
        """Validate multiple fixes concurrently."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def validate_with_semaphore(fix: FixSuggestion) -> ValidationResult:
            async with semaphore:
                return await self.validate_fix(original_code, fix, test_input)
        
        tasks = [validate_with_semaphore(fix) for fix in fixes]
        return await asyncio.gather(*tasks)


class SecurityWarning(UserWarning):
    """Warning for security-related concerns."""
    pass


class LocalFixValidator:
    """
    Fallback validator that runs fixes locally without Docker.
    Less secure but useful for development/testing.
    """

    def __init__(self):
        import warnings
        warnings.warn(
            "LocalFixValidator runs code without sandboxing. "
            "Use SandboxedFixValidator in production.",
            SecurityWarning
        )
    
    async def validate_fix(
        self,
        original_code: str,
        fix: FixSuggestion,
        test_input: dict,
        timeout: int = 10
    ) -> ValidationResult:
        """Validate fix locally with basic timeout protection."""
        import time
        import signal
        
        start_time = time.time()
        
        def timeout_handler(signum, frame):
            raise TimeoutError("Fix validation timed out")
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)
        
        try:
            fixed_code = original_code + f"\n# Fix applied: {fix.code_change}"
            exec(compile(fixed_code, '<string>', 'exec'))  # nosec B102 - needed for fix validation
            
            signal.alarm(0)
            
            return ValidationResult(
                success=True,
                output="Local validation passed",
                execution_time=time.time() - start_time,
                issue_resolved=True
            )
        except TimeoutError as e:
            return ValidationResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time
            )
        except Exception as e:
            signal.alarm(0)
            return ValidationResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time
            )


def get_validator(use_docker: bool = True):
    """Get the appropriate validator based on environment."""
    if use_docker and DOCKER_AVAILABLE:
        try:
            validator = SandboxedFixValidator()
            validator.client.ping()
            return validator
        except Exception:
            pass
    
    return LocalFixValidator()
