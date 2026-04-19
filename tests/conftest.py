"""
Shared test fixtures.

The autouse ``mock_neo4j_health_check`` fixture patches
``rei_cli.commands.scan.check_neo4j_health`` to return a healthy response
for every test by default, so existing scan tests are unaffected by Phase 2's
pre-scan health probe.  Individual Phase 2 tests override this by wrapping the
relevant code in their own ``with patch(...)`` context, which takes precedence
over the autouse fixture for the duration of that block.
"""

import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def mock_neo4j_health_check():
    """Default: Neo4j is healthy.  Override per-test as needed."""
    with patch(
        "rei_cli.commands.scan.check_neo4j_health",
        return_value={"status": "healthy", "url": "http://localhost:7474"},
    ) as mock:
        yield mock
