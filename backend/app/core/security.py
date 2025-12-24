import re
from typing import List, Tuple


class PIIScanner:
    PATTERNS = {
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "phone": r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b',
        "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
        "credit_card": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
        "ip_address": r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
    }
    
    def scan(self, text: str) -> List[Tuple[str, str, int, int]]:
        findings = []
        for pii_type, pattern in self.PATTERNS.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                findings.append((pii_type, match.group(), match.start(), match.end()))
        return findings
    
    def redact(self, text: str) -> str:
        redacted = text
        for pii_type, pattern in self.PATTERNS.items():
            redacted = re.sub(pattern, f"[REDACTED_{pii_type.upper()}]", redacted, flags=re.IGNORECASE)
        return redacted


class SecretsScanner:
    PATTERNS = {
        "aws_key": r'AKIA[0-9A-Z]{16}',
        "aws_secret": r'[A-Za-z0-9/+=]{40}',
        "github_token": r'ghp_[A-Za-z0-9]{36}',
        "openai_key": r'sk-[A-Za-z0-9]{48}',
        "anthropic_key": r'sk-ant-[A-Za-z0-9-]{95}',
        "generic_api_key": r'(?i)(api[_-]?key|apikey|secret|password|token)\s*[=:]\s*["\']?[A-Za-z0-9_\-]{16,}["\']?',
    }
    
    def scan(self, text: str) -> List[Tuple[str, int, int]]:
        findings = []
        for secret_type, pattern in self.PATTERNS.items():
            for match in re.finditer(pattern, text):
                findings.append((secret_type, match.start(), match.end()))
        return findings
    
    def redact(self, text: str) -> str:
        redacted = text
        for secret_type, pattern in self.PATTERNS.items():
            redacted = re.sub(pattern, f"[REDACTED_SECRET]", redacted)
        return redacted


pii_scanner = PIIScanner()
secrets_scanner = SecretsScanner()


def sanitize_text(text: str) -> str:
    text = pii_scanner.redact(text)
    text = secrets_scanner.redact(text)
    return text
