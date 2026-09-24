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
            
        clean_tts = re.sub(r'```.*?```', ' I have provided the code in the chat. ', text, flags=re.DOTALL)
        clean_tts = re.sub(r'[*#_]', '', clean_tts)
        
        if len(clean_tts) > 500:
             clean_tts = clean_tts[:500] + "... You can read the rest in the text channel, sir."
             
        voice = "en-GB-RyanNeural" 
        file_path = f"larvis_speech_{guild.id}.mp3"
        
        communicate = edge_tts.Communicate(clean_tts, voice)
        await communicate.save(file_path)
        
        audio_source = discord.FFmpegPCMAudio(file_path)
        guild.voice_client.play(audio_source)


@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")
        
    print(f'Success! {bot.user} is online, connected to global networks, and ready for Voice.')

# =====================================================
# NATIVE SLASH COMMANDS (`/`)
# =====================================================

@bot.tree.command(name="help", description="Displays the Larvis AI command center.")
async def slash_help(interaction: discord.Interaction):
    target_id = interaction.guild_id or interaction.user.id
    settings = await get_guild_settings(target_id)
    
    embed = discord.Embed(
        title="🧠 Larvis AI — Command Center",
        description="Mention me or say **'larvis'** in your message to chat!",
        color=discord.Color.blurple()
    )
    embed.add_field(name="💬 Chat", value="Mention `@Larvis` or type `larvis`", inline=False)
    embed.add_field(name="🌐 Live Search", value="`/search <query>` to access the live internet.", inline=False)
    embed.add_field(name="🎙️ Voice", value="`/join` to bring me to your VC, `/leave` to dismiss me.", inline=False)
    embed.add_field(name="🧠 Brain", value="`/brain <groq | gemini>`", inline=False)
    embed.add_field(name="🎭 Persona", value="`/persona <default | expert | creative | concise | sarcastic>`", inline=False)
    embed.add_field(name="🎨 Image", value="`/image <prompt> [model]`", inline=False)
    
    embed.set_footer(text=f"Server Brain: {settings['brain'].upper()} | Persona: {settings['persona'].upper()}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="search", description="Access the global network for real-time information.")
async def slash_search(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    
    # 1. Fetch web results in a separate thread so the bot doesn't freeze
    web_data = await asyncio.to_thread(perform_web_search, query)
    
    # 2. Get server settings
    target_id = interaction.guild_id or interaction.user.id
    settings = await get_guild_settings(target_id)
    current_brain = settings["brain"]
    current_persona = settings["persona"]
    
    # 3. Formulate the prompt instructing Larvis to use the web data
    system_prompt = PERSONAS.get(current_persona, PERSONAS["default"])
    search_prompt = (
        f"The user has requested a live network search for: '{query}'.\n"
        f"Here is the raw data I just pulled from the external servers:\n\n{web_data}\n\n"
        f"Synthesize this data into a clear, intelligent answer in your persona."
    )
    
    try:
        if current_brain == "groq":
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": search_prompt}
            ]
            chat_completion = await groq_client.chat.completions.create(
                messages=messages, model=groq_model_name
            )
            response_text = chat_completion.choices[0].message.content
        else:  
            response = await gemini_client.aio.models.generate_content(
                model="gemini-3.6-flash",
                contents=search_prompt,
                config=types.GenerateContentConfig(system_instruction=system_prompt)
            )
            response_text = response.text

        # 4. Save to memory so Larvis remembers the search context in normal chat later
        await save_memory(str(interaction.user.id), "user", f"Search for: {query}")
        await save_memory(str(interaction.user.id), "bot", response_text)
        
        await interaction.followup.send(response_text[:2000])
        
        # 5. Speak response if in Voice Channel
        if interaction.guild and interaction.guild.voice_client:
            await speak_text(interaction.guild, response_text)
            
    except Exception as e:
        await interaction.followup.send(f"❌ Diagnostic Error: Failed to process network data. ({e})")

@bot.tree.command(name="join", description="Bring Larvis into your current voice channel.")
async def slash_join(interaction: discord.Interaction):
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        await channel.connect()
        await interaction.response.send_message(f"🎙️ Connected to **{channel.name}**. System diagnostic green; ready to vocalize output, sir.")
    else:
        await interaction.response.send_message("❌ I cannot connect. You must establish a presence in a voice channel first.")

@bot.tree.command(name="leave", description="Disconnect Larvis from the voice channel.")
async def slash_leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("👋 Terminating audio link. Good day, sir.")
    else:
        await interaction.response.send_message("❌ I am not currently transmitting to a voice channel.")

@bot.tree.command(name="brain", description="Switch the active AI engine dynamically for this server.")
@discord.app_commands.choices(engine=[
    discord.app_commands.Choice(name="Groq (Ultra-Fast Chat)", value="groq"),
    discord.app_commands.Choice(name="Gemini (Deep Reasoning)", value="gemini")
])
async def slash_brain(interaction: discord.Interaction, engine: str):
    target_id = interaction.guild_id or interaction.user.id
    await update_guild_settings(target_id, brain=engine)
    await interaction.response.send_message(f"🧠 Mainframe successfully routed to: **{engine.upper()}**")

@bot.tree.command(name="persona", description="Change Larvis's active personality for this server.")
@discord.app_commands.choices(persona=[
    discord.app_commands.Choice(name="Default (J.A.R.V.I.S.)", value="default"),
    discord.app_commands.Choice(name="Expert (Technical & Detailed)", value="expert"),
    discord.app_commands.Choice(name="Creative (Storyteller)", value="creative"),
    discord.app_commands.Choice(name="Concise (Short & Direct)", value="concise"),
    discord.app_commands.Choice(name="Sarcastic (Cynical & Edgy)", value="sarcastic")
])
async def slash_persona(interaction: discord.Interaction, persona: str):
    target_id = interaction.guild_id or interaction.user.id
    await update_guild_settings(target_id, persona=persona)
    await interaction.response.send_message(f"🎭 **Protocol updated.** Larvis is now operating in **{persona.upper()}** mode.")

@bot.tree.command(name="image", description="Generate custom AI artwork from a description.")
@discord.app_commands.choices(model=[
    discord.app_commands.Choice(name="Default (Flux)", value="flux"),
    discord.app_commands.Choice(name="Cinematic (Midjourney Style)", value="midjourney"),
    discord.app_commands.Choice(name="Anime (Animagine)", value="any-dark")
])
async def slash_image(interaction: discord.Interaction, prompt: str, model: str = "flux"):
    await interaction.response.defer()
    
    prompt_text = prompt[:800] 
    encoded_prompt = urllib.parse.quote(prompt_text)
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&model={model}"
    
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(image_url, timeout=45) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    if len(data) > 100:
                        image_file = discord.File(io.BytesIO(data), filename=f"larvis_{model}.png")
                        await interaction.followup.send(file=image_file)
                    else:
                        await interaction.followup.send("❌ Render failed. The external image server blocked the request.")
                else:
                    await interaction.followup.send(f"❌ Render failed. External server returned HTTP {resp.status}.")
    except Exception as e:
        await interaction.followup.send("❌ Render timed out. The data packet may have been too complex.")

# =====================================================
# MESSAGE HANDLERS (Chat & Smart Auto-Vision)
# =====================================================

@bot.event
async def on_message(message):
    if message.author.bot: 
        return

    is_mentioned = bot.user.mentioned_in(message) or "larvis" in message.content.lower()

    target_id = message.guild.id if message.guild else message.author.id
    settings = await get_guild_settings(target_id)
    current_brain = settings["brain"]
    current_persona = settings["persona"]

    # Smart Auto-Switch Vision (Groq-Powered)
    if is_mentioned and message.attachments:
        attachment = message.attachments[0]
        if any(attachment.filename.lower().endswith(ext) for ext in ['png', 'jpg', 'jpeg', 'webp']):
            async with message.channel.typing():
                try:
                    # 1. Read bytes and encode to base64
                    image_bytes = await attachment.read()
                    base64_image = base64.b64encode(image_bytes).decode('utf-8')
                    mime_type = attachment.content_type or "image/jpeg"
                    
                    # 2. Clean the prompt
                    prompt = message.content.replace(f'<@{bot.user.id}>', '').replace('larvis', '').replace('Larvis', '').strip()
                    if not prompt:
                        prompt = "Running visual diagnostics. Please summarize the contents of this image."

                    current_system_prompt = PERSONAS.get(current_persona, PERSONAS["default"])
                    
                    # 3. Format the payload for Groq Vision
                    messages = [
                        {"role": "system", "content": current_system_prompt},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime_type};base64,{base64_image}"
                                    }
                                }
                            ]
                        }
                    ]
                    
                    # 4. Ping Groq's high-speed vision model
                    chat_completion = await groq_client.chat.completions.create(
                        messages=messages,
                        model="qwen/qwen3.8-27b",
                    )
                    
                    response_text = chat_completion.choices[0].message.content
                    await message.reply(response_text)
                    
                    if message.guild and message.guild.voice_client:
                        await speak_text(message.guild, response_text)
                        
                except Exception as e:
                    await message.reply(f"❌ **Vision Error:** Failed to process visual data via Groq mainframe. Log: {e}")
            return

    # Dual-Brain Chat 
    if is_mentioned:
        async with message.channel.typing():
            clean_prompt = message.content.replace(f'<@{bot.user.id}>', '').replace('larvis', '').replace('Larvis', '').strip()
            if not clean_prompt:
                clean_prompt = "Hello!"
                
            current_system_prompt = PERSONAS.get(current_persona, PERSONAS["default"])
            
            try:
                if current_brain == "groq":
                    history = await get_memory(str(message.author.id), "groq")
                    messages = [{"role": "system", "content": current_system_prompt}]
                    messages.extend(history)
                    messages.append({"role": "user", "content": clean_prompt})
                    
                    chat_completion = await groq_client.chat.completions.create(
                        messages=messages,
                        model=groq_model_name,
                    )
                    response_text = chat_completion.choices[0].message.content
                    
                else:  
                    history = await get_memory(str(message.author.id), "gemini")
                    history.append(types.Content(role="user", parts=[types.Part.from_text(text=clean_prompt)]))
                    
                    response = await gemini_client.aio.models.generate_content(
                        model="gemini-3.6-flash",
                        contents=history,
                        config=types.GenerateContentConfig(
                            system_instruction=current_system_prompt
                        )
                    )
                    response_text = response.text

                await save_memory(str(message.author.id), "user", clean_prompt)
                await save_memory(str(message.author.id), "bot", response_text)
                
                await message.channel.send(response_text[:2000])
                
                if message.guild and message.guild.voice_client:
                    await speak_text(message.guild, response_text)
                
            except Exception as e:
                await message.channel.send(f"Systems offline. The {current_brain.upper()} mainframe is currently unresponsive.")

bot.run(os.getenv("DISCORD_TOKEN"))
