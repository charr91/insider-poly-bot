"""
Utility functions for detection modules.
Provides common functionality to avoid code duplication.
"""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class TradeNormalizer:
    """Handles normalization of trade data from different sources."""
    
    @staticmethod
    def normalize_timestamp(timestamp: Any) -> Optional[pd.Timestamp]:
        """
        Normalize timestamp from various formats to pandas Timestamp with UTC timezone.
        
        Args:
            timestamp: Timestamp in various formats (int, float, str, datetime)
            
        Returns:
            Normalized pandas Timestamp with UTC timezone, or None if invalid
        """
        if not timestamp:
            return None
            
        try:
            if isinstance(timestamp, (int, float)):
                return pd.to_datetime(timestamp, unit='s', utc=True)
            elif isinstance(timestamp, str):
                # Handle different string formats
                if 'Z' in timestamp:
                    timestamp = timestamp.replace('Z', '+00:00')
                
                try:
                    return pd.to_datetime(timestamp, utc=True)
                except:
                    # Fallback for various string formats
                    return pd.to_datetime(timestamp, utc=True, errors='coerce')
            else:
                # Handle datetime objects or other formats
                return pd.to_datetime(timestamp, utc=True)
        except (ValueError, TypeError, OverflowError):
            logger.debug(f"Failed to normalize timestamp: {timestamp}")
            return None
    
    @staticmethod
    def normalize_price(trade: Dict[str, Any]) -> float:
        """
        Extract and normalize price from trade data.
        
        Args:
            trade: Trade dictionary with various possible price field names
            
        Returns:
            Normalized price as float, or 0.0 if invalid
        """
        try:
            price_value = trade.get('price', trade.get('feeRate', trade.get('outcome_price', 0)))
            return float(price_value) if price_value is not None else 0.0
        except (ValueError, TypeError):
            return 0.0
    
    @staticmethod
    def normalize_size(trade: Dict[str, Any]) -> float:
        """
        Extract and normalize size/amount from trade data.
        
        Args:
            trade: Trade dictionary with various possible size field names
            
        Returns:
            Normalized size as float, or 0.0 if invalid
        """
        try:
            size_value = trade.get('size', trade.get('amount', trade.get('shares', 0)))
            return float(size_value) if size_value is not None else 0.0
        except (ValueError, TypeError):
            return 0.0
    
    @staticmethod
    def normalize_side(trade: Dict[str, Any]) -> str:
        """
        Extract and normalize trading side from trade data.
        
        Args:
            trade: Trade dictionary with various possible side field names
            
        Returns:
            Normalized side as uppercase string ('BUY', 'SELL', or 'UNKNOWN')
        """
        side_value = trade.get('side', trade.get('type', 'BUY'))
        if isinstance(side_value, str):
            return side_value.upper()
        return 'UNKNOWN'
    
    @staticmethod
    def normalize_maker(trade: Dict[str, Any]) -> str:
        """
        Extract and normalize maker/user address from trade data.
        
        Args:
            trade: Trade dictionary with various possible maker field names
            
        Returns:
            Normalized maker address or 'unknown'
        """
        return trade.get('maker', trade.get('trader', trade.get('user', 'unknown')))
    
    @classmethod
    def normalize_trade(cls, trade: Dict[str, Any], require_timestamp: bool = True) -> Optional[Dict[str, Any]]:
        """
        Normalize a complete trade object with all fields.
        
        Args:
            trade: Raw trade dictionary
            require_timestamp: Whether timestamp is required for validity
            
        Returns:
            Normalized trade dictionary, or None if invalid
        """
        try:
            timestamp = cls.normalize_timestamp(
                trade.get('timestamp', trade.get('createdAt', trade.get('created_at')))
            )
            price = cls.normalize_price(trade)
            size = cls.normalize_size(trade)
            
            # Validate required fields
            if price <= 0:
                return None
            
            if require_timestamp and timestamp is None:
                return None
            
            result = {
                'price': price,
                'size': size,
                'volume_usd': price * size,
                'side': cls.normalize_side(trade),
                'maker': cls.normalize_maker(trade)
            }
            
            # Only add timestamp if available
            if timestamp is not None:
                result['timestamp'] = timestamp
            
            return result
        except Exception as e:
            logger.debug(f"Failed to normalize trade: {e}")
            return None
    
    @classmethod
    def normalize_trades(cls, trades: List[Dict[str, Any]], require_timestamp: bool = True) -> List[Dict[str, Any]]:
        """
        Normalize a list of trades, filtering out invalid ones.
        
        Args:
            trades: List of raw trade dictionaries
            require_timestamp: Whether timestamp is required for validity
            
        Returns:
            List of normalized trade dictionaries
        """
        normalized = []
        for trade in trades:
            normalized_trade = cls.normalize_trade(trade, require_timestamp=require_timestamp)
            if normalized_trade is not None:
                normalized.append(normalized_trade)
        return normalized


class ThresholdValidator:
    """Handles threshold validation and comparison with floating point tolerance."""
    
    FLOAT_TOLERANCE = 1e-6
    
    @classmethod
    def meets_threshold(cls, value: float, threshold: float, inclusive: bool = True) -> bool:
        """
        Check if value meets threshold with floating point tolerance.
        
        Args:
            value: Value to check
            threshold: Threshold to compare against
            inclusive: Whether to include exact threshold value
            
        Returns:
            True if value meets threshold
        """
        if inclusive:
            return value >= (threshold - cls.FLOAT_TOLERANCE)
        else:
            return value > (threshold + cls.FLOAT_TOLERANCE)
    
    @classmethod
    def calculate_z_score(cls, value: float, mean: float, std: float) -> float:
        """
        Calculate z-score with protection against division by zero.
        
        Args:
            value: Value to calculate z-score for
            mean: Mean of the distribution
            std: Standard deviation of the distribution
            
        Returns:
            Z-score value
        """
        return (value - mean) / (std + cls.FLOAT_TOLERANCE)


def create_consistent_early_return(
    anomaly: bool = False,
    reason: str = "",
    additional_fields: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a consistent structure for early returns from detector methods.
    
    Args:
        anomaly: Whether an anomaly was detected
        reason: Reason for the result
        additional_fields: Additional fields to include
        
    Returns:
        Consistent result dictionary
    """
    result = {
        'anomaly': anomaly,
        'reason': reason,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    if additional_fields:
        result.update(additional_fields)
    
    return result