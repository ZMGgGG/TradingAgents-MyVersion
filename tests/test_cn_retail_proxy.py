import pytest
import pandas as pd

from tradingagents.dataflows.cn_retail_proxy import fetch_cn_retail_proxy_bundle


@pytest.mark.unit
def test_fetch_cn_retail_proxy_bundle_collects_status_and_counts(monkeypatch):
    class _Frame:
        empty = False

        def __init__(self, rows=2):
            self._rows = rows

        def head(self, n):
            return self

        def __len__(self):
            return self._rows

        def to_csv(self, index=False):
            return "代码,热度\n300308,1\n300308,2\n"

        @property
        def columns(self):
            return ["代码", "热度"]

        def __getitem__(self, key):
            return self

        def astype(self, _dtype):
            return self

        def __eq__(self, _other):
            return True

    class _AK:
        pass

    def _hot_detail(symbol=None):
        return pd.DataFrame({"代码": ["300308", "300308"], "热度": [1, 2]})

    def _comment(symbol=None):
        return pd.DataFrame({"代码": ["300308", "300308"], "评论": [1, 2]})

    def _hot_rank():
        return pd.DataFrame({"代码": ["300308", "300308"], "热度": [1, 2]})

    def _notice(symbol=None):
        return pd.DataFrame({"代码": ["300308", "300308"], "标题": ["a", "b"]})

    _hot_detail.__name__ = "stock_hot_rank_detail_em"
    _comment.__name__ = "stock_comment_em"
    _hot_rank.__name__ = "stock_hot_rank_em"
    _notice.__name__ = "stock_individual_notice_report"

    _AK.stock_hot_rank_detail_em = _hot_detail
    _AK.stock_comment_em = _comment
    _AK.stock_hot_rank_em = _hot_rank
    _AK.stock_individual_notice_report = _notice
    _AK.stock_notice_report = None

    import sys
    monkeypatch.setitem(sys.modules, "akshare", _AK)

    result = fetch_cn_retail_proxy_bundle("300308.SZ")
    assert result.source_status["hot_rank_detail"] == "ok"
    assert result.source_sample_counts["hot_rank_detail"] == 2
    assert result.active_source_count >= 1
