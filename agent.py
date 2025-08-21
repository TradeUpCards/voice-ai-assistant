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
    print("⚙️  Starting Echo agent…")

    # --- Build the voice stack ---
    # Notes:
    # - Deepgram set to English for slightly lower latency vs "multi"
    # - ElevenLabs voice = your original voice_id + explicit model to avoid silent streams
    # - Silero VAD resolves "VAD is not set" and speeds up end-of-turn detection
    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="en"),
        llm=google.LLM(model="gemini-2.0-flash-exp", temperature=0.7),
        tts=elevenlabs.TTS(
            voice_id=ELEVEN_VOICE_ID,
            model="eleven_turbo_v2_5",   # explicit model helps prevent "no audio frames" issues
            # auto_mode=True,            # optional: can reduce latency on longer phrases
        ),
        vad=silero.VAD.load(),
    )

    agent = VoiceAgent()

    # ----- Event wiring (before start) -----

    # (A) Live STT (partials & finals)
    @session.on("user_input_transcribed")
    def _on_user_input_transcribed(ev: UserInputTranscribedEvent):
        print(f"📝 STT: {ev.transcript} (final={ev.is_final}, speaker={ev.speaker_id})")

    # (B) Forward assistant replies as chat data to the frontend
    @session.on("conversation_item_added")
    def _on_conversation_item_added(ev: ConversationItemAddedEvent):
        role = ev.item.role  # "user" or "assistant"
        text = ev.item.text_content or ""
        if role == "assistant" and text:
            print(f"🤖 Agent reply: {text}")
            payload = {
                "type": "agent.chat",
                "text": text,
                "agentId": AGENT_NAME,
                "ts": int(time.time() * 1000),
            }
            asyncio.create_task(
                ctx.room.local_participant.publish_data(
                    json.dumps(payload).encode("utf-8"),
                    reliable=True,
                    topic=CHAT_TOPIC,
                )
            )

    # ----- Start the session -----
    await session.start(
        room=ctx.room,
        agent=agent,
        room_input_options=RoomInputOptions(
            audio_enabled=True,
            text_enabled=True,  # if you also send text via lk.chat or custom UI
        ),
        room_output_options=RoomOutputOptions(
            audio_enabled=True,             # ensure agent audio is published
            transcription_enabled=True,     # send transcripts to clients
            sync_transcription=True,        # align captions with TTS playback
        ),
    )

    # Greeting (goes through the same pipeline: TTS + chat payload)
    await session.say("Hello, I am Echo, your AI assistant. How can I help you today?")

    print("✅ Echo is live. Waiting for turns…")
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            request_fnc=request_fnc,
        )
    )
