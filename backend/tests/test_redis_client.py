"""
test_redis_client.py

Tests that verify the Redis client factory and connectivity helper behave correctly.

Role in project:
    Test suite — verifies the behaviour of backend.core.redis_client. Run with:
    pytest tests/test_redis_client.py -v

Coverage:
    - get_redis_client returns a redis.Redis instance configured for localhost:6379, db 0
    - ping_redis returns True when the underlying client.ping() succeeds
    - ping_redis returns False when a redis.ConnectionError is raised
    - An integration test (marked @pytest.mark.integration) verifies a live ping against a running Redis container
"""

import pytest
import redis as redis_lib
from unittest.mock import patch, MagicMock
from backend.core.redis_client import get_redis_client, ping_redis


def test_get_redis_client_returns_redis_instance():
    client = get_redis_client()
    assert isinstance(client, redis_lib.Redis)


def test_get_redis_client_uses_config():
    client = get_redis_client()
    connection_kwargs = client.connection_pool.connection_kwargs
    assert connection_kwargs["host"] == "localhost"
    assert connection_kwargs["port"] == 6379
    assert connection_kwargs["db"] == 0


def test_ping_redis_returns_true_when_connected():
    mock_client = MagicMock()
    mock_client.ping.return_value = True
    with patch("backend.core.redis_client.get_redis_client", return_value=mock_client):
        assert ping_redis() is True


def test_ping_redis_returns_false_when_connection_fails():
    mock_client = MagicMock()
    mock_client.ping.side_effect = redis_lib.ConnectionError("refused")
    with patch("backend.core.redis_client.get_redis_client", return_value=mock_client):
        assert ping_redis() is False


@pytest.mark.integration
def test_ping_redis_live():
    """Requires: docker run -d --name redis-finsight -p 6379:6379 redis:alpine"""
    assert ping_redis() is True
