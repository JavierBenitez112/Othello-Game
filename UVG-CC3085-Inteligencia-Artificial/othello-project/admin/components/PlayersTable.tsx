"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { deletePlayer, forfeitPlayer, updatePlayer } from "@/lib/api";
import { Player } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export function PlayersTable({ players }: { players: Player[] }) {
  const queryClient = useQueryClient();
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["players"] });
    void queryClient.invalidateQueries({ queryKey: ["tournament"] });
    void queryClient.invalidateQueries({ queryKey: ["tournaments"] });
    void queryClient.invalidateQueries({ queryKey: ["standings"] });
    void queryClient.invalidateQueries({ queryKey: ["live-games"] });
  };
  const forfeitMutation = useMutation({
    mutationFn: forfeitPlayer,
    onSuccess: invalidate,
  });
  const updateMutation = useMutation({
    mutationFn: ({ playerId, name }: { playerId: number; name: string }) => updatePlayer(playerId, { name }),
    onSuccess: invalidate,
  });
  const deleteMutation = useMutation({
    mutationFn: deletePlayer,
    onSuccess: invalidate,
  });

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Player</TableHead>
          <TableHead>Connection</TableHead>
          <TableHead>Score</TableHead>
          <TableHead>Current Game</TableHead>
          <TableHead>Games Played</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {players.map((player) => (
          <TableRow key={player.id}>
            <TableCell className="font-medium">{player.name}</TableCell>
            <TableCell>
              <Badge variant={player.connected ? "success" : "outline"}>{player.connected ? "connected" : "offline"}</Badge>
            </TableCell>
            <TableCell>{player.score ?? "—"}</TableCell>
            <TableCell>{player.currentGameId ?? "—"}</TableCell>
            <TableCell>{player.gamesPlayed ?? "—"}</TableCell>
            <TableCell className="text-right">
              <div className="flex justify-end gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    const name = window.prompt("Rename player", player.name);
                    if (name && name.trim()) {
                      updateMutation.mutate({ playerId: player.id, name: name.trim() });
                    }
                  }}
                  disabled={updateMutation.isPending}
                >
                  Edit
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    if (window.confirm(`Delete player ${player.name}?`)) {
                      deleteMutation.mutate(player.id);
                    }
                  }}
                  disabled={deleteMutation.isPending}
                >
                  Delete
                </Button>
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={() => forfeitMutation.mutate(player.id)}
                  disabled={forfeitMutation.isPending}
                >
                  Forfeit
                </Button>
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
