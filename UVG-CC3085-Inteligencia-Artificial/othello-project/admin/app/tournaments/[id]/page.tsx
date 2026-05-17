"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { use } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { closeRegistration, createPlayer, deleteTournament, getTournament, startRegistration, startRound, startTournament, updateTournament } from "@/lib/api";
import { LiveGamesTable } from "@/components/LiveGamesTable";
import { PlayersTable } from "@/components/PlayersTable";
import { StandingsTable } from "@/components/StandingsTable";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export default function TournamentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const queryClient = useQueryClient();
  const [playerName, setPlayerName] = useState("");
  const tournamentQuery = useQuery({
    queryKey: ["tournament", id],
    queryFn: () => getTournament(id),
  });

  const mutationOptions = {
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["tournament", id] });
      void queryClient.invalidateQueries({ queryKey: ["tournaments"] });
      void queryClient.invalidateQueries({ queryKey: ["standings"] });
      void queryClient.invalidateQueries({ queryKey: ["live-games"] });
    },
  };

  const startRegistrationMutation = useMutation({ mutationFn: () => startRegistration(id), ...mutationOptions });
  const closeRegistrationMutation = useMutation({ mutationFn: () => closeRegistration(id), ...mutationOptions });
  const startTournamentMutation = useMutation({ mutationFn: () => startTournament(id), ...mutationOptions });
  const updateTournamentMutation = useMutation({
    mutationFn: ({ name, totalRounds }: { name?: string; totalRounds?: number }) =>
      updateTournament(id, { name, total_rounds: totalRounds }),
    ...mutationOptions,
  });
  const deleteTournamentMutation = useMutation({
    mutationFn: () => deleteTournament(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["tournaments"] });
      window.location.href = "/tournaments";
    },
  });
  const createPlayerMutation = useMutation({
    mutationFn: () => createPlayer({ tournament_id: Number(id), name: playerName.trim() }),
    onSuccess: () => {
      setPlayerName("");
      void queryClient.invalidateQueries({ queryKey: ["tournament", id] });
      void queryClient.invalidateQueries({ queryKey: ["players"] });
    },
  });
  const nextRound = tournamentQuery.data?.rounds?.find((round) => round.status !== "completed");
  const startRoundMutation = useMutation({
    mutationFn: () => {
      if (!nextRound) {
        throw new Error("No round available to start");
      }
      return startRound(nextRound.id);
    },
    ...mutationOptions,
  });

  const tournament = tournamentQuery.data;

  function onCreatePlayer(event: FormEvent) {
    event.preventDefault();
    if (!playerName.trim()) {
      return;
    }
    createPlayerMutation.mutate();
  }

  if (!tournament) {
    return <div className="text-sm text-muted-foreground">Loading tournament…</div>;
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-start justify-between">
          <div>
            <CardTitle>{tournament.name ?? `Tournament ${tournament.id}`}</CardTitle>
            <div className="mt-2 grid gap-2 text-sm text-muted-foreground md:grid-cols-2">
              <div>Status: {tournament.status}</div>
              <div>Registration: {tournament.registrationStatus ?? "—"}</div>
              <div>Current round: {tournament.currentRound ?? "—"}</div>
              <div>Players: {tournament.playerCount ?? "—"}</div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => startRegistrationMutation.mutate()} disabled={startRegistrationMutation.isPending}>
              Start registration
            </Button>
            <Button variant="outline" onClick={() => closeRegistrationMutation.mutate()} disabled={closeRegistrationMutation.isPending}>
              Close registration
            </Button>
            <Button onClick={() => startTournamentMutation.mutate()} disabled={startTournamentMutation.isPending}>
              Start tournament
            </Button>
            <Button variant="secondary" onClick={() => startRoundMutation.mutate()} disabled={startRoundMutation.isPending || !nextRound}>
              Start next round
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                const name = window.prompt("Tournament name", tournament.name ?? "");
                if (!name || !name.trim()) {
                  return;
                }
                const totalRounds = window.prompt("Total rounds", `${tournament.totalRounds ?? 10}`);
                updateTournamentMutation.mutate({
                  name: name.trim(),
                  totalRounds: Number.parseInt(totalRounds ?? `${tournament.totalRounds ?? 10}`, 10) || 10,
                });
              }}
              disabled={updateTournamentMutation.isPending}
            >
              Edit tournament
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                if (window.confirm(`Delete tournament ${tournament.name ?? tournament.id}?`)) {
                  deleteTournamentMutation.mutate();
                }
              }}
              disabled={deleteTournamentMutation.isPending}
            >
              Delete tournament
            </Button>
          </div>
        </CardHeader>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardHeader>
            <CardTitle>Standings</CardTitle>
          </CardHeader>
          <CardContent>
            <StandingsTable standings={tournament.standings ?? []} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Rounds</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Round</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Pairings</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(tournament.rounds ?? []).map((round) => (
                  <TableRow key={round.id}>
                    <TableCell>
                      <Link className="font-medium text-primary" href={`/rounds/${round.id}`}>
                        Round {round.roundNumber ?? round.number}
                      </Link>
                    </TableCell>
                    <TableCell>{round.status ?? "—"}</TableCell>
                    <TableCell>{round.pairings?.length ?? "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Enrolled players</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <form className="flex flex-wrap gap-3" onSubmit={onCreatePlayer}>
            <Input placeholder="New player name" value={playerName} onChange={(event) => setPlayerName(event.target.value)} />
            <Button type="submit" disabled={createPlayerMutation.isPending || !playerName.trim()}>
              Add player
            </Button>
          </form>
          <PlayersTable players={tournament.players ?? []} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Active games</CardTitle>
        </CardHeader>
        <CardContent>
          <LiveGamesTable games={tournament.activeGames ?? []} />
        </CardContent>
      </Card>
    </div>
  );
}
