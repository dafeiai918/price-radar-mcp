# -*- coding: utf-8 -*-
"""price-radar-mcp 测试：协议 + 比价逻辑"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import price_radar_mcp as pr  # noqa: E402


class ProtocolTest(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.server = pr.MCPServer("t", "1.0", pr.TOOLS)
        self.server._send = lambda m: self.sent.append(m)

    def _call(self, method, **kw):
        msg = {"jsonrpc": "2.0", "id": 1, "method": method}
        if kw:
            msg["params"] = kw
        self.server.handle(msg)
        return self.sent[-1]

    def test_initialize(self):
        self.assertEqual(self._call("initialize")["result"]["serverInfo"]["name"], "t")

    def test_tools_list(self):
        names = [t["name"] for t in self._call("tools/list")["result"]["tools"]]
        self.assertEqual(sorted(names),
                         ["compare_models", "cost_estimate", "price_table",
                          "recommend_cheap", "set_price"])

    def test_unknown_tool(self):
        self.assertEqual(self._call("tools/call", name="x", arguments={})["error"]["code"], -32602)


class PriceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._orig = pr.PRICE_PATH
        pr.PRICE_PATH = Path(self.tmp.name) / "prices.json"

    def tearDown(self):
        pr.PRICE_PATH = self._orig
        self.tmp.cleanup()

    def test_blended_price(self):
        self.assertAlmostEqual(pr.blended_price([4.0, 8.0, 5, "t"]), 5.0)

    def test_value_score_higher_for_cheaper_quality(self):
        cheap = [0.1, 0.1, 3, "a"]
        pricey = [10.0, 10.0, 3, "b"]
        self.assertGreater(pr.value_score(cheap), pr.value_score(pricey))

    def test_catalog_contains_models(self):
        data = pr.catalog()
        self.assertIn("gpt-4o", data)
        self.assertIn("deepseek-chat", data)

    def test_price_table_default_sort(self):
        text = pr.tool_price_table({})
        self.assertIn("按价格排序", text)
        self.assertIn("gpt-4o", text)

    def test_price_table_sort_value(self):
        self.assertIn("性价比", pr.tool_price_table({"sort": "value"}))

    def test_price_table_keyword(self):
        text = pr.tool_price_table({"keyword": "deepseek"})
        self.assertIn("deepseek-chat", text)
        self.assertNotIn("gpt-4o ", text)
        self.assertIn("没有匹配", pr.tool_price_table({"keyword": "zzzz"}))

    def test_compare_models(self):
        text = pr.tool_compare_models({"models": ["gpt-4o", "deepseek-chat"]})
        self.assertIn("最便宜", text)
        self.assertIn("最划算", text)
        self.assertIn("质量最高", text)

    def test_compare_requires_two(self):
        self.assertIn("至少 2 个", pr.tool_compare_models({"models": ["gpt-4o"]}))

    def test_compare_unknown_model(self):
        text = pr.tool_compare_models({"models": ["gpt-4o", "不存在模型"]})
        self.assertIn("没有价格数据", text)

    def test_recommend_cheap_by_task(self):
        text = pr.tool_recommend_cheap({"task": "写代码"})
        self.assertIn("推荐先试", text)
        self.assertIn("性价比", text)

    def test_recommend_cheap_translate_prefers_cheap(self):
        text = pr.tool_recommend_cheap({"task": "翻译文档"})
        self.assertIn("qwen-turbo", text + " " + text)  # 至少出现在候选里
        self.assertIn("推荐先试", text)

    def test_recommend_unknown_task(self):
        self.assertIn("通用性价比排行", pr.tool_recommend_cheap({"task": "随便"}))
        self.assertIn("请说明任务", pr.tool_recommend_cheap({}))

    def test_set_price_overrides_catalog(self):
        text = pr.tool_set_price({"model": "my-model", "input_price": 1.5,
                                  "output_price": 3.0, "quality": 4})
        self.assertIn("已设置", text)
        data = pr.catalog()
        self.assertEqual(data["my-model"][:2], [1.5, 3.0])
        self.assertEqual(data["my-model"][2], 4)

    def test_set_price_persists_to_disk(self):
        pr.tool_set_price({"model": "persisted", "input_price": 0.5, "output_price": 1.0})
        self.assertTrue(pr.PRICE_PATH.exists())
        saved = json.loads(pr.PRICE_PATH.read_text(encoding="utf-8"))
        self.assertIn("persisted", saved)

    def test_set_price_validation(self):
        self.assertIn("需要 model", pr.tool_set_price({"input_price": 1, "output_price": 1}))
        self.assertIn("需要 input_price", pr.tool_set_price({"model": "x", "input_price": "abc"}))

    def test_cost_estimate(self):
        text = pr.tool_cost_estimate({"input_tokens": 1_000_000, "output_tokens": 500_000})
        self.assertIn("用量", text)
        self.assertIn("$", text)
        self.assertIn("倍", text)

    def test_cost_estimate_specific_models(self):
        text = pr.tool_cost_estimate({"input_tokens": 1_000_000, "output_tokens": 0,
                                      "models": ["gpt-4o"]})
        self.assertIn("gpt-4o", text)
        self.assertIn("2.5000", text)

    def test_cost_estimate_validation(self):
        self.assertIn("需要是数字", pr.tool_cost_estimate({"input_tokens": "x"}))
        self.assertIn("请给出", pr.tool_cost_estimate({}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
