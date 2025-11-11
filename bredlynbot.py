import discord
from discord.ext import commands
import requests
from datetime import datetime
from typing import Optional, Dict
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class OsuAPI:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://osu.ppy.sh/api/v2"
        self.token_url = "https://osu.ppy.sh/oauth/token"
        self.access_token = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with the osu! API."""
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials',
            'scope': 'public'
        }
        
        try:
            response = requests.post(self.token_url, data=data)
            response.raise_for_status()
            self.access_token = response.json()['access_token']
            print("✓ Authenticated with osu! API")
        except Exception as e:
            print(f"✗ osu! API authentication failed: {e}")
            raise
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make an authenticated request to the osu! API."""
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        try:
            response = requests.get(f"{self.base_url}/{endpoint}", 
                                   headers=headers, 
                                   params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"✗ API request failed: {e}")
            return None
    
    def get_user(self, username: str, mode: str = "osu") -> Optional[Dict]:
        """Get user profile information."""
        return self._make_request(f"users/{username}/{mode}")
    
    def get_recent_scores(self, user_id: int, mode: str = "osu", limit: int = 5) -> list:
        """Get recent scores for a user."""
        params = {
            'include_fails': '1',
            'mode': mode,
            'limit': limit
        }
        return self._make_request(f"users/{user_id}/scores/recent", params) or []
    
    def get_user_best(self, user_id: int, mode: str = "osu", limit: int = 5) -> list:
        """Get best scores for a user."""
        params = {
            'mode': mode,
            'limit': limit
        }
        return self._make_request(f"users/{user_id}/scores/best", params) or []


# Initialize bot with command prefix
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Initialize osu! API
osu_api = None

@bot.event
async def on_ready():
    print(f'✓ Bot is ready! Logged in as {bot.user.name}')
    print(f'Bot ID: {bot.user.id}')
    print('------')

@bot.command(name='profile', aliases=['osu', 'p'])
async def profile(ctx, username: str, mode: str = "osu"):
    """
    Get osu! user profile.
    Usage: !profile <username> [mode]
    Modes: osu, taiko, fruits, mania
    """
    await ctx.send(f"🔍 Fetching profile for **{username}**...")
    
    user = osu_api.get_user(username, mode)
    
    if not user:
        await ctx.send(f"❌ Could not find user **{username}** in mode **{mode}**")
        return
    
    # Create embed
    embed = discord.Embed(
        title=f"{user['username']}'s Profile",
        url=f"https://osu.ppy.sh/users/{user['id']}",
        color=discord.Color.pink()
    )
    
    # Set thumbnail to user avatar
    embed.set_thumbnail(url=user['avatar_url'])
    
    # Add fields
    stats = user['statistics']
    embed.add_field(name="🌍 Country", value=f"{user['country']['name']} :flag_{user['country']['code'].lower()}:", inline=True)
    embed.add_field(name="🏆 Global Rank", value=f"#{stats['global_rank']:,}" if stats['global_rank'] else "N/A", inline=True)
    embed.add_field(name="📍 Country Rank", value=f"#{stats['country_rank']:,}" if stats['country_rank'] else "N/A", inline=True)
    
    embed.add_field(name="⭐ PP", value=f"{stats['pp']:,.0f}", inline=True)
    embed.add_field(name="🎯 Accuracy", value=f"{stats['hit_accuracy']:.2f}%", inline=True)
    embed.add_field(name="📊 Level", value=f"{stats['level']['current']}", inline=True)
    
    embed.add_field(name="🎮 Play Count", value=f"{stats['play_count']:,}", inline=True)
    embed.add_field(name="⏱️ Play Time", value=f"{stats['play_time'] // 3600:,}h", inline=True)
    embed.add_field(name="🎖️ SS/S Ranks", value=f"{stats['grade_counts']['ss'] + stats['grade_counts']['ssh']}/{stats['grade_counts']['s'] + stats['grade_counts']['sh']}", inline=True)
    
    embed.set_footer(text=f"Mode: {mode} | Requested by {ctx.author.name}")
    
    await ctx.send(embed=embed)

@bot.command(name='recent', aliases=['rs', 'r'])
async def recent(ctx, username: str, mode: str = "osu", limit: int = 1):
    """
    Get recent osu! scores.
    Usage: !recent <username> [mode] [limit]
    """
    if limit > 5:
        limit = 5
    
    await ctx.send(f"🔍 Fetching recent scores for **{username}**...")
    
    user = osu_api.get_user(username, mode)
    if not user:
        await ctx.send(f"❌ Could not find user **{username}**")
        return
    
    scores = osu_api.get_recent_scores(user['id'], mode, limit)
    
    if not scores:
        await ctx.send(f"❌ No recent scores found for **{username}**")
        return
    
    for score in scores:
        beatmap = score['beatmap']
        beatmapset = score['beatmapset']
        stats = score['statistics']
        
        # Create embed
        embed = discord.Embed(
            title=f"{beatmapset['artist']} - {beatmapset['title']}",
            url=f"https://osu.ppy.sh/b/{beatmap['id']}",
            description=f"[{beatmap['version']}]",
            color=discord.Color.blue()
        )
        
        # Set thumbnail
        embed.set_thumbnail(url=beatmapset['covers']['list'])
        embed.set_author(name=f"{user['username']}'s Recent Play", 
                        icon_url=user['avatar_url'],
                        url=f"https://osu.ppy.sh/users/{user['id']}")
        
        # Grade emoji
        grade_emoji = {
            'SS': '🥇', 'SSH': '🥇', 'S': '🥈', 'SH': '🥈',
            'A': '🥉', 'B': '📗', 'C': '📘', 'D': '📙', 'F': '❌'
        }
        
        # Main stats
        rank_display = f"{grade_emoji.get(score['rank'], '❓')} {score['rank']}"
        pp_display = f"{score.get('pp', 0):.0f}pp" if score.get('pp') else "0pp"
        
        embed.add_field(name="⭐ Difficulty", value=f"{beatmap['difficulty_rating']:.2f}★", inline=True)
        embed.add_field(name="Grade", value=rank_display, inline=True)
        embed.add_field(name="PP", value=pp_display, inline=True)
        
        embed.add_field(name="🎯 Accuracy", value=f"{score['accuracy'] * 100:.2f}%", inline=True)
        embed.add_field(name="💯 Combo", value=f"{score['max_combo']}x", inline=True)
        embed.add_field(name="📊 Score", value=f"{score['score']:,}", inline=True)
        
        # Hit counts
        hits = f"300: {stats['count_300']} | 100: {stats['count_100']} | 50: {stats['count_50']} | Miss: {stats['count_miss']}"
        embed.add_field(name="Hits", value=hits, inline=False)
        
        # Mods
        mods = score.get('mods', [])
        if mods:
            embed.add_field(name="Mods", value=f"+{', '.join(mods)}", inline=False)
        
        # Timestamp
        played_at = datetime.fromisoformat(score['created_at'].replace('Z', '+00:00'))
        embed.set_footer(text=f"Played at {played_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        await ctx.send(embed=embed)

@bot.command(name='top', aliases=['best', 'bp'])
async def top(ctx, username: str, mode: str = "osu", limit: int = 5):
    """
    Get top osu! plays.
    Usage: !top <username> [mode] [limit]
    """
    if limit > 10:
        limit = 10
    
    await ctx.send(f"🔍 Fetching top plays for **{username}**...")
    
    user = osu_api.get_user(username, mode)
    if not user:
        await ctx.send(f"❌ Could not find user **{username}**")
        return
    
    scores = osu_api.get_user_best(user['id'], mode, limit)
    
    if not scores:
        await ctx.send(f"❌ No top plays found for **{username}**")
        return
    
    # Create single embed with all top plays
    embed = discord.Embed(
        title=f"🏆 Top {len(scores)} Plays for {user['username']}",
        url=f"https://osu.ppy.sh/users/{user['id']}",
        color=discord.Color.gold()
    )
    
    embed.set_thumbnail(url=user['avatar_url'])
    
    for i, score in enumerate(scores, 1):
        beatmap = score['beatmap']
        beatmapset = score['beatmapset']
        
        mods = f"+{','.join(score.get('mods', []))}" if score.get('mods') else "NoMod"
        
        value = (f"[{beatmap['version']}]({f'https://osu.ppy.sh/b/{beatmap["id"]}'}) "
                f"({beatmap['difficulty_rating']:.2f}★)\n"
                f"**{score.get('pp', 0):.0f}pp** • {score['accuracy'] * 100:.2f}% • "
                f"{score['rank']} • {score['max_combo']}x • {mods}")
        
        embed.add_field(
            name=f"{i}. {beatmapset['artist']} - {beatmapset['title']}",
            value=value,
            inline=False
        )
    
    embed.set_footer(text=f"Mode: {mode} | Total PP: {user['statistics']['pp']:,.0f}")
    
    await ctx.send(embed=embed)

@bot.command(name='help')
async def help_command(ctx):
    """Show help message."""
    embed = discord.Embed(
        title="🎮 osu! Bot Commands",
        description="Get osu! player stats and scores!",
        color=discord.Color.purple()
    )
    
    embed.add_field(
        name="!profile <username> [mode]",
        value="Get user profile (aliases: !osu, !p)",
        inline=False
    )
    embed.add_field(
        name="!recent <username> [mode] [limit]",
        value="Get recent scores (aliases: !rs, !r)",
        inline=False
    )
    embed.add_field(
        name="!top <username> [mode] [limit]",
        value="Get top plays (aliases: !best, !bp)",
        inline=False
    )
    embed.add_field(
        name="Modes",
        value="osu, taiko, fruits, mania (default: osu)",
        inline=False
    )
    
    embed.set_footer(text="Made with ❤️ for osu! players")
    
    await ctx.send(embed=embed)


if __name__ == "__main__":
    # Load tokens from environment variables
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    OSU_CLIENT_ID = os.getenv("OSU_CLIENT_ID")
    OSU_CLIENT_SECRET = os.getenv("OSU_CLIENT_SECRET")
    
    # Check if tokens are loaded
    if not all([DISCORD_TOKEN, OSU_CLIENT_ID, OSU_CLIENT_SECRET]):
        print("❌ ERROR: Missing environment variables!")
        print("Make sure you have a .env file with:")
        print("  DISCORD_TOKEN=your_token")
        print("  OSU_CLIENT_ID=your_id")
        print("  OSU_CLIENT_SECRET=your_secret")
        exit(1)
    
    # Initialize osu! API
    print("Initializing osu! API...")
    osu_api = OsuAPI(OSU_CLIENT_ID, OSU_CLIENT_SECRET)
    
    # Start the bot
    print("Starting Discord bot...")
    bot.run(DISCORD_TOKEN)