# PayRail Hub — Local Payment Link Extractors

Multi-rail toolkit for extracting local payment links (UPI, iDEAL, Pix, GoPay, MoMo, DANA, ...) from hosted checkout flows, with locale-aware autofill billing identities.

> Fork lineage: [Niceswz/chatgpt-upi-extractor](https://github.com/Niceswz/chatgpt-upi-extractor) (UPI rail). Hardened for public consumption: no tracked databases, no hardcoded personal identities, masked credential output, env-driven config.

## 项目简介

**PayRail Hub** 是一个 FastAPI + SQLite 工具集，自动生成 ChatGPT Plus 的本地支付链接（适用于 PhonePe / GPay / Paytm 等支付应用），并附带 locale 感知的账单身份自动填充模块。

## 主要功能

- 🔐 **密码保护管理后台**（Session Cookie + CSRF 双重验证）— 需在 `.env` 中配置 `CHATUPI_PASSWORD_HASH` 激活；留空仅限本机调试
- 🗄️ **SQLite 任务队列**（单并发提取，任务记录持久化）
- 🌏 **双代理策略**：结账/UPI 环节走印度代理，促销环节走越南代理
- 👤 **自动填充账单身份**（`api_python/identity.py`）：按国家生成本地化姓名/地址/邮编/电话，支持 IN / ID / NL / BR / VN / PH / TH，seed 可复现，env 变量可覆盖任意字段
- 🔄 **在线 / 维护模式**切换（管理员可动态控制）
- ⚛️ **React 组件**，可嵌入到更大的门户类前端项目中

## Rails

| Rail | 国家 | 状态 |
|---|---|---|
| UPI | 🇮🇳 IN | ✅ 可用（本仓库核心） |
| iDEAL / Pix / GoPay / MoMo / DANA | 🇳🇱 🇧🇷 🇮🇩 🇻🇳 🇵🇭 | 🧭 identity 模块已支持这些 locale 的账单身份 |

## 项目结构（部署示例）

```
payrail-hub/
  .env                 # 密钥与代理配置（禁止提交到版本库）
  .env.example         # 环境变量模板
  data/                # SQLite 数据库（gitignore）
  run-output/          # 任务调试产物（gitignore）
  api_python/          # FastAPI 应用包
    identity.py        # locale-aware autofill billing identity
    upi_link_service.py  # UPI rail
  scripts/             # CLI 工具
  src/components/      # React 嵌入组件
  deploy/              # systemd + nginx 示例
```

服务仅监听 `127.0.0.1:8104`，通过 Nginx 以 `/CHATUPI/` 路径对外暴露。

## 环境变量配置

将 `.env.example` 复制为 `.env`（生产环境使用 `/opt/chatupi/.env`），并填写以下变量：

| 变量名 | 说明 |
|---|---|
| `CHATUPI_SECRET_KEY` | Session Cookie 随机密钥（至少 48 字符） |
| `CHATUPI_PASSWORD_HASH` | PBKDF2 密码哈希（格式：`pbkdf2_sha256$...`）— 留空则管理后台不鉴权 |
| `CHATUPI_BASE_PATH` | 公开访问路径，例如 `/CHATUPI` |
| `CHATUPI_DATABASE` | SQLite 数据库文件路径（默认 `data/chatupi.sqlite3`，相对解析） |
| `CHATUPI_RETENTION_DAYS` | 任务记录保留天数（默认 30 天） |
| `CHATUPI_HOURLY_LIMIT` | 每用户每小时最大任务数（默认 10） |
| `CHATUPI_ALLOWED_HOSTS` | 允许访问的主机名（逗号分隔，默认 `localhost,127.0.0.1`） |
| `VERIFY_APP_ROOT` | 项目根目录（用于清理 run-output；默认仓库根） |
| `UPI_LINK_PROXY` | 印度出口代理 URL |
| `UPI_LINK_PROMOTION_PROXY` | 越南促销代理 URL |

可选代理专用文件：将 `env_upi_link.txt.example` 复制为 `env_upi_link.txt`。

### 账单身份（可选覆盖）

UPI rail 默认自动生成印度账单身份（locale-aware，从 `identity.py` 随机生成）。如需固定身份，可覆盖任意字段：

```
UPI_BILLING_NAME=...
UPI_BILLING_LINE1=...
UPI_BILLING_CITY=...
UPI_BILLING_STATE=...
UPI_BILLING_POSTAL=...
```

未设置的自动填充字段将从 `identity.py` 按 locale 随机生成。

### Identity API

```python
from api_python.identity import generate_billing_identity, env_billing_identity

# 随机印度身份
ident = generate_billing_identity("IN")

# seed 可复现（同一 seed 同一身份）
ident = generate_billing_identity("VN", seed="job-123")

# env 覆盖 + 自动填充兜底
ident = env_billing_identity("IN", env_prefix="UPI_BILLING_")
```

支持国家：IN, ID, NL, BR, VN, PH, TH（邮编格式与真实国家规则一致）。

### 生成密码哈希

```bash
python -c "from api_python.security import hash_password; print(hash_password('你的密码'))"
```

## 本地运行

```bash
# 1. 确保安装了 venv 模块（如果没装）
sudo apt update
sudo apt install python3-venv python3-full -y

# 2. 在项目目录下创建虚拟环境（名字叫 venv，可自定义）
python3 -m venv venv

# 3. 激活虚拟环境
source venv/bin/activate   # Linux / macOS
# 或 Windows: venv\Scripts\activate

# 4. 现在 pip 就是虚拟环境里的了，正常安装
pip install -r requirements.txt
export CHATUPI_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export CHATUPI_PASSWORD_HASH="$(python -c 'from api_python.security import hash_password; print(hash_password("changeme"))')"
export CHATUPI_ALLOWED_HOSTS="localhost,127.0.0.1"
python -m uvicorn api_python.main:app --host 127.0.0.1 --port 8104
```

打开浏览器访问：`http://127.0.0.1:8104/CHATUPI/login`（或你配置的 `CHATUPI_BASE_PATH`）

> ⚠️ **请只使用单个 Uvicorn Worker**：提取队列和实时任务状态存储在进程内存中，多 Worker 会导致状态不一致。

## 生产部署

`deploy/` 目录中提供了 systemd 服务单元文件和 Nginx 配置示例，根据你的环境修改路径、用户名和主机名即可。**切勿将真实密钥、代理凭证或生产主机名提交到代码仓库。**

## 安全说明

- Session JSON / Access Token 仅在当前任务的内存中使用，不以明文写入 SQLite。
- 控制台显示的代理 URL 已做脱敏处理（掩码）。
- 所有错误信息在返回给客户端前均经过脱敏。
- `.env` 文件、数据库文件、token dump 均已在 `.gitignore` 中排除。

## 可选模块

- **`chatgpt_rt_oauth`**（可选）：如未安装，审批请求将在没有 OpenAI Sentinel Token 的情况下运行，可能会降低对风控机制的成功率。
- **`src/components/`**：React 嵌入组件，供宿主门户项目使用。已附带 `src/utils/`、`src/constants/` 及相关 Stub，可独立解析导入。宿主项目仍需自行安装 React 和 `lucide-react`。

## 前端依赖（仅嵌入组件）

```text
react
lucide-react
```

本仓库不包含完整的 SPA 构建；核心产品是 `api_python/templates/` 下的 FastAPI 管理控制台。

## 许可证

MIT — 详见 [LICENSE](LICENSE)。

---

## 📢 Telegram

[Free\_to\_AI](https://t.me/Free_to_AI) — AI 平台福利、限免资源情报。

## 友情链接

**[linux.do](https://linux.do)**
