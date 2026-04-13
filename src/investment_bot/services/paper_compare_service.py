from dataclasses import dataclass


@dataclass
class PaperCompareService:
    def compare(self, backtest_trades: list[dict], paper_trades: list[dict]) -> dict:
        matches = min(len(backtest_trades), len(paper_trades))
        pairs = zip(backtest_trades[:matches], paper_trades[:matches])
        signal_time_diff = []
        fill_price_diff = []
        pnl_diff = []
        for bt, paper in pairs:
            bt_price = float(bt.get('entry_price', 0.0) or 0.0)
            paper_price = float(paper.get('entry_price', 0.0) or 0.0)
            bt_pnl = float(bt.get('net_pnl', 0.0) or 0.0)
            paper_pnl = float(paper.get('net_pnl', 0.0) or 0.0)
            fill_price_diff.append(round(paper_price - bt_price, 4))
            pnl_diff.append(round(paper_pnl - bt_pnl, 4))
            signal_time_diff.append(0)

        return {
            'matched_count': matches,
            'backtest_count': len(backtest_trades),
            'paper_count': len(paper_trades),
            'missed_trade_count': max(len(backtest_trades) - len(paper_trades), 0),
            'avg_signal_time_diff': round(sum(signal_time_diff) / len(signal_time_diff), 4) if signal_time_diff else 0.0,
            'avg_fill_price_diff': round(sum(fill_price_diff) / len(fill_price_diff), 4) if fill_price_diff else 0.0,
            'avg_pnl_diff': round(sum(pnl_diff) / len(pnl_diff), 4) if pnl_diff else 0.0,
        }
