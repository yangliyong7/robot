# 微信返利机器人（wxauto 版）

基于 **wxauto4** 驱动 PC 微信客户端，监听好友/群聊消息并自动回复。业务逻辑与 SQLite 数据库保持不变。

## 架构

```
Windows 电脑（PC 微信已登录）
└── py -m src.main  ← 一键启动：机器人 + 管理后台 + 订单同步

好友/群友 → 给你的微信发消息 → wxauto 捕获 → 转链/余额/签到 → 自动回复
                                              ↓
                               SQLite data/rebate_bot.db
```

## 环境要求


| 项目     | 要求                                            |
| ------ | --------------------------------------------- |
| 系统     | **Windows**（wxauto 依赖 UI 自动化）                 |
| 微信     | PC 微信已登录并保持运行                                 |
| Python | 3.9+                                          |
| wxauto | Python 3.13 推荐 `wxautox4`（见 requirements.txt） |


> wxauto4 对微信版本有要求，若连接失败请参考 [wxauto 文档](https://docs.wxauto.org/) 确认版本兼容。

## 部署步骤

### 1. 安装依赖

```powershell
cd E:\workspace\robot
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
mkdir logs, data -Force
```

### 2. 一键启动（推荐）

> 说明：`src.main` 默认会同时启动 **管理后台 + 订单同步 + 微信机器人**（3 个独立进程），你只需要跑一条命令。

```powershell
py -m src.main
```

### 3. 按需启动（可选）

`src.main` 支持通过参数指定启动哪些进程（默认全启动）：

```powershell
# 仅启动管理后台 + 订单同步（本机没装微信/不装 wxauto 时用这个）
py -m src.main --no-bot

# 只启动管理后台（用于首次配置）
py -m src.main --start api --no-bot --no-worker

# 只启动订单同步
py -m src.main --start worker --no-bot --no-api

# 只启动机器人（不启后台/同步）
py -m src.main --start bot --no-api --no-worker
```

如果你更喜欢用 PowerShell “分开拉起”（分别开/关或跑在不同窗口），也可以用下面方式：它会在后台启动管理后台和订单同步，然后以前台方式启动机器人（方便看日志与 Ctrl+C 停止）。

```powershell
# 管理后台（后台运行）
Start-Process -NoNewWindow -FilePath py -ArgumentList "-m","src.api_server"

# 订单同步 worker（后台运行）
Start-Process -NoNewWindow -FilePath py -ArgumentList "-m","src.worker.order_sync_worker"

# 微信机器人（前台运行）
py -m src.main
```

### 4. 首次配置（管理后台）

```powershell
py -m src.main --start api --no-bot --no-worker
```

浏览器打开 [http://127.0.0.1:8765/admin](http://127.0.0.1:8765/admin) ，配置：

- **管理后台**：登录密码
- **联盟密钥**：淘宝/京东/拼多多
- **微信机器人**：被动模式、群聊回复策略、**自动通过好友申请 / 群邀请** 等
- **防封限流**：回复间隔

### 5. 单独启动微信机器人（仅需要机器人时）

**先确保 PC 微信已登录**，再运行：

```powershell
py -m src.main --start bot --no-api --no-worker
```

程序会通过 wxauto 连接微信，监听新消息并自动回复。

### 6. 单独启动订单同步（仅需要同步时，另开终端）

```powershell
py -m src.main --start worker --no-bot --no-api
```

### 7. 无微信环境的自动回复测试

本机没有微信客户端 / 不装 wxauto 时，仍可测试完整路由与回复逻辑：

**方式 A：管理后台（推荐）**

1. 启动：`py -m src.main --no-bot`
2. 打开 [http://127.0.0.1:8765/admin](http://127.0.0.1:8765/admin) → **回复测试**
3. 粘贴用户消息（如淘宝分享文案、余额、帮助），点击「发送并获取回复」

**方式 B：命令行**

```powershell
py -m src.test_reply "余额"
py -m src.test_reply --text "【淘宝】假一赔四 https://e.tb.cn/..." --wxid test_user
```

**方式 C：HTTP API**（需配置 `API_SERVER_CONFIG.api_token`）

```powershell
curl -X POST http://127.0.0.1:8765/v1/bot/reply `
  -H "Authorization: Bearer 你的token" `
  -H "Content-Type: application/json" `
  -d "{\"text\":\"余额\",\"wxid\":\"test_wxid\"}"
```

### 8. 验证（真实微信）

1. 用另一个微信号给你的机器人微信号发 **「余额」**
2. 应收到钱包文案
3. `logs/bot.log` 有回复记录

## 监听模式

### 默认：GetSession 轮询

使用 `GetSession()` 扫描会话列表，发现新消息后自动打开会话并处理。**私聊**默认全部监听（受黑名单、`listen_private` 约束）。

**群聊**不会默认全量监听：须在管理后台开启 **启用群聊监听**，并在 **群聊白名单** 填写群名称（与微信会话列表一致，逗号分隔），机器人才会处理该群消息。

### 群聊白名单示例

```
返利交流群,测试群
```

- 群聊：白名单中的群名才会自动回复（还须配合 `group_reply_mode`）。
- 私聊：不受群白名单影响，默认全部私聊都会处理（受 `listen_private`、黑名单约束）。

## 群聊回复策略


| group_reply_mode | 行为                   |
| ---------------- | -------------------- |
| `link_only`（默认）  | 群内仅回复含链接/口令/关键词意图的消息 |
| `at_me_only`     | 仅 @机器人 时回复           |
| `all`            | 回复群内所有消息（慎用，易刷屏）     |


在 **微信机器人 → 机器人昵称** 填写你的微信昵称，用于群 @ 识别。

## 自动通过好友 / 群邀请

管理后台 **微信机器人** 中勾选：

| 配置项 | 说明 |
| --- | --- |
| `auto_accept_friend` | 自动通过好友申请（依赖 wxauto `GetNewFriends` 等接口） |
| `auto_accept_group` | 自动通过群聊邀请（依赖库是否提供群邀请 API，见下） |

机器人启动后会另起**后台线程**，按 `poll_interval_seconds`（至少 5 秒）轮询一次，不阻塞收消息主循环。

**限制：**

- 需 **Windows + PC 微信已登录**，并安装 `wxautox4`（或支持该能力的 `wxauto4`）。
- **好友申请**：官方示例为 `GetNewFriends(acceptable=True)`，对每条请求调用 `accept()`。
- **群邀请**：不同版本 API 名称不一致（如 `GetNewGroupInvites`）；若当前库无对应方法，仅会打一次警告日志并跳过，不会崩溃。
- 部分版本把群邀请混在「新的朋友」列表里，代码会尝试根据文案/类型识别。

**Dry-run 预览（不点击通过）：**

```powershell
py -c "from config.settings_store import init_runtime_settings; init_runtime_settings(); from config.config import WECHAT_CONFIG; from src.wechat_bot import _import_wxauto, _connect_wechat; from src.wechat_auto_accept import preview_pending_accepts; W,_=_import_wxauto(); wx=_connect_wechat(W); print(preview_pending_accepts(wx, WECHAT_CONFIG))"
```

## 管理员指令（微信内）

管理员 wxid 在 **系统配置 → ADMIN_CONFIG → admin_wxids** 中设置（逗号分隔，填**微信号**，如 `qya11118`）。


| 指令         | 说明       |
| ---------- | -------- |
| 待审提现       | 查看待审核列表  |
| 通过提现 编号    | 审核通过     |
| 拒绝提现 编号 原因 | 拒绝并退回余额  |
| 同步订单       | 手动拉取联盟订单 |


## 用户指令


| 指令                          | 说明    |
| --------------------------- | ----- |
| 余额 / 订单 / 统计 / 签到 / 提现 / 帮助 | 钱包与账户 |
| 发送商品链接或淘口令                  | 自动转链  |


## 常见问题


| 现象           | 处理                                                                      |
| ------------ | ----------------------------------------------------------------------- |
| 提示未安装 wxauto | `py -m pip install -r requirements.txt`（或 `py -m pip install wxautox4`） |
| 连接微信失败       | 确认 PC 微信已登录；检查 wxauto4 与微信版本兼容                                          |
| 好友发消息无回复     | 查看 `logs/bot.log`；群聊检查是否已填「群聊白名单」群名、`listen_groups`、`group_reply_mode`；重启后需对方再发一条新消息 |
| 管理后台打不开      | 另开终端运行 `py -m src.api_server`                                           |
| 结算通知未推送      | 确认 `src.main` 在运行；通知会写入 DB 后由机器人主动推送                                    |


