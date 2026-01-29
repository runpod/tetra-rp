"""Tests for load balancer module."""

import pytest

from tetra_rp.runtime.load_balancer import LoadBalancer
from tetra_rp.runtime.reliability_config import LoadBalancerStrategy


class TestLoadBalancer:
    """Test LoadBalancer class."""

    def test_round_robin_selection(self):
        """Test round-robin endpoint selection."""
        lb = LoadBalancer(strategy=LoadBalancerStrategy.ROUND_ROBIN)
        endpoints = ["http://a.com", "http://b.com", "http://c.com"]

        selected = []
        for _ in range(9):
            endpoint = lb._round_robin_index
            selected_ep = endpoints[endpoint % len(endpoints)]
            lb._round_robin_index += 1
            selected.append(selected_ep)

        # Should cycle through endpoints
        assert selected[0] == "http://a.com"
        assert selected[1] == "http://b.com"
        assert selected[2] == "http://c.com"
        assert selected[3] == "http://a.com"

    @pytest.mark.asyncio
    async def test_select_endpoint_round_robin(self):
        """Test select_endpoint with round-robin."""
        lb = LoadBalancer(strategy=LoadBalancerStrategy.ROUND_ROBIN)
        endpoints = ["http://a.com", "http://b.com"]

        selected1 = await lb.select_endpoint(endpoints)
        selected2 = await lb.select_endpoint(endpoints)
        selected3 = await lb.select_endpoint(endpoints)

        assert selected1 == "http://a.com"
        assert selected2 == "http://b.com"
        assert selected3 == "http://a.com"

    @pytest.mark.asyncio
    async def test_select_endpoint_random(self):
        """Test select_endpoint with random strategy."""
        lb = LoadBalancer(strategy=LoadBalancerStrategy.RANDOM)
        endpoints = ["http://a.com", "http://b.com"]

        selected = await lb.select_endpoint(endpoints)
        assert selected in endpoints

    @pytest.mark.asyncio
    async def test_select_endpoint_least_connections(self):
        """Test select_endpoint with least connections strategy."""
        lb = LoadBalancer(strategy=LoadBalancerStrategy.LEAST_CONNECTIONS)
        endpoints = ["http://a.com", "http://b.com"]

        await lb.record_request(endpoints[0])
        await lb.record_request(endpoints[0])

        selected = await lb.select_endpoint(endpoints)
        assert selected == endpoints[1]

    @pytest.mark.asyncio
    async def test_empty_endpoints_returns_none(self):
        """Test that empty endpoint list returns None."""
        lb = LoadBalancer()
        selected = await lb.select_endpoint([])
        assert selected is None

    @pytest.mark.asyncio
    async def test_record_request_and_complete(self):
        """Test recording in-flight requests."""
        lb = LoadBalancer()
        endpoint = "http://a.com"

        await lb.record_request(endpoint)
        stats = lb.get_stats()
        assert stats[endpoint] == 1

        await lb.record_request(endpoint)
        stats = lb.get_stats()
        assert stats[endpoint] == 2

        await lb.record_request_complete(endpoint)
        stats = lb.get_stats()
        assert stats[endpoint] == 1

    @pytest.mark.asyncio
    async def test_record_request_complete_does_not_go_negative(self):
        """Test that in-flight count doesn't go negative."""
        lb = LoadBalancer()
        endpoint = "http://a.com"

        await lb.record_request_complete(endpoint)
        stats = lb.get_stats()
        assert stats.get(endpoint, 0) == 0

    @pytest.mark.asyncio
    async def test_select_endpoint_with_circuit_breaker(self):
        """Test select_endpoint filters unhealthy endpoints."""

        class MockCircuitBreaker:
            def __init__(self, open_endpoints):
                self.open_endpoints = open_endpoints

            def get_state(self, endpoint):
                from tetra_rp.runtime.circuit_breaker import CircuitState

                if endpoint in self.open_endpoints:
                    return CircuitState.OPEN
                return CircuitState.CLOSED

        lb = LoadBalancer(strategy=LoadBalancerStrategy.ROUND_ROBIN)
        endpoints = ["http://a.com", "http://b.com", "http://c.com"]
        circuit_breaker = MockCircuitBreaker({"http://a.com"})

        # Should skip the open endpoint
        selected = await lb.select_endpoint(endpoints, circuit_breaker)
        assert selected != "http://a.com"

    @pytest.mark.asyncio
    async def test_all_endpoints_unhealthy_returns_none(self):
        """Test that all unhealthy endpoints returns None."""

        class MockCircuitBreaker:
            def get_state(self, endpoint):
                from tetra_rp.runtime.circuit_breaker import CircuitState

                return CircuitState.OPEN

        lb = LoadBalancer()
        endpoints = ["http://a.com", "http://b.com"]
        circuit_breaker = MockCircuitBreaker()

        selected = await lb.select_endpoint(endpoints, circuit_breaker)
        assert selected is None

    def test_get_stats(self):
        """Test getting load balancer statistics."""
        lb = LoadBalancer()
        stats = lb.get_stats()
        assert isinstance(stats, dict)
        assert len(stats) == 0
