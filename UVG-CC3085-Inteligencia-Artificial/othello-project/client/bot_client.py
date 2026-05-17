from __future__ import annotations

import argparse
import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from urllib import error, request

import websockets

logger = logging.getLogger(__name__)

ChooseMove = Callable[[list[list[str]], str, list[str]], str | Awaitable[str]]


class BotClient:
    def __init__(
        self,
        server_url: str,
        tournament_name: str,
        username: str,
        choose_move: ChooseMove,
        reconnect_delay_seconds: float = 1.0,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.tournament_name = tournament_name
        self.username = username
        self.choose_move = choose_move
        self.reconnect_delay_seconds = reconnect_delay_seconds
        self.player_id: int | None = None
        self.token: str | None = None

    async def run_forever(self) -> None:
        if self.player_id is None or self.token is None:
            await asyncio.to_thread(self._enroll)

        while True:
            assert self.player_id is not None
            assert self.token is not None
            ws_url = f"{self.server_url.replace('http', 'ws')}/ws/{self.player_id}?token={self.token}"
            try:
                logger.info("Connecting to %s", ws_url)
                async with websockets.connect(ws_url) as websocket:
                    await self._run_connection(websocket)
            except Exception as exc:
                logger.warning("Connection dropped: %s", exc)
                await asyncio.sleep(self.reconnect_delay_seconds)

    async def _run_connection(self, websocket) -> None:
        async for raw_message in websocket:
            payload = json.loads(raw_message)
            message_type = payload.get("type")

            if message_type == "your_turn":
                move = await self._choose_move(
                    payload["board"],
                    payload["color"],
                    payload["legal_moves"],
                )
                await websocket.send(
                    json.dumps(
                        {
                            "type": "move",
                            "game_id": payload["game_id"],
                            "move": move,
                        }
                    )
                )
                logger.info("Submitted move %s for game %s", move, payload["game_id"])
            elif message_type == "game_update":
                logger.info(
                    "Game %s updated: next_player=%s last_move=%s",
                    payload["game_id"],
                    payload["next_player"],
                    payload["last_move"],
                )
            elif message_type == "game_over":
                logger.info(
                    "Game %s finished: result=%s score=%s-%s",
                    payload["game_id"],
                    payload["result"],
                    payload["black_score"],
                    payload["white_score"],
                )
            else:
                logger.info("Received message: %s", payload)

    async def _choose_move(self, board: list[list[str]], color: str, legal_moves: list[str]) -> str:
        result = self.choose_move(board, color, legal_moves)
        if asyncio.iscoroutine(result):
            return await result
        return result

    def _enroll(self) -> None:
        enroll_url = f"{self.server_url}/players"
        payload = json.dumps({"tournament_name": self.tournament_name, "name": self.username}).encode("utf-8")
        http_request = request.Request(
            enroll_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=10) as response:
                body = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Enrollment failed: {exc.code} {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Enrollment failed: {exc.reason}") from exc

        self.player_id = int(body["player_id"])
        self.token = str(body["client_token"])
        logger.info(
            "Enrolled in tournament %s as %s (player_id=%s)",
            body.get("tournament_name", self.tournament_name),
            body["name"],
            self.player_id,
        )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reusable Othello bot client")
    parser.add_argument("--server-url", default="http://localhost:8000")
    parser.add_argument("--tournament-name", required=True)
    parser.add_argument("--username", required=True)
    return parser


async def _missing_bot(*_: Any) -> str:
    raise RuntimeError("Pass a choose_move implementation when instantiating BotClient")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = build_arg_parser().parse_args()
    client = BotClient(
        server_url=args.server_url,
        tournament_name=args.tournament_name,
        username=args.username,
        choose_move=_missing_bot,
    )
    asyncio.run(client.run_forever())


if __name__ == "__main__":
    main()
