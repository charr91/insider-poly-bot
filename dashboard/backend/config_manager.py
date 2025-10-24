"""
Configuration Manager for Dashboard Backend

Handles configuration loading, validation, and management
for the insider trading detection dashboard.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


logger = logging.getLogger(__name__)


class DashboardConfig:
    """Manages dashboard configuration and settings"""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path(__file__).parent.parent.parent / "insider_config.json"
        self.config_data: Dict[str, Any] = {}
        self.last_modified: Optional[datetime] = None
        
        # Default configuration structure
        self.default_config = {
            "dashboard": {
                "host": "127.0.0.1",
                "port": 8000,
                "debug": True,
                "cors_origins": ["http://localhost:3000", "http://127.0.0.1:3000"],
                "websocket_ping_interval": 30,
                "max_clients": 100
            },
            "detection": {
                "volume_spike_multiplier": 3.0,
                "whale_threshold_usd": 2000,
                "coordination_threshold": 0.7,
                "price_change_threshold": 15.0,
                "z_score_threshold": 3.0,
                "directional_bias_threshold": 0.8,
                "volatility_multiplier": 3.0,
                "time_window_seconds": 30,
                "min_coordinated_wallets": 5,
                "burst_intensity_multiplier": 3.0
            },
            "monitoring": {
                "max_markets": None,
                "min_volume_threshold": 1000,
                "baseline_days": 7,
                "cross_market_window_minutes": 15,
                "min_similar_markets": 3,
                "min_volume_surge_markets": 4
            },
            "alerts": {
                "min_severity": "MEDIUM",
                "discord_enabled": False,
                "discord_webhook_url": "",
                "rate_limit_per_hour": 100,
                "anomaly_thresholds": {
                    "single_anomaly": 8.0,
                    "multi_anomaly": 10.0,
                    "critical": 15.0
                },
                "confidence_bonuses": {
                    "historical_match": 1.0,
                    "coordination_detected": 2.0,
                    "directional_bias": 1.0,
                    "multi_trigger": 2.0,
                    "wash_trading": 2.0
                }
            },
            "data_sources": {
                "websocket_url": "wss://ws-subscriptions.polymarket.com/",
                "api_base_url": "https://gamma-api.polymarket.com/",
                "clob_api_enabled": False,
                "rate_limit_requests_per_minute": 60
            }
        }
        
        self.load_config()
    
    def load_config(self) -> None:
        """Load configuration from file"""
        try:
            if self.config_path.exists():
                stat = self.config_path.stat()
                modification_time = datetime.fromtimestamp(stat.st_mtime)
                
                # Only reload if file was modified
                if self.last_modified is None or modification_time > self.last_modified:
                    with open(self.config_path, 'r') as f:
                        file_config = json.load(f)
                    
                    # Merge with defaults
                    self.config_data = self._merge_configs(self.default_config, file_config)
                    self.last_modified = modification_time
                    
                    logger.info(f"Configuration loaded from {self.config_path}")
                else:
                    logger.debug("Configuration file unchanged, using cached config")
            else:
                logger.warning(f"Configuration file {self.config_path} not found, using defaults")
                self.config_data = self.default_config.copy()
                
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            logger.info("Falling back to default configuration")
            self.config_data = self.default_config.copy()
    
    def _merge_configs(self, default: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge configuration dictionaries"""
        merged = default.copy()
        
        for key, value in override.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_configs(merged[key], value)
            else:
                merged[key] = value
        
        return merged
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation
        
        Examples:
            config.get("dashboard.port")
            config.get("detection.volume_spike_multiplier") 
            config.get("alerts.anomaly_thresholds.critical")
        """
        try:
            keys = key_path.split('.')
            value = self.config_data
            
            for key in keys:
                value = value[key]
            
            return value
            
        except (KeyError, TypeError):
            return default
    
    def set(self, key_path: str, value: Any) -> bool:
        """
        Set configuration value using dot notation
        
        Returns True if successful, False otherwise
        """
        try:
            keys = key_path.split('.')
            config_ref = self.config_data
            
            # Navigate to parent dictionary
            for key in keys[:-1]:
                if key not in config_ref:
                    config_ref[key] = {}
                config_ref = config_ref[key]
            
            # Set the value
            config_ref[keys[-1]] = value
            
            logger.info(f"Configuration updated: {key_path} = {value}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting configuration {key_path}: {e}")
            return False
    
    def save_config(self) -> bool:
        """Save current configuration to file"""
        try:
            # Create backup of existing config
            if self.config_path.exists():
                backup_path = self.config_path.with_suffix('.json.backup')
                self.config_path.replace(backup_path)
            
            # Write new configuration
            with open(self.config_path, 'w') as f:
                json.dump(self.config_data, f, indent=2, default=str)
            
            self.last_modified = datetime.now()
            logger.info(f"Configuration saved to {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate current configuration and return validation results"""
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        try:
            # Validate dashboard settings
            port = self.get("dashboard.port", 8000)
            if not isinstance(port, int) or port < 1024 or port > 65535:
                validation_results["errors"].append("Dashboard port must be integer between 1024-65535")
                validation_results["valid"] = False
            
            # Validate detection thresholds
            volume_multiplier = self.get("detection.volume_spike_multiplier", 3.0)
            if not isinstance(volume_multiplier, (int, float)) or volume_multiplier <= 0:
                validation_results["errors"].append("Volume spike multiplier must be positive number")
                validation_results["valid"] = False
            
            whale_threshold = self.get("detection.whale_threshold_usd", 2000)
            if not isinstance(whale_threshold, (int, float)) or whale_threshold <= 0:
                validation_results["errors"].append("Whale threshold must be positive number")
                validation_results["valid"] = False
            
            # Validate alert thresholds
            single_threshold = self.get("alerts.anomaly_thresholds.single_anomaly", 8.0)
            multi_threshold = self.get("alerts.anomaly_thresholds.multi_anomaly", 10.0)
            critical_threshold = self.get("alerts.anomaly_thresholds.critical", 15.0)
            
            if not all(isinstance(t, (int, float)) and t > 0 for t in [single_threshold, multi_threshold, critical_threshold]):
                validation_results["errors"].append("Anomaly thresholds must be positive numbers")
                validation_results["valid"] = False
            
            if not (single_threshold < multi_threshold < critical_threshold):
                validation_results["errors"].append("Anomaly thresholds must be in ascending order")
                validation_results["valid"] = False
            
            # Validate monitoring settings
            max_markets = self.get("monitoring.max_markets", 50)
            if not isinstance(max_markets, int) or max_markets <= 0:
                validation_results["warnings"].append("Max markets should be positive integer")
            
            # Check Discord webhook if enabled
            discord_enabled = self.get("alerts.discord_enabled", False)
            if discord_enabled:
                webhook_url = self.get("alerts.discord_webhook_url", "")
                if not webhook_url or not webhook_url.startswith("https://discord.com/api/webhooks/"):
                    validation_results["errors"].append("Invalid Discord webhook URL")
                    validation_results["valid"] = False
            
        except Exception as e:
            validation_results["errors"].append(f"Configuration validation error: {e}")
            validation_results["valid"] = False
        
        return validation_results
    
    def get_dashboard_config(self) -> Dict[str, Any]:
        """Get configuration specific to dashboard operations"""
        return {
            "host": self.get("dashboard.host", "127.0.0.1"),
            "port": self.get("dashboard.port", 8000), 
            "debug": self.get("dashboard.debug", True),
            "cors_origins": self.get("dashboard.cors_origins", ["http://localhost:3000"]),
            "websocket_ping_interval": self.get("dashboard.websocket_ping_interval", 30),
            "max_clients": self.get("dashboard.max_clients", 100)
        }
    
    def get_detection_config(self) -> Dict[str, Any]:
        """Get configuration for detection algorithms"""
        return self.get("detection", {})
    
    def get_monitoring_config(self) -> Dict[str, Any]:
        """Get configuration for monitoring settings"""
        return self.get("monitoring", {})
    
    def get_alert_config(self) -> Dict[str, Any]:
        """Get configuration for alert system"""
        return self.get("alerts", {})
    
    def refresh_config(self) -> bool:
        """Force reload configuration from file"""
        try:
            self.last_modified = None
            self.load_config()
            return True
        except Exception as e:
            logger.error(f"Error refreshing configuration: {e}")
            return False
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get summary of current configuration"""
        return {
            "config_file": str(self.config_path),
            "file_exists": self.config_path.exists(),
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
            "validation": self.validate_config(),
            "sections": list(self.config_data.keys()),
            "dashboard_enabled": True,
            "detection_algorithms": {
                "volume_detector": self.get("detection.volume_spike_multiplier") > 0,
                "whale_detector": self.get("detection.whale_threshold_usd") > 0,
                "price_detector": self.get("detection.price_change_threshold") > 0,
                "coordination_detector": self.get("detection.coordination_threshold") > 0
            }
        }