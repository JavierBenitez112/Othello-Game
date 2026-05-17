"use client";

import { FormEvent, useState } from "react";
import { use } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createGame, getRound, startRound } from "@/lib/api";
import { PairingsTable } from "@/components/PairingsTable";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function RoundDetailPage({ params }: { params: Promise<{ roundId: string }> }) {
  const { roundId } = use(params);
  const queryClient = useQueryClient();
  const [blackPlayerId, setBlackPlayerId] = useState("");
  const [whitePlayerId, setWhitePlayerId] = useState("");
  const roundQuery = useQuery({
    queryKey: ["round", roundId],
    queryFn: () => getRound(roundId),
  });
  const round = roundQuery.data;
  const startMutation = useMutation({
    mutationFn: () => startRound(roundId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["round", roundId] }),
  });
  const createGameMutation = useMutation({
    mutationFn: () =>
      createGame({
        round_id: round.id,
        black_player_id: Number.parseInt(blackPlayerId, 10),
        white_player_id: Number.parseInt(whitePlayerId, 10),
      }),
    onSuccess: () => {
      setBlackPlayerId("");
      setWhitePlayerId("");
      void queryClient.invalidateQueries({ queryKey: ["round", roundId] });
      void queryClient.invalidateQueries({ queryKey: ["live-games"] });
    },
  });

  function onCreateGame(event: FormEvent) {
    event.preventDefault();
    if (!round || !Number.parseInt(blackPlayerId, 10) || !Number.parseInt(whitePlayerId, 10)) {
      return;
    }
    createGameMutation.mutate();
  }

  if (!round) {
    return <div className="text-sm text-muted-foreground">Loading round…</div>;
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Round {round.number}</CardTitle>
            <div className="mt-2 text-sm text-muted-foreground">Status: {round.status}</div>
          </div>
          <Button onClick={() => startMutation.mutate()} disabled={startMutation.isPending}>
            Start round
          </Button>
        </CardHeader>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Pairings</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <form className="grid gap-3 md:grid-cols-[1fr_1fr_auto]" onSubmit={onCreateGame}>
            <Input placeholder="Black player ID" value={blackPlayerId} onChange={(event) => setBlackPlayerId(event.target.value)} />
            <Input placeholder="White player ID" value={whitePlayerId} onChange={(event) => setWhitePlayerId(event.target.value)} />
            <Button type="submit" disabled={createGameMutation.isPending || !blackPlayerId.trim() || !whitePlayerId.trim()}>
              Create game
            </Button>
          </form>
          <PairingsTable pairings={round.pairings} />
        </CardContent>
      </Card>
    </div>
  );
}
