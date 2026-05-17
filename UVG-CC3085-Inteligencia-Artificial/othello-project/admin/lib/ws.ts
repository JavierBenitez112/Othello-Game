"use client";

import { getAuthToken } from "@/lib/auth";
import { LiveEvent, KnownLiveEventType } from "@/lib/types";

type Handler = (event: LiveEvent) => void;
type Status = "idle" | "connecting" | "connected" | "disconnected";
type StatusHandler = (status: Status) => void;

const KNOWN_EVENT_TYPES = new Set<KnownLiveEventType>([
  "tournament_update",
  "player_connected",
  "player_disconnected",
  "round_started",
  "game_started",
  "game_update",
  "game_over",
  "move_recorded",
  "illegal_move",
  "timeout",
  "forfeit",
]);

class AdminWebSocketClient {
  private socket: WebSocket | null = null;
  private reconnectAttempts = 0;
  private reconnectTimer: number | null = null;
  private handlers = new Set<Handler>();
  private statusHandlers = new Set<StatusHandler>();
  private status: Status = "idle";
  private manuallyClosed = false;

  connect() {
    if (typeof window === "undefined" || this.socket || this.status === "connecting") {
      return;
    }

    const token = getAuthToken();
    if (!token) {
      this.setStatus("idle");
      return;
    }

    const wsBase = process.env.NEXT_PUBLIC_WS_BASE_URL ?? "ws://localhost:8000";
    const url = new URL("/admin/ws", wsBase);
    url.searchParams.set("token", token);

    this.manuallyClosed = false;
    this.setStatus("connecting");
    this.socket = new WebSocket(url.toString());

    this.socket.onopen = () => {
      this.reconnectAttempts = 0;
      this.setStatus("connected");
    };

    this.socket.onmessage = (message) => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(message.data);
      } catch {
        return;
      }

      if (!parsed || typeof parsed !== "object" || !("type" in parsed)) {
        return;
      }

      const event = parsed as LiveEvent;
      if (!KNOWN_EVENT_TYPES.has(event.type)) {
        return;
      }

      this.handlers.forEach((handler) => handler(event));
    };

    this.socket.onclose = () => {
      this.socket = null;
      this.setStatus("disconnected");
      if (!this.manuallyClosed) {
        this.scheduleReconnect();
      }
    };

    this.socket.onerror = () => {
      this.socket?.close();
    };
  }

  disconnect() {
    this.manuallyClosed = true;
    if (this.reconnectTimer) {
      window.clearTimeout(this.reconnectTimer);
    }
    this.reconnectTimer = null;
    this.socket?.close();
    this.socket = null;
    this.setStatus("idle");
  }

  subscribe(handler: Handler) {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  subscribeStatus(handler: StatusHandler) {
    this.statusHandlers.add(handler);
    handler(this.status);
    return () => this.statusHandlers.delete(handler);
  }

  getStatus() {
    return this.status;
  }

  private setStatus(status: Status) {
    this.status = status;
    this.statusHandlers.forEach((handler) => handler(status));
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) {
      window.clearTimeout(this.reconnectTimer);
    }

    const delay = Math.min(30_000, 1_000 * 2 ** this.reconnectAttempts);
    this.reconnectAttempts += 1;
    this.reconnectTimer = window.setTimeout(() => this.connect(), delay);
  }
}

export const adminWsClient = new AdminWebSocketClient();
