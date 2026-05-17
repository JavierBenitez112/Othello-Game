"use client";

import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { LiveGamesGrid } from "@/components/LiveGamesGrid";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getLiveGames, normalizeLiveGamesResponse } from "@/lib/api";
import { GameSummary, LiveEvent } from "@/lib/types";
import { adminWsClient } from "@/lib/ws";

function applyEvent(game: GameSummary, event: LiveEvent): GameSummary {
  return {
    ...game,
    board: event.board ?? game.board,
    currentTurn: event.currentTurn ?? event.nextPlayer ?? game.currentTurn,
    lastMove: event.lastMove ?? game.lastMove,
    blackScore: event.blackScore ?? game.blackScore,
    whiteScore: event.whiteScore ?? game.whiteScore,
    countdownMs: event.deadlineMs ?? event.remainingMs ?? game.countdownMs,
    status: event.status ?? (event.type === "game_over" ? "completed" : game.status),
    updatedAt: event.timestamp ?? new Date().toISOString(),
  };
}

export default function LiveGamesPage() {
  const queryClient = useQueryClient();
  const [games, setGames] = useState<GameSummary[]>([]);
  const [wsStatus, setWsStatus] = useState(adminWsClient.getStatus());

  const liveGamesQuery = useQuery({
    queryKey: ["live-games"],
    queryFn: async () => normalizeLiveGamesResponse(await getLiveGames()),
    refetchInterval: wsStatus === "connected" ? false : 5_000,
  });

  useEffect(() => {
    setGames(liveGamesQuery.data?.games ?? []);
  }, [liveGamesQuery.data]);

  useEffect(() => {
    adminWsClient.connect();
    const unsubscribe = adminWsClient.subscribe((event) => {
      if (!event.gameId) {
        return;
      }
      setGames((current) => {
        const exists = current.some((game) => game.id === event.gameId);
        if (!exists) {
          void queryClient.invalidateQueries({ queryKey: ["live-games"] });
          return current;
        }
        return current.map((game) => (game.id === event.gameId ? applyEvent(game, event) : game));
      });
    });
    const unsubscribeStatus = adminWsClient.subscribeStatus((status) => {
      setWsStatus(status);
      if (status !== "connected") {
        void queryClient.invalidateQueries({ queryKey: ["live-games"] });
      }
    });
    return () => {
      unsubscribe();
      unsubscribeStatus();
    };
  }, [queryClient]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Live games</CardTitle>
      </CardHeader>
      <CardContent>
        <LiveGamesGrid games={games} />
      </CardContent>
    </Card>
  );
}
