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
    
    # Track latest finalized user input for reply context (voice fallback)
    last_user_snippet = None
    last_user_name = None  # no 'You' fallback
    
    # Per-turn context from frontend handshake to avoid stale data
    current_turn = {"id": None, "identity": None, "name": None, "text": None}
    
    # Create agent session with basic plugins
    from livekit.agents import AgentSession, RoomInputOptions, RoomOutputOptions
    
    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="multi"),
        llm=google.LLM(model="gemini-2.0-flash-exp", temperature=0.7),
        tts=elevenlabs.TTS(
            voice_id=ELEVEN_VOICE_ID,
            model="eleven_turbo_v2_5",
        ),
        vad=silero.VAD.load(),
    )
    
    # Capture 'agent:turn' data packets from clients (with exhaustive logging)
    try:
        @ctx.room.on("data_packet_received")
        def _on_data_packet_received(data: bytes, participant, kind, topic: str | None = None):
            nonlocal current_turn, last_user_snippet, last_user_name
            try:
                raw = data or b""
                decoded = None
                try:
                    decoded = raw.decode("utf-8", errors="replace")
                except Exception:
                    decoded = "<decode-error>"
                pid = getattr(participant, "identity", None)
                print(f"📨 data_packet_received: len={len(raw)} topic={topic} kind={kind} participant={pid} decoded={decoded}")
                if topic != "agent:turn":
                    return
                payload = {}
                try:
                    payload = json.loads(decoded) if decoded else {}
                except Exception as e:
                    print("⚠️ JSON parse error for agent:turn:", e)
                pname = payload.get("userName") or payload.get("participantIdentity") or pid
                current_turn = {
                    "id": payload.get("turnId"),
                    "identity": payload.get("participantIdentity") or pid,
                    "name": pname,
                    "text": payload.get("text"),
                }
                if isinstance(current_turn.get("text"), str) and current_turn["text"].strip():
                    last_user_snippet = current_turn["text"].strip()
                    last_user_name = pname
                print(f"↩️  Turn handshake: id={current_turn['id']} identity={current_turn['identity']} name={current_turn['name']} text={(current_turn.get('text') or '')[:120]}")
            except Exception as e:
                print("data_packet_received handler error:", e)

        # Note: legacy data_received handler removed to avoid signature mismatch.
        # We rely solely on data_packet_received (above) which provides participant identity.
    except Exception as e:
        print("Note: binding room data handlers failed or unsupported:", e)
    
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
    pending_greeting = True
    @session.on("conversation_item_added")
    def _on_conversation_item_added(ev):
        nonlocal pending_greeting, current_turn
        try:
            role = getattr(ev.item, "role", None)
            text = getattr(ev.item, "text_content", "") or ""
            if role == "assistant" and text:
                payload = {
                    "type": "agent.chat",
                    "text": text,
                    "agentId": AGENT_NAME,
                    "ts": int(time.time() * 1000),
                }
                if pending_greeting:
                    payload["isGreeting"] = True
                    pending_greeting = False
                # Use the most recent explicit turn (if present)
                if current_turn.get("id") or current_turn.get("identity") or current_turn.get("name"):
                    if current_turn.get("identity"):
                        payload["replyToIdentity"] = current_turn["identity"]
                    if current_turn.get("name"):
                        payload["replyToName"] = current_turn["name"]
                    if current_turn.get("id"):
                        payload["turnId"] = current_turn["id"]
                    if current_turn.get("text"):
                        payload["replySnippet"] = current_turn["text"]
                    # reset once consumed
                    current_turn = {"id": None, "identity": None, "name": None, "text": None}
                elif last_user_snippet:
                    # Fallback to last finalized transcript only; include name if known
                    if last_user_name:
                        payload["replyToName"] = last_user_name
                    payload["replySnippet"] = last_user_snippet
                print(f"🤖 Agent reply: {text}")
                # Log reply meta being sent back
                try:
                    print(
                        f"↪️ Sending reply meta: name={payload.get('replyToName')}, "
                        f"identity={payload.get('replyToIdentity')}, turnId={payload.get('turnId')}, "
                        f"snippet={(payload.get('replySnippet') or '')[:120]}"
                    )
                except Exception:
                    pass
                asyncio.create_task(
                    ctx.room.local_participant.publish_data(
                        json.dumps(payload).encode("utf-8"),
                        reliable=True,
                        topic=CHAT_TOPIC,
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
    
    print("Agent connected to room, sending greeting (audio + chat)...")
    await session.say("Hello, I am Echo, your AI assistant. How can I help you today?")
    
    print("Agent connected to room, staying connected...")
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
        entrypoint_fnc=entrypoint,
            request_fnc=request_fnc,
        )
    )
