**Larvis AI — The Advanced Discord Assistant**

Larvis is a high-performance, production-ready Discord companion modeled after the MCU's J.A.R.V.I.S. It features a dual-brain architecture routing between Groq (for ultra-fast conversational speed) and Google Gemini (for deep reasoning and computer vision). Larvis operates completely autonomously across multiple servers, offering persistent local memory, real-time web search, AI art generation, and high-fidelity voice synthesis.


**Core Features**

1] Dual-Brain Architecture: Seamlessly swap the active LLM engine dynamically. Use Groq (gpt-oss-20b) for near-instant conversational responses, or Gemini (gemini-3.6-flash) for deep, analytical reasoning.

2] MCU Voice Synthesis: Using edge-tts, Larvis can join Discord Voice Channels and read his responses aloud using a crisp, professional British neural voice (en-GB-RyanNeural), complete with deadpan MCU-style delivery.

3] Live Web Search: Integrated with DuckDuckGo, Larvis can scrape the live internet to pull up-to-date data on current events and summarize it in character.

4] Smart Auto-Vision: Drop an image into chat and mention Larvis. The system automatically bypasses Groq, routes the image to Gemini Vision, analyzes the visual data, and replies natively in chat.

5] Multi-Model Image Generation: Generate 1024x1024 AI artwork on demand using Flux, Midjourney-style, or Anime models via Pollinations.ai.

6] Per-Server Autonomy: Powered by SQLite, Larvis tracks separate conversational histories and custom settings (active brain and active persona) for every single Discord guild he joins.

7] Dynamic Personas: Instantly shift Larvis's behavior between his default MCU J.A.R.V.I.S. personality, a strict Technical Expert, a Storyteller, a Concise assistant, or an aggressively Sarcastic bot.

8] Effortless Activation: No prefixes required for chat. Simply include the word "larvis" anywhere in your message or ping him, and he will respond.



**Command Reference**

Larvis operates entirely on modern Discord Slash Commands (/) for tools, and natural language for chat.

<img width="713" height="540" alt="image" src="https://github.com/user-attachments/assets/4aeb3993-f007-4a70-a002-3f64e2d1fa52" />



**Tech Stack**

Language: Python 3.10+

Discord Framework: discord.py (with PyNaCl for Voice)

AI Engines: groq (Text) & google-genai (Text & Vision)

Audio Synthesis: edge-tts & FFmpeg

Web Search: duckduckgo-search

Image Generation: aiohttp & Pollinations API

Database: sqlite3 (Local file-based persistent memory)


**Installation & Setup**

1. Clone the repository and install dependencies:

 pip install -r requirements.txt

 Required packages: discord.py[voice], google-genai, groq, python-dotenv, aiohttp, Pillow, PyNaCl, edge-tts, duckduckgo-search.
(Note: You must have FFmpeg installed on your system/server for voice features to function).

2. Configure your Environment Variables:
Create a .env file in the root directory and add your API keys:
DISCORD_TOKEN=your_discord_bot_token_here
GEMINI_API_KEY=your_google_gemini_key_here
GROQ_API_KEY=your_groq_api_key_here


3. Initialize the Bot:

python main.py




Youre done! You have your Larvis running.
