from pathlib import Path
import ast
import re
import textwrap


def test_staging_endpoint_workflow_embedded_python_is_valid():
    workflow = Path(".github/workflows/atena_staging_endpoint_verification.yml").read_text(
        encoding="utf-8"
    )
    match = re.search(
        r"python - <<'PY'\s*\n(?P<script>.*?)\n\s+PY",
        workflow,
        re.DOTALL,
    )
    assert match, "The staging endpoint verification Python block must exist."
    script = textwrap.dedent(match.group("script"))
    ast.parse(script)

    # The synthetic profile test must never store health data and must clean up.
    assert '"health_data_consent": False' in script
    assert "finally:" in script
    assert "def call_profile_api(" in script
    assert '"discomfort_reported"' not in script
