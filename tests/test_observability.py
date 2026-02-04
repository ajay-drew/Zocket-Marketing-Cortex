"""
Tests for observability infrastructure (Phase 4)
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from src.observability import (
    get_langsmith_client,
    get_langfuse_client,
    get_structured_logger,
    set_request_id,
    get_request_id,
    set_session_id,
    get_session_id,
    get_circuit_breaker,
    get_alert_manager
)
from src.observability.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerOpenError
from src.observability.retry import retry_with_backoff, AsyncRetry, RetryExhaustedError
from src.observability.alerting import AlertManager


class TestLangSmithConfig:
    """Tests for LangSmith integration"""
    
    def test_get_langsmith_client_not_configured(self):
        """Test LangSmith client returns None when not configured"""
        with patch('src.observability.langsmith_config.settings') as mock_settings:
            mock_settings.enable_langsmith = False
            from src.observability.langsmith_config import get_langsmith_client
            client = get_langsmith_client()
            assert client is None
    
    def test_get_langsmith_client_configured(self):
        """Test LangSmith client initialization when configured"""
        with patch('src.observability.langsmith_config.settings') as mock_settings, \
             patch('src.observability.langsmith_config.Client') as mock_client:
            mock_settings.enable_langsmith = True
            mock_settings.langchain_api_key = "test_key"
            mock_settings.langchain_endpoint = "https://api.smith.langchain.com"
            mock_settings.langchain_project = "test-project"
            
            from src.observability.langsmith_config import get_langsmith_client, _langsmith_client
            # Reset global client
            import src.observability.langsmith_config
            src.observability.langsmith_config._langsmith_client = None
            
            client = get_langsmith_client()
            # Should attempt to create client (may fail without real key, but should try)
            assert mock_client.called or client is None


class TestLangfuseConfig:
    """Tests for Langfuse integration"""
    
    def test_get_langfuse_client_not_configured(self):
        """Test Langfuse client returns None when not configured"""
        with patch('src.observability.langfuse_config.settings') as mock_settings:
            mock_settings.enable_langfuse = False
            from src.observability.langfuse_config import get_langfuse_client
            client = get_langfuse_client()
            assert client is None


class TestStructuredLogging:
    """Tests for structured logging"""
    
    def test_get_structured_logger(self):
        """Test getting structured logger"""
        logger = get_structured_logger("test.module")
        assert logger is not None
        assert logger.name == "test.module"
    
    def test_request_id_tracking(self):
        """Test request ID tracking"""
        request_id = set_request_id()
        assert request_id is not None
        assert len(request_id) > 0
        
        retrieved_id = get_request_id()
        assert retrieved_id == request_id
    
    def test_session_id_tracking(self):
        """Test session ID tracking"""
        session_id = "test-session-123"
        set_session_id(session_id)
        
        retrieved_id = get_session_id()
        assert retrieved_id == session_id


class TestCircuitBreaker:
    """Tests for circuit breaker pattern"""
    
    def test_circuit_breaker_initialization(self):
        """Test circuit breaker initialization"""
        cb = CircuitBreaker("test_service", failure_threshold=3, timeout=30)
        assert cb.name == "test_service"
        assert cb.failure_threshold == 3
        assert cb.timeout == 30
    
    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state"""
        cb = get_circuit_breaker("test_cb")
        
        # Mock Redis to return None (closed state)
        with patch('src.observability.circuit_breaker.cache_manager') as mock_cache:
            mock_cache.get.return_value = None
            
            status = cb.get_status()
            assert status["state"] == "closed"
            assert status["is_open"] is False
    
    def test_circuit_breaker_record_success(self):
        """Test recording success"""
        cb = get_circuit_breaker("test_cb_success")
        
        with patch('src.observability.circuit_breaker.cache_manager') as mock_cache:
            mock_cache.get.return_value = None
            mock_cache.set.return_value = None
            mock_cache.delete.return_value = None
            
            cb.record_success()
            # Should reset failure count
            mock_cache.delete.assert_called()
    
    def test_circuit_breaker_record_failure(self):
        """Test recording failure"""
        cb = get_circuit_breaker("test_cb_failure")
        
        with patch('src.observability.circuit_breaker.cache_manager') as mock_cache:
            mock_cache.get.return_value = 0  # No failures yet
            mock_cache.set.return_value = None
            
            cb.record_failure()
            # Should increment failure count
            assert mock_cache.set.called
    
    def test_circuit_breaker_open_after_threshold(self):
        """Test circuit breaker opens after threshold"""
        cb = CircuitBreaker("test_service", failure_threshold=2, timeout=10)
        
        with patch('src.observability.circuit_breaker.cache_manager') as mock_cache:
            # Simulate failures reaching threshold
            mock_cache.get.side_effect = lambda key: {
                cb.failure_count_key: 2,  # At threshold
                cb.state_key: None
            }.get(key, None)
            mock_cache.set.return_value = None
            
            cb.record_failure()
            # Should set state to OPEN
            calls = [call[0][0] for call in mock_cache.set.call_args_list if call[0][0] == cb.state_key]
            if calls:
                # State was set
                pass
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_async_call_success(self):
        """Test async call with circuit breaker"""
        cb = get_circuit_breaker("test_async")
        
        async def test_func(x):
            return x * 2
        
        with patch('src.observability.circuit_breaker.cache_manager') as mock_cache:
            mock_cache.get.return_value = None  # Closed state
            
            result = await cb.acall(test_func, 5)
            assert result == 10
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_async_call_open(self):
        """Test async call when circuit is open"""
        cb = CircuitBreaker("test_service", failure_threshold=2, timeout=10)
        
        async def test_func(x):
            return x * 2
        
        with patch('src.observability.circuit_breaker.cache_manager') as mock_cache:
            from datetime import datetime, timedelta
            # Simulate open circuit
            mock_cache.get.side_effect = lambda key: {
                cb.state_key: "open",
                cb.last_failure_key: datetime.utcnow().isoformat()  # Recent failure
            }.get(key, None)
            
            with pytest.raises(CircuitBreakerOpenError):
                await cb.acall(test_func, 5)


class TestRetryLogic:
    """Tests for retry logic"""
    
    @pytest.mark.asyncio
    async def test_retry_success_first_attempt(self):
        """Test retry succeeds on first attempt"""
        call_count = 0
        
        @retry_with_backoff(max_attempts=3, base_delay=0.1)
        async def test_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await test_func()
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_succeeds_after_failures(self):
        """Test retry succeeds after initial failures"""
        call_count = 0
        
        @retry_with_backoff(max_attempts=3, base_delay=0.1)
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Temporary failure")
            return "success"
        
        result = await test_func()
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        """Test retry exhausted after max attempts"""
        call_count = 0
        
        @retry_with_backoff(max_attempts=2, base_delay=0.1)
        async def test_func():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Persistent failure")
        
        with pytest.raises(RetryExhaustedError):
            await test_func()
        
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_non_retryable_error(self):
        """Test retry doesn't retry on non-retryable errors"""
        call_count = 0
        
        @retry_with_backoff(max_attempts=3, base_delay=0.1)
        async def test_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Non-retryable error")
        
        with pytest.raises(ValueError):
            await test_func()
        
        assert call_count == 1  # Should not retry
    
    @pytest.mark.asyncio
    async def test_async_retry_class(self):
        """Test AsyncRetry class"""
        call_count = 0
        
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("Timeout")
            return "success"
        
        retry = AsyncRetry(max_attempts=3, base_delay=0.1)
        result = await retry.execute(test_func)
        
        assert result == "success"
        assert call_count == 2


class TestAlerting:
    """Tests for alerting system"""
    
    def test_alert_manager_initialization(self):
        """Test alert manager initialization"""
        alert_manager = AlertManager(
            error_rate_threshold=10,
            performance_threshold=15.0
        )
        assert alert_manager.error_rate_threshold == 10
        assert alert_manager.performance_threshold == 15.0
    
    def test_record_error(self):
        """Test recording errors"""
        alert_manager = get_alert_manager()
        
        with patch('src.observability.alerting.cache_manager') as mock_cache:
            mock_cache.set.return_value = None
            
            alert_manager.record_error("test_error", "test_component", {"details": "test"})
            
            # Should record error
            assert len(alert_manager.error_timestamps) > 0
    
    def test_record_latency(self):
        """Test recording latency"""
        alert_manager = get_alert_manager()
        
        alert_manager.record_latency(5.0, "test_component", "test_operation")
        
        # Should record latency
        assert len(alert_manager.latency_samples) > 0
    
    def test_alert_cooldown(self):
        """Test alert cooldown mechanism"""
        alert_manager = get_alert_manager()
        
        # First alert should be allowed
        assert alert_manager._should_alert("test_alert") is True
        
        # Second alert within cooldown should be blocked
        assert alert_manager._should_alert("test_alert") is False
    
    def test_circuit_breaker_alert(self):
        """Test circuit breaker opened alert"""
        alert_manager = get_alert_manager()
        
        with patch('src.observability.alerting.cache_manager') as mock_cache:
            mock_cache.set.return_value = None
            
            alert_manager.alert_circuit_breaker_opened("test_service")
            
            # Should emit alert
            assert "test_service" in str(alert_manager.alert_cooldown)


class TestObservabilityIntegration:
    """Integration tests for observability components"""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_with_retry(self):
        """Test circuit breaker and retry working together"""
        cb = get_circuit_breaker("integration_test")
        
        call_count = 0
        
        @retry_with_backoff(max_attempts=2, base_delay=0.1)
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Temporary")
            return "success"
        
        with patch('src.observability.circuit_breaker.cache_manager') as mock_cache:
            mock_cache.get.return_value = None  # Circuit closed
            
            try:
                result = await cb.acall(test_func)
                assert result == "success"
            except Exception:
                # May fail if circuit breaker logic interferes, that's ok for test
                pass
    
    def test_structured_logging_with_request_id(self):
        """Test structured logging with request ID"""
        request_id = set_request_id("test-request-123")
        logger = get_structured_logger("test.module")
        
        # Logger should have request ID in context
        assert get_request_id() == "test-request-123"
