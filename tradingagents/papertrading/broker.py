from __future__ import annotations

from copy import deepcopy

from .models import PaperAccountSnapshot, PaperFill, PaperOrder, PaperPosition


class PaperBroker:
    """Minimal long-only broker for applying execution plans to a simulated account."""

    def __init__(
        self,
        initial_cash: float = 100000.0,
        commission_rate: float = 0.0,
        slippage_rate: float = 0.0,
    ):
        if initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        if commission_rate < 0:
            raise ValueError("commission_rate must be non-negative")
        if slippage_rate < 0:
            raise ValueError("slippage_rate must be non-negative")
        self.initial_cash = float(initial_cash)
        self.cash = float(initial_cash)
        self.commission_rate = float(commission_rate)
        self.slippage_rate = float(slippage_rate)
        self.positions: dict[str, PaperPosition] = {}
        self.fills: list[PaperFill] = []

    def equity(self, last_prices: dict[str, float] | None = None) -> float:
        self._mark_positions(last_prices or {})
        return self.cash + sum(position.market_value for position in self.positions.values())

    def submit_order(self, order: PaperOrder, price: float) -> PaperFill | None:
        if price <= 0:
            raise ValueError("price must be positive")
        self._mark_positions({order.ticker: price})
        if not order.risk_gate_approved:
            return None

        target_weight = self._target_weight(order.action, order.target_position_size)
        account_equity = self.equity({order.ticker: price})
        target_value = account_equity * target_weight
        current_position = self.positions.get(order.ticker)
        current_value = (current_position.quantity * price) if current_position else 0.0
        delta_value = target_value - current_value

        if abs(delta_value) < 1e-9:
            return None
        if delta_value > 0:
            return self._buy(order, self._execution_price(price, "buy"), delta_value)
        return self._sell(order, self._execution_price(price, "sell"), abs(delta_value))

    def snapshot(
        self,
        trade_date: str,
        last_prices: dict[str, float] | None = None,
    ) -> PaperAccountSnapshot:
        self._mark_positions(last_prices or {})
        positions_value = sum(position.market_value for position in self.positions.values())
        equity = self.cash + positions_value
        return PaperAccountSnapshot(
            trade_date=trade_date,
            cash=self.cash,
            positions_value=positions_value,
            equity=equity,
            total_return=(equity / self.initial_cash) - 1.0,
            positions=deepcopy(self.positions),
        )

    def _buy(self, order: PaperOrder, price: float, desired_gross: float) -> PaperFill | None:
        gross = min(desired_gross, self.cash / (1.0 + self.commission_rate))
        if gross <= 0:
            return None
        commission = gross * self.commission_rate
        quantity = gross / price
        position = self.positions.get(
            order.ticker,
            PaperPosition(ticker=order.ticker, quantity=0.0, average_cost=0.0, last_price=price),
        )
        new_quantity = position.quantity + quantity
        average_cost = (
            ((position.average_cost * position.quantity) + gross) / new_quantity
            if new_quantity
            else 0.0
        )
        self.positions[order.ticker] = PaperPosition(
            ticker=order.ticker,
            quantity=new_quantity,
            average_cost=average_cost,
            last_price=price,
        )
        self.cash -= gross + commission
        fill = PaperFill(
            ticker=order.ticker,
            trade_date=order.trade_date,
            side="buy",
            rating=order.rating,
            action=order.action,
            target_position_size=order.target_position_size,
            source_run_id=order.source_run_id,
            thesis=order.thesis,
            horizon_days=order.horizon_days,
            quantity=quantity,
            price=price,
            gross_amount=gross,
            commission=commission,
            cash_after=self.cash,
        )
        self.fills.append(fill)
        return fill

    def _sell(self, order: PaperOrder, price: float, desired_gross: float) -> PaperFill | None:
        position = self.positions.get(order.ticker)
        if position is None or position.quantity <= 0:
            return None
        quantity = min(position.quantity, desired_gross / price)
        if quantity <= 0:
            return None
        gross = quantity * price
        commission = gross * self.commission_rate
        remaining_quantity = position.quantity - quantity
        if remaining_quantity <= 1e-12:
            self.positions.pop(order.ticker, None)
        else:
            self.positions[order.ticker] = PaperPosition(
                ticker=order.ticker,
                quantity=remaining_quantity,
                average_cost=position.average_cost,
                last_price=price,
            )
        self.cash += gross - commission
        fill = PaperFill(
            ticker=order.ticker,
            trade_date=order.trade_date,
            side="sell",
            rating=order.rating,
            action=order.action,
            target_position_size=order.target_position_size,
            source_run_id=order.source_run_id,
            thesis=order.thesis,
            horizon_days=order.horizon_days,
            quantity=quantity,
            price=price,
            gross_amount=gross,
            commission=commission,
            cash_after=self.cash,
        )
        self.fills.append(fill)
        return fill

    def _mark_positions(self, last_prices: dict[str, float]) -> None:
        for ticker, price in last_prices.items():
            if ticker in self.positions and price > 0:
                position = self.positions[ticker]
                self.positions[ticker] = PaperPosition(
                    ticker=position.ticker,
                    quantity=position.quantity,
                    average_cost=position.average_cost,
                    last_price=float(price),
                )

    def _target_weight(self, action: str, target_position_size: float) -> float:
        if action == "sell":
            return 0.0
        return max(0.0, min(1.0, float(target_position_size)))

    def _execution_price(self, price: float, side: str) -> float:
        if side == "buy":
            return price * (1.0 + self.slippage_rate)
        return price * max(0.0, 1.0 - self.slippage_rate)
