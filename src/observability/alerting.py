"""
Alerting system for error rate spikes and performance degradation
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import deque
from src.config import settings
from src.core.cache import cache_manager

logger = logging.getLogger(__name__)


class AlertManager:
    """
    Manages alerts for error rates, performance, and service health
    """
    
    def __init__(
        self,
        error_rate_threshold: int = None,
        performance_threshold: float = None,
        window_size: int = 60  # 1 minute window
    ):
        """
        Initialize alert manager
        
        Args:
            error_rate_threshold: Errors per minute to trigger alert (default: from settings)
            performance_threshold: P95 latency in seconds to trigger alert (default: from settings)
            window_size: Time window in seconds for rate calculations
        """
        self.error_rate_threshold = error_rate_threshold or settings.alert_error_rate_threshold
        self.performance_threshold = performance_threshold or settings.alert_performance_threshold
        self.window_size = window_size
        
        # In-memory tracking (can be moved to Redis for distributed systems)
        self.error_timestamps: deque = deque(maxlen=1000)  # Keep last 1000 errors
        self.latency_samples: deque = deque(maxlen=1000)  # Keep last 1000 latency samples
        self.alert_cooldown: Dict[str, datetime] = {}  # Prevent spam
        self.cooldown_period = timedelta(minutes=5)  # 5 minute cooldown between alerts
    
    def record_error(self, error_type: str, component: str, details: Optional[Dict] = None):
        """
        Record an error occurrence
        
        Args:
            error_type: Type of error
            component: Component where error occurred
            details: Additional error details
        """
        timestamp = datetime.utcnow()
        self.error_timestamps.append(timestamp)
        
        # Store error in Redis for persistence
        error_key = f"alert:error:{component}:{timestamp.isoformat()}"
        error_data = {
            "type": error_type,
            "component": component,
            "timestamp": timestamp.isoformat(),
            "details": details or {}
        }
        cache_manager.set(error_key, error_data, ttl=self.window_size * 2)
        
        # Check for error rate spike
        self._check_error_rate(component)
    
    def record_latency(self, latency: float, component: str, operation: str):
        """
        Record operation latency
        
        Args:
            latency: Latency in seconds
            component: Component name
            operation: Operation name
        """
        self.latency_samples.append({
            "latency": latency,
            "component": component,
            "operation": operation,
            "timestamp": datetime.utcnow()
        })
        
        # Check for performance degradation
        self._check_performance(component, operation)
    
    def _check_error_rate(self, component: str):
        """
        Check if error rate exceeds threshold
        
        Args:
            component: Component name
        """
        # Calculate errors in last window
        cutoff = datetime.utcnow() - timedelta(seconds=self.window_size)
        recent_errors = [ts for ts in self.error_timestamps if ts >= cutoff]
        error_rate = len(recent_errors)
        
        if error_rate >= self.error_rate_threshold:
            alert_key = f"error_rate:{component}"
            if self._should_alert(alert_key):
                self._emit_alert(
                    "error_rate_spike",
                    component,
                    {
                        "error_rate": error_rate,
                        "threshold": self.error_rate_threshold,
                        "window_seconds": self.window_size
                    }
                )
    
    def _check_performance(self, component: str, operation: str):
        """
        Check if performance degrades
        
        Args:
            component: Component name
            operation: Operation name
        """
        if len(self.latency_samples) < 10:
            # Need at least 10 samples for meaningful P95
            return
        
        # Get recent samples for this component/operation
        cutoff = datetime.utcnow() - timedelta(seconds=self.window_size)
        recent_samples = [
            s for s in self.latency_samples
            if s["timestamp"] >= cutoff and
            s["component"] == component and
            s["operation"] == operation
        ]
        
        if len(recent_samples) < 10:
            return
        
        # Calculate P95 latency
        latencies = sorted([s["latency"] for s in recent_samples])
        p95_index = int(len(latencies) * 0.95)
        p95_latency = latencies[p95_index] if p95_index < len(latencies) else latencies[-1]
        
        if p95_latency >= self.performance_threshold:
            alert_key = f"performance:{component}:{operation}"
            if self._should_alert(alert_key):
                self._emit_alert(
                    "performance_degradation",
                    component,
                    {
                        "operation": operation,
                        "p95_latency": p95_latency,
                        "threshold": self.performance_threshold,
                        "sample_count": len(recent_samples)
                    }
                )
    
    def _should_alert(self, alert_key: str) -> bool:
        """
        Check if alert should be emitted (cooldown check)
        
        Args:
            alert_key: Alert key
            
        Returns:
            True if alert should be emitted, False otherwise
        """
        last_alert = self.alert_cooldown.get(alert_key)
        if last_alert:
            if datetime.utcnow() - last_alert < self.cooldown_period:
                return False
        
        self.alert_cooldown[alert_key] = datetime.utcnow()
        return True
    
    def _emit_alert(self, alert_type: str, component: str, details: Dict):
        """
        Emit an alert
        
        Args:
            alert_type: Type of alert
            component: Component name
            details: Alert details
        """
        alert_message = (
            f"🚨 ALERT: {alert_type.upper()} - Component: {component}\n"
            f"Details: {details}"
        )
        
        # Log as error for visibility
        logger.error(alert_message)
        
        # Store alert in Redis for monitoring
        alert_key = f"alert:{alert_type}:{component}:{datetime.utcnow().isoformat()}"
        alert_data = {
            "type": alert_type,
            "component": component,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details
        }
        cache_manager.set(alert_key, alert_data, ttl=3600)  # Keep for 1 hour
    
    def alert_circuit_breaker_opened(self, circuit_name: str):
        """
        Alert when circuit breaker opens
        
        Args:
            circuit_name: Circuit breaker name
        """
        alert_key = f"circuit_breaker:{circuit_name}"
        if self._should_alert(alert_key):
            self._emit_alert(
                "circuit_breaker_opened",
                circuit_name,
                {
                    "circuit_name": circuit_name,
                    "message": f"Circuit breaker {circuit_name} has opened"
                }
            )
    
    def get_recent_alerts(self, limit: int = 10) -> List[Dict]:
        """
        Get recent alerts
        
        Args:
            limit: Maximum number of alerts to return
            
        Returns:
            List of alert dictionaries
        """
        # In a production system, this would query Redis or a database
        # For now, return empty list (alerts are logged)
        return []


# Global alert manager instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """
    Get or create alert manager instance
    
    Returns:
        AlertManager instance
    """
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager
