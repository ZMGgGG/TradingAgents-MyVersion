from __future__ import annotations

from pydantic import BaseModel


def _clip(value: float, floor: float = -1.0, ceiling: float = 1.0) -> float:
    """Clamp a score into a bounded range."""
    return max(floor, min(ceiling, value))


class FactorScore(BaseModel):
    technical: float
    fundamentals: float
    sentiment: float
    news: float
    alpha: float
    debate: float
    risk_penalty: float
    composite_score: float
    summary: str


class FactorEngine:
    """Build a deterministic factor score from stage-one outputs."""

    def __init__(
        self,
        technical_weight: float = 0.22,
        fundamentals_weight: float = 0.24,
        sentiment_weight: float = 0.14,
        news_weight: float = 0.14,
        alpha_weight: float = 0.12,
        debate_weight: float = 0.14,
    ):
        self.technical_weight = technical_weight
        self.fundamentals_weight = fundamentals_weight
        self.sentiment_weight = sentiment_weight
        self.news_weight = news_weight
        self.alpha_weight = alpha_weight
        self.debate_weight = debate_weight

    def score(self, state: dict) -> FactorScore:
        """Compute a composite factor score from current reports and debate state."""
        weights = self._weights_for_asset_type(str(state.get("asset_type", "stock")))
        market_report = str(state.get("market_report", "")).lower()
        fundamentals_report = str(state.get("fundamentals_report", "")).lower()
        sentiment_report = str(state.get("sentiment_report", "")).lower()
        news_report = str(state.get("news_report", "")).lower()
        market_features = state.get("market_features", {})
        fundamentals_features = state.get("fundamentals_features", {})
        sentiment_features = state.get("sentiment_features", {})
        news_features = state.get("news_features", {})
        debate_signal = float(state.get("investment_debate_state", {}).get("signal_score", 0.0))
        risk_signal = float(state.get("risk_debate_state", {}).get("signal_score", 0.0))
        alpha_mining_result = state.get("alpha_mining_result", {})

        technical = self._resolve_feature_score(market_features, market_report)
        fundamentals = self._resolve_feature_score(fundamentals_features, fundamentals_report)
        sentiment = self._resolve_feature_score(sentiment_features, sentiment_report)
        news = self._resolve_feature_score(news_features, news_report)
        alpha = self._resolve_alpha_score(alpha_mining_result)
        debate = _clip(debate_signal)
        risk_penalty = abs(min(risk_signal, 0.0))

        composite = _clip(
            technical * weights["technical"]
            + fundamentals * weights["fundamentals"]
            + sentiment * weights["sentiment"]
            + news * weights["news"]
            + alpha * weights["alpha"]
            + debate * weights["debate"]
            - risk_penalty * 0.20
        )

        summary = (
            f"Factor score technical={technical:.2f}, fundamentals={fundamentals:.2f}, "
            f"sentiment={sentiment:.2f}, news={news:.2f}, alpha={alpha:.2f}, debate={debate:.2f}, "
            f"risk_penalty={risk_penalty:.2f}, composite={composite:.2f}, "
            f"asset_type={state.get('asset_type', 'stock')}, weights={weights}."
        )
        return FactorScore(
            technical=technical,
            fundamentals=fundamentals,
            sentiment=sentiment,
            news=news,
            alpha=alpha,
            debate=debate,
            risk_penalty=risk_penalty,
            composite_score=composite,
            summary=summary,
        )

    def _weights_for_asset_type(self, asset_type: str) -> dict[str, float]:
        """Use crypto-native weights when company fundamentals are not applicable."""
        if asset_type.lower() == "crypto":
            return {
                "technical": 0.30,
                "fundamentals": 0.00,
                "sentiment": 0.18,
                "news": 0.18,
                "alpha": 0.16,
                "debate": 0.18,
            }
        return {
            "technical": self.technical_weight,
            "fundamentals": self.fundamentals_weight,
            "sentiment": self.sentiment_weight,
            "news": self.news_weight,
            "alpha": self.alpha_weight,
            "debate": self.debate_weight,
        }

    def _keyword_score(self, text: str) -> float:
        """Estimate a bounded polarity score from a report body."""
        positive = sum(
            text.count(token)
            for token in ("bullish", "strong", "upside", "growth", "positive", "constructive")
        )
        negative = sum(
            text.count(token)
            for token in ("bearish", "weak", "downside", "risk", "negative", "deteriorating")
        )
        total = positive + negative
        if total == 0:
            return 0.0
        return (positive - negative) / total

    def _resolve_feature_score(self, features: dict, text: str) -> float:
        """Prefer structured feature scores; fall back to keyword polarity."""
        if isinstance(features, dict) and "score" in features:
            try:
                score = float(features["score"])
                confidence = max(0.4, min(1.0, float(features.get("confidence", 1.0))))
                source_coverage = max(0.5, min(1.0, float(features.get("source_coverage", 1.0))))
                quality_weight = max(0.3, min(1.0, float(features.get("quality_weight", 1.0))))
                return _clip(score * confidence * source_coverage * quality_weight)
            except (TypeError, ValueError):
                pass
        return _clip(self._keyword_score(text))

    def _resolve_alpha_score(self, alpha_result: dict) -> float:
        """Read the mined alpha signal produced by the alpha-mining layer."""
        if not isinstance(alpha_result, dict):
            return 0.0
        try:
            return _clip(float(alpha_result.get("signal_score", 0.0)))
        except (TypeError, ValueError):
            return 0.0
