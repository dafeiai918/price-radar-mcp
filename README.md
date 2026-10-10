# price-radar-mcp · 模型价格雷达 MCP

**让 AI 直接比价：「写代码最省的方案是什么？」「这几个哪个便宜？」「这样跑一次多少钱？」**

零依赖 · 单文件 · stdio MCP 服务器 · 中文

---

## 它让 AI 能做什么

> 「模型都什么价？」
> → AI 调用 `price_table`，21 个模型的价格表

> 「写代码最省钱的方案」
> → AI 调用 `recommend_cheap`，按性价比排序给候选

> 「gpt-4o 和 deepseek-chat 哪个划算？」
> → AI 调用 `compare_models`，给出最便宜 / 最划算 / 质量最高三个结论

> 「我这边 gpt-4o 是 1块/3块」
> → AI 调用 `set_price`，之后所有计算都用你的实付价

> 「10万输入 2万输出，要花多少？」
> → AI 调用 `cost_estimate`，各模型花费对比

---

## 提供的工具

| 工具 | 作用 |
|---|---|
| `price_table` | 价格表（可按价格/质量/性价比排序） |
| `compare_models` | 对比指定模型单价 |
| `recommend_cheap` | 按任务推荐最划算的模型 |
| `set_price` | 设置你实付的价格（覆盖内置参考价） |
| `cost_estimate` | 按 token 量估算花费 |

---

## 安装

```json
{
  "mcpServers": {
    "price-radar-mcp": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/dafeiai918/price-radar-mcp", "price-radar-mcp"]
    }
  }
}
```

零第三方依赖，Python 3.9+。

---

## 两个关键概念

### 综合单价
按 **3:1 的输入输出比例** 估算：`输入价 × 0.75 + 输出价 × 0.25`

为什么不用单一价格？因为输出通常比输入贵好几倍，只看输入价会误判。

### 性价比分
`质量档 ÷ 综合单价`。质量档是内置的 1-5 评分，代表能力水平。

数值越大越划算。这样「便宜但很弱」和「贵但很强」能放在一个尺度上比。

---

## 内置目录（21 个模型）

覆盖 gpt-4o / gpt-4.1 / claude 系列 / deepseek / qwen / glm / gemini / kimi 等，
每个带价格、质量档、标签（通用 / 推理 / 极便宜 / 视觉 / 长文…）。

**这是参考价，中转站实际价格通常不同。** 用 `set_price` 设成你实付的价格，之后所有计算都用你的价。

---

## 使用场景

| 场景 | 对 AI 说 |
|---|---|
| 选型 | 「翻译文档用哪个便宜」 |
| 比价 | 「对比一下这几个模型的价格」 |
| 预算 | 「100万输入50万输出，选哪个不超预算」 |
| 记账 | 「我这边 deepseek 是 0.5 元/2 元，设进去」 |

---

## 相关项目

| 项目 | 用途 |
|---|---|
| [token-meter-mcp](https://github.com/dafeiai918/token-meter-mcp) | 算**已经花了多少**（回顾） |
| [model-arena-mcp](https://github.com/dafeiai918/model-arena-mcp) | 实测**哪个更好用** |
| [relay-mcp](https://github.com/dafeiai918/relay-mcp) | 查**账户还剩多少** |
| [awesome-relay](https://github.com/dafeiai918/awesome-relay) | 中转站与客户端导航 |

**三个 MCP 的分工**：relay-mcp 看余额 → price-radar-mcp 算该用哪个 → token-meter-mcp 看实际花了多少。

---

## License

MIT
