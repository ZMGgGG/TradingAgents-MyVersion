from __future__ import annotations

import json
import threading
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .models import PaperTradingResult


LEDGER_VERSION = "1"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _model_dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return dict(value or {})


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _date_text(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value or "")[:10]


def _parse_date(value: Any) -> date | None:
    text = _date_text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def quote_staleness_days(as_of: Any, reference_date: Any | None = None) -> int | None:
    quote_date = _parse_date(as_of)
    if quote_date is None:
        return None
    reference = _parse_date(reference_date) if reference_date is not None else date.today()
    if reference is None:
        return None
    return max(0, (reference - quote_date).days)


class MarketDataStamp(BaseModel):
    symbol: str = ""
    as_of: str = ""
    vendor: str = ""
    stale_after_days: int = 1
    staleness_days: int | None = None

    @property
    def is_stale(self) -> bool:
        return self.staleness_days is not None and self.staleness_days > self.stale_after_days


class PaperEpisode(BaseModel):
    episode_id: str
    mode: str
    simulation_type: str = ""
    ticker: str
    asset_type: str = "stock"
    source_run_id: str = ""
    signal_date: str = ""
    decision_date: str = ""
    execution_date: str = ""
    horizon_days: int = 20
    benchmark: str = ""
    thesis: str = ""
    rating: str = ""
    action: str = ""
    target_position_size: float = 0.0
    confidence: float = 0.0
    risk_gate_approved: bool = True
    entry_price: float | None = None
    current_price: float | None = None
    benchmark_entry_price: float | None = None
    benchmark_current_price: float | None = None
    benchmark_return: float | None = None
    strategy_return: float | None = None
    status: str = "tracking"
    resolved: bool = False
    reason: str = ""
    initial_capital: float = 0.0
    final_equity: float | None = None
    final_return: float | None = None
    alpha_return: float | None = None
    order: dict[str, Any] = Field(default_factory=dict)
    fills: list[dict[str, Any]] = Field(default_factory=list)
    snapshots: list[dict[str, Any]] = Field(default_factory=list)
    market_data: MarketDataStamp = Field(default_factory=MarketDataStamp)
    tags: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)

    @classmethod
    def from_paper_result(
        cls,
        result: PaperTradingResult,
        mode: str,
        *,
        source_run_id: str = "",
        thesis: str = "",
        confidence: float = 0.0,
        benchmark: str = "",
        initial_capital: float | None = None,
        market_vendor: str = "",
        market_as_of: str = "",
        reference_date: str | None = None,
        tags: dict[str, Any] | None = None,
        episode_id: str | None = None,
    ) -> "PaperEpisode":
        order = _model_dump(result.order) if result.order else {}
        fills = [_model_dump(fill) for fill in result.fills]
        snapshots = [_model_dump(snapshot) for snapshot in result.snapshots]
        final_snapshot = snapshots[-1] if snapshots else {}
        first_fill = fills[0] if fills else {}
        target_size = _safe_float(order.get("target_position_size")) or 0.0
        resolved = bool(result.resolved)
        final_return = _safe_float(final_snapshot.get("total_return"))
        final_equity = _safe_float(final_snapshot.get("equity"))
        resolved_initial = _safe_float(initial_capital)
        if resolved_initial is None:
            if final_equity is not None and final_return is not None and final_return != -1.0:
                resolved_initial = final_equity / (1.0 + final_return)
            else:
                resolved_initial = final_equity or 0.0

        signal_date = _date_text(result.trade_date)
        action = str(order.get("action") or "").strip().lower()
        ticker = str(result.ticker or order.get("ticker") or "").strip().upper()
        final_positions = final_snapshot.get("positions") if isinstance(final_snapshot.get("positions"), dict) else {}
        final_position = final_positions.get(ticker) if isinstance(final_positions.get(ticker), dict) else {}
        episode_id = episode_id or make_episode_id(
            mode=mode,
            ticker=ticker,
            signal_date=signal_date,
            horizon_days=result.holding_days,
            source_run_id=source_run_id or str(order.get("source_run_id") or ""),
            action=action,
        )
        status = _episode_status(mode, resolved=resolved, fill_count=len(fills))
        data_as_of = market_as_of or _date_text(final_snapshot.get("trade_date") or result.trade_date)
        staleness_days = quote_staleness_days(data_as_of, reference_date)

        return cls(
            episode_id=episode_id,
            mode=mode,
            simulation_type=_simulation_type_for_mode(mode),
            ticker=ticker,
            asset_type=str(order.get("asset_type") or "stock"),
            source_run_id=source_run_id or str(order.get("source_run_id") or ""),
            signal_date=signal_date,
            decision_date=signal_date,
            execution_date=_date_text(first_fill.get("trade_date") or signal_date),
            horizon_days=int(result.holding_days or order.get("horizon_days") or 20),
            benchmark=benchmark,
            thesis=thesis or str(order.get("thesis") or ""),
            rating=str(order.get("rating") or ""),
            action=action,
            target_position_size=target_size,
            confidence=max(0.0, min(1.0, float(confidence or 0.0))),
            risk_gate_approved=bool(order.get("risk_gate_approved", True)),
            entry_price=_safe_float(first_fill.get("price") or order.get("entry_price")),
            current_price=_safe_float(final_position.get("last_price")),
            strategy_return=final_return,
            status=status,
            resolved=resolved,
            reason=str(result.reason or ""),
            initial_capital=float(resolved_initial or 0.0),
            final_equity=final_equity,
            final_return=final_return,
            order=order,
            fills=fills,
            snapshots=snapshots,
            market_data=MarketDataStamp(
                symbol=ticker,
                as_of=data_as_of,
                vendor=market_vendor,
                staleness_days=staleness_days,
            ),
            tags=dict(tags or {}),
        )

    @classmethod
    def from_backtest_trade(
        cls,
        trade: Any,
        *,
        mode: str = "backtest",
        source_run_id: str = "",
        thesis: str = "",
        tags: dict[str, Any] | None = None,
        episode_id: str | None = None,
    ) -> "PaperEpisode":
        payload = _model_dump(trade)
        ticker = str(payload.get("ticker") or "").strip().upper()
        signal_date = _date_text(payload.get("trade_date"))
        horizon_days = int(payload.get("holding_days") or 20)
        action = str(payload.get("action") or "").strip().lower()
        episode_id = episode_id or make_episode_id(
            mode=mode,
            ticker=ticker,
            signal_date=signal_date,
            horizon_days=horizon_days,
            source_run_id=source_run_id,
            action=action,
        )
        final_return = _safe_float(payload.get("executed_return"))
        initial_capital = _safe_float(payload.get("initial_capital")) or 0.0

        return cls(
            episode_id=episode_id,
            mode=mode,
            simulation_type=_simulation_type_for_mode(mode),
            ticker=ticker,
            asset_type=str(payload.get("asset_type") or "stock"),
            source_run_id=source_run_id,
            signal_date=signal_date,
            decision_date=signal_date,
            execution_date=signal_date,
            horizon_days=horizon_days,
            benchmark=str(payload.get("benchmark") or ""),
            thesis=thesis,
            rating=str(payload.get("rating") or ""),
            action=action,
            target_position_size=float(payload.get("target_position_size") or 0.0),
            confidence=max(0.0, min(1.0, float(payload.get("confidence") or 0.0))),
            risk_gate_approved=bool(payload.get("risk_gate_approved", True)),
            status="completed",
            resolved=True,
            initial_capital=initial_capital,
            final_equity=_safe_float(payload.get("ending_capital")),
            final_return=final_return,
            alpha_return=_safe_float(payload.get("executed_alpha_return")),
            order={
                "rating": payload.get("rating"),
                "action": action,
                "target_position_size": payload.get("target_position_size"),
                "risk_gate_approved": payload.get("risk_gate_approved"),
            },
            tags=dict(tags or {}),
        )


class PaperEpisodeBook(BaseModel):
    version: str = LEDGER_VERSION
    episodes: list[PaperEpisode] = Field(default_factory=list)
    updated_at: str = Field(default_factory=_now_iso)


def make_episode_id(
    *,
    mode: str,
    ticker: str,
    signal_date: str,
    horizon_days: int,
    source_run_id: str = "",
    action: str = "",
) -> str:
    seed = "|".join(
        [
            "paper-episode",
            mode,
            source_run_id,
            ticker.upper(),
            signal_date,
            str(horizon_days),
            action.lower(),
        ]
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def summarize_episodes(episodes: list[PaperEpisode]) -> dict[str, Any]:
    return {
        "total_episodes": len(episodes),
        "mode_counts": _count_by(episodes, "mode"),
        "simulation_type_counts": _count_by(episodes, "simulation_type"),
        "status_counts": _count_by(episodes, "status"),
        "facets": {
            "mode": _facet_stats(episodes, "mode"),
            "simulation_type": _facet_stats(episodes, "simulation_type"),
            "asset_type": _facet_stats(episodes, "asset_type"),
            "ticker": _facet_stats(episodes, "ticker"),
            "rating": _facet_stats(episodes, "rating"),
            "action": _facet_stats(episodes, "action"),
        },
        **_aggregate_stats(episodes),
    }


class PaperEpisodeLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> PaperEpisodeBook:
        if not self.path.exists():
            return PaperEpisodeBook()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return PaperEpisodeBook(**payload)
        except Exception as error:
            raise ValueError(f"Could not load paper episode ledger: {self.path}") from error

    def save(self, book: PaperEpisodeBook) -> None:
        book.updated_at = _now_iso()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = self.path.with_name(
            f"{self.path.name}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp"
        )
        tmp_file.write_text(
            json.dumps(book.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_file.replace(self.path)

    def upsert(self, episode: PaperEpisode) -> PaperEpisodeBook:
        book = self.load()
        for index, existing in enumerate(book.episodes):
            if existing.episode_id == episode.episode_id:
                episode.created_at = existing.created_at
                episode.updated_at = _now_iso()
                book.episodes[index] = episode
                self.save(book)
                return book
        book.episodes.append(episode)
        self.save(book)
        return book

    def append_from_paper_result(
        self,
        result: PaperTradingResult,
        mode: str,
        **kwargs: Any,
    ) -> PaperEpisodeBook:
        return self.upsert(PaperEpisode.from_paper_result(result, mode, **kwargs))

    def summary(self) -> dict[str, Any]:
        return summarize_episodes(self.load().episodes)


def _episode_status(mode: str, *, resolved: bool, fill_count: int) -> str:
    if not resolved:
        return "unresolved"
    if fill_count == 0:
        return "no_trade"
    if mode == "live":
        return "tracking"
    return "completed"


def _simulation_type_for_mode(mode: str) -> str:
    normalized = str(mode or "").strip().lower()
    if normalized in {"backtest", "historical_replay"}:
        return "backtest"
    if normalized in {"forward_test", "forecast", "forecast_observation"}:
        return "forecast"
    if normalized in {"live", "paper_trade", "paper_account"}:
        return "paper_trade"
    return normalized or "unknown"


def _count_by(episodes: list[PaperEpisode], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for episode in episodes:
        key = str(getattr(episode, field) or "unknown")
        if field == "simulation_type" and key == "unknown":
            key = _simulation_type_for_mode(episode.mode)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _facet_stats(episodes: list[PaperEpisode], field: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[PaperEpisode]] = {}
    for episode in episodes:
        key = str(getattr(episode, field) or "unknown")
        if field == "simulation_type" and key == "unknown":
            key = _simulation_type_for_mode(episode.mode)
        grouped.setdefault(key, []).append(episode)
    return {key: _aggregate_stats(items) for key, items in sorted(grouped.items())}


def _aggregate_stats(episodes: list[PaperEpisode]) -> dict[str, Any]:
    observed = [
        episode for episode in episodes
        if episode.resolved and episode.final_return is not None
    ]
    returns = [float(episode.final_return or 0.0) for episode in observed]
    compounded = 1.0
    for item in returns:
        compounded *= 1.0 + item
    wins = len([item for item in returns if item > 0])
    confidence_values = [episode.confidence for episode in observed if episode.confidence > 0]
    target_sizes = [episode.target_position_size for episode in observed]
    return {
        "count": len(episodes),
        "observed_count": len(observed),
        "total_return": compounded - 1.0 if returns else 0.0,
        "average_return": sum(returns) / len(returns) if returns else 0.0,
        "win_rate": wins / len(returns) if returns else 0.0,
        "average_confidence": (
            sum(confidence_values) / len(confidence_values)
            if confidence_values
            else 0.0
        ),
        "average_target_position_size": (
            sum(target_sizes) / len(target_sizes)
            if target_sizes
            else 0.0
        ),
    }
