"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createTournament, deleteTournament, getTournaments, updateTournament } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export default function TournamentsPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [totalRounds, setTotalRounds] = useState("10");
  const tournamentsQuery = useQuery({ queryKey: ["tournaments"], queryFn: getTournaments });
  const createMutation = useMutation({
    mutationFn: createTournament,
    onSuccess: () => {
      setName("");
      void queryClient.invalidateQueries({ queryKey: ["tournaments"] });
    },
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, name: tournamentName, totalRounds: rounds }: { id: string | number; name?: string; totalRounds?: number }) =>
      updateTournament(id, { name: tournamentName, total_rounds: rounds }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["tournaments"] }),
  });
  const deleteMutation = useMutation({
    mutationFn: deleteTournament,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["tournaments"] }),
  });

  function onCreate(event: FormEvent) {
    event.preventDefault();
    createMutation.mutate({ name, totalRounds: Number.parseInt(totalRounds, 10) || 10 });
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Create tournament</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="grid gap-3 md:grid-cols-[1fr_180px_auto]" onSubmit={onCreate}>
            <Input placeholder="Tournament name" value={name} onChange={(event) => setName(event.target.value)} />
            <Input placeholder="Total rounds" value={totalRounds} onChange={(event) => setTotalRounds(event.target.value)} />
            <Button type="submit" disabled={createMutation.isPending || !name.trim()}>
              Create
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Tournaments</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Players</TableHead>
                <TableHead>Current Round</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(tournamentsQuery.data ?? []).map((tournament) => (
                <TableRow key={tournament.id}>
                  <TableCell className="font-mono text-xs">{tournament.id}</TableCell>
                  <TableCell>
                    <Link className="font-medium text-primary" href={`/tournaments/${tournament.id}`}>
                      {tournament.name ?? `Tournament ${tournament.id}`}
                    </Link>
                  </TableCell>
                  <TableCell>{tournament.status}</TableCell>
                  <TableCell>{tournament.playerCount ?? "—"}</TableCell>
                  <TableCell>{tournament.currentRound ?? "—"}</TableCell>
                  <TableCell>{tournament.createdAt ? new Date(tournament.createdAt).toLocaleString() : "—"}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          const nextName = window.prompt("Tournament name", tournament.name ?? "");
                          if (!nextName || !nextName.trim()) {
                            return;
                          }
                          const nextRounds = window.prompt("Total rounds", `${tournament.totalRounds ?? 10}`);
                          updateMutation.mutate({
                            id: tournament.id,
                            name: nextName.trim(),
                            totalRounds: Number.parseInt(nextRounds ?? `${tournament.totalRounds ?? 10}`, 10) || 10,
                          });
                        }}
                        disabled={updateMutation.isPending}
                      >
                        Edit
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          if (window.confirm(`Delete tournament ${tournament.name ?? tournament.id}?`)) {
                            deleteMutation.mutate(tournament.id);
                          }
                        }}
                        disabled={deleteMutation.isPending}
                      >
                        Delete
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
