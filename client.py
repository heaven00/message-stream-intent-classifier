import argparse
import asyncio
import websockets
import json


async def listen(url):
    async with websockets.connect(url) as websocket:
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            print(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="A WebSocket client to connect to a specified host and port."
    )
    parser.add_argument(
        "url",
        type=str,
        help="A URL corresponding to the WebSocket server (e.g., ws://127.0.0.1:8000)",
    )

    args = parser.parse_args()

    asyncio.run(listen(args.url))
