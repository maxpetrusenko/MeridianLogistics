from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DISPATCH_BOARD = ROOT / "dispatch-board.md"
ARTIFACT_LEDGER = ROOT / "artifact-ledger.md"
CONTROLLER_REPORT = (
    ROOT / "reports" / "2026-03-15-1454-controller-review-lane-contract-closeout-report.md"
)
CONTROLLER_CHECKPOINT = (
    ROOT / "reports"
    / "2026-03-15-1454-controller-review-lane-contract-closeout-checkpoint.json"
)


def _read(path: Path) -> str:
    return path.read_text()


class ReviewLaneTruthMergeTests(unittest.TestCase):
    def test_dispatch_board_records_review_lane_contract_closure_without_wave_closeout(
        self,
    ) -> None:
        dispatch_board = _read(DISPATCH_BOARD)

        self.assertIn(
            "review-lane contract closure is merged into controller truth",
            dispatch_board,
        )
        self.assertIn(
            "review-lane contract enforced across prompts, report rules, and regression tests",
            dispatch_board,
        )
        self.assertIn(
            "Bounded review packet set is approved and review agent status is literal `APPROVE`",
            dispatch_board,
        )
        self.assertIn(
            "`observability and replay gate closure` is now the active non-terminal auto wave",
            dispatch_board,
        )

    def test_artifact_ledger_tracks_review_lane_contract_closeout_artifacts(self) -> None:
        artifact_ledger = _read(ARTIFACT_LEDGER)

        self.assertIn(
            "reports/2026-03-15-1454-controller-review-lane-contract-closeout-checkpoint.json",
            artifact_ledger,
        )
        self.assertIn(
            "reports/2026-03-15-1454-controller-review-lane-contract-closeout-report.md",
            artifact_ledger,
        )
        self.assertIn("active wave: `observability and replay closure wave`", artifact_ledger)
        self.assertIn("terminal_state: `null`", artifact_ledger)

    def test_controller_report_records_packet_approval_and_open_wave_status(self) -> None:
        report = _read(CONTROLLER_REPORT)

        self.assertIn(
            "- review lane contract enforced across prompts, rules, and tests",
            report,
        )
        self.assertIn("- packet set approved", report)
        self.assertIn("- controller verification green: 33 tests", report)
        self.assertIn("- review agent status: APPROVE", report)
        self.assertIn(
            "- wave remains open; this is lane-contract closure only, not wave closure",
            report,
        )

    def test_controller_checkpoint_preserves_open_async_wave_truth(self) -> None:
        checkpoint = json.loads(CONTROLLER_CHECKPOINT.read_text())

        self.assertEqual(
            checkpoint["controller_last_decision"]["reason"],
            "review_lane_contract_closure_merged",
        )
        self.assertEqual(checkpoint["queue"]["wave_name"], "async job lifecycle expansion")
        self.assertEqual(checkpoint["queue"]["status"], "active")
        self.assertEqual(checkpoint["queue"]["run_policy"], "auto")
        self.assertTrue(checkpoint["queue"]["eligible"])
        self.assertEqual(checkpoint["queue"]["approval_authority"], "main")
        self.assertIsNone(checkpoint["terminal_state"])


if __name__ == "__main__":
    unittest.main()
