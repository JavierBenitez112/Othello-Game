"use client";

import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { PlayersTable } from "@/components/PlayersTable";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { createPlayer, getPlayers } from "@/lib/api";

export default function PlayersPage() {
  const queryClient = useQueryClient();
  const [tournamentId, setTournamentId] = useState("");
  const [playerName, setPlayerName] = useState("");
  const playersQuery = useQuery({ queryKey: ["players"], queryFn: getPlayers, refetchInterval: 5_000 });
  const createMutation = useMutation({
    mutationFn: () => createPlayer({ tournament_id: Number.parseInt(tournamentId, 10), name: playerName.trim() }),
    onSuccess: () => {
      setPlayerName("");
      void queryClient.invalidateQueries({ queryKey: ["players"] });
      void queryClient.invalidateQueries({ queryKey: ["tournaments"] });
    },
  });

  function onCreate(event: FormEvent) {
    event.preventDefault();
    if (!playerName.trim() || !Number.parseInt(tournamentId, 10)) {
      return;
    }
    createMutation.mutate();
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Create player</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="grid gap-3 md:grid-cols-[180px_1fr_auto]" onSubmit={onCreate}>
            <Input placeholder="Tournament ID" value={tournamentId} onChange={(event) => setTournamentId(event.target.value)} />
            <Input placeholder="Player name" value={playerName} onChange={(event) => setPlayerName(event.target.value)} />
            <Button type="submit" disabled={createMutation.isPending || !playerName.trim() || !tournamentId.trim()}>
              Create
            </Button>
          </form>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Players</CardTitle>
        </CardHeader>
        <CardContent>
          <PlayersTable players={playersQuery.data ?? []} />
        </CardContent>
      </Card>
    </div>
  );
}
