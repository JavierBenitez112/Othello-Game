"use client";

import { memo } from "react";

import { Board } from "@/lib/types";
import { cn } from "@/lib/utils";

type Props = {
  board?: Board;
  lastMove?: string | null;
  compact?: boolean;
};

function MiniOthelloBoardInner({ board, compact = false }: Props) {
  const safeBoard = board ?? Array.from({ length: 8 }, () => Array.from({ length: 8 }, () => "."));

  return (
    <div className={cn("grid grid-cols-8 gap-px rounded-lg bg-[#174a32] p-1", compact ? "w-28" : "w-40")}>
      {safeBoard.flatMap((row, rowIndex) =>
        row.map((cell, colIndex) => {
          const isBlack = cell === "B" || cell === "black";
          const isWhite = cell === "W" || cell === "white";
          return (
            <div key={`${rowIndex}-${colIndex}`} className="flex aspect-square items-center justify-center bg-[#2d7b52]">
              {isBlack ? <div className="h-2/3 w-2/3 rounded-full bg-slate-950" /> : null}
              {isWhite ? <div className="h-2/3 w-2/3 rounded-full bg-stone-50 ring-1 ring-slate-300" /> : null}
            </div>
          );
        }),
      )}
    </div>
  );
}

export const MiniOthelloBoard = memo(MiniOthelloBoardInner);
