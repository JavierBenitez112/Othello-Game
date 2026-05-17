"use client";

import { Standing } from "@/lib/types";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export function StandingsTable({ standings }: { standings: Standing[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Rank</TableHead>
          <TableHead>Player</TableHead>
          <TableHead>Score</TableHead>
          <TableHead>W</TableHead>
          <TableHead>L</TableHead>
          <TableHead>D</TableHead>
          <TableHead>Byes</TableHead>
          <TableHead>Disc Diff</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {standings.map((standing, index) => (
          <TableRow key={standing.playerId}>
            <TableCell>{standing.rank ?? index + 1}</TableCell>
            <TableCell>{standing.playerName}</TableCell>
            <TableCell>{standing.score}</TableCell>
            <TableCell>{standing.wins}</TableCell>
            <TableCell>{standing.losses}</TableCell>
            <TableCell>{standing.draws}</TableCell>
            <TableCell>{standing.byes}</TableCell>
            <TableCell>{standing.discDifferential ?? "—"}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
