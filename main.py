import os
import json
import difflib
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Load from .env
monitor_channel_names = [name.strip() for name in os.getenv("MONITOR_CHANNEL_NAMES", "").split(",")]
status_channel_name = os.getenv("STATUS_CHANNEL_NAME", "").strip()
STATUS_MESSAGE_FILE = "status_message.json"

# Globals
monitor_channels = []
status_channel = None
status_message_id = None
last_summary = None

# Utility to save/load status message ID
def load_status_message_id():
    if os.path.exists(STATUS_MESSAGE_FILE):
        with open(STATUS_MESSAGE_FILE, "r") as f:
            return json.load(f).get("status_message_id")
    return None

def save_status_message_id(msg_id):
    with open(STATUS_MESSAGE_FILE, "w") as f:
        json.dump({"status_message_id": msg_id}, f)

# Fuzzy matching to find a channel by name
def find_channel_by_fuzzy_name(guild, fuzzy_name, cutoff=0.6):
    channel_names = {channel.name: channel for channel in guild.text_channels}
    matches = difflib.get_close_matches(fuzzy_name.lower(), [name.lower() for name in channel_names], n=1, cutoff=cutoff)
    if matches:
        matched_name = next(name for name in channel_names if name.lower() == matches[0])
        return channel_names[matched_name]
    return None

# Update status message now
async def update_status_message_now():
    global status_message_id, last_summary

    if not status_channel:
        print("⚠️ No status channel. Skipping update.")
        return

    lines = []

    for channel in monitor_channels:
        messages = [
            msg async for msg in channel.history(limit=20)
            if not msg.author.bot
        ]
        status = "❌ Active Razz" if messages else "🤑 Free to use"
        lines.append(f"<#{channel.id}> : {status}")

    summary = "**📊 Razz Status:**\n\n" + "\n".join(lines)

    if summary == last_summary:
        print("⏭ No change detected.")
        return

    try:
        if status_message_id:
            msg = await status_channel.fetch_message(status_message_id)
            await msg.edit(content=summary)
            print("✅ Status message updated.")
        else:
            raise discord.NotFound
    except (discord.NotFound, discord.Forbidden):
        print("📨 Status message not found. Sending new one.")
        msg = await status_channel.send(summary)
        status_message_id = msg.id
        save_status_message_id(status_message_id)

    last_summary = summary

# Bot ready event
@bot.event
async def on_ready():
    global monitor_channels, status_channel, status_message_id

    print(f"✅ Logged in as {bot.user}")
    guild = bot.guilds[0]  # assumes one server

    monitor_channels = []
    for name in monitor_channel_names:
        ch = find_channel_by_fuzzy_name(guild, name)
        if ch:
            monitor_channels.append(ch)
            print(f"✔️ Matched: {name} → {ch.name}")
        else:
            print(f"❌ No match for: {name}")

    status_channel = find_channel_by_fuzzy_name(guild, status_channel_name)
    if not status_channel:
        print(f"❌ Could not match status channel: {status_channel_name}")
        return

    status_message_id = load_status_message_id()
    await update_status_message_now()

# React to message changes
@bot.event
async def on_message(message):
    if message.channel in monitor_channels and not message.author.bot:
        await update_status_message_now()
    await bot.process_commands(message)

@bot.event
async def on_message_delete(message):
    if message.channel in monitor_channels and not message.author.bot:
        await update_status_message_now()

@bot.event
async def on_message_edit(before, after):
    if after.channel in monitor_channels and not after.author.bot:
        await update_status_message_now()

# Start bot
bot.run(os.getenv("DISCORD_TOKEN"))
