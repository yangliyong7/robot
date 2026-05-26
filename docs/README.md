# 微信返利机器人（wxauto 版）

基于 **wxauto4** 驱动 PC 微信客户端，监听好友/群聊消息并自动回复。业务逻辑与 SQLite 数据库保持不变。

## 架构

```
Windows 电脑（PC 微信已登录）
├── python -m src.main          ← wxauto 监听消息、自动回复
├── python -m src.api_server    ← 管理后台 :8765（可选）
└── python -m src.worker.order_sync_worker  ← 联盟订单同步

好友/群友 → 给你的微信发消息 → wxauto 捕获 → 转链/余额/签到 → 自动回复
                                              ↓
                               SQLite data/rebate_bot.db
```

## 环境要求


| 项目      | 要求                                        |
| ------- | ----------------------------------------- |
| 系统      | **Windows**（wxauto 依赖 UI 自动化）             |
| 微信      | PC 微信已登录并保持运行                             |
| Python  | 3.9+                                      |
| wxauto4 | `pip install wxauto4`（见 requirements.txt） |


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

### 2. 启动管理后台（首次配置）

```powershell
python -m src.api_server
```

浏览器打开 [http://127.0.0.1:8765/admin](http://127.0.0.1:8765/admin) ，配置：

- **管理后台**：登录密码
- **联盟密钥**：淘宝/京东/拼多多
- **微信机器人**：被动模式、群聊回复策略等
- **防封限流**：回复间隔

### 3. 启动微信机器人

**先确保 PC 微信已登录**，再运行：

```powershell
python -m src.main
```

程序会通过 wxauto 连接微信，监听新消息并自动回复。

### 4. 启动订单同步（另开终端）

```powershell
python -m src.worker.order_sync_worker
```

### 5. 验证

1. 用另一个微信号给你的机器人微信号发 **「余额」**
2. 应收到钱包文案
3. `logs/bot.log` 有回复记录

## 监听模式

### 默认：GetSession 轮询

不配置 `listen_targets` 时，使用 `GetSession()` 扫描会话列表，发现新消息后自动打开会话并处理。

### 指定监听对象

在管理后台 **微信机器人 → 仅监听名单** 填写（逗号分隔），例如：

```
返利群,张三,李四
```

将仅对这些会话回复（轮询模式下按白名单过滤）。

## 群聊回复策略


| group_reply_mode | 行为                   |
| ---------------- | -------------------- |
| `link_only`（默认）  | 群内仅回复含链接/口令/关键词意图的消息 |
| `at_me_only`     | 仅 @机器人 时回复           |
| `all`            | 回复群内所有消息（慎用，易刷屏）     |


在 **微信机器人 → 机器人昵称** 填写你的微信昵称，用于群 @ 识别。

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


| 现象            | 处理                                                      |
| ------------- | ------------------------------------------------------- |
| 提示未安装 wxauto4 | `pip install wxauto4`                                   |
| 连接微信失败        | 确认 PC 微信已登录；检查 wxauto4 与微信版本兼容                          |
| 好友发消息无回复      | 查看 `logs/bot.log`；群聊检查 `group_reply_mode`；重启后需对方再发一条新消息 |
| 管理后台打不开       | 另开终端运行 `python -m src.api_server`                       |
| 结算通知未推送       | 确认 `src.main` 在运行；通知会写入 DB 后由机器人主动推送                    |


