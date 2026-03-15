from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REVIEW_AGENT_PROMPT = ROOT / ".agents" / "agents" / "review.md"
MAIN_AGENT_PROMPT = ROOT / ".agents" / "agents" / "main.md"
REPORT_RULES = ROOT / "reports" / "README.md"


def _read(path: Path) -> str:
    return path.read_text()


class ReviewLaneContractTests(unittest.TestCase):
    def test_review_prompt_requires_literal_first_line_verdict(self) -> None:
        prompt = _read(REVIEW_AGENT_PROMPT)

        self.assertIn("First non-empty line", prompt)
        self.assertIn("APPROVE", prompt)
        self.assertIn("REQUEST_REPAIR", prompt)
        self.assertIn("NEEDS_VERIFICATION", prompt)
        self.assertIn("HOLD", prompt)
        self.assertIn("Do not emit `APPROVE_WITH_NOTES`", prompt)

    def test_review_prompt_rejects_oversized_review_scope(self) -> None:
        prompt = _read(REVIEW_AGENT_PROMPT)

        self.assertIn("one artifact", prompt)
        self.assertIn("two directly related files", prompt)
        self.assertIn("split", prompt)
        self.assertIn("HOLD", prompt)

    def test_main_prompt_waits_longer_and_splits_review_packets(self) -> None:
        prompt = _read(MAIN_AGENT_PROMPT)

        self.assertIn("60-second", prompt)
        self.assertIn("split", prompt.lower())
        self.assertIn("review packet", prompt.lower())

    def test_report_rules_keep_review_requests_bounded(self) -> None:
        report_rules = _read(REPORT_RULES)

        self.assertIn("Review requests", report_rules)
        self.assertIn("one artifact", report_rules)
        self.assertIn("two directly related files", report_rules)


if __name__ == "__main__":
    unittest.main()
