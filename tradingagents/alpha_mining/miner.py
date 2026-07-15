from __future__ import annotations

from typing import Any

from .history import AlphaMiningHistory
from .i18n import alpha_text
from .registry import AlphaRegistry
from .schemas import AlphaCandidate, AlphaMiningResult


def _clip(value: float, floor: float = -1.0, ceiling: float = 1.0) -> float:
    return max(floor, min(ceiling, value))


def _feature_score(features: dict[str, Any]) -> float:
    if not isinstance(features, dict):
        return 0.0
    try:
        score = float(features.get("score", 0.0))
        confidence = max(0.4, min(1.0, float(features.get("confidence", 1.0))))
        source_coverage = max(0.5, min(1.0, float(features.get("source_coverage", 1.0))))
        quality_weight = max(0.3, min(1.0, float(features.get("quality_weight", 1.0))))
        return _clip(score * confidence * source_coverage * quality_weight)
    except (TypeError, ValueError):
        return 0.0


class QuantaAlphaMiner:
    """Lightweight QuantaAlpha adapter for the TradingAgents factor pipeline.

    This first implementation mines a validated alpha proxy from the structured
    signals already produced by the agent graph. The schema mirrors the
    QuantaAlpha trajectory idea: hypothesis, factor expression, validation
    status, and selected candidate. The mining backend can later be swapped for
    an LLM/evolutionary search without changing the consuming factor layer.
    """

    def __init__(
        self,
        registry: AlphaRegistry | None = None,
        history: AlphaMiningHistory | None = None,
    ):
        self.registry = registry
        self.history = history

    def mine(self, state: dict[str, Any]) -> AlphaMiningResult:
        asset_type = str(state.get("asset_type", "stock")).lower()
        market = _feature_score(state.get("market_features", {}))
        fundamentals = _feature_score(state.get("fundamentals_features", {}))
        sentiment = _feature_score(state.get("sentiment_features", {}))
        news = _feature_score(state.get("news_features", {}))
        debate = _clip(float(state.get("investment_debate_state", {}).get("signal_score", 0.0)))
        risk = _clip(float(state.get("risk_debate_state", {}).get("signal_score", 0.0)))

        if asset_type == "crypto":
            candidates = [
                self._crypto_trend_liquidity_candidate(market, sentiment, news, debate),
                self._event_sentiment_candidate(sentiment, news, debate),
                self._crypto_risk_adjusted_candidate(market, sentiment, news, debate, risk),
            ]
        else:
            candidates = [
                self._trend_quality_candidate(market, fundamentals, debate),
                self._event_sentiment_candidate(sentiment, news, debate),
                self._risk_adjusted_candidate(market, fundamentals, sentiment, news, debate, risk),
            ]
        candidates.extend(self._history_guided_candidates(state))
        selected = max(candidates, key=lambda item: abs(item.signal_score) * item.confidence)
        stability = self._stability_from_sources(state)
        redundancy_penalty = self._redundancy_penalty(candidates)
        signal = _clip(selected.signal_score * selected.confidence * stability * (1.0 - redundancy_penalty))

        return AlphaMiningResult(
            selected_alpha=selected,
            signal_score=signal,
            confidence=selected.confidence,
            stability=stability,
            redundancy_penalty=redundancy_penalty,
            candidates=candidates,
            summary=(
                alpha_text(
                    f"QuantaAlpha selected {selected.name}: signal={signal:.2f}, "
                    f"raw={selected.signal_score:.2f}, confidence={selected.confidence:.2f}, "
                    f"stability={stability:.2f}, redundancy_penalty={redundancy_penalty:.2f}.",
                    f"QuantaAlpha 选中 {selected.name}：signal={signal:.2f}，"
                    f"raw={selected.signal_score:.2f}，confidence={selected.confidence:.2f}，"
                    f"stability={stability:.2f}，redundancy_penalty={redundancy_penalty:.2f}。",
                )
            ),
        )

    def _history_guided_candidates(self, state: dict[str, Any]) -> list[AlphaCandidate]:
        if self.registry is None:
            return []
        registry_rows = self.registry.load()
        if not registry_rows:
            return []

        ticker = str(state.get("company_of_interest", ""))
        asset_type = str(state.get("asset_type", "stock")).lower() or "stock"
        related = [
            row
            for row in registry_rows
            if row.get("source")
            and (row.get("trade_date") or row.get("name"))
            and self._registry_asset_matches(row, asset_type)
        ]
        if ticker:
            same_ticker = [row for row in related if ticker in str(row.get("source", "")) or ticker in str(row.get("name", ""))]
            if same_ticker:
                related = same_ticker

        candidates: list[AlphaCandidate] = []
        for row in related[-3:]:
            try:
                candidates.append(
                    AlphaCandidate(
                        name=f"registry_{row.get('name', 'alpha')}",
                        hypothesis=str(row.get("hypothesis", "")),
                        expression=str(row.get("expression", "")),
                        signal_score=_clip(float(row.get("signal_score", 0.0))),
                        confidence=max(0.0, min(1.0, float(row.get("confidence", 0.0)))),
                        complexity=3,
                        validation_status="registry_reuse",
                        evidence=[str(item) for item in row.get("evidence", [])],
                    )
                )
            except (TypeError, ValueError):
                continue
        return candidates

    def _registry_asset_matches(self, row: dict[str, Any], asset_type: str) -> bool:
        row_asset_type = str(row.get("asset_type") or "stock").lower()
        return row_asset_type == asset_type

    def _trend_quality_candidate(self, market: float, fundamentals: float, debate: float) -> AlphaCandidate:
        signal = _clip(0.45 * market + 0.35 * fundamentals + 0.20 * debate)
        return AlphaCandidate(
            name="trend_quality_alignment",
            hypothesis=alpha_text(
                "Price trend and business quality aligned with debate conviction should improve short-to-medium horizon selection.",
                "价格趋势、业务质量与辩论共识方向一致时，更容易提升中短期选股有效性。",
            ),
            expression="0.45*market_features + 0.35*fundamentals_features + 0.20*investment_debate_signal",
            signal_score=signal,
            confidence=0.68 if abs(signal) >= 0.15 else 0.48,
            complexity=3,
            validation_status="validated_proxy",
            evidence=[
                f"market={market:.2f}",
                f"fundamentals={fundamentals:.2f}",
                f"debate={debate:.2f}",
            ],
        )

    def _crypto_trend_liquidity_candidate(
        self,
        market: float,
        sentiment: float,
        news: float,
        debate: float,
    ) -> AlphaCandidate:
        signal = _clip(0.52 * market + 0.18 * sentiment + 0.12 * news + 0.18 * debate)
        return AlphaCandidate(
            name="crypto_trend_liquidity_alignment",
            hypothesis=alpha_text(
                "For crypto assets, trend persistence is more actionable when liquidity and event sentiment do not contradict the price signal.",
                "对 crypto 资产，价格趋势若没有被流动性和事件情绪明显反向验证，其延续性信号更有交易价值。",
            ),
            expression="0.52*market_features + 0.18*sentiment_features + 0.12*news_features + 0.18*investment_debate_signal",
            signal_score=signal,
            confidence=0.66 if abs(signal) >= 0.14 else 0.46,
            complexity=4,
            validation_status="crypto_validated_proxy",
            evidence=[
                f"market={market:.2f}",
                f"sentiment={sentiment:.2f}",
                f"news={news:.2f}",
                f"debate={debate:.2f}",
            ],
        )

    def _event_sentiment_candidate(self, sentiment: float, news: float, debate: float) -> AlphaCandidate:
        signal = _clip(0.40 * sentiment + 0.40 * news + 0.20 * debate)
        return AlphaCandidate(
            name="event_sentiment_confirmation",
            hypothesis=alpha_text(
                "Event tone confirmed by sentiment proxy is more actionable than either signal alone.",
                "事件语气若被情绪代理验证，其可交易性通常高于单独依赖事件或情绪任一信号。",
            ),
            expression="0.40*sentiment_features + 0.40*news_features + 0.20*investment_debate_signal",
            signal_score=signal,
            confidence=0.62 if abs(signal) >= 0.12 else 0.42,
            complexity=3,
            validation_status="validated_proxy",
            evidence=[
                f"sentiment={sentiment:.2f}",
                f"news={news:.2f}",
                f"debate={debate:.2f}",
            ],
        )

    def _risk_adjusted_candidate(
        self,
        market: float,
        fundamentals: float,
        sentiment: float,
        news: float,
        debate: float,
        risk: float,
    ) -> AlphaCandidate:
        base = 0.25 * market + 0.20 * fundamentals + 0.15 * sentiment + 0.15 * news + 0.25 * debate
        signal = _clip(base - abs(min(risk, 0.0)) * 0.30)
        return AlphaCandidate(
            name="risk_adjusted_composite",
            hypothesis=alpha_text(
                "Composite alpha should be discounted when risk debate is materially negative.",
                "当风险辩论明显偏负时，复合 alpha 信号应当打折处理。",
            ),
            expression="weighted_features + debate_signal - 0.30*negative_risk_signal",
            signal_score=signal,
            confidence=0.72 if abs(signal) >= 0.10 else 0.50,
            complexity=6,
            validation_status="validated_proxy",
            evidence=[
                f"base={base:.2f}",
                f"risk={risk:.2f}",
            ],
        )

    def _crypto_risk_adjusted_candidate(
        self,
        market: float,
        sentiment: float,
        news: float,
        debate: float,
        risk: float,
    ) -> AlphaCandidate:
        base = 0.36 * market + 0.18 * sentiment + 0.18 * news + 0.28 * debate
        signal = _clip(base - abs(min(risk, 0.0)) * 0.36)
        return AlphaCandidate(
            name="crypto_risk_adjusted_momentum",
            hypothesis=alpha_text(
                "Crypto momentum should be discounted more aggressively when risk debate flags drawdown, liquidity, or macro stress.",
                "当风险辩论提示回撤、流动性或宏观压力时，crypto 动量信号需要更强折扣。",
            ),
            expression="crypto_weighted_momentum + debate_signal - 0.36*negative_risk_signal",
            signal_score=signal,
            confidence=0.70 if abs(signal) >= 0.10 else 0.48,
            complexity=5,
            validation_status="crypto_validated_proxy",
            evidence=[
                f"base={base:.2f}",
                f"risk={risk:.2f}",
            ],
        )

    def _stability_from_sources(self, state: dict[str, Any]) -> float:
        if str(state.get("asset_type", "stock")).lower() == "crypto":
            feature_names = ("market_features", "sentiment_features", "news_features")
        else:
            feature_names = ("market_features", "fundamentals_features", "sentiment_features", "news_features")
        populated = sum(1 for name in feature_names if isinstance(state.get(name), dict) and state[name].get("score") is not None)
        return max(0.45, min(1.0, populated / len(feature_names)))

    def _redundancy_penalty(self, candidates: list[AlphaCandidate]) -> float:
        if len(candidates) < 2:
            return 0.0
        directions = [1 if item.signal_score > 0 else -1 if item.signal_score < 0 else 0 for item in candidates]
        nonzero = [direction for direction in directions if direction != 0]
        if len(nonzero) < 2:
            return 0.0
        same_direction = len(set(nonzero)) == 1
        return 0.12 if same_direction else 0.04
