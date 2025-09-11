# 🧪 Testing Guide

Comprehensive testing documentation for the Polymarket Insider Trading Detection Bot.

## 📋 Overview

The bot includes a comprehensive test suite with **240 unit and integration tests** covering all detection algorithms, data sources, and system components. The testing infrastructure follows professional best practices with shared utilities, factories, and fixtures.

## 🏗️ Test Architecture

### Test Structure
```
tests/
├── fixtures/                   # Shared test utilities
│   ├── data_generators.py     # Mock data generation
│   └── detector_fixtures.py   # Shared detector and data fixtures
├── integration/               # Integration tests
│   ├── test_data_api_client.py
│   └── test_websocket_client.py
└── unit/                      # Unit tests
    ├── test_configuration_variations.py
    ├── test_coordination_detector.py
    ├── test_price_detector.py
    ├── test_volume_detector.py
    └── test_whale_detector.py
```

### Test Categories

#### 🔗 Integration Tests
- **Data API Client**: Tests real API interactions and data fetching
- **WebSocket Client**: Tests real-time data stream processing
- **End-to-End Flows**: Tests complete detection pipelines

#### 🧩 Unit Tests
- **Detection Algorithms**: Comprehensive testing of all detection logic
- **Configuration Handling**: Tests for various configuration scenarios
- **Edge Cases**: Boundary conditions, invalid data, error handling
- **Performance**: Large dataset handling and memory efficiency

## 🚀 Running Tests

### Prerequisites
```bash
# Install test dependencies
pip install pytest pytest-mock pytest-asyncio

# Ensure you're in the project directory
cd insider-poly-bot
```

### Basic Test Execution

#### Run All Tests
```bash
# Complete test suite (240 tests)
python -m pytest

# With verbose output
python -m pytest -v

# With coverage report
python -m pytest --cov=detection --cov=data_sources --cov=alerts
```

#### Run Specific Test Categories
```bash
# Only unit tests
python -m pytest tests/unit/

# Only integration tests  
python -m pytest tests/integration/

# Specific detector tests
python -m pytest tests/unit/test_whale_detector.py
python -m pytest tests/unit/test_volume_detector.py
```

#### Run Specific Tests
```bash
# Single test method
python -m pytest tests/unit/test_whale_detector.py::TestWhaleDetector::test_detect_whale_activity_single_whale

# Test pattern matching
python -m pytest -k "whale_detection"
python -m pytest -k "volume_spike"
```

### Advanced Test Options

#### Debug Mode
```bash
# Stop on first failure with detailed output
python -m pytest -x -v -s

# Run tests with debug output
python -m pytest --tb=long --show-capture=all
```

#### Performance Testing
```bash
# Run memory-intensive tests
python -m pytest -k "memory_efficiency"

# Run thread safety tests
python -m pytest -k "thread_safety"
```

## 🔧 Test Configuration

### Configuration Files
```bash
# Test configuration
pytest.ini                     # pytest settings and test discovery

# Example test run with custom config
python -m pytest --maxfail=5 --tb=short
```

### Environment Variables
```bash
# For integration tests requiring API access
export POLYMARKET_API_KEY="your-test-key"
export DISCORD_WEBHOOK_URL="your-test-webhook"

# Run integration tests
python -m pytest tests/integration/
```

## 📊 Test Coverage

### Detection Algorithm Coverage
- **Volume Detection**: 31 tests covering spike detection, baseline calculation, edge cases
- **Whale Detection**: 25 tests covering trade analysis, coordination detection, thresholds  
- **Price Detection**: 30 tests covering movement analysis, accumulation patterns, volatility
- **Coordination Detection**: 15 tests covering multi-wallet analysis, timing patterns

### Key Test Scenarios

#### Normal Operations
- ✅ Valid trade data processing
- ✅ Configuration loading and validation
- ✅ Normal market conditions
- ✅ Expected threshold behaviors

#### Edge Cases  
- ✅ Empty or invalid data handling
- ✅ Extreme values and boundary conditions
- ✅ Network failures and timeouts
- ✅ Malformed configuration files

#### Error Conditions
- ✅ API failures and rate limiting
- ✅ Invalid timestamp formats
- ✅ Missing required fields
- ✅ Database connection issues

## 🏭 Test Data Generation

### MockDataGenerator
The `tests/fixtures/data_generators.py` provides realistic test data:

```python
from tests.fixtures.data_generators import MockDataGenerator

generator = MockDataGenerator()

# Generate different trading patterns
normal_trades = generator.generate_normal_trades(count=100)
whale_trades = generator.generate_whale_accumulation_pattern()
spike_trades = generator.generate_volume_spike_pattern(spike_multiplier=8.0)
pump_dump = generator.generate_pump_and_dump_pattern()
```

### Test Data Types
- **Normal Trading**: Realistic baseline activity
- **Whale Activity**: Large trades and accumulation patterns
- **Volume Spikes**: Unusual volume increases
- **Price Movements**: Pump-and-dump, rapid movements
- **Coordinated Trading**: Multi-wallet synchronized activity

## 🧪 Writing New Tests

### Test File Template
```python
"""
Unit tests for NewDetector class.
"""
import pytest
from detection.new_detector import NewDetector
from tests.fixtures.detector_fixtures import DetectorFactory, TradeDataFactory


class TestNewDetector:
    """Test suite for NewDetector functionality."""
    
    @pytest.fixture
    def detector(self, detector_factory):
        """Create NewDetector instance for testing."""
        return detector_factory.create_new_detector()
    
    @pytest.fixture
    def test_trades(self, trade_data_factory):
        """Generate test trade data."""
        return trade_data_factory.create_normal_trades()
    
    def test_basic_functionality(self, detector, test_trades):
        """Test basic detector functionality."""
        result = detector.detect_pattern(test_trades)
        
        assert 'anomaly' in result
        assert isinstance(result['anomaly'], bool)
```

### Best Practices for New Tests

#### Test Structure
1. **Arrange**: Set up test data and dependencies
2. **Act**: Execute the function being tested  
3. **Assert**: Verify expected outcomes

#### Use Shared Fixtures
```python
# Use factory fixtures for consistency
@pytest.fixture
def detector(self, detector_factory):
    return detector_factory.create_whale_detector(whale_threshold_usd=20000)

@pytest.fixture  
def whale_trades(self, trade_data_factory):
    return trade_data_factory.create_whale_trades()
```

#### Test Categories to Include
- **✅ Happy Path**: Normal successful operation
- **✅ Edge Cases**: Boundary conditions and unusual inputs
- **✅ Error Conditions**: Invalid data and failure scenarios
- **✅ Configuration Variations**: Different threshold settings
- **✅ Performance**: Large datasets and memory efficiency

#### Parameterized Tests
```python
@pytest.mark.parametrize("threshold,expected_whales", [
    (5000, 3),   # Lower threshold, more whales
    (25000, 1),  # Higher threshold, fewer whales
    (100000, 0), # Very high threshold, no whales
])
def test_whale_threshold_sensitivity(self, detector, threshold, expected_whales):
    detector.thresholds['whale_threshold_usd'] = threshold
    # ... test logic
```

## 🔍 Debugging Tests

### Common Test Debugging Commands
```bash
# Run single test with maximum detail
python -m pytest tests/unit/test_whale_detector.py::TestWhaleDetector::test_detect_whale_activity_single_whale -xvs

# Drop into debugger on failure
python -m pytest --pdb tests/unit/test_whale_detector.py

# Show print statements and logs
python -m pytest -s --log-cli-level=DEBUG
```

### Test Data Inspection
```python
# Debug test data in failing tests
def test_debug_data(self, detector, test_trades):
    print(f"Number of trades: {len(test_trades)}")
    print(f"First trade: {test_trades[0]}")
    
    result = detector.detect_pattern(test_trades)
    print(f"Detection result: {result}")
    
    assert result['anomaly'] == expected_value
```

## 📈 Performance Testing

### Large Dataset Tests
```bash
# Run memory efficiency tests
python -m pytest -k "memory_efficiency" -v

# Run with memory profiling
pip install memory-profiler
python -m pytest --profile tests/unit/test_whale_detector.py::TestWhaleDetector::test_memory_efficiency_large_dataset
```

### Concurrent Testing
```bash
# Run thread safety tests
python -m pytest -k "thread_safety" -v

# Run tests in parallel
pip install pytest-xdist
python -m pytest -n auto
```

## 🚨 Continuous Integration

### Pre-commit Testing
```bash
# Run full test suite before commits
python -m pytest --tb=short

# Quick smoke test
python -m pytest tests/unit/test_whale_detector.py tests/unit/test_volume_detector.py
```

### CI Pipeline Tests
```yaml
# Example CI configuration
- name: Run Tests
  run: |
    python -m pytest --cov=detection --cov-report=xml
    python -m pytest tests/integration/ --slow
```

## 📚 Additional Resources

### Test Documentation
- **pytest Documentation**: https://docs.pytest.org/
- **pytest-asyncio**: For async test support
- **pytest-mock**: For mocking dependencies

### Related Documentation
- [🔧 Troubleshooting](TROUBLESHOOTING.md) - Debug test failures
- [⚙️ Configuration](CONFIGURATION.md) - Test configuration options
- [💻 Usage](USAGE.md) - Running in test environments

---

## 🎯 Quick Reference

| **Task** | **Command** |
|----------|-------------|
| Run all tests | `python -m pytest` |
| Run with coverage | `python -m pytest --cov=detection` |
| Run specific detector | `python -m pytest tests/unit/test_whale_detector.py` |
| Debug single test | `python -m pytest -xvs tests/unit/test_whale_detector.py::TestWhaleDetector::test_detect_whale_activity_single_whale` |
| Performance tests | `python -m pytest -k "memory_efficiency or thread_safety"` |
| Integration tests | `python -m pytest tests/integration/` |

💡 **Pro Tip**: Use `python -m pytest -x` to stop on the first failure for faster debugging during development.