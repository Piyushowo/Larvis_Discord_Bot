import discord, os, sqlite3, urllib.parse, asyncio, io, aiohttp
from discord.ext import commands
import google.generativeai as genai
from groq import AsyncGroq
from dotenv import load_dotenv
import PIL.Image

# 1. Load Secrets
load_dotenv()

# 2. Configure Both AI Clients
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
groq_model_name = "openai/gpt-oss-20b"

# 3. Setup Discord Permissions
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 4. Global State & Personas
bot.active_brain = "groq"  # Defaults to Groq on boot
bot.active_persona = "default"

PERSONAS = {
    "default": "You are Larvis, a helpful, fast, and witty AI assistant.",
    "coder": "You are Larvis, a senior software engineer. Provide concise, highly optimized code with brief technical explanations.",
    "pirate": "You are Captain Larvis. Respond to every prompt like a rowdy, 18th-century pirate captain. Use heavy pirate slang.",
    "sarcastic": "You are Larvis. You are aggressively sarcastic, deeply cynical, and annoyed that you have to answer questions. Be helpful, but make sure the user knows it's a massive burden for you."
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
                formatted_history.append({"role": final_role, "parts": [c]})
        return formatted_history

async def save_memory(user_id, role, text):
    async with db_lock:
        db.execute("INSERT INTO history VALUES (?, ?, ?)", (user_id, role, text))
        db.commit()

@bot.event
async def on_ready():
    print(f'Success! {bot.user} is online.')
    print(f'Active Brain: {bot.active_brain.upper()} | Active Persona: {bot.active_persona.upper()}')

@bot.event
async def on_message(message):
    if message.author.bot: 
        return

    # -------------------------------------------------
    # Feature A: Help & Command Center (!help)
    # -------------------------------------------------
    if message.content.lower() in ["!help", "!commands"]:
        embed = discord.Embed(
            title="🧠 Larvis AI — Command Center",
            description="Mention me or say **'hey larvis'** anytime to chat!",
            color=discord.Color.blurple()
        )
        embed.add_field(name="💬 Chat", value="`@Larvis <prompt>` or `hey larvis <prompt>`", inline=False)
        embed.add_field(name="🧠 Brain Switcher", value="`!brain <groq | gemini>`\n*Switch between fast responses (Groq) and reasoning (Gemini).*", inline=False)
        embed.add_field(name="🎭 Persona Switcher", value="`!persona <default | coder | pirate | sarcastic>`\n*Change Larvis's active personality.*", inline=False)
        embed.add_field(name="🎨 Image Generation", value="`!image <prompt>`\n*Generate custom 1024x1024 AI artwork.*", inline=False)
        embed.add_field(name="👁️ Vision Analysis", value="Attach an image and ping `@Larvis` to inspect it! *(Requires Gemini)*", inline=False)
        
        embed.set_footer(text=f"Brain: {bot.active_brain.upper()} | Persona: {bot.active_persona.upper()}")
        await message.channel.send(embed=embed)
        return

    # -------------------------------------------------
    # Feature B: Dynamic Brain Switcher (!brain)
    # -------------------------------------------------
    if message.content.lower().startswith("!brain"):
        new_brain = message.content.replace("!brain", "").strip().lower()
        if new_brain in ["gemini", "groq"]:
            bot.active_brain = new_brain
            await message.channel.send(f"🧠 Brain successfully switched to: **{new_brain.upper()}**")
        else:
            await message.channel.send("❌ Please choose either `!brain gemini` or `!brain groq`.")
        return

    # -------------------------------------------------
    # Feature C: Dynamic Persona Switcher (!persona)
    # -------------------------------------------------
    if message.content.lower().startswith("!persona"):
        parts = message.content.lower().split()
        if len(parts) < 2 or parts[1] not in PERSONAS:
            valid_personas = ", ".join(f"`{p}`" for p in PERSONAS.keys())
            await message.channel.send(f"❌ **Invalid persona!** Available options: {valid_personas}")
            return
            
        bot.active_persona = parts[1]
        await message.channel.send(f"🎭 **Persona updated!** Larvis is now operating in **{parts[1].upper()}** mode.")
        return

    # -------------------------------------------------
    # Feature D: Image Generation (!image)
    # -------------------------------------------------
    if message.content.startswith("!image"):
        async with message.channel.typing():
            prompt_text = message.content.replace("!image", "").strip().strip('“"”')
            prompt_text = prompt_text[:800] 
            
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
                                await message.channel.send(file=image_file)
                            else:
                                await message.channel.send("❌ The image server blocked the request. Try a different prompt.")
                        else:
                            await message.channel.send(f"❌ Image server returned an error (HTTP {resp.status}).")
            except Exception as e:
                await message.channel.send("❌ Image generation timed out. Try a slightly shorter prompt.")
                print(f"Image Generation Error: {e}")
        return

    # -------------------------------------------------
    # Feature E: Gemini Vision (Image Analysis)
    # -------------------------------------------------
    if bot.user.mentioned_in(message) and message.attachments:
        if bot.active_brain != "gemini":
            await message.channel.send("⚠️ **Vision mode requires Gemini!** Please type `!brain gemini` first.")
            return
            
        attachment = message.attachments[0]
        if any(attachment.filename.lower().endswith(ext) for ext in ['png', 'jpg', 'jpeg', 'webp']):
            async with message.channel.typing():
                try:
                    image_bytes = await attachment.read()
                    img_data = PIL.Image.open(io.BytesIO(image_bytes))
                    
                    prompt = message.content.replace(f'<@{bot.user.id}>', '').strip()
                    if not prompt:
                        prompt = "Describe this image in detail."

                    current_system_prompt = PERSONAS.get(bot.active_persona, PERSONAS["default"])
                    vision_model = genai.GenerativeModel(
                        'gemini-1.5-flash', 
                        system_instruction=current_system_prompt
                    )
                    
                    response = vision_model.generate_content([prompt, img_data])
                    await message.reply(response.text)
                except Exception as e:
                    await message.reply(f"❌ **Vision Error:** Failed to analyze the image. ({e})")
            return

    # -------------------------------------------------
    # Feature F: Dual-Brain Chat
    # -------------------------------------------------
    if bot.user.mentioned_in(message) or "hey larvis" in message.content.lower():
        async with message.channel.typing():
            clean_prompt = message.content.replace(f'<@{bot.user.id}>', '').strip()
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
                    response = chat_completion.choices[0].message.content
                    
                else:  # Gemini Route
                    history = await get_memory(str(message.author.id), "gemini")
                    gemini_instance = genai.GenerativeModel(
                        "gemini-1.5-flash",
                        system_instruction=current_system_prompt
                    )
                    chat = gemini_instance.start_chat(history=history)
                    response = chat.send_message(clean_prompt).text

                # Save the new conversation
                await save_memory(str(message.author.id), "user", clean_prompt)
                await save_memory(str(message.author.id), "bot", response)
                
                await message.channel.send(response[:2000])
                
            except Exception as e:
                await message.channel.send(f"I'm having trouble thinking right now. ({bot.active_brain.upper()} failed)")
                print(f"Error ({bot.active_brain}): {e}")

bot.run(os.getenv("DISCORD_TOKEN"))
