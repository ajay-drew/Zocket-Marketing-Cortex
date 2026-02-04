"""
Tests for alerting system
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from src.observability.alerting import AlertManager, get_alert_manager


class TestAlertManager:
    """Tests for AlertManager"""
    
    def test_alert_manager_initialization(self):
        """Test alert manager initialization"""
        alert_manager = AlertManager(
            error_rate_threshold=10,
            performance_threshold=15.0,
            window_size=60
        )
        assert alert_manager.error_rate_threshold == 10
        assert alert_manager.performance_threshold == 15.0
        assert alert_manager.window_size == 60
    
    def test_record_error(self):
        """Test recording errors"""
        alert_manager = get_alert_manager()
        initial_count = len(alert_manager.error_timestamps)
        
        with patch.object(alert_manager, '_check_error_rate') as mock_check:
            alert_manager.record_error("test_error", "test_component", {"details": "test"})
            
            assert len(alert_manager.error_timestamps) == initial_count + 1
            mock_check.assert_called_once_with("test_component")
    
    def test_record_latency(self):
        """Test recording latency"""
        alert_manager = get_alert_manager()
        initial_count = len(alert_manager.latency_samples)
        
        with patch.object(alert_manager, '_check_performance') as mock_check:
            alert_manager.record_latency(5.0, "test_component", "test_operation")
            
            assert len(alert_manager.latency_samples) == initial_count + 1
            mock_check.assert_called_once_with("test_component", "test_operation")
    
    def test_error_rate_check_threshold(self):
        """Test error rate check triggers alert at threshold"""
        alert_manager = AlertManager(error_rate_threshold=3, window_size=60)
        
        # Record errors up to threshold
        for i in range(3):
            alert_manager.error_timestamps.append(datetime.utcnow())
        
        with patch.object(alert_manager, '_emit_alert') as mock_emit, \
             patch.object(alert_manager, '_should_alert', return_value=True):
            alert_manager._check_error_rate("test_component")
            
            # Should emit alert
            mock_emit.assert_called_once()
    
    def test_performance_check_threshold(self):
        """Test performance check triggers alert at threshold"""
        alert_manager = AlertManager(performance_threshold=10.0, window_size=60)
        
        # Record high latencies
        for i in range(10):
            alert_manager.latency_samples.append({
                "latency": 15.0,  # Above threshold
                "component": "test_component",
                "operation": "test_operation",
                "timestamp": datetime.utcnow()
            })
        
        with patch.object(alert_manager, '_emit_alert') as mock_emit, \
             patch.object(alert_manager, '_should_alert', return_value=True):
            alert_manager._check_performance("test_component", "test_operation")
            
            # Should emit alert
            mock_emit.assert_called_once()
    
    def test_alert_cooldown(self):
        """Test alert cooldown prevents spam"""
        # Create fresh alert manager for this test
        alert_manager = AlertManager()
        
        # First alert should be allowed
        assert alert_manager._should_alert("test_alert") is True
        
        # Second alert immediately should be blocked
        assert alert_manager._should_alert("test_alert") is False
        
        # Different alert key should be allowed
        assert alert_manager._should_alert("different_alert") is True
    
    def test_circuit_breaker_alert(self):
        """Test circuit breaker opened alert"""
        alert_manager = get_alert_manager()
        
        with patch.object(alert_manager, '_emit_alert') as mock_emit, \
             patch.object(alert_manager, '_should_alert', return_value=True):
            alert_manager.alert_circuit_breaker_opened("test_service")
            
            mock_emit.assert_called_once()
            call_args = mock_emit.call_args[0]
            assert call_args[0] == "circuit_breaker_opened"
            assert call_args[1] == "test_service"
    
    def test_emit_alert(self):
        """Test alert emission"""
        alert_manager = get_alert_manager()
        
        with patch('src.observability.alerting.cache_manager') as mock_cache, \
             patch('src.observability.alerting.logger') as mock_logger:
            mock_cache.set.return_value = None
            
            alert_manager._emit_alert(
                "test_alert",
                "test_component",
                {"details": "test"}
            )
            
            # Should log error
            mock_logger.error.assert_called_once()
            
            # Should store in cache
            mock_cache.set.assert_called_once()
    
    def test_get_recent_alerts(self):
        """Test getting recent alerts"""
        alert_manager = get_alert_manager()
        
        alerts = alert_manager.get_recent_alerts(limit=10)
        assert isinstance(alerts, list)
