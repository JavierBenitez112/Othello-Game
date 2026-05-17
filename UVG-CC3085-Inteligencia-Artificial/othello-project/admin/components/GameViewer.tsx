"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { OthelloBoard } from "@/components/OthelloBoard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { deleteGame, forceEndGame, forfeitPlayer, getGame } from "@/lib/api";
import { Game, LiveEvent } from "@/lib/types";
import { adminWsClient } from "@/lib/ws";

type Props = {
  gameId: string;
};

function mergeGameWithEvent(game: Game, event: LiveEvent): Game {
  return {
    ...game,
    board: event.board ?? game.board,
    currentTurn: event.currentTurn ?? event.nextPlayer ?? game.currentTurn,
    lastMove: event.lastMove ?? game.lastMove,
    legalMoves: event.legalMoves ?? game.legalMoves,
    blackScore: event.blackScore ?? game.blackScore,
    whiteScore: event.whiteScore ?? game.whiteScore,
    countdownMs: event.deadlineMs ?? event.remainingMs ?? game.countdownMs,
    result: event.result ?? game.result,
    winner: event.winner ?? game.winner,
    moveHistory: event.move ? [...game.moveHistory, event.move] : game.moveHistory,
    status: event.type === "game_over" ? "completed" : event.status ?? game.status,
  };
}

export function GameViewer({ gameId }: Props) {
  const queryClient = useQueryClient();
  const [wsStatus, setWsStatus] = useState(adminWsClient.getStatus());
  const { data, isLoading } = useQuery({
    queryKey: ["game", gameId],
    queryFn: () => getGame(gameId),
    refetchInterval: wsStatus === "connected" ? false : 5_000,
  });
  const [liveGame, setLiveGame] = useState<Game | null>(null);
  const [remainingMs, setRemainingMs] = useState<number | null>(null);

  useEffect(() => {
    if (!data) {
      return;
    }
    setLiveGame(data);
  }, [data]);

  useEffect(() => {
    setRemainingMs((liveGame ?? data)?.countdownMs ?? null);
  }, [data, liveGame]);

  useEffect(() => {
    adminWsClient.connect();
    const unsubscribe = adminWsClient.subscribe((event) => {
      if (event.gameId !== gameId) {
        return;
      }
      setLiveGame((current) => (current ? mergeGameWithEvent(current, event) : current));
      void queryClient.invalidateQueries({ queryKey: ["game", gameId] });
    });

    const unsubscribeStatus = adminWsClient.subscribeStatus((status) => {
      setWsStatus(status);
      if (status !== "connected") {
        void queryClient.invalidateQueries({ queryKey: ["game", gameId] });
      }
    });

    return () => {
      unsubscribe();
      unsubscribeStatus();
    };
  }, [gameId, queryClient]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setRemainingMs((current) => (current == null ? null : Math.max(0, current - 500)));
    }, 500);
    return () => window.clearInterval(timer);
  }, []);

  const game = liveGame ?? data;

  const forceEndMutation = useMutation({
    mutationFn: () => forceEndGame(gameId),
    onSuccess: (updatedGame) => setLiveGame(updatedGame),
  });

  const forfeitMutation = useMutation({
    mutationFn: (playerId: number) => forfeitPlayer(playerId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["game", gameId] }),
  });
  const deleteMutation = useMutation({
    mutationFn: () => deleteGame(gameId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["live-games"] });
      window.location.href = "/live-games";
    },
  });

  if (isLoading || !game) {
    return <div className="text-sm text-muted-foreground">Loading game…</div>;
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
      <Card>
        <CardHeader>
          <CardTitle>Live game</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <OthelloBoard board={game.board ?? []} lastMove={game.lastMove} legalMoves={game.legalMoves} currentPlayer={game.currentTurn} />
          <div className="grid gap-2 text-sm text-muted-foreground md:grid-cols-2">
            <div>Black: {game.blackPlayerName}</div>
            <div>White: {game.whitePlayerName}</div>
            <div>Status: {game.status}</div>
            <div>Current turn: {game.currentTurn ?? "—"}</div>
            <div>Last move: {game.lastMove ?? "—"}</div>
            <div>Countdown: {remainingMs == null ? "—" : `${Math.ceil(remainingMs / 1000)}s`}</div>
            <div>
              Score: {game.blackScore ?? "—"} - {game.whiteScore ?? "—"}
            </div>
            <div>Winner: {game.winner ?? "—"}</div>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Controls and history</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button variant="destructive" onClick={() => forceEndMutation.mutate()} disabled={forceEndMutation.isPending}>
              Force end
            </Button>
            {game.blackPlayerId ? (
              <Button variant="outline" onClick={() => forfeitMutation.mutate(game.blackPlayerId)} disabled={forfeitMutation.isPending}>
                Forfeit black
              </Button>
            ) : null}
            {game.whitePlayerId ? (
              <Button variant="outline" onClick={() => forfeitMutation.mutate(game.whitePlayerId)} disabled={forfeitMutation.isPending}>
                Forfeit white
              </Button>
            ) : null}
            <Button
              variant="outline"
              onClick={() => {
                if (window.confirm(`Delete game ${gameId}?`)) {
                  deleteMutation.mutate();
                }
              }}
              disabled={deleteMutation.isPending}
            >
              Delete game
            </Button>
          </div>
          <div className="max-h-[420px] space-y-2 overflow-auto rounded-lg border p-3">
            {game.moveHistory.length === 0 ? (
              <div className="text-sm text-muted-foreground">No moves recorded yet.</div>
            ) : (
              game.moveHistory.map((move, index) => (
                <div key={`${move.move}-${index}`} className="flex items-center justify-between rounded-md bg-muted/50 px-3 py-2 text-sm">
                  <span>
                    {move.turnNumber ?? move.moveNumber ?? index + 1}. {move.player ?? move.color ?? "Player"}
                  </span>
                  <span className="font-medium">{move.move}</span>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
