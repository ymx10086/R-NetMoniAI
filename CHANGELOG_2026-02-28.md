# NetMoniAI 修改记录（2026-02-28）

## 修改概览
本次主要目的是让项目在 Linux 环境下更容易直接运行，并移除机器相关的硬编码路径。

---

## 1) backend/config.py
**修改目的**：让抓包网卡可配置，避免默认 `en0` 在 Linux 上不可用。

**变更内容**：
- 将固定网卡配置：
  - `INTERFACE = "en0"`
- 改为环境变量可配置：
  - `INTERFACE = os.getenv("NETMON_INTERFACE", "wlp9s0")`

**效果**：
- 可通过环境变量覆盖：`NETMON_INTERFACE=eno1` 或 `NETMON_INTERFACE=wlp9s0`。
- 不再依赖 macOS 风格网卡名。

---

## 2) backend/analyze_nodes.py
**修改目的**：修复离线分析脚本中与开发者本机绑定的绝对路径。

**变更内容**：
- 新增导入：`from pathlib import Path`
- 删除硬编码路径读取：
  - `/Users/thanikella_nikhil/.../frontend/public/nodes_data.json`
- 改为仓库相对路径解析：
  - `project_root = Path(__file__).resolve().parent.parent`
  - `nodes_data_path = project_root / "frontend" / "public" / "nodes_data.json"`
- 增加兜底逻辑：
  - 当 `nodes_data.json` 不存在时，自动回退为 `192.168.1.x` 的索引映射。

**效果**：
- 离线脚本可跨机器运行，不依赖原作者目录结构。
- 缺少前端数据文件时仍可继续执行。

---

## 3) backend/secretKeys.py（新建）
**修改目的**：补齐项目缺失的密钥配置文件，避免导入失败。

**文件内容**：
- 从环境变量读取：
  - `GEMINI_API_KEY`
  - `GEMINI_API_KEYS`（支持逗号分隔多 Key）
- 当只提供单个 `GEMINI_API_KEY` 时，自动生成 `GEMINI_API_KEYS` 列表。

**注意**：
- 该文件已被 `.gitignore` 忽略（规则：`backend/secretKeys.py`），不会被 Git 跟踪。
- 这符合密钥文件的安全实践。

---

## 4) requirements.runtime.txt（新建）
**修改目的**：提供一份可在 Python 3.11 上安装成功的最小运行依赖，绕过原始 `requirements.txt` 中不可用锁定版本。

**变更内容**：
- 新增运行时依赖清单：
  - FastAPI/Uvicorn
  - pydantic-ai 相关
  - 抓包与系统监控相关（scapy、pyshark、psutil、netifaces）
  - API 客户端相关（openai、httpx、aiohttp）

**效果**：
- 可用 `pip install -r requirements.runtime.txt` 快速完成后端运行所需安装。

---

## 当前 Git 状态
- 已跟踪改动：
  - `backend/config.py`
  - `backend/analyze_nodes.py`
  - `requirements.runtime.txt`
  - `CHANGELOG_2026-02-28.md`
- 未跟踪但已创建（被忽略）：
  - `backend/secretKeys.py`

---

## 运行时建议（对应本次修改）
- 启动前设置网卡：
  - `export NETMON_INTERFACE=wlp9s0`（或 `eno1`）
- 设置密钥：
  - `export GEMINI_API_KEY=...`
  - `export OPENAI_API_KEY=...`
