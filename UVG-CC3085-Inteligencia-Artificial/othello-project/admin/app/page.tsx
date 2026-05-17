"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { getLiveGames, getPlayers, getStandings, getTournaments, normalizeLiveGamesResponse } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LiveGamesTable } from "@/components/LiveGamesTable";
import { Button } from "@/components/ui/button";

export default function DashboardPage() {
  const tournamentsQuery = useQuery({ queryKey: ["tournaments"], queryFn: getTournaments });
  const playersQuery = useQuery({ queryKey: ["players"], queryFn: getPlayers });
  const standingsQuery = useQuery({ queryKey: ["standings"], queryFn: getStandings });
  const liveGamesQuery = useQuery({
    queryKey: ["live-games"],
    queryFn: async () => normalizeLiveGamesResponse(await getLiveGames()),
    refetchInterval: 5_000,
  });

  const tournaments = tournamentsQuery.data ?? [];
  const activeTournament = tournaments.find((tournament) => tournament.status === "active") ?? tournaments[0];
  const players = playersQuery.data ?? [];
  const standings = standingsQuery.data ?? [];
  const liveGames = liveGamesQuery.data?.games ?? [];
  const connectedPlayers = players.filter((player) => player.connected).length;

  const summaryCards = [
    { label: "Registered Players", value: players.length },
    { label: "Connected Players", value: connectedPlayers },
    { label: "Active Games", value: liveGames.filter((game) => game.status === "active").length },
    { label: "Current Round", value: activeTournament?.currentRound ?? "—" },
  ];

  return (
    <div className="space-y-6">
      <section className="grid gap-4 xl:grid-cols-[1.2fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Active tournament</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {activeTournament ? (
              <>
                <div className="text-2xl font-semibold">{activeTournament.name ?? `Tournament ${activeTournament.id}`}</div>
                <div className="grid gap-2 text-sm text-muted-foreground md:grid-cols-2">
                  <div>Status: {activeTournament.status}</div>
                  <div>Registration: {activeTournament.registrationStatus ?? "—"}</div>
                  <div>Players: {activeTournament.playerCount ?? players.length}</div>
                  <div>Round: {activeTournament.currentRound ?? "—"}</div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button asChild>
                    <Link href="/tournaments">Open tournaments</Link>
                  </Button>
                  <Button asChild variant="outline">
                    <Link href="/live-games">Live games</Link>
                  </Button>
                </div>
              </>
            ) : (
              <div className="text-sm text-muted-foreground">No tournament data available yet.</div>
            )}
          </CardContent>
        </Card>
        <div className="grid gap-4 sm:grid-cols-2">
          {summaryCards.map((card) => (
            <Card key={card.label}>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm text-muted-foreground">{card.label}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-semibold">{card.value}</div>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Live games preview</CardTitle>
            <Button asChild variant="outline" size="sm">
              <Link href="/live-games">See all</Link>
            </Button>
          </CardHeader>
          <CardContent>
            <LiveGamesTable games={liveGames.slice(0, 6)} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Standings snapshot</CardTitle>
            <Button asChild variant="outline" size="sm">
              <Link href="/standings">Full standings</Link>
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            {standings.slice(0, 5).map((standing, index) => (
              <div key={standing.playerId} className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2">
                <div>
                  <div className="font-medium">
                    {index + 1}. {standing.playerName}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {standing.wins}W / {standing.losses}L / {standing.draws}D
                  </div>
                </div>
                <div className="text-lg font-semibold">{standing.score}</div>
              </div>
            ))}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
