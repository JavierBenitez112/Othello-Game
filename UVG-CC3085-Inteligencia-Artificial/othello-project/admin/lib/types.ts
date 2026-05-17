export type BoardCell = "." | "B" | "W" | "black" | "white" | null;
export type Board = BoardCell[][];

export type Player = {
  id: number;
  name: string;
  connected?: boolean;
  score?: number;
  currentGameId?: string | null;
  gamesPlayed?: number;
  status?: string;
  discDifferential?: number | null;
};

export type TournamentStatus = "draft" | "registration" | "active" | "completed" | string;

export type Tournament = {
  id: string | number;
  name?: string;
  status: TournamentStatus;
  playerCount?: number;
  connectedPlayers?: number;
  currentRound?: number | null;
  totalRounds?: number | null;
  registrationStatus?: "open" | "closed" | string;
  createdAt?: string;
  metadata?: Record<string, unknown>;
  standings?: Standing[];
  rounds?: RoundSummary[];
  activeGames?: GameSummary[];
  players?: Player[];
};

export type RoundSummary = {
  id: string | number;
  roundNumber?: number;
  number?: number;
  status?: string;
  pairings?: Pairing[];
};

export type Round = {
  id: string | number;
  tournamentId?: string | number;
  number: number;
  status: string;
  pairings: Pairing[];
  results?: RoundResult[];
  activeGames?: GameSummary[];
};

export type Pairing = {
  gameId: string;
  board?: Board;
  blackPlayerId?: number;
  whitePlayerId?: number;
  blackPlayerName: string;
  whitePlayerName: string;
  status: string;
  result?: string | null;
  roundNumber?: number;
};

export type RoundResult = {
  gameId: string;
  result: string;
  winner?: string | null;
};

export type Move = {
  id?: string | number;
  moveNumber?: number;
  turnNumber?: number;
  player?: string;
  playerId?: number;
  color?: "black" | "white";
  move: string;
  boardAfter?: Board;
  timestamp?: string;
  createdAt?: string;
};

export type GameSummary = {
  id: string;
  tournamentId?: string | number;
  roundId?: string | number;
  roundNumber?: number;
  status: string;
  blackPlayerName: string;
  whitePlayerName: string;
  blackPlayerId?: number;
  whitePlayerId?: number;
  board?: Board;
  currentTurn?: "black" | "white" | null;
  countdownMs?: number | null;
  lastMove?: string | null;
  blackScore?: number | null;
  whiteScore?: number | null;
  scoreDifference?: number | null;
  updatedAt?: string;
  forfeitReason?: string | null;
};

export type Game = GameSummary & {
  legalMoves?: string[];
  moveHistory: Move[];
  winner?: string | null;
  result?: string | null;
  finalScore?: {
    black: number;
    white: number;
  };
};

export type Standing = {
  rank?: number;
  playerId: number;
  playerName: string;
  score: number;
  wins: number;
  losses: number;
  draws: number;
  byes: number;
  discDifferential?: number | null;
};

export type DashboardSummary = {
  activeTournament?: Tournament | null;
  registeredPlayers: number;
  connectedPlayers: number;
  activeGames: number;
  currentRound?: number | null;
};

export type LiveGamesResponse = {
  games: GameSummary[];
};

export type KnownLiveEventType =
  | "tournament_update"
  | "player_connected"
  | "player_disconnected"
  | "round_started"
  | "game_started"
  | "game_update"
  | "game_over"
  | "move_recorded"
  | "illegal_move"
  | "timeout"
  | "forfeit";

export type LiveEvent = {
  type: KnownLiveEventType;
  tournamentId?: string | number;
  roundId?: string | number;
  roundNumber?: number;
  gameId?: string;
  playerId?: number;
  playerName?: string;
  status?: string;
  board?: Board;
  currentTurn?: "black" | "white" | null;
  nextPlayer?: "black" | "white" | null;
  legalMoves?: string[];
  lastMove?: string | null;
  blackScore?: number;
  whiteScore?: number;
  remainingMs?: number;
  deadlineMs?: number;
  winner?: string | null;
  result?: string | null;
  move?: Move;
  timestamp?: string;
  [key: string]: unknown;
};
