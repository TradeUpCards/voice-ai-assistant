from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import (
    google,
    deepgram,
    cartesia,
    silero,
)
from livekit.plugins.turn_detector.multilingual import MultilingualModel 
import os
import asyncio
from aiohttp import web
import threading
import time

load_dotenv()

class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions="You are a helpful voice AI assistant powered by Google Gemini. Be conversational, friendly, and helpful. Keep responses concise but informative.")

async def request_fnc(req: agents.JobRequest):
    await req.accept(
        name="Echo-agent",  # This sets the display name
        identity="Echo (AI)"
    )

async def entrypoint(ctx: agents.JobContext):
    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="multi"),
        llm=google.LLM(
            model="gemini-2.0-flash-exp",
            temperature=0.7,
        ),
        tts=cartesia.TTS(model="sonic-2", voice="4f7f1324-1853-48a6-b294-4e78e8036a83"),
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
    )

    await session.start(
        room=ctx.room,
        agent=Assistant(),
    )

    await session.generate_reply(
        instructions="Greet the user warmly and offer your assistance. Mention that you're powered by Google Gemini and ready to help with any questions or tasks."
    )

# Health check endpoint
async def health_check(request):
    return web.Response(text="OK", status=200)

async def start_web_server():
    port = int(os.environ.get('PORT', 10000))
    app = web.Application()
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Health check server running on port {port}")
    return runner

def run_web_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    runner = loop.run_until_complete(start_web_server())
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(runner.cleanup())
        loop.close()

if __name__ == "__main__":
    # Start health check server in a separate thread
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    
    # Give the web server a moment to start up
    time.sleep(2)
    
    # Run the LiveKit agent
    agents.cli.run_app(agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
        request_fnc=request_fnc
    ))
