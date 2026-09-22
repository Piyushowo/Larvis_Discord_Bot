import discord, os, sqlite3, urllib.parse, asyncio
from discord.ext import commands
import google.generativeai as genai
from groq import AsyncGroq
from dotenv import load_dotenv
import io
import aiohttp

# 1. Load Secrets
load_dotenv()

# 2. Configure Both AI Clients
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
# Fallback to gemini-1.5-flash if 3.5 gives you access errors later
gemini_model = genai.GenerativeModel("gemini-3.5-flash") 

groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
groq_model_name = "openai/gpt-oss-20b"

# 3. Setup Discord Permissions
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 4. Global State: Track which brain is currently active
bot.active_brain = "groq" # Defaults to Groq on boot

# 5. Setup Local Memory Database
db = sqlite3.connect("memory.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS history (user_id TEXT, role TEXT, content TEXT)")
db_lock = asyncio.Lock()

async def get_memory(user_id, target_brain):
    async with db_lock:
        cursor = db.execute("SELECT role, content FROM history WHERE user_id=? ORDER BY ROWID DESC LIMIT 6", (user_id,))
        formatted_history = []
        for r, c in reversed(cursor.fetchall()):
            # Catch old legacy roles ("model" or "assistant") and standardize them
            universal_role = "bot" if r in ["model", "assistant", "bot"] else "user"
            
            # Format the memory specifically for the brain currently being used
            if target_brain == "groq":
                final_role = "assistant" if universal_role == "bot" else "user"
                formatted_history.append({"role": final_role, "content": c})
            else: # Gemini
                final_role = "model" if universal_role == "bot" else "user"
                formatted_history.append({"role": final_role, "parts": [c]})
        return formatted_history

async def save_memory(user_id, role, text):
    async with db_lock:
        # We now universally save bot responses as "bot" to prevent database conflicts
        db.execute("INSERT INTO history VALUES (?, ?, ?)", (user_id, role, text))
        db.commit()

@bot.event
async def on_ready():
    print(f'Success! {bot.user} is online. Default brain is {bot.active_brain.upper()}.')

@bot.event
async def on_message(message):
    if message.author.bot: return
    
    # Feature A: Dynamic Brain Switcher
    if message.content.lower().startswith("!brain"):
        new_brain = message.content.replace("!brain ", "").strip().lower()
        if new_brain in ["gemini", "groq"]:
            bot.active_brain = new_brain # Changes the active attribute
            await message.channel.send(f"🧠 Brain successfully switched to: **{new_brain.upper()}**")
        else:
            await message.channel.send("❌ Please choose either `!brain gemini` or `!brain groq`.")
        return

    # Feature B: Image Generation
    # Feature B: Image Generation
    if message.content.startswith("!image"):
        async with message.channel.typing():
            # Clean quotes and cap the prompt length to prevent "URL Too Long" crashes
            prompt_text = message.content.replace("!image", "").strip().strip('“"”')
            prompt_text = prompt_text[:800] 
            
            encoded_prompt = urllib.parse.quote(prompt_text)
            image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
            
            try:
                # Disguise the Python script as a Google Chrome browser to bypass Cloudflare
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                
                async with aiohttp.ClientSession(headers=headers) as session:
                    # Extended timeout for highly detailed prompts
                    async with session.get(image_url, timeout=45) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            
                            # Safety check: Ensure the file actually contains image data (not 0 bytes)
                            if len(data) > 100:
                                image_file = discord.File(io.BytesIO(data), filename="generated_image.png")
                                await message.channel.send(file=image_file)
                            else:
                                await message.channel.send("❌ The image server blocked the request. Try a different prompt.")
                        else:
                            await message.channel.send(f"❌ Image server returned an error (HTTP {resp.status}).")
            except Exception as e:
                await message.channel.send("❌ Image generation timed out. Try a slightly shorter prompt.")
                print(f"Image Generation Error: {e}")
        return

    # Feature C: Dual-Brain Chat
    if bot.user.mentioned_in(message) or "hey larvis" in message.content.lower():
        async with message.channel.typing():
            clean_prompt = message.content.replace(f'<@{bot.user.id}>', '').strip()
            
            try:
                # Route the processing to the currently selected brain
                if bot.active_brain == "groq":
                    history = await get_memory(str(message.author.id), "groq")
                    messages = [{"role": "system", "content": "You are Larvis, a witty and helpful bot."}]
                    messages.extend(history)
                    messages.append({"role": "user", "content": clean_prompt})
                    
                    chat_completion = await groq_client.chat.completions.create(
                        messages=messages,
                        model=groq_model_name,
                    )
                    response = chat_completion.choices[0].message.content
                    
                else: # Gemini Route
                    history = await get_memory(str(message.author.id), "gemini")
                    chat = gemini_model.start_chat(history=history)
                    response = chat.send_message(clean_prompt).text

                # Save the new conversation
                await save_memory(str(message.author.id), "user", clean_prompt)
                await save_memory(str(message.author.id), "bot", response)
                
                await message.channel.send(response[:2000])
                
            except Exception as e:
                await message.channel.send(f"I'm having trouble thinking right now. ({bot.active_brain.upper()} failed)")
                print(f"Error ({bot.active_brain}): {e}")

bot.run(os.getenv("DISCORD_TOKEN"))