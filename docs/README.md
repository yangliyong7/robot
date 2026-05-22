# 微信返利机器人（OpenClaw 版）

Python 业务后端 + OpenClaw 微信通道。适用于**腾讯云 OpenClaw 镜像**（轻量应用服务器 / 云桌面等已预装 OpenClaw 的环境）。

## 架构

```
同一台腾讯云服务器
├── OpenClaw Gateway（镜像自带） + openclaw-weixin + rebate-router
└── Python FastAPI :8765（本仓库 python -m src.main）
         ↑
    Plugin 通过 127.0.0.1 调用，勿把 8765 暴露公网
```

```
微信 ClawBot → openclaw-weixin → rebate-router Plugin
                                      ↓ HTTP :8765
                               FastAPI → modules/ → 联盟 API
                                      ↓
                               SQLite data/rebate_bot.db（业务数据 + app_config 配置）
```

## 部署步骤

### 1. 拉取代码

SSH 登录服务器后，将本仓库放到例如 `/opt/rebate-bot`：

```bash
cd /opt
git clone <你的仓库地址> rebate-bot
cd rebate-bot
```

业务配置保存在 **`data/rebate_bot.db`** 的 **`app_config`** 表。若仓库已包含该数据库文件，clone 后可直接使用；否则首次启动后需在管理后台填写配置。

### 2. 启动 Python 业务 API

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

mkdir -p logs data

# 前台试跑，确认无报错
python -m src.main

# 确认 OK 后 Ctrl+C，再后台运行：
nohup python -m src.main > logs/api.log 2>&1 &
nohup python -m src.worker.order_sync_worker > logs/sync.log 2>&1 &

curl http://127.0.0.1:8765/v1/health
```

**必须在项目根目录**执行 `python -m src.main`，程序才会读写 `data/rebate_bot.db`。

管理后台地址：**http://127.0.0.1:8765/admin**（仅本机或 SSH 隧道访问，见下文）。

若数据库无配置，在 **系统配置** 中填写联盟密钥、`api_token`、管理密码等。`OPENCLAW_API_CONFIG.host` 保持 `127.0.0.1`，**安全组不要开放 8765 端口**。

**SSH 隧道访问管理后台**（在你自己的电脑上执行）：

```bash
ssh -L 8765:127.0.0.1:8765 root@你的服务器IP
```

然后浏览器打开 http://127.0.0.1:8765/admin 。

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

### 7. 验证

1. 微信私聊发 **「余额」** → 应返回钱包文案
2. 服务器 `logs/api.log` 有 `/v1/wallet/balance` 请求
3. `openclaw plugins inspect rebate-router --runtime` 显示 enabled
4. `curl http://127.0.0.1:8765/v1/health` 返回 `{"status":"ok","mode":"openclaw"}`

若微信有回复但 API 无日志 → Plugin 未装上或未启用。  
若 API 有日志但微信无回复 → 检查 Gateway 日志、`openclaw-weixin` 是否登录成功。

### 8. 常见问题

| 现象 | 处理 |
|------|------|
| `app_config 为空` 警告 | 首次部署正常；在管理后台填配置，或确保 clone 后存在 `data/rebate_bot.db` |
| `logs/api.log: No such file or directory` | 先执行 `mkdir -p logs` |
| `plugins install` 很慢/失败 | `npm config set registry https://registry.npmmirror.com` 后重试 |
| Plugin 装了不生效 | 必须 `openclaw gateway restart` |
| API 连接拒绝 | 确认 `python -m src.main` 在跑，`curl 127.0.0.1:8765/v1/health` |
| Token 401 | 后台 `api_token` 与 `openclaw.json` 里 `apiToken` 不一致 |
| 改配置不生效 | 确认在管理后台已点保存；改 db_path / 日志路径需重启 API |
| 浏览器打不开管理后台 | 8765 仅监听 127.0.0.1，需 SSH 隧道，不要依赖公网 IP |
| Python 与 OpenClaw 分机部署 | 把 `apiBaseUrl` 改成 Python 内网 IP，并限制安全组 |

### 9. 升级 rebate-router

```bash
cd /opt/rebate-bot
git pull
cd openclaw/extensions/rebate-router
openclaw plugins install .
openclaw gateway restart
```
