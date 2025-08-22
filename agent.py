# agent.py
# Echo agent with your original ElevenLabs voice:
# - Uses your prior voice_id ("1QHS0LeWK66KMx5bufOz") + explicit model
# - Adds Silero VAD for snappier endpointing
# - Streams live STT logs (partials/finals)
# - Sends assistant text to your UI on topic "chat:agent"
# - Publishes audio + synced transcription to the room

import os
import json
import time
import asyncio
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobRequest,
    WorkerOptions,
    cli,
    RoomInputOptions,
    RoomOutputOptions,
    UserInputTranscribedEvent,
    ConversationItemAddedEvent,
)

from livekit.plugins import deepgram, google, elevenlabs, silero

load_dotenv()

AGENT_IDENTITY = "Echo (AI)"   # what appears in the participant list
AGENT_NAME = "echo-ai"         # internal/logical name
CHAT_TOPIC = "chat:agent"      # your web client listens for this

ELEVEN_VOICE_ID = "1QHS0LeWK66KMx5bufOz"  # <-- your original voice


class VoiceAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are Echo, a helpful, friendly voice AI assistant. "
                "Be concise, conversational, and helpful."
            )
        )

    async def on_user_turn_completed(self, chat_ctx, new_message):
        if new_message.text_content:
            print(f"🧑 Final user transcript: {new_message.text_content}")


async def request_fnc(req: JobRequest):
    await req.accept(name=AGENT_NAME, identity=AGENT_IDENTITY)


async def entrypoint(ctx: JobContext):
    print("Voice agent starting up...")
    
    # Track latest finalized user input for reply context
    last_user_snippet = None
    last_user_name = "You"
    
    # Create agent session with basic plugins
    from livekit.agents import AgentSession, RoomInputOptions, RoomOutputOptions
    
    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="multi"),
        llm=google.LLM(model="gemini-2.0-flash-exp", temperature=0.7),
        tts=elevenlabs.TTS(voice_id="1QHS0LeWK66KMx5bufOz"),  
    )
    
    # Event: capture final user transcripts for reply context
    @session.on("user_input_transcribed")
    def _on_user_input_transcribed(ev):
        nonlocal last_user_snippet
        try:
            if getattr(ev, "is_final", False) and getattr(ev, "transcript", ""):
                last_user_snippet = ev.transcript
                print(f"📝 Final user transcript: {last_user_snippet}")
        except Exception as e:
            print("user_input_transcribed handler error:", e)

    # Event: forward assistant replies to frontend via data channel with reply context
    @session.on("conversation_item_added")
    def _on_conversation_item_added(ev):
        try:
            role = getattr(ev.item, "role", None)
            text = getattr(ev.item, "text_content", "") or ""
            if role == "assistant" and text:
                payload = {
                    "type": "agent.chat",
                    "text": text,
                    "agentId": "echo-ai",
                    "ts": int(time.time() * 1000),
                }
                if last_user_snippet:
                    payload["replyToName"] = last_user_name
                    payload["replySnippet"] = last_user_snippet
                print(f"🤖 Agent reply: {text}")
                asyncio.create_task(
                    ctx.room.local_participant.publish_data(
                        json.dumps(payload).encode("utf-8"),
                        reliable=True,
                        topic="chat:agent",
                    )
                )
        except Exception as e:
            print("conversation_item_added handler error:", e)
    
    print("Agent session created, joining room...")
    await session.start(
        room=ctx.room,
        agent=VoiceAgent(),
        room_input_options=RoomInputOptions(audio_enabled=True, text_enabled=True),
        room_output_options=RoomOutputOptions(audio_enabled=True, transcription_enabled=True, sync_transcription=True),
    )
    
    print("Agent connected to room, sending greeting...")
    greeting = "Hello, I am Echo, your AI assistant. How can I help you today?"
    try:
        greet_payload = {
            "type": "agent.chat",
            "text": greeting,
            "agentId": "echo-ai",
            "ts": int(time.time() * 1000),
        }
        await ctx.room.local_participant.publish_data(
            json.dumps(greet_payload).encode("utf-8"),
            reliable=True,
            topic="chat:agent",
        )
    except Exception as e:
        print("Error sending greeting via data channel:", e)
    
    print("Agent connected to room, staying connected...")
    # Keep agent alive in the room
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            request_fnc=request_fnc,
        )
    )
