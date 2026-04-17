import urllib.request
import urllib.error


def check_neo4j_health(host: str = "localhost", http_port: int = 7474) -> dict:
    """Check if Neo4j is reachable via its HTTP API."""
    url = f"http://{host}:{http_port}"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return {"status": "healthy", "url": url}
    except (urllib.error.URLError, OSError) as e:
        return {"status": "unhealthy", "url": url, "error": str(e)}
