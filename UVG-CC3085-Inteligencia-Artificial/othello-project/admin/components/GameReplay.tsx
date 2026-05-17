"use client";

import { useEffect, useMemo, useState } from "react";

import { OthelloBoard } from "@/components/OthelloBoard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Board, Move } from "@/lib/types";

type Props = {
  initialBoard?: Board;
  moveHistory: Move[];
};

const INITIAL_BOARD: Board = Array.from({ length: 8 }, (_, row) =>
  Array.from({ length: 8 }, (_, col) => {
    if (row === 3 && col === 3) return "W";
    if (row === 3 && col === 4) return "B";
    if (row === 4 && col === 3) return "B";
    if (row === 4 && col === 4) return "W";
    return ".";
  }),
);

export function GameReplay({ initialBoard = INITIAL_BOARD, moveHistory }: Props) {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);

  const positions = useMemo(() => [initialBoard, ...moveHistory.map((move) => move.boardAfter ?? initialBoard)], [initialBoard, moveHistory]);

  useEffect(() => {
    if (!playing) {
      return;
    }
    const timer = window.setInterval(() => {
      setIndex((current) => {
        if (current >= positions.length - 1) {
          setPlaying(false);
          return current;
        }
        return current + 1;
      });
    }, 900);

    return () => window.clearInterval(timer);
  }, [playing, positions.length]);

  const currentMove = moveHistory[index - 1];

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Replay</CardTitle>
        <div className="text-sm text-muted-foreground">
          Move {index} / {moveHistory.length}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <OthelloBoard board={positions[index]} lastMove={currentMove?.move} currentPlayer={currentMove?.color ?? null} />
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => setIndex(0)}>
            Start
          </Button>
          <Button variant="outline" size="sm" onClick={() => setIndex((current) => Math.max(0, current - 1))}>
            Back
          </Button>
          <Button size="sm" onClick={() => setPlaying((current) => !current)}>
            {playing ? "Pause" : "Autoplay"}
          </Button>
          <Button variant="outline" size="sm" onClick={() => setIndex((current) => Math.min(positions.length - 1, current + 1))}>
            Forward
          </Button>
          <Button variant="outline" size="sm" onClick={() => setIndex(positions.length - 1)}>
            End
          </Button>
        </div>
        {currentMove ? (
          <div className="text-sm text-muted-foreground">
            {currentMove.player ?? currentMove.color ?? "Player"} played {currentMove.move}
          </div>
        ) : (
          <div className="text-sm text-muted-foreground">Initial position</div>
        )}
      </CardContent>
    </Card>
  );
}
