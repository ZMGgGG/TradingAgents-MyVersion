# TradingAgents MyVersion

这是一个基于 TradingAgents 改造的量化研究与多 Agent 交易分析项目。当前版本重点不再只是命令行研究框架，而是围绕 Web Workbench、因子库、Alpha Mining、报告评估、回测和执行过程可观测性，做成一个更适合日常研究和复盘的工作台。

本项目仅用于研究和策略分析，不构成投资建议。

## 当前版本做了什么

- 新增 Web Workbench：提供登录、任务创建、历史任务、执行编排、Agent 输出、报告预览、日志、回测和评估结果查看。
- 新增 Factor Manager：在 Research Manager 之后、Trader 之前运行，读取因子库和 Alpha Mining 经验，生成 `factor_score` 参与交易计划前的决策输入。
- 新增 Alpha Mining：支持候选因子生成、变异、评估、历史沉淀和经验摘要。
- 新增报告评估：支持参考报告、HTML/PDF 文本抽取和报告质量评估。
- 新增回测链路：可对交易决策做持有期验证，并在 Workbench 中展示回测结果。
- 新增运行指标：记录 LLM 调用、Tool 调用、Token、耗时、Agent 阶段和事件，方便定位任务卡住或输出缺失。
- 增强数据链路：补充加密货币工具、中文零售代理数据、社交数据 fallback、非美资产和中文输出支持。
- 优化执行策略：Hold 决策不会再产生默认仓位，仓位逻辑集中到执行策略层处理。
- 优化前端体验：参考 Tabler 风格整理工作台布局、统一字体、简化执行编排视图，并修复 Factor Manager 实时输出展示。
- 优化 Docker 部署：增加 `tradingagents-workbench` 服务，方便直接启动 Web 操作台。

## 执行流程

当前分析任务的大致流程是：

```text
创建任务
  -> Analyst Team 生成市场/情绪/新闻/基本面分析
  -> Bull Researcher / Bear Researcher 辩论
  -> Research Manager 汇总研究结论
  -> Factor Manager 读取因子库并生成 factor_score
  -> Trader 生成交易计划
  -> Risk Team 做风险辩论
  -> Portfolio Manager 给出最终决策
  -> 报告、回测、评估、历史沉淀
```

因子库不是替代 LLM 研究过程，而是在研究经理形成结论后，把历史因子、Alpha Mining 经验和当前上下文转成结构化评分，再交给 Trader 作为交易计划前的额外证据。

## 项目结构

```text
.
├── cli/
│   ├── main.py                 # 交互式 CLI 主入口
│   ├── alpha_flow.py           # Alpha Mining CLI 流程
│   ├── backtest_flow.py        # 回测 CLI 流程
│   ├── report_helpers.py       # 报告辅助逻辑
│   └── report_io.py            # 报告读写逻辑
├── frontend/
│   ├── index.html              # Workbench 页面入口
│   ├── app.js                  # Workbench 前端逻辑
│   ├── styles.css              # Workbench 样式
│   └── server.py               # Workbench 轻量后端服务
├── tradingagents/
│   ├── agents/                 # 分析师、研究员、交易员、风险和管理类 Agent
│   ├── alpha_mining/           # 因子挖掘、候选生成、变异、评估和经验摘要
│   ├── backtesting/            # 回测引擎
│   ├── content_discovery/      # 参考内容发现
│   ├── core/                   # 运行指标、时间上下文等核心工具
│   ├── dataflows/              # 市场、社交、中文代理和加密货币数据链路
│   ├── decisioning/            # 执行策略、因子评分和风险门控
│   ├── evaluation/             # 报告评估和参考文本抽取
│   ├── graph/                  # LangGraph 编排、传播和状态日志
│   └── llm_clients/            # LLM 客户端适配
├── tests/                      # Workbench、因子、回测、报告、数据链路和运行指标测试
├── docker-compose.yml          # CLI / Workbench / Ollama 容器编排
├── Dockerfile
├── pyproject.toml
└── README.md
```

## 本地启动

安装依赖：

```bash
python -m venv .venv
source .venv/bin/activate
pip install .
```

启动 CLI：

```bash
python -m cli.main
```

启动 Web Workbench：

```bash
python -m frontend.server
```

## Docker 启动

准备环境变量：

```bash
cp .env.example .env
```

启动 Web Workbench：

```bash
docker compose up -d tradingagents-workbench
```

启动 CLI 容器：

```bash
docker compose run --rm tradingagents
```

如需 Ollama：

```bash
docker compose --profile ollama up -d ollama
docker compose --profile ollama run --rm tradingagents-ollama
```

## 配置说明

常用配置来自 `.env`、`DEFAULT_CONFIG` 和 Workbench 表单。支持的模型供应商包括 OpenAI、Qwen、GLM、MiniMax、DeepSeek、OpenRouter、Ollama、Azure 等。

敏感信息不要提交到 Git：

- `.env`
- API key
- 登录账号、cookie、token
- `.tradingagents/` 运行缓存和历史
- 本地报告、研报和临时研究材料
- 个人内网地址或代理地址

## Workbench 说明

Workbench 的主要模块包括：

- 新建分析：配置标的、日期、资产类型、模型、研究深度、回测、报告评估和 Alpha Mining。
- 执行编排：查看每个 Agent 的状态和输出。
- 结果：查看最终评级、仓位、置信度、因子评分、回测摘要和风险结论。
- 报告预览：查看结构化报告章节。
- 日志：查看运行过程、LLM/Tool 调用和异常信息。
- 历史任务：查看、同步、复用和重新运行历史分析。

Factor Manager 的输出会在实时执行过程中写入任务快照；如果是旧历史任务，后端会尝试从落盘状态日志回填。

## 测试与验证

常用快速验证：

```bash
node --check frontend/app.js
python -m py_compile frontend/server.py
python -m pytest tests/test_workbench_server_hardening.py tests/test_execution_policy.py tests/test_run_metrics.py -q
```

更完整的相关回归：

```bash
python -m pytest tests/test_alpha_mining.py tests/test_content_discovery.py tests/test_report_evaluation.py -q
```

## Git 维护

提交前建议检查：

```bash
git status --short
git diff --cached --name-only
```

当前项目已在 `.gitignore` 中排除 `.env`、`.tradingagents/`、`reports/`、`.DS_Store` 等本地文件。推送前仍建议扫描 staged diff，避免误提交 API key、内网地址或本地运行数据。
