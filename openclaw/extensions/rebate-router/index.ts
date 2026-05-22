import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { RebateApiClient } from "./api-client.js";
import { routeMessage } from "./router.js";

type PluginConfig = {
  apiBaseUrl?: string;
  apiToken?: string;
  passiveMode?: boolean;
};

function silentReply() {
  // OpenClaw 会过滤 NO_REPLY，避免被动模式下发空消息
  return { handled: true, replyText: "NO_REPLY" };
}

export default definePluginEntry({
  id: "rebate-router",
  name: "Rebate Router",
  description: "Hard-route rebate bot messages before LLM (zero token)",
  register(api) {
    api.on(
      "before_dispatch",
      async (event, ctx) => {
        const text = String(event.content ?? event.body ?? "").trim();
        if (!text) return silentReply();

        const config = (ctx.pluginConfig ?? {}) as PluginConfig;
        const token = config.apiToken ?? "";
        if (!token) {
          api.logger.warn("[rebate-router] apiToken 未配置");
          return;
        }

        const wxid = String(ctx.senderId ?? ctx.sessionKey ?? "unknown");
        const client = new RebateApiClient(
          config.apiBaseUrl ?? "http://127.0.0.1:8765",
          token,
        );

        const decision = routeMessage(text, config.passiveMode ?? true);

        if (decision.action === "ignore") {
          return silentReply();
        }

        if (decision.action === "pass") {
          return;
        }

        try {
          const pending = await client.pullPendingNotifications(wxid);
          const result = await client.call(decision.kind, wxid, decision.content);
          const body = (result.message ?? "").trim();
          const parts = [pending, body].filter(Boolean);
          const replyText = parts.join("\n\n") || "处理完成";

          return { handled: true, replyText };
        } catch (err) {
          api.logger.error("[rebate-router] API 调用失败: %s", err);
          return {
            handled: true,
            replyText: "服务暂时不可用，请稍后再试",
          };
        }
      },
      { priority: 100 },
    );
  },
});
