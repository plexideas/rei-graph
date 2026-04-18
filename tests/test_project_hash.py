import hashlib

from dgk_core.hashing import project_hash


class TestProjectHash:
    def test_returns_12_hex_chars(self):
        """project_hash returns a 12-character hex string."""
        result = project_hash("/home/user/my-project")
        assert len(result) == 12
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic(self):
        """Same path always returns the same hash."""
        assert project_hash("/home/user/my-project") == project_hash("/home/user/my-project")

    def test_different_paths_differ(self):
        """Different paths produce different hashes."""
        h1 = project_hash("/home/user/project-a")
        h2 = project_hash("/home/user/project-b")
        assert h1 != h2

    def test_matches_sha256_prefix(self):
        """Hash is the first 12 hex chars of the SHA256 of the path."""
        path = "/home/user/my-project"
        expected = hashlib.sha256(path.encode()).hexdigest()[:12]
        assert project_hash(path) == expected
