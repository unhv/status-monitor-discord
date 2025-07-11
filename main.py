from dotenv import load_dotenv
import discord
from discord.ext import commands, tasks
import os
import json
from keep_alive import keep_alive

load_dotenv()
keep_alive()

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

channel_ids_to_monitor = [
    int(cid.strip()) for cid in os.getenv("MONITOR_CHANNEL_IDS").split(",")
]
status_channel_id = int(os.getenv("STATUS_CHANNEL_ID"))

STATUS_MESSAGE_FILE = "status_message.json"


def load_status_message_id():
    if os.path.exists(STATUS_MESSAGE_FILE):
        with open(STATUS_MESSAGE_FILE, "r") as f:
            return json.load(f).get("status_message_id")
    return None


def save_status_message_id(msg_id):
    with open(STATUS_MESSAGE_FILE, "w") as f:
        json.dump({"status_message_id": msg_id}, f)


status_message_id = load_status_message_id()

last_summary = None  # Keep track of last message content

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    update_status_message.start()


@tasks.loop(seconds=60)
async def update_status_message():
    global status_message_id
    status_channel = bot.get_channel(status_channel_id)
    
    
    if status_channel is None:
        print(
            f"❌ ERROR: Could not find status channel with ID {status_channel_id}"
        )
        return

    lines = []

    for channel_id in channel_ids_to_monitor:
        channel = bot.get_channel(channel_id)
        if not channel:
            lines.append(f"<#{channel_id}>: ❓ Unknown channel")
            continue

        messages = [
            msg async for msg in channel.history(limit=20)
            if not msg.author.bot
        ]

        status = "✅ Occupied" if messages else "⚠️ Empty"
        lines.append(f"<#{channel.id}>: {status}")

    summary = "**Channel Monitoring Status:**\n\n" + "\n".join(lines)

    global last_summary
    if summary == last_summary:
        print("No change detected. Skipping message update.")
        return

    try:
        if status_message_id:
            msg = await status_channel.fetch_message(status_message_id)
            await msg.edit(content=summary)
        else:
            raise discord.NotFound  # force it to send a new one
    except (discord.NotFound, discord.Forbidden):
        print("⚠️ Status message not found or deleted. Sending new one.")
        msg = await status_channel.send(summary)
        last_summary = summary
        status_message_id = msg.id
        save_status_message_id(status_message_id)
