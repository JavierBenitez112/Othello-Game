"use client";

import { Board, BoardCell } from "@/lib/types";
import { cn } from "@/lib/utils";

type Props = {
  board: Board;
  lastMove?: string | null;
  legalMoves?: string[];
  currentPlayer?: "black" | "white" | null;
  compact?: boolean;
};

const FILES = "abcdefgh";

function normalizeCell(cell: BoardCell) {
  if (cell === "B" || cell === "black") {
    return "black";
  }
  if (cell === "W" || cell === "white") {
    return "white";
  }
  return null;
}

function moveToPosition(move?: string | null): [number, number] | null {
  if (!move || move.length !== 2) {
    return null;
  }

  const col = FILES.indexOf(move[0].toLowerCase());
  const row = Number.parseInt(move[1], 10) - 1;
  if (col < 0 || Number.isNaN(row) || row < 0 || row > 7) {
    return null;
  }
  return [row, col];
}

export function OthelloBoard({ board, lastMove, legalMoves = [], currentPlayer, compact = false }: Props) {
  const lastMovePosition = moveToPosition(lastMove);
  const legalMovePositions = new Set(legalMoves.map((move) => moveToPosition(move)?.join(":")).filter(Boolean));

  return (
    <div className="space-y-3">
      <div className={cn("grid grid-cols-8 gap-1 rounded-xl bg-[#174a32] p-2 shadow-inner", compact && "gap-px p-1")}>
        {board.map((row, rowIndex) =>
          row.map((cell, colIndex) => {
            const occupant = normalizeCell(cell);
            const isLastMove = lastMovePosition?.[0] === rowIndex && lastMovePosition?.[1] === colIndex;
            const isLegalMove = legalMovePositions.has(`${rowIndex}:${colIndex}`);

            return (
              <div
                key={`${rowIndex}-${colIndex}`}
                className={cn(
                  "relative flex aspect-square items-center justify-center rounded-[6px] bg-[#2d7b52]",
                  compact ? "rounded-[4px]" : "min-h-10",
                  isLastMove && "ring-2 ring-amber-300",
                )}
              >
                {occupant ? (
                  <div
                    className={cn(
                      "h-4/5 w-4/5 rounded-full shadow-md",
                      occupant === "black" ? "bg-slate-950" : "bg-stone-50 ring-1 ring-slate-300",
                    )}
                  />
                ) : isLegalMove ? (
                  <div className="h-2.5 w-2.5 rounded-full bg-amber-200/90" />
                ) : null}
              </div>
            );
          }),
        )}
      </div>
      {currentPlayer ? (
        <div className="text-sm text-muted-foreground">
          Current player: <span className="font-medium text-foreground">{currentPlayer}</span>
        </div>
      ) : null}
    </div>
  );
}
