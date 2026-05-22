type ApiResult = { success?: boolean; message?: string; data?: Record<string, unknown> };

export class RebateApiClient {
  constructor(
    private baseUrl: string,
    private token: string,
  ) {}

  private headers() {
    return {
      Authorization: `Bearer ${this.token}`,
      "Content-Type": "application/json",
    };
  }

  async ensureUser(wxid: string, nickname: string) {
    await fetch(`${this.baseUrl}/v1/users/ensure`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({ wxid, nickname }),
    });
  }

  async call(kind: string, wxid: string, content?: string): Promise<ApiResult> {
    await this.ensureUser(wxid, wxid);

    if (kind === "help") {
      const res = await fetch(`${this.baseUrl}/v1/help`, { headers: this.headers() });
      return res.json();
    }

    if (kind === "convert") {
      const res = await fetch(`${this.baseUrl}/v1/convert`, {
        method: "POST",
        headers: this.headers(),
        body: JSON.stringify({
          wxid,
          nickname: wxid,
          content: content ?? "",
          notify_is_group: false,
        }),
      });
      return res.json();
    }

    if (kind === "balance" || kind === "orders" || kind === "stats") {
      const res = await fetch(`${this.baseUrl}/v1/wallet/${kind}?wxid=${encodeURIComponent(wxid)}`, {
        headers: this.headers(),
      });
      return res.json();
    }

    if (kind === "withdraw" || kind === "checkin") {
      const res = await fetch(`${this.baseUrl}/v1/wallet/${kind}`, {
        method: "POST",
        headers: this.headers(),
        body: JSON.stringify({ wxid }),
      });
      return res.json();
    }

    return { success: false, message: "未知指令" };
  }

  async pullPendingNotifications(wxid: string): Promise<string> {
    const res = await fetch(
      `${this.baseUrl}/v1/notifications/pending?wxid=${encodeURIComponent(wxid)}&limit=3`,
      { headers: this.headers() },
    );
    const data = (await res.json()) as ApiResult;
    const ids = (data.data?.ids as number[] | undefined) ?? [];
    if (ids.length) {
      await fetch(`${this.baseUrl}/v1/notifications/deliver`, {
        method: "POST",
        headers: this.headers(),
        body: JSON.stringify({ wxid, ids }),
      });
    }
    return (data.message ?? "").trim();
  }
}
