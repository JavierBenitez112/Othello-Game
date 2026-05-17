"use client";

import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { deleteGame, updateGame } from "@/lib/api";
import { Pairing } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export function PairingsTable({ pairings }: { pairings: Pairing[] }) {
  const queryClient = useQueryClient();
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["round"] });
    void queryClient.invalidateQueries({ queryKey: ["live-games"] });
    void queryClient.invalidateQueries({ queryKey: ["tournaments"] });
  };
  const startMutation = useMutation({
    mutationFn: (gameId: string) => updateGame(gameId, { status: "active" }),
    onSuccess: invalidate,
  });
  const deleteMutation = useMutation({
    mutationFn: deleteGame,
    onSuccess: invalidate,
  });

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Board</TableHead>
          <TableHead>Black</TableHead>
          <TableHead>White</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Result</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {pairings.map((pairing) => (
          <TableRow key={pairing.gameId}>
            <TableCell>
              <Link className="font-medium text-primary" href={`/games/${pairing.gameId}`}>
                {pairing.gameId}
              </Link>
            </TableCell>
            <TableCell>{pairing.blackPlayerName}</TableCell>
            <TableCell>{pairing.whitePlayerName}</TableCell>
            <TableCell>
              <Badge variant={pairing.status === "active" ? "success" : "outline"}>{pairing.status}</Badge>
            </TableCell>
            <TableCell>{pairing.result ?? "—"}</TableCell>
            <TableCell className="text-right">
              <div className="flex justify-end gap-2">
                {pairing.status === "pending" ? (
                  <Button size="sm" variant="outline" onClick={() => startMutation.mutate(pairing.gameId)} disabled={startMutation.isPending}>
                    Start
                  </Button>
                ) : null}
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    if (window.confirm(`Delete game ${pairing.gameId}?`)) {
                      deleteMutation.mutate(pairing.gameId);
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
  );
}
