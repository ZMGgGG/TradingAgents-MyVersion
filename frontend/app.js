const { createApp, computed, onMounted, reactive, ref, watch } = Vue;

createApp({
  setup() {
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
      analysisDate: "2026-06-01",
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
    const selectedAlphaView = ref("selected");
    const showAllAlphaHistory = ref(false);
    const showAllAlphaRegistry = ref(false);
    const alphaLibrary = reactive({
      ticker: "",
      loading: false,
      error: "",
      data: null,
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
      const date = new Date(ts);
      if (Number.isNaN(date.getTime())) {
        return String(ts).slice(11, 19) || String(ts);
      }
      return date.toLocaleTimeString("zh-CN", { hour12: false });
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
      modules.push({ id: "extras", label: "附加功能", desc: "回测与因子" });
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
              updated_at: new Date().toISOString(),
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
          updated_at: item.updated_at || item.persisted_at || new Date().toISOString(),
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
      taskHistory.value = Array.from(byId.values()).slice(0, 50);
      if (!selectedTaskRunId.value && taskHistory.value.length > 0) {
        selectedTaskRunId.value = taskHistory.value[0].run_id;
      }
      persistTaskHistory();
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
            const snapshot = await fetchJson(`/api/runs/${selectedTaskRunId.value}`);
            syncBackendQueue(snapshot.queue || {});
            applyRunSnapshot(snapshot);
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
        updated_at: snapshot.updated_at || new Date().toISOString(),
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
          updated_at: new Date().toISOString(),
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
              updated_at: new Date().toISOString(),
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
            updated_at: new Date().toISOString(),
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
      try {
        const parsed = JSON.parse(message);
        return parsed.message || parsed.error || message;
      } catch (error) {
        return message || "请求失败。";
      }
    }

    async function fetchJson(url, options = {}) {
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
        throw new Error(message || `HTTP ${response.status}`);
      }

      return response.json();
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
        applyFormSnapshot(JSON.parse(raw));
        logs.value.unshift("[system] 已载入你的默认任务参数");
        return true;
      } catch (error) {
        logs.value.unshift("[warning] 默认任务参数读取失败，已使用系统默认值");
        return false;
      }
    }

    function saveDefaultParams() {
      localStorage.setItem(
        `tradingagents_workbench_default_params_v2_${userId}`,
        JSON.stringify(snapshotForm())
      );
      logs.value.unshift("[system] 已将当前任务参数设为默认");
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
        savedAt: new Date().toISOString(),
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

    async function pollRun(runId) {
      if (!backend.connected || !runId) {
        return;
      }

      try {
        const snapshot = await fetchJson(`/api/runs/${runId}`);
        syncBackendQueue(snapshot.queue || {});
          applyRunSnapshot(snapshot);
          if (snapshot.status === "completed" || snapshot.status === "failed" || snapshot.status === "cancelled") {
            if (snapshot.status === "completed") {
              activeWorkbenchModule.value = "result";
              resetMainScroll();
            } else {
              showRunProgressTab();
            }
          window.clearInterval(pollTimer);
          pollTimer = null;
          refreshQueueAfterTerminal();
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
              updated_at: new Date().toISOString(),
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
      form.analysisDate = "2026-06-01";
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
      form.backtestInitialCapital = "100000";
      form.backtestHoldingDays = "5,10,20";
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
      copyAgentOutput,
      commandPreview,
      deleteManagedUser,
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
      currentDecisionDetails,
      currentRunningAgent,
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
      loadAlphaLibrary,
      loadServerHistory,
      loadPreset,
      logs,
      nextPendingAgent,
      outputLanguages,
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
            <span>{{ selectedTaskView.ticker || form.ticker }} · {{ selectedTaskView.status || "idle" }}</span>
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
            <div class="build-tag">UI Build 2026-07-15S</div>
          </div>
        </header>

        <section class="current-run-strip panel">
          <div class="current-run-main">
            <span class="run-phase" :class="{ live: selectedTaskView.status === 'queued' || selectedTaskView.status === 'running' || selectedTaskView.status === 'cancelling' }">
              {{ selectedTaskView.phase || "待运行" }}
            </span>
            <div>
              <strong>{{ selectedTaskView.ticker || form.ticker }}</strong>
              <small>{{ selectedTaskView.payload?.analysis_date || form.analysisDate }} · {{ selectedTaskView.status || "idle" }} · {{ selectedTaskView.elapsed || "00:00" }}</small>
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
                    <span :class="'status-' + (item.status || 'pending')">{{ item.status || 'pending' }}</span>
                  </div>
                </button>
                <p>{{ item.provider }} · {{ item.phase }}</p>
                <div class="history-date-row">
                  <small>分析日期 {{ item.payload?.analysis_date || "N/A" }}</small>
                  <small>运行时间 {{ item.updated_at || "N/A" }}</small>
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
          v-show="activeWorkbenchModule === 'run' || (simpleMode && activeWorkbenchModule === 'history')"
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
                <p>先选股票/币种、模型与语言，再决定是否附加回测、报告评估和完成后更新因子库。</p>
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
              <span class="group-label">运行后附加功能</span>
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
                  <span>{{ item.rating || item.status || "pending" }}</span>
                </button>
                <small>{{ item.payload?.analysis_date || "N/A" }} · {{ item.elapsed || "00:00" }}</small>
                <button type="button" class="ghost-button mini" @click="rerunHistoryItem(item)">重跑</button>
              </article>
            </div>
            <p v-else class="simple-empty">{{ historySearch ? "没有匹配当前搜索条件的任务。" : "完成后的任务会自动保存在这里。" }}</p>
          </section>
        </section>

        <section
          v-show="['agents', 'result', 'timeline', 'logs', 'report', 'extras', 'params'].includes(activeWorkbenchModule)"
          class="inspect-column module-panel-main"
        >
          <section class="result-panel">
          <article v-show="activeWorkbenchModule !== 'agents'" class="panel selection-banner">
            <div class="selection-banner-copy">
              <span>当前查看任务</span>
              <strong>{{ selectedTaskView.ticker || form.ticker }}</strong>
              <small>{{ selectedTaskView.payload?.analysis_date || form.analysisDate }} · {{ selectedTaskView.status || "idle" }}</small>
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
            v-show="['result', 'timeline', 'logs', 'report', 'extras', 'params'].includes(activeWorkbenchModule)"
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

            <div v-else-if="activeWorkbenchModule === 'extras'" class="feature-summary">
              <div class="feature-grid">
                <article class="feature-card">
                  <span>报告保存</span>
                  <strong>{{ (selectedTaskView.attachments || {}).report_saved ? "已启用" : "未启用" }}</strong>
                  <p>{{ (selectedTaskView.attachments || {}).report_path || "无" }}</p>
                  <button
                    type="button"
                    class="ghost-button mini"
                    :disabled="!(selectedTaskView.attachments || {}).report_saved"
                    @click="downloadReport"
                  >
                    下载报告
                  </button>
                </article>
                <article class="feature-card">
                  <span>报告评估</span>
                  <strong>{{ (selectedTaskView.attachments || {}).evaluation_enabled ? "已启用" : "未启用" }}</strong>
                  <p>{{ (selectedTaskView.attachments || {}).evaluation_summary || "无" }}</p>
                </article>
                <article class="feature-card feature-wide">
                  <span>Backtest</span>
                  <strong>{{ (selectedTaskView.attachments || {}).backtest_enabled ? "已启用" : "未启用" }}</strong>
                  <p>{{ (selectedTaskView.attachments || {}).backtest_summary || "无" }}</p>
                  <div v-if="selectedBacktestDetail.length" class="feature-detail">
                    <label class="field full">
                      <span>回测结果视图</span>
                      <select v-model="selectedBacktestView">
                        <option value="overview">Overview</option>
                        <option value="trades">Trades</option>
                        <option value="raw">Raw JSON</option>
                      </select>
                    </label>
                    <div v-if="selectedBacktestView === 'overview'" class="metric-table">
                      <div class="metric-row metric-head">
                        <span>Days</span>
                        <span>Return</span>
                        <span>Alpha</span>
                        <span>Win</span>
                        <span>Sharpe</span>
                        <span>Drawdown</span>
                      </div>
                      <div v-for="item in selectedBacktestDetail" :key="item.holding_days" class="metric-row">
                        <span>{{ item.holding_days }}d</span>
                        <span>{{ item.resolved ? formatPercent(item.trade?.executed_return) : "No data" }}</span>
                        <span>{{ item.resolved ? formatPercent(item.trade?.executed_alpha_return) : "No data" }}</span>
                        <span>{{ item.resolved ? formatPercent(item.metrics?.win_rate) : "No data" }}</span>
                        <span>{{ item.resolved ? formatNumber(item.metrics?.sharpe_ratio, 4) : "No data" }}</span>
                        <span>{{ item.resolved ? formatPercent(item.metrics?.max_drawdown) : "No data" }}</span>
                      </div>
                    </div>
                    <div v-else-if="selectedBacktestView === 'trades'" class="detail-stack">
                      <div v-for="item in selectedBacktestDetail" :key="item.holding_days" class="detail-card">
                        <strong>{{ item.holding_days }}d</strong>
                        <p v-if="!item.resolved">{{ item.reason || "未解析到可回测交易或未来价格数据。" }}</p>
                        <div v-else class="kv-grid">
                          <span>Action</span><b>{{ item.trade?.action || "N/A" }}</b>
                          <span>Rating</span><b>{{ item.trade?.rating || "N/A" }}</b>
                          <span>Position</span><b>{{ formatPercent(item.trade?.target_position_size) }}</b>
                          <span>Capital</span><b>{{ formatNumber(item.trade?.ending_capital) }}</b>
                          <span>Benchmark</span><b>{{ item.trade?.benchmark || "N/A" }}</b>
                          <span>Confidence</span><b>{{ formatPercent(item.trade?.confidence) }}</b>
                        </div>
                      </div>
                    </div>
                    <pre v-else>{{ JSON.stringify(selectedBacktestDetail, null, 2) }}</pre>
                  </div>
                </article>
                <article class="feature-card feature-wide">
                  <span>完成后更新因子库</span>
                  <strong>{{ (selectedTaskView.attachments || {}).alpha_mining_enabled ? "已启用" : "未启用" }}</strong>
                  <p>{{ (selectedTaskView.attachments || {}).alpha_mining_summary || "无" }}</p>
                  <div v-if="(selectedTaskView.attachments || {}).alpha_mining_detail" class="feature-detail">
                    <label class="field full">
                      <span>Alpha 因子结果</span>
                      <select v-model="selectedAlphaView">
                        <option value="selected">Selected Alpha</option>
                        <option value="metrics">Signal Metrics</option>
                        <option value="summary">Alpha Summary</option>
                        <option value="raw">Raw JSON</option>
                      </select>
                    </label>
                    <div v-if="selectedAlphaView === 'selected'" class="alpha-panel">
                      <div v-if="Object.keys(selectedAlphaDetail.selected_alpha || {}).length" class="kv-grid">
                        <template v-for="(value, key) in selectedAlphaDetail.selected_alpha" :key="key">
                          <span>{{ key }}</span>
                          <b>{{ formatAlphaValue(value) }}</b>
                        </template>
                      </div>
                      <p v-else>本次任务没有返回 selected_alpha 详情。</p>
                    </div>
                    <div v-else-if="selectedAlphaView === 'metrics'" class="metric-strip">
                      <div>
                        <span>Signal Score</span>
                        <strong>{{ formatNumber(selectedAlphaDetail.signal_score, 4) }}</strong>
                      </div>
                      <div>
                        <span>Confidence</span>
                        <strong>{{ formatPercent(selectedAlphaDetail.confidence) }}</strong>
                      </div>
                      <div>
                        <span>Registry</span>
                        <strong>{{ selectedAlphaDetail.registry_file || "N/A" }}</strong>
                      </div>
                    </div>
                    <div v-else-if="selectedAlphaView === 'summary'" class="alpha-summary">
                      <pre>{{ formatAlphaValue(selectedAlphaDetail.summary) }}</pre>
                    </div>
                    <pre v-else>{{ JSON.stringify(selectedAlphaDetail, null, 2) }}</pre>
                  </div>
                </article>
              </div>
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
