"""Trade-level performance statistics and payoff ratios."""

from typing import Any
from engine.models.trade import Trade


def calculate_trade_statistics(trades: list[Trade]) -> dict[str, Any]:
    """Compute detailed trade execution statistics from a list of completed trades."""
    # Only trades that closed positions carry realized PnL
    closing_trades = [t for t in trades if abs(t.realized_pnl) > 1e-9]

    total_closed = len(closing_trades)
    if total_closed == 0:
        return {
            "total_trades": len(trades),
            "closed_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate_pct": 0.0,
            "loss_rate_pct": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "profit_factor": 0.0,
            "average_win": 0.0,
            "average_loss": 0.0,
            "payoff_ratio": 0.0,
            "expectancy": 0.0,
            "max_consecutive_wins": 0,
            "max_consecutive_losses": 0,
            "total_fees_paid": sum(t.fee for t in trades),
        }

    winning = [t for t in closing_trades if t.realized_pnl > 0]
    losing = [t for t in closing_trades if t.realized_pnl < 0]

    gross_profit = sum(t.realized_pnl for t in winning)
    gross_loss = abs(sum(t.realized_pnl for t in losing))

    win_rate = (len(winning) / total_closed) * 100.0
    loss_rate = (len(losing) / total_closed) * 100.0

    avg_win = (gross_profit / len(winning)) if winning else 0.0
    avg_loss = (gross_loss / len(losing)) if losing else 0.0
    payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else (float("inf") if avg_win > 0 else 0.0)

    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    else:
        profit_factor = float("inf") if gross_profit > 0 else 0.0

    # Mathematical Expectancy = (Win_Rate * Avg_Win) - (Loss_Rate * Avg_Loss)
    win_frac = len(winning) / total_closed
    loss_frac = len(losing) / total_closed
    expectancy = (win_frac * avg_win) - (loss_frac * avg_loss)

    # Consecutive streak tracking
    max_wins = 0
    current_wins = 0
    max_losses = 0
    current_losses = 0

    for t in closing_trades:
        if t.realized_pnl > 0:
            current_wins += 1
            current_losses = 0
            if current_wins > max_wins:
                max_wins = current_wins
        else:
            current_losses += 1
            current_wins = 0
            if current_losses > max_losses:
                max_losses = current_losses

    return {
        "total_trades": len(trades),
        "closed_trades": total_closed,
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "win_rate_pct": round(win_rate, 2),
        "loss_rate_pct": round(loss_rate, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else 999.0,
        "average_win": round(avg_win, 2),
        "average_loss": round(avg_loss, 2),
        "payoff_ratio": round(payoff_ratio, 2) if payoff_ratio != float("inf") else 999.0,
        "expectancy": round(expectancy, 2),
        "max_consecutive_wins": max_wins,
        "max_consecutive_losses": max_losses,
        "total_fees_paid": round(sum(t.fee for t in trades), 2),
    }
