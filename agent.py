from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import (
    google,
    deepgram,
    elevenlabs,
    silero,
    noise_cancellation,
)
from livekit.plugins.turn_detector.multilingual import MultilingualModel

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
    print(f"🚀 Agent entrypoint called with context: {ctx}")
    print(f"🏠 Room: {ctx.room.name}")
    print(f"👤 Local participant: {ctx.room.local_participant.identity}")
    
    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="multi"),
        llm=google.LLM(
            model="gemini-2.0-flash-exp",
            temperature=0.7,
        ),
        tts=elevenlabs.TTS(voice="7p1Ofvcwsv7UBPoFNcpI"),
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
    )
    
    print("📡 Starting AgentSession...")
    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )
    print("✅ AgentSession started successfully!")
    
    # Generate a simple greeting without TTS
    print("🤖 Agent joining room...")
    print("📝 Generating greeting with Gemini...")
    
    # Try to get a text response directly from Gemini
    try:
        response = await session.generate_reply(
            instructions="Say 'Hello, I am Echo, your AI assistant."
        )
        print(f"✅ Gemini response generated: {response}")
        
        # Try to extract the actual text content
        print("🔍 Attempting to extract response text...")
        
        # Method 1: Check if response has text attribute
        if hasattr(response, 'text') and response.text:
            print(f"📝 Response text: {response.text}")
        
        # Method 2: Check if response has content attribute
        elif hasattr(response, 'content') and response.content:
            print(f"📝 Response content: {response.content}")
        
        # Method 3: Check if response has message attribute
        elif hasattr(response, 'message') and response.message:
            print(f"📝 Response message: {response.message}")
        
        # Method 4: Check chat_items specifically
        elif hasattr(response, 'chat_items') and response.chat_items:
            print(f"📝 Chat items found: {response.chat_items}")
            for i, item in enumerate(response.chat_items):
                print(f"  Item {i}: {item}")
                if hasattr(item, 'content'):
                    print(f"    Content: {item.content}")
                if hasattr(item, 'text'):
                    print(f"    Text: {item.text}")
        
        # Method 5: Check all available attributes
        else:
            print(f"🔍 Response attributes: {dir(response)}")
            print(f"🔍 Response type: {type(response)}")
            
    except Exception as e:
        print(f"❌ Error generating response: {e}")
        print("🤔 This suggests TTS is required for generate_reply to work")

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
        request_fnc=request_fnc
    ))
