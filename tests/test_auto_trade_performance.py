#!/usr/bin/env python3
"""
Performance tests for AutoTradeService.

Verifies:
1. 10 symbols evaluate in <15 seconds (was 75s before optimization)
2. API calls scale with O(symbols), not O(symbols × strategies)
3. Candle caching reduces API calls by 67%
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch

from investment_bot.services.auto_trade_service import AutoTradeService
from investment_bot.services.shadow_service import ShadowService
from investment_bot.services.semi_live_service import SemiLiveService
from investment_bot.services.market_data_service import MarketDataService
from investment_bot.core.settings import Settings


class TestAutoTradeServicePerformance:
    """Performance tests for AutoTradeService.run_once()."""

    @pytest.fixture
    def mock_services(self):
        """Create mock services for performance testing."""
        settings = Settings()
        settings.symbols = [f"KRW-BTC{i}" for i in range(10)]  # 10 symbols
        settings.auto_trade_enabled = True
        settings.auto_trade_symbol = "KRW-BTC0"
        settings.auto_trade_timeframe = "m5"
        settings.auto_trade_limit = 5
        settings.auto_trade_interval_seconds = 60
        settings.auto_trade_min_krw_balance = 10000
        settings.auto_trade_target_allocation_pct = 10
        settings.auto_trade_meaningful_order_notional = 5000
        settings.auto_trade_max_total_exposure_pct = 80
        settings.auto_trade_min_managed_position_notional = 10000
        settings.min_order_notional = 1000
        
        # Mock market data service with realistic latency
        mock_market_data = Mock(spec=MarketDataService)
        mock_market_data.get_recent_candles = Mock(side_effect=lambda **kwargs: (
            time.sleep(0.1),  # Simulate 100ms API latency
            [{"open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000}]
        )[1])
        
        # Mock semi-live service
        mock_semi_live = Mock(spec=SemiLiveService)
        mock_semi_live.market_data_service = mock_market_data
        mock_semi_live.run_once = Mock(return_value={
            "decision": {
                "review": {"action": "hold", "confidence": 0.5, "latest_price": 100},
                "market_regime": {"regime": "neutral"}
            }
        })
        
        # Mock shadow service
        mock_shadow = Mock(spec=ShadowService)
        mock_shadow.semi_live_service = mock_semi_live
        mock_shadow.run_once = Mock(return_value={
            "decision": {
                "review": {"action": "hold", "confidence": 0.5, "latest_price": 100},
                "market_regime": {"regime": "neutral"}
            }
        })
        mock_shadow.invalidate_cache = Mock()
        mock_shadow._get_cached_account_summary = Mock(return_value={"krw_cash": 100000})
        
        # Mock other services
        mock_account = Mock()
        mock_account.summarize_upbit_balances = Mock(return_value={"krw_cash": 100000})
        mock_account.get_asset_balance = Mock(return_value={
            "balance": 0.1,
            "avg_buy_price": 95,
            "estimated_cost_basis": 9.5
        })
        
        mock_live_execution = Mock()
        mock_live_execution.preview_order = Mock(return_value={"allowed": True})
        mock_live_execution.submit_order = Mock(return_value={"status": "submitted"})
        
        mock_run_history = Mock()
        mock_run_history.record = Mock()
        
        mock_strategy_selection = Mock()
        mock_strategy_selection.choose = Mock(side_effect=lambda **kwargs: None)
        
        return {
            "settings": settings,
            "shadow_service": mock_shadow,
            "live_execution_service": mock_live_execution,
            "account_service": mock_account,
            "run_history_service": mock_run_history,
            "strategy_selection_service": mock_strategy_selection,
        }

    def test_10_symbol_evaluation_time(self, mock_services):
        """Verify 10 symbols evaluate in <15 seconds (was 75s before optimization)."""
        service = AutoTradeService(**mock_services)
        
        # Mock strategy list (3 strategies)
        with patch('investment_bot.services.auto_trade_service.list_enabled_strategies') as mock_list:
            mock_list.return_value = ["strategy1", "strategy2", "strategy3"]
            
            t0 = time.time()
            result = service.run_once()
            elapsed = time.time() - t0
            
            # Performance requirement: <15s for 10 symbols (was 75s)
            assert elapsed < 15.0, \
                f"Evaluation too slow: {elapsed:.2f}s (expected <15s, was 75s before optimization)"
            
            # Verify API call reduction
            # With caching: 10 symbols × 1 call = 10 calls
            # Without caching: 10 symbols × 3 strategies = 30 calls
            call_count = mock_services["shadow_service"].semi_live_service.market_data_service.get_recent_candles.call_count
            assert call_count == 10, \
                f"API calls not optimized: {call_count} (expected 10, not 30)"

    def test_candle_caching_reduces_api_calls(self, mock_services):
        """Verify candles are fetched once per symbol (not per strategy)."""
        service = AutoTradeService(**mock_services)
        
        with patch('investment_bot.services.auto_trade_service.list_enabled_strategies') as mock_list:
            mock_list.return_value = ["strategy1", "strategy2", "strategy3"]
            
            service.run_once()
            
            # Count get_recent_candles calls
            call_count = mock_services["shadow_service"].semi_live_service.market_data_service.get_recent_candles.call_count
            
            # Should be 10 (once per symbol), not 30 (once per symbol per strategy)
            assert call_count == 10, \
                f"Candle caching not working: {call_count} calls (expected 10, not 30)"
            
            # Verify 67% reduction
            expected_without_optimization = 10 * 3  # 30 calls
            reduction = (expected_without_optimization - call_count) / expected_without_optimization
            assert reduction >= 0.65, \
                f"API reduction insufficient: {reduction:.1%} (expected ≥67%)"

    def test_position_sync_once_per_symbol(self, mock_services):
        """Verify position sync happens once per symbol (not per strategy)."""
        service = AutoTradeService(**mock_services)
        
        with patch('investment_bot.services.auto_trade_service.list_enabled_strategies') as mock_list:
            mock_list.return_value = ["strategy1", "strategy2", "strategy3"]
            
            service.run_once()
            
            # Count shadow_service.run_once calls with skip_position_sync
            calls = mock_services["shadow_service"].run_once.call_args_list
            
            # All calls should have skip_position_sync=True
            skip_count = sum(
                1 for call in calls 
                if call.kwargs.get('skip_position_sync', False)
            )
            
            total_calls = len(calls)
            assert skip_count == total_calls, \
                f"Position sync not skipped: {skip_count}/{total_calls} calls (expected all True)"
            
            # Verify get_asset_balance called once per symbol (not per strategy)
            asset_call_count = mock_services["account_service"].get_asset_balance.call_count
            assert asset_call_count == 10, \
                f"Asset fetch not optimized: {asset_call_count} calls (expected 10, not 30)"

    def test_scaling_with_symbols(self, mock_services):
        """Verify performance scales linearly with symbols (not symbols × strategies)."""
        # Test with 5 symbols
        mock_services["settings"].symbols = [f"KRW-BTC{i}" for i in range(5)]
        service_5 = AutoTradeService(**mock_services)
        
        with patch('investment_bot.services.auto_trade_service.list_enabled_strategies') as mock_list:
            mock_list.return_value = ["strategy1", "strategy2", "strategy3"]
            
            t0 = time.time()
            service_5.run_once()
            time_5 = time.time() - t0
            
            # Test with 10 symbols
            mock_services["settings"].symbols = [f"KRW-BTC{i}" for i in range(10)]
            service_10 = AutoTradeService(**mock_services)
            
            t0 = time.time()
            service_10.run_once()
            time_10 = time.time() - t0
            
            # Time should roughly double (linear scaling), not triple (quadratic)
            # Allow variance for system noise
            ratio = time_10 / time_5 if time_5 > 0 else 1
            assert 1.5 < ratio < 2.5, \
                f"Scaling not linear: {time_5:.2f}s (5 symbols) → {time_10:.2f}s (10 symbols), ratio={ratio:.2f}"


class TestAutoTradeServiceMaintainability:
    """Tests to ensure optimization is preserved in future changes."""

    def test_collect_symbol_candidates_has_performance_docstring(self):
        """Verify _collect_symbol_candidates has performance documentation."""
        docstring = AutoTradeService._collect_symbol_candidates.__doc__
        
        assert docstring is not None, "Missing docstring"
        assert "PERFORMANCE" in docstring.upper(), "Missing performance section"
        assert "CANDLE" in docstring.upper() or "CACHE" in docstring.upper(), \
            "Missing candle caching documentation"
        assert "STRATEGY" in docstring.upper(), "Missing strategy addition guide"

    def test_shadow_service_supports_skip_position_sync(self):
        """Verify shadow_service.run_once() supports skip_position_sync parameter."""
        import inspect
        
        sig = inspect.signature(ShadowService.run_once)
        params = sig.parameters
        
        assert 'skip_position_sync' in params, "Missing skip_position_sync parameter"
        assert params['skip_position_sync'].default is False, \
            "skip_position_sync should default to False for backward compatibility"

    def test_semi_live_service_supports_candles_parameter(self):
        """Verify semi_live_service.run_once() supports candles parameter."""
        import inspect
        
        sig = inspect.signature(SemiLiveService.run_once)
        params = sig.parameters
        
        assert 'candles' in params, "Missing candles parameter"
        assert params['candles'].default is None, \
            "candles should default to None for backward compatibility"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
