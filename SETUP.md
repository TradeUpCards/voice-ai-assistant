# Voice AI Setup Guide

This project provides a complete voice AI assistant using LiveKit, Google Gemini, Deepgram, and Cartesia.

## Prerequisites

- Node.js 18+ and pnpm
- Python 3.9+
- LiveKit Cloud account
- Google Gemini API key
- Deepgram API key (free tier available)
- Cartesia API key (free tier available)

## Quick Start

### 1. Install Dependencies

```bash
# Frontend dependencies
pnpm install

# Python dependencies
python -m venv venv
source venv/Scripts/activate  # On Windows
# source venv/bin/activate     # On Mac/Linux
pip install "livekit-agents[google,deepgram,cartesia,silero,turn-detector]~=1.2" "livekit-plugins-noise-cancellation~=0.2" "python-dotenv"
```

### 2. Environment Setup

Copy `env.template` to `.env` and fill in your API keys:

```bash
cp env.template .env
# Edit .env with your actual API keys
```

### 3. Download AI Models

```bash
source venv/Scripts/activate  # On Windows
python agent.py download-files
```

### 4. Start the Services

**Terminal 1 - Python Agent:**
```bash
source venv/Scripts/activate
python agent.py dev
```

**Terminal 2 - React Frontend:**
```bash
pnpm dev
```

### 5. Test Voice AI

1. Open http://localhost:3001
2. Click "Start call"
3. Allow microphone permissions
4. Start talking to your AI!

## Features

- 🎤 **Real-time voice conversation**
- 🤖 **Powered by Google Gemini**
- 🗣️ **High-quality speech-to-text (Deepgram)**
- 🔊 **Natural text-to-speech (Cartesia)**
- 🎯 **Smart turn detection**
- 🚫 **Noise cancellation**
- 🌐 **Web-based interface**

## Integration

To integrate this into another project:

1. Copy the `agent.py` file
2. Copy the `components/livekit/` directory
3. Install the Python dependencies
4. Set up your environment variables
5. Run the agent alongside your main application

## Troubleshooting

- **Agent not joining room**: Check LiveKit credentials in `.env`
- **No voice output**: Verify Cartesia API key
- **Speech not recognized**: Check Deepgram API key
- **AI not responding**: Verify Google Gemini API key

## API Key Sources

- **LiveKit**: [cloud.livekit.io](https://cloud.livekit.io)
- **Google Gemini**: [ai.google.dev](https://ai.google.dev)
- **Deepgram**: [deepgram.com](https://deepgram.com)
- **Cartesia**: [cartesia.ai](https://cartesia.ai)
