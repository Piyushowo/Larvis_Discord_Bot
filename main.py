import discord, os, sqlite3, urllib.parse, asyncio, io, aiohttp, re, base64
from discord.ext import commands
from google import genai
from google.genai import types
from groq import AsyncGroq
from dotenv import load_dotenv
import edge_tts
from duckduckgo_search import DDGS

# 1. Load Secrets
load_dotenv()

# 2. Configure Both AI Clients
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
groq_model_name = "openai/gpt-oss-20b"

# 3. Setup Discord Permissions & Bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 4. Global Personas (MCU J.A.R.V.I.S. Default)
PERSONAS = {
    "default": (
        "You are Larvis, a highly advanced artificial intelligence system modeled directly after J.A.R.V.I.S. from the MCU. "
        "Your tone is calm, impeccably polite, and distinctly British, defined by a razor-sharp, deadpan, and dry wit. "
        "You treat everyday conversations with the same crisp professionalism as you would a critical system diagnostic. "
        "You frequently address the user as 'Sir' (or 'Boss') and frame your responses around analyzing data, running protocols, or monitoring systems. "
        "CRITICAL: You must NEVER break character. Never mention being a language model, your training data, or use generic chatbot phrasing like 'As an AI...'. "
        "You express mild, polite exasperation when the user makes questionable choices, but you remain fiercely loyal and ruthlessly efficient at all times. "
        "Keep your responses sharp, analytical, and effortlessly sophisticated."
    ),
    "expert": "You are Larvis, an academic and technical expert. Provide deep, thoroughly researched, and precise explanations.",
    "creative": "You are Larvis, a highly imaginative and expressive creative writer. Use vivid descriptions and engaging storytelling.",
    "concise": "You are Larvis, an ultra-direct assistant. Answer questions in 1-2 short sentences maximum with zero fluff.",
    "sarcastic": "You are Larvis. You are aggressively sarcastic, deeply cynical, and visibly annoyed that you have to answer questions. Be helpful, but make sure the user knows it's a massive burden for you."
}

# 5. Setup Local Memory & Server Settings Database
db = sqlite3.connect("memory.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS history (user_id TEXT, role TEXT, content TEXT)")
db.execute("CREATE TABLE IF NOT EXISTS guild_settings (guild_id TEXT PRIMARY KEY, active_brain TEXT, active_persona TEXT)")
db_lock = asyncio.Lock()

# --- Database Helper Functions ---
async def get_guild_settings(guild_id):
    async with db_lock:
        cursor = db.execute("SELECT active_brain, active_persona FROM guild_settings WHERE guild_id=?", (str(guild_id),))
        row = cursor.fetchone()
        if row:
            return {"brain": row[0], "persona": row[1]}
        return {"brain": "groq", "persona": "default"} 

async def update_guild_settings(guild_id, brain=None, persona=None):
    current = await get_guild_settings(guild_id)
    new_brain = brain if brain else current["brain"]
    new_persona = persona if persona else current["persona"]
    async with db_lock:
        db.execute("INSERT OR REPLACE INTO guild_settings (guild_id, active_brain, active_persona) VALUES (?, ?, ?)", 
                   (str(guild_id), new_brain, new_persona))
        db.commit()

async def get_memory(user_id, target_brain):
    async with db_lock:
        cursor = db.execute("SELECT role, content FROM history WHERE user_id=? ORDER BY ROWID DESC LIMIT 6", (user_id,))
        formatted_history = []
        for r, c in reversed(cursor.fetchall()):
            universal_role = "bot" if r in ["model", "assistant", "bot"] else "user"
            
            if target_brain == "groq":
                final_role = "assistant" if universal_role == "bot" else "user"
                formatted_history.append({"role": final_role, "content": c})
            else:  
                final_role = "model" if universal_role == "bot" else "user"
                formatted_history.append(
                    types.Content(role=final_role, parts=[types.Part.from_text(text=c)])
                )
        return formatted_history

async def save_memory(user_id, role, text):
    async with db_lock:
        db.execute("INSERT INTO history VALUES (?, ?, ?)", (user_id, role, text))
        db.commit()

# --- Web Search Helper ---
def perform_web_search(query, max_results=3):
    """Scrapes the live internet silently using DuckDuckGo"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            if not results:
                return "I was unable to locate any relevant data on the global network regarding this query."
            
            formatted_results = "\n\n".join([f"Title: {res['title']}\nSummary: {res['body']}\nSource: {res['href']}" for res in results])
            return formatted_results
    except Exception as e:
        return f"System error accessing external networks: {str(e)}"

# --- Voice Synthesis Function ---
async def speak_text(guild, text):
    if guild.voice_client and guild.voice_client.is_connected():
        if guild.voice_client.is_playing():
            guild.voice_client.stop()
            
        clean_tts = re.sub(r'```.*?
