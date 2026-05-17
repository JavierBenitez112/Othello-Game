"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";

import { GameReplay } from "@/components/GameReplay";
import { GameViewer } from "@/components/GameViewer";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getGame } from "@/lib/api";

export default function GameDetailPage({ params }: { params: Promise<{ gameId: string }> }) {
  const { gameId } = use(params);
  const gameQuery = useQuery({
    queryKey: ["game", gameId],
    queryFn: () => getGame(gameId),
  });

  return (
    <div className="space-y-6">
      <GameViewer gameId={gameId} />
      <Card>
        <CardHeader>
          <CardTitle>Replay mode</CardTitle>
        </CardHeader>
        <CardContent>
          {gameQuery.data ? (
            <GameReplay moveHistory={gameQuery.data.moveHistory} />
          ) : (
            <div className="text-sm text-muted-foreground">Loading replay…</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
