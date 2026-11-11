"""Service de transcription streaming (Deepgram WebSocket).

Relaye des chunks audio vers Deepgram et invoque des callbacks pour le texte
partiel et final. Utilisé par le proxy WebSocket du backend.
"""

from collections.abc import AsyncIterator, Awaitable, Callable

import websockets

DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"

PartialCb = Callable[[str], Awaitable[None]]
FinalCb = Callable[[str], Awaitable[None]]


async def stream_deepgram(
    audio_chunks: AsyncIterator[bytes],
    api_key: str,
    language: str = "fr",
    model: str = "nova-2",
    on_partial: PartialCb | None = None,
    on_final: FinalCb | None = None,
) -> None:
    """Ouvre une session Deepgram, envoie les chunks, relaie les transcripts."""
    params = (
        f"?model={model}&language={language}"
        "&smart_format=true&punctuate=true&interim_results=true&encoding=opus"
    )
    headers = {"Authorization": f"Token {api_key}"}

    async with websockets.connect(DEEPGRAM_WS_URL + params, additional_headers=headers) as dg:
        import asyncio

        async def sender() -> None:
            async for chunk in audio_chunks:
                await dg.send(chunk)
            # signal de fin
            await dg.send(b'{"type":"CloseStream"}')

        async def receiver() -> None:
            import json

            async for raw in dg:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if msg.get("type") != "Results":
                    continue
                alt = msg.get("channel", {}).get("alternatives", [{}])[0]
                text = alt.get("transcript", "").strip()
                if not text:
                    continue
                if msg.get("is_final"):
                    if on_final:
                        await on_final(text)
                elif on_partial:
                    await on_partial(text)

        send_task = asyncio.create_task(sender())
        recv_task = asyncio.create_task(receiver())
        try:
            await asyncio.gather(send_task, recv_task)
        finally:
            for task in (send_task, recv_task):
                if not task.done():
                    task.cancel()
