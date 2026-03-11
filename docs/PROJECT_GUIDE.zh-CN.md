# NetMoniAI 项目总览文档（面向开发者）

> 目标：帮助你快速理解这个仓库里“每一个部分”是干什么的、怎么串起来跑、以及要改功能时该从哪里下手。

---

## 1. 项目一句话

NetMoniAI 是一个 **“本地节点智能体 + 全局控制器 + 可视化前端”** 的网络监控/安全分析系统：

- 本地侧持续采集网络指标，异常时抓包并做攻击识别；
- 识别结果由报告智能体结构化后上报；
- 全局控制器聚合所有节点状态；
- 前端通过 REST + WebSocket 实时展示与问答。

---

## 2. 仓库结构与职责

### 根目录

- `README.md`：项目背景、架构图、快速启动。
- `requirements.txt`：完整 Python 依赖（研究/开发环境）。
- `requirements.runtime.txt`：更轻量运行依赖。
- `CHANGELOG_2026-02-28.md`：阶段性变更记录。
- `LICENSE-*`：双许可证（MIT/Apache-2.0）。

### `backend/`（核心后端）

- `app.py`：当前主 FastAPI 入口（本地 agent pipeline + 全局接口 + WebSocket 挂载）。
- `app1.py`：增强版控制器实验入口（包含 attacker/victim/benign 相关聚合逻辑）。
- `appWebsocket.py`：WebSocket 推送与聊天消息处理（`/ws`）。
- `config.py`：全局队列、默认参数、网卡名等配置。
- `common_classes.py`：Pydantic 数据模型与依赖数据结构。
- `utils.py`：ping 指标采集、默认网关检测。
- `analyze_nodes.py`：离线批量分析 PCAP 并将结果发给全局控制器。
- `nw_agents/`：五个核心 agent（详见第 4 节）。
- `tools/`：抓包与攻击检测/PCAP 解析工具（详见第 6 节）。
- `segregated/`：NS-3 导出的分节点 PCAP 样本目录。
- `lastCapture/`：在线监控时本地抓包输出目录。
- `history.json`：性能监控历史记录（由 `PerformanceMonitoringAgent` 持久化）。

### `frontend/`（React 可视化）

- `src/App.js`：页面路由（Local Controller / Central Controller）。
- `src/components/LocalControllerDashboard.js`：本地控制器监控页（实时指标与告警）。
- `src/components/GlobalControllerDashboard.js`：全局控制器页（节点状态聚合、图表、明细）。
- `src/components/NetworkVisualizer.js`：D3 网络拓扑 + 包流动画。
- `src/components/chatbot.js`、`GlobalChatbot.js`：本地/全局聊天 UI。
- `src/apiService.js`：REST API 访问（当前主要是 `/gcstatuses`）。
- `public/nodes_data.json`、`packets_data.json`：拓扑与包流演示数据。
- `json_parser.py`：将 NetAnim XML 转换为前端可视化 JSON。

### `simulations/`（NS-3 场景）

- `dos-simulation.cc`：8 节点 UDP Flood DoS 场景。
- `port-scan-simulation.cc`：20 节点 TCP 端口扫描场景。
- `README.md`：仿真参数与网络拓扑说明。

### `paper/`

- 论文图和附属材料（架构图等）。

---

## 3. 运行时总数据流（从采集到大屏）

1. `PerformanceMonitoringAgent` 周期采集吞吐、延迟、丢包。
2. 若指标超阈值，触发抓包（`tshark`）并送入安全分析队列。
3. `SecurityAnalysisAgent` 调用检测函数（当前默认 `tools/attack_detection3.py`）得到攻击判断。
4. `ReportingAgent` 结合攻击结果 + 指标 + PCAP 摘要，生成结构化 `NetworkReport`。
5. 报告进入：
   - WebSocket 广播（前端实时刷新）；
   - 或被离线脚本 `analyze_nodes.py` 组装后 POST 到 `/gcreport`。
6. `app.py` 维护 `node_statuses`，供 `/gcstatuses` 和全局面板读取。

---

## 4. `nw_agents/` 五个智能体模块详解

### 4.1 `PerformanceMonitoringAgent.py`

**职责**
- 周期读取网络 IO、外网/网关 ping 指标。
- 维护滑动窗口（`SLIDING_WINDOW_MAXLEN`）。
- 基于阈值决定是否抓包。
- 记录历史到 `history.json`（含是否异常、是否攻击）。

**关键点**
- 抓包命令依赖 `tshark`。
- 异常阈值写死在代码逻辑里（延迟与丢包）。
- 与调参/安全 agent 用 `asyncio.Queue` 解耦。

### 4.2 `ParameterTuningAgent.py`

**职责**
- 依据当前指标 + 最近历史 + 上轮结果，动态给出：
  - 抓包时长 `duration`
  - 检测间隔 `cycle_interval`

**实现方式**
- 通过 `pydantic_ai + Gemini` 输出 `ParameterResult`。

### 4.3 `SecurityAnalysisAgent.py`

**职责**
- 消费待分析 pcap 路径；
- 调用攻击检测函数；
- 输出：攻击队列（给前端）、回传队列（给性能 agent）、报告队列（给 Reporting）。

**关键点**
- 目前 `monitoring_agent.run` 被重写为 `custom_monitoring_run`，直接调用 `detect_attack_func`。
- `raw_bert_output` 作为后续报告的重要输入。

### 4.4 `ReportingAgent.py`

**职责**
- 将攻击结果、指标与 `pcap_analyzer` 摘要拼装成可读且结构化报告。
- 输出 `NetworkReport` 到 `reports_queue`。

**关键点**
- 使用 LLM 生成摘要、可能原因、建议动作、置信度等。

### 4.5 `ChatAgent.py`

**职责**
- 作为聊天问答模型。
- 被 WebSocket 入口用于本地监控问答与全局状态问答。

---

## 5. 后端 API & WebSocket 说明

### REST（`app.py`）

- `POST /gcreport`：接收节点报告并更新 `node_statuses`。
- `GET /gcstatuses`：返回当前节点状态字典。

### WebSocket（`/ws`）

接收/发送消息类型：

- 输入：
  - `chat`：本地监控问答。
  - `global_chat`：全局控制器问答。
- 输出：
  - `metrics`：实时指标。
  - `attack_detection`：攻击检测结果。
  - `network_report`：报告结果。
  - `chat_response` / `global_chat_response`：聊天回复。

---

## 6. `tools/` 工具模块说明

- `attack_detection3.py`（当前主力）
  - `tshark` 将 PCAP 转 CSV；
  - 调用 OpenAI（`o3-2025-04-16`）输出攻击类型+置信度；
  - 回写为“Normal 与攻击类型计数”格式。

- `attack_detection.py`
  - 基于 HuggingFace BERT 的本地包级分类实现（更偏研究原型）。

- `attack_detection2.py` / `attack_detection4.py`
  - 其它实验版本（Gemini/采样策略等），包含较多环境耦合代码。

- `pcap_analyzer.py`
  - 统计 top IP、端口、协议、包长、异常端口等，用于报告辅助。

- `data_collection.py`
  - 简单抓包工具（当前和主流程不完全一致，接口名/网卡配置较旧）。

---

## 7. 前端模块与页面行为

### 7.1 路由

- `/` → `LocalControllerDashboard`
- `/gc` → `GlobalControllerDashboard`

### 7.2 LocalControllerDashboard

- 建立 `ws://localhost:8000/ws`；
- 实时接收并绘制指标（line/bar/pie）；
- 告警时显示 `attack_detection`；
- 内置本地 chat 面板（发送 `type=chat`）。

### 7.3 GlobalControllerDashboard

- 定时拉取 `/gcstatuses`（默认 60s）+ 手动刷新；
- 用 `NetworkVisualizer` 展示节点状态；
- 展示 selected node 的时序图/元数据/包明细；
- 内置全局 chat 面板（发送 `type=global_chat`）。

### 7.4 NetworkVisualizer

- 读取 `public/nodes_data.json` 与 `packets_data.json`；
- 节点状态由后端 `attack_detected` 映射为红/绿；
- 使用 D3 进行力导向微调与包动画。

---

## 8. 离线批处理流程（`analyze_nodes.py`）

适用于 NS-3 生成 PCAP 的批量回放分析。

流程：
1. 扫描 `backend/segregated/segregated_pcaps*` 目录。
2. 逐个 pcap 调 `SecurityAnalysisAgent + ReportingAgent`。
3. 抽取 time-series metrics（`PcapReader`）。
4. 结果附加 `node_ip` 后 POST 到 `http://localhost:8000/gcreport`。
5. 前端全局页即可看到汇总状态。

内置：
- Gemini 速率限制（RPM/RPD）；
- 429 指数退避重试；
- Decimal 转换保证 JSON 可序列化。

---

## 9. 仿真与可视化数据转换

- NS-3 运行生成：PCAP + NetAnim XML。
- `frontend/json_parser.py` 可将 XML 转 `nodes_data.json` 与 `packets_data.json`。
- 前端读取这些 JSON 做拓扑/包流动画。

这让系统同时支持：
- 在线采集监控（真实网卡）；
- 离线仿真回放（NS-3 数据集）。

---

## 10. 配置与依赖要点

### Python

- 推荐先用 `requirements.runtime.txt` 跑通核心流程。
- 研究/训练/实验再用 `requirements.txt`。

### 外部系统依赖

- `tshark`：抓包与 PCAP->CSV 必需。
- 网络权限：抓包通常需要 root/capabilities。

### 环境变量（关键）

- `OPENAI_API_KEY`：`attack_detection3.py` 必需。
- `NETMON_INTERFACE`：覆盖默认网卡名（`config.py`）。

> 注意：仓库里存在 `secretKeys.py`，建议改为环境变量与 `.env` 管理，避免明文密钥。

---

## 11. 你后续改代码时的“定位指南”

- 想改异常触发逻辑：看 `PerformanceMonitoringAgent._should_capture`。
- 想改攻击识别模型：看 `tools/attack_detection3.py` 与 `SecurityAnalysisAgent` 调用点。
- 想改报告字段：看 `common_classes.NetworkReport` + `ReportingAgent`。
- 想加全局统计接口：看 `app.py`（或参考 `app1.py` 的聚合逻辑）。
- 想改前端图表：
  - 本地页：`LocalControllerDashboard.js`
  - 全局页：`GlobalControllerDashboard.js`
  - 拓扑图：`NetworkVisualizer.js`

---

## 12. 当前项目状态评估（基于现有代码）

### 已具备
- 端到端链路完整：采集 → 检测 → 报告 → 推送 → 展示。
- 在线监控与离线批处理两种模式都可跑。

### 需要注意
- 前端大文件中保留了大量历史注释代码，维护成本较高。
- `app.py` 与 `app1.py` 存在并行入口，建议统一主入口策略。
- 部分工具脚本含本机路径/强环境绑定（如 `attack_detection2.py`）。
- 密钥管理方式有改进空间（建议全面 `.env` 化）。

---

## 13. 最小运行建议（开发模式）

1. 启动后端：`uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000`
2. 启动前端：`cd frontend && npm install && npm start`
3. 打开：`http://localhost:3000`

若你要验证离线场景：
1. 先启动后端；
2. 再运行 `backend/analyze_nodes.py`；
3. 打开全局面板查看节点状态变化。

---

## 14. 一句话理解每个子系统

- `backend/nw_agents`：智能体编排核心。
- `backend/tools`：抓包/检测/解析能力库。
- `backend/analyze_nodes.py`：离线数据“灌入”全局控制器。
- `backend/app.py`：服务对外入口（API + WS）。
- `frontend/src/components`：监控可视化与交互界面。
- `simulations`：可控攻击场景数据生产端。
- `paper`：论文与架构说明材料。

