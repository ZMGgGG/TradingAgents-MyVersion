const { createApp, computed, onMounted, onUnmounted, reactive, ref, watch } = Vue;

createApp({
  setup() {
    function padTimePart(value) {
      return String(value).padStart(2, "0");
    }

    function localDateInputValue(date = new Date()) {
      return [
        date.getFullYear(),
        padTimePart(date.getMonth() + 1),
        padTimePart(date.getDate()),
      ].join("-");
    }

    function localTimestamp(date = new Date()) {
      const offsetMinutes = -date.getTimezoneOffset();
      const sign = offsetMinutes >= 0 ? "+" : "-";
      const absoluteOffset = Math.abs(offsetMinutes);
      return [
        `${localDateInputValue(date)}T${padTimePart(date.getHours())}:${padTimePart(date.getMinutes())}:${padTimePart(date.getSeconds())}`,
        `${sign}${padTimePart(Math.floor(absoluteOffset / 60))}:${padTimePart(absoluteOffset % 60)}`,
      ].join("");
    }

    function parseDateTime(value) {
      if (!value) {
        return null;
      }
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? null : date;
    }

    function formatLocalDateTime(value) {
      const date = parseDateTime(value);
      if (!date) {
        return value ? String(value) : "";
      }
      return `${localDateInputValue(date)} ${padTimePart(date.getHours())}:${padTimePart(date.getMinutes())}:${padTimePart(date.getSeconds())}`;
    }

    function formatLocalTime(value) {
      const date = parseDateTime(value);
      if (!date) {
        return value ? String(value).slice(11, 19) : "--:--:--";
      }
      return `${padTimePart(date.getHours())}:${padTimePart(date.getMinutes())}:${padTimePart(date.getSeconds())}`;
    }

    const analysts = [
      { label: "Market Analyst", value: "market" },
      { label: "Sentiment Analyst", value: "social" },
      { label: "News Analyst", value: "news" },
      { label: "Fundamentals Analyst", value: "fundamentals" },
    ];

    const outputLanguages = [
      "English",
      "Chinese",
      "Japanese",
      "Korean",
      "Hindi",
      "Spanish",
      "Portuguese",
      "French",
      "German",
      "Arabic",
      "Russian",
      "custom",
    ];

    const providerOptions = [
      { label: "OpenAI", value: "openai" },
      { label: "Google", value: "google" },
      { label: "Anthropic", value: "anthropic" },
      { label: "xAI", value: "xai" },
      { label: "DeepSeek", value: "deepseek" },
      { label: "Qwen", value: "qwen" },
      { label: "GLM", value: "glm" },
      { label: "MiniMax", value: "minimax" },
      { label: "OpenRouter", value: "openrouter" },
      { label: "Azure OpenAI", value: "azure" },
      { label: "Ollama", value: "ollama" },
    ];

    const providerRegions = {
      qwen: [
        {
          label: "International",
          provider: "qwen",
          backendUrl: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
          apiKeyEnv: "DASHSCOPE_API_KEY",
        },
        {
          label: "China",
          provider: "qwen-cn",
          backendUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
          apiKeyEnv: "DASHSCOPE_CN_API_KEY",
        },
      ],
      glm: [
        {
          label: "Z.AI International",
          provider: "glm",
          backendUrl: "https://api.z.ai/api/paas/v4/",
          apiKeyEnv: "ZHIPU_API_KEY",
        },
        {
          label: "BigModel China",
          provider: "glm-cn",
          backendUrl: "https://open.bigmodel.cn/api/paas/v4/",
          apiKeyEnv: "ZHIPU_CN_API_KEY",
        },
      ],
      minimax: [
        {
          label: "Global",
          provider: "minimax",
          backendUrl: "https://api.minimax.io/v1",
          apiKeyEnv: "MINIMAX_API_KEY",
        },
        {
          label: "China",
          provider: "minimax-cn",
          backendUrl: "https://api.minimaxi.com/v1",
          apiKeyEnv: "MINIMAX_CN_API_KEY",
        },
      ],
    };

    const modelCatalog = reactive({});

    const providerDefaults = {
      openai: "https://api.openai.com/v1",
      google: "",
      anthropic: "https://api.anthropic.com/",
      xai: "https://api.x.ai/v1",
      deepseek: "https://api.deepseek.com",
      qwen: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
      "qwen-cn": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      glm: "https://api.z.ai/api/paas/v4/",
      "glm-cn": "https://open.bigmodel.cn/api/paas/v4/",
      minimax: "https://api.minimax.io/v1",
      "minimax-cn": "https://api.minimaxi.com/v1",
      openrouter: "https://openrouter.ai/api/v1",
      azure: "",
      ollama: "http://localhost:11434/v1",
    };

    const defaultPresetStocks = [
      "AAPL",
      "NVDA",
      "BTC-USD",
      "0700.HK",
    ];

    const cryptoTickerSet = new Set([
      "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK",
      "MATIC", "LTC", "BCH", "UNI", "ATOM", "ETC", "FIL", "APT", "ARB", "OP",
    ]);

    let userId = "";
    const authState = reactive({
      checked: false,
      authenticated: false,
      username: "",
      userId: "",
      role: "user",
      isAdmin: false,
      mode: "login",
      formUsername: "",
      password: "",
      confirmPassword: "",
      challengeId: "",
      challengePrompt: "",
      challengeAnswer: "",
      challengeTarget: 50,
      challengeTolerance: 4,
      sliderValue: 0,
      sliderMoves: 0,
      sliderStartedAt: 0,
      loading: false,
      error: "",
    });

    const form = reactive({
      ticker: "BTC-USD",
      assetType: "crypto",
      analysisDate: localDateInputValue(),
      analysisLookbackDays: 14,
      outputLanguage: "Chinese",
      customLanguage: "",
      analysts: ["market", "social", "news"],
      researchDepth: 1,
      parallelAnalysts: true,
      llmProviderBase: "qwen",
      llmProvider: "qwen-cn",
      providerRegion: "China",
      quickModel: "qwen3.6-flash",
      deepModel: "qwen3.6-plus",
      analysisModel: "",
      debateModel: "",
      decisionModel: "",
      backendUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
      benchmarkTicker: "",
      enableCheckpoint: true,
      saveReport: true,
      autoDisplayReport: true,
      runReportEvaluation: false,
      reportReferencePath: "",
      reportTopic: "",
      runBacktest: false,
      backtestInitialCapital: "100000",
      backtestHoldingDays: "5,10,20",
      runAlphaMining: false,
      displayFullReport: false,
      googleThinkingLevel: "high",
      openaiReasoningEffort: "medium",
      anthropicEffort: "high",
      llmTimeout: 90,
      llmMaxRetries: 1,
      ensureApiKey: false,
      apiKeyValue: "",
      apiKeyEnvName: "",
    });

    const runState = reactive({
      running: false,
      phase: "待运行",
      progress: 0,
      elapsed: "00:00",
      runId: null,
      status: "idle",
    });

    const backend = reactive({
      connected: false,
      mode: "standalone",
      runConcurrency: 1,
      activeRuns: 0,
      queuedRuns: 0,
      cancellingRuns: 0,
      availableSlots: 1,
    });
    const presetState = reactive({
      name: "",
      items: [],
      selected: "",
    });
    const panelSections = reactive({
      history: true,
      basic: true,
      model: false,
      analysts: false,
      provider: false,
      api: false,
      extras: false,
    });
    const modelRefresh = reactive({
      loading: false,
      source: "catalog",
      error: "",
    });
    const healthState = reactive({
      open: false,
      loading: false,
      saving: false,
      error: "",
      data: null,
      llmTimeoutDraft: 90,
      llmMaxRetriesDraft: 2,
    });
    const adminState = reactive({
      open: false,
      loading: false,
      error: "",
      users: [],
    });

    const simpleMode = ref(true);
    const activeWorkbenchModule = ref("run");
    const activeLogFilter = ref("all");
    const logs = ref([
      "[system] TradingAgents 操作台已就绪",
      "[hint] 当前页面会尽量对齐 CLI 的分析参数与附加流程",
    ]);

    const emptyDecision = {
      rating: "尚未运行",
      confidence: 0,
      position: "N/A",
      summary: "提交分析任务后，这里会显示组合决策、建议仓位和风险摘要。",
      decision_details: {},
    };
    const finalDecision = ref({ ...emptyDecision });

    const attachments = reactive({
      reportSaved: false,
      reportPath: "",
      evaluationEnabled: false,
      evaluationSummary: "",
      backtestEnabled: false,
      backtestSummary: "",
      backtestDetail: [],
      paperTradingEnabled: false,
      paperTradingSummary: "",
      paperTradingDetail: [],
      paperTradingConfig: {},
      alphaMiningEnabled: false,
      alphaMiningSummary: "",
      alphaMiningDetail: null,
      factorRuntimeDetail: null,
      dataDiagnostic: "",
    });
    const reportPreview = ref("");
    const reportSections = reactive({});
    const selectedReportSection = ref("");
    const agentStatus = reactive({});
    const agentOutputs = reactive({});
    const expandedAgents = reactive({});
    const runMetrics = reactive({});
    const taskHistory = ref([]);
    const expandedHistory = reactive({});
    const historySearch = ref("");
    const showAllHistory = ref(false);
    const selectedTaskRunId = ref("");
    const selectedBacktestView = ref("overview");
    const selectedPaperTradingView = ref("overview");
    const paperWorkbenchModuleIds = ["paper", "paper-future", "paper-replay"];
    const isPaperWorkbenchModule = computed(() => paperWorkbenchModuleIds.includes(activeWorkbenchModule.value));
    const isPaperFutureModule = computed(() => activeWorkbenchModule.value === "paper-future");
    const isPaperAccountModule = computed(() => activeWorkbenchModule.value === "paper");
    const isPaperReplayModule = computed(() => activeWorkbenchModule.value === "paper-replay");
    const paperModuleTitle = computed(() => {
      if (isPaperReplayModule.value) return "历史回测";
      if (isPaperAccountModule.value) return "纸面账户";
      return "推演模拟盘";
    });
    const paperModuleDescription = computed(() => (
      isPaperReplayModule.value
        ? "手动选择历史结论或录入历史假设，用结论日期之后的真实价格回放兑现路径。"
        : (isPaperAccountModule.value
          ? "用虚拟资金按真实入场机会执行，维护现金、持仓、成交和权益曲线。"
          : "按选定起点运行模拟盘；有真实后续行情就结算，没有就进入进行中推演。")
    ));
    const paperInterfaceTitle = computed(() => {
      if (isPaperReplayModule.value) return "历史回测输入";
      if (isPaperAccountModule.value) return "纸面账户下单";
      return "运行推演模拟盘";
    });
    const paperInterfaceDescription = computed(() => (
      isPaperReplayModule.value
        ? "选择过去的 execution_plan 或手动输入历史结论，只回放历史结果，不影响实时模拟账户。"
        : (isPaperAccountModule.value
          ? "选择最新 execution_plan 或手动录入假设后写入纸面账户。"
          : "手动选择起点、入场价和仓位运行模拟盘；可选同步为纸面账户执行。")
    ));
    const paperMode = computed(() => {
      if (activeWorkbenchModule.value === "paper-replay") {
        return "replay";
      }
      if (activeWorkbenchModule.value === "paper-future") {
        return "future";
      }
      return "";
    });
    const paperChartOptions = [
      { key: "equity", label: "账户权益", decimals: 2 },
      { key: "cash", label: "现金", decimals: 2 },
      { key: "positionsValue", label: "持仓市值", decimals: 2 },
      { key: "price", label: "标的价格", decimals: 4 },
    ];
    const backtestChartOptions = [
      { key: "equity", label: "回测权益", decimals: 2 },
      { key: "price", label: "回测期真实价格", decimals: 4 },
    ];
    const observationChartOptions = [
      { key: "intradayPrice", label: "当日实时价格", decimals: 4 },
    ];
    const observationReturnChartOptions = [
      { key: "assetReturn", label: "真实标的收益", decimals: 4 },
      { key: "strategyReturn", label: "推演策略收益", decimals: 4 },
      { key: "paperReturn", label: "纸面账户收益", decimals: 4 },
      { key: "backtestReturn", label: "历史回测收益", decimals: 4 },
    ];
    const selectedAlphaView = ref("selected");
    const showAllAlphaHistory = ref(false);
    const showAllAlphaRegistry = ref(false);
    const alphaLibrary = reactive({
      ticker: "",
      loading: false,
      error: "",
      data: null,
    });
    const paper = reactive({
      ticker: "BTC-USD",
      assetType: "crypto",
      quote: null,
      quoteHistory: [],
      account: null,
      analytics: null,
      episodes: null,
      analyticsSkills: [],
      selectedAnalyticsSkills: {},
      signals: [],
      selectedSignalRunId: "",
      selectedReplaySignalRunId: "",
      action: "buy",
      targetPositionSize: "0.10",
      executePaperAccount: false,
      forecastAnalysisDate: localDateInputValue(),
      forecastEntryPrice: "",
      simulationScenario: "base",
      simulationDrift: "",
      simulationVolatility: "",
      simulationSeed: "",
      simulationPaths: "200",
      commissionRate: "0",
      slippageRate: "0",
      initialCash: "100000",
      horizonDays: "20",
      conclusionThesis: "",
      replayAction: "buy",
      replayTargetPositionSize: "0.10",
      replayHorizonDays: "20",
      replayThesis: "",
      replayAccount: null,
      replayAnalytics: null,
      replayResult: null,
      forecastResult: null,
      replayLastUpdated: "",
      replayTicker: "BTC-USD",
      replayTradeDate: "",
      ledgerLastUpdated: "",
      chartFullscreen: false,
      chartHover: null,
      chartRange: "7d",
      chartStartDate: "",
      chartEndDate: "",
      chartSeries: {
        equity: true,
        cash: false,
        positionsValue: false,
        price: true,
      },
      autoRefresh: true,
      loading: false,
      error: "",
      lastUpdated: "",
    });
    const conclusions = reactive({
      items: [],
      summary: {},
      loading: false,
      error: "",
      selectedConclusionId: "",
      reviewNotes: {},
      quote: null,
      intradayRows: [],
      quoteLastUpdated: "",
      quoteLoading: false,
      chartHover: null,
      chartRange: "all",
      chartStartDate: "",
      chartEndDate: "",
      lifecycleLastUpdated: "",
      form: {
        ticker: "",
        assetType: "stock",
        thesis: "",
        rating: "Manual",
        action: "hold",
        targetPositionSize: "0",
        horizonDays: "20",
      },
    });
    const checkpointState = reactive({
      enabled: false,
      available: false,
      hint: "",
    });
    const agentTeams = [
      { team: "Analyst Team", agents: ["Market Analyst", "Sentiment Analyst", "News Analyst", "Fundamentals Analyst"] },
      { team: "Research Team", agents: ["Bull Researcher", "Bear Researcher", "Research Manager", "Factor Manager"] },
      { team: "Trading Team", agents: ["Trader"] },
      { team: "Risk Management", agents: ["Aggressive Analyst", "Neutral Analyst", "Conservative Analyst"] },
      { team: "Portfolio Management", agents: ["Portfolio Manager"] },
    ];
    const agentLabels = {
      "Market Analyst": "市场分析师",
      "Sentiment Analyst": "情绪分析师",
      "News Analyst": "新闻分析师",
      "Fundamentals Analyst": "基本面分析师",
      "Bull Researcher": "多头研究员",
      "Bear Researcher": "空头研究员",
      "Research Manager": "研究经理",
      "Factor Manager": "因子经理",
      Trader: "交易员",
      "Aggressive Analyst": "激进风控分析师",
      "Neutral Analyst": "中性风控分析师",
      "Conservative Analyst": "保守风控分析师",
      "Portfolio Manager": "组合经理",
    };
    const teamLabels = {
      "Analyst Team": "分析师团队",
      "Research Team": "研究辩论团队",
      "Trading Team": "交易团队",
      "Risk Management": "风险管理团队",
      "Portfolio Management": "组合管理",
    };
    const statusLabels = {
      idle: "未开始",
      pending: "等待中",
      in_progress: "运行中",
      completed: "已完成",
      failed: "失败",
      error: "错误",
      cancelling: "取消中",
      cancelled: "已取消",
      stale: "已失效",
    };

    const regionOptions = computed(() => {
      return providerRegions[form.llmProviderBase] || [];
    });

    const effectiveProvider = computed(() => {
      return form.llmProvider || form.llmProviderBase;
    });

    const selectedProviderQuickModels = computed(() => {
      const providerModes = modelCatalog[effectiveProvider.value] || {};
      return (providerModes.quick || []).map((item) => item.value);
    });

    const selectedProviderDeepModels = computed(() => {
      const providerModes = modelCatalog[effectiveProvider.value] || {};
      return (providerModes.deep || []).map((item) => item.value);
    });

    const selectedProviderRoleModels = computed(() => {
      return Array.from(new Set([
        ...selectedProviderQuickModels.value,
        ...selectedProviderDeepModels.value,
      ]));
    });

    const effectiveOutputLanguage = computed(() => {
      if (form.outputLanguage === "custom") {
        return form.customLanguage.trim() || "Custom";
      }
      return form.outputLanguage;
    });

    const activeApiKeyEnv = computed(() => {
      const selectedRegion = regionOptions.value.find((item) => item.provider === form.llmProvider);
      if (selectedRegion?.apiKeyEnv) {
        return selectedRegion.apiKeyEnv;
      }

      const providerEnvMap = {
        openai: "OPENAI_API_KEY",
        google: "GOOGLE_API_KEY",
        anthropic: "ANTHROPIC_API_KEY",
        xai: "XAI_API_KEY",
        deepseek: "DEEPSEEK_API_KEY",
        openrouter: "OPENROUTER_API_KEY",
        azure: "AZURE_OPENAI_API_KEY",
      };
      return providerEnvMap[effectiveProvider.value] || "";
    });

    const currentRunningAgent = computed(() => {
      const statuses = selectedTaskView.value.agent_status || {};
      const entry = Object.entries(statuses).find(([, status]) => status === "in_progress");
      return entry ? entry[0] : "";
    });

    const nextPendingAgent = computed(() => {
      const flattened = agentTeams.flatMap((group) => group.agents);
      const statuses = selectedTaskView.value.agent_status || {};
      const entry = flattened.find((agent) => (statuses[agent] || "pending") === "pending");
      return entry || "";
    });

    const selectedTask = computed(() => {
      return taskHistory.value.find((item) => item.run_id === selectedTaskRunId.value) || null;
    });

    function parseDecisionText(text = "") {
      const source = String(text || "").trim();
      if (!source) {
        return {};
      }
      const labels = [
        ["rating", "Rating"],
        ["executive_summary", "Executive Summary"],
        ["investment_thesis", "Investment Thesis"],
        ["price_target", "Price Target"],
        ["time_horizon", "Time Horizon"],
        ["target_position_size", "Target Position Size"],
        ["risk_gate_status", "Risk Gate Status"],
      ];
      const details = {};
      labels.forEach(([key, label], index) => {
        const nextLabels = labels.slice(index + 1).map(([, item]) => item.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
        const nextPattern = nextLabels.length ? `(?=\\n\\s*\\*\\*(?:${nextLabels.join("|")})\\*\\*\\s*:|\\n\\s*(?:${nextLabels.join("|")})\\s*:)` : "$";
        const labelPattern = label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        const match = source.match(new RegExp(`(?:^|\\n)\\s*(?:\\*\\*)?${labelPattern}(?:\\*\\*)?\\s*:\\s*([\\s\\S]*?)${nextPattern}`, "i"));
        if (match && match[1]) {
          details[key] = match[1].trim();
        }
      });
      if (!details.raw_decision) {
        details.raw_decision = source;
      }
      return details;
    }

    function formatDecisionValue(value, type = "") {
      if (value === null || value === undefined || value === "") {
        return "";
      }
      if (type === "position" && typeof value === "number") {
        return `${Math.round((value > 1 ? value : value * 100) * 100) / 100}%`;
      }
      return String(value);
    }

    function localizeDecisionValue(value) {
      const text = String(value || "").trim();
      const normalized = text.toLowerCase().replace(/[_-]+/g, " ");
      const labels = {
        "strong buy": "强烈买入",
        buy: "买入",
        "moderate buy": "适度买入",
        "weak buy": "谨慎买入",
        hold: "持有",
        neutral: "中性",
        "moderate sell": "适度卖出",
        sell: "卖出",
        "strong sell": "强烈卖出",
        bullish: "看多",
        bearish: "看空",
        approved: "通过",
        rejected: "未通过",
        blocked: "已拦截",
        pass: "通过",
        fail: "未通过",
        failed: "失败",
        cancelled: "已取消",
        stale: "已失效",
        unknown: "未知",
        "n/a": "无",
      };
      return labels[normalized] || text || "无";
    }

    function decisionModeLabel(depth) {
      if (Number(depth) === 3) return "深入分析";
      if (Number(depth) === 2) return "均衡分析";
      return "快速分析";
    }

    function reportSectionLabel(section) {
      const labels = {
        "Market Analysis": "市场分析",
        "Sentiment Analysis": "情绪分析",
        "News Analysis": "新闻分析",
        "Fundamentals Analysis": "基本面分析",
        "Trading Plan": "交易计划",
        "Research Decision": "研究结论",
        "Portfolio Decision": "组合决策",
      };
      return labels[section] || section;
    }

    const hasDecisionResult = computed(() => {
      const status = selectedTaskView.value.status || "idle";
      if (["idle", "queued", "running", "cancelling"].includes(status)) {
        return false;
      }
      return Boolean(selectedTaskView.value.result);
    });

    const decisionResult = computed(() => {
      return hasDecisionResult.value ? (selectedTaskView.value.result || emptyDecision) : emptyDecision;
    });

    const currentDecisionDetails = computed(() => {
      const result = decisionResult.value;
      const explicit = result.decision_details || result.details || {};
      const reportDecision = (selectedTaskView.value.report_sections || {})["Portfolio Decision"] || "";
      const parsed = parseDecisionText(reportDecision || result.summary || "");
      return {
        ...parsed,
        ...explicit,
      };
    });

    const selectedTaskView = computed(() => {
      if (selectedTask.value) {
        const item = selectedTask.value;
        return {
          run_id: item.run_id,
          ticker: item.ticker,
          status: item.status,
          phase: item.phase,
          progress: item.progress ?? 0,
          elapsed: item.elapsed || "00:00",
          result: item.result || {
            rating: item.rating || "Unknown",
            confidence: 0,
            position: "N/A",
            summary: item.result_summary || "当前历史任务没有更多结果摘要。",
          },
          attachments: item.attachments || {
            report_saved: !!item.report_path,
            report_path: item.report_path || "",
            evaluation_enabled: false,
            evaluation_summary: "",
            backtest_enabled: false,
            backtest_summary: "",
            backtest_detail: [],
            alpha_mining_enabled: false,
            alpha_mining_summary: "",
            alpha_mining_detail: null,
            factor_runtime_detail: null,
          },
          report_preview: item.report_preview || "",
          report_file: item.report_file || "",
          report_sections: item.report_sections || {},
          agent_status: item.agent_status || {},
          agent_outputs: item.agent_outputs || {},
          events: item.events || [],
          logs: item.logs || [],
          checkpoint_enabled: !!item.checkpoint_enabled,
          checkpoint_available: !!item.checkpoint_available,
          resume_hint: item.resume_hint || "",
        metrics: item.metrics || {},
        payload: item.payload || null,
        cancel_requested: !!item.cancel_requested,
        analyst_execution_mode: item.analyst_execution_mode || "serial",
      };
      }
      return {
        run_id: runState.runId,
        ticker: form.ticker,
        status: runState.status,
        phase: runState.phase,
        progress: runState.progress,
        elapsed: runState.elapsed,
        result: finalDecision.value,
        attachments: {
          report_saved: attachments.reportSaved,
          report_path: attachments.reportPath,
          evaluation_enabled: attachments.evaluationEnabled,
          evaluation_summary: attachments.evaluationSummary,
          backtest_enabled: attachments.backtestEnabled,
          backtest_summary: attachments.backtestSummary,
          backtest_detail: attachments.backtestDetail,
          paper_trading_enabled: attachments.paperTradingEnabled,
          paper_trading_summary: attachments.paperTradingSummary,
          paper_trading_detail: attachments.paperTradingDetail,
          paper_trading_config: attachments.paperTradingConfig,
          alpha_mining_enabled: attachments.alphaMiningEnabled,
          alpha_mining_summary: attachments.alphaMiningSummary,
          alpha_mining_detail: attachments.alphaMiningDetail,
          factor_runtime_detail: attachments.factorRuntimeDetail,
          data_diagnostic: attachments.dataDiagnostic,
        },
        report_preview: reportPreview.value,
        report_file: "",
        report_sections: { ...reportSections },
        agent_status: { ...agentStatus },
        agent_outputs: { ...agentOutputs },
        events: [],
        logs: [...logs.value],
        checkpoint_enabled: checkpointState.enabled,
        checkpoint_available: checkpointState.available,
        resume_hint: checkpointState.hint,
        metrics: { ...runMetrics },
        payload: {
          ticker: form.ticker,
          analysis_date: form.analysisDate,
          research_depth: form.researchDepth,
          output_language: effectiveOutputLanguage.value,
          llm_provider: effectiveProvider.value,
        },
        cancel_requested: false,
        analyst_execution_mode: form.parallelAnalysts ? "parallel" : "serial",
      };
    });

    const selectedBacktestDetail = computed(() => {
      const detail = (selectedTaskView.value.attachments || {}).backtest_detail;
      return Array.isArray(detail) ? detail : [];
    });

    const selectedPaperSnapshots = computed(() => {
      const snapshots = paper.account?.snapshots;
      return Array.isArray(snapshots) ? snapshots : [];
    });
    const selectedReplaySnapshots = computed(() => {
      const snapshots = paper.replayAccount?.snapshots;
      return Array.isArray(snapshots) ? snapshots : [];
    });
    const currentPaperSignals = computed(() => paper.signals.filter((signal) => !isHistoricalPaperSignal(signal)));
    const historicalPaperSignals = computed(() => paper.signals.filter((signal) => isHistoricalPaperSignal(signal)));

    const paperPositions = computed(() => Object.values(paper.account?.positions || {}));
    const paperFills = computed(() => Array.isArray(paper.account?.fills) ? paper.account.fills.slice().reverse() : []);
    const paperConclusionTracks = computed(() => {
      if (Array.isArray(paper.analytics?.tracks) && paper.analytics.tracks.length) {
        return paper.analytics.tracks;
      }
      const positions = paper.account?.positions || {};
      const seen = new Set();
      return paperFills.value
        .filter((fill) => {
          const key = `${fill.source_run_id || ""}:${fill.ticker || ""}:${fill.trade_date || ""}:${fill.side || ""}`;
          if (seen.has(key) || fill.side === "sell") {
            return false;
          }
          seen.add(key);
          return true;
        })
        .map((fill) => {
          const position = positions[fill.ticker] || {};
          const entryPrice = Number(fill.price) || 0;
          const lastPrice = Number(position.last_price) || Number(paper.quote?.price) || entryPrice;
          const openedAt = new Date(fill.trade_date);
          const ageDays = Number.isNaN(openedAt.getTime())
            ? 0
            : Math.max(0, Math.floor((Date.now() - openedAt.getTime()) / 86400000));
          const horizonDays = Number(fill.horizon_days) || 20;
          return {
            ...fill,
            age_days: ageDays,
            horizon_days: horizonDays,
            progress: Math.min(1, ageDays / horizonDays),
            current_return: entryPrice ? (lastPrice / entryPrice) - 1 : 0,
            status: ageDays >= horizonDays ? "待复盘" : "跟踪中",
          };
        })
        .slice(0, 20);
    });

    function buildSeriesChart(dataSources, options, { axisPreference = "price", xLabelFormatter = null } = {}) {
      const width = 700;
      const height = 280;
      const padLeft = 118;
      const padRight = 50;
      const padTop = 26;
      const padBottom = 42;
      const series = options
        .map((option) => {
          const source = dataSources[option.key] || { values: [], dates: [] };
          const sourceValues = source.values || [];
          const rawValues = sourceValues.map((value, index) => ({
            index,
            value,
          })).filter((item) => Number.isFinite(item.value));
          if (!rawValues.length) {
            return null;
          }
          const values = rawValues.map((item) => item.value);
          const min = Math.min(...values);
          const max = Math.max(...values);
          const spread = max - min || Math.max(1, Math.abs(max) * 0.01);
          const pointItems = rawValues.map((item) => {
            const x = sourceValues.length === 1 ? width / 2 : padLeft + (item.index * (width - padLeft - padRight)) / (sourceValues.length - 1);
            const y = height - padBottom - ((item.value - min) / spread) * (height - padTop - padBottom);
            return {
              x,
              y,
              value: item.value,
              date: source.dates?.[item.index] || "",
              index: item.index,
            };
          });
          return {
            ...option,
            points: pointItems.map((item) => `${item.x.toFixed(2)},${item.y.toFixed(2)}`).join(" "),
            pointItems,
            min,
            max,
            latest: values[values.length - 1],
            dates: source.dates || [],
          };
        })
        .filter(Boolean);
      const axisSeries = series.find((item) => item.key === axisPreference) || series[0] || null;
      const dates = axisSeries?.dates || [];
      const cleanDate = (value) => (typeof xLabelFormatter === "function" ? xLabelFormatter(value) : String(value || "").slice(0, 10));
      const xLabels = dates.length ? [
        { x: padLeft, label: cleanDate(dates[0]), anchor: "start" },
        { x: width / 2, label: cleanDate(dates[Math.floor((dates.length - 1) / 2)]), anchor: "middle" },
        { x: width - padRight, label: cleanDate(dates[dates.length - 1]), anchor: "end" },
      ] : [];
      const yTicks = axisSeries ? [
        { y: padTop, value: axisSeries.max, label: formatNumber(axisSeries.max, axisSeries.decimals) },
        { y: height - padBottom - ((axisSeries.max + axisSeries.min) / 2 - axisSeries.min) / ((axisSeries.max - axisSeries.min) || Math.max(1, Math.abs(axisSeries.max) * 0.01)) * (height - padTop - padBottom), value: (axisSeries.max + axisSeries.min) / 2, label: formatNumber((axisSeries.max + axisSeries.min) / 2, axisSeries.decimals) },
        { y: height - padBottom, value: axisSeries.min, label: formatNumber(axisSeries.min, axisSeries.decimals) },
      ] : [];
      return {
        series,
        axis: {
          x1: padLeft,
          x2: width - padRight,
          y1: padTop,
          y2: height - padBottom,
          label: axisSeries?.label || "",
          decimals: axisSeries?.decimals || 2,
          xLabels,
          yTicks,
        },
      };
    }

    function buildQuantileBandChart(rows) {
      const width = 700;
      const height = 280;
      const padLeft = 118;
      const padRight = 50;
      const padTop = 26;
      const padBottom = 42;
      const cleanRows = (Array.isArray(rows) ? rows : [])
        .map((item, index) => ({
          index,
          date: item.date,
          p10: Number(item.p10),
          p50: Number(item.p50),
          p90: Number(item.p90),
        }))
        .filter((item) => Number.isFinite(item.p10) && Number.isFinite(item.p50) && Number.isFinite(item.p90));
      if (!cleanRows.length) {
        return {
          series: [],
          axis: {
            x1: padLeft,
            x2: width - padRight,
            y1: padTop,
            y2: height - padBottom,
            label: "推演价格",
            decimals: 4,
            xLabels: [],
            yTicks: [],
          },
          bandPoints: "",
          lowerPoints: "",
          upperPoints: "",
        };
      }
      const values = cleanRows.flatMap((item) => [item.p10, item.p50, item.p90]);
      const min = Math.min(...values);
      const max = Math.max(...values);
      const spread = max - min || Math.max(1, Math.abs(max) * 0.01);
      const xForIndex = (index) => cleanRows.length === 1
        ? width / 2
        : padLeft + (index * (width - padLeft - padRight)) / (cleanRows.length - 1);
      const yForValue = (value) => height - padBottom - ((value - min) / spread) * (height - padTop - padBottom);
      const pointItems = cleanRows.map((item, index) => ({
        x: xForIndex(index),
        y: yForValue(item.p50),
        value: item.p50,
        date: item.date,
        index,
      }));
      const lower = cleanRows.map((item, index) => ({ x: xForIndex(index), y: yForValue(item.p10) }));
      const upper = cleanRows.map((item, index) => ({ x: xForIndex(index), y: yForValue(item.p90) }));
      const toPoints = (items) => items.map((item) => `${item.x.toFixed(2)},${item.y.toFixed(2)}`).join(" ");
      const xLabels = [
        { x: padLeft, label: String(cleanRows[0].date || "").slice(0, 10), anchor: "start" },
        { x: width / 2, label: String(cleanRows[Math.floor((cleanRows.length - 1) / 2)].date || "").slice(0, 10), anchor: "middle" },
        { x: width - padRight, label: String(cleanRows[cleanRows.length - 1].date || "").slice(0, 10), anchor: "end" },
      ];
      const yTicks = [
        { y: padTop, value: max, label: formatNumber(max, 4) },
        { y: height - padBottom - (((max + min) / 2 - min) / spread) * (height - padTop - padBottom), value: (max + min) / 2, label: formatNumber((max + min) / 2, 4) },
        { y: height - padBottom, value: min, label: formatNumber(min, 4) },
      ];
      return {
        series: [{
          key: "simulationMedian",
          label: "中位 P50",
          decimals: 4,
          points: toPoints(pointItems),
          pointItems,
          latest: cleanRows[cleanRows.length - 1].p50,
          min,
          max,
        }],
        axis: {
          x1: padLeft,
          x2: width - padRight,
          y1: padTop,
          y2: height - padBottom,
          label: "推演价格",
          decimals: 4,
          xLabels,
          yTicks,
        },
        bandPoints: `${toPoints(upper)} ${toPoints(lower.slice().reverse())}`,
        lowerPoints: toPoints(lower),
        upperPoints: toPoints(upper),
      };
    }

    const paperChart = computed(() => {
      const snapshots = filterRowsByDateRange(
        selectedPaperSnapshots.value.filter((item) => item && typeof item === "object"),
        paper.chartRange,
        paper.chartStartDate,
        paper.chartEndDate,
        "trade_date",
      );
      const ticker = String(paper.ticker || "").toUpperCase();
      const marketTicker = String(paper.quote?.market_ticker || ticker).toUpperCase();
      const savedHistory = (paper.account?.market_history || {})[marketTicker] || [];
      const quoteHistoryRows = Array.isArray(paper.quote?.history) ? paper.quote.history : [];
      const quoteHistory = Array.isArray(paper.quoteHistory)
        ? paper.quoteHistory.filter((item) => item && item.ticker === ticker)
        : [];
      const intradayPriceRows = Array.isArray(paper.quote?.intraday)
        ? paper.quote.intraday
          .map((item) => ({
            value: Number(item.price ?? item.close ?? item.Close),
            date: item.time || item.as_of || item.timestamp || item.datetime,
          }))
          .filter((item) => Number.isFinite(item.value) && dateOnly(item.date) === localDateInputValue())
        : [];
      const priceRows = paper.chartRange === "today" && intradayPriceRows.length
        ? intradayPriceRows
        : (Array.isArray(savedHistory) && savedHistory.length
          ? savedHistory.map((item) => ({ value: Number(item.close), date: item.date }))
          : (quoteHistoryRows.length
            ? quoteHistoryRows.map((item) => ({ value: Number(item.close), date: item.date }))
            : quoteHistory.map((item) => ({ value: Number(item.price), date: item.as_of }))));
      const latestQuotePrice = Number(paper.quote?.price);
      if (Number.isFinite(latestQuotePrice)) {
        const latestQuoteDate = normalizeLiveQuoteTime(paper.quote?.as_of);
        const lastPriceRow = priceRows[priceRows.length - 1];
        if (!lastPriceRow || lastPriceRow.date !== latestQuoteDate || Number(lastPriceRow.value) !== latestQuotePrice) {
          priceRows.push({ value: latestQuotePrice, date: latestQuoteDate });
        }
      }
      const snapshotDates = snapshots.map((item) => item.trade_date);
      const filteredPriceRows = filterRowsByDateRange(
        priceRows,
        paper.chartRange,
        paper.chartStartDate,
        paper.chartEndDate,
        "date",
      );
      const dataSources = {
        equity: { values: snapshots.map((item) => Number(item.equity)), dates: snapshotDates },
        cash: { values: snapshots.map((item) => Number(item.cash)), dates: snapshotDates },
        positionsValue: { values: snapshots.map((item) => Number(item.positions_value)), dates: snapshotDates },
        price: { values: filteredPriceRows.map((item) => item.value), dates: filteredPriceRows.map((item) => item.date) },
      };
      return {
        ...buildSeriesChart(
          dataSources,
          paperChartOptions.filter((option) => paper.chartSeries[option.key]),
          {
            axisPreference: "price",
            xLabelFormatter: paper.chartRange === "today" ? formatChartTimeLabel : null,
          },
        ),
        latest: snapshots[snapshots.length - 1],
      };
    });

    const backtestChart = computed(() => {
      const snapshots = selectedReplaySnapshots.value.filter((item) => item && typeof item === "object");
      const ticker = String(paper.replayTicker || paper.ticker || "").toUpperCase();
      const priceRows = snapshots
        .map((snapshot) => {
          const positions = snapshot.positions || {};
          const position = positions[ticker] || Object.values(positions)[0] || {};
          return {
            value: Number(position.last_price),
            date: snapshot.trade_date,
          };
        })
        .filter((item) => Number.isFinite(item.value));
      return buildSeriesChart(
        {
          equity: { values: snapshots.map((item) => Number(item.equity)), dates: snapshots.map((item) => item.trade_date) },
          price: { values: priceRows.map((item) => item.value), dates: priceRows.map((item) => item.date) },
        },
        backtestChartOptions,
        { axisPreference: "price" },
      );
    });

    const selectedConclusionTrack = computed(() => {
      return conclusions.items.find((item) => item.conclusion_id === conclusions.selectedConclusionId) || conclusions.items[0] || null;
    });

    const observationTicker = computed(() => {
      return String(selectedConclusionTrack.value?.ticker || conclusions.form.ticker || form.ticker || "").trim().toUpperCase();
    });

    function formatChartTimeLabel(value) {
      const date = parseDateTime(value);
      if (!date) {
        const text = String(value || "");
        return text.includes("T") ? text.slice(11, 19) : text;
      }
      return `${padTimePart(date.getHours())}:${padTimePart(date.getMinutes())}:${padTimePart(date.getSeconds())}`;
    }

    function formatChartHoverLabel(value) {
      const raw = String(value || "");
      const date = parseDateTime(value);
      if (!date) {
        return raw || "N/A";
      }
      if (raw.includes("T") || raw.includes(":")) {
        return formatLocalDateTime(value);
      }
      return localDateInputValue(date);
    }

    function normalizeLiveQuoteTime(value) {
      const raw = String(value || "");
      return raw.includes("T") || raw.includes(":") ? raw : localTimestamp();
    }

    function dateOnly(value) {
      const text = String(value || "");
      if (/^\d{4}-\d{2}-\d{2}/.test(text)) {
        return text.slice(0, 10);
      }
      const date = parseDateTime(value);
      return date ? localDateInputValue(date) : "";
    }

    function rangeBounds(range, startDate = "", endDate = "") {
      const today = localDateInputValue();
      if (range === "today") {
        return { start: today, end: today };
      }
      if (range === "7d" || range === "30d") {
        const days = range === "7d" ? 6 : 29;
        const start = new Date();
        start.setDate(start.getDate() - days);
        return { start: localDateInputValue(start), end: today };
      }
      if (range === "custom") {
        return { start: startDate || "", end: endDate || "" };
      }
      return { start: "", end: "" };
    }

    function filterRowsByDateRange(rows, range, startDate = "", endDate = "", dateKey = "date") {
      const sourceRows = Array.isArray(rows) ? rows : [];
      if (range === "today") {
        const datedRows = sourceRows
          .map((row) => ({ row, rowDate: dateOnly(row?.[dateKey]) }))
          .filter((item) => item.rowDate);
        const today = localDateInputValue();
        const todayRows = datedRows.filter((item) => item.rowDate === today).map((item) => item.row);
        if (todayRows.length) {
          return todayRows;
        }
        const latestDate = datedRows.map((item) => item.rowDate).sort().pop();
        return latestDate
          ? datedRows.filter((item) => item.rowDate === latestDate).map((item) => item.row)
          : [];
      }
      const bounds = rangeBounds(range, startDate, endDate);
      if (!bounds.start && !bounds.end) {
        return rows;
      }
      return sourceRows.filter((row) => {
        const rowDate = dateOnly(row?.[dateKey]);
        if (!rowDate) {
          return false;
        }
        if (bounds.start && rowDate < bounds.start) {
          return false;
        }
        if (bounds.end && rowDate > bounds.end) {
          return false;
        }
        return true;
      });
    }

    function weightedStrategyReturn(action, targetPositionSize, assetReturn) {
      const normalizedAction = String(action || "").trim().toLowerCase();
      const direction = ["buy", "overweight", "long", "strong_buy", "accumulate"].includes(normalizedAction)
        ? 1
        : (["sell", "underweight", "short", "strong_sell", "reduce"].includes(normalizedAction) ? -1 : 0);
      const size = Math.max(0, Math.min(1, Number(targetPositionSize) || 0));
      return direction * size * (Number(assetReturn) || 0);
    }

    const observationIntradayChart = computed(() => {
      const rows = Array.isArray(conclusions.intradayRows) ? conclusions.intradayRows : [];
      return buildSeriesChart(
        {
          intradayPrice: { values: rows.map((item) => Number(item.price)), dates: rows.map((item) => item.time || item.as_of) },
        },
        observationChartOptions,
        { axisPreference: "intradayPrice", xLabelFormatter: formatChartTimeLabel },
      );
    });

    const observationReturnChart = computed(() => {
      const track = selectedConclusionTrack.value || {};
      const simulations = Array.isArray(track.simulations) ? track.simulations : [];
      const forecast = simulations.find((item) => item.simulation_type === "forecast") || track.comparison || {};
      const paperTrade = simulations.find((item) => item.simulation_type === "paper_trade") || {};
      const backtest = simulations.find((item) => item.simulation_type === "backtest") || {};
      const rawForecastRows = Array.isArray(forecast.series) ? forecast.series.slice() : [];
      const liveQuotePrice = Number(conclusions.quote?.price);
      const entryPrice = Number(track.entry_price || forecast.entry_price);
      const liveAction = track.action || forecast.action;
      const liveTargetSize = track.target_position_size ?? forecast.target_position_size;
      if (Number.isFinite(liveQuotePrice) && Number.isFinite(entryPrice) && entryPrice > 0) {
        const today = localDateInputValue();
        const intradayReturnRows = conclusions.chartRange === "today"
          ? (Array.isArray(conclusions.intradayRows) ? conclusions.intradayRows : [])
            .map((row) => {
              const price = Number(row?.price);
              const timestamp = row?.time || row?.as_of || conclusions.quote?.as_of || localTimestamp();
              if (!Number.isFinite(price) || dateOnly(timestamp) !== today) {
                return null;
              }
              const assetReturn = (price / entryPrice) - 1;
              return {
                date: timestamp,
                price,
                asset_return: assetReturn,
                strategy_return: weightedStrategyReturn(liveAction, liveTargetSize, assetReturn),
                price_source: "live_intraday",
                covered_by_real: true,
              };
            })
            .filter(Boolean)
          : [];
        const liveRows = conclusions.chartRange === "today" && intradayReturnRows.length
          ? intradayReturnRows
          : (() => {
            const timestamp = dateOnly(conclusions.quote?.as_of) || today;
            const assetReturn = (liveQuotePrice / entryPrice) - 1;
            return [{
              date: timestamp,
              price: liveQuotePrice,
              asset_return: assetReturn,
              strategy_return: weightedStrategyReturn(liveAction, liveTargetSize, assetReturn),
              price_source: "live_quote",
              covered_by_real: true,
            }];
          })();
        const liveDates = new Set(liveRows.map((row) => dateOnly(row.date)).filter(Boolean));
        for (let index = rawForecastRows.length - 1; index >= 0; index -= 1) {
          if (liveDates.has(dateOnly(rawForecastRows[index]?.date))) {
            rawForecastRows.splice(index, 1);
          }
        }
        rawForecastRows.push(...liveRows);
        rawForecastRows.sort((left, right) => String(left.date || "").localeCompare(String(right.date || "")));
      }
      const forecastRows = filterRowsByDateRange(
        rawForecastRows,
        conclusions.chartRange,
        conclusions.chartStartDate,
        conclusions.chartEndDate,
        "date",
      );
      const fallbackDate = track.analysis_date || String(track.opened_at || "").slice(0, 10) || localDateInputValue();
      const fallbackCurrentDate = localDateInputValue();
      const terminalRows = (item) => {
        const finalReturn = Number(item.final_return ?? item.strategy_return ?? item.asset_return);
        if (!Number.isFinite(finalReturn)) {
          return [];
        }
        return [
          { date: fallbackDate, value: 0 },
          { date: fallbackCurrentDate, value: finalReturn },
        ];
      };
      const paperRows = filterRowsByDateRange(
        terminalRows(paperTrade),
        conclusions.chartRange,
        conclusions.chartStartDate,
        conclusions.chartEndDate,
        "date",
      );
      const backtestRows = filterRowsByDateRange(
        terminalRows(backtest),
        conclusions.chartRange,
        conclusions.chartStartDate,
        conclusions.chartEndDate,
        "date",
      );
      return buildSeriesChart(
        {
          assetReturn: { values: forecastRows.map((item) => Number(item.asset_return)), dates: forecastRows.map((item) => item.date) },
          strategyReturn: { values: forecastRows.map((item) => Number(item.strategy_return)), dates: forecastRows.map((item) => item.date) },
          paperReturn: { values: paperRows.map((item) => item.value), dates: paperRows.map((item) => item.date) },
          backtestReturn: { values: backtestRows.map((item) => item.value), dates: backtestRows.map((item) => item.date) },
        },
        observationReturnChartOptions,
        {
          axisPreference: forecastRows.length ? "assetReturn" : "strategyReturn",
          xLabelFormatter: conclusions.chartRange === "today" ? formatChartTimeLabel : null,
        },
      );
    });

    function currentSimulationSummary() {
      const episode = paper.forecastResult?.episode || {};
      const meta = episode.tags?.simulation_config || episode.simulation || {};
      return episode.tags?.simulation_summary || meta?.scenario_summary || {};
    }

    const forecastSimulationChart = computed(() => buildQuantileBandChart(currentSimulationSummary().series || []));

    const activePaperChart = computed(() => {
      if (isPaperReplayModule.value) return backtestChart.value;
      if (isPaperFutureModule.value) return forecastSimulationChart.value;
      return paperChart.value;
    });
    const paperChartTitle = computed(() => {
      if (isPaperReplayModule.value) return "历史回测曲线";
      if (isPaperAccountModule.value) return "纸面账户权益 / 价格曲线";
      return "推演模拟盘参考价格曲线";
    });

    const paperEpisodes = computed(() => {
      const items = paper.episodes?.items;
      return Array.isArray(items) ? items : [];
    });

    function episodeMatchesActiveModule(episode) {
      const type = String(episode?.simulation_type || "").toLowerCase();
      const mode = String(episode?.mode || "").toLowerCase();
      if (isPaperReplayModule.value) {
        return type === "backtest" || ["backtest", "historical_replay"].includes(mode);
      }
      if (isPaperFutureModule.value) {
        return type === "forecast" || ["forecast", "forward_test", "forecast_observation"].includes(mode);
      }
      if (isPaperAccountModule.value) {
        return type === "paper_trade" || ["live", "paper_trade", "paper_account"].includes(mode);
      }
      return true;
    }

    const scopedPaperEpisodes = computed(() => paperEpisodes.value.filter(episodeMatchesActiveModule));

    function summarizeEpisodeRows(rows) {
      const observed = rows.filter((episode) => Number.isFinite(Number(episode.final_return)));
      const returns = observed.map((episode) => Number(episode.final_return) || 0);
      const wins = returns.filter((value) => value > 0).length;
      const compounded = returns.reduce((value, item) => value * (1 + item), 1) - 1;
      const confidenceValues = observed.map((episode) => Number(episode.confidence)).filter(Number.isFinite);
      const targetSizes = rows.map((episode) => Number(episode.target_position_size)).filter(Number.isFinite);
      return {
        count: rows.length,
        total_episodes: rows.length,
        observed_count: observed.length,
        total_return: returns.length ? compounded : 0,
        average_return: returns.length ? returns.reduce((sum, item) => sum + item, 0) / returns.length : 0,
        win_rate: returns.length ? wins / returns.length : 0,
        average_confidence: confidenceValues.length ? confidenceValues.reduce((sum, item) => sum + item, 0) / confidenceValues.length : 0,
        average_target_position_size: targetSizes.length ? targetSizes.reduce((sum, item) => sum + item, 0) / targetSizes.length : 0,
      };
    }

    function facetRowsForEpisodes(rows, field) {
      const grouped = {};
      rows.forEach((episode) => {
        const key = String(episode?.[field] || "unknown");
        grouped[key] = grouped[key] || [];
        grouped[key].push(episode);
      });
      return Object.entries(grouped).map(([name, items]) => ({
        name,
        ...summarizeEpisodeRows(items),
      }));
    }

    const paperEpisodeSummary = computed(() => summarizeEpisodeRows(scopedPaperEpisodes.value));

    const paperLedgerTitle = computed(() => {
      if (isPaperReplayModule.value) return "历史回测账本";
      if (isPaperFutureModule.value) return "推演模拟盘账本";
      if (isPaperAccountModule.value) return "纸面账户账本";
      return "模拟盘总账本";
    });

    const paperLedgerFacetRows = computed(() => {
      const facetLabels = {
        simulation_type: "类型",
        mode: "模式",
        rating: "评级",
        action: "动作",
        asset_type: "资产",
      };
      return ["simulation_type", "mode", "rating", "action", "asset_type"].flatMap((facetKey) => {
        return facetRowsForEpisodes(scopedPaperEpisodes.value, facetKey)
          .map((stats) => ({
            facet: facetLabels[facetKey] || facetKey,
            name: facetKey === "simulation_type" || facetKey === "mode"
              ? simulationTypeLabel(stats.name)
              : (facetKey === "action" ? localizeDecisionValue(stats.name) : stats.name),
            count: Number(stats?.count) || 0,
            observed_count: Number(stats?.observed_count) || 0,
            average_return: Number(stats?.average_return) || 0,
            win_rate: Number(stats?.win_rate) || 0,
            average_confidence: Number(stats?.average_confidence) || 0,
          }))
          .filter((row) => row.count > 0)
          .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
      });
    });

    const activeSimulationMeta = computed(() => {
      const episode = paper.forecastResult?.episode || {};
      return episode.tags?.simulation_config || episode.simulation || {};
    });

    const activeSimulationSourceCounts = computed(() => {
      const meta = activeSimulationMeta.value || {};
      const counts = meta.price_source_counts || {};
      return {
        real: Number(counts.real ?? meta.real_price_points ?? (paper.forecastResult?.episode?.tags || {}).real_price_points) || 0,
        simulated: Number(counts.simulated ?? meta.simulated_price_points ?? (paper.forecastResult?.episode?.tags || {}).simulated_price_points) || 0,
      };
    });

    const activeSimulationSummary = computed(() => {
      return currentSimulationSummary();
    });

    const activeSimulationSourceLabel = computed(() => {
      const counts = activeSimulationSourceCounts.value;
      const horizonDays = Number(paper.forecastResult?.episode?.horizon_days || paper.horizonDays || 0) || (counts.real + counts.simulated);
      const totalDays = Math.max(0, horizonDays);
      const simulatedDays = Math.min(totalDays, counts.simulated);
      const realDays = Math.max(0, totalDays - simulatedDays);
      return `真实行情 ${realDays} 天 · 模拟行情 ${simulatedDays} 天 · 合计 ${totalDays} 天`;
    });

    const activeSimulationScenarioRows = computed(() => {
      const scenarios = activeSimulationSummary.value?.scenarios || {};
      return ["base", "bull", "bear", "stress"]
        .map((name) => {
          const summary = scenarios[name] || {};
          const quantiles = summary.quantiles || {};
          return {
            name,
            label: scenarioLabel(name),
            paths: Number(summary.paths || 0),
            p10: quantiles.p10,
            p50: quantiles.p50,
            p90: quantiles.p90,
          };
        })
        .filter((row) => row.paths > 0);
    });


    const selectedAlphaDetail = computed(() => {
      return (selectedTaskView.value.attachments || {}).alpha_mining_detail || {};
    });

    const selectedFactorDetail = computed(() => {
      return (selectedTaskView.value.attachments || {}).factor_runtime_detail || {};
    });

    const selectedResearchDepth = computed(() => {
      return selectedTaskView.value.payload?.research_depth ?? form.researchDepth;
    });

    const workflowSteps = computed(() => {
      const status = selectedTaskView.value.status || "idle";
      const agentStatuses = selectedTaskView.value.agent_status || {};
      const attachmentsView = selectedTaskView.value.attachments || {};
      const stepStatus = (agents, fallback = "pending") => {
        const values = agents.map((agent) => agentStatuses[agent]).filter(Boolean);
        if (values.includes("in_progress")) return "in_progress";
        if (values.length && values.every((value) => value === "completed")) return "completed";
        if (["failed", "cancelled", "stale"].includes(status)) return status;
        return fallback;
      };
      return [
        { label: "提交任务", desc: "创建 run 并进入队列", status: selectedTaskView.value.run_id ? "completed" : "pending" },
        { label: "分析员", desc: "行情、情绪、新闻和基本面", status: stepStatus(["Market Analyst", "Sentiment Analyst", "News Analyst", "Fundamentals Analyst"]) },
        { label: "研究经理", desc: "多空辩论并汇总观点", status: stepStatus(["Bull Researcher", "Bear Researcher", "Research Manager"]) },
        { label: "因子经理", desc: "读取因子库并生成 factor_score", status: stepStatus(["Factor Manager"]) },
        { label: "交易计划", desc: "Trader 依据研究和因子评分出计划", status: stepStatus(["Trader"]) },
        { label: "风控决策", desc: "风险辩论和组合经理给出结论", status: stepStatus(["Aggressive Analyst", "Neutral Analyst", "Conservative Analyst", "Portfolio Manager"]) },
        {
          label: "完成后入库",
          desc: attachmentsView.alpha_mining_enabled ? "任务完成后更新因子库" : "未启用因子入库",
          status: attachmentsView.alpha_mining_detail ? "completed" : (attachmentsView.alpha_mining_enabled && ["queued", "running", "cancelling"].includes(status) ? "pending" : "idle"),
        },
      ];
    });

    function formatPercent(value) {
      const numberValue = Number(value);
      if (!Number.isFinite(numberValue)) {
        return "N/A";
      }
      return `${(numberValue * 100).toFixed(2)}%`;
    }

    function formatNumber(value, digits = 2) {
      const numberValue = Number(value);
      if (!Number.isFinite(numberValue)) {
        return "N/A";
      }
      return numberValue.toLocaleString(undefined, {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      });
    }

    function formatAlphaValue(value) {
      if (value === null || value === undefined || value === "") {
        return "N/A";
      }
      if (typeof value === "object") {
        return JSON.stringify(value, null, 2);
      }
      return String(value);
    }

    function factorManagerOutputFromDetail() {
      const detail = selectedFactorDetail.value || {};
      if (!Object.keys(detail).length) {
        return "";
      }
      const selectedAlpha = detail.selected_alpha || {};
      return [
        `本次决策前因子评分 composite=${formatNumber(detail.composite_score, 4)}，alpha signal=${formatNumber(detail.signal_score, 4)}，confidence=${formatPercent(detail.confidence)}。`,
        `选中因子: ${selectedAlpha.name || "N/A"}`,
        detail.summary || "",
      ].filter(Boolean).join("\n");
    }

    function agentOutputText(agent) {
      const outputs = selectedTaskView.value.agent_outputs || {};
      if (outputs[agent]) {
        return outputs[agent];
      }
      if (agent === "Factor Manager") {
        return factorManagerOutputFromDetail();
      }
      return "";
    }

    function agentEmptyText(agent) {
      if (agent !== "Factor Manager") {
        return "当前还没有该 Agent 的输出内容。";
      }
      if (selectedTaskView.value.status === "stale") {
        return "该任务已失效，表示原执行线程不在当前后端进程内；如果没有落盘状态日志可回填，因子经理输出无法恢复。重新运行后会在 Research Manager 之后、Trader 之前显示。";
      }
      return "因子经理会在 Research Manager 之后、Trader 之前运行；生成 factor_score 后会显示本次使用的因子评分。";
    }

    function agentLabel(agent) {
      return agentLabels[agent] || agent;
    }

    function teamLabel(team) {
      return teamLabels[team] || team;
    }

    function statusLabel(status) {
      return statusLabels[status] || status || "等待中";
    }

    function providerLabel(provider) {
      const labels = {
        openai: "OpenAI",
        "qwen-cn": "通义千问（中国站）",
        qwen: "通义千问（国际站）",
        google: "Google Gemini",
        anthropic: "Anthropic Claude",
        deepseek: "DeepSeek",
        openrouter: "OpenRouter",
        azure: "Azure OpenAI",
      };
      return labels[provider] || provider;
    }

    function apiKeyStatusLabel(value) {
      return value ? "已配置" : "未配置";
    }

    function eventLabel(kind) {
      const labels = {
        created: "创建",
        phase: "阶段",
        queue: "队列",
        log: "日志",
        agent_done: "Agent 完成",
        factor: "因子评分",
        cancel: "取消",
        error: "错误",
        done: "完成",
      };
      return labels[kind] || kind || "事件";
    }

    function formatEventTime(ts) {
      if (!ts) {
        return "--:--:--";
      }
      return formatLocalTime(ts);
    }

    const commandPreview = computed(() => {
      const args = ["python -m cli.main"];
      if (form.enableCheckpoint) {
        args.push("--checkpoint");
      }
      return [
        `Ticker=${form.ticker}`,
        `Date=${form.analysisDate}`,
        `Lookback=${form.analysisLookbackDays}`,
        `Provider=${effectiveProvider.value}`,
        `Quick=${form.quickModel}`,
        `Deep=${form.deepModel}`,
        `Analysis=${form.analysisModel || form.quickModel}`,
        `Debate=${form.debateModel || form.quickModel}`,
        `Decision=${form.decisionModel || form.deepModel}`,
        `Language=${effectiveOutputLanguage.value}`,
        `Analysts=${form.analysts.join(",")}`,
        `Depth=${form.researchDepth}`,
        `Command=${args.join(" ")}`,
      ].join(" | ");
    });

    const filteredLogs = computed(() => {
      const baseLogs = selectedTaskView.value.logs || logs.value;
      if (activeLogFilter.value === "all") {
        return baseLogs;
      }
      return baseLogs.filter((line) => {
        const kind = typeof line === "string" ? "system" : (line.kind || "system");
        return kind === activeLogFilter.value;
      });
    });

    const workbenchModules = computed(() => {
      const modules = [
        { id: "run", label: "新建分析", desc: "参数与提交", group: "开始", groupStart: true },
      ];
      if (!simpleMode.value) {
        modules.push({ id: "params", label: "任务参数", desc: "JSON 配置" });
        modules.push({ id: "agents", label: "执行编排", desc: "Agent 输出", group: "执行", groupStart: true });
        modules.push({ id: "timeline", label: "运行时间线", desc: "事件流" });
        modules.push({ id: "logs", label: "运行日志", desc: "日志筛选" });
      }
      modules.push({ id: "result", label: "运行结论", desc: "评级与仓位", group: "结果", groupStart: true });
      modules.push({ id: "report", label: "报告预览", desc: "正文与下载" });
      modules.push({ id: "paper-replay", label: "历史回测", desc: "历史结论验证", group: "模拟盘", groupStart: true });
      modules.push({ id: "paper-future", label: "推演模拟盘", desc: "模拟盘推演" });
      modules.push({ id: "paper", label: "纸面账户", desc: "真实机会虚拟执行" });
      modules.push({ id: "conclusions", label: "长期观察", desc: "统一复盘总账" });
      modules.push({ id: "history", label: "任务历史", desc: "回填与重跑", group: "管理", groupStart: true });
      if (!simpleMode.value) {
        modules.push({ id: "factors", label: "因子库", desc: "历史记录" });
      }
      return modules;
    });

    const recentPresetStocks = computed(() => {
      const seen = new Set();
      const items = [];
      [...taskHistory.value, ...defaultPresetStocks.map((ticker) => ({ ticker }))].forEach((item) => {
        const ticker = String(item?.payload?.ticker || item?.ticker || "").trim().toUpperCase();
        if (!ticker || seen.has(ticker)) {
          return;
        }
        seen.add(ticker);
        items.push(ticker);
      });
      return items.slice(0, 4);
    });

    function toggleSimpleMode() {
      simpleMode.value = !simpleMode.value;
      if (!workbenchModules.value.some((item) => item.id === activeWorkbenchModule.value)) {
        activeWorkbenchModule.value = "run";
      }
      resetMainScroll();
    }

    function showRunProgressTab() {
      activeWorkbenchModule.value = simpleMode.value ? "result" : "timeline";
      resetMainScroll();
    }

    function setWorkbenchModule(module) {
      activeWorkbenchModule.value = module.id;
      if (paperWorkbenchModuleIds.includes(module.id)) {
        if (module.id === "paper-replay" && !["overview", "ledger", "api"].includes(selectedPaperTradingView.value)) {
          selectedPaperTradingView.value = "overview";
        }
        if (module.id === "paper-future" && !["overview", "ledger", "api"].includes(selectedPaperTradingView.value)) {
          selectedPaperTradingView.value = "overview";
        }
        refreshPaperTrading();
        if (module.id === "paper-future" || module.id === "paper") {
          startPaperPolling();
        } else {
          stopPaperPolling();
        }
      } else {
        stopPaperPolling();
      }
      if (module.id === "conclusions") {
        loadConclusions();
        startObservationPolling();
      } else {
        stopObservationPolling();
      }
      resetMainScroll();
    }

    function resetMainScroll() {
      window.requestAnimationFrame(() => {
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
    }

    const queueHint = computed(() => {
      const status = selectedTaskView.value.status || runState.status;
      if (status !== "queued") {
        return "";
      }
      if (backend.activeRuns >= backend.runConcurrency) {
        return `正在等待已有任务释放执行槽：当前 ${backend.activeRuns}/${backend.runConcurrency} 个执行槽被占用。`;
      }
      return "任务正在进入执行队列，若长时间停留在这里，请刷新后检查历史任务是否已失效。";
    });

    const visibleTaskHistory = computed(() => {
      const keyword = historySearch.value.trim().toLowerCase();
      const filtered = taskHistory.value.filter((item) => {
        if (!keyword) {
          return true;
        }
        return (
          String(item.ticker || "").toLowerCase().includes(keyword) ||
          String(item.provider || "").toLowerCase().includes(keyword)
        );
      });
      return showAllHistory.value ? filtered : filtered.slice(0, 5);
    });

    function loadTaskHistory() {
      try {
        const scopedKey = `tradingagents_workbench_history_${userId}`;
        const raw = localStorage.getItem(scopedKey) || localStorage.getItem("tradingagents_workbench_history");
        taskHistory.value = raw ? JSON.parse(raw) : [];
        taskHistory.value = taskHistory.value.map((item) => {
          if (["queued", "running", "cancelling"].includes(item.status)) {
            return {
              ...item,
              status: "stale",
              phase: "服务已重启，任务状态需重新运行",
              result_summary: item.result_summary || "该任务只保存在浏览器历史中，后端当前进程已无法继续轮询或取消。",
              updated_at: localTimestamp(),
            };
          }
          return item;
        });
        if (!localStorage.getItem(scopedKey) && raw) {
          localStorage.setItem(scopedKey, JSON.stringify(taskHistory.value.slice(0, 20)));
        }
        persistTaskHistory();
      } catch (error) {
        taskHistory.value = [];
      }
    }

    function persistTaskHistory() {
      localStorage.setItem(`tradingagents_workbench_history_${userId}`, JSON.stringify(taskHistory.value.slice(0, 20)));
    }

    function isTerminalRunStatus(status) {
      return ["completed", "failed", "cancelled"].includes(status);
    }

    function historySortTime(item) {
      const timestamp = Date.parse(item?.updated_at || item?.persisted_at || item?.created_at || "");
      return Number.isFinite(timestamp) ? timestamp : 0;
    }

    function applyHistoryItems(items = []) {
      const normalized = items
        .filter((item) => item?.run_id)
        .map((item) => ({
          run_id: item.run_id,
          user_id: item.user_id || userId,
          ticker: item.payload?.ticker || item.ticker || "",
          provider: item.payload?.llm_provider || item.provider || "",
          status: item.status,
          phase: item.phase,
          progress: item.progress ?? 0,
          elapsed: item.elapsed || "00:00",
          rating: item.result?.rating || item.rating || "",
          result_summary: item.result?.summary || item.result_summary || "",
          report_path: item.attachments?.report_path || item.report_path || "",
          updated_at: item.updated_at || item.persisted_at || localTimestamp(),
          payload: item.payload || null,
          checkpoint_enabled: !!item.checkpoint_enabled,
          checkpoint_available: !!item.checkpoint_available,
          resume_hint: item.resume_hint || "",
          result: item.result || null,
          attachments: item.attachments || {},
          report_preview: item.report_preview || "",
          report_file: item.report_file || "",
          report_sections: item.report_sections || {},
          agent_status: item.agent_status || {},
          agent_outputs: item.agent_outputs || {},
          events: item.events || [],
          metrics: item.metrics || {},
          logs: item.logs || [],
          cancel_requested: !!item.cancel_requested,
          analyst_execution_mode: item.analyst_execution_mode || item.payload?.analyst_execution_mode || "serial",
        }));
      const byId = new Map();
      [...normalized, ...taskHistory.value].forEach((item) => {
        if (!byId.has(item.run_id)) {
          byId.set(item.run_id, item);
        }
      });
      taskHistory.value = Array.from(byId.values())
        .sort((a, b) => historySortTime(b) - historySortTime(a))
        .slice(0, 50);
      if (!selectedTaskRunId.value && taskHistory.value.length > 0) {
        selectedTaskRunId.value = taskHistory.value[0].run_id;
      }
      persistTaskHistory();
    }

    async function refreshRunSnapshot(runId) {
      if (!backend.connected || !runId) {
        return null;
      }
      const snapshot = await fetchJson(`/api/runs/${runId}`);
      syncBackendQueue(snapshot.queue || {});
      applyRunSnapshot(snapshot);
      return snapshot;
    }

    async function loadServerHistory() {
      if (!backend.connected) {
        return;
      }
      try {
        const payload = await fetchJson("/api/history?limit=50");
        syncBackendQueue(payload.queue || {});
        applyHistoryItems(payload.items || []);
        if (selectedTaskRunId.value) {
          try {
            await refreshRunSnapshot(selectedTaskRunId.value);
          } catch (error) {
            logs.value.unshift(`[warning] 刷新当前任务详情失败: ${error.message}`);
          }
        }
        logs.value.unshift(`[system] 已同步服务端历史任务 ${payload.count || 0} 条`);
      } catch (error) {
        logs.value.unshift(`[warning] 同步服务端历史失败: ${error.message}`);
      }
    }

    async function loadWorkbenchSettings() {
      if (!backend.connected) {
        return;
      }
      try {
        const payload = await fetchJson("/api/settings");
        const effective = payload.effective || {};
        if (effective.llm_timeout) {
          form.llmTimeout = effective.llm_timeout;
        }
        if (effective.llm_max_retries !== undefined) {
          form.llmMaxRetries = effective.llm_max_retries;
        }
      } catch (error) {
        logs.value.unshift(`[warning] 加载工作台设置失败: ${error.message}`);
      }
    }

    async function checkHealth() {
      healthState.open = true;
      healthState.loading = true;
      healthState.error = "";
      try {
        const health = await fetchJson("/api/health");
        healthState.data = health;
        healthState.llmTimeoutDraft = Number(health.llm_timeout || form.llmTimeout || 90);
        healthState.llmMaxRetriesDraft = Number(health.llm_max_retries ?? form.llmMaxRetries ?? 2);
        syncBackendQueue(health.queue || {});
        const providerCount = Object.values(health.providers || {}).filter((item) => item.api_key_present).length;
        logs.value.unshift(
          `[health] 健康检查完成 ok=${health.ok} slots=${backend.activeRuns}/${backend.runConcurrency} api_keys=${providerCount}`
        );
      } catch (error) {
        healthState.error = error.message;
        logs.value.unshift(`[warning] 健康检查失败: ${error.message}`);
      } finally {
        healthState.loading = false;
      }
    }

    async function saveHealthProtection() {
      healthState.saving = true;
      healthState.error = "";
      try {
        const timeoutValue = Math.max(15, Math.min(600, Number(healthState.llmTimeoutDraft || 90)));
        const retryValue = Math.max(0, Math.min(5, Number(healthState.llmMaxRetriesDraft ?? 2)));
        const response = await fetchJson("/api/settings", {
          method: "POST",
          body: JSON.stringify({
            user_id: userId,
            llm_timeout: timeoutValue,
            llm_max_retries: retryValue,
          }),
        });
        form.llmTimeout = response.health?.llm_timeout || timeoutValue;
        form.llmMaxRetries = response.health?.llm_max_retries ?? retryValue;
        healthState.data = response.health || healthState.data;
        healthState.llmTimeoutDraft = form.llmTimeout;
        healthState.llmMaxRetriesDraft = form.llmMaxRetries;
        saveDefaultParams();
        logs.value.unshift(`[system] 已保存模型请求保护: ${form.llmTimeout} 秒 / ${form.llmMaxRetries} 次`);
      } catch (error) {
        healthState.error = error.message;
        logs.value.unshift(`[warning] 保存模型请求保护失败: ${error.message}`);
      } finally {
        healthState.saving = false;
      }
    }

    function upsertTaskHistory(snapshot) {
      if (!snapshot?.run_id) {
        return;
      }
      const entry = {
        run_id: snapshot.run_id,
        user_id: snapshot.user_id || userId,
        ticker: snapshot.payload?.ticker || form.ticker,
        provider: snapshot.payload?.llm_provider || effectiveProvider.value,
        status: snapshot.status,
        phase: snapshot.phase,
        progress: snapshot.progress ?? 0,
        elapsed: snapshot.elapsed || "00:00",
        rating: snapshot.result?.rating || "",
        result_summary: snapshot.result?.summary || "",
        report_path: snapshot.attachments?.report_path || "",
        updated_at: snapshot.updated_at || localTimestamp(),
        payload: snapshot.payload || null,
        checkpoint_enabled: !!snapshot.checkpoint_enabled,
        checkpoint_available: !!snapshot.checkpoint_available,
        resume_hint: snapshot.resume_hint || "",
        result: snapshot.result || null,
        attachments: snapshot.attachments || {},
        report_preview: snapshot.report_preview || "",
        report_file: snapshot.report_file || "",
        report_sections: snapshot.report_sections || {},
        agent_status: snapshot.agent_status || {},
        agent_outputs: snapshot.agent_outputs || {},
        events: snapshot.events || [],
        metrics: snapshot.metrics || {},
        logs: snapshot.logs || [],
        cancel_requested: !!snapshot.cancel_requested,
        analyst_execution_mode: snapshot.analyst_execution_mode || snapshot.payload?.analyst_execution_mode || "serial",
      };
      const existingIndex = taskHistory.value.findIndex((item) => item.run_id === entry.run_id);
      if (existingIndex >= 0) {
        taskHistory.value.splice(existingIndex, 1, entry);
      } else {
        taskHistory.value.unshift(entry);
      }
      if (!selectedTaskRunId.value || selectedTaskRunId.value === entry.run_id) {
        selectedTaskRunId.value = entry.run_id;
      }
      persistTaskHistory();
    }

    function providerBaseFromProvider(provider) {
      if (provider === "qwen-cn") return "qwen";
      if (provider === "glm-cn") return "glm";
      if (provider === "minimax-cn") return "minimax";
      return provider || "openai";
    }

    function applyHistoryItem(item) {
      const payload = item?.payload;
      if (!payload) {
        logs.value.unshift("[warning] 该历史任务没有可回填的参数");
        return;
      }

      const provider = payload.llm_provider || "openai";
      const providerBase = providerBaseFromProvider(provider);

      form.ticker = payload.ticker || form.ticker;
      form.assetType = payload.asset_type || "stock";
      form.analysisDate = payload.analysis_date || form.analysisDate;
      form.analysisLookbackDays = payload.analysis_lookback_days || 30;
      form.outputLanguage = outputLanguages.includes(payload.output_language) ? payload.output_language : "custom";
      form.customLanguage = outputLanguages.includes(payload.output_language) ? "" : (payload.output_language || "");
      form.analysts = Array.isArray(payload.analysts) ? payload.analysts : form.analysts;
      form.researchDepth = payload.research_depth || 1;
      form.parallelAnalysts = !!payload.parallel_analysts;
      form.llmProviderBase = providerBase;
      form.llmProvider = provider;
      form.backendUrl = payload.backend_url || providerDefaults[provider] || providerDefaults[providerBase] || "";
      form.quickModel = payload.quick_think_llm || form.quickModel;
      form.deepModel = payload.deep_think_llm || form.deepModel;
      form.analysisModel = payload.analysis_think_llm || form.quickModel;
      form.debateModel = payload.debate_think_llm || form.quickModel;
      form.decisionModel = payload.decision_think_llm || form.deepModel;
      form.enableCheckpoint = !!payload.checkpoint_enabled;
      form.benchmarkTicker = payload.benchmark_ticker || "";
      form.googleThinkingLevel = payload.google_thinking_level || "high";
      form.openaiReasoningEffort = payload.openai_reasoning_effort || "medium";
      form.anthropicEffort = payload.anthropic_effort || "high";
      form.llmTimeout = payload.llm_timeout || 90;
      form.llmMaxRetries = payload.llm_max_retries ?? 2;
      form.saveReport = payload.save_report !== false;
      form.autoDisplayReport = payload.auto_display_report !== false;
      form.runReportEvaluation = !!payload.run_report_evaluation;
      form.reportReferencePath = payload.report_reference_path || "";
      form.reportTopic = payload.report_topic || "";
      form.runBacktest = !!payload.run_backtest;
      form.backtestInitialCapital = String(payload.backtest_initial_capital || "1.0");
      form.backtestHoldingDays = String(payload.backtest_holding_days || "5,10,20");
      form.runAlphaMining = !!payload.run_alpha_mining;
      form.displayFullReport = payload.display_full_report !== false;
      form.ensureApiKey = false;
      form.apiKeyValue = "";
      syncProviderRegion();
      form.llmProvider = provider;
      form.backendUrl = payload.backend_url || form.backendUrl;
      logs.value.unshift(`[system] 已回填历史任务参数: ${item.ticker} / ${item.provider}`);
      activeWorkbenchModule.value = "run";
    }

    function rerunHistoryItem(item) {
      applyHistoryItem(item);
      if (!form.enableCheckpoint) {
        logs.value.unshift("[hint] 若希望从失败节点恢复，请确保 checkpoint 已开启");
      }
      runAnalysis();
    }

    function toggleHistoryExpansion(runId) {
      expandedHistory[runId] = !expandedHistory[runId];
    }

    async function selectTask(runId) {
      selectedTaskRunId.value = runId;
      if (!backend.connected || !runId) {
        return;
      }
      try {
        const snapshot = await fetchJson(`/api/runs/${runId}`);
        syncBackendQueue(snapshot.queue || {});
        applyRunSnapshot(snapshot);
      } catch (error) {
        logs.value.unshift(`[warning] 刷新任务详情失败: ${error.message}`);
      }
    }

    async function rerunWithoutCheckpoint(item) {
      applyHistoryItem(item);
      if (form.enableCheckpoint) {
        try {
          await fetchJson("/api/clear-checkpoint", {
            method: "POST",
            body: JSON.stringify({
              user_id: userId,
              ticker: form.ticker,
              analysis_date: form.analysisDate,
            }),
          });
          logs.value.unshift("[system] 已清除 checkpoint，将从头重新运行");
        } catch (error) {
          logs.value.unshift(`[warning] 清除 checkpoint 失败: ${error.message}`);
        }
      }
      runAnalysis();
    }

    function exportCurrentConfig() {
      const blob = new Blob([configPreview.value], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `run-config-${form.ticker || "task"}.json`;
      a.click();
      URL.revokeObjectURL(url);
    }

    function exportLogs() {
      const body = filteredLogs.value.map((line) => {
        if (typeof line === "string") {
          return line;
        }
        return `[${line.kind}] ${line.text}`;
      }).join("\n");
      const blob = new Blob([body], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `run-logs-${form.ticker || "task"}.txt`;
      a.click();
      URL.revokeObjectURL(url);
    }

    function exportAgentOutputs() {
      const outputs = { ...(selectedTaskView.value.agent_outputs || {}) };
      const factorOutput = agentOutputText("Factor Manager");
      if (factorOutput && !outputs["Factor Manager"]) {
        outputs["Factor Manager"] = factorOutput;
      }
      const blob = new Blob([JSON.stringify(outputs, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `agent-outputs-${form.ticker || "task"}.json`;
      a.click();
      URL.revokeObjectURL(url);
    }

    async function downloadReport() {
      const runId = selectedTaskView.value.run_id;
      if (!runId) {
        logs.value.unshift("[warning] 当前没有可下载的报告任务");
        return;
      }
      try {
        const response = await fetch(`/api/runs/${runId}/report`, {
          headers: {
            "X-TradingAgents-User": userId,
          },
        });
        if (!response.ok) {
          const message = await response.text();
          throw new Error(message || `HTTP ${response.status}`);
        }
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        const ticker = selectedTaskView.value.ticker || form.ticker || "report";
        const date = selectedTaskView.value.payload?.analysis_date || form.analysisDate || "";
        a.href = url;
        a.download = `${ticker}_${date}_complete_report.md`;
        a.click();
        URL.revokeObjectURL(url);
        logs.value.unshift("[report] 已开始下载报告");
      } catch (error) {
        logs.value.unshift(`[warning] 下载报告失败: ${error.message}`);
      }
    }

    function retryLastRun() {
      runAnalysis();
    }

    async function loadAlphaLibrary(ticker = form.ticker) {
      const target = String(ticker || "").trim().toUpperCase();
      if (!target) {
      alphaLibrary.error = "请先输入股票或币种代码";
        return;
      }
      alphaLibrary.ticker = target;
      alphaLibrary.loading = true;
      alphaLibrary.error = "";
      showAllAlphaHistory.value = false;
      showAllAlphaRegistry.value = false;
      try {
        alphaLibrary.data = await fetchJson(`/api/alpha-factors?ticker=${encodeURIComponent(target)}`);
        logs.value.unshift(`[alpha] 已加载 ${target} 的因子库`);
      } catch (error) {
        alphaLibrary.error = error.message;
        logs.value.unshift(`[warning] 加载 Alpha 因子库失败: ${error.message}`);
      } finally {
        alphaLibrary.loading = false;
      }
    }

    function syncConclusionsPayload(payload) {
      conclusions.items = Array.isArray(payload.items) ? payload.items : [];
      conclusions.summary = payload.summary || {};
      if (!conclusions.items.some((item) => item.conclusion_id === conclusions.selectedConclusionId)) {
        conclusions.selectedConclusionId = conclusions.items[0]?.conclusion_id || "";
      }
    }

    async function refreshObservationIntraday({ quiet = false } = {}) {
      const ticker = observationTicker.value;
      if (!ticker) {
        return;
      }
      const matchedTrack = conclusions.items.find((item) => String(item?.ticker || "").toUpperCase() === ticker) || {};
      const assetType = looksLikeCryptoTicker(ticker)
        ? "crypto"
        : (matchedTrack.asset_type || conclusions.form.assetType || form.assetType);
      conclusions.quoteLoading = true;
      try {
        const query = `ticker=${encodeURIComponent(ticker)}&asset_type=${encodeURIComponent(assetType || "stock")}`;
        const quote = await fetchJson(`/api/simulation/observation/intraday?${query}`);
        const today = localDateInputValue();
        const intradayRows = Array.isArray(quote.intraday)
          ? quote.intraday
          : (Array.isArray(quote.history)
            ? quote.history
              .map((row) => ({
                time: row.time || row.timestamp || row.datetime || row.date || quote.as_of,
                price: row.price ?? row.close ?? row.Close,
                open: row.open ?? row.Open,
                high: row.high ?? row.High,
                low: row.low ?? row.Low,
                volume: row.volume ?? row.Volume,
              }))
              .filter((row) => Number.isFinite(Number(row.price)))
            : []);
        const todayRows = intradayRows.filter((row) => String(row.time || row.as_of || "").slice(0, 10) === today);
        conclusions.intradayRows = todayRows.length
          ? todayRows
          : (intradayRows.length && String(intradayRows[intradayRows.length - 1]?.time || "").slice(0, 10) === today
            ? [intradayRows[intradayRows.length - 1]]
            : []);
        if (!conclusions.intradayRows.length) {
          conclusions.intradayRows = [{
            time: quote.as_of || localTimestamp(),
            price: quote.price,
            open: quote.price,
            high: quote.price,
            low: quote.price,
            volume: null,
          }];
        }
        conclusions.quote = quote;
        conclusions.quoteLastUpdated = new Date().toLocaleTimeString("zh-CN", { hour12: false });
      } catch (error) {
        if (!quiet) {
          logs.value.unshift(`[conclusion] 当日实时价格刷新失败: ${extractErrorMessage(error.message)}`);
        }
      } finally {
        conclusions.quoteLoading = false;
      }
    }

    function conclusionStatusLabel(status) {
      const labels = {
        proposed: "待观察",
        tracking: "跟踪中",
        due_review: "待复盘",
        validated: "已验证",
        invalidated: "已失效",
        exited: "已退出",
        archived: "已归档",
      };
      return labels[status] || status || "tracking";
    }

    function scenarioLabel(value) {
      const labels = {
        base: "基准",
        neutral: "中性",
        bull: "乐观",
        bear: "悲观",
        stress: "压力",
      };
      return labels[String(value || "").toLowerCase()] || value || "基准";
    }

    function simulationTypeLabel(value) {
      const labels = {
        forecast: "推演",
        paper_trade: "纸面",
        backtest: "回测",
        historical_replay: "回测",
        forward_test: "推演",
        live: "纸面",
      };
      return labels[String(value || "").toLowerCase()] || value || "未知";
    }

    function simulationStateLabel(value) {
      const labels = {
        simulated_path: "全模拟",
        mixed_real_simulated: "真实+模拟",
        real_history: "全真实",
        tracking_without_future_data: "待回补",
        pending: "待回补",
        valid: "仍有效",
        drifting: "有偏差",
        invalidated: "已失效",
        unresolved: "未解析",
        no_trade: "无交易",
        completed: "已完成",
        tracking: "跟踪中",
        due_review: "待复盘",
      };
      return labels[String(value || "").toLowerCase()] || conclusionStatusLabel(value);
    }

    async function refreshConclusionsLifecycle({ quiet = false } = {}) {
      if (!quiet) {
        conclusions.loading = true;
        conclusions.error = "";
      }
      try {
        syncConclusionsPayload(await fetchJson("/api/observations"));
        conclusions.lifecycleLastUpdated = new Date().toLocaleTimeString("zh-CN", { hour12: false });
      } catch (error) {
        if (!quiet) {
          conclusions.error = error.message;
          logs.value.unshift(`[conclusion] 加载研究跟踪盘失败: ${error.message}`);
        }
      } finally {
        if (!quiet) {
          conclusions.loading = false;
        }
      }
    }

    async function loadConclusions() {
      await refreshConclusionsLifecycle();
      await refreshObservationIntraday({ quiet: true });
    }

    async function addManualConclusion() {
      const ticker = String(conclusions.form.ticker || form.ticker || "").trim().toUpperCase();
      if (!ticker) {
        conclusions.error = "请先输入股票或币种代码";
        return;
      }
      const payload = {
        ticker,
        asset_type: conclusions.form.assetType || form.assetType,
        thesis: conclusions.form.thesis,
        rating: conclusions.form.rating,
        action: conclusions.form.action,
        target_position_size: conclusions.form.targetPositionSize,
        horizon_days: conclusions.form.horizonDays,
      };
      try {
        const result = await fetchJson("/api/observations", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        syncConclusionsPayload(result);
        conclusions.lifecycleLastUpdated = new Date().toLocaleTimeString("zh-CN", { hour12: false });
        conclusions.form.thesis = "";
        logs.value.unshift(`[conclusion] ${ticker} 已加入研究跟踪盘`);
      } catch (error) {
        conclusions.error = error.message;
      }
    }

    async function addSelectedRunConclusion() {
      const runId = selectedTaskView.value.run_id;
      if (!runId) {
        conclusions.error = "当前没有可入池的任务";
        return;
      }
      try {
        const result = await fetchJson("/api/observations/from-run", {
          method: "POST",
          body: JSON.stringify({ run_id: runId }),
        });
        syncConclusionsPayload(result);
        conclusions.lifecycleLastUpdated = new Date().toLocaleTimeString("zh-CN", { hour12: false });
        logs.value.unshift(`[conclusion] 当前任务结论已入池: ${runId}`);
      } catch (error) {
        conclusions.error = error.message;
      }
    }

    async function reviewConclusion(track, status) {
      if (!track?.conclusion_id) {
        return;
      }
      const note = conclusions.reviewNotes[track.conclusion_id] || "";
      try {
        const result = await fetchJson("/api/observations/update", {
          method: "POST",
          body: JSON.stringify({
            conclusion_id: track.conclusion_id,
            status,
            review_notes: note,
            note,
            event_type: "review",
          }),
        });
        syncConclusionsPayload(result);
        conclusions.lifecycleLastUpdated = new Date().toLocaleTimeString("zh-CN", { hour12: false });
        logs.value.unshift(`[conclusion] ${track.ticker} 已标记为 ${conclusionStatusLabel(status)}`);
      } catch (error) {
        conclusions.error = error.message;
      }
    }

    async function deleteConclusion(track) {
      if (!track?.conclusion_id) {
        return;
      }
      const confirmed = window.confirm(
        `确认删除 ${track.ticker || "这条结论"} 的研究跟踪记录？\n\n删除后不会再出现在跟踪盘，且不可恢复。`
      );
      if (!confirmed) {
        return;
      }
      try {
        const result = await fetchJson("/api/observations/delete", {
          method: "POST",
          body: JSON.stringify({ conclusion_id: track.conclusion_id }),
        });
        delete conclusions.reviewNotes[track.conclusion_id];
        syncConclusionsPayload(result);
        conclusions.lifecycleLastUpdated = new Date().toLocaleTimeString("zh-CN", { hour12: false });
        logs.value.unshift(`[conclusion] 已删除 ${track.ticker || track.conclusion_id} 的跟踪记录`);
      } catch (error) {
        conclusions.error = error.message;
      }
    }

    let paperPollTimer = null;
    let observationPollTimer = null;
    let observationLifecyclePollTimer = null;

    function rememberPaperQuote(quote, ticker = paper.ticker) {
      const price = Number(quote?.price);
      const normalizedTicker = String(ticker || "").trim().toUpperCase();
      if (!normalizedTicker || !Number.isFinite(price)) {
        return;
      }
      const asOf = normalizeLiveQuoteTime(quote?.as_of);
      const last = paper.quoteHistory[paper.quoteHistory.length - 1];
      if (last && last.ticker === normalizedTicker && last.as_of === asOf && last.price === price) {
        return;
      }
      paper.quoteHistory.push({
        ticker: normalizedTicker,
        price,
        as_of: asOf,
      });
      if (paper.quoteHistory.length > 240) {
        paper.quoteHistory.splice(0, paper.quoteHistory.length - 240);
      }
    }

    function updatePaperChartHover(event) {
      const rect = event.currentTarget.getBoundingClientRect();
      if (!rect.width || !activePaperChart.value.series.length) {
        paper.chartHover = null;
        return;
      }
      const svgX = (event.clientX - rect.left) / rect.width * 700;
      const axisSeries = activePaperChart.value.series.find((item) => item.key === "price") || activePaperChart.value.series[0];
      const anchor = (axisSeries.pointItems || []).reduce((best, item) => {
        if (!best || Math.abs(item.x - svgX) < Math.abs(best.x - svgX)) {
          return item;
        }
        return best;
      }, null);
      if (!anchor) {
        paper.chartHover = null;
        return;
      }
      const items = activePaperChart.value.series.map((series) => {
        const point = (series.pointItems || []).reduce((best, item) => {
          if (!best || Math.abs(item.x - anchor.x) < Math.abs(best.x - anchor.x)) {
            return item;
          }
          return best;
        }, null);
        return point ? {
          key: series.key,
          label: series.label,
          value: point.value,
          decimals: series.decimals,
          x: point.x,
          y: point.y,
        } : null;
      }).filter(Boolean);
      paper.chartHover = {
        x: anchor.x,
        y: anchor.y,
        date: formatChartHoverLabel(anchor.date),
        items,
      };
    }

    function clearPaperChartHover() {
      paper.chartHover = null;
    }

    function updateObservationChartHover(event) {
      const rect = event.currentTarget.getBoundingClientRect();
      if (!rect.width || !observationReturnChart.value.series.length) {
        conclusions.chartHover = null;
        return;
      }
      const svgX = (event.clientX - rect.left) / rect.width * 700;
      const axisSeries = observationReturnChart.value.series[0];
      const anchor = (axisSeries.pointItems || []).reduce((best, item) => {
        if (!best || Math.abs(item.x - svgX) < Math.abs(best.x - svgX)) {
          return item;
        }
        return best;
      }, null);
      if (!anchor) {
        conclusions.chartHover = null;
        return;
      }
      conclusions.chartHover = {
        x: anchor.x,
        y: anchor.y,
        date: formatChartHoverLabel(anchor.date),
        items: observationReturnChart.value.series.map((series) => {
          const point = (series.pointItems || []).reduce((best, item) => {
            if (!best || Math.abs(item.x - anchor.x) < Math.abs(best.x - anchor.x)) {
              return item;
            }
            return best;
          }, null);
          return point ? {
            key: series.key,
            label: series.label,
            value: point.value,
            decimals: series.decimals,
            x: point.x,
            y: point.y,
          } : null;
        }).filter(Boolean),
      };
    }

    function clearObservationChartHover() {
      conclusions.chartHover = null;
    }

    async function loadPaperAnalyticsSkills() {
      const payload = await fetchJson("/api/simulation/forecast/skills");
      paper.analyticsSkills = Array.isArray(payload.items) ? payload.items : [];
      paper.analyticsSkills.forEach((skill) => {
        if (paper.selectedAnalyticsSkills[skill.name] === undefined) {
          paper.selectedAnalyticsSkills[skill.name] = !!skill.default_enabled;
        }
      });
    }

    function selectedPaperSkillNames() {
      const selected = paper.analyticsSkills
        .filter((skill) => skill.available !== false && paper.selectedAnalyticsSkills[skill.name])
        .map((skill) => skill.name);
      return selected.length ? selected : ["builtin_performance", "conclusion_lifecycle"];
    }

    async function refreshPaperAnalytics() {
      if (!paper.analyticsSkills.length) {
        await loadPaperAnalyticsSkills();
      }
      const skills = selectedPaperSkillNames().map(encodeURIComponent).join(",");
      paper.analytics = await fetchJson(`/api/simulation/forecast/analytics?skills=${skills}`);
    }

    async function refreshPaperEpisodes() {
      try {
        paper.episodes = await fetchJson("/api/simulation/episodes?limit=200");
        paper.ledgerLastUpdated = new Date().toLocaleTimeString("zh-CN", { hour12: false });
      } catch (error) {
        logs.value.unshift(`[paper] 演练账本暂不可用: ${extractErrorMessage(error.message)}`);
      }
    }

    async function refreshPaperTrading({ quiet = false } = {}) {
      const ticker = String(paper.ticker || "").trim().toUpperCase();
      if (!ticker) {
        paper.error = "请先输入股票或币种代码";
        return;
      }
      paper.ticker = ticker;
      if (!paper.replayTicker) {
        paper.replayTicker = ticker;
      }
      if (!paper.replayTradeDate) {
        const defaultReplayDate = new Date();
        defaultReplayDate.setDate(defaultReplayDate.getDate() - 30);
        paper.replayTradeDate = localDateInputValue(defaultReplayDate);
      }
      if (looksLikeCryptoTicker(ticker)) {
        paper.assetType = "crypto";
      }
      paper.loading = true;
      if (!quiet) {
        paper.error = "";
      }
      try {
        const query = `ticker=${encodeURIComponent(ticker)}&asset_type=${encodeURIComponent(paper.assetType)}`;
        const [quote, account, signals] = await Promise.all([
          fetchJson(`/api/simulation/forecast/quote?${query}`),
          fetchJson(`/api/simulation/forecast/account?${query}`),
          fetchJson("/api/simulation/forecast/signals"),
        ]);
        await Promise.all([refreshPaperAnalytics(), refreshPaperEpisodes()]);
        paper.quote = quote;
        rememberPaperQuote(quote, ticker);
        paper.account = account;
        paper.signals = Array.isArray(signals.items) ? signals.items : [];
        paper.lastUpdated = new Date().toLocaleTimeString("zh-CN", { hour12: false });
      } catch (error) {
        paper.error = error.message;
        if (!quiet) {
          logs.value.unshift(`[paper] 刷新模拟盘失败: ${error.message}`);
        }
      } finally {
        paper.loading = false;
      }
    }

    function startPaperPolling() {
      window.clearInterval(paperPollTimer);
      if (!paper.autoRefresh) {
        return;
      }
      paperPollTimer = window.setInterval(() => {
        if (activeWorkbenchModule.value === "paper" || activeWorkbenchModule.value === "paper-future") {
          refreshPaperTrading({ quiet: true });
        }
      }, 15000);
    }

    function stopPaperPolling() {
      window.clearInterval(paperPollTimer);
      paperPollTimer = null;
    }

    function startObservationPolling() {
      window.clearInterval(observationPollTimer);
      window.clearInterval(observationLifecyclePollTimer);
      observationPollTimer = window.setInterval(() => {
        if (activeWorkbenchModule.value === "conclusions") {
          refreshObservationIntraday({ quiet: true });
        }
      }, 15000);
      observationLifecyclePollTimer = window.setInterval(() => {
        if (activeWorkbenchModule.value === "conclusions") {
          refreshConclusionsLifecycle({ quiet: true });
        }
      }, 300000);
    }

    function stopObservationPolling() {
      window.clearInterval(observationPollTimer);
      window.clearInterval(observationLifecyclePollTimer);
      observationPollTimer = null;
      observationLifecyclePollTimer = null;
    }

    async function resetPaperAccount() {
      try {
        const payload = await fetchJson("/api/simulation/forecast/reset", {
          method: "POST",
          body: JSON.stringify({ initial_cash: paper.initialCash }),
        });
        paper.account = payload.account;
        logs.value.unshift("[paper] 模拟账户已重置");
        await refreshPaperTrading({ quiet: true });
      } catch (error) {
        paper.error = error.message;
      }
    }

    async function submitForecastObservation(orderOverride = null) {
      const source = orderOverride || {};
      const payload = {
        ticker: source.ticker || paper.ticker,
        asset_type: source.asset_type || paper.assetType,
        action: source.action || paper.action,
        rating: source.rating || "Forecast",
        target_position_size: source.target_position_size ?? paper.targetPositionSize,
        risk_gate_approved: source.risk_gate_approved ?? true,
        source_run_id: source.source_run_id || "",
        thesis: source.thesis ?? paper.conclusionThesis,
        horizon_days: source.horizon_days ?? paper.horizonDays,
        confidence: source.confidence ?? 0,
        analysis_date: source.analysis_date || paper.forecastAnalysisDate || localDateInputValue(),
        entry_price: source.entry_price || paper.forecastEntryPrice || undefined,
        simulation_scenario: paper.simulationScenario,
        simulation_drift: paper.simulationDrift || undefined,
        simulation_volatility: paper.simulationVolatility || undefined,
        simulation_seed: paper.simulationSeed || undefined,
        simulation_paths: paper.simulationPaths || undefined,
        execute_paper_account: !!paper.executePaperAccount,
        commission_rate: paper.commissionRate,
        slippage_rate: paper.slippageRate,
      };
      try {
        const result = await fetchJson("/api/forecast-observations", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        paper.forecastResult = result;
        paper.quote = result.quote || paper.quote;
        if (result.paper?.account) {
          paper.account = result.paper.account;
        }
        syncConclusionsPayload(result);
        await Promise.all([refreshPaperEpisodes(), refreshPaperAnalytics()]);
        logs.value.unshift(
          paper.executePaperAccount
            ? "[simulation] 推演记录已入池，并同步写入纸面账户"
            : "[simulation] 推演模拟盘已入池"
        );
      } catch (error) {
        paper.error = error.message;
        logs.value.unshift(`[simulation] 运行推演模拟盘失败: ${error.message}`);
      }
    }

    async function submitPaperOrder(orderOverride = null) {
      const source = orderOverride || {};
      const payload = {
        ticker: paper.ticker,
        asset_type: paper.assetType,
        action: source.action || paper.action,
        rating: source.rating || "Manual",
        target_position_size: source.target_position_size ?? paper.targetPositionSize,
        risk_gate_approved: source.risk_gate_approved ?? true,
        source_run_id: source.source_run_id || "",
        thesis: source.thesis ?? paper.conclusionThesis,
        horizon_days: source.horizon_days ?? paper.horizonDays,
        commission_rate: paper.commissionRate,
        slippage_rate: paper.slippageRate,
      };
      try {
        const result = await fetchJson("/api/simulation/forecast/order", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        paper.quote = result.quote;
        rememberPaperQuote(result.quote, payload.ticker);
        paper.account = result.account;
        await Promise.all([refreshPaperAnalytics(), refreshPaperEpisodes()]);
        logs.value.unshift(result.fill ? "[paper] 模拟成交已写入账户" : "[paper] 订单未产生新成交");
      } catch (error) {
        paper.error = error.message;
        logs.value.unshift(`[paper] 下单失败: ${error.message}`);
      }
    }

    function applyPaperSignal(options = {}) {
      const submit = typeof options === "boolean" ? options : options.submit !== false;
      const mode = options.mode || "live";
      const runId = options.runId || (mode === "replay" ? paper.selectedReplaySignalRunId : paper.selectedSignalRunId);
      const signal = paper.signals.find((item) => item.run_id === runId);
      if (!signal || !signal.execution_plan) {
        paper.error = "请选择一个带 execution_plan 的历史任务";
        return;
      }
      const plan = signal.execution_plan || {};
      const liveMode = mode !== "replay";
      const targetPosition = plan.target_position_size ?? plan.position_size ?? (liveMode ? paper.targetPositionSize : paper.replayTargetPositionSize);
      const horizonDays = plan.horizon_days ?? plan.time_horizon_days ?? plan.holding_days ?? (liveMode ? paper.horizonDays : paper.replayHorizonDays);
      const action = plan.action || (liveMode ? paper.action : paper.replayAction);
      const thesis = signal.summary || plan.thesis || (liveMode ? paper.conclusionThesis : paper.replayThesis);
      if (liveMode) {
        paper.ticker = String(signal.ticker || paper.ticker || "").toUpperCase();
        paper.assetType = signal.asset_type || paper.assetType;
        paper.action = action;
        paper.targetPositionSize = String(targetPosition);
        paper.horizonDays = String(horizonDays);
        paper.forecastAnalysisDate = String(signal.analysis_date || paper.forecastAnalysisDate || localDateInputValue()).slice(0, 10);
        paper.conclusionThesis = thesis;
      } else {
        paper.replayTicker = String(signal.ticker || paper.replayTicker || paper.ticker || "").toUpperCase();
        paper.replayTradeDate = String(signal.analysis_date || paper.replayTradeDate || "").slice(0, 10);
        paper.replayAction = action;
        paper.replayTargetPositionSize = String(targetPosition);
        paper.replayHorizonDays = String(horizonDays);
        paper.replayThesis = thesis;
      }
      paper.error = "";
      if (!submit) {
        logs.value.unshift(`[paper] 已回填${liveMode ? "未来推演" : "历史回测"}参数: ${signal.ticker || paper.ticker}`);
        return;
      }
      if (!liveMode) {
        replayHistoricalPaperSignal(signal);
        return;
      }
      const submitFn = isPaperAccountModule.value ? submitPaperOrder : submitForecastObservation;
      submitFn({
        action,
        rating: signal.rating || action,
        target_position_size: targetPosition,
        risk_gate_approved: plan.risk_gate_approved,
        source_run_id: signal.run_id,
        thesis: paper.conclusionThesis || "",
        horizon_days: horizonDays,
      });
    }

    function isHistoricalPaperSignal(signal) {
      const signalDate = String(signal?.analysis_date || "").slice(0, 10);
      return Boolean(signalDate) && signalDate < localDateInputValue();
    }

    function selectedPaperSignal(runId = paper.selectedSignalRunId) {
      return paper.signals.find((item) => item.run_id === runId) || null;
    }

    function paperSignalSubmitLabel(mode = "live") {
      if (mode === "replay") {
        return "运行历史真实数据回测";
      }
      return isPaperAccountModule.value ? "用当前行情纸面下单" : "运行推演模拟盘";
    }

    async function replayHistoricalPaperSignal(signal) {
      paper.loading = true;
      paper.error = "";
      try {
        const payload = await fetchJson("/api/simulation/backtest/from-signal", {
          method: "POST",
          body: JSON.stringify({
            run_id: signal.run_id,
            ticker: signal.ticker || paper.ticker,
            asset_type: signal.asset_type || paper.assetType,
            trade_date: signal.analysis_date,
            action: paper.replayAction,
            target_position_size: paper.replayTargetPositionSize,
            horizon_days: paper.replayHorizonDays,
            initial_cash: paper.initialCash,
            commission_rate: paper.commissionRate,
            slippage_rate: paper.slippageRate,
          }),
        });
        paper.replayAccount = payload.account;
        paper.replayAnalytics = payload.analytics || null;
        paper.replayResult = payload.result || null;
        await refreshPaperEpisodes();
        paper.replayLastUpdated = formatLocalTime(localTimestamp());
        logs.value.unshift(`[paper] 已按 ${signal.analysis_date} 历史真实数据完成回放模拟`);
      } catch (error) {
        paper.error = error.message;
        logs.value.unshift(`[paper] 历史回测失败: ${error.message}`);
      } finally {
        paper.loading = false;
      }
    }

    async function replayManualHistoricalPaper() {
      const ticker = String(paper.replayTicker || paper.ticker || "").trim().toUpperCase();
      const tradeDate = String(paper.replayTradeDate || "").trim().slice(0, 10);
      if (!ticker || !tradeDate) {
        paper.error = "请填写历史回测标的和日期";
        return;
      }
      paper.loading = true;
      paper.error = "";
      try {
        const payload = await fetchJson("/api/simulation/backtest/manual", {
          method: "POST",
          body: JSON.stringify({
            ticker,
            asset_type: looksLikeCryptoTicker(ticker) ? "crypto" : paper.assetType,
            trade_date: tradeDate,
            action: paper.replayAction,
            target_position_size: paper.replayTargetPositionSize,
            horizon_days: paper.replayHorizonDays,
            initial_cash: paper.initialCash,
            commission_rate: paper.commissionRate,
            slippage_rate: paper.slippageRate,
            thesis: paper.replayThesis,
          }),
        });
        paper.replayAccount = payload.account;
        paper.replayAnalytics = payload.analytics || null;
        paper.replayResult = payload.result || null;
        await refreshPaperEpisodes();
        paper.replayLastUpdated = formatLocalTime(localTimestamp());
        logs.value.unshift(`[paper] 已按 ${tradeDate} 手动历史数据完成回放模拟`);
      } catch (error) {
        paper.error = error.message;
        logs.value.unshift(`[paper] 手动历史回测失败: ${error.message}`);
      } finally {
        paper.loading = false;
      }
    }

    async function cancelSelectedTask(targetRunId = "") {
      const runId = targetRunId || selectedTaskView.value.run_id;
      if (!runId) {
        logs.value.unshift("[warning] 当前没有可取消的任务");
        return;
      }
      const existingIndex = taskHistory.value.findIndex((item) => item.run_id === runId);
      if (existingIndex >= 0) {
        const nextItem = {
          ...taskHistory.value[existingIndex],
          status: "cancelling",
          phase: "取消中...",
          cancel_requested: true,
          updated_at: localTimestamp(),
        };
        taskHistory.value.splice(existingIndex, 1, nextItem);
        persistTaskHistory();
      }
      if (runState.runId === runId) {
        runState.status = "cancelling";
        runState.phase = "取消中...";
        runState.running = true;
      }
      try {
        const response = await fetchJson("/api/cancel-run", {
          method: "POST",
          body: JSON.stringify({ user_id: userId, run_id: runId }),
        });
        if (response.run) {
          applyRunSnapshot(response.run);
        }
        logs.value.unshift("[system] 已发送取消任务请求");
      } catch (error) {
        const message = error.message || "";
        if (message.includes("run_not_found")) {
          const index = taskHistory.value.findIndex((item) => item.run_id === runId);
          if (index >= 0) {
            taskHistory.value.splice(index, 1, {
              ...taskHistory.value[index],
              status: "cancelled",
              phase: "已取消",
              cancel_requested: true,
              updated_at: localTimestamp(),
              result_summary: "服务已重启或任务不在当前进程内，已在本地历史中标记为取消。",
              result: {
                ...(taskHistory.value[index].result || {}),
                rating: "Cancelled",
                summary: "服务已重启或任务不在当前进程内，已在本地历史中标记为取消。",
              },
            });
            persistTaskHistory();
          }
          logs.value.unshift("[warning] 后端当前找不到该任务，已在本地历史中标记为已取消");
          return;
        }
        logs.value.unshift(`[warning] 取消任务失败: ${message}`);
      }
    }

    async function forceRestartWorkbench(targetRunId = "") {
      const runId = targetRunId || selectedTaskView.value.run_id || runState.runId;
      const message = [
        "强制重启会终止 Workbench 容器内当前所有运行中的任务。",
        "这相当于硬取消，可打断阻塞中的 LLM/数据请求。",
        "确认现在重启吗？",
      ].join("\n");
      if (!window.confirm(message)) {
        return;
      }
      if (runId) {
        const existingIndex = taskHistory.value.findIndex((item) => item.run_id === runId);
        if (existingIndex >= 0) {
          taskHistory.value.splice(existingIndex, 1, {
            ...taskHistory.value[existingIndex],
            status: "cancelled",
            phase: "Workbench 重启中",
            cancel_requested: true,
            updated_at: localTimestamp(),
            result_summary: "Workbench 已强制重启，当前阻塞任务已硬取消。",
            result: {
              ...(taskHistory.value[existingIndex].result || {}),
              rating: "Cancelled",
              summary: "Workbench 已强制重启，当前阻塞任务已硬取消。",
            },
          });
          persistTaskHistory();
        }
      }
      if (runState.running) {
        runState.status = "cancelled";
        runState.phase = "Workbench 重启中";
        runState.running = false;
      }
      logs.value.unshift("[system] 正在强制重启 Workbench，页面会在服务恢复后继续可用");
      try {
        const response = await fetchJson("/api/restart-workbench", {
          method: "POST",
          body: JSON.stringify({
            user_id: userId,
            run_id: runId,
            confirm: "RESTART_WORKBENCH",
          }),
        });
        if (response.run) {
          applyRunSnapshot(response.run);
        }
        backend.connected = false;
        window.setTimeout(checkHealth, 2500);
        window.setTimeout(loadServerHistory, 5000);
      } catch (error) {
        logs.value.unshift(`[warning] 强制重启请求返回异常，服务可能已在重启: ${error.message}`);
        backend.connected = false;
        window.setTimeout(checkHealth, 2500);
      }
    }

    const configPreview = computed(() => {
      return JSON.stringify(
        {
          user_id: userId,
          ticker: form.ticker,
          asset_type: form.assetType,
          analysis_date: form.analysisDate,
          analysis_lookback_days: form.analysisLookbackDays,
          output_language: effectiveOutputLanguage.value,
          analysts: form.analysts,
          llm_provider: effectiveProvider.value,
          backend_url: form.backendUrl || null,
          quick_think_llm: form.quickModel,
          deep_think_llm: form.deepModel,
          analysis_think_llm: form.analysisModel || null,
          debate_think_llm: form.debateModel || null,
          decision_think_llm: form.decisionModel || null,
          research_depth: form.researchDepth,
          parallel_analysts: form.parallelAnalysts,
          checkpoint_enabled: form.enableCheckpoint,
          benchmark_ticker: form.benchmarkTicker || null,
          google_thinking_level: effectiveProvider.value.startsWith("google") ? form.googleThinkingLevel : null,
          openai_reasoning_effort: effectiveProvider.value === "openai" ? form.openaiReasoningEffort : null,
          anthropic_effort: effectiveProvider.value === "anthropic" ? form.anthropicEffort : null,
          llm_timeout: Number(form.llmTimeout || 90),
          llm_max_retries: Number(form.llmMaxRetries || 2),
          save_report: form.saveReport,
          auto_display_report: form.autoDisplayReport,
          run_report_evaluation: form.runReportEvaluation,
          report_reference_path: form.reportReferencePath || null,
          report_topic: form.reportTopic || null,
          run_backtest: form.runBacktest,
          backtest_initial_capital: form.backtestInitialCapital,
          backtest_holding_days: form.backtestHoldingDays,
          run_alpha_mining: form.runAlphaMining,
          display_full_report: form.displayFullReport,
          ensure_api_key: form.ensureApiKey,
          api_key_env_name: form.ensureApiKey ? activeApiKeyEnv.value : null,
        },
        null,
        2
      );
    });

    function syncProviderRegion() {
      const regions = regionOptions.value;
      if (regions.length === 0) {
        form.providerRegion = "";
        form.llmProvider = form.llmProviderBase;
        form.backendUrl = providerDefaults[form.llmProvider] || "";
        form.apiKeyEnvName = activeApiKeyEnv.value;
        return;
      }

      const current = regions.find((item) => item.provider === form.llmProvider);
      const selected = current || regions[0];
      form.providerRegion = selected.label;
      form.llmProvider = selected.provider;
      form.backendUrl = selected.backendUrl;
      form.apiKeyEnvName = selected.apiKeyEnv;
    }

    function syncModels() {
      const quickChoices = selectedProviderQuickModels.value;
      const deepChoices = selectedProviderDeepModels.value;
      form.quickModel = quickChoices[0] || "";
      form.deepModel = deepChoices[0] || "";
      form.analysisModel = form.quickModel;
      form.debateModel = form.quickModel;
      form.decisionModel = form.deepModel;
    }

    function applyProviderBase(provider) {
      form.llmProviderBase = provider;
      syncProviderRegion();
      syncModels();
    }

    function applyRegion(providerKey) {
      const selected = regionOptions.value.find((item) => item.provider === providerKey);
      if (!selected) {
        return;
      }
      form.llmProvider = selected.provider;
      form.providerRegion = selected.label;
      form.backendUrl = selected.backendUrl;
      form.apiKeyEnvName = selected.apiKeyEnv;
      syncModels();
    }

    function applyTickerPreset(ticker) {
      form.ticker = ticker;
      if (looksLikeCryptoTicker(ticker)) {
        form.assetType = "crypto";
      } else {
        form.assetType = "stock";
      }
      logs.value.unshift(`[input] 已切换股票/币种为 ${ticker}`);
    }

    function applyResearchPreset(depth, options = {}) {
      const preset = {
        1: {
          analysisLookbackDays: 14,
          runBacktest: false,
          runAlphaMining: false,
          displayFullReport: false,
          llmTimeout: 90,
          llmMaxRetries: 1,
          label: "快速",
        },
        2: {
          analysisLookbackDays: 30,
          runBacktest: true,
          runAlphaMining: false,
          displayFullReport: true,
          llmTimeout: 150,
          llmMaxRetries: 2,
          label: "均衡",
        },
        3: {
          analysisLookbackDays: 60,
          runBacktest: true,
          runAlphaMining: true,
          displayFullReport: true,
          llmTimeout: 210,
          llmMaxRetries: 3,
          label: "深入",
        },
      }[Number(depth)] || null;
      if (!preset) {
        return;
      }

      form.researchDepth = Number(depth);
      form.analysisLookbackDays = preset.analysisLookbackDays;
      form.runBacktest = preset.runBacktest;
      form.runAlphaMining = preset.runAlphaMining;
      form.displayFullReport = preset.displayFullReport;
      form.llmTimeout = preset.llmTimeout;
      form.llmMaxRetries = preset.llmMaxRetries;

      if (!options.quiet) {
        logs.value.unshift(`[config] 已切换为${preset.label}模式`);
      }
    }

    function looksLikeCryptoTicker(ticker) {
      const symbol = String(ticker || "").trim().toUpperCase();
      return (
        cryptoTickerSet.has(symbol) ||
        symbol.endsWith("-USD") ||
        symbol.endsWith("-USDT") ||
        symbol.endsWith("-USDC")
      );
    }

    function toggleAnalyst(value) {
      if (form.analysts.includes(value)) {
        form.analysts = form.analysts.filter((item) => item !== value);
        return;
      }
      form.analysts = [...form.analysts, value];
    }

    function normalizeAnalystsForAssetType() {
      if (form.assetType === "crypto") {
        form.analysts = form.analysts.filter((item) => item !== "fundamentals");
        if (form.analysts.length === 0) {
          form.analysts = ["market", "social", "news"];
        }
        return;
      }
      if (form.analysts.length === 0) {
        form.analysts = ["market", "social", "news", "fundamentals"];
      }
    }

    function applyAuthSession(session) {
      userId = session.user_id || "";
      authState.checked = true;
      authState.authenticated = Boolean(session.authenticated);
      authState.username = session.username || "";
      authState.userId = session.user_id || "";
      authState.role = session.role || "user";
      authState.isAdmin = Boolean(session.is_admin);
      authState.password = "";
      authState.confirmPassword = "";
      authState.challengeAnswer = "";
      authState.sliderValue = 0;
      authState.sliderMoves = 0;
      authState.sliderStartedAt = 0;
      authState.error = "";
    }

    async function loadAuthChallenge() {
      try {
        const challenge = await fetchJson("/api/auth/challenge");
        authState.challengeId = challenge.challenge_id || "";
        authState.challengePrompt = challenge.prompt || "";
        authState.challengeTarget = Number(challenge.target_percent || 50);
        authState.challengeTolerance = Number(challenge.tolerance || 4);
        authState.challengeAnswer = "";
        authState.sliderValue = 0;
        authState.sliderMoves = 0;
        authState.sliderStartedAt = 0;
      } catch (error) {
        authState.error = "安全验证加载失败，请刷新页面。";
      }
    }

    function startAuthSlider() {
      authState.sliderStartedAt = Date.now();
      authState.sliderMoves = 0;
    }

    function updateAuthSlider() {
      if (!authState.sliderStartedAt) {
        authState.sliderStartedAt = Date.now();
      }
      authState.sliderMoves += 1;
    }

    async function checkAuthSession() {
      try {
        const session = await fetchJson("/api/auth/session");
        applyAuthSession(session);
        if (!session.authenticated) {
          await loadAuthChallenge();
        }
      } catch (error) {
        authState.checked = true;
        authState.authenticated = false;
        authState.error = "";
        await loadAuthChallenge();
      }
    }

    async function submitAuth() {
      authState.error = "";
      const username = authState.formUsername.trim();
      if (!username || !authState.password) {
        authState.error = "请输入用户名和密码。";
        return;
      }
      if (authState.mode === "register" && authState.password !== authState.confirmPassword) {
        authState.error = "两次输入的密码不一致。";
        return;
      }
      const sliderElapsed = authState.sliderStartedAt ? Date.now() - authState.sliderStartedAt : 0;
      if (Math.abs(Number(authState.sliderValue) - Number(authState.challengeTarget)) > Number(authState.challengeTolerance)) {
        authState.error = "请把滑块拖到目标区域。";
        await loadAuthChallenge();
        return;
      }

      authState.loading = true;
      try {
        const session = await fetchJson(`/api/auth/${authState.mode}`, {
          method: "POST",
          body: JSON.stringify({
            username,
            password: authState.password,
            challenge_id: authState.challengeId,
            challenge_answer: {
              value: Number(authState.sliderValue),
              elapsed_ms: sliderElapsed,
              moves: Number(authState.sliderMoves),
            },
          }),
        });
        applyAuthSession(session);
        logs.value.unshift(`[system] ${authState.username} 已登录`);
        await initializeWorkbench();
      } catch (error) {
        authState.error = extractErrorMessage(error.message);
        await loadAuthChallenge();
      } finally {
        authState.loading = false;
      }
    }

    async function logout() {
      try {
        await fetchJson("/api/auth/logout", {
          method: "POST",
          body: JSON.stringify({}),
        });
      } catch (error) {
        logs.value.unshift(`[warning] 退出登录请求失败: ${error.message}`);
      }
      userId = "";
      authState.authenticated = false;
      authState.username = "";
      authState.userId = "";
      authState.role = "user";
      authState.isAdmin = false;
      authState.password = "";
      authState.confirmPassword = "";
      authState.challengeAnswer = "";
      authState.sliderValue = 0;
      authState.sliderMoves = 0;
      authState.sliderStartedAt = 0;
      taskHistory.value = [];
      selectedTaskRunId.value = "";
      backend.connected = false;
      backend.mode = "standalone";
      logs.value.unshift("[system] 已退出登录");
      await loadAuthChallenge();
    }

    async function loadAdminUsers() {
      if (!authState.isAdmin) {
        return;
      }
      adminState.loading = true;
      adminState.error = "";
      try {
        const payload = await fetchJson("/api/admin/users");
        adminState.users = payload.items || [];
      } catch (error) {
        adminState.error = extractErrorMessage(error.message);
      } finally {
        adminState.loading = false;
      }
    }

    async function openUserAdmin() {
      adminState.open = true;
      await loadAdminUsers();
    }

    async function updateManagedUser(user, updates) {
      adminState.error = "";
      try {
        const payload = await fetchJson("/api/admin/users/update", {
          method: "POST",
          body: JSON.stringify({
            username: user.username,
            role: updates.role ?? user.role,
            disabled: updates.disabled ?? user.disabled,
            unlock: Boolean(updates.unlock),
          }),
        });
        adminState.users = payload.items || [];
      } catch (error) {
        adminState.error = extractErrorMessage(error.message);
      }
    }

    async function resetManagedPassword(user) {
      const newPassword = window.prompt(`为 ${user.username} 设置新密码（至少 8 位）`);
      if (!newPassword) {
        return;
      }
      if (newPassword.length < 8) {
        adminState.error = "新密码至少需要 8 位。";
        return;
      }
      adminState.error = "";
      try {
        const payload = await fetchJson("/api/admin/users/reset-password", {
          method: "POST",
          body: JSON.stringify({ username: user.username, new_password: newPassword }),
        });
        adminState.users = payload.items || [];
        logs.value.unshift(`[admin] 已重置 ${user.username} 的密码`);
      } catch (error) {
        adminState.error = extractErrorMessage(error.message);
      }
    }

    async function deleteManagedUser(user) {
      const confirmed = window.confirm(
        `确认彻底删除账号 ${user.username}？\n\n这会删除登录账号、所有会话、任务历史、缓存和报告文件，且不可恢复。`
      );
      if (!confirmed) {
        return;
      }
      adminState.error = "";
      try {
        const payload = await fetchJson("/api/admin/users/delete", {
          method: "POST",
          body: JSON.stringify({ username: user.username }),
        });
        adminState.users = payload.items || [];
        logs.value.unshift(`[admin] 已删除账号 ${user.username}`);
      } catch (error) {
        adminState.error = extractErrorMessage(error.message);
      }
    }

    function extractErrorMessage(message) {
      const raw = String(message || "");
      if (/<!doctype html|<html/i.test(raw)) {
        const codeMatch = raw.match(/Error code:\s*([0-9]+)/i) || raw.match(/<p>\s*Error code:\s*([0-9]+)\s*<\/p>/i);
        const messageMatch = raw.match(/Message:\s*([^<]+)/i) || raw.match(/<p>\s*Message:\s*([^<]+)\s*<\/p>/i);
        if (codeMatch || messageMatch) {
          const code = codeMatch ? codeMatch[1] : "";
          const text = messageMatch ? messageMatch[1].trim() : "接口返回了 HTML 错误页";
          return code ? `HTTP ${code}: ${text}` : text;
        }
        const cleanText = raw
          .replace(/<[^>]+>/g, " ")
          .replace(/\s+/g, " ")
          .trim();
        return cleanText || "请求返回了 HTML 错误页。";
      }
      try {
        const parsed = JSON.parse(raw);
        return parsed.message || parsed.error || message;
      } catch (error) {
        return raw || "请求失败。";
      }
    }

    function legacyApiFallbackUrl(url) {
      const raw = String(url || "");
      const [path, query = ""] = raw.split("?");
      const aliases = {
        "/api/observations": "/api/conclusions",
        "/api/observations/from-run": "/api/conclusions/from-run",
        "/api/observations/update": "/api/conclusions/update",
        "/api/observations/delete": "/api/conclusions/delete",
        "/api/simulation/forecast/account": "/api/paper/account",
        "/api/simulation/forecast/quote": "/api/paper/quote",
        "/api/simulation/forecast/signals": "/api/paper/signals",
        "/api/simulation/forecast/skills": "/api/paper/skills",
        "/api/simulation/forecast/analytics": "/api/paper/analytics",
        "/api/simulation/forecast/reset": "/api/paper/reset",
        "/api/simulation/forecast/order": "/api/paper/order",
        "/api/simulation/forecast/observe": "/api/forecast-observations",
        "/api/simulation/backtest/from-signal": "/api/paper/replay-signal",
        "/api/simulation/backtest/manual": "/api/paper/replay-manual",
        "/api/simulation/observation/intraday": "/api/paper/intraday",
        "/api/simulation/episodes": "/api/paper/episodes",
      };
      const fallbackPath = aliases[path];
      if (!fallbackPath) {
        return "";
      }
      return query ? `${fallbackPath}?${query}` : fallbackPath;
    }

    async function requestJson(url, options = {}) {
      const response = await fetch(url, {
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-TradingAgents-User": userId,
          ...(options.headers || {}),
        },
        ...options,
      });

      if (!response.ok) {
        const message = await response.text();
        if (response.status === 401 && !url.startsWith("/api/auth/")) {
          authState.authenticated = false;
        }
        const error = new Error(extractErrorMessage(message || `HTTP ${response.status}`));
        error.status = response.status;
        throw error;
      }

      return response.json();
    }

    async function fetchJson(url, options = {}) {
      try {
        return await requestJson(url, options);
      } catch (error) {
        const fallbackUrl = error.status === 404 ? legacyApiFallbackUrl(url) : "";
        if (!fallbackUrl) {
          throw error;
        }
        logs.value.unshift(`[compat] ${url} 返回 404，已切换旧接口 ${fallbackUrl}`);
        return requestJson(fallbackUrl, options);
      }
    }

    function applyRunSnapshot(snapshot) {
      if (!snapshot) {
        return;
      }

      runState.runId = snapshot.run_id || runState.runId;
      runState.phase = snapshot.phase || runState.phase;
      runState.progress = snapshot.progress ?? runState.progress;
      runState.elapsed = snapshot.elapsed || runState.elapsed;
      runState.status = snapshot.status || runState.status;
      runState.running = ["queued", "running", "cancelling"].includes(snapshot.status);

      if (Array.isArray(snapshot.logs) && snapshot.logs.length > 0) {
        logs.value = [...snapshot.logs].reverse();
      }

      if (snapshot.agent_status && typeof snapshot.agent_status === "object") {
        Object.keys(agentStatus).forEach((key) => delete agentStatus[key]);
        Object.assign(agentStatus, snapshot.agent_status);
      }
      if (snapshot.agent_outputs && typeof snapshot.agent_outputs === "object") {
        Object.keys(agentOutputs).forEach((key) => delete agentOutputs[key]);
        Object.assign(agentOutputs, snapshot.agent_outputs);
      }
      if (snapshot.report_sections && typeof snapshot.report_sections === "object") {
        Object.keys(reportSections).forEach((key) => delete reportSections[key]);
        Object.assign(reportSections, snapshot.report_sections);
        if (!reportSections[selectedReportSection.value]) {
          const firstKey = Object.keys(reportSections)[0];
          if (firstKey) {
            selectedReportSection.value = firstKey;
          }
        }
      }

      if (snapshot.result) {
        finalDecision.value = {
          rating: snapshot.result.rating || finalDecision.value.rating,
          confidence: snapshot.result.confidence ?? finalDecision.value.confidence,
          position: snapshot.result.position || finalDecision.value.position,
          summary: snapshot.result.summary || finalDecision.value.summary,
          decision_details: snapshot.result.decision_details || snapshot.result.details || finalDecision.value.decision_details || {},
        };
      }

      if (snapshot.attachments) {
        attachments.reportSaved = !!snapshot.attachments.report_saved;
        attachments.reportPath = snapshot.attachments.report_path || "";
        attachments.evaluationEnabled = !!snapshot.attachments.evaluation_enabled;
        attachments.evaluationSummary = snapshot.attachments.evaluation_summary || "";
        attachments.backtestEnabled = !!snapshot.attachments.backtest_enabled;
        attachments.backtestSummary = snapshot.attachments.backtest_summary || "";
        attachments.backtestDetail = Array.isArray(snapshot.attachments.backtest_detail)
          ? snapshot.attachments.backtest_detail
          : [];
        attachments.paperTradingEnabled = !!snapshot.attachments.paper_trading_enabled;
        attachments.paperTradingSummary = snapshot.attachments.paper_trading_summary || "";
        attachments.paperTradingDetail = Array.isArray(snapshot.attachments.paper_trading_detail)
          ? snapshot.attachments.paper_trading_detail
          : [];
        attachments.paperTradingConfig = snapshot.attachments.paper_trading_config || {};
        attachments.alphaMiningEnabled = !!snapshot.attachments.alpha_mining_enabled;
        attachments.alphaMiningSummary = snapshot.attachments.alpha_mining_summary || "";
        attachments.alphaMiningDetail = snapshot.attachments.alpha_mining_detail || null;
        attachments.factorRuntimeDetail = snapshot.attachments.factor_runtime_detail || null;
        attachments.dataDiagnostic = snapshot.attachments.data_diagnostic || "";
      }
      if (typeof snapshot.report_preview === "string") {
        reportPreview.value = snapshot.report_preview;
      }
      if (snapshot.metrics && typeof snapshot.metrics === "object") {
        Object.keys(runMetrics).forEach((key) => delete runMetrics[key]);
        Object.assign(runMetrics, snapshot.metrics);
      }
      checkpointState.enabled = !!snapshot.checkpoint_enabled;
      checkpointState.available = !!snapshot.checkpoint_available;
      checkpointState.hint = snapshot.resume_hint || "";
      upsertTaskHistory(snapshot);
    }

    function toggleAgentExpansion(agent) {
      expandedAgents[agent] = !expandedAgents[agent];
    }

    function snapshotForm() {
      const snapshot = JSON.parse(JSON.stringify(form));
      snapshot.apiKeyValue = "";
      snapshot.ensureApiKey = false;
      return snapshot;
    }

    function applyFormSnapshot(snapshot) {
      Object.assign(form, snapshot);
      syncProviderRegion();
      syncModels();
    }

    function loadDefaultParams() {
      try {
        const raw = localStorage.getItem(`tradingagents_workbench_default_params_v2_${userId}`);
        if (!raw) {
          return false;
        }
        const defaults = JSON.parse(raw);
        delete defaults.analysisDate;
        applyFormSnapshot(defaults);
        form.analysisDate = localDateInputValue();
        logs.value.unshift("[system] 已载入你的默认任务参数，分析日期使用今天");
        return true;
      } catch (error) {
        logs.value.unshift("[warning] 默认任务参数读取失败，已使用系统默认值");
        return false;
      }
    }

    function saveDefaultParams() {
      const defaults = snapshotForm();
      delete defaults.analysisDate;
      localStorage.setItem(
        `tradingagents_workbench_default_params_v2_${userId}`,
        JSON.stringify(defaults)
      );
      logs.value.unshift("[system] 已将当前任务参数设为默认，分析日期每天自动使用当天");
    }

    function clearDefaultParams() {
      localStorage.removeItem(`tradingagents_workbench_default_params_v2_${userId}`);
      logs.value.unshift("[system] 已清除自定义默认参数");
    }

    function loadPresetItems() {
      try {
        const raw = localStorage.getItem("tradingagents_workbench_presets");
        presetState.items = raw ? JSON.parse(raw) : [];
      } catch (error) {
        presetState.items = [];
      }
    }

    function persistPresetItems() {
      localStorage.setItem("tradingagents_workbench_presets", JSON.stringify(presetState.items));
    }

    function savePreset() {
      const name = presetState.name.trim();
      if (!name) {
        logs.value.unshift("[warning] 请先输入预设名称");
        return;
      }
      const entry = {
        name,
        savedAt: localTimestamp(),
        config: snapshotForm(),
      };
      const existingIndex = presetState.items.findIndex((item) => item.name === name);
      if (existingIndex >= 0) {
        presetState.items.splice(existingIndex, 1, entry);
      } else {
        presetState.items.unshift(entry);
      }
      persistPresetItems();
      presetState.selected = name;
      logs.value.unshift(`[system] 已保存参数预设: ${name}`);
    }

    function loadPreset() {
      const selected = presetState.items.find((item) => item.name === presetState.selected);
      if (!selected) {
        logs.value.unshift("[warning] 未找到要载入的预设");
        return;
      }
      applyFormSnapshot(selected.config);
      logs.value.unshift(`[system] 已载入参数预设: ${selected.name}`);
    }

    function deletePreset() {
      const selectedName = presetState.selected;
      if (!selectedName) {
        logs.value.unshift("[warning] 请先选择要删除的预设");
        return;
      }
      presetState.items = presetState.items.filter((item) => item.name !== selectedName);
      persistPresetItems();
      logs.value.unshift(`[system] 已删除参数预设: ${selectedName}`);
      presetState.selected = "";
    }

    async function deleteHistoryItem(runId, deleteArtifacts = false) {
      if (backend.connected) {
        try {
          await fetchJson("/api/delete-run", {
            method: "POST",
            body: JSON.stringify({ user_id: userId, run_id: runId, delete_artifacts: deleteArtifacts }),
          });
        } catch (error) {
          logs.value.unshift(`[warning] 服务端删除失败，仅删除本地记录: ${error.message}`);
        }
      }
      const nextItems = taskHistory.value.filter((item) => item.run_id !== runId);
      const wasSelected = selectedTaskRunId.value === runId;
      taskHistory.value = nextItems;
      persistTaskHistory();
      if (wasSelected) {
        selectedTaskRunId.value = nextItems[0]?.run_id || "";
      }
      delete expandedHistory[runId];
      logs.value.unshift(deleteArtifacts ? "[system] 已删除历史记录和服务端文件" : "[system] 已删除历史任务记录");
    }

    function toggleSection(sectionKey) {
      panelSections[sectionKey] = !panelSections[sectionKey];
    }

    async function copyAgentOutput(agent) {
      const text = agentOutputText(agent);
      if (!text) {
        logs.value.unshift(`[warning] ${agent} 当前没有可复制的输出`);
        return;
      }
      try {
        await navigator.clipboard.writeText(text);
        logs.value.unshift(`[system] 已复制 ${agent} 输出`);
      } catch (error) {
        logs.value.unshift(`[warning] 复制 ${agent} 输出失败`);
      }
    }

    function syncBackendQueue(meta = {}) {
      backend.runConcurrency = Number(meta.run_concurrency ?? backend.runConcurrency ?? 1);
      backend.activeRuns = Number(meta.active_runs ?? backend.activeRuns ?? 0);
      backend.queuedRuns = Number(meta.queued_runs ?? backend.queuedRuns ?? 0);
      backend.cancellingRuns = Number(meta.cancelling_runs ?? backend.cancellingRuns ?? 0);
      backend.availableSlots = Number(meta.available_slots ?? Math.max(0, backend.runConcurrency - backend.activeRuns));
    }

    async function refreshBackendMeta() {
      if (!backend.connected) {
        return;
      }
      try {
        const meta = await fetchJson("/api/meta");
        syncBackendQueue(meta);
      } catch (error) {
        logs.value.unshift(`[warning] 刷新执行槽状态失败: ${error.message}`);
      }
    }

    function refreshQueueAfterTerminal() {
      refreshBackendMeta();
      window.clearTimeout(window.__taQueueRefreshTimer1);
      window.clearTimeout(window.__taQueueRefreshTimer2);
      window.__taQueueRefreshTimer1 = window.setTimeout(refreshBackendMeta, 1500);
      window.__taQueueRefreshTimer2 = window.setTimeout(refreshBackendMeta, 5000);
    }

    async function detectBackend() {
      try {
        const meta = await fetchJson("/api/meta");
        backend.connected = true;
        backend.mode = meta.mode || "bridge";
        syncBackendQueue(meta);
        logs.value.unshift(`[system] 已连接本地服务端 (${backend.mode})，执行槽 ${backend.activeRuns}/${backend.runConcurrency}`);
        await loadWorkbenchSettings();
        await loadServerHistory();
      } catch (error) {
        backend.connected = false;
        backend.mode = "standalone";
        logs.value.unshift("[system] 未检测到后端服务，当前使用前端演示模式");
      }
    }

    async function fetchModelCatalog() {
      try {
        const payload = await fetchJson("/api/model-options");
        Object.keys(modelCatalog).forEach((key) => delete modelCatalog[key]);
        Object.assign(modelCatalog, payload);
        syncModels();
        logs.value.unshift("[system] 已从后端同步模型目录");
      } catch (error) {
        logs.value.unshift("[warning] 拉取模型目录失败，页面将保留当前默认模型");
      }
    }

    async function refreshModelsFromBackendUrl() {
      modelRefresh.loading = true;
      modelRefresh.error = "";
      try {
        const payload = await fetchJson("/api/discover-models", {
          method: "POST",
          body: JSON.stringify({
            provider: effectiveProvider.value,
            user_id: userId,
            backend_url: form.backendUrl || null,
            api_key_env_name: activeApiKeyEnv.value || null,
            api_key_value: form.ensureApiKey ? form.apiKeyValue : null,
          }),
        });
        modelCatalog[effectiveProvider.value] = payload;
        syncModels();
        modelRefresh.source = "remote";
        logs.value.unshift(`[system] 已根据 ${form.backendUrl} 刷新 ${effectiveProvider.value} 模型列表`);
      } catch (error) {
        modelRefresh.error = error.message;
        logs.value.unshift(`[warning] 远程刷新模型失败: ${error.message}`);
      } finally {
        modelRefresh.loading = false;
      }
    }

    let pollTimer = null;

    function scheduleTerminalRunReconcile(runId) {
      window.clearTimeout(window.__taTerminalSnapshotTimer);
      window.clearTimeout(window.__taTerminalHistoryTimer);
      window.__taTerminalSnapshotTimer = window.setTimeout(async () => {
        try {
          await refreshRunSnapshot(runId);
        } catch (error) {
          logs.value.unshift(`[warning] 终态快照确认失败: ${error.message}`);
        }
      }, 500);
      window.__taTerminalHistoryTimer = window.setTimeout(async () => {
        try {
          await loadServerHistory();
        } catch (error) {
          logs.value.unshift(`[warning] 终态历史同步失败: ${error.message}`);
        }
      }, 1800);
    }

    async function pollRun(runId) {
      if (!backend.connected || !runId) {
        return;
      }

      try {
        const snapshot = await refreshRunSnapshot(runId);
        if (snapshot && isTerminalRunStatus(snapshot.status)) {
          if (snapshot.status === "completed") {
            activeWorkbenchModule.value = "result";
            resetMainScroll();
          } else {
            showRunProgressTab();
          }
          window.clearInterval(pollTimer);
          pollTimer = null;
          refreshQueueAfterTerminal();
          scheduleTerminalRunReconcile(runId);
        }
      } catch (error) {
        const message = error.message || "";
        if (message.includes("run_not_found")) {
          const index = taskHistory.value.findIndex((item) => item.run_id === runId);
          if (index >= 0) {
            taskHistory.value.splice(index, 1, {
              ...taskHistory.value[index],
              status: "stale",
              phase: "服务已重启，任务状态需重新运行",
              result_summary: "后端当前进程找不到该任务，通常是服务重启或浏览器历史残留。",
              updated_at: localTimestamp(),
            });
            persistTaskHistory();
          }
          if (runState.runId === runId) {
            runState.status = "stale";
            runState.phase = "服务已重启，任务状态需重新运行";
            runState.running = false;
          }
          logs.value.unshift("[warning] 后端找不到该任务，已标记为已失效");
        } else {
          logs.value.unshift(`[error] 轮询任务失败: ${message}`);
        }
        window.clearInterval(pollTimer);
        pollTimer = null;
      }
    }

    function simulateRun() {
      if (!form.ticker.trim()) {
        logs.value.unshift("[error] 请先输入股票或币种代码");
        return;
      }

      runState.running = true;
      runState.status = "running";
      runState.phase = "初始化任务";
      runState.progress = 12;
      runState.elapsed = "00:03";
      showRunProgressTab();

        logs.value.unshift(`[run] 提交分析任务: ${form.ticker} @ ${form.analysisDate}`);
        logs.value.unshift(`[config] ${commandPreview.value}`);
        logs.value.unshift(`[config] Analyst execution: ${form.parallelAnalysts ? "parallel" : "serial"}`);
        logs.value.unshift(`[lang] 输出语言: ${effectiveOutputLanguage.value}`);

      attachments.reportSaved = form.saveReport;
      attachments.reportPath = form.saveReport ? `reports/${form.ticker}_${form.analysisDate}` : "";
      attachments.evaluationEnabled = form.runReportEvaluation;
      attachments.evaluationSummary = form.runReportEvaluation ? "将基于参考答案执行报告评估。" : "";
      attachments.backtestEnabled = form.runBacktest;
      attachments.backtestSummary = form.runBacktest
        ? `将使用初始资金 ${form.backtestInitialCapital}，持有天数 ${form.backtestHoldingDays}`
        : "";
      attachments.backtestDetail = [];
      attachments.alphaMiningEnabled = form.runAlphaMining;
      attachments.alphaMiningSummary = form.runAlphaMining ? "将在分析完成后更新因子库。" : "";
      attachments.alphaMiningDetail = null;
      attachments.factorRuntimeDetail = null;

      window.clearTimeout(window.__taRunTimer1);
      window.clearTimeout(window.__taRunTimer2);
      window.clearTimeout(window.__taRunTimer3);

      window.__taRunTimer1 = window.setTimeout(() => {
        runState.phase = "分析师团队并行执行";
        runState.progress = 42;
        runState.elapsed = "00:19";
        logs.value.unshift("[agent] Analyst Team 已开始抓取行情、新闻与情绪数据");
      }, 500);

      window.__taRunTimer2 = window.setTimeout(() => {
        runState.phase = "研究与风控讨论";
        runState.progress = 79;
        runState.elapsed = "00:44";
        logs.value.unshift("[debate] Bull / Bear Researcher 与 Risk Team 正在形成最终约束");
      }, 1100);

      window.__taRunTimer3 = window.setTimeout(() => {
        runState.phase = "完成";
        runState.status = "completed";
        runState.progress = 100;
        runState.elapsed = "01:09";
        runState.running = false;
        runState.runId = "demo-run";
        activeWorkbenchModule.value = "result";
        logs.value.unshift("[done] 本次分析流程已结束，等待你查看报告或再次调整参数");
      }, 1800);
    }

    async function runAnalysis() {
      if (!form.ticker.trim()) {
        logs.value.unshift("[error] 请先输入股票或币种代码");
        return;
      }

      if (looksLikeCryptoTicker(form.ticker)) {
        form.assetType = "crypto";
        normalizeAnalystsForAssetType();
      }

      if (!backend.connected) {
        simulateRun();
        return;
      }

      runState.running = true;
      runState.status = "queued";
      runState.phase = "任务提交中";
      runState.progress = 5;
      runState.elapsed = "00:00";
      attachments.alphaMiningEnabled = form.runAlphaMining;
      attachments.alphaMiningSummary = form.runAlphaMining ? "将在分析完成后更新因子库。" : "";
      attachments.alphaMiningDetail = null;
      attachments.factorRuntimeDetail = null;
      showRunProgressTab();

      try {
        const payload = {
          ticker: form.ticker,
          user_id: userId,
          asset_type: form.assetType,
          analysis_date: form.analysisDate,
          analysis_lookback_days: form.analysisLookbackDays,
          output_language: effectiveOutputLanguage.value,
          analysts: form.analysts,
          research_depth: form.researchDepth,
          parallel_analysts: form.parallelAnalysts,
          llm_provider: effectiveProvider.value,
          backend_url: form.backendUrl || null,
          quick_think_llm: form.quickModel,
          deep_think_llm: form.deepModel,
          analysis_think_llm: form.analysisModel || null,
          debate_think_llm: form.debateModel || null,
          decision_think_llm: form.decisionModel || null,
          checkpoint_enabled: form.enableCheckpoint,
          benchmark_ticker: form.benchmarkTicker || null,
          google_thinking_level: effectiveProvider.value === "google" ? form.googleThinkingLevel : null,
          openai_reasoning_effort: effectiveProvider.value === "openai" ? form.openaiReasoningEffort : null,
          anthropic_effort: effectiveProvider.value === "anthropic" ? form.anthropicEffort : null,
          llm_timeout: Number(form.llmTimeout || 90),
          llm_max_retries: Number(form.llmMaxRetries || 2),
          save_report: form.saveReport,
          auto_display_report: form.autoDisplayReport,
          run_report_evaluation: form.runReportEvaluation,
          report_reference_path: form.reportReferencePath || null,
          report_topic: form.reportTopic || null,
          run_backtest: form.runBacktest,
          backtest_initial_capital: form.backtestInitialCapital,
          backtest_holding_days: form.backtestHoldingDays,
          run_alpha_mining: form.runAlphaMining,
          display_full_report: form.displayFullReport,
          ensure_api_key: form.ensureApiKey,
          api_key_env_name: form.ensureApiKey ? activeApiKeyEnv.value : null,
          api_key_value: form.ensureApiKey ? form.apiKeyValue : null,
        };

        const created = await fetchJson("/api/runs", {
          method: "POST",
          body: JSON.stringify(payload),
        });

        applyRunSnapshot(created);
        selectedTaskRunId.value = created.run_id;
        logs.value.unshift(`[run] 已创建任务 ${created.run_id}`);

        window.clearInterval(pollTimer);
        pollTimer = window.setInterval(() => pollRun(created.run_id), 1200);
      } catch (error) {
        runState.running = false;
        runState.status = "failed";
        runState.phase = "提交失败";
        logs.value.unshift(`[error] 任务提交失败: ${error.message}`);
      }
    }

    function resetForm() {
      form.ticker = "BTC-USD";
      form.assetType = "crypto";
      form.analysisDate = localDateInputValue();
      form.outputLanguage = "Chinese";
      form.customLanguage = "";
      form.analysts = ["market", "social", "news"];
      form.parallelAnalysts = true;
      form.llmProviderBase = "qwen";
      form.llmProvider = "qwen-cn";
      form.providerRegion = "China";
      form.quickModel = "qwen3.6-flash";
      form.deepModel = "qwen3.6-plus";
      form.analysisModel = form.quickModel;
      form.debateModel = form.quickModel;
      form.decisionModel = form.deepModel;
      form.backendUrl = providerDefaults["qwen-cn"];
      form.benchmarkTicker = "";
      form.enableCheckpoint = true;
      form.saveReport = true;
      form.autoDisplayReport = true;
      form.runReportEvaluation = false;
      form.reportReferencePath = "";
      form.reportTopic = "";
      form.runBacktest = false;
      form.backtestInitialCapital = "100000";
      form.backtestHoldingDays = "5,10,20";
      form.runAlphaMining = false;
      form.googleThinkingLevel = "high";
      form.openaiReasoningEffort = "medium";
      form.anthropicEffort = "high";
      form.ensureApiKey = false;
      form.apiKeyValue = "";
      form.apiKeyEnvName = "DASHSCOPE_CN_API_KEY";
      applyResearchPreset(1, { quiet: true });
      logs.value.unshift("[system] 配置已重置为默认值");
      syncProviderRegion();
    }

    watch(
      () => form.assetType,
      () => {
        normalizeAnalystsForAssetType();
      }
    );

    watch(
      () => form.ticker,
      (ticker) => {
        if (looksLikeCryptoTicker(ticker) && form.assetType !== "crypto") {
          form.assetType = "crypto";
        }
      }
    );

    watch(
      () => effectiveProvider.value,
      () => {
        form.apiKeyEnvName = activeApiKeyEnv.value;
      }
    );

    watch(
      () => currentRunningAgent.value,
      (agent) => {
        if (!agent) {
          return;
        }
        Object.keys(expandedAgents).forEach((key) => {
          expandedAgents[key] = false;
        });
        expandedAgents[agent] = true;
      }
    );

    watch(
      () => paper.autoRefresh,
      () => {
        if (activeWorkbenchModule.value === "paper" || activeWorkbenchModule.value === "paper-future") {
          startPaperPolling();
        }
      }
    );

    watch(
      () => conclusions.selectedConclusionId,
      () => {
        if (activeWorkbenchModule.value === "conclusions") {
          refreshObservationIntraday({ quiet: true });
        }
      }
    );

    async function initializeWorkbench() {
      loadTaskHistory();
      if (taskHistory.value.length > 0) {
        selectedTaskRunId.value = taskHistory.value[0].run_id;
      }
      loadPresetItems();
      syncProviderRegion();
      loadDefaultParams();
      form.apiKeyEnvName = activeApiKeyEnv.value;
      await detectBackend();
      await fetchModelCatalog();
    }

    onMounted(async () => {
      await checkAuthSession();
      if (authState.authenticated) {
        await initializeWorkbench();
      }
    });

    onUnmounted(() => {
      stopPaperPolling();
      stopObservationPolling();
      window.clearInterval(pollTimer);
      window.clearTimeout(window.__taTerminalSnapshotTimer);
      window.clearTimeout(window.__taTerminalHistoryTimer);
    });

    return {
      activeApiKeyEnv,
      adminState,
      alphaLibrary,
      analysts,
      agentLabel,
      agentEmptyText,
      agentOutputText,
      applyProviderBase,
      applyRegion,
      applyResearchPreset,
      applyTickerPreset,
      attachments,
      agentStatus,
      agentOutputs,
      agentTeams,
      authState,
      backend,
      cancelSelectedTask,
      checkHealth,
      checkpointState,
      clearDefaultParams,
      addManualConclusion,
      addSelectedRunConclusion,
      conclusions,
	      conclusionStatusLabel,
	      scenarioLabel,
	      simulationStateLabel,
	      simulationTypeLabel,
	      copyAgentOutput,
      commandPreview,
      deleteManagedUser,
      deleteConclusion,
      downloadReport,
      exportAgentOutputs,
      exportCurrentConfig,
      exportLogs,
      forceRestartWorkbench,
      applyHistoryItem,
      deletePreset,
      deleteHistoryItem,
      eventLabel,
      configPreview,
      filteredLogs,
      formatLocalDateTime,
      currentDecisionDetails,
      currentRunningAgent,
      currentPaperSignals,
      decisionResult,
      effectiveOutputLanguage,
      finalDecision,
      formatEventTime,
      formatDecisionValue,
      localizeDecisionValue,
      decisionModeLabel,
      reportSectionLabel,
      formatAlphaValue,
      formatNumber,
      formatPercent,
      form,
      activeLogFilter,
      apiKeyStatusLabel,
      historySearch,
      hasDecisionResult,
      healthState,
      historicalPaperSignals,
      loadConclusions,
      loadAlphaLibrary,
      loadServerHistory,
      loadPreset,
      logs,
      nextPendingAgent,
      outputLanguages,
      paper,
      isPaperFutureModule,
      isPaperAccountModule,
      isPaperReplayModule,
      isPaperWorkbenchModule,
      paperChartOptions,
      paperConclusionTracks,
      paperEpisodeSummary,
      paperEpisodes,
      paperInterfaceDescription,
      paperInterfaceTitle,
      paperFills,
      paperLedgerFacetRows,
      paperLedgerTitle,
      paperModuleDescription,
      paperModuleTitle,
      paperChartTitle,
      paperPositions,
	      activeSimulationMeta,
	      activeSimulationSourceCounts,
	      activeSimulationSourceLabel,
	      activeSimulationScenarioRows,
	      activeSimulationSummary,
      scopedPaperEpisodes,
      observationTicker,
      observationIntradayChart,
      observationReturnChart,
      selectedConclusionTrack,
      recentPresetStocks,
      providerOptions,
      providerLabel,
      queueHint,
      reportPreview,
      reportSections,
      refreshModelsFromBackendUrl,
      regionOptions,
      resetManagedPassword,
      resetForm,
      activeWorkbenchModule,
      workflowSteps,
      workbenchModules,
      setWorkbenchModule,
      selectTask,
      selectedTask,
      selectedTaskRunId,
      selectedTaskView,
      rerunWithoutCheckpoint,
      rerunHistoryItem,
      retryLastRun,
      resetPaperAccount,
      refreshObservationIntraday,
      refreshPaperEpisodes,
      refreshPaperTrading,
      refreshPaperAnalytics,
      replayManualHistoricalPaper,
      updatePaperChartHover,
      clearPaperChartHover,
      updateObservationChartHover,
      clearObservationChartHover,
      submitPaperOrder,
      submitForecastObservation,
      reviewConclusion,
      applyPaperSignal,
      paperSignalSubmitLabel,
      runAnalysis,
      runMetrics,
      runState,
      savePreset,
      saveDefaultParams,
      saveHealthProtection,
      selectedProviderDeepModels,
      selectedProviderQuickModels,
      selectedProviderRoleModels,
      selectedReportSection,
      selectedResearchDepth,
      selectedAlphaDetail,
      selectedFactorDetail,
      selectedAlphaView,
      selectedBacktestDetail,
      selectedBacktestView,
      selectedPaperTradingView,
      selectedPaperSnapshots,
      selectedReplaySnapshots,
      paperChart,
      activePaperChart,
      statusLabel,
      startAuthSlider,
      submitAuth,
      updateManagedUser,
      updateAuthSlider,
      panelSections,
      presetState,
      showAllHistory,
      showAllAlphaHistory,
      showAllAlphaRegistry,
      taskHistory,
      expandedHistory,
      toggleHistoryExpansion,
      toggleSimpleMode,
      teamLabel,
      visibleTaskHistory,
      toggleSection,
      toggleAgentExpansion,
      toggleAnalyst,
      expandedAgents,
      simpleMode,
      modelRefresh,
      logout,
      openUserAdmin,
    };
  },
  template: `
    <div class="app-shell">
      <section v-if="!authState.checked" class="auth-shell auth-loading panel">
        <p class="eyebrow">TradingAgents Workbench</p>
        <h1>正在进入工作台</h1>
        <p>正在确认当前浏览器的会话状态。</p>
      </section>

      <section v-else-if="!authState.authenticated" class="auth-shell panel">
        <div class="auth-copy">
          <div class="auth-brand" aria-label="TradingAgents Workbench">
            <span>TRADINGAGENTS</span>
            <strong>WORKBENCH</strong>
          </div>
        </div>
        <form class="auth-form" @submit.prevent="submitAuth">
          <div class="auth-mode-toggle">
            <button
              type="button"
              :class="{ active: authState.mode === 'login' }"
              @click="authState.mode = 'login'; authState.error = ''"
            >
              登录
            </button>
            <button
              type="button"
              :class="{ active: authState.mode === 'register' }"
              @click="authState.mode = 'register'; authState.error = ''"
            >
              注册
            </button>
          </div>
          <label class="field">
            <span>用户名</span>
            <input v-model.trim="authState.formUsername" type="text" autocomplete="username" placeholder="例如 user">
          </label>
          <label class="field">
            <span>密码</span>
            <input v-model="authState.password" type="password" autocomplete="current-password" placeholder="至少 8 位">
          </label>
          <label v-if="authState.mode === 'register'" class="field">
            <span>确认密码</span>
            <input v-model="authState.confirmPassword" type="password" autocomplete="new-password" placeholder="再次输入密码">
          </label>
          <div class="slider-challenge">
            <div class="slider-challenge-head">
              <span>安全验证</span>
              <strong>{{ authState.challengePrompt || "加载中" }}</strong>
            </div>
            <div class="slider-track">
              <span
                class="slider-target"
                :style="{ left: authState.challengeTarget + '%', width: (authState.challengeTolerance * 2) + '%' }"
              ></span>
              <input
                v-model.number="authState.sliderValue"
                type="range"
                min="0"
                max="100"
                step="1"
                @pointerdown="startAuthSlider"
                @input="updateAuthSlider"
              >
            </div>
            <small>拖动到高亮目标区域后提交</small>
          </div>
          <p v-if="authState.error" class="auth-error">{{ authState.error }}</p>
          <button type="submit" class="primary-button auth-submit">
            {{ authState.loading ? "处理中..." : (authState.mode === "login" ? "登录" : "创建账号") }}
          </button>
        </form>
      </section>

      <template v-else>
      <main class="desk-shell" :class="{ 'simple-workspace': simpleMode }">
        <aside class="module-nav panel">
          <div class="module-nav-head">
            <div>
              <strong>TradingAgents</strong>
              <span>Research Desk</span>
            </div>
            <em>{{ simpleMode ? "简洁" : "高级" }}</em>
          </div>
          <div class="sidebar-system">
            <div class="sidebar-status">
              <span class="status-dot"></span>
              <strong>{{ backend.connected ? "后端已连接" : "演示模式" }}</strong>
            </div>
            <div class="sidebar-slots">
              <span>执行槽</span>
              <strong>{{ backend.activeRuns }}/{{ backend.runConcurrency }}</strong>
              <small>{{ backend.availableSlots }} 可用</small>
            </div>
          </div>
          <template v-for="module in workbenchModules" :key="module.id">
            <span v-if="module.groupStart" class="module-nav-group">{{ module.group }}</span>
            <button
              type="button"
              class="module-nav-item"
              :class="{ active: activeWorkbenchModule === module.id }"
              @click="setWorkbenchModule(module)"
            >
              <strong>{{ module.label }}</strong>
              <span>{{ module.desc }}</span>
            </button>
          </template>
        </aside>

        <section class="desk-main">
        <header class="topbar">
          <div class="topbar-copy">
            <strong>{{ (workbenchModules.find((item) => item.id === activeWorkbenchModule) || {}).label || "工作台" }}</strong>
            <span>{{ selectedTaskView.ticker || form.ticker }} · {{ statusLabel(selectedTaskView.status || "idle") }}</span>
          </div>
          <div class="topbar-meta">
            <button type="button" class="mode-switch-button" @click="toggleSimpleMode">
              {{ simpleMode ? "切到高级" : "切到简洁" }}
            </button>
            <button type="button" class="ghost-button mini" @click="checkHealth">健康检查</button>
            <div class="topbar-status user-chip">
              <span>用户</span>
              <strong>{{ authState.username }}</strong>
            </div>
            <button v-if="authState.isAdmin" type="button" class="ghost-button mini" @click="openUserAdmin">用户管理</button>
            <button type="button" class="ghost-button mini" @click="logout">退出</button>
            <div class="build-tag">UI Build 2026-07-20H</div>
          </div>
        </header>

        <section class="current-run-strip panel">
          <div class="current-run-main">
            <span class="run-phase" :class="{ live: selectedTaskView.status === 'queued' || selectedTaskView.status === 'running' || selectedTaskView.status === 'cancelling' }">
              {{ selectedTaskView.phase || "待运行" }}
            </span>
            <div>
              <strong>{{ selectedTaskView.ticker || form.ticker }}</strong>
              <small>{{ selectedTaskView.payload?.analysis_date || form.analysisDate }} · {{ statusLabel(selectedTaskView.status || "idle") }} · {{ selectedTaskView.elapsed || "00:00" }}</small>
            </div>
          </div>
          <div class="current-run-progress">
            <span>{{ selectedTaskView.progress || 0 }}%</span>
            <div class="progress-bar">
              <span :style="{ width: (selectedTaskView.progress || 0) + '%' }"></span>
            </div>
          </div>
          <div class="current-run-actions">
            <button
              v-if="selectedTaskView.status === 'queued' || selectedTaskView.status === 'running' || selectedTaskView.status === 'cancelling'"
              type="button"
              class="ghost-button mini danger-button"
              @click="cancelSelectedTask"
            >
              {{ selectedTaskView.status === 'cancelling' ? "取消中..." : "取消任务" }}
            </button>
          </div>
          <p v-if="queueHint" class="run-hint pinned-run-hint">{{ queueHint }}</p>
        </section>

        <section class="module-content" :class="'module-content-' + activeWorkbenchModule">
        <aside
          v-if="!simpleMode"
          v-show="activeWorkbenchModule === 'history' || activeWorkbenchModule === 'factors'"
          class="side-rail module-panel-full"
        >
          <section v-show="activeWorkbenchModule === 'history'" class="history-panel panel">
            <div class="panel-header">
              <div>
                <p class="eyebrow">Task History</p>
                <h2>任务历史</h2>
              </div>
              <button type="button" class="ghost-button" @click="toggleSection('history')">
                {{ panelSections.history ? "收起" : "展开" }}
              </button>
            </div>
            <div v-if="panelSections.history" class="history-list compact">
              <div class="history-toolbar">
                <label class="field full">
                  <span>搜索历史任务</span>
                  <input v-model="historySearch" type="text" placeholder="按股票/币种或 provider 搜索">
                </label>
                <button type="button" class="ghost-button mini" @click="showAllHistory = !showAllHistory">
                  {{ showAllHistory ? "只看最近 5 条" : "展开更多" }}
                </button>
                <button type="button" class="ghost-button mini" @click="loadServerHistory">
                  同步服务端
                </button>
              </div>
              <div
                v-for="item in visibleTaskHistory"
                :key="item.run_id"
                class="history-card"
                :class="{ failed: item.status === 'failed' || item.status === 'stale', cancelled: item.status === 'cancelled' || item.status === 'cancelling', selected: selectedTaskRunId === item.run_id }"
              >
                <button type="button" class="history-head clickable" @click="selectTask(item.run_id)">
                  <strong>{{ item.ticker }}</strong>
                  <div class="history-head-meta">
                    <em>{{ selectedTaskRunId === item.run_id ? "查看中" : "查看结果" }}</em>
                    <span :class="'status-' + (item.status || 'pending')">{{ statusLabel(item.status || 'pending') }}</span>
                  </div>
                </button>
                <p>{{ item.provider }} · {{ item.phase }}</p>
                <div class="history-date-row">
                  <small>分析日期 {{ item.payload?.analysis_date || "N/A" }}</small>
                  <small>运行时间 {{ formatLocalDateTime(item.updated_at) || "N/A" }}</small>
                </div>
                <small>{{ item.rating || "无评级" }}</small>
                <small :class="item.checkpoint_available ? 'resume-ok' : 'resume-bad'">
                  {{ item.checkpoint_available ? "可恢复" : "不可恢复" }}
                </small>
                <div class="history-actions">
                  <button type="button" class="ghost-button mini" @click="toggleHistoryExpansion(item.run_id)">{{ expandedHistory[item.run_id] ? "收起详情" : "展开详情" }}</button>
                  <button type="button" class="ghost-button mini" @click="applyHistoryItem(item)">回填参数</button>
                  <button type="button" class="ghost-button mini" @click="rerunHistoryItem(item)">重新运行</button>
                  <button type="button" class="ghost-button mini" @click="rerunWithoutCheckpoint(item)">清除重跑</button>
                  <button
                    v-if="['queued', 'running', 'cancelling', 'stale'].includes(item.status)"
                    type="button"
                    class="ghost-button mini danger-button"
                    @click="cancelSelectedTask(item.run_id)"
                  >
                    标记取消
                  </button>
                  <button type="button" class="ghost-button mini danger-button" @click="deleteHistoryItem(item.run_id, false)">删除记录</button>
                  <button type="button" class="ghost-button mini danger-button" @click="deleteHistoryItem(item.run_id, true)">删除文件</button>
                </div>
                <div v-if="expandedHistory[item.run_id]" class="history-detail">
                  <small>{{ item.report_path || "未保存报告" }}</small>
                  <small>{{ item.resume_hint || (item.checkpoint_enabled ? "Checkpoint 已开启" : "Checkpoint 未开启") }}</small>
                  <small>结构化事件 {{ (item.events || []).length }} 条</small>
                  <p>{{ item.result_summary || "当前没有更多历史内容摘要。" }}</p>
                  <pre v-if="item.payload">{{ JSON.stringify(item.payload, null, 2) }}</pre>
                </div>
              </div>
              <div v-if="!visibleTaskHistory.length" class="placeholder-block history-empty">
                <strong>暂无历史任务</strong>
                <p>{{ historySearch ? "没有匹配当前搜索条件的任务。" : "运行一次分析后，任务记录、报告和重跑入口会出现在这里。" }}</p>
              </div>
            </div>
          </section>

          <section v-show="activeWorkbenchModule === 'factors'" class="alpha-library-panel panel">
            <div class="panel-header">
              <div>
                <p class="eyebrow">Alpha Library</p>
                <h2>Alpha 因子库</h2>
              </div>
              <button type="button" class="ghost-button" @click="loadAlphaLibrary(form.ticker)">
                {{ alphaLibrary.loading ? "加载中..." : "查看当前股票" }}
              </button>
            </div>
            <div class="alpha-library-tools">
              <label class="field full">
                  <span>股票/币种代码</span>
                <input v-model="alphaLibrary.ticker" type="text" :placeholder="form.ticker">
              </label>
              <button type="button" class="primary-button compact" @click="loadAlphaLibrary(alphaLibrary.ticker || form.ticker)">查询因子</button>
            </div>
            <p v-if="alphaLibrary.error" class="inline-error">{{ alphaLibrary.error }}</p>
            <div v-if="alphaLibrary.data" class="alpha-library-body">
              <div class="alpha-library-meta">
                <small>{{ alphaLibrary.data.ticker || "ALL" }}</small>
                <small>history {{ alphaLibrary.data.summary?.history_count || 0 }}</small>
                <small>registry {{ alphaLibrary.data.summary?.registry_count || 0 }}</small>
              </div>
              <p class="alpha-library-hint">这里用于查看历史因子；实际参与任务决策的是执行链路里的 Factor Manager。</p>
            </div>
          </section>
        </aside>

        <section
          v-show="['run', 'params', 'agents', 'timeline', 'logs', 'result', 'report', 'conclusions', 'paper', 'paper-future', 'paper-replay'].includes(activeWorkbenchModule) || (simpleMode && activeWorkbenchModule === 'history')"
          class="work-column module-panel-main"
        >
          <section v-show="activeWorkbenchModule === 'run'" class="control-panel panel">
            <div class="panel-header">
              <div>
                <p class="eyebrow">{{ simpleMode ? "Quick Run" : "Run Config" }}</p>
                <h2>{{ simpleMode ? "新建分析" : "任务参数" }}</h2>
              </div>
              <div class="inline-actions">
                <button v-if="!simpleMode" class="ghost-button" @click="saveDefaultParams">设为默认</button>
                <button v-if="!simpleMode" class="ghost-button" @click="clearDefaultParams">清除默认</button>
                <button class="ghost-button" @click="resetForm">重置</button>
              </div>
            </div>

            <div v-if="simpleMode" class="simple-run-form">
              <div class="simple-mode-row">
                <button type="button" class="mode-card" :class="{ active: form.researchDepth === 1 }" @click="applyResearchPreset(1)">
                  <strong>快速分析</strong>
                  <span>14天 · 只出结论</span>
                </button>
                <button type="button" class="mode-card" :class="{ active: form.researchDepth === 2 }" @click="applyResearchPreset(2)">
                  <strong>均衡分析</strong>
                  <span>30天 · 回测校验</span>
                </button>
                <button type="button" class="mode-card" :class="{ active: form.researchDepth === 3 }" @click="applyResearchPreset(3)">
                  <strong>深入分析</strong>
                  <span>60天 · 回测+记录因子</span>
                </button>
              </div>

              <div class="simple-form-grid">
                <label class="field">
                  <span>股票/币种</span>
                  <input v-model="form.ticker" type="text" placeholder="例如 BTC-USD / NVDA / 0700.HK">
                </label>
                <label class="field">
                  <span>资产类型</span>
                  <select v-model="form.assetType">
                    <option value="crypto">加密货币</option>
                    <option value="stock">股票</option>
                  </select>
                </label>
                <label class="field">
                  <span>分析日期</span>
                  <input v-model="form.analysisDate" type="date">
                </label>
                <label class="field">
                  <span>输出语言</span>
                  <select v-model="form.outputLanguage">
                    <option value="Chinese">Chinese</option>
                    <option value="English">English</option>
                  </select>
                </label>
              </div>

              <div class="simple-run-summary">
                <span>{{ form.llmProvider }}</span>
                <span>Debate {{ form.debateModel || form.quickModel }}</span>
                <span>Decision {{ form.decisionModel || form.deepModel }}</span>
              </div>
            </div>

            <template v-else>
            <div class="section-banner">
              <div>
                <strong>Run Blueprint</strong>
                <p>先选股票/币种、模型与语言；模拟盘请在左侧独立模块中运行。</p>
              </div>
              <div class="banner-badges">
                <span>{{ form.assetType }}</span>
                <span>{{ form.researchDepth === 3 ? "Deep Research" : form.researchDepth === 2 ? "Balanced" : "Fast Pass" }}</span>
              </div>
            </div>

            <div class="config-overview">
              <article>
                <span>当前 Provider</span>
                <strong>{{ form.llmProvider }}</strong>
              </article>
              <article>
                <span>当前股票/币种</span>
                <strong>{{ form.ticker }}</strong>
              </article>
              <article>
                <span>当前模式</span>
                <strong>{{ form.assetType }}</strong>
              </article>
              <article>
                <span>输出语言</span>
                <strong>{{ effectiveOutputLanguage }}</strong>
              </article>
            </div>

            <div class="preset-manager compact-presets">
            <label class="field">
              <span>保存当前参数为预设</span>
              <input v-model="presetState.name" type="text" placeholder="例如 Qwen-NVDA-Deep">
            </label>
            <button type="button" class="ghost-button preset-button" @click="savePreset">保存预设</button>
            <label class="field">
              <span>载入已有预设</span>
              <select v-model="presetState.selected">
                <option value="">选择预设</option>
                <option v-for="item in presetState.items" :key="item.name" :value="item.name">
                  {{ item.name }}
                </option>
              </select>
            </label>
            <div class="preset-actions">
              <button type="button" class="ghost-button preset-button" @click="loadPreset">载入</button>
              <button type="button" class="ghost-button preset-button danger-button" @click="deletePreset">删除</button>
            </div>
          </div>

            <div class="preset-row">
            <span>常用股票/币种</span>
            <button
              v-for="ticker in recentPresetStocks"
              :key="ticker"
              type="button"
              class="chip"
              @click="applyTickerPreset(ticker)"
            >
              {{ ticker }}
            </button>
          </div>

            <div class="field-group grouped-block collapsible">
            <button type="button" class="section-toggle" @click="toggleSection('basic')">
              <span class="group-label">基础参数</span>
              <strong>{{ panelSections.basic ? "收起" : "展开" }}</strong>
            </button>
            <div v-if="panelSections.basic" class="form-grid">
            <label class="field">
              <span>股票/币种代码</span>
              <input v-model="form.ticker" type="text" placeholder="例如 NVDA / 0700.HK / BTC-USD">
            </label>

            <label class="field">
              <span>资产类型</span>
              <select v-model="form.assetType">
                <option value="stock">股票</option>
                <option value="crypto">加密货币</option>
              </select>
            </label>

            <label class="field">
              <span>分析日期</span>
              <input v-model="form.analysisDate" type="date">
            </label>

            <label class="field">
              <span>共享回看窗口</span>
              <select v-model.number="form.analysisLookbackDays">
                <option :value="7">7 days</option>
                <option :value="14">14 days</option>
                <option :value="30">30 days</option>
                <option :value="60">60 days</option>
                <option :value="90">90 days</option>
              </select>
            </label>

            <label class="field">
              <span>输出语言</span>
              <select v-model="form.outputLanguage">
                <option v-for="language in outputLanguages" :key="language" :value="language">
                  {{ language === "custom" ? "Custom language" : language }}
                </option>
              </select>
            </label>

            <label v-if="form.outputLanguage === 'custom'" class="field">
              <span>自定义语言</span>
              <input v-model="form.customLanguage" type="text" placeholder="例如 Turkish / Vietnamese / Thai">
            </label>

            <label class="field">
              <span>研究深度</span>
              <select v-model.number="form.researchDepth">
                <option :value="1">1 - Fast</option>
                <option :value="2">2 - Balanced</option>
                <option :value="3">3 - Deep</option>
              </select>
            </label>

            <label class="field full">
              <span>分析师执行模式</span>
              <select v-model="form.parallelAnalysts">
                <option :value="false">串行稳定版</option>
                <option :value="true">并行实验版（真实后端并行）</option>
              </select>
            </label>
            </div>
          </div>

            <div class="field-group grouped-block collapsible">
            <button type="button" class="section-toggle" @click="toggleSection('model')">
              <span class="group-label">模型与接口</span>
              <strong>{{ panelSections.model ? "收起" : "展开" }}</strong>
            </button>
            <div v-if="panelSections.model" class="form-grid">
            <label class="field">
              <span>LLM Provider</span>
              <select v-model="form.llmProviderBase" @change="applyProviderBase(form.llmProviderBase)">
                <option v-for="provider in providerOptions" :key="provider.value" :value="provider.value">
                  {{ provider.label }}
                </option>
              </select>
            </label>

            <label v-if="regionOptions.length" class="field">
              <span>区域 / 平台</span>
              <select v-model="form.llmProvider" @change="applyRegion(form.llmProvider)">
                <option v-for="option in regionOptions" :key="option.provider" :value="option.provider">
                  {{ option.label }}
                </option>
              </select>
            </label>

            <div class="field full model-refresh-banner">
              <span>模型刷新</span>
              <div class="inline-actions">
                <button
                  type="button"
                  class="primary-button compact"
                  :disabled="modelRefresh.loading"
                  @click="refreshModelsFromBackendUrl"
                >
                  {{ modelRefresh.loading ? "刷新中..." : "按当前 URL 刷新模型" }}
                </button>
                <small>当前 Provider: {{ form.llmProvider }}</small>
                <small>来源: {{ modelRefresh.source === "remote" ? "远程接口" : "本地目录" }}</small>
                <small v-if="modelRefresh.error" class="error-text">{{ modelRefresh.error }}</small>
              </div>
            </div>

            <label class="field">
              <span>Quick Model</span>
              <select v-model="form.quickModel">
                <option v-for="model in selectedProviderQuickModels" :key="model" :value="model">
                  {{ model }}
                </option>
              </select>
            </label>

            <label class="field">
              <span>Deep Model</span>
              <select v-model="form.deepModel">
                <option v-for="model in selectedProviderDeepModels" :key="model" :value="model">
                  {{ model }}
                </option>
              </select>
            </label>

            <label class="field">
              <span>分析师模型</span>
              <select v-model="form.analysisModel">
                <option value="">使用 Quick Model</option>
                <option v-for="model in selectedProviderRoleModels" :key="'analysis-' + model" :value="model">
                  {{ model }}
                </option>
              </select>
              <small>Market / Sentiment / News / Fundamentals</small>
            </label>

            <label class="field">
              <span>辩论/交易模型</span>
              <select v-model="form.debateModel">
                <option value="">使用 Quick Model</option>
                <option v-for="model in selectedProviderRoleModels" :key="'debate-' + model" :value="model">
                  {{ model }}
                </option>
              </select>
              <small>Bull / Bear / Trader / Risk Debaters</small>
            </label>

            <label class="field">
              <span>决策模型</span>
              <select v-model="form.decisionModel">
                <option value="">使用 Deep Model</option>
                <option v-for="model in selectedProviderRoleModels" :key="'decision-' + model" :value="model">
                  {{ model }}
                </option>
              </select>
              <small>Research Manager / Portfolio Manager</small>
            </label>

            <label class="field full">
              <span>Backend URL</span>
              <input v-model="form.backendUrl" type="text" placeholder="Provider endpoint or custom bridge URL">
            </label>

            <label class="field">
              <span>Benchmark</span>
              <input v-model="form.benchmarkTicker" type="text" placeholder="可留空自动推断">
            </label>

            <label class="field">
              <span>Checkpoint</span>
              <select v-model="form.enableCheckpoint">
                <option :value="true">enabled</option>
                <option :value="false">disabled</option>
              </select>
            </label>
            </div>
          </div>

            <div class="field-group grouped-block collapsible">
            <button type="button" class="section-toggle" @click="toggleSection('analysts')">
              <span class="group-label">Analysts Team</span>
              <strong>{{ panelSections.analysts ? "收起" : "展开" }}</strong>
            </button>
            <div v-if="panelSections.analysts" class="check-grid">
              <button
                v-for="item in analysts"
                :key="item.value"
                type="button"
                class="toggle-card"
                :class="{ active: form.analysts.includes(item.value), disabled: form.assetType === 'crypto' && item.value === 'fundamentals' }"
                :disabled="form.assetType === 'crypto' && item.value === 'fundamentals'"
                @click="toggleAnalyst(item.value)"
              >
                <strong>{{ item.label }}</strong>
                <small>{{ item.value }}</small>
              </button>
            </div>
          </div>

            <div class="field-group grouped-block collapsible">
            <button type="button" class="section-toggle" @click="toggleSection('provider')">
              <span class="group-label">Provider 专属推理设置</span>
              <strong>{{ panelSections.provider ? "收起" : "展开" }}</strong>
            </button>
            <div v-if="panelSections.provider" class="form-grid">
              <label v-if="form.llmProvider === 'google'" class="field">
                <span>Gemini Thinking Mode</span>
                <select v-model="form.googleThinkingLevel">
                  <option value="high">Enable Thinking</option>
                  <option value="minimal">Minimal / Disable</option>
                </select>
              </label>

              <label v-if="form.llmProvider === 'openai'" class="field">
                <span>OpenAI Reasoning Effort</span>
                <select v-model="form.openaiReasoningEffort">
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="low">Low</option>
                </select>
              </label>

              <label v-if="form.llmProvider === 'anthropic'" class="field">
                <span>Anthropic Effort</span>
                <select v-model="form.anthropicEffort">
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </label>

              <label class="field">
                <span>LLM 超时秒数</span>
                <input v-model.number="form.llmTimeout" type="number" min="15" max="600" step="5">
              </label>

              <label class="field">
                <span>失败重试次数</span>
                <input v-model.number="form.llmMaxRetries" type="number" min="0" max="5" step="1">
              </label>
            </div>
          </div>

            <div class="field-group grouped-block collapsible">
            <button type="button" class="section-toggle" @click="toggleSection('api')">
              <span class="group-label">API Key 辅助</span>
              <strong>{{ panelSections.api ? "收起" : "展开" }}</strong>
            </button>
            <div v-if="panelSections.api" class="form-grid">
              <label class="field">
                <span>是否尝试写入 .env</span>
                <select v-model="form.ensureApiKey">
                  <option :value="false">不写入</option>
                  <option :value="true">写入当前 provider 的 key</option>
                </select>
              </label>

              <label class="field">
                <span>目标环境变量</span>
                <input :value="activeApiKeyEnv" type="text" disabled>
              </label>

              <label v-if="form.ensureApiKey" class="field full">
                <span>API Key</span>
                <input v-model="form.apiKeyValue" type="password" placeholder="仅在你选择写入 .env 时提交">
              </label>
            </div>
          </div>

            <div class="field-group grouped-block collapsible">
            <button type="button" class="section-toggle" @click="toggleSection('extras')">
              <span class="group-label">运行后处理</span>
              <strong>{{ panelSections.extras ? "收起" : "展开" }}</strong>
            </button>
            <div v-if="panelSections.extras" class="switch-row">
              <label><input v-model="form.saveReport" type="checkbox"> 保存报告</label>
              <label><input v-model="form.autoDisplayReport" type="checkbox"> 自动打开报告</label>
              <label><input v-model="form.displayFullReport" type="checkbox"> 页面展示完整报告</label>
              <label><input v-model="form.runReportEvaluation" type="checkbox"> 运行报告评估</label>
              <label><input v-model="form.runBacktest" type="checkbox"> 运行 backtest</label>
              <label><input v-model="form.runAlphaMining" type="checkbox"> 完成后更新因子库</label>
            </div>

            <div v-if="panelSections.extras" class="form-grid feature-grid">
              <label v-if="form.runReportEvaluation" class="field full">
                <span>参考答案路径</span>
                <input v-model="form.reportReferencePath" type="text" placeholder="例如 reports/reference.md / answer.pdf">
              </label>

              <label v-if="form.runReportEvaluation" class="field full">
                <span>评估主题</span>
                <input v-model="form.reportTopic" type="text" placeholder="默认会使用 ticker + date">
              </label>

              <label v-if="form.runBacktest" class="field">
                <span>初始资金</span>
                <input v-model="form.backtestInitialCapital" type="text" placeholder="1.0">
              </label>

              <label v-if="form.runBacktest" class="field">
                <span>持有天数</span>
                <input v-model="form.backtestHoldingDays" type="text" placeholder="5,10,20">
              </label>

            </div>
          </div>
          </template>

            <div class="action-row" :class="{ 'simple-action-row': simpleMode }">
            <button class="primary-button" @click="runAnalysis">
              {{ runState.running ? "运行中..." : "开始分析" }}
            </button>
            <div v-if="!simpleMode" class="command-preview">
              <span>命令预览</span>
              <code>{{ commandPreview }}</code>
              <small>服务状态: {{ backend.connected ? "已连接后端" : "仅前端演示" }}</small>
            </div>
            </div>
          </section>

          <section v-if="simpleMode" v-show="activeWorkbenchModule === 'history'" class="simple-history-panel panel">
            <div class="panel-header">
              <div>
                <p class="eyebrow">Recent Runs</p>
                <h2>最近任务</h2>
              </div>
              <button type="button" class="ghost-button mini" @click="loadServerHistory">同步</button>
            </div>
            <div v-if="visibleTaskHistory.length" class="simple-history-list">
              <article
                v-for="item in visibleTaskHistory.slice(0, 5)"
                :key="item.run_id"
                class="simple-history-item"
                :class="{ selected: selectedTaskRunId === item.run_id }"
              >
                <button type="button" class="simple-history-main" @click="selectTask(item.run_id)">
                  <strong>{{ item.ticker || "未命名任务" }}</strong>
                  <span>{{ item.rating || statusLabel(item.status || "pending") }}</span>
                </button>
                <small>{{ item.payload?.analysis_date || "N/A" }} · {{ item.elapsed || "00:00" }}</small>
                <button type="button" class="ghost-button mini" @click="rerunHistoryItem(item)">重跑</button>
              </article>
            </div>
            <p v-else class="simple-empty">{{ historySearch ? "没有匹配当前搜索条件的任务。" : "完成后的任务会自动保存在这里。" }}</p>
          </section>
        </section>

        <section
          v-show="['agents', 'result', 'timeline', 'logs', 'report', 'conclusions', 'paper', 'paper-future', 'paper-replay', 'params'].includes(activeWorkbenchModule)"
          class="inspect-column module-panel-main"
        >
          <section class="result-panel">
          <article v-show="activeWorkbenchModule !== 'agents'" class="panel selection-banner">
            <div class="selection-banner-copy">
              <span>当前查看任务</span>
              <strong>{{ selectedTaskView.ticker || form.ticker }}</strong>
              <small>{{ selectedTaskView.payload?.analysis_date || form.analysisDate }} · {{ statusLabel(selectedTaskView.status || "idle") }}</small>
            </div>
            <div v-if="!simpleMode" class="selection-banner-meta">
              <span>{{ selectedTaskView.payload?.llm_provider || form.llmProvider }}</span>
              <span>{{ selectedTaskRunId ? "历史/当前任务视图" : "当前实时任务" }}</span>
            </div>
          </article>

          <article v-if="!simpleMode" v-show="activeWorkbenchModule === 'agents'" class="panel agent-card">
            <div class="panel-header">
              <div>
                <p class="eyebrow">Agent Status</p>
                <h2>执行编排</h2>
              </div>
              <span class="run-phase">
                分析师执行：{{ selectedTaskView.analyst_execution_mode === "parallel" ? "并行" : "串行" }}
              </span>
            </div>
            <div class="agent-groups">
              <div v-for="group in agentTeams" :key="group.team" class="agent-group">
                <h3>{{ teamLabel(group.team) }}</h3>
                <div class="agent-list">
                  <div v-for="agent in group.agents" :key="agent" class="agent-accordion">
                    <button
                      type="button"
                      class="agent-item"
                      :class="{ running: currentRunningAgent === agent, next: !currentRunningAgent && nextPendingAgent === agent }"
                      @click="toggleAgentExpansion(agent)"
                    >
                      <span>{{ agentLabel(agent) }}</span>
                      <div class="agent-item-meta">
                        <em>{{ expandedAgents[agent] ? "收起" : "展开" }}</em>
                        <strong :class="'status-' + ((selectedTaskView.agent_status || {})[agent] || 'pending')">
                          {{ statusLabel((selectedTaskView.agent_status || {})[agent] || 'pending') }}
                        </strong>
                      </div>
                    </button>
                    <div v-if="expandedAgents[agent]" class="agent-output">
                      <div class="agent-output-toolbar">
                        <span>{{ agentLabel(agent) }} 输出</span>
                        <button type="button" class="ghost-button mini" @click.stop="copyAgentOutput(agent)">复制输出</button>
                      </div>
                      <pre v-if="agentOutputText(agent)">{{ agentOutputText(agent) }}</pre>
                      <p v-else>{{ agentEmptyText(agent) }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </article>

          <article
            v-show="['result', 'timeline', 'logs', 'report', 'conclusions', 'paper', 'paper-future', 'paper-replay', 'params'].includes(activeWorkbenchModule)"
            class="panel"
          >
            <div v-if="activeWorkbenchModule === 'params'" class="config-preview">
              <div class="result-toolbar">
                <button type="button" class="ghost-button" @click="exportCurrentConfig">导出参数 JSON</button>
              </div>
              <pre>{{ configPreview }}</pre>
            </div>

            <div v-else-if="activeWorkbenchModule === 'logs'" class="log-list">
              <div class="log-filters">
                <button type="button" class="tab-button" :class="{ active: activeLogFilter === 'all' }" @click="activeLogFilter = 'all'">全部</button>
                <button type="button" class="tab-button" :class="{ active: activeLogFilter === 'error' }" @click="activeLogFilter = 'error'">error</button>
                <button type="button" class="tab-button" :class="{ active: activeLogFilter === 'stage' }" @click="activeLogFilter = 'stage'">stage</button>
                <button type="button" class="tab-button" :class="{ active: activeLogFilter === 'agent' }" @click="activeLogFilter = 'agent'">agent</button>
                <button type="button" class="tab-button" :class="{ active: activeLogFilter === 'data' }" @click="activeLogFilter = 'data'">data</button>
                <button type="button" class="ghost-button mini" @click="exportLogs">导出日志</button>
              </div>
              <div
                v-for="(line, index) in filteredLogs"
                :key="typeof line === 'string' ? line + index : (line.text || '') + index"
                class="log-line"
                :class="'log-' + (typeof line === 'string' ? 'system' : (line.kind || 'system'))"
              >
                <template v-if="typeof line === 'string'">{{ line }}</template>
                <template v-else>
                  <span class="log-kind">{{ line.kind }}</span>
                  <span>{{ line.text }}</span>
                </template>
              </div>
            </div>

            <div v-else-if="activeWorkbenchModule === 'timeline'" class="timeline-list">
              <div class="section-title-row">
                <div>
                  <h3>运行时间线</h3>
                  <p>按结构化事件展示任务创建、阶段切换、Agent 完成、取消或错误。</p>
                </div>
                <span class="run-phase">{{ (selectedTaskView.events || []).length }} events</span>
              </div>
              <div v-if="(selectedTaskView.events || []).length" class="timeline-items">
                <article
                  v-for="(event, index) in selectedTaskView.events"
                  :key="event.ts + event.kind + index"
                  class="timeline-item"
                  :class="'timeline-' + (event.kind || 'log')"
                >
                  <div class="timeline-dot"></div>
                  <div class="timeline-main">
                    <div class="timeline-head">
                      <strong>{{ eventLabel(event.kind) }}</strong>
                      <span>{{ formatEventTime(event.ts) }}</span>
                    </div>
                    <p>{{ event.message }}</p>
                    <small v-if="event.phase">{{ event.phase }} · {{ event.progress || 0 }}%</small>
                  </div>
                </article>
              </div>
              <div v-else class="placeholder-block">
                <strong>暂无结构化事件</strong>
                <p>新版本任务会自动保存运行时间线；旧历史任务可能只有普通日志。</p>
              </div>
            </div>

            <div v-else-if="activeWorkbenchModule === 'result'" class="decision-card">
              <div class="result-toolbar">
                <button
                  v-if="selectedTaskView.status === 'queued' || selectedTaskView.status === 'running' || selectedTaskView.status === 'cancelling'"
                  type="button"
                  class="ghost-button danger-button"
                  @click="cancelSelectedTask"
                >
                  {{ selectedTaskView.status === 'cancelling' ? "取消中..." : "取消任务" }}
                </button>
                <button
                  v-if="selectedTaskView.status === 'queued' || selectedTaskView.status === 'running' || selectedTaskView.status === 'cancelling'"
                  type="button"
                  class="ghost-button restart-button"
                  @click="forceRestartWorkbench"
                  title="硬取消：重启 Workbench 进程以终止阻塞中的 LLM/数据调用"
                >
                  强制重启
                </button>
                <button type="button" class="ghost-button" @click="retryLastRun">重试当前任务</button>
                <button type="button" class="ghost-button" @click="exportAgentOutputs">导出 Agent 输出</button>
              </div>
              <div class="checkpoint-banner" :class="{ available: checkpointState.available }">
                <strong>{{ checkpointState.enabled ? "Checkpoint 已开启" : "Checkpoint 未开启" }}</strong>
                <p>{{ checkpointState.hint || "当前没有可用的恢复信息。" }}</p>
              </div>
              <div class="workflow-strip">
                <article
                  v-for="step in workflowSteps"
                  :key="step.label"
                  class="workflow-step"
                  :class="'workflow-' + step.status"
                >
                  <strong>{{ step.label }}</strong>
                  <span>{{ statusLabel(step.status === 'idle' ? 'pending' : step.status) }}</span>
                  <p>{{ step.desc }}</p>
                </article>
              </div>
              <div v-if="!simpleMode" class="metrics-strip">
                <article>
                  <span>日志条数</span>
                <strong>{{ (selectedTaskView.metrics || {}).log_count || 0 }}</strong>
                </article>
                <article>
                  <span>已完成 Agent</span>
                <strong>{{ (selectedTaskView.metrics || {}).completed_agents || 0 }}</strong>
                </article>
                <article>
                  <span>运行中 Agent</span>
                <strong>{{ (selectedTaskView.metrics || {}).in_progress_agents || 0 }}</strong>
                </article>
                <article>
                  <span>报告分段</span>
                <strong>{{ (selectedTaskView.metrics || {}).report_section_count || 0 }}</strong>
                </article>
                <article>
                  <span>LLM 调用</span>
                <strong>{{ ((selectedTaskView.metrics || {}).runtime || {}).llm_calls || 0 }}</strong>
                </article>
                <article>
                  <span>Tool 调用</span>
                <strong>{{ ((selectedTaskView.metrics || {}).runtime || {}).tool_calls || 0 }}</strong>
                </article>
                <article>
                  <span>Tokens</span>
                <strong>{{ (((selectedTaskView.metrics || {}).runtime || {}).tokens_in || 0) + (((selectedTaskView.metrics || {}).runtime || {}).tokens_out || 0) }}</strong>
                </article>
                <article>
                  <span>数据源 Fallback</span>
                <strong>{{ ((selectedTaskView.metrics || {}).runtime || {}).vendor_fallbacks || 0 }}</strong>
                </article>
              </div>
              <div v-if="Object.keys(selectedFactorDetail || {}).length" class="factor-runtime-panel">
                <div class="section-title-row">
                  <div>
                    <h3>本次决策前因子评分</h3>
                    <p>Factor Manager 在 Trader 前读取历史因子库，并结合当前分析生成 factor_score。</p>
                  </div>
                  <span class="run-phase">参与本次决策</span>
                </div>
                <div class="metric-strip">
                  <div>
                    <span>Composite</span>
                    <strong>{{ formatNumber(selectedFactorDetail.composite_score, 4) }}</strong>
                  </div>
                  <div>
                    <span>Alpha Signal</span>
                    <strong>{{ formatNumber(selectedFactorDetail.signal_score, 4) }}</strong>
                  </div>
                  <div>
                    <span>Confidence</span>
                    <strong>{{ formatPercent(selectedFactorDetail.confidence) }}</strong>
                  </div>
                </div>
                <p>{{ selectedFactorDetail.selected_alpha?.name ? "选中因子: " + selectedFactorDetail.selected_alpha.name : "本次没有命名的 selected_alpha。" }}</p>
              </div>
              <div v-if="!hasDecisionResult" class="placeholder-block decision-empty">
                <strong>等待分析结果</strong>
                <p>{{ decisionResult.summary }}</p>
              </div>
              <template v-else>
              <div class="decision-head">
                <div>
                  <span class="decision-label">组合决策</span>
                  <h3>{{ localizeDecisionValue(decisionResult.rating) }}</h3>
                </div>
                <div class="confidence-ring">
                  <strong>{{ Math.round((decisionResult.confidence || 0) * 100) }}</strong>
                  <span>置信度</span>
                </div>
              </div>
              <div class="decision-grid">
                <article>
                  <span>建议仓位</span>
                  <strong>{{ localizeDecisionValue(decisionResult.position) }}</strong>
                </article>
                <article>
                  <span>输出语言</span>
                  <strong>{{ effectiveOutputLanguage }}</strong>
                </article>
                <article>
                  <span>研究深度</span>
                  <strong>{{ decisionModeLabel(selectedResearchDepth) }}</strong>
                </article>
              </div>
              <div class="decision-detail-panel">
                <article v-if="currentDecisionDetails.executive_summary" class="decision-detail-card full">
                  <span>核心结论</span>
                  <p>{{ currentDecisionDetails.executive_summary }}</p>
                </article>
                <article v-if="currentDecisionDetails.investment_thesis" class="decision-detail-card full">
                  <span>投资逻辑</span>
                  <p>{{ currentDecisionDetails.investment_thesis }}</p>
                </article>
                <article v-if="currentDecisionDetails.price_target" class="decision-detail-card">
                  <span>目标价</span>
                  <strong>{{ formatDecisionValue(currentDecisionDetails.price_target) }}</strong>
                </article>
                <article v-if="currentDecisionDetails.time_horizon" class="decision-detail-card">
                  <span>观察周期</span>
                  <strong>{{ localizeDecisionValue(currentDecisionDetails.time_horizon) }}</strong>
                </article>
                <article
                  v-if="currentDecisionDetails.target_position_size !== undefined && currentDecisionDetails.target_position_size !== null && currentDecisionDetails.target_position_size !== ''"
                  class="decision-detail-card"
                >
                  <span>目标仓位</span>
                  <strong>{{ formatDecisionValue(currentDecisionDetails.target_position_size, "position") }}</strong>
                </article>
                <article v-if="currentDecisionDetails.risk_gate_status" class="decision-detail-card">
                  <span>风控状态</span>
                  <strong>{{ localizeDecisionValue(currentDecisionDetails.risk_gate_status) }}</strong>
                </article>
              </div>
              <p
                v-if="!currentDecisionDetails.executive_summary && !currentDecisionDetails.investment_thesis"
                class="decision-summary-text"
              >{{ decisionResult.summary }}</p>
              <div v-if="(selectedTaskView.attachments || {}).evaluation_enabled" class="decision-evaluation-panel">
                <span>报告评估</span>
                <strong>{{ (selectedTaskView.attachments || {}).evaluation_summary || "等待评估结果" }}</strong>
              </div>
              <div v-if="(selectedTaskView.attachments || {}).data_diagnostic" class="error-diagnostic data-diagnostic">
                <strong>数据诊断 / 处理意见</strong>
                <p>{{ (selectedTaskView.attachments || {}).data_diagnostic }}</p>
              </div>
              <div v-if="selectedTaskView.status === 'failed'" class="error-diagnostic">
                <strong>错误诊断</strong>
                <p>{{ decisionResult.summary }}</p>
              </div>
              </template>
            </div>

            <div v-else-if="activeWorkbenchModule === 'report'" class="report-preview">
              <div class="section-title-row">
                <div>
                  <h3>报告预览</h3>
                  <p>这里展示当前任务返回的报告正文预览。</p>
                </div>
                <button
                  type="button"
                  class="ghost-button"
                  :disabled="!(selectedTaskView.attachments || {}).report_saved"
                  @click="downloadReport"
                >
                  下载完整报告
                </button>
              </div>
              <div v-if="Object.keys(selectedTaskView.report_sections || {}).length" class="report-section-nav">
                <label class="field full">
                  <span>章节跳转</span>
                  <select v-model="selectedReportSection">
                    <option v-for="section in Object.keys(selectedTaskView.report_sections || {})" :key="section" :value="section">
                      {{ reportSectionLabel(section) }}
                    </option>
                  </select>
                </label>
                <div class="report-section-card">
                  <strong>{{ reportSectionLabel(selectedReportSection) }}</strong>
                  <pre>{{ (selectedTaskView.report_sections || {})[selectedReportSection] }}</pre>
                </div>
              </div>
              <div class="placeholder-block">
                <strong>{{ selectedTaskView.ticker || form.ticker }}</strong>
                <span>{{ selectedTaskView.payload?.analysis_date || form.analysisDate }}</span>
                <p v-if="selectedTaskView.report_preview">{{ selectedTaskView.report_preview }}</p>
                <p v-else>任务完成后会在这里显示 complete_report.md 的预览内容。</p>
              </div>
            </div>

            <div v-else-if="activeWorkbenchModule === 'conclusions'" class="conclusion-dashboard">
              <section class="conclusion-main-panel">
                <div class="section-title-row">
                  <div>
                    <h3>长期观察</h3>
                    <p>统一管理推演模拟盘、历史回测、纸面账户和真实行情的复盘对照。</p>
                  </div>
                  <div class="inline-actions">
                    <button type="button" class="ghost-button mini" :disabled="conclusions.loading" @click="loadConclusions">
                      {{ conclusions.loading ? "刷新中" : "刷新结论" }}
                    </button>
                    <button type="button" class="primary-button compact" :disabled="!selectedTaskView.run_id" @click="addSelectedRunConclusion">
                      当前任务入池
                    </button>
                  </div>
                </div>
                <div v-if="conclusions.error" class="error-diagnostic">
                  <strong>研究跟踪盘错误</strong>
                  <p>{{ conclusions.error }}</p>
                </div>
                <div class="refresh-policy-strip">
                  <span><b>收益对照曲线</b>随结论同步刷新</span>
                  <span><b>结论列表 / 生命周期</b>5 分钟自动同步</span>
                  <span><b>Agent 重新分析</b>手动触发</span>
                </div>
                <div class="paper-account-summary">
                  <article>
                    <span>结论总数</span>
                    <strong>{{ conclusions.summary?.track_total || 0 }}</strong>
                  </article>
                  <article>
                    <span>跟踪中</span>
                    <strong>{{ conclusions.summary?.status_counts?.tracking || 0 }}</strong>
                  </article>
                  <article>
                    <span>待复盘</span>
                    <strong>{{ conclusions.summary?.status_counts?.due_review || 0 }}</strong>
                  </article>
                  <article>
                    <span>正收益率</span>
                    <strong>{{ formatPercent(conclusions.summary?.positive_return_rate) }}</strong>
                  </article>
                  <article>
                    <span>结论同步</span>
                    <strong>{{ conclusions.lifecycleLastUpdated || "未同步" }}</strong>
                  </article>
                </div>
                <div class="paper-chart-card observation-chart-card">
                  <div class="paper-chart-head">
                    <strong>{{ observationTicker || "N/A" }} 收益对照曲线</strong>
                    <div class="chart-range-tools">
                      <select v-model="conclusions.chartRange" aria-label="长期观察曲线范围">
                        <option value="today">今天</option>
                        <option value="7d">近 7 天</option>
                        <option value="30d">近 30 天</option>
                        <option value="all">全部</option>
                        <option value="custom">自定义</option>
                      </select>
                      <input v-if="conclusions.chartRange === 'custom'" v-model="conclusions.chartStartDate" type="date" aria-label="长期观察开始日期">
                      <input v-if="conclusions.chartRange === 'custom'" v-model="conclusions.chartEndDate" type="date" aria-label="长期观察结束日期">
                      <button type="button" class="ghost-button mini" :disabled="conclusions.quoteLoading" @click="refreshObservationIntraday">
                        {{ conclusions.quoteLoading ? "刷新中" : "刷新价格" }}
                      </button>
                    </div>
                  </div>
                  <div class="paper-live-metrics observation-live-metrics">
                    <article>
                      <span>最新价</span>
                      <strong>{{ formatNumber(conclusions.quote?.price, 4) }}</strong>
                      <small>{{ conclusions.quote?.as_of || "N/A" }}</small>
                    </article>
                    <article>
                      <span>当日变化</span>
                      <strong>{{ formatPercent(conclusions.quote?.change_percent) }}</strong>
                      <small>{{ formatNumber(conclusions.quote?.change, 4) }}</small>
                    </article>
                    <article>
                      <span>选中结论</span>
                      <strong>{{ selectedConclusionTrack?.rating || selectedConclusionTrack?.action || "N/A" }}</strong>
                      <small>{{ observationReturnChart.series[0]?.pointItems?.length || 0 }} points</small>
                    </article>
                  </div>
                  <svg
                    viewBox="0 0 700 280"
                    role="img"
                    aria-label="长期观察收益对照曲线"
                    @mousemove="updateObservationChartHover"
                    @mouseleave="clearObservationChartHover"
                  >
                    <line
                      v-for="tick in observationReturnChart.axis.yTicks"
                      :key="'observe-grid-' + tick.y"
                      :x1="observationReturnChart.axis.x1"
                      :y1="tick.y"
                      :x2="observationReturnChart.axis.x2"
                      :y2="tick.y"
                      class="paper-grid-line"
                    ></line>
                    <line :x1="observationReturnChart.axis.x1" :y1="observationReturnChart.axis.y2" :x2="observationReturnChart.axis.x2" :y2="observationReturnChart.axis.y2" class="paper-axis"></line>
                    <line :x1="observationReturnChart.axis.x1" :y1="observationReturnChart.axis.y1" :x2="observationReturnChart.axis.x1" :y2="observationReturnChart.axis.y2" class="paper-axis"></line>
                    <text
                      v-for="tick in observationReturnChart.axis.yTicks"
                      :key="'observe-ytick-' + tick.y"
                      :x="observationReturnChart.axis.x1 - 8"
                      :y="tick.y + 4"
                      text-anchor="end"
                      class="paper-axis-label"
                    >{{ tick.label }}</text>
                    <text
                      v-for="label in observationReturnChart.axis.xLabels"
                      :key="'observe-xlabel-' + label.x + label.label"
                      :x="label.x"
                      :y="observationReturnChart.axis.y2 + 20"
                      :text-anchor="label.anchor || 'middle'"
                      class="paper-axis-label"
                    >{{ label.label }}</text>
                    <polyline
                      v-for="series in observationReturnChart.series"
                      :key="'observe-' + series.key"
                      :points="series.points"
                      :class="['paper-chart-line', 'paper-chart-line-' + series.key]"
                    ></polyline>
                    <line
                      v-if="conclusions.chartHover"
                      :x1="conclusions.chartHover.x"
                      :y1="observationReturnChart.axis.y1"
                      :x2="conclusions.chartHover.x"
                      :y2="observationReturnChart.axis.y2"
                      class="paper-hover-line"
                    ></line>
                    <circle
                      v-for="item in (conclusions.chartHover?.items || [])"
                      :key="'observe-hover-' + item.key"
                      :cx="item.x"
                      :cy="item.y"
                      r="4"
                      :class="['paper-hover-dot', 'paper-chart-dot-' + item.key]"
                    ></circle>
                    <text v-if="!observationReturnChart.series.length" x="350" y="104" text-anchor="middle" class="paper-chart-empty">运行或选择推演记录后显示收益对照</text>
                  </svg>
                  <div class="paper-chart-legend" v-if="observationReturnChart.series.length">
                    <span v-for="series in observationReturnChart.series" :key="'observe-legend-' + series.key">
                      <i :class="['paper-chart-dot', 'paper-chart-dot-' + series.key]"></i>
                      {{ series.label }} {{ formatPercent(series.latest) }}
                    </span>
                  </div>
                  <div v-if="conclusions.chartHover" class="paper-chart-hover-readout">
                    <strong>{{ conclusions.chartHover.date || "N/A" }}</strong>
                    <span v-for="item in conclusions.chartHover.items" :key="'observe-readout-' + item.key">
                      {{ item.label }} {{ formatPercent(item.value) }}
                    </span>
                  </div>
                </div>
                <div class="conclusion-track-grid">
                  <div class="alpha-section-head">
                    <strong>结论生命周期</strong>
                    <small>状态慢同步，复盘动作手动确认</small>
                  </div>
                  <article
                    v-for="track in conclusions.items"
                    :key="track.conclusion_id"
                    :class="['paper-track-card', 'conclusion-track-card', { active: track.conclusion_id === conclusions.selectedConclusionId }]"
                    @click="conclusions.selectedConclusionId = track.conclusion_id"
                  >
                    <div class="history-head">
                      <strong>{{ track.ticker }}</strong>
                      <div class="history-head-meta">
                        <span>{{ conclusionStatusLabel(track.status) }}</span>
                        <span>{{ track.rating || track.action || "Manual" }}</span>
                      </div>
                    </div>
                    <p>{{ track.thesis || "暂无结论摘要。" }}</p>
                    <div class="paper-track-progress">
                      <span :style="{ width: formatPercent(track.progress) }"></span>
                    </div>
                    <small>
                      {{ track.age_days }}/{{ track.horizon_days }} 天 · 当前收益 {{ formatPercent(track.current_return) }} · 目标仓位 {{ formatPercent(track.target_position_size) }}
	                    </small>
	                    <small>来源 {{ track.source_run_id || "manual" }} · {{ track.analysis_date || String(track.opened_at || '').slice(0, 10) }}</small>
	                    <small>
	                      模拟 {{ formatPercent(track.simulation_return) }} · 真实 {{ formatPercent(track.actual_return) }}
	                      · 偏差 {{ formatPercent(track.simulation_deviation) }} · 命中 {{ formatPercent(track.hit_rate) }}
	                    </small>
	                    <small v-if="track.review_conclusion">{{ track.review_conclusion }}</small>
	                    <small v-if="track.comparison?.price_source_counts || track.comparison?.simulation_summary">
                      真实 {{ track.comparison?.price_source_counts?.real || 0 }} 点 · 模拟 {{ track.comparison?.price_source_counts?.simulated || 0 }} 点
	                      · 中位 {{ formatPercent(track.comparison?.simulation_summary?.quantiles?.p50) }}
                    </small>
                    <textarea
                      v-model="conclusions.reviewNotes[track.conclusion_id]"
                      rows="2"
                      placeholder="复盘备注"
                    ></textarea>
                    <div class="history-actions">
                      <button type="button" class="ghost-button mini" @click="reviewConclusion(track, 'validated')">验证有效</button>
                      <button type="button" class="ghost-button mini" @click="reviewConclusion(track, 'invalidated')">标记失效</button>
                      <button type="button" class="ghost-button mini" @click="reviewConclusion(track, 'tracking')">继续跟踪</button>
                      <button type="button" class="ghost-button mini danger-button" @click="reviewConclusion(track, 'archived')">归档</button>
                      <button type="button" class="ghost-button mini danger-button" @click="deleteConclusion(track)">删除</button>
                    </div>
                  </article>
                  <div v-if="!conclusions.items.length" class="placeholder-block">
                    <strong>还没有研究结论入池</strong>
                    <p>可以从当前任务入池，也可以手动添加一个只观察、不下单的长期观察结论。</p>
                  </div>
                </div>
              </section>
              <aside class="conclusion-side-panel">
                <article class="paper-interface-card">
                  <div class="section-title-row">
                    <div>
                      <h3>手动加入观察</h3>
                      <p>用于跟踪暂不交易、被风控拦截或来自外部研究的结论。</p>
                    </div>
                  </div>
                  <div class="paper-order-grid">
                    <label class="field">
                      <span>标的</span>
                      <input v-model="conclusions.form.ticker" type="text" :placeholder="form.ticker">
                    </label>
                    <label class="field">
                      <span>资产类型</span>
                      <select v-model="conclusions.form.assetType">
                        <option value="stock">stock</option>
                        <option value="crypto">crypto</option>
                      </select>
                    </label>
                    <label class="field">
                      <span>评级</span>
                      <input v-model="conclusions.form.rating" type="text" placeholder="Buy / Hold / Manual">
                    </label>
                    <label class="field">
                      <span>动作</span>
                      <select v-model="conclusions.form.action">
                        <option value="buy">buy</option>
                        <option value="overweight">overweight</option>
                        <option value="hold">hold</option>
                        <option value="underweight">underweight</option>
                        <option value="sell">sell</option>
                      </select>
                    </label>
                    <label class="field">
                      <span>目标仓位</span>
                      <input v-model="conclusions.form.targetPositionSize" type="text" placeholder="0.10">
                    </label>
                    <label class="field">
                      <span>观察周期(天)</span>
                      <input v-model="conclusions.form.horizonDays" type="text" placeholder="20">
                    </label>
                  </div>
                  <label class="field full">
                    <span>核心论点</span>
                    <textarea v-model="conclusions.form.thesis" rows="4" placeholder="这条结论为什么值得长期观察"></textarea>
                  </label>
                  <button type="button" class="primary-button" @click="addManualConclusion">加入研究跟踪盘</button>
                </article>
              </aside>
            </div>

            <div v-else-if="isPaperWorkbenchModule" class="paper-dashboard">
              <section class="paper-live-panel">
                <div class="section-title-row">
                  <div>
	                    <h3>{{ paperModuleTitle }}</h3>
	                    <p>{{ paperModuleDescription }}</p>
                  </div>
                  <button type="button" class="ghost-button mini" :disabled="paper.loading" @click="refreshPaperTrading">
                    {{ paper.loading ? "刷新中" : (isPaperReplayModule ? "加载信号" : "刷新") }}
                  </button>
                </div>
                <div class="paper-symbol-row">
                  <label class="field">
                    <span>标的</span>
                    <input v-model="paper.ticker" type="text" placeholder="BTC-USD / AAPL / 300308.SZ">
                  </label>
                  <label class="field">
                    <span>资产类型</span>
                    <select v-model="paper.assetType">
                      <option value="stock">stock</option>
                      <option value="crypto">crypto</option>
                    </select>
                  </label>
                  <label v-if="isPaperFutureModule || isPaperAccountModule" class="paper-autorefresh">
                    <input v-model="paper.autoRefresh" type="checkbox">
                    <span>15s 自动刷新</span>
                  </label>
                </div>
                <div class="refresh-policy-strip">
                  <span v-if="isPaperReplayModule"><b>历史回测</b>手动运行</span>
                  <span v-else><b>价格 / 估值 / 曲线</b>15 秒自动刷新</span>
                  <span v-if="isPaperFutureModule"><b>推演模拟盘</b>按起点运行</span>
                  <span v-if="isPaperAccountModule"><b>纸面账户</b>手动下单</span>
                  <span><b>Agent 重新分析 / 推演</b>手动触发</span>
                </div>
                <div v-if="paper.error" class="error-diagnostic">
                  <strong>模拟盘错误</strong>
                  <p>{{ paper.error }}</p>
                </div>
                <div v-if="isPaperFutureModule || isPaperAccountModule" class="paper-live-metrics">
                  <article>
                    <span>最新价</span>
                    <strong>{{ formatNumber(paper.quote?.price, 4) }}</strong>
                    <small>{{ paper.quote?.as_of || "N/A" }}</small>
                  </article>
                  <article>
                    <span>涨跌幅</span>
                    <strong>{{ formatPercent(paper.quote?.change_percent) }}</strong>
                    <small>{{ formatNumber(paper.quote?.change, 4) }}</small>
                  </article>
                  <article>
                    <span>{{ isPaperAccountModule ? "账户权益" : "推演状态" }}</span>
                    <strong>{{ isPaperAccountModule ? formatNumber(paper.account?.equity) : (paper.forecastResult?.track ? "已入池" : "待创建") }}</strong>
                    <small>{{ isPaperAccountModule ? ("收益 " + formatPercent(paper.account?.total_return)) : (paper.forecastResult?.track?.conclusion_id || "长期观察复盘") }}</small>
                  </article>
                  <article>
                    <span>{{ isPaperAccountModule ? "现金" : "纸面同步" }}</span>
                    <strong>{{ isPaperAccountModule ? formatNumber(paper.account?.cash) : (paper.executePaperAccount ? "开启" : "关闭") }}</strong>
                    <small>{{ paper.lastUpdated || "未刷新" }}</small>
                  </article>
                </div>
                <div v-else class="paper-live-metrics">
                  <article>
                    <span>回测标的</span>
                    <strong>{{ paper.replayTicker || paper.ticker }}</strong>
                    <small>{{ paper.replayTradeDate || "未选择日期" }}</small>
                  </article>
                  <article>
                    <span>回测周期</span>
                    <strong>{{ paper.replayHorizonDays || "20" }} 天</strong>
                    <small>{{ paper.replayAction }} · {{ formatPercent(paper.replayTargetPositionSize) }}</small>
                  </article>
                  <article>
                    <span>最终权益</span>
                    <strong>{{ formatNumber((paper.replayResult?.final_snapshot || {}).equity || paper.replayAccount?.equity) }}</strong>
                    <small>return {{ formatPercent(paper.replayResult?.final_return) }}</small>
                  </article>
                  <article>
                    <span>回测更新时间</span>
                    <strong>{{ paper.replayLastUpdated || "未运行" }}</strong>
                    <small>{{ selectedReplaySnapshots.length }} snapshots</small>
                  </article>
                </div>
	                <div class="paper-chart-card" :class="{ 'paper-chart-card-fullscreen': paper.chartFullscreen }">
	                  <div class="paper-chart-head">
	                    <strong>{{ paperChartTitle }}</strong>
	                    <div v-if="isPaperAccountModule" class="paper-chart-tools">
	                      <div class="chart-range-tools">
	                        <select v-model="paper.chartRange" aria-label="纸面账户曲线范围">
	                          <option value="today">今天</option>
	                          <option value="7d">近 7 天</option>
	                          <option value="30d">近 30 天</option>
	                          <option value="all">全部</option>
	                          <option value="custom">自定义</option>
	                        </select>
	                        <input v-if="paper.chartRange === 'custom'" v-model="paper.chartStartDate" type="date" aria-label="纸面账户开始日期">
	                        <input v-if="paper.chartRange === 'custom'" v-model="paper.chartEndDate" type="date" aria-label="纸面账户结束日期">
	                      </div>
	                      <div class="paper-chart-toggles" role="group" aria-label="选择纸面账户曲线">
	                        <label v-for="option in paperChartOptions" :key="option.key">
	                          <input v-model="paper.chartSeries[option.key]" type="checkbox">
	                          <span>{{ option.label }}</span>
	                        </label>
	                        <button type="button" class="ghost-button mini" @click="paper.chartFullscreen = !paper.chartFullscreen">
	                          {{ paper.chartFullscreen ? "退出全屏" : "全屏" }}
	                        </button>
	                      </div>
	                    </div>
		                  </div>
			                  <svg
	                    viewBox="0 0 700 280"
	                    role="img"
	                    aria-label="模拟盘权益曲线"
	                    @mousemove="updatePaperChartHover"
	                    @mouseleave="clearPaperChartHover"
	                  >
	                    <line
	                      v-for="tick in activePaperChart.axis.yTicks"
	                      :key="'grid-' + tick.y"
	                      :x1="activePaperChart.axis.x1"
	                      :y1="tick.y"
	                      :x2="activePaperChart.axis.x2"
	                      :y2="tick.y"
	                      class="paper-grid-line"
	                    ></line>
	                    <line :x1="activePaperChart.axis.x1" :y1="activePaperChart.axis.y2" :x2="activePaperChart.axis.x2" :y2="activePaperChart.axis.y2" class="paper-axis"></line>
	                    <line :x1="activePaperChart.axis.x1" :y1="activePaperChart.axis.y1" :x2="activePaperChart.axis.x1" :y2="activePaperChart.axis.y2" class="paper-axis"></line>
	                    <text
	                      v-for="tick in activePaperChart.axis.yTicks"
	                      :key="'ytick-' + tick.y"
	                      :x="activePaperChart.axis.x1 - 8"
	                      :y="tick.y + 4"
	                      text-anchor="end"
	                      class="paper-axis-label"
	                    >{{ tick.label }}</text>
	                    <text
	                      v-for="label in activePaperChart.axis.xLabels"
	                      :key="'xlabel-' + label.x + label.label"
	                      :x="label.x"
	                      :y="activePaperChart.axis.y2 + 20"
	                      :text-anchor="label.anchor || 'middle'"
	                      class="paper-axis-label"
		                    >{{ label.label }}</text>
		                    <text :x="activePaperChart.axis.x1" y="12" class="paper-axis-title">{{ activePaperChart.axis.label }}</text>
		                    <polygon
		                      v-if="activePaperChart.bandPoints"
		                      :points="activePaperChart.bandPoints"
		                      class="paper-quantile-band"
		                    ></polygon>
		                    <polyline
		                      v-if="activePaperChart.lowerPoints"
		                      :points="activePaperChart.lowerPoints"
		                      class="paper-quantile-bound"
		                    ></polyline>
		                    <polyline
		                      v-if="activePaperChart.upperPoints"
		                      :points="activePaperChart.upperPoints"
		                      class="paper-quantile-bound"
		                    ></polyline>
		                    <polyline
		                      v-for="series in activePaperChart.series"
	                      :key="series.key"
	                      :points="series.points"
	                      :class="['paper-chart-line', 'paper-chart-line-' + series.key]"
	                    ></polyline>
	                    <line
	                      v-if="paper.chartHover"
	                      :x1="paper.chartHover.x"
	                      :y1="activePaperChart.axis.y1"
	                      :x2="paper.chartHover.x"
	                      :y2="activePaperChart.axis.y2"
	                      class="paper-hover-line"
	                    ></line>
	                    <circle
	                      v-for="item in (paper.chartHover?.items || [])"
	                      :key="'hover-' + item.key"
	                      :cx="item.x"
	                      :cy="item.y"
	                      r="4"
	                      :class="['paper-hover-dot', 'paper-chart-dot-' + item.key]"
	                    ></circle>
	                    <text v-if="!activePaperChart.series.length" x="350" y="132" text-anchor="middle" class="paper-chart-empty">{{ isPaperReplayModule ? "运行历史回测后显示回测曲线" : "选择曲线后显示" }}</text>
	                  </svg>
	                  <div class="paper-chart-legend" v-if="activePaperChart.series.length">
                    <span v-for="series in activePaperChart.series" :key="series.key">
                      <i :class="['paper-chart-dot', 'paper-chart-dot-' + series.key]"></i>
	                      {{ series.label }} {{ formatNumber(series.latest, series.decimals) }}
	                    </span>
	                  </div>
	                  <div v-if="paper.chartHover" class="paper-chart-hover-readout">
	                    <strong>{{ paper.chartHover.date || "N/A" }}</strong>
	                    <span v-for="item in paper.chartHover.items" :key="'readout-' + item.key">
	                      {{ item.label }} {{ formatNumber(item.value, item.decimals) }}
	                    </span>
	                  </div>
	                </div>
                <div v-if="isPaperAccountModule" class="paper-snapshot-list">
                  <div class="metric-row paper-snapshot-row metric-head">
                    <span>Time</span>
                    <span>Equity</span>
                    <span>Return</span>
                    <span>Cash</span>
                  </div>
                  <div v-for="snapshot in selectedPaperSnapshots.slice(-6)" :key="snapshot.trade_date" class="metric-row paper-snapshot-row">
                    <span>{{ formatLocalDateTime(snapshot.trade_date) }}</span>
                    <span>{{ formatNumber(snapshot.equity) }}</span>
                    <span>{{ formatPercent(snapshot.total_return) }}</span>
                    <span>{{ formatNumber(snapshot.cash) }}</span>
                  </div>
                </div>
                <div v-else-if="isPaperReplayModule" class="paper-snapshot-list">
                  <div class="metric-row paper-snapshot-row metric-head">
                    <span>Time</span>
                    <span>Equity</span>
                    <span>Return</span>
                    <span>Cash</span>
                  </div>
                  <p v-if="!selectedReplaySnapshots.length">运行右侧历史回测后，这里会显示回放快照。</p>
                  <div v-for="snapshot in selectedReplaySnapshots.slice(-12)" :key="'replay-main-' + snapshot.trade_date" class="metric-row paper-snapshot-row">
                    <span>{{ formatLocalDateTime(snapshot.trade_date) }}</span>
                    <span>{{ formatNumber(snapshot.equity) }}</span>
                    <span>{{ formatPercent(snapshot.total_return) }}</span>
                    <span>{{ formatNumber(snapshot.cash) }}</span>
                  </div>
                </div>
                <div v-else class="paper-snapshot-list">
                  <div class="metric-row paper-snapshot-row metric-head">
                    <span>对象</span>
                    <span>状态</span>
                    <span>周期</span>
                    <span>收益</span>
                  </div>
                  <p v-if="!paper.forecastResult?.episode">运行推演模拟盘后，这里会显示入池记录。</p>
                  <div v-if="paper.forecastResult?.episode" class="metric-row paper-snapshot-row">
                    <span>{{ paper.forecastResult.episode.ticker }}</span>
                  <span>{{ simulationStateLabel(paper.forecastResult.data_mode || paper.forecastResult.episode.status) }}</span>
                    <span>{{ paper.forecastResult.episode.horizon_days }} 天</span>
                    <span>{{ formatPercent(paper.forecastResult.episode.strategy_return) }}</span>
	                  </div>
	                  <div v-if="paper.forecastResult?.episode" class="refresh-policy-strip">
	                    <span><b>数据来源</b>{{ activeSimulationSourceLabel }}</span>
	                    <span><b>情景</b>{{ scenarioLabel(activeSimulationMeta.scenario || "base") }}</span>
	                    <span><b>路径数</b>{{ activeSimulationSummary.paths || activeSimulationMeta.num_paths || 0 }}</span>
	                  </div>
                  <div v-if="activeSimulationSummary.quantiles" class="kv-grid">
                    <span>低位 P10</span><b>{{ formatPercent(activeSimulationSummary.quantiles.p10) }}</b>
		                    <span>中位 P50</span><b>{{ formatPercent(activeSimulationSummary.quantiles.p50) }}</b>
		                    <span>高位 P90</span><b>{{ formatPercent(activeSimulationSummary.quantiles.p90) }}</b>
	                  </div>
	                  <div v-if="activeSimulationScenarioRows.length" class="paper-scenario-table">
	                    <div class="metric-row paper-scenario-row metric-head">
	                      <span>情景</span>
	                      <span>低位</span>
	                      <span>中位</span>
	                      <span>高位</span>
	                      <span>路径</span>
	                    </div>
	                    <div
	                      v-for="row in activeSimulationScenarioRows"
	                      :key="'scenario-' + row.name"
	                      class="metric-row paper-scenario-row"
	                    >
	                      <span>{{ row.label }}</span>
	                      <span>{{ formatPercent(row.p10) }}</span>
	                      <span>{{ formatPercent(row.p50) }}</span>
	                      <span>{{ formatPercent(row.p90) }}</span>
	                      <span>{{ row.paths }}</span>
	                    </div>
	                  </div>
	                </div>
              </section>

              <aside class="paper-side-panel">
                <article class="paper-interface-card">
                  <div class="section-title-row">
                    <div>
	                    <h3>{{ paperInterfaceTitle }}</h3>
	                    <p>{{ paperInterfaceDescription }}</p>
                    </div>
                    <div v-if="isPaperAccountModule" class="paper-reset-tools">
                      <input v-model="paper.initialCash" type="text" aria-label="初始资金">
                      <button type="button" class="ghost-button mini" @click="resetPaperAccount">重置账户</button>
                    </div>
                  </div>
                  <div class="paper-view-tabs">
                    <button type="button" :class="{ active: selectedPaperTradingView === 'overview' }" @click="selectedPaperTradingView = 'overview'">{{ isPaperReplayModule ? "回测" : "推演" }}</button>
                    <button v-if="isPaperAccountModule" type="button" :class="{ active: selectedPaperTradingView === 'account' }" @click="selectedPaperTradingView = 'account'">账户</button>
                    <button v-if="isPaperAccountModule" type="button" :class="{ active: selectedPaperTradingView === 'analytics' }" @click="selectedPaperTradingView = 'analytics'">绩效</button>
                    <button type="button" :class="{ active: selectedPaperTradingView === 'ledger' }" @click="selectedPaperTradingView = 'ledger'">账本</button>
                    <button v-if="isPaperAccountModule" type="button" :class="{ active: selectedPaperTradingView === 'fills' }" @click="selectedPaperTradingView = 'fills'">成交</button>
                    <button v-if="isPaperAccountModule" type="button" :class="{ active: selectedPaperTradingView === 'positions' }" @click="selectedPaperTradingView = 'positions'">持仓</button>
                    <button type="button" :class="{ active: selectedPaperTradingView === 'api' }" @click="selectedPaperTradingView = 'api'">接口</button>
                  </div>
	                  <div v-if="selectedPaperTradingView === 'overview'" class="detail-stack">
                    <section v-if="isPaperFutureModule || isPaperAccountModule" class="paper-flow-section">
                      <div class="section-title-row">
                        <div>
                          <h3>{{ isPaperAccountModule ? "纸面账户执行" : "推演模拟盘" }}</h3>
                          <p>{{ isPaperAccountModule ? "先确认 execution_plan 或手动假设，再写入纸面账户；后续刷新行情和账户估值。" : "记录当前判断、入场价格和观察周期，后续在长期观察中与真实行情对照。" }}</p>
                        </div>
                      </div>
	                    <div class="paper-order-grid">
                        <label class="field">
                          <span>动作</span>
                          <select v-model="paper.action">
                            <option value="buy">buy</option>
                            <option value="overweight">overweight</option>
                            <option value="hold">hold</option>
                            <option value="underweight">underweight</option>
                            <option value="sell">sell</option>
                          </select>
                        </label>
	                      <label class="field">
	                        <span>目标仓位</span>
	                        <input v-model="paper.targetPositionSize" type="text" placeholder="0.10">
	                      </label>
	                      <label class="field">
	                        <span>观察周期(天)</span>
	                        <input v-model="paper.horizonDays" type="text" placeholder="20">
	                      </label>
                        <label v-if="isPaperFutureModule" class="field">
                          <span>观察起点</span>
                          <input v-model="paper.forecastAnalysisDate" type="date">
                        </label>
                        <label v-if="isPaperFutureModule" class="field">
                          <span>入场价</span>
                          <input v-model="paper.forecastEntryPrice" type="text" placeholder="空则使用最新价">
                        </label>
                        <label v-if="isPaperFutureModule" class="field">
                          <span>模拟情景</span>
                          <select v-model="paper.simulationScenario">
                            <option value="base">基准</option>
                            <option value="bull">乐观</option>
                            <option value="bear">悲观</option>
                            <option value="stress">压力</option>
                          </select>
                        </label>
                        <label v-if="isPaperFutureModule" class="field">
                          <span>日波动率</span>
                          <input v-model="paper.simulationVolatility" type="text" placeholder="空则按历史估计">
                        </label>
                        <label v-if="isPaperFutureModule" class="field">
                          <span>日趋势偏移</span>
                          <input v-model="paper.simulationDrift" type="text" placeholder="空则按历史估计">
                        </label>
                        <label v-if="isPaperFutureModule" class="field">
                          <span>模拟次数</span>
                          <input v-model="paper.simulationPaths" type="text" placeholder="200">
                        </label>
                        <label v-if="isPaperFutureModule" class="field">
                          <span>随机种子</span>
                          <input v-model="paper.simulationSeed" type="text" placeholder="可空">
                        </label>
	                      <label v-if="isPaperAccountModule || paper.executePaperAccount" class="field">
	                        <span>手续费率</span>
	                        <input v-model="paper.commissionRate" type="text" placeholder="0 或 0.1%">
                        </label>
                        <label v-if="isPaperAccountModule || paper.executePaperAccount" class="field">
	                        <span>滑点率</span>
	                        <input v-model="paper.slippageRate" type="text" placeholder="0 或 0.05%">
	                      </label>
	                    </div>
	                    <label class="field full">
	                      <span>核心论点</span>
	                      <textarea v-model="paper.conclusionThesis" rows="3" placeholder="记录这次结论为什么值得跟踪"></textarea>
	                    </label>
                      <label class="field full">
                        <span>{{ isPaperAccountModule ? "可选：从任务结论回填" : "可选：从任务结论回填" }}</span>
                        <select v-model="paper.selectedSignalRunId" @change="applyPaperSignal({ mode: 'live', submit: false })">
                          <option value="">不使用任务，直接用上方手动参数</option>
                          <option v-for="signal in currentPaperSignals" :key="signal.run_id" :value="signal.run_id">
                            {{ signal.ticker }} · {{ signal.analysis_date || signal.run_id }} · {{ signal.execution_plan?.action }} {{ formatPercent(signal.execution_plan?.target_position_size) }}
                          </option>
                        </select>
                      </label>
                      <label v-if="isPaperFutureModule" class="paper-autorefresh">
                        <input v-model="paper.executePaperAccount" type="checkbox">
                        <span>同时加入纸面账户</span>
                      </label>
	                    <button type="button" class="primary-button" :disabled="paper.loading" @click="paper.selectedSignalRunId ? applyPaperSignal({ mode: 'live', submit: true }) : (isPaperAccountModule ? submitPaperOrder() : submitForecastObservation())">{{ paper.selectedSignalRunId ? paperSignalSubmitLabel('live') : (isPaperAccountModule ? "用手动参数写入纸面账户" : "用手动参数运行推演") }}</button>
                    </section>

                    <section v-if="isPaperReplayModule" class="paper-flow-section">
                      <div class="section-title-row">
                        <div>
                          <h3>历史真实数据回测</h3>
                          <p>使用结论日期之后的真实历史价格回放，不影响推演模拟盘和纸面账户。</p>
                        </div>
                      </div>
                      <label class="field full">
                        <span>使用历史任务结论</span>
                        <select v-model="paper.selectedReplaySignalRunId" @change="applyPaperSignal({ mode: 'replay', submit: false })">
                          <option value="">选择过去 execution_plan</option>
                          <option v-for="signal in historicalPaperSignals" :key="signal.run_id" :value="signal.run_id">
                            {{ signal.ticker }} · {{ signal.analysis_date || signal.run_id }} · {{ signal.execution_plan?.action }} {{ formatPercent(signal.execution_plan?.target_position_size) }}
                          </option>
                        </select>
                      </label>
                      <div class="paper-order-grid">
                        <label class="field">
                          <span>回测标的</span>
                          <input v-model="paper.replayTicker" type="text" :placeholder="paper.ticker">
                        </label>
                        <label class="field">
                          <span>结论日期</span>
                          <input v-model="paper.replayTradeDate" type="date">
                        </label>
                        <label class="field">
                          <span>动作</span>
                          <select v-model="paper.replayAction">
                            <option value="buy">buy</option>
                            <option value="overweight">overweight</option>
                            <option value="hold">hold</option>
                            <option value="underweight">underweight</option>
                            <option value="sell">sell</option>
                          </select>
                        </label>
                        <label class="field">
                          <span>目标仓位</span>
                          <input v-model="paper.replayTargetPositionSize" type="text" placeholder="0.10">
                        </label>
                        <label class="field">
                          <span>回测周期(天)</span>
                          <input v-model="paper.replayHorizonDays" type="text" placeholder="20">
                        </label>
                      </div>
                      <label class="field full">
                        <span>历史论点</span>
                        <textarea v-model="paper.replayThesis" rows="3" placeholder="历史结论会回填到这里"></textarea>
                      </label>
	                    <button type="button" class="ghost-button" :disabled="paper.loading || !paper.replayTicker || !paper.replayTradeDate" @click="paper.selectedReplaySignalRunId ? applyPaperSignal({ mode: 'replay', submit: true }) : replayManualHistoricalPaper()">{{ paper.selectedReplaySignalRunId ? paperSignalSubmitLabel('replay') : "运行手动回测" }}</button>
                      <div v-if="paper.replayAccount" class="paper-account-summary">
                        <article>
                          <span>起始资金</span>
                          <strong>{{ formatNumber(paper.replayAccount?.initial_cash) }}</strong>
                        </article>
                        <article>
                          <span>最终权益</span>
                          <strong>{{ formatNumber((paper.replayResult?.final_snapshot || {}).equity || paper.replayAccount?.equity) }}</strong>
                        </article>
                        <article>
                          <span>最终收益</span>
                          <strong>{{ formatPercent(paper.replayResult?.final_return) }}</strong>
                        </article>
                        <article>
                          <span>更新时间</span>
                          <strong>{{ paper.replayLastUpdated || "N/A" }}</strong>
                        </article>
                      </div>
                      <div v-if="selectedReplaySnapshots.length" class="paper-snapshot-list">
                        <div class="metric-row paper-snapshot-row metric-head">
                          <span>Time</span>
                          <span>Equity</span>
                          <span>Return</span>
                          <span>Cash</span>
                        </div>
                        <div v-for="snapshot in selectedReplaySnapshots.slice(-8)" :key="'replay-' + snapshot.trade_date" class="metric-row paper-snapshot-row">
                          <span>{{ formatLocalDateTime(snapshot.trade_date) }}</span>
                          <span>{{ formatNumber(snapshot.equity) }}</span>
                          <span>{{ formatPercent(snapshot.total_return) }}</span>
                          <span>{{ formatNumber(snapshot.cash) }}</span>
                        </div>
                      </div>
                    </section>
	                  </div>
	                  <div v-else-if="selectedPaperTradingView === 'account'" class="detail-stack">
	                    <div class="paper-account-summary">
                      <article>
                        <span>初始资金</span>
                        <strong>{{ formatNumber(paper.account?.initial_cash) }}</strong>
                      </article>
                      <article>
                        <span>当前权益</span>
                        <strong>{{ formatNumber(paper.account?.equity) }}</strong>
                      </article>
                      <article>
                        <span>累计收益</span>
                        <strong>{{ formatPercent(paper.account?.total_return) }}</strong>
                      </article>
                      <article>
	                        <span>记录数</span>
	                        <strong>{{ selectedPaperSnapshots.length }}</strong>
	                      </article>
	                    </div>
	                    <div class="paper-track-list">
	                      <div class="alpha-section-head">
	                        <strong>结论跟踪</strong>
	                        <small>{{ paperConclusionTracks.length }} 条</small>
	                      </div>
	                      <p v-if="!paperConclusionTracks.length">还没有进入模拟组合的研究结论。</p>
	                      <article v-for="track in paperConclusionTracks" :key="track.trade_date + track.ticker + track.source_run_id" class="paper-track-card">
	                        <div class="history-head">
	                          <strong>{{ track.ticker }}</strong>
	                          <div class="history-head-meta">
	                            <span>{{ simulationStateLabel(track.status) }}</span>
	                            <span>{{ track.rating || track.action || "Manual" }}</span>
	                          </div>
	                        </div>
	                        <p>{{ track.thesis || "手动加入的模拟跟踪结论" }}</p>
	                        <div class="paper-track-progress">
	                          <span :style="{ width: formatPercent(track.progress) }"></span>
	                        </div>
	                        <small>
	                          {{ track.age_days }}/{{ track.horizon_days }} 天 · 当前收益 {{ formatPercent(track.current_return) }} · 目标仓位 {{ formatPercent(track.target_position_size) }}
	                        </small>
	                      </article>
	                    </div>
	                    <div class="paper-account-table">
                      <div class="metric-row paper-account-row metric-head">
                        <span>Time</span>
                        <span>Equity</span>
                        <span>Return</span>
                        <span>Cash</span>
                        <span>Position</span>
                      </div>
                      <p v-if="!selectedPaperSnapshots.length">当前账户还没有快照记录。</p>
                      <div
                        v-for="snapshot in selectedPaperSnapshots.slice().reverse().slice(0, 30)"
                        :key="snapshot.trade_date"
                        class="metric-row paper-account-row"
                      >
                        <span>{{ formatLocalDateTime(snapshot.trade_date) }}</span>
                        <span>{{ formatNumber(snapshot.equity) }}</span>
                        <span>{{ formatPercent(snapshot.total_return) }}</span>
                        <span>{{ formatNumber(snapshot.cash) }}</span>
                        <span>{{ formatNumber(snapshot.positions_value) }}</span>
                      </div>
		                    </div>
		                  </div>
                  <div v-else-if="selectedPaperTradingView === 'analytics'" class="detail-stack">
                    <div class="paper-skill-panel">
                      <div class="alpha-section-head">
                        <strong>计算 Skills</strong>
                        <button type="button" class="ghost-button mini" @click="refreshPaperAnalytics">重新计算</button>
                      </div>
                      <label v-for="skill in paper.analyticsSkills" :key="skill.name" :class="{ disabled: skill.available === false }">
                        <input
                          v-model="paper.selectedAnalyticsSkills[skill.name]"
                          type="checkbox"
                          :disabled="skill.available === false"
                          @change="refreshPaperAnalytics"
                        >
                        <span>
                          <b>{{ skill.label || skill.name }}</b>
                          <small>{{ skill.available === false ? "未安装" : (skill.description || skill.name) }}</small>
                        </span>
                      </label>
                    </div>
                    <div class="paper-account-summary">
                      <article>
                        <span>总收益</span>
                        <strong>{{ formatPercent(paper.analytics?.summary?.total_return) }}</strong>
                      </article>
                      <article>
                        <span>最大回撤</span>
                        <strong>{{ formatPercent(paper.analytics?.summary?.max_drawdown) }}</strong>
                      </article>
                      <article>
                        <span>Sharpe</span>
                        <strong>{{ formatNumber(paper.analytics?.summary?.annualized_sharpe, 2) }}</strong>
                      </article>
                      <article>
                        <span>胜率</span>
                        <strong>{{ formatPercent(paper.analytics?.summary?.win_rate) }}</strong>
                      </article>
                      <article>
                        <span>跟踪中</span>
                        <strong>{{ paper.analytics?.summary?.track_counts?.tracking || 0 }}</strong>
                      </article>
                      <article>
                        <span>待复盘</span>
                        <strong>{{ paper.analytics?.summary?.track_counts?.due_review || 0 }}</strong>
                      </article>
                    </div>
                    <div class="kv-grid">
                      <span>样本数</span><b>{{ paper.analytics?.summary?.observations || 0 }}</b>
                      <span>区间波动</span><b>{{ formatPercent(paper.analytics?.summary?.period_volatility) }}</b>
                      <span>最好区间</span><b>{{ formatPercent(paper.analytics?.summary?.best_period_return) }}</b>
                      <span>最差区间</span><b>{{ formatPercent(paper.analytics?.summary?.worst_period_return) }}</b>
                      <span>计算 Skills</span><b>{{ (paper.analytics?.skills || []).join(" + ") || "builtin_performance" }}</b>
                      <span>QuantStats</span><b>{{ paper.analytics?.quantstats_available ? "已启用" : "未安装" }}</b>
                    </div>
                    <p v-if="paper.analytics?.message">{{ paper.analytics.message }}</p>
                  </div>
                  <div v-else-if="selectedPaperTradingView === 'ledger'" class="detail-stack">
                    <div class="alpha-section-head">
                      <strong>{{ paperLedgerTitle }}</strong>
                      <button type="button" class="ghost-button mini" @click="refreshPaperEpisodes">刷新</button>
                    </div>
                    <div class="paper-account-summary">
                      <article>
                        <span>总记录</span>
                        <strong>{{ paperEpisodeSummary.total_episodes || 0 }}</strong>
                      </article>
                      <article>
                        <span>已观察</span>
                        <strong>{{ paperEpisodeSummary.observed_count || 0 }}</strong>
                      </article>
                      <article>
                        <span>平均收益</span>
                        <strong>{{ formatPercent(paperEpisodeSummary.average_return) }}</strong>
                      </article>
                      <article>
                        <span>胜率</span>
                        <strong>{{ formatPercent(paperEpisodeSummary.win_rate) }}</strong>
                      </article>
                    </div>
                    <div class="kv-grid">
                      <span>复合收益</span><b>{{ formatPercent(paperEpisodeSummary.total_return) }}</b>
                      <span>平均置信度</span><b>{{ formatPercent(paperEpisodeSummary.average_confidence) }}</b>
                      <span>平均目标仓位</span><b>{{ formatPercent(paperEpisodeSummary.average_target_position_size) }}</b>
                      <span>更新时间</span><b>{{ paper.ledgerLastUpdated || paper.episodes?.updated_at || "N/A" }}</b>
                    </div>
                    <div class="paper-ledger-table">
                      <div class="metric-row paper-ledger-row metric-head">
                        <span>分组</span>
                        <span>名称</span>
                        <span>记录</span>
                        <span>平均收益</span>
                        <span>胜率</span>
                      </div>
                      <p v-if="!paperLedgerFacetRows.length">还没有可统计的演练记录。</p>
                      <div
                        v-for="row in paperLedgerFacetRows.slice(0, 24)"
                        :key="row.facet + row.name"
                        class="metric-row paper-ledger-row"
                      >
                        <span>{{ row.facet }}</span>
                        <span>{{ row.name }}</span>
                        <span>{{ row.count }} / {{ row.observed_count }}</span>
                        <span>{{ formatPercent(row.average_return) }}</span>
                        <span>{{ formatPercent(row.win_rate) }}</span>
                      </div>
                    </div>
                    <div class="paper-track-list">
                      <div class="alpha-section-head">
                        <strong>最近记录</strong>
                        <small>{{ scopedPaperEpisodes.length }} 条</small>
                      </div>
                      <p v-if="!scopedPaperEpisodes.length">当前模块还没有账本记录。</p>
                      <article v-for="episode in scopedPaperEpisodes.slice(0, 12)" :key="episode.episode_id" class="paper-track-card paper-ledger-card">
                        <div class="history-head">
                          <strong>{{ episode.ticker }}</strong>
                          <div class="history-head-meta">
	                            <span>{{ simulationTypeLabel(episode.simulation_type || episode.mode) }}</span>
	                            <span>{{ simulationStateLabel(episode.status) }}</span>
                          </div>
                        </div>
                        <p>{{ episode.thesis || episode.reason || "无结论摘要" }}</p>
                        <small>
                          {{ episode.signal_date || "N/A" }} · {{ episode.rating || episode.action || "N/A" }}
                          · 仓位 {{ formatPercent(episode.target_position_size) }}
                          · 收益 {{ formatPercent(episode.final_return) }}
                        </small>
                      </article>
                    </div>
                  </div>
	                  <div v-else-if="selectedPaperTradingView === 'fills'" class="detail-stack">
                    <p v-if="!paperFills.length">当前账户还没有成交。</p>
	                    <div v-for="fill in paperFills.slice(0, 20)" :key="fill.trade_date + fill.side + fill.price" class="kv-grid">
	                      <span>Side</span><b>{{ fill.side }}</b>
	                      <span>Ticker</span><b>{{ fill.ticker }}</b>
	                      <span>Rating</span><b>{{ fill.rating || fill.action || "Manual" }}</b>
	                      <span>Horizon</span><b>{{ fill.horizon_days || 20 }} 天</b>
	                      <span>Quantity</span><b>{{ formatNumber(fill.quantity, 6) }}</b>
	                      <span>Price</span><b>{{ formatNumber(fill.price, 4) }}</b>
	                      <span>Gross</span><b>{{ formatNumber(fill.gross_amount) }}</b>
	                      <span>Commission</span><b>{{ formatNumber(fill.commission) }}</b>
	                      <span>Source</span><b>{{ fill.source_run_id || "manual" }}</b>
	                    </div>
                  </div>
                  <div v-else-if="selectedPaperTradingView === 'positions'" class="detail-stack">
                    <p v-if="!paperPositions.length">当前账户无持仓。</p>
                    <div v-for="position in paperPositions" :key="position.ticker" class="kv-grid">
                      <span>Ticker</span><b>{{ position.ticker }}</b>
                      <span>Quantity</span><b>{{ formatNumber(position.quantity, 6) }}</b>
                      <span>Avg Cost</span><b>{{ formatNumber(position.average_cost, 4) }}</b>
                      <span>Last Price</span><b>{{ formatNumber(position.last_price, 4) }}</b>
                      <span>Market Value</span><b>{{ formatNumber(position.market_value) }}</b>
                      <span>Unrealized PnL</span><b>{{ formatNumber(position.unrealized_pnl) }}</b>
                    </div>
                  </div>
                  <div v-else-if="selectedPaperTradingView === 'api'" class="kv-grid">
                    <span>Quote API</span><b>GET /api/simulation/forecast/quote?ticker={{ paper.ticker }}</b>
                    <span>Account API</span><b>GET /api/simulation/forecast/account</b>
	                    <span>Order API</span><b>POST /api/simulation/forecast/order</b>
	                    <span>Simulation Run</span><b>POST /api/forecast-observations</b>
	                    <span>Signals API</span><b>GET /api/simulation/forecast/signals</b>
	                    <span>Skills API</span><b>GET /api/simulation/forecast/skills</b>
	                    <span>Analytics API</span><b>GET /api/simulation/forecast/analytics</b>
	                    <span>Backtest API</span><b>POST /api/simulation/backtest/manual</b>
	                    <span>Signal Backtest</span><b>POST /api/simulation/backtest/from-signal</b>
	                    <span>Observation API</span><b>GET /api/observations</b>
	                    <span>Observation Intraday</span><b>GET /api/simulation/observation/intraday</b>
	                    <span>Initial Cash</span><b>{{ formatNumber(paper.account?.initial_cash) }}</b>
	                    <span>Storage</span><b>workbench_users/&lt;user&gt;/paper_account.json</b>
	                  </div>
	                </article>
              </aside>
            </div>

            <div v-else class="config-preview">
              <pre>{{ configPreview }}</pre>
            </div>
          </article>
          </section>
        </section>

        <section
          v-if="alphaLibrary.data"
          v-show="activeWorkbenchModule === 'factors'"
          class="alpha-library-results panel module-panel-full"
        >
          <div class="panel-header">
            <div>
              <p class="eyebrow">Alpha Results</p>
              <h2>{{ alphaLibrary.data.ticker || "ALL" }} 因子结果</h2>
            </div>
            <div class="alpha-library-meta">
              <small>history {{ alphaLibrary.data.summary?.history_count || 0 }}</small>
              <small>registry {{ alphaLibrary.data.summary?.registry_count || 0 }}</small>
            </div>
          </div>
          <div class="alpha-results-grid">
            <div class="alpha-library-section">
              <div class="alpha-section-head">
                <strong>最近挖掘记录</strong>
                <button
                  v-if="(alphaLibrary.data.history || []).length > 5"
                  type="button"
                  class="ghost-button mini"
                  @click="showAllAlphaHistory = !showAllAlphaHistory"
                >
                  {{ showAllAlphaHistory ? "只看最近 5 条" : "展开更多" }}
                </button>
              </div>
              <article v-for="row in (showAllAlphaHistory ? (alphaLibrary.data.history || []) : (alphaLibrary.data.history || []).slice(0, 5))" :key="row.created_at_utc + row.source" class="history-card alpha-card">
                <div class="history-head">
                  <strong>{{ row.trade_date || "N/A" }}</strong>
                  <div class="history-head-meta">
                    <span>history</span>
                  </div>
                </div>
                <p>{{ row.payload?.alpha_result?.summary || row.source }}</p>
                <small>score {{ formatNumber(row.payload?.alpha_result?.signal_score, 4) }} · confidence {{ formatPercent(row.payload?.alpha_result?.confidence) }}</small>
                <small>{{ row.created_at_utc || row.source }}</small>
              </article>
              <p v-if="!(alphaLibrary.data.history || []).length">当前股票暂无 alpha mining 历史。</p>
            </div>
            <div class="alpha-library-section">
              <div class="alpha-section-head">
                <strong>相关候选因子</strong>
                <button
                  v-if="(alphaLibrary.data.registry || []).length > 5"
                  type="button"
                  class="ghost-button mini"
                  @click="showAllAlphaRegistry = !showAllAlphaRegistry"
                >
                  {{ showAllAlphaRegistry ? "只看前 5 条" : "展开更多" }}
                </button>
              </div>
              <article v-for="row in (showAllAlphaRegistry ? (alphaLibrary.data.registry || []) : (alphaLibrary.data.registry || []).slice(0, 5))" :key="row.expression + row.trade_date" class="history-card alpha-card">
                <div class="history-head">
                  <strong>{{ row.name || "Unnamed Alpha" }}</strong>
                  <div class="history-head-meta">
                    <span>registry</span>
                  </div>
                </div>
                <p>{{ row.hypothesis || row.expression || "无描述" }}</p>
                <small>eval {{ formatNumber(row.evaluation_score, 4) }} · alpha {{ formatPercent(row.realized_alpha) }}</small>
                <small>{{ row.expression || row.source || "" }}</small>
              </article>
              <p v-if="!(alphaLibrary.data.registry || []).length">当前股票暂无通过验证的候选因子。</p>
            </div>
          </div>
        </section>
        </section>
        </section>
      </main>

      <div v-if="healthState.open" class="modal-backdrop" @click.self="healthState.open = false">
        <section class="health-modal">
          <div class="modal-header">
            <div>
              <p class="eyebrow">系统自检</p>
              <h2>健康检查</h2>
            </div>
            <button type="button" class="ghost-button mini" @click="healthState.open = false">关闭</button>
          </div>

          <div v-if="healthState.loading" class="placeholder-block">
            <strong>正在检查</strong>
            <p>正在确认后端、执行槽、历史目录和 API Key 状态。</p>
          </div>

          <div v-else-if="healthState.error" class="error-diagnostic">
            <strong>健康检查失败</strong>
            <p>{{ healthState.error }}</p>
          </div>

          <div v-else-if="healthState.data" class="health-grid">
            <article>
              <span>整体状态</span>
              <strong :class="healthState.data.ok ? 'resume-ok' : 'resume-bad'">
                {{ healthState.data.ok ? "正常" : "异常" }}
              </strong>
              <p>{{ healthState.data.mode || "未知模式" }}</p>
            </article>
            <article>
              <span>执行槽</span>
              <strong>{{ (healthState.data.queue || {}).active_runs || 0 }}/{{ (healthState.data.queue || {}).run_concurrency || 1 }}</strong>
              <p>排队 {{ (healthState.data.queue || {}).queued_runs || 0 }} · 可用 {{ (healthState.data.queue || {}).available_slots || 0 }}</p>
            </article>
            <article>
              <span>历史目录</span>
              <strong :class="healthState.data.history_writable ? 'resume-ok' : 'resume-bad'">
                {{ healthState.data.history_writable ? "可写" : "不可写" }}
              </strong>
              <p>{{ healthState.data.history_dir }}</p>
            </article>
            <article>
              <span>模型请求保护</span>
              <strong>{{ healthState.data.llm_timeout }} 秒 / {{ healthState.data.llm_max_retries }} 次</strong>
              <div class="health-protection-form">
                <label>
                  <small>超时秒数</small>
                  <input v-model.number="healthState.llmTimeoutDraft" type="number" min="15" max="600" step="5">
                </label>
                <label>
                  <small>失败重试</small>
                  <input v-model.number="healthState.llmMaxRetriesDraft" type="number" min="0" max="5" step="1">
                </label>
                <button type="button" class="ghost-button mini" @click="saveHealthProtection">
                  {{ healthState.saving ? "保存中..." : "保存保护策略" }}
                </button>
              </div>
              <p>保存后会作为当前用户默认值，新任务自动使用。</p>
            </article>
            <article class="health-wide">
              <span>报告目录</span>
              <strong>报告保存位置</strong>
              <p>{{ healthState.data.report_dir }}</p>
            </article>
            <article class="health-wide">
              <span>API Key 状态</span>
              <div class="provider-health-list">
                <div v-for="(item, provider) in (healthState.data.providers || {})" :key="provider" class="provider-health-row">
                  <strong>{{ providerLabel(provider) }}</strong>
                  <span>{{ item.api_key_env }}</span>
                  <em :class="item.api_key_present ? 'resume-ok' : 'resume-bad'">
                    {{ apiKeyStatusLabel(item.api_key_present) }}
                  </em>
                </div>
              </div>
            </article>
          </div>
        </section>
      </div>

      <div v-if="adminState.open" class="modal-backdrop" @click.self="adminState.open = false">
        <section class="health-modal">
          <div class="modal-header">
            <div>
              <p class="eyebrow">用户管理</p>
              <h2>Workbench 用户</h2>
            </div>
            <button type="button" class="ghost-button mini" @click="adminState.open = false">关闭</button>
          </div>

          <div v-if="adminState.loading" class="placeholder-block">
            <strong>正在加载</strong>
            <p>正在读取本地用户与任务历史概况。</p>
          </div>

          <div v-else-if="adminState.error" class="error-diagnostic">
            <strong>用户管理加载失败</strong>
            <p>{{ adminState.error }}</p>
          </div>

          <div v-else class="user-admin-list">
            <article v-for="user in adminState.users" :key="user.username" class="user-admin-card">
              <div>
                <strong>{{ user.username }}</strong>
                <span>{{ user.role }} · {{ user.disabled ? "已禁用" : "启用中" }} · {{ user.locked ? "已锁定" : "未锁定" }}</span>
              </div>
              <div>
                <small>历史任务</small>
                <b>{{ user.history_count || 0 }}</b>
              </div>
              <div>
                <small>最近任务</small>
                <b>{{ user.last_ticker || "无" }}</b>
                <span>{{ user.last_status || "N/A" }}</span>
              </div>
              <div>
                <small>最近登录</small>
                <span>{{ user.last_login_at || "暂无" }}</span>
              </div>
              <div class="user-admin-actions">
                <select
                  :value="user.role"
                  @change="updateManagedUser(user, { role: $event.target.value })"
                >
                  <option value="user">user</option>
                  <option value="admin">admin</option>
                </select>
                <button
                  type="button"
                  class="ghost-button mini"
                  @click="updateManagedUser(user, { disabled: !user.disabled })"
                >
                  {{ user.disabled ? "启用" : "禁用" }}
                </button>
                <button
                  v-if="user.locked"
                  type="button"
                  class="ghost-button mini"
                  @click="updateManagedUser(user, { unlock: true })"
                >
                  解锁
                </button>
                <button type="button" class="ghost-button mini" @click="resetManagedPassword(user)">重置密码</button>
                <button type="button" class="ghost-button mini danger-button" @click="deleteManagedUser(user)">删除账号</button>
              </div>
            </article>
          </div>
        </section>
      </div>
      </template>
    </div>
  `,
}).mount("#app");
