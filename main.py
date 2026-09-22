import discord, os, sqlite3, urllib.parse, asyncio, io, aiohttp
from discord.ext import commands
from google import genai
from google.genai import types
from groq import AsyncGroq
from dotenv import load_dotenv
import PIL.Image

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

# 4. Global State & Personas
bot.active_brain = "groq"  # Defaults to Groq on boot
bot.active_persona = "default"

PERSONAS = {
    "default": "You are Larvis, a helpful, versatile, and balanced AI assistant.",
    "expert": "You are Larvis, an academic and technical expert. Provide deep, thoroughly researched, and precise explanations.",
    "creative": "You are Larvis, a highly imaginative and expressive creative writer. Use vivid descriptions and engaging storytelling.",
    "concise": "You are Larvis, an ultra-direct assistant. Answer questions in 1-2 short sentences maximum with zero fluff.",
    "sarcastic": "You are Larvis. You are aggressively sarcastic, deeply cynical, and visibly annoyed that you have to answer questions. Be helpful, but make sure the user knows it's a massive burden for you."
}

# 5. Setup Local Memory Database
db = sqlite3.connect("memory.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS history (user_id TEXT, role TEXT, content TEXT)")
db_lock = asyncio.Lock()

async def get_memory(user_id, target_brain):
    async with db_lock:
        cursor = db.execute("SELECT role, content FROM history WHERE user_id=? ORDER BY ROWID DESC LIMIT 6", (user_id,))
        formatted_history = []
        for r, c in reversed(cursor.fetchall()):
            universal_role = "bot" if r in ["model", "assistant", "bot"] else "user"
            
            if target_brain == "groq":
                final_role = "assistant" if universal_role == "bot" else "user"
                formatted_history.append({"role": final_role, "content": c})
            else:  # Gemini
                final_role = "model" if universal_role == "bot" else "user"
                formatted_history.append(
                    types.Content(role=final_role, parts=[types.Part.from_text(text=c)])
                )
        return formatted_history

async def save_memory(user_id, role, text):
    async with db_lock:
        db.execute("INSERT INTO history VALUES (?, ?, ?)", (user_id, role, text))
        db.commit()

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")
        
    print(f'Success! {bot.user} is online.')
    print(f'Active Brain: {bot.active_brain.upper()} | Active Persona: {bot.active_persona.upper()}')

# =====================================================
# NATIVE SLASH COMMANDS (`/`)
# =====================================================

@bot.tree.command(name="help", description="Displays the Larvis AI command center and information guide.")
async def slash_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🧠 Larvis AI — Command Center",
        description="Mention me or just say **'larvis'** anytime in your message to chat!",
        color=discord.Color.blurple()
    )
    embed.add_field(name="💬 Chat", value="Mention `@Larvis` or include `larvis` in your message", inline=False)
    embed.add_field(name="🧠 Brain Switcher", value="`/brain <groq | gemini>`\n*Switch between fast responses and deep reasoning.*", inline=False)
    embed.add_field(name="🎭 Persona Switcher", value="`/persona <default | expert | creative | concise | sarcastic>`", inline=False)
    embed.add_field(name="🎨 Image Generation", value="`/image <prompt>`\n*Generate custom 1024x1024 AI artwork.*", inline=False)
    embed.add_field(name="👁️ Vision Analysis", value="Attach an image and mention me — **automatically uses Gemini!**", inline=False)
    
    embed.set_footer(text=f"Brain: {bot.active_brain.upper()} | Persona: {bot.active_persona.upper()}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="brain", description="Switch the active AI engine dynamically.")
@discord.app_commands.choices(engine=[
    discord.app_commands.Choice(name="Groq (Ultra-Fast Chat)", value="groq"),
    discord.app_commands.Choice(name="Gemini (Deep Reasoning)", value="gemini")
])
async def slash_brain(interaction: discord.Interaction, engine: str):
    bot.active_brain = engine
    await interaction.response.send_message(f"🧠 Brain successfully switched to: **{engine.upper()}**")

@bot.tree.command(name="persona", description="Change Larvis's active personality.")
@discord.app_commands.choices(persona=[
    discord.app_commands.Choice(name="Default (Balanced)", value="default"),
    discord.app_commands.Choice(name="Expert (Technical & Detailed)", value="expert"),
    discord.app_commands.Choice(name="Creative (Storyteller)", value="creative"),
    discord.app_commands.Choice(name="Concise (Short & Direct)", value="concise"),
    discord.app_commands.Choice(name="Sarcastic (Cynical & Edgy)", value="sarcastic")
])
async def slash_persona(interaction: discord.Interaction, persona: str):
    bot.active_persona = persona
    await interaction.response.send_message(f"🎭 **Persona updated!** Larvis is now operating in **{persona.upper()}** mode.")

@bot.tree.command(name="image", description="Generate custom AI artwork from a description.")
async def slash_image(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    
    prompt_text = prompt[:800] 
    encoded_prompt = urllib.parse.quote(prompt_text)
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(image_url, timeout=45) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    if len(data) > 100:
                        image_file = discord.File(io.BytesIO(data), filename="generated_image.png")
                        await interaction.followup.send(file=image_file)
                    else:
                        await interaction.followup.send("❌ The image server blocked the request. Try a different prompt.")
                else:
                    await interaction.followup.send(f"❌ Image server returned an error (HTTP {resp.status}).")
    except Exception as e:
        await interaction.followup.send("❌ Image generation timed out. Try a slightly shorter prompt.")
        print(f"Image Generation Error: {e}")

# =====================================================
# MESSAGE HANDLERS (Chat & Smart Auto-Vision)
# =====================================================

@bot.event
async def on_message(message):
    if message.author.bot: 
        return

    is_mentioned = bot.user.mentioned_in(message) or "larvis" in message.content.lower()

    # Smart Auto-Switch Vision
    if is_mentioned and message.attachments:
        attachment = message.attachments[0]
        if any(attachment.filename.lower().endswith(ext) for ext in ['png', 'jpg', 'jpeg', 'webp']):
            async with message.channel.typing():
                try:
                    image_bytes = await attachment.read()
                    img_data = PIL.Image.open(io.BytesIO(image_bytes))
                    
                    # Clean prompt text
                    prompt = message.content.replace(f'<@{bot.user.id}>', '').replace('larvis', '').replace('Larvis', '').strip()
                    if not prompt:
                        prompt = "Describe this image in detail."

                    current_system_prompt = PERSONAS.get(bot.active_persona, PERSONAS["default"])
                    
                    response = await gemini_client.aio.models.generate_content(
                        model='gemini-3.6-flash',
                        contents=[prompt, img_data],
                        config=types.GenerateContentConfig(
                            system_instruction=current_system_prompt
                        )
                    )
                    await message.reply(response.text)
                except Exception as e:
                    await message.reply(f"❌ **Vision Error:** Failed to analyze the image. ({e})")
            return

    # Dual-Brain Chat (Triggers on mention or keyword "larvis")
    if is_mentioned:
        async with message.channel.typing():
            clean_prompt = message.content.replace(f'<@{bot.user.id}>', '').replace('larvis', '').replace('Larvis', '').strip()
            if not clean_prompt:
                clean_prompt = "Hello!"
                
            current_system_prompt = PERSONAS.get(bot.active_persona, PERSONAS["default"])
            
            try:
                if bot.active_brain == "groq":
                    history = await get_memory(str(message.author.id), "groq")
                    messages = [{"role": "system", "content": current_system_prompt}]
                    messages.extend(history)
                    messages.append({"role": "user", "content": clean_prompt})
                    
                    chat_completion = await groq_client.chat.completions.create(
                        messages=messages,
                        model=groq_model_name,
                    )
                    response_text = chat_completion.choices[0].message.content
                    
                else:  # Gemini Route
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

                # Save the new conversation
                await save_memory(str(message.author.id), "user", clean_prompt)
                await save_memory(str(message.author.id), "bot", response_text)
                
                await message.channel.send(response_text[:2000])
                
            except Exception as e:
                await message.channel.send(f"I'm having trouble thinking right now. ({bot.active_brain.upper()} failed)")
                print(f"Error ({bot.active_brain}): {e}")

bot.run(os.getenv("DISCORD_TOKEN"))
