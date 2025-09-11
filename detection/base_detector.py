"""
Base Detector Class
Provides common configuration management for all detectors
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict

logger = logging.getLogger(__name__)

class DetectorBase(ABC):
    """Base class for all detection algorithms"""
    
    def __init__(self, config: Dict, detector_type: str):
        """
        Initialize base detector with configuration validation
        
        Args:
            config: Configuration dictionary (must contain 'detection' section)
            detector_type: Type of detector (e.g., 'volume', 'price', 'whale', 'coordination')
        """
        if not config:
            raise ValueError(f"{detector_type.title()}Detector requires configuration")
        
        if 'detection' not in config:
            raise ValueError(f"Configuration missing 'detection' section for {detector_type} detector")
        
        self.config = config
        self.detector_type = detector_type
        self.detection_config = config['detection']
        
        # Initialize detector-specific configuration
        self._load_detector_config()
        
        logger.info(f"🔧 {detector_type.title()}Detector initialized")
    
    @abstractmethod
    def _load_detector_config(self):
        """Load detector-specific configuration from config dict"""
        pass
    
    def _validate_config_section(self, section_name: str, required_fields: list) -> Dict:
        """Validate that a config section contains all required fields"""
        if section_name not in self.detection_config:
            raise ValueError(f"Configuration missing '{section_name}' section for {self.detector_type} detector")
        
        section = self.detection_config[section_name]
        
        for field in required_fields:
            if field not in section:
                raise ValueError(f"Configuration missing required field '{field}' in '{section_name}' section")
        
        return section