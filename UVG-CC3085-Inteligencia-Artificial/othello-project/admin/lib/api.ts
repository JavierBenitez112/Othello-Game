"use client";

import {
  Game,
  GameSummary,
  LiveGamesResponse,
  Player,
  Round,
  Standing,
  Tournament,
} from "@/lib/types";
import { getAuthToken } from "@/lib/auth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type RequestOptions = RequestInit & {
  authenticated?: boolean;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers ?? {});
  headers.set("Content-Type", "application/json");

  if (options.authenticated !== false) {
    const token = getAuthToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      detail = body.detail ?? body.message ?? detail;
    } catch {
      // Ignore JSON parsing errors for non-JSON bodies.
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export type LoginResponse = { token: string; username?: string };

export async function adminLogin(username: string, password: string): Promise<LoginResponse> {
  return request<LoginResponse>("/admin/login", {
    method: "POST",
    authenticated: false,
    body: JSON.stringify({ username, password }),
  });
}

export function getTournaments() {
  return request<Tournament[]>("/admin/tournaments");
}

export function createTournament(payload: { name: string; totalRounds?: number }) {
  return request<Tournament>("/admin/tournaments", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateTournament(id: string | number, payload: { name?: string; total_rounds?: number }) {
  return request<Tournament>(`/admin/tournaments/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteTournament(id: string | number) {
  return request<void>(`/admin/tournaments/${id}`, { method: "DELETE" });
}

export function getTournament(id: string | number) {
  return request<Tournament>(`/admin/tournaments/${id}`);
}

export function startRegistration(id: string | number) {
  return request<Tournament>(`/admin/tournaments/${id}/start-registration`, { method: "POST" });
}

export function closeRegistration(id: string | number) {
  return request<Tournament>(`/admin/tournaments/${id}/close-registration`, { method: "POST" });
}

export function startTournament(id: string | number) {
  return request<Tournament>(`/admin/tournaments/${id}/start`, { method: "POST" });
}

export function startRound(roundId: string | number) {
  return request<Round>(`/admin/rounds/${roundId}/start`, { method: "POST" });
}

export function getRound(roundId: string | number) {
  return request<Round>(`/admin/rounds/${roundId}`);
}

export function getGame(gameId: string) {
  return request<Game>(`/admin/games/${gameId}`);
}

export function createGame(payload: { round_id: number | string; black_player_id: number; white_player_id: number }) {
  return request<Game>("/admin/games", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateGame(
  gameId: string,
  payload: { round_id?: number | string; black_player_id?: number; white_player_id?: number; status?: "pending" | "active" },
) {
  return request<Game>(`/admin/games/${gameId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteGame(gameId: string) {
  return request<void>(`/admin/games/${gameId}`, { method: "DELETE" });
}

export function forceEndGame(gameId: string) {
  return request<Game>(`/admin/games/${gameId}/force-end`, { method: "POST" });
}

export function forfeitPlayer(playerId: number) {
  return request<Player>(`/admin/players/${playerId}/forfeit`, { method: "POST" });
}

export function createPlayer(payload: { tournament_id: number; name: string }) {
  return request<Player>("/admin/players", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updatePlayer(playerId: number, payload: { name?: string }) {
  return request<Player>(`/admin/players/${playerId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deletePlayer(playerId: number) {
  return request<void>(`/admin/players/${playerId}`, { method: "DELETE" });
}

export function getPlayers() {
  return request<Player[]>("/admin/players");
}

export function getStandings() {
  return request<Standing[]>("/admin/standings");
}

export function getLiveGames() {
  return request<LiveGamesResponse | GameSummary[]>("/admin/live-games");
}

export function normalizeLiveGamesResponse(payload: LiveGamesResponse | GameSummary[]): LiveGamesResponse {
  if (Array.isArray(payload)) {
    return { games: payload };
  }
  return { games: payload.games ?? [] };
}
