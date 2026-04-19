import hashlib


def project_hash(project_id: str) -> str:
    """Return the first 12 hex characters of the SHA-256 hash of *project_id*."""
    return hashlib.sha256(project_id.encode()).hexdigest()[:12]
