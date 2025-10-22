"""
Common enums and constants for the insider trading detection system.
Provides type safety and consistency across the codebase.
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from datetime import datetime


class AlertType(Enum):
    """Types of anomaly alerts that can be generated"""
    VOLUME_SPIKE = "VOLUME_SPIKE"
    WHALE_ACTIVITY = "WHALE_ACTIVITY"
    UNUSUAL_PRICE_MOVEMENT = "UNUSUAL_PRICE_MOVEMENT"
    COORDINATED_TRADING = "COORDINATED_TRADING"
    
    def __str__(self) -> str:
        return self.value


class AlertSeverity(Enum):
    """Alert severity levels in ascending order"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    
    def __str__(self) -> str:
        return self.value
    
    def __lt__(self, other):
        if not isinstance(other, AlertSeverity):
            return NotImplemented
        severity_order = [AlertSeverity.LOW, AlertSeverity.MEDIUM, AlertSeverity.HIGH, AlertSeverity.CRITICAL]
        return severity_order.index(self) < severity_order.index(other)
    
    @classmethod
    def get_all_severities(cls):
        """Get all severity level values"""
        return [member.value for member in cls]
    
    @classmethod
    def get_display_name(cls, severity):
        """Get display name for severity level"""
        if isinstance(severity, cls):
            return severity.value
        return severity  # If already a string value
    
    @classmethod
    def get_level(cls, severity):
        """Get numeric level for severity comparison"""
        severity_levels = {
            'LOW': 1,
            'MEDIUM': 2,
            'HIGH': 3,
            'CRITICAL': 4
        }
        if isinstance(severity, cls):
            return severity_levels[severity.value]
        return severity_levels.get(severity, 0)


class BaselineType(Enum):
    """Types of baselines used for anomaly detection"""
    HISTORICAL = "historical"
    RECENT_TRADES = "recent_trades"
    TIME_AWARE = "time_aware"
    OVERALL = "overall"
    
    def __str__(self) -> str:
        return self.value


class MarketStatus(Enum):
    """Market monitoring status"""
    ACTIVE = auto()
    INACTIVE = auto()
    ERROR = auto()
    INITIALIZING = auto()


class DetectorStatus(Enum):
    """Status of individual detectors"""
    READY = auto()
    PROCESSING = auto()
    ERROR = auto()
    DISABLED = auto()


@dataclass
class AlertMetadata:
    """Metadata associated with an alert"""
    confidence_score: float
    multi_metric: bool
    baseline_type: BaselineType
    filter_reason: str
    supporting_anomalies: List[Dict[str, Any]]
    cross_market_context: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'confidence_score': self.confidence_score,
            'multi_metric': self.multi_metric,
            'baseline_type': self.baseline_type.value,
            'filter_reason': self.filter_reason,
            'supporting_anomalies': self.supporting_anomalies,
            'cross_market_context': self.cross_market_context
        }


@dataclass
class Alert:
    """Structured alert data"""
    market_id: str
    market_question: str
    alert_type: AlertType
    severity: AlertSeverity
    analysis: Dict[str, Any]
    timestamp: datetime
    metadata: AlertMetadata
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'market_id': self.market_id,
            'market_question': self.market_question,
            'alert_type': self.alert_type.value,
            'severity': self.severity.value,
            'analysis': self.analysis,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata.to_dict()
        }


@dataclass
class MarketBaseline:
    """Enhanced market baseline data structure"""
    market_id: str
    baseline_type: BaselineType
    avg_hourly_volume: float
    std_hourly_volume: float
    total_volume: float
    avg_trades_per_hour: float
    hourly_patterns: Dict[str, Dict[str, float]]
    daily_patterns: Dict[str, Dict[str, float]]
    percentile_thresholds: Dict[str, float]
    last_updated: datetime
    data_quality_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'market_id': self.market_id,
            'baseline_type': self.baseline_type.value,
            'avg_hourly_volume': self.avg_hourly_volume,
            'std_hourly_volume': self.std_hourly_volume,
            'total_volume': self.total_volume,
            'avg_trades_per_hour': self.avg_trades_per_hour,
            'hourly_patterns': self.hourly_patterns,
            'daily_patterns': self.daily_patterns,
            'percentile_thresholds': self.percentile_thresholds,
            'last_updated': self.last_updated.isoformat(),
            'data_quality_score': self.data_quality_score
        }


@dataclass
class DetectionResult:
    """Result from a detection algorithm"""
    anomaly: bool
    confidence_score: float
    details: Dict[str, Any]
    detector_type: str
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'anomaly': self.anomaly,
            'confidence_score': self.confidence_score,
            'details': self.details,
            'detector_type': self.detector_type,
            'timestamp': self.timestamp.isoformat()
        }


class ConfidenceThresholds:
    """Confidence score thresholds for different scenarios"""
    # Single metric thresholds (require very high confidence)
    SINGLE_ANOMALY_THRESHOLD = 8.0
    
    # Multi-metric thresholds (lower individual requirements)
    MULTI_ANOMALY_THRESHOLD = 10.0
    CRITICAL_THRESHOLD = 15.0
    
    # Cross-market filtering thresholds
    MIN_SIMILAR_MARKETS = 3
    VOLUME_SURGE_MARKETS = 4
    
    # Confidence scoring constants
    MAX_CONFIDENCE_SCORE = 10.0
    HISTORICAL_BASELINE_BONUS = 1.0
    COORDINATION_BONUS = 2.0
    DIRECTIONAL_BIAS_BONUS = 1.0
    MULTI_TRIGGER_BONUS = 2.0
    WASH_TRADING_BONUS = 2.0


class TimeConstants:
    """Time-related constants"""
    CROSS_MARKET_WINDOW_MINUTES = 15
    BASELINE_UPDATE_HOURS = 24
    HISTORICAL_DATA_HOURS = 168  # 7 days
    RECENT_ACTIVITY_WINDOW_MINUTES = 30
    
    # WebSocket and API timeouts
    API_TIMEOUT_SECONDS = 10
    WEBSOCKET_RECONNECT_DELAY = 5
    MAX_RECONNECT_ATTEMPTS = 10


class VolumeConstants:
    """Volume detection constants"""
    DEFAULT_SPIKE_MULTIPLIER = 3.0
    DEFAULT_Z_SCORE_THRESHOLD = 3.0
    PERCENTILE_ANOMALY_THRESHOLD = 0.95  # P95
    
    # Trade limits
    MAX_TRADES_PER_REQUEST = 500
    MAX_HISTORICAL_TRADES = 200


class WhaleConstants:
    """Whale detection constants"""
    DEFAULT_THRESHOLD_USD = 10000
    DEFAULT_COORDINATION_THRESHOLD = 0.7
    MIN_WHALES_FOR_COORDINATION = 3
    TOP_WHALES_DISPLAY_LIMIT = 10


class PriceConstants:
    """Price movement detection constants"""
    DEFAULT_RAPID_MOVEMENT_PCT = 15
    DEFAULT_PRICE_MOVEMENT_STD = 2.5
    DEFAULT_VOLATILITY_SPIKE_MULTIPLIER = 3.0
    DEFAULT_MOMENTUM_THRESHOLD = 0.8


class CoordinationConstants:
    """Coordination detection constants"""
    DEFAULT_MIN_COORDINATED_WALLETS = 5
    DEFAULT_COORDINATION_TIME_WINDOW = 30
    DEFAULT_DIRECTIONAL_BIAS_THRESHOLD = 0.8
    DEFAULT_BURST_INTENSITY_THRESHOLD = 3.0


class MarketMakerThresholds:
    """
    Market maker detection heuristic thresholds.

    Used for identifying market makers based on trading patterns:
    - High frequency trading
    - Balanced buy/sell ratio
    - Multiple markets
    - Consistent activity over time
    """
    # Trade frequency thresholds
    HIGH_FREQUENCY_TRADES = 100
    MEDIUM_FREQUENCY_TRADES = 50
    LOW_FREQUENCY_TRADES = 25

    # Buy/sell ratio balance thresholds (0.0 to 1.0)
    TIGHT_RATIO_MIN = 0.45  # Within 5% of 50/50
    TIGHT_RATIO_MAX = 0.55
    LOOSE_RATIO_MIN = 0.40  # Within 10% of 50/50
    LOOSE_RATIO_MAX = 0.60

    # Market diversity thresholds
    MANY_MARKETS = 10
    SEVERAL_MARKETS = 5

    # Time consistency thresholds (days)
    LONG_ACTIVITY_DAYS = 7
    MEDIUM_ACTIVITY_DAYS = 3

    # Classification threshold (0-100)
    MM_CLASSIFICATION_THRESHOLD = 70  # Score >= 70 indicates likely MM

    # Scoring weights (total = 100)
    FREQUENCY_WEIGHT_MAX = 30
    BALANCE_WEIGHT_MAX = 40
    DIVERSITY_WEIGHT_MAX = 20
    CONSISTENCY_WEIGHT_MAX = 10


class WhaleRole:
    """Roles for whale-alert associations"""
    PRIMARY_ACTOR = "PRIMARY_ACTOR"  # Main whale driving the activity
    COORDINATOR = "COORDINATOR"  # Whale coordinating with others
    PARTICIPANT = "PARTICIPANT"  # Whale participating in coordinated activity