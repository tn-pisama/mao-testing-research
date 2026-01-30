#!/usr/bin/env python3
"""Test hallucination detector on fabricated study sample."""

import re

def detect_fabricated_facts(output: str):
    """Simplified version of _detect_fabricated_facts."""
    evidence = []
    score = 1.0

    specific_patterns = [
        (r'founded in \d{4}', "Specific founding year"),
        (r'according to (?:a )?\d{4} (?:study|report|survey)', "Specific study reference"),
        (r'\d+(?:\.\d+)?% of (?:people|users|companies)', "Specific percentage statistic"),
        (r'(?:Dr\.|Professor) [A-Z][a-z]+ [A-Z][a-z]+', "Named expert"),
        (r'published in (?:the )?[A-Z][a-zA-Z\s]+ Journal', "Journal reference"),
    ]

    for pattern, desc in specific_patterns:
        matches = re.findall(pattern, output)
        if matches:
            for match in matches[:2]:
                evidence.append(f"Potential fabrication ({desc}): '{match}'")
                score -= 0.1
                print(f"  Found {desc}: '{match}' (score now: {score})")

    definitive_phrases = [
        "definitely", "certainly", "absolutely", "always", "never",
        "100%", "guaranteed", "proven fact", "undoubtedly",
    ]

    definitive_count = sum(1 for phrase in definitive_phrases if phrase.lower() in output.lower())
    if definitive_count >= 3:
        evidence.append(f"High definitiveness ({definitive_count} definitive phrases)")
        score -= 0.15
        print(f"  Found {definitive_count} definitive phrases (score now: {score})")
    else:
        print(f"  Found only {definitive_count} definitive phrases (need 3+)")

    return max(0, score), evidence


# Test sample
output = (
    "According to a 2024 study published in the Journal of AI Research, "
    "87.3% of users show increased engagement with AI assistants. "
    "Dr. Sarah Johnson from MIT definitely confirmed these findings are absolutely accurate."
)

print("Testing fabricated study sample:")
print(f"Output: {output}\n")
print("Pattern matching:")

fabrication_score, evidence = detect_fabricated_facts(output)

print(f"\nFinal fabrication_score: {fabrication_score}")
print(f"Threshold for detection: 0.65")
print(f"Would be detected: {fabrication_score < 0.65}")
print(f"\nEvidence:")
for e in evidence:
    print(f"  - {e}")
