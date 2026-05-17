"use client";

import { useQuery } from "@tanstack/react-query";

import { StandingsTable } from "@/components/StandingsTable";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getStandings } from "@/lib/api";

export default function StandingsPage() {
  const standingsQuery = useQuery({ queryKey: ["standings"], queryFn: getStandings, refetchInterval: 10_000 });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Standings</CardTitle>
      </CardHeader>
      <CardContent>
        <StandingsTable standings={standingsQuery.data ?? []} />
      </CardContent>
    </Card>
  );
}
