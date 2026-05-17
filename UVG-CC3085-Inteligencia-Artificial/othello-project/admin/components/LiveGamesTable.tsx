"use client";

import Link from "next/link";

import { GameSummary } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export function LiveGamesTable({ games }: { games: GameSummary[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Game</TableHead>
          <TableHead>Black</TableHead>
          <TableHead>White</TableHead>
          <TableHead>Round</TableHead>
          <TableHead>Turn</TableHead>
          <TableHead>Last Move</TableHead>
          <TableHead>Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {games.map((game) => (
          <TableRow key={game.id}>
            <TableCell>
              <Link className="font-medium text-primary" href={`/games/${game.id}`}>
                {game.id}
              </Link>
            </TableCell>
            <TableCell>{game.blackPlayerName}</TableCell>
            <TableCell>{game.whitePlayerName}</TableCell>
            <TableCell>{game.roundNumber ?? "—"}</TableCell>
            <TableCell>{game.currentTurn ?? "—"}</TableCell>
            <TableCell>{game.lastMove ?? "—"}</TableCell>
            <TableCell>
              <Badge variant={game.status === "active" ? "success" : "outline"}>{game.status}</Badge>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
