import discord
from discord import app_commands
from discord.ext import commands
import requests
from datetime import datetime
import os
from flask import Flask
from threading import Thread

# =========================
# ВЕБ-СЕРВЕР (БУДИЛЬНИК)
# =========================
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web_server():
    # Render выдает порт через переменную среды, по умолчанию 10000
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web_server)
    t.daemon = True
    t.start()

# =========================
# SETTINGS (Берем из Render Environment Variables)
# =========================
DISCORD_TOKEN = os.environ.get("Bottoken")
ROBLOX_API_KEY = os.environ.get("Apitoken")
GROUP_ID = 841435331
ALLOWED_ROLE_ID = 1479884336051388604
LOG_CHANNEL_ID = 1481718190961590392

ROLE_IDS = {
    "Guest": 601712008,
    "『SR』Seaman Recruit": 627311089,
    "『SA』Seaman Apprentice": 626371120,
    "『SM』Seaman": 625449142,
    "『SS』Senior Seaman": 626739123,
    "『PO』Petty Officer": 625591116,
    "『CPO』Chief Petty Officer": 625249228,
    "『SC』Senior Chief": 626151118,
    "『MC』Master Chief": 621855265,
    "『DEV』Developer": 601712009,
    "『OOT』Officer On Trial": 625687178,
    "『ENS』Ensign": 626819052,
    "『LT』Lieutenant": 626001157,
    "『COM』Commodore": 625657188,
    "『CAPT』Captain": 625233175,
    "『FCDR』Fleet Commande": 601712006,
    "Admiral": 601712007
}

VALID_ROLES = [
    "『SR』Seaman Recruit", "『SA』Seaman Apprentice", "『SM』Seaman", 
    "『SS』Senior Seaman", "『PO』Petty Officer", "『CPO』Chief Petty Officer",
    "『SC』Senior Chief", "『MC』Master Chief", "『DEV』Developer",
    "『OOT』Officer On Trial", "『ENS』Ensign", "『LT』Lieutenant",
    "『COM』Commodore", "『CAPT』Captain", "『FCDR』Fleet Commande"
]

# =========================
# BOT SETUP
# =========================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
headers = {"x-api-key": ROBLOX_API_KEY, "Content-Type": "application/json"}

# Вспомогательные функции (has_permission, get_user_id и т.д. остаются без изменений)
def has_permission(interaction: discord.Interaction):
    return any(role.id == ALLOWED_ROLE_ID for role in interaction.user.roles)

async def send_log(action_type, moderator, target_user, old_rank, new_rank):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if not channel: return
    embed = discord.Embed(title="Rank Update Log", color=discord.Color.blue(), timestamp=datetime.now())
    embed.add_field(name="Action", value=action_type, inline=True)
    embed.add_field(name="Moderator", value=moderator.mention, inline=True)
    embed.add_field(name="Target User", value=target_user, inline=False)
    embed.add_field(name="Old Rank", value=old_rank, inline=True)
    embed.add_field(name="New Rank", value=new_rank, inline=True)
    await channel.send(embed=embed)

def get_user_id(username):
    url = "https://users.roblox.com/v1/usernames/users"
    data = {"usernames": [username], "excludeBannedUsers": True}
    r = requests.post(url, json=data)
    if r.status_code != 200: return None, "Error fetching UserID"
    result = r.json().get("data", [])
    return (result[0]["id"], None) if result else (None, "User not found")

def get_user_current_role(user_id):
    url = f"https://groups.roblox.com/v2/users/{user_id}/groups/roles"
    r = requests.get(url)
    if r.status_code != 200: return "Guest", 0
    data = r.json().get("data", [])
    for g in data:
        if g["group"]["id"] == GROUP_ID:
            return g["role"]["name"], g["role"]["rank"]
    return "Guest", 0

def promote_user(user_id, role_name):
    role_id = ROLE_IDS.get(role_name)
    url = f"https://apis.roblox.com/cloud/v2/groups/{GROUP_ID}/memberships/{user_id}"
    r = requests.patch(url, headers=headers, json={"role": f"groups/{GROUP_ID}/roles/{role_id}"})
    return r.status_code == 200, r.text

# Команды (/promote, /demote, /setrank) остаются такими же...
@tree.command(name="promote", description="Promote a member")
async def promote_command(interaction: discord.Interaction, username: str):
    if not has_permission(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    await interaction.response.defer()
    user_id, err = get_user_id(username.strip())
    if err:
        await interaction.followup.send(err)
        return
    current_role, _ = get_user_current_role(user_id)
    next_role = None
    if current_role == "Guest": next_role = VALID_ROLES[0]
    elif current_role in VALID_ROLES:
        idx = VALID_ROLES.index(current_role)
        if idx + 1 < len(VALID_ROLES): next_role = VALID_ROLES[idx + 1]
    if not next_role:
        await interaction.followup.send("Max rank reached.")
        return
    success, _ = promote_user(user_id, next_role)
    if success:
        await interaction.followup.send(f"Promoted {username} to {next_role}")
        await send_log("Promotion", interaction.user, username, current_role, next_role)

@tree.command(name="demote", description="Demote a member")
async def demote_command(interaction: discord.Interaction, username: str):
    if not has_permission(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    await interaction.response.defer()
    user_id, err = get_user_id(username.strip())
    if err:
        await interaction.followup.send(err)
        return
    current_role, _ = get_user_current_role(user_id)
    prev_role = None
    if current_role in VALID_ROLES:
        idx = VALID_ROLES.index(current_role)
        prev_role = VALID_ROLES[idx - 1] if idx > 0 else "Guest"
    if not prev_role:
        await interaction.followup.send("Cannot demote further.")
        return
    success, _ = promote_user(user_id, prev_role)
    if success:
        await interaction.followup.send(f"Demoted {username} to {prev_role}")
        await send_log("Demotion", interaction.user, username, current_role, prev_role)

@tree.command(name="setrank", description="Set a specific rank")
@app_commands.choices(rank=[app_commands.Choice(name=r, value=r) for r in VALID_ROLES])
async def setrank_command(interaction: discord.Interaction, username: str, rank: app_commands.Choice[str]):
    if not has_permission(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    await interaction.response.defer()
    user_id, err = get_user_id(username.strip())
    if err:
        await interaction.followup.send(err)
        return
    current_role, _ = get_user_current_role(user_id)
    success, _ = promote_user(user_id, rank.value)
    if success:
        await interaction.followup.send(f"Set {username} to {rank.value}")
        await send_log("SetRank", interaction.user, username, current_role, rank.value)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {bot.user}")

# =========================
# ЗАПУСК
# =========================
if __name__ == "__main__":
    if DISCORD_TOKEN:
        keep_alive() # Запуск Flask
        bot.run(DISCORD_TOKEN)
    else:
        print("Error: DISCORD_TOKEN not found in environment variables!")
