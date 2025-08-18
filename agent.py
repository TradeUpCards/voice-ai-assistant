from livekit.agents import JobContext, WorkerOptions, cli, Agent, JobRequest
from livekit.plugins import deepgram, google, elevenlabs
from dotenv import load_dotenv
import asyncio

load_dotenv()

class VoiceAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions="You are Echo, a helpful voice AI assistant. Be conversational and friendly."
        )

async def request_fnc(req: JobRequest):
    await req.accept(
        name="Echo (AI)", # This is the display name in the UI
        identity="echo-ai" # This is the internal identifier
    )

async def entrypoint(ctx: JobContext):
    print("Voice agent starting up...")
    
    # Create agent session with basic plugins
    from livekit.agents import AgentSession
    
    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="multi"),
        llm=google.LLM(model="gemini-2.0-flash-exp", temperature=0.7),
        tts=elevenlabs.TTS(voice_id="1QHS0LeWK66KMx5bufOz"),  
    )
    
    print("Agent session created, joining room...")
    await session.start(room=ctx.room, agent=VoiceAgent())
    
    print("Agent connected to room, generating greeting...")
    
    # Generate a greeting when joining the room
    print("Generating greeting...")
    response = await session.generate_reply(
        instructions="Say 'Hello, I am Echo, your AI assistant. How can I help you today?'"
    )
    
    # Extract and send the response text to frontend
    if hasattr(response, '_chat_items') and response._chat_items:
        for item in response._chat_items:
            if hasattr(item, 'content') and item.content:
                response_text = item.content[0] if isinstance(item.content, list) else str(item.content)
                print(f"Agent response: {response_text}")
                
                # Send response text to frontend via data channel
                try:
                    await ctx.room.local_participant.publish_data(
                        payload=response_text.encode('utf-8'),
                        topic="chat"
                    )
                    print("Response sent to frontend chat!")
                except Exception as e:
                    print(f"Error sending to frontend: {e}")
    
    print("Greeting generated successfully!")
    
    print("Agent connected to room, staying connected...")
    # Keep agent alive in the room
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        request_fnc=request_fnc
    ))
