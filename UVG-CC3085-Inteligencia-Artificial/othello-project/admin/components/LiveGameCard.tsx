"use client";

import { memo } from "react";
import Link from "next/link";

import { MiniOthelloBoard } from "@/components/MiniOthelloBoard";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { GameSummary } from "@/lib/types";

type Props = {
  game: GameSummary;
  mode: "compact" | "expanded";
};

function formatMs(ms?: number | null) {
  if (ms == null) {
    return "—";
  }
  return `${Math.max(0, Math.ceil(ms / 1000))}s`;
}

function LiveGameCardInner({ game, mode }: Props) {
  return (
    <Card className="overflow-hidden">
      <CardContent className={mode === "compact" ? "grid grid-cols-[auto,1fr] gap-3 p-4" : "space-y-4 p-5"}>
        <MiniOthelloBoard board={game.board} compact={mode === "compact"} />
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="text-sm font-semibold text-foreground">
              {game.blackPlayerName} vs {game.whitePlayerName}
            </div>
            <Badge variant={game.status === "active" ? "success" : "outline"}>{game.status}</Badge>
          </div>
          <div className="grid gap-1 text-xs text-muted-foreground">
            <div>Round {game.roundNumber ?? "—"}</div>
            <div>Turn: {game.currentTurn ?? "—"}</div>
            <div>Last move: {game.lastMove ?? "—"}</div>
            <div>
              Score: {game.blackScore ?? "—"} - {game.whiteScore ?? "—"}
            </div>
            <div>Timer: {formatMs(game.countdownMs)}</div>
          </div>
          <Link href={`/games/${game.id}`} className="text-sm font-medium text-primary">
            Open game
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}

export const LiveGameCard = memo(LiveGameCardInner);
