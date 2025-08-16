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
import sys

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

def download_models():
    """Download required model files for the turn detector"""
    print("Downloading required model files...")
    try:
        # Import and initialize the turn detector to trigger model download
        from livekit.plugins.turn_detector.base import _download_from_hf_hub
        from livekit.plugins.turn_detector.base import HG_MODEL
        
        print("Downloading turn detector model files...")
        # Download the required files
        files_to_download = ['config.json', 'model.safetensors', 'tokenizer.json', 'tokenizer_config.json']
        
        for filename in files_to_download:
            print(f"Downloading {filename}...")
            _download_from_hf_hub(HG_MODEL, filename, local_files_only=False)
        
        print("Model files downloaded successfully!")
    except Exception as e:
        print(f"Error downloading models: {e}")
        print("Continuing without turn detection...")

if __name__ == "__main__":
    # Check if we need to download models
    if len(sys.argv) > 1 and sys.argv[1] == "download-files":
        download_models()
        sys.exit(0)
    
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
