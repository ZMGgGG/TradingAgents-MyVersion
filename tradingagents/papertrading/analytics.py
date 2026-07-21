from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _equity_points(account: dict[str, Any]) -> list[dict[str, Any]]:
    snapshots = [
        item for item in (account.get("snapshots") or [])
        if isinstance(item, dict) and _safe_float(item.get("equity")) is not None
    ]
    points = []
    for item in snapshots:
        equity = _safe_float(item.get("equity"))
        if equity is None:
            continue
        points.append(
            {
                "trade_date": str(item.get("trade_date") or ""),
                "equity": equity,
                "cash": _safe_float(item.get("cash")) or 0.0,
                "positions_value": _safe_float(item.get("positions_value")) or 0.0,
                "total_return": _safe_float(item.get("total_return")) or 0.0,
            }
        )
    return points


def _period_returns(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    returns = []
    peak = points[0]["equity"] if points else 0.0
    for index, point in enumerate(points):
        equity = point["equity"]
        peak = max(peak, equity)
        period_return = 0.0
        if index > 0 and points[index - 1]["equity"]:
            period_return = (equity / points[index - 1]["equity"]) - 1.0
        returns.append(
            {
                "trade_date": point["trade_date"],
                "return": period_return,
                "equity": equity,
                "drawdown": (equity / peak) - 1.0 if peak else 0.0,
            }
        )
    return returns


class PaperAnalyticsSkill(Protocol):
    name: str

    def compute(self, account: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class BuiltinPerformanceSkill:
    name: str = "builtin_performance"

    def compute(self, account: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        points = _equity_points(account)
        if not points:
            return {
                "summary": {},
                "returns": [],
                "message": "暂无账户快照，加入结论跟踪后会生成绩效指标。",
            }

        returns = _period_returns(points)
        period_returns = [item["return"] for item in returns[1:]]
        mean_return = sum(period_returns) / len(period_returns) if period_returns else 0.0
        variance = (
            sum((item - mean_return) ** 2 for item in period_returns) / (len(period_returns) - 1)
            if len(period_returns) > 1
            else 0.0
        )
        volatility = variance ** 0.5
        winning_periods = len([item for item in period_returns if item > 0])
        initial_cash = float(account.get("initial_cash") or points[0]["equity"] or 1.0)
        summary = {
            "observations": len(points),
            "total_return": (points[-1]["equity"] / initial_cash) - 1.0 if initial_cash else 0.0,
            "max_drawdown": min((item["drawdown"] for item in returns), default=0.0),
            "period_volatility": volatility,
            "annualized_sharpe": (mean_return / volatility) * (252 ** 0.5) if volatility else 0.0,
            "win_rate": winning_periods / len(period_returns) if period_returns else 0.0,
            "best_period_return": max(period_returns) if period_returns else 0.0,
            "worst_period_return": min(period_returns) if period_returns else 0.0,
            "latest_equity": points[-1]["equity"],
            "latest_cash": points[-1]["cash"],
            "latest_positions_value": points[-1]["positions_value"],
        }
        return {"summary": summary, "returns": returns[-240:]}


@dataclass(frozen=True)
class QuantStatsPerformanceSkill:
    name: str = "quantstats_performance"

    def compute(self, account: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        returns = context.get("returns") or _period_returns(_equity_points(account))
        if len(returns) <= 1:
            return {"available": False, "summary": {}}
        try:
            import pandas as pd
            import quantstats as qs

            series = pd.Series(
                [item["return"] for item in returns[1:]],
                index=pd.to_datetime([item["trade_date"] for item in returns[1:]], errors="coerce"),
                dtype="float64",
            ).dropna()
            if series.empty:
                return {"available": False, "summary": {}}
            return {
                "available": True,
                "summary": {
                    "sharpe": float(qs.stats.sharpe(series)),
                    "max_drawdown": float(qs.stats.max_drawdown(series)),
                    "cagr": float(qs.stats.cagr(series)),
                    "volatility": float(qs.stats.volatility(series)),
                },
            }
        except Exception as error:
            return {"available": False, "summary": {}, "message": str(error)}


@dataclass(frozen=True)
class ConclusionLifecycleSkill:
    name: str = "conclusion_lifecycle"

    def compute(self, account: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        fills = [item for item in (account.get("fills") or []) if isinstance(item, dict)]
        positions = account.get("positions") if isinstance(account.get("positions"), dict) else {}
        tracks = []
        status_counts = {"tracking": 0, "due_review": 0, "exited": 0}
        try:
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc)
        except Exception:
            now = None

        for fill in reversed(fills):
            if str(fill.get("side") or "").lower() == "sell":
                continue
            ticker = str(fill.get("ticker") or "")
            position = positions.get(ticker) if isinstance(positions.get(ticker), dict) else {}
            quantity = _safe_float(position.get("quantity")) or 0.0
            entry_price = _safe_float(fill.get("price")) or 0.0
            last_price = _safe_float(position.get("last_price")) or entry_price
            horizon_days = int(_safe_float(fill.get("horizon_days")) or 20)
            age_days = 0
            if now is not None:
                try:
                    raw_date = str(fill.get("trade_date") or "").replace("Z", "+00:00")
                    opened_at = datetime.fromisoformat(raw_date)
                    if opened_at.tzinfo is None:
                        opened_at = opened_at.replace(tzinfo=timezone.utc)
                    age_days = max(0, (now - opened_at).days)
                except Exception:
                    age_days = 0
            status = "exited" if quantity <= 0 else ("due_review" if age_days >= horizon_days else "tracking")
            status_counts[status] += 1
            tracks.append(
                {
                    "ticker": ticker,
                    "trade_date": fill.get("trade_date"),
                    "rating": fill.get("rating") or fill.get("action") or "Manual",
                    "action": fill.get("action") or fill.get("side"),
                    "source_run_id": fill.get("source_run_id") or "",
                    "thesis": fill.get("thesis") or "",
                    "target_position_size": _safe_float(fill.get("target_position_size")) or 0.0,
                    "horizon_days": horizon_days,
                    "age_days": age_days,
                    "progress": min(1.0, age_days / horizon_days) if horizon_days else 1.0,
                    "current_return": (last_price / entry_price) - 1.0 if entry_price else 0.0,
                    "status": status,
                }
            )
        return {
            "summary": {"track_counts": status_counts, "track_total": len(tracks)},
            "tracks": tracks[:50],
        }


class PaperAnalyticsSkillRegistry:
    def __init__(self, skills: list[PaperAnalyticsSkill] | None = None):
        self.skills = skills or [BuiltinPerformanceSkill(), ConclusionLifecycleSkill(), QuantStatsPerformanceSkill()]

    def describe(self) -> list[dict[str, Any]]:
        descriptions = {
            "builtin_performance": {
                "label": "基础绩效",
                "description": "基于账户快照计算收益、回撤、波动、Sharpe 和胜率。",
                "default_enabled": True,
                "available": True,
            },
            "conclusion_lifecycle": {
                "label": "结论生命周期",
                "description": "按观察周期统计跟踪中、待复盘、已退出的研究结论。",
                "default_enabled": True,
                "available": True,
            },
            "quantstats_performance": {
                "label": "QuantStats",
                "description": "安装 QuantStats 后提供增强绩效指标。",
                "default_enabled": False,
                "available": self._module_available("quantstats"),
            },
        }
        return [
            {"name": skill.name, **descriptions.get(skill.name, {"label": skill.name, "description": "", "default_enabled": False, "available": True})}
            for skill in self.skills
        ]

    def _module_available(self, module_name: str) -> bool:
        try:
            __import__(module_name)
            return True
        except Exception:
            return False

    def run(
        self,
        account: dict[str, Any],
        requested: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        selected = set(requested or [])
        context = dict(context or {})
        summary: dict[str, Any] = {}
        returns: list[dict[str, Any]] = []
        tracks: list[dict[str, Any]] = []
        executed: list[str] = []
        unavailable: list[str] = []
        messages: list[str] = []

        for skill in self.skills:
            if selected and skill.name not in selected:
                continue
            result = skill.compute(account, {**context, "summary": summary})
            executed.append(skill.name)
            if result.get("summary"):
                if skill.name == "quantstats_performance":
                    summary["quantstats"] = result["summary"]
                else:
                    summary.update(result["summary"])
            if result.get("returns"):
                returns = result["returns"]
                context["returns"] = returns
            if result.get("tracks"):
                tracks = result["tracks"]
                context["tracks"] = tracks
            if result.get("available") is False:
                unavailable.append(skill.name)
            if result.get("message"):
                messages.append(str(result["message"]))

        quantstats_available = "quantstats_performance" not in unavailable and "quantstats" in summary
        if not messages and "quantstats_performance" in executed and not quantstats_available:
            messages.append("QuantStats 未安装，当前使用内置绩效指标。")

        return {
            "summary": summary,
            "returns": returns,
            "tracks": tracks,
            "provider": "+".join([name for name in executed if name not in unavailable]) or "none",
            "skills": executed,
            "unavailable_skills": unavailable,
            "quantstats_available": quantstats_available,
            "message": "；".join(messages),
        }


def run_paper_analytics(
    account: dict[str, Any],
    requested: list[str] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return PaperAnalyticsSkillRegistry().run(account, requested=requested, context=context)


def list_paper_analytics_skills() -> list[dict[str, Any]]:
    return PaperAnalyticsSkillRegistry().describe()
