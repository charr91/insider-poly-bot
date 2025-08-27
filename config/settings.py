"""
Settings Management
Centralized configuration management for the insider trading bot
"""

import os
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class MonitoringSettings:
    """Settings for market monitoring"""
    volume_threshold: float = 1000
    max_markets: int = 50
    check_interval: int = 60
    sort_by_volume: bool = True
    market_discovery_interval: int = 300  # 5 minutes
    analysis_interval: int = 60  # 1 minute

@dataclass
class DetectionSettings:
    """Settings for detection algorithms"""
    # Volume detection
    volume_spike_multiplier: float = 3.0
    z_score_threshold: float = 3.0
    
    # Whale detection
    whale_threshold_usd: float = 10000
    coordination_threshold: float = 0.7
    min_whales_for_coordination: int = 3
    
    # Price detection
    rapid_movement_pct: float = 15
    price_movement_std: float = 2.5
    volatility_spike_multiplier: float = 3.0
    momentum_threshold: float = 0.8
    
    # Coordination detection
    min_coordinated_wallets: int = 5
    coordination_time_window: int = 30
    directional_bias_threshold: float = 0.8
    burst_intensity_threshold: float = 3.0

@dataclass
class AlertSettings:
    """Settings for alert management"""
    discord_webhook: str = ""
    min_severity: str = "MEDIUM"
    max_alerts_per_hour: int = 10
    duplicate_window_minutes: int = 10

@dataclass
class APISettings:
    """Settings for external APIs"""
    # Data API
    data_api_base_url: str = "https://data-api.polymarket.com"
    data_api_timeout: int = 10
    
    # WebSocket
    websocket_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    websocket_reconnect_attempts: int = 10
    websocket_reconnect_delay: int = 5
    
    # CLOB API (for fallback)
    clob_api_key: str = ""
    clob_api_secret: str = ""
    clob_api_passphrase: str = ""
    
    # Polygon settings
    polygon_private_key: str = ""
    funder_address: str = ""
    simulation_mode: bool = False

class Settings:
    """Main settings manager"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        
        # Load environment variables
        self._load_env_vars()
        
        # Initialize setting groups
        self.monitoring = self._init_monitoring_settings()
        self.detection = self._init_detection_settings()
        self.alerts = self._init_alert_settings()
        self.api = self._init_api_settings()
        
        logger.info("⚙️ Settings initialized")
    
    def _load_env_vars(self):
        """Load settings from environment variables"""
        # API Keys
        os.environ.setdefault('CLOB_API_KEY', '')
        os.environ.setdefault('CLOB_API_SECRET', '')
        os.environ.setdefault('CLOB_API_PASSPHRASE', '')
        os.environ.setdefault('DISCORD_WEBHOOK', '')
        
        # Blockchain
        os.environ.setdefault('POLYGON_PRIVATE_KEY', '')
        os.environ.setdefault('FUNDER_ADDRESS', '')
        os.environ.setdefault('SIMULATION_MODE', 'false')
    
    def _init_monitoring_settings(self) -> MonitoringSettings:
        """Initialize monitoring settings"""
        monitoring_config = self.config.get('monitoring', {})
        
        return MonitoringSettings(
            volume_threshold=monitoring_config.get('volume_threshold', 1000),
            max_markets=monitoring_config.get('max_markets', 50),
            check_interval=monitoring_config.get('check_interval', 60),
            sort_by_volume=monitoring_config.get('sort_by_volume', True),
            market_discovery_interval=monitoring_config.get('market_discovery_interval', 300),
            analysis_interval=monitoring_config.get('analysis_interval', 60)
        )
    
    def _init_detection_settings(self) -> DetectionSettings:
        """Initialize detection algorithm settings"""
        detection_config = self.config.get('detection', {})
        
        # Volume settings
        volume_thresholds = detection_config.get('volume_thresholds', {})
        
        # Whale settings
        whale_thresholds = detection_config.get('whale_thresholds', {})
        
        # Price settings
        price_thresholds = detection_config.get('price_thresholds', {})
        
        # Coordination settings
        coordination_thresholds = detection_config.get('coordination_thresholds', {})
        
        return DetectionSettings(
            # Volume
            volume_spike_multiplier=volume_thresholds.get('volume_spike_multiplier', 3.0),
            z_score_threshold=volume_thresholds.get('z_score_threshold', 3.0),
            
            # Whale
            whale_threshold_usd=whale_thresholds.get('whale_threshold_usd', 10000),
            coordination_threshold=whale_thresholds.get('coordination_threshold', 0.7),
            min_whales_for_coordination=whale_thresholds.get('min_whales_for_coordination', 3),
            
            # Price
            rapid_movement_pct=price_thresholds.get('rapid_movement_pct', 15),
            price_movement_std=price_thresholds.get('price_movement_std', 2.5),
            volatility_spike_multiplier=price_thresholds.get('volatility_spike_multiplier', 3.0),
            momentum_threshold=price_thresholds.get('momentum_threshold', 0.8),
            
            # Coordination
            min_coordinated_wallets=coordination_thresholds.get('min_coordinated_wallets', 5),
            coordination_time_window=coordination_thresholds.get('coordination_time_window', 30),
            directional_bias_threshold=coordination_thresholds.get('directional_bias_threshold', 0.8),
            burst_intensity_threshold=coordination_thresholds.get('burst_intensity_threshold', 3.0)
        )
    
    def _init_alert_settings(self) -> AlertSettings:
        """Initialize alert settings"""
        alert_config = self.config.get('alerts', {})
        
        return AlertSettings(
            discord_webhook=os.getenv('DISCORD_WEBHOOK', alert_config.get('discord_webhook', '')),
            min_severity=alert_config.get('min_severity', 'MEDIUM'),
            max_alerts_per_hour=alert_config.get('max_alerts_per_hour', 10),
            duplicate_window_minutes=alert_config.get('duplicate_window_minutes', 10)
        )
    
    def _init_api_settings(self) -> APISettings:
        """Initialize API settings"""
        api_config = self.config.get('api', {})
        
        return APISettings(
            # Data API
            data_api_base_url=api_config.get('data_api_base_url', 'https://data-api.polymarket.com'),
            data_api_timeout=api_config.get('data_api_timeout', 10),
            
            # WebSocket
            websocket_url=api_config.get('websocket_url', 'wss://ws-subscriptions-clob.polymarket.com/ws/market'),
            websocket_reconnect_attempts=api_config.get('websocket_reconnect_attempts', 10),
            websocket_reconnect_delay=api_config.get('websocket_reconnect_delay', 5),
            
            # CLOB API
            clob_api_key=os.getenv('CLOB_API_KEY', api_config.get('clob_api_key', '')),
            clob_api_secret=os.getenv('CLOB_API_SECRET', api_config.get('clob_api_secret', '')),
            clob_api_passphrase=os.getenv('CLOB_API_PASSPHRASE', api_config.get('clob_api_passphrase', '')),
            
            # Blockchain
            polygon_private_key=os.getenv('POLYGON_PRIVATE_KEY', api_config.get('polygon_private_key', '')),
            funder_address=os.getenv('FUNDER_ADDRESS', api_config.get('funder_address', '')),
            simulation_mode=os.getenv('SIMULATION_MODE', '').lower() == 'true' if os.getenv('SIMULATION_MODE') else api_config.get('simulation_mode', False)
        )
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of current settings"""
        return {
            'monitoring': {
                'volume_threshold': self.monitoring.volume_threshold,
                'max_markets': self.monitoring.max_markets,
                'check_interval': self.monitoring.check_interval,
                'sort_by_volume': self.monitoring.sort_by_volume
            },
            'detection': {
                'volume_spike_multiplier': self.detection.volume_spike_multiplier,
                'whale_threshold_usd': self.detection.whale_threshold_usd,
                'rapid_movement_pct': self.detection.rapid_movement_pct,
                'min_coordinated_wallets': self.detection.min_coordinated_wallets
            },
            'alerts': {
                'min_severity': self.alerts.min_severity,
                'max_alerts_per_hour': self.alerts.max_alerts_per_hour,
                'discord_configured': bool(self.alerts.discord_webhook)
            },
            'api': {
                'simulation_mode': self.api.simulation_mode,
                'clob_authenticated': bool(self.api.clob_api_key),
                'data_api_url': self.api.data_api_base_url
            }
        }
    
    def validate_settings(self) -> List[str]:
        """Validate settings and return list of issues"""
        issues = []
        
        # Check monitoring settings
        if self.monitoring.volume_threshold <= 0:
            issues.append("Volume threshold must be positive")
        
        if self.monitoring.max_markets <= 0:
            issues.append("Max markets must be positive")
        
        # Check detection thresholds
        if self.detection.volume_spike_multiplier <= 1:
            issues.append("Volume spike multiplier must be > 1")
        
        if self.detection.whale_threshold_usd <= 0:
            issues.append("Whale threshold must be positive")
        
        # Check alert settings
        if self.alerts.min_severity not in ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']:
            issues.append("Invalid min_severity value")
        
        # Check API settings in non-simulation mode
        if not self.api.simulation_mode:
            if not self.api.polygon_private_key:
                issues.append("Polygon private key required for non-simulation mode")
        
        return issues
    
    def log_settings(self):
        """Log current settings"""
        logger.info("⚙️ Current Settings:")
        logger.info(f"  📊 Monitoring: {self.monitoring.max_markets} markets, min volume ${self.monitoring.volume_threshold}")
        logger.info(f"  🔍 Detection: Volume {self.detection.volume_spike_multiplier}x, Whale ${self.detection.whale_threshold_usd}")
        logger.info(f"  🔔 Alerts: Min severity {self.alerts.min_severity}, Discord {'✅' if self.alerts.discord_webhook else '❌'}")
        logger.info(f"  🌐 API: {'Simulation' if self.api.simulation_mode else 'Live'} mode")
        
        # Validation
        issues = self.validate_settings()
        if issues:
            logger.warning(f"⚠️ Configuration issues: {', '.join(issues)}")
        else:
            logger.info("✅ Settings validation passed")