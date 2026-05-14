import unittest

from flaw_finder.models import InputArtifact
from flaw_finder.pipeline import render_markdown, run_review


class PipelineTest(unittest.TestCase):
    def test_flags_sensitive_uploads_without_privacy_claims(self) -> None:
        artifact = InputArtifact(
            title="Pitch",
            body="Upload your investor deck and get feedback from an investor, lawyer, and user in minutes.",
        )

        synthesis = run_review(artifact)
        report = render_markdown(synthesis)

        self.assertIn("Sensitive input handling is not addressed", report)
        self.assertIn("Top fixes", report)

    def test_does_not_treat_first_customer_segment_as_competitive_claim(self) -> None:
        artifact = InputArtifact(
            title="Pitch",
            body="The first customer segment is solo founders who upload decks before investor calls.",
        )

        report = render_markdown(run_review(artifact))

        self.assertNotIn("Competitive claims need substantiation", report)


if __name__ == "__main__":
    unittest.main()
