# 微信返利机器人（OpenClaw 版）

Python 业务后端 + OpenClaw 微信通道。核心业务在 `platforms/`、`modules/`，微信收发由 OpenClaw Plugin 完成。

## 架构

```
微信 ClawBot → openclaw-weixin → rebate-router Plugin（零 token 硬路由）
                                      ↓ HTTP :8765
                               FastAPI → modules/ → 联盟 API
                                      ↓
                               SQLite（业务数据 + app_config 配置）
```

## 快速启动

### 1. 依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

**业务配置已存入 SQLite**，不再通过编辑 `config/config.py` 填写密钥。

| 方式 | 说明 |
|------|------|
| **管理后台（推荐）** | 启动 API 后访问 [http://127.0.0.1:8765/admin](http://127.0.0.1:8765/admin) → **系统配置** |
| **首次部署** | 在管理后台「系统配置」填写；配置保存在 SQLite `app_config` 表 |
| **环境变量（可选）** | `ROBOT_DB_PATH` 可覆盖数据库文件路径（默认 `data/rebate_bot.db`） |

OpenClaw 插件侧参考 `openclaw/openclaw.config.example.json` 配置 rebate-router；其中 **`apiToken` 须与后台「OpenClaw API → api_token」一致**。

### 3. 启动 Python

```bash
# 终端 1：业务 API + 管理后台
python -m src.main

# 终端 2：联盟订单同步（可选）
python -m src.worker.order_sync_worker
```

Windows（PowerShell）：

```powershell
.venv\Scripts\python.exe -m src.main
.venv\Scripts\python.exe -m src.worker.order_sync_worker
```

验证：

```bash
curl http://127.0.0.1:8765/v1/health
```

### 4. 启动 OpenClaw

```bash
npm install -g openclaw@latest
openclaw plugins install "@tencent-weixin/openclaw-weixin"
openclaw plugins enable rebate-router
openclaw channels login --channel openclaw-weixin
openclaw gateway restart
```

将 `openclaw/extensions/rebate-router` 加入 OpenClaw workspace。

## 目录结构

```
src/
├── main.py / api_server.py       # API 入口
├── api/                          # HTTP 接口 + 管理后台 /admin
├── worker/order_sync_worker.py   # 联盟订单轮询
├── modules/                      # 转链、比价、本地生活
├── platforms/                    # 各联盟 API
└── database.py                   # SQLite 业务表

config/
├── config.py                     # 数据库路径 + 空占位（值由 DB 填充）
├── settings_store.py             # 读/写 SQLite 配置
├── config_repository.py          # app_config 表读写
└── schema_builder.py             # 根据库内 JSON 生成后台表单

data/rebate_bot.db                # SQLite（users/orders/… + app_config）
openclaw/extensions/rebate-router/  # JS 硬路由插件
```

## 配置存储说明

配置保存在 **`data/rebate_bot.db`** 的 **`app_config`** 表中，按配置块存 JSON（共 19 行，如 `REBATE_CONFIG`、`COMMISSION_CONFIG` 等）。

```
管理后台保存 → SettingsStore → app_config 表 → 同步内存 config.config → 业务代码立即读取
```

- 后台修改后**即时写库**，当前进程**立即生效**（无需改代码）
- 密钥字段留空表示**不修改**原值
- **数据库路径、日志路径** 修改后需**重启** `python -m src.main` 才完全生效
- 查看配置：`sqlite3 data/rebate_bot.db "SELECT config_key, updated_at FROM app_config;"`

## 管理后台 Web

地址：**http://127.0.0.1:8765/admin**

登录密码在 **系统配置 → 管理后台 → password**（或侧边栏修改登录密码）。首次部署请尽快修改默认密码。

| 菜单 | 功能 |
|------|------|
| 数据概览 | 用户/订单/提现等统计 |
| 用户管理 | 用户列表，点击 wxid 查看详情（订单、提现、流水、签到） |
| 订单管理 | 筛选、**手动同步联盟订单**、**手动结算** |
| 提现审核 | 通过 / 驳回 |
| 资金流水 | 返利与提现流水 |
| 签到记录 | 签到历史 |
| 系统配置 | 全部业务配置（微信、防封、联盟密钥、返利比例、OpenClaw API 等） |

管理页与 OpenClaw Plugin 共用同一进程，**仅建议本机或 SSH 隧道访问**，不要暴露 8765 到公网。

## 用户指令

| 指令 | 说明 |
|------|------|
| 发商品链接/淘口令 | 转链查券 |
| 余额 / 订单 / 提现 | 钱包 |
| 签到 | 每日奖励（规则在后台「签到奖励」配置） |

## API（Plugin 内部调用）

请求头：`Authorization: Bearer <api_token>`

| 路径 | 说明 |
|------|------|
| POST /v1/convert | 转链 |
| GET /v1/wallet/balance | 余额 |
| POST /v1/wallet/checkin | 签到 |
| GET /v1/notifications/pending | 拉取结算通知 |
| GET /v1/health | 健康检查 |

## 注意

- 需微信 8.0.70+ 且 ClawBot 灰度；当前以**单聊**为主
- 结算通知无法主动推送，写入 `pending_notifications`，用户下次对话时 Plugin 拉取
- 比价逻辑在 `src/modules/price_comparison.py`，转链失败时自动触发

---

## 腾讯云 OpenClaw 镜像：接入 rebate-router Plugin

适用于轻量应用服务器 / 云桌面等**已预装 OpenClaw** 的腾讯云镜像。镜像里通常已有 `openclaw` 命令和 Gateway，你只需部署本项目的 **Python API** 和 **rebate-router 插件**。

### 整体拓扑

```
同一台腾讯云服务器
├── OpenClaw Gateway（镜像自带） + openclaw-weixin + rebate-router
└── Python FastAPI :8765（本仓库 src/main.py）
         ↑
    Plugin 通过 127.0.0.1 调用，勿把 8765 暴露公网
```

### 1. 上传项目代码

SSH 登录服务器后，将本仓库放到例如 `/opt/rebate-bot`：

```bash
cd /opt
git clone <你的仓库地址> rebate-bot
cd rebate-bot
```

### 2. 启动 Python 业务 API（同机）

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

nohup python -m src.main > logs/api.log 2>&1 &
nohup python -m src.worker.order_sync_worker > logs/sync.log 2>&1 &

curl http://127.0.0.1:8765/v1/health
```

首次启动后浏览器打开 **http://127.0.0.1:8765/admin**，在 **系统配置** 中填写联盟密钥、`api_token`、管理密码等。

`OPENCLAW_API_CONFIG.host` 保持 `127.0.0.1`，**安全组不要开放 8765 端口**。

### 3. 安装微信 Channel 插件（官方）

```bash
npm config set registry https://registry.npmmirror.com

openclaw plugins install "@tencent-weixin/openclaw-weixin"
openclaw plugins enable openclaw-weixin
```

### 4. 安装本仓库 rebate-router（本地 Plugin）

```bash
cd /opt/rebate-bot/openclaw/extensions/rebate-router
openclaw plugins install .
openclaw plugins enable rebate-router
```

确认已加载：

```bash
openclaw plugins list
openclaw plugins inspect rebate-router --runtime
```

### 5. 写入 Plugin 配置

将 `openclaw/openclaw.config.example.json` 中的 `plugins.entries.rebate-router` 合并进 OpenClaw 主配置。

配置文件常见位置：

- `~/.openclaw/openclaw.json`
- 或 Docker 挂载目录，如 `/data/openclaw/openclaw.json`

**关键：`apiToken` 须与管理后台「OpenClaw API → api_token」一致**（存于 SQLite `app_config` 表）。

```json
{
  "plugins": {
    "allow": ["rebate-router", "openclaw-weixin"],
    "entries": {
      "rebate-router": {
        "enabled": true,
        "config": {
          "apiBaseUrl": "http://127.0.0.1:8765",
          "apiToken": "与后台 OpenClaw API 中 api_token 相同",
          "passiveMode": true
        },
        "hooks": {
          "allowConversationAccess": true
        }
      },
      "openclaw-weixin": {
        "enabled": true
      }
    }
  }
}
```

也可用命令行写入：

```bash
openclaw config set plugins.entries.rebate-router.enabled true
openclaw config set plugins.entries.rebate-router.config.apiBaseUrl "http://127.0.0.1:8765"
openclaw config set plugins.entries.rebate-router.config.apiToken "你的token"
openclaw config set plugins.entries.rebate-router.config.passiveMode true
```

### 6. 绑定微信并重启 Gateway

```bash
openclaw channels login --channel openclaw-weixin
openclaw gateway restart
```

### 7. 验证 Plugin 是否生效

1. 微信私聊发 **「余额」** → 应返回钱包文案
2. 服务器 API 日志有 `/v1/wallet/balance` 请求
3. `openclaw plugins inspect rebate-router --runtime` 显示 enabled

若微信有回复但 API 无日志 → Plugin 未装上或未启用。  
若 API 有日志但微信无回复 → 检查 Gateway 日志、`openclaw-weixin` 是否登录成功。

### 8. 常见问题（腾讯云镜像）

| 现象 | 处理 |
|------|------|
| `plugins install` 很慢/失败 | `npm config set registry https://registry.npmmirror.com` 后重试 |
| Plugin 装了不生效 | 必须 `openclaw gateway restart` |
| API 连接拒绝 | 确认 `python -m src.main` 在跑，`curl 127.0.0.1:8765/v1/health` |
| Token 401 | 后台 `api_token` 与 `openclaw.json` 里 `apiToken` 不一致 |
| 改配置不生效 | 确认在管理后台已点保存；改 db_path / 日志路径需重启 API |
| Python 与 OpenClaw 分机部署 | 把 `apiBaseUrl` 改成 Python 内网 IP，并限制安全组 |

### 9. 升级 rebate-router

```bash
cd /opt/rebate-bot
git pull
cd openclaw/extensions/rebate-router
openclaw plugins install .
openclaw gateway restart
```
