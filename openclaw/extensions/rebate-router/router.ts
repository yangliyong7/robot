export type RouteDecision =
  | { action: "handle"; kind: string; content?: string }
  | { action: "ignore" }
  | { action: "pass" };

const COMMANDS: Record<string, RegExp> = {
  help: /^(帮助|help|\?|？|使用说明)$/i,
  balance: /^(余额|查询余额|我的余额)$/i,
  withdraw: /^(提现|申请提现)$/i,
  orders: /^(订单|我的订单|查询订单)$/i,
  stats: /^(统计|收益统计|我的收益)$/i,
  checkin: /^(签到|打卡|每日签到)$/i,
};

const PASSIVE_KEYWORDS = [
  "饿了么", "eleme", "饿了嘛", "外卖红包",
  "携程", "同程", "去哪儿", "酒店", "机票", "订票", "订房", "航班",
  "飞猪", "淘票票", "美团", "团购",
  "闲鱼", "拼多多", "京东", "淘宝", "天猫",
];

function hasProductIntent(text: string): boolean {
  if (/https?:\/\//i.test(text)) return true;
  if (/【淘宝】.*?[￥¥Y]\w+[￥¥Y]/i.test(text)) return true;
  if (/【京东】.*?[￥¥Y]\w+[￥¥Y]/i.test(text)) return true;
  if (/^(找|买|搜|查)\s*[\u4e00-\u9fff\w]{1,20}/.test(text)) return true;
  return PASSIVE_KEYWORDS.some((kw) => text.includes(kw));
}

export function routeMessage(text: string, passiveMode: boolean): RouteDecision {
  const trimmed = text.trim();
  if (!trimmed) return { action: "ignore" };

  for (const [cmd, re] of Object.entries(COMMANDS)) {
    if (re.test(trimmed)) {
      return { action: "handle", kind: cmd };
    }
  }

  if (hasProductIntent(trimmed)) {
    return { action: "handle", kind: "convert", content: trimmed };
  }

  if (passiveMode) {
    return { action: "ignore" };
  }

  return { action: "pass" };
}
