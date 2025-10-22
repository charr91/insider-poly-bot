"""
Configuration Variant Management

Defines and generates configuration variants for A/B testing detector parameters.
"""

import copy
import json
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from itertools import product


@dataclass
class ConfigurationVariant:
    """
    Represents a specific configuration variant for testing.

    A variant contains detector parameter overrides that differ from the baseline.
    """

    name: str
    description: str
    config: Dict[str, Any]
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate variant on creation"""
        if not self.name:
            raise ValueError("Variant name cannot be empty")
        if not isinstance(self.config, dict):
            raise ValueError("Config must be a dictionary")

    def to_dict(self) -> Dict[str, Any]:
        """Export variant to dictionary"""
        return {
            'name': self.name,
            'description': self.description,
            'config': self.config,
            'tags': self.tags,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConfigurationVariant':
        """Create variant from dictionary"""
        return cls(
            name=data['name'],
            description=data['description'],
            config=data['config'],
            tags=data.get('tags', []),
            metadata=data.get('metadata', {})
        )

    def get_parameter(self, path: str, default: Any = None) -> Any:
        """
        Get a parameter value using dot notation.

        Args:
            path: Parameter path (e.g., 'whale_thresholds.whale_threshold_usd')
            default: Default value if path not found

        Returns:
            Parameter value or default
        """
        parts = path.split('.')
        current = self.config

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default

        return current

    def set_parameter(self, path: str, value: Any):
        """
        Set a parameter value using dot notation.

        Args:
            path: Parameter path (e.g., 'whale_thresholds.whale_threshold_usd')
            value: Value to set
        """
        parts = path.split('.')
        current = self.config

        # Navigate to the parent of the target parameter
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        # Set the final parameter
        current[parts[-1]] = value


class VariantGenerator:
    """
    Generates configuration variants for systematic parameter testing.

    Supports:
    - Single parameter sweeps
    - Grid search across multiple parameters
    - Random sampling
    - Predefined variant templates
    """

    def __init__(self, base_config: Dict[str, Any]):
        """
        Initialize variant generator.

        Args:
            base_config: Baseline configuration to build variants from
        """
        self.base_config = copy.deepcopy(base_config)

    def sweep_parameter(
        self,
        param_path: str,
        values: List[Any],
        name_template: str = None,
        description_template: str = None
    ) -> List[ConfigurationVariant]:
        """
        Generate variants by sweeping a single parameter across multiple values.

        Args:
            param_path: Parameter path in dot notation (e.g., 'whale_thresholds.whale_threshold_usd')
            values: List of values to test
            name_template: Template for variant names (use {value} placeholder)
            description_template: Template for descriptions (use {value} placeholder)

        Returns:
            List of configuration variants
        """
        if not values:
            raise ValueError("Values list cannot be empty")

        # Default templates
        if name_template is None:
            param_name = param_path.split('.')[-1]
            name_template = f"{param_name}_{{{value}}}"

        if description_template is None:
            description_template = f"Sweep {param_path} = {{value}}"

        variants = []
        for value in values:
            # Create a deep copy of base config
            variant_config = copy.deepcopy(self.base_config)

            # Set the parameter value
            parts = param_path.split('.')
            current = variant_config
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = value

            # Create variant
            variant = ConfigurationVariant(
                name=name_template.format(value=value),
                description=description_template.format(value=value),
                config=variant_config,
                tags=[f"sweep:{param_path}"],
                metadata={'param_path': param_path, 'param_value': value}
            )
            variants.append(variant)

        return variants

    def grid_search(
        self,
        param_grid: Dict[str, List[Any]],
        name_template: str = None,
        description_template: str = None
    ) -> List[ConfigurationVariant]:
        """
        Generate variants using grid search across multiple parameters.

        Args:
            param_grid: Dictionary mapping parameter paths to value lists
                       e.g., {'whale_thresholds.whale_threshold_usd': [5000, 10000],
                              'volume_thresholds.volume_spike_multiplier': [2.0, 3.0]}
            name_template: Template for variant names (use {params} placeholder)
            description_template: Template for descriptions

        Returns:
            List of configuration variants representing all combinations
        """
        if not param_grid:
            raise ValueError("Parameter grid cannot be empty")

        # Get all parameter combinations
        param_paths = list(param_grid.keys())
        value_lists = [param_grid[path] for path in param_paths]
        combinations = list(product(*value_lists))

        variants = []
        for i, combo in enumerate(combinations):
            # Create variant config
            variant_config = copy.deepcopy(self.base_config)

            # Set all parameters
            param_values = {}
            for param_path, value in zip(param_paths, combo):
                parts = param_path.split('.')
                current = variant_config
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                current[parts[-1]] = value

                # Store for metadata
                param_name = param_path.split('.')[-1]
                param_values[param_name] = value

            # Generate name and description
            if name_template is None:
                name = f"grid_variant_{i+1}"
            else:
                name = name_template.format(params=param_values, index=i+1)

            if description_template is None:
                param_str = ", ".join(f"{k}={v}" for k, v in param_values.items())
                description = f"Grid search: {param_str}"
            else:
                description = description_template.format(params=param_values, index=i+1)

            # Create variant
            variant = ConfigurationVariant(
                name=name,
                description=description,
                config=variant_config,
                tags=["grid_search"] + [f"param:{path}" for path in param_paths],
                metadata={'param_values': param_values, 'param_paths': param_paths}
            )
            variants.append(variant)

        return variants

    def create_named_variants(self) -> List[ConfigurationVariant]:
        """
        Create predefined named variants with common configurations.

        Returns:
            List of predefined variants (baseline, aggressive, conservative, balanced)
        """
        variants = []

        # Baseline variant (current settings)
        variants.append(ConfigurationVariant(
            name="baseline",
            description="Default configuration parameters",
            config=copy.deepcopy(self.base_config),
            tags=["baseline", "default"]
        ))

        # Aggressive variant (lower thresholds, more alerts)
        aggressive_config = copy.deepcopy(self.base_config)
        if 'whale_thresholds' in aggressive_config:
            aggressive_config['whale_thresholds']['whale_threshold_usd'] = 5000
            aggressive_config['whale_thresholds']['min_whales_for_coordination'] = 2
        if 'volume_thresholds' in aggressive_config:
            aggressive_config['volume_thresholds']['volume_spike_multiplier'] = 2.0
            aggressive_config['volume_thresholds']['z_score_threshold'] = 2.0

        variants.append(ConfigurationVariant(
            name="aggressive",
            description="Lower thresholds for more sensitive detection",
            config=aggressive_config,
            tags=["preset", "aggressive", "high_sensitivity"]
        ))

        # Conservative variant (higher thresholds, fewer alerts)
        conservative_config = copy.deepcopy(self.base_config)
        if 'whale_thresholds' in conservative_config:
            conservative_config['whale_thresholds']['whale_threshold_usd'] = 20000
            conservative_config['whale_thresholds']['min_whales_for_coordination'] = 5
        if 'volume_thresholds' in conservative_config:
            conservative_config['volume_thresholds']['volume_spike_multiplier'] = 4.0
            conservative_config['volume_thresholds']['z_score_threshold'] = 4.0

        variants.append(ConfigurationVariant(
            name="conservative",
            description="Higher thresholds for high-confidence alerts only",
            config=conservative_config,
            tags=["preset", "conservative", "low_sensitivity"]
        ))

        # Balanced variant (middle ground)
        balanced_config = copy.deepcopy(self.base_config)
        if 'whale_thresholds' in balanced_config:
            balanced_config['whale_thresholds']['whale_threshold_usd'] = 12000
            balanced_config['whale_thresholds']['min_whales_for_coordination'] = 3
        if 'volume_thresholds' in balanced_config:
            balanced_config['volume_thresholds']['volume_spike_multiplier'] = 2.5
            balanced_config['volume_thresholds']['z_score_threshold'] = 2.5

        variants.append(ConfigurationVariant(
            name="balanced",
            description="Balanced approach between sensitivity and precision",
            config=balanced_config,
            tags=["preset", "balanced", "medium_sensitivity"]
        ))

        return variants

    def export_variants(self, variants: List[ConfigurationVariant], filepath: str):
        """
        Export variants to JSON file.

        Args:
            variants: List of variants to export
            filepath: Output file path
        """
        data = {
            'base_config': self.base_config,
            'variants': [v.to_dict() for v in variants]
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load_variants(cls, filepath: str) -> tuple[Dict[str, Any], List[ConfigurationVariant]]:
        """
        Load variants from JSON file.

        Args:
            filepath: Input file path

        Returns:
            Tuple of (base_config, variants)
        """
        with open(filepath, 'r') as f:
            data = json.load(f)

        base_config = data['base_config']
        variants = [ConfigurationVariant.from_dict(v) for v in data['variants']]

        return base_config, variants


def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two configuration dictionaries.

    Args:
        base: Base configuration
        override: Override configuration (takes precedence)

    Returns:
        Merged configuration
    """
    result = copy.deepcopy(base)

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dicts
            result[key] = merge_configs(result[key], value)
        else:
            # Override value
            result[key] = copy.deepcopy(value)

    return result
