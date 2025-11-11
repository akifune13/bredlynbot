import discord
from discord.ext import commands
from discord.ui import Button, View
import requests
from datetime import datetime
from typing import Optional, Dict
import os
from dotenv import load_dotenv
import json

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
    
    def get_user_best(self, user_id: int, mode: str = "osu", limit: int = 100) -> list:
        """Get best scores for a user."""
        params = {
            'mode': mode,
            'limit': limit
        }
        return self._make_request(f"users/{user_id}/scores/best", params) or []


class UserLinkManager:
    """Manager for storing Discord user to osu! account links."""
    
    def __init__(self, filename: str = "user_links.json"):
        self.filename = filename
        self.links = self._load_links()
    
    def _load_links(self) -> dict:
        """Load user links from file."""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading user links: {e}")
        return {}
    
    def _save_links(self):
        """Save user links to file."""
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.links, f, indent=2)
        except Exception as e:
            print(f"Error saving user links: {e}")
    
    def link_user(self, discord_id: int, osu_username: str, mode: str = "osu"):
        """Link a Discord user to an osu! account."""
        self.links[str(discord_id)] = {
            "osu_username": osu_username,
            "mode": mode
        }
        self._save_links()
    
    def unlink_user(self, discord_id: int):
        """Unlink a Discord user from their osu! account."""
        discord_id_str = str(discord_id)
        if discord_id_str in self.links:
            del self.links[discord_id_str]
            self._save_links()
            return True
        return False
    
    def get_linked_user(self, discord_id: int) -> Optional[Dict]:
        """Get the linked osu! account for a Discord user."""
        return self.links.get(str(discord_id))


class TopPlaysPaginator(View):
    """Paginated view for top plays."""
    
    def __init__(self, scores: list, user: dict, mode: str, per_page: int = 10):
        super().__init__(timeout=300)  # 5 minute timeout
        self.scores = scores
        self.user = user
        self.mode = mode
        self.per_page = per_page
        self.current_page = 0
        self.max_pages = (len(scores) - 1) // per_page
        
        # Update button states
        self.update_buttons()
    
    def update_buttons(self):
        """Update button states based on current page."""
        self.first_button.disabled = self.current_page == 0
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.max_pages
        self.last_button.disabled = self.current_page >= self.max_pages
    
    def get_embed(self) -> discord.Embed:
        """Generate embed for current page."""
        start_idx = self.current_page * self.per_page
        end_idx = min(start_idx + self.per_page, len(self.scores))
        page_scores = self.scores[start_idx:end_idx]
        
        embed = discord.Embed(
            title=f"🏆 Top Plays for {self.user['username']}",
            url=f"https://osu.ppy.sh/users/{self.user['id']}",
            color=discord.Color.gold()
        )
        
        embed.set_thumbnail(url=self.user['avatar_url'])
        
        for i, score in enumerate(page_scores, start_idx + 1):
            beatmap = score['beatmap']
            beatmapset = score['beatmapset']
            
            mods = f"+{','.join(score.get('mods', []))}" if score.get('mods') else "NoMod"
            
            value = (f"[{beatmap['version']}](https://osu.ppy.sh/b/{beatmap['id']}) "
                    f"({beatmap['difficulty_rating']:.2f}★)\n"
                    f"**{score.get('pp', 0):.0f}pp** • {score['accuracy'] * 100:.2f}% • "
                    f"{score['rank']} • {score['max_combo']}x • {mods}")
            
            embed.add_field(
                name=f"{i}. {beatmapset['artist']} - {beatmapset['title']}",
                value=value,
                inline=False
            )
        
        embed.set_footer(
            text=f"Page {self.current_page + 1}/{self.max_pages + 1} | "
                 f"Mode: {self.mode} | Total PP: {self.user['statistics']['pp']:,.0f}"
        )
        
        return embed
    
    @discord.ui.button(label="⏮️", style=discord.ButtonStyle.gray)
    async def first_button(self, interaction: discord.Interaction, button: Button):
        """Go to first page."""
        self.current_page = 0
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
    
    @discord.ui.button(label="◀️", style=discord.ButtonStyle.primary)
    async def prev_button(self, interaction: discord.Interaction, button: Button):
        """Go to previous page."""
        self.current_page = max(0, self.current_page - 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
    
    @discord.ui.button(label="▶️", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: Button):
        """Go to next page."""
        self.current_page = min(self.max_pages, self.current_page + 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
    
    @discord.ui.button(label="⏭️", style=discord.ButtonStyle.gray)
    async def last_button(self, interaction: discord.Interaction, button: Button):
        """Go to last page."""
        self.current_page = self.max_pages
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
    
    @discord.ui.button(label="🗑️", style=discord.ButtonStyle.danger)
    async def delete_button(self, interaction: discord.Interaction, button: Button):
        """Delete the message."""
        await interaction.message.delete()


# Initialize bot with command prefix
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Initialize osu! API and user link manager
osu_api = None
user_links = None

@bot.event
async def on_ready():
    print(f'✓ Bot is ready! Logged in as {bot.user.name}')
    print(f'Bot ID: {bot.user.id}')
    print('------')

@bot.command(name='link')
async def link_account(ctx, osu_username: str, mode: str = "osu"):
    """
    Link your Discord account to your osu! profile.
    Usage: !link <osu_username> [mode]
    Example: !link peppy osu
    """
    # Verify the osu! account exists
    user = osu_api.get_user(osu_username, mode)
    
    if not user:
        await ctx.send(f"❌ Could not find osu! user **{osu_username}** in mode **{mode}**")
        return
    
    # Link the account
    user_links.link_user(ctx.author.id, user['username'], mode)
    
    embed = discord.Embed(
        title="✅ Account Linked!",
        description=f"Your Discord account has been linked to **{user['username']}** ({mode} mode)",
        color=discord.Color.green()
    )
    embed.set_thumbnail(url=user['avatar_url'])
    embed.add_field(
        name="💡 Tip",
        value="You can now use commands without typing your username!\n"
              "Example: `!profile` or `!recent`",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name='unlink')
async def unlink_account(ctx):
    """
    Unlink your Discord account from your osu! profile.
    Usage: !unlink
    """
    if user_links.unlink_user(ctx.author.id):
        await ctx.send("✅ Your account has been unlinked!")
    else:
        await ctx.send("❌ You don't have a linked account!")

@bot.command(name='profile', aliases=['osu', 'p'])
async def profile(ctx, username: str = None, mode: str = None):
    """
    Get osu! user profile.
    Usage: !profile [username] [mode]
    If username is not provided, uses your linked account.
    """
    # If no username provided, try to get linked account
    if username is None:
        linked = user_links.get_linked_user(ctx.author.id)
        if linked:
            username = linked['osu_username']
            mode = mode or linked['mode']
        else:
            await ctx.send("❌ Please provide a username or link your account with `!link <username>`")
            return
    
    # Default mode
    if mode is None:
        mode = "osu"
    
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
async def recent(ctx, username: str = None, mode: str = None, limit: int = 1):
    """
    Get recent osu! scores.
    Usage: !recent [username] [mode] [limit]
    If username is not provided, uses your linked account.
    """
    # If no username provided, try to get linked account
    if username is None:
        linked = user_links.get_linked_user(ctx.author.id)
        if linked:
            username = linked['osu_username']
            mode = mode or linked['mode']
        else:
            await ctx.send("❌ Please provide a username or link your account with `!link <username>`")
            return
    
    # Default mode
    if mode is None:
        mode = "osu"
    
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
async def top(ctx, username: str = None, mode: str = None, limit: int = 100):
    """
    Get top osu! plays with pagination.
    Usage: !top [username] [mode] [limit]
    If username is not provided, uses your linked account.
    Max limit: 100 plays
    """
    # If no username provided, try to get linked account
    if username is None:
        linked = user_links.get_linked_user(ctx.author.id)
        if linked:
            username = linked['osu_username']
            mode = mode or linked['mode']
        else:
            await ctx.send("❌ Please provide a username or link your account with `!link <username>`")
            return
    
    # Default mode
    if mode is None:
        mode = "osu"
    
    # Cap limit at 100
    if limit > 100:
        limit = 100
    
    await ctx.send(f"🔍 Fetching top {limit} plays for **{username}**...")
    
    user = osu_api.get_user(username, mode)
    if not user:
        await ctx.send(f"❌ Could not find user **{username}**")
        return
    
    scores = osu_api.get_user_best(user['id'], mode, limit)
    
    if not scores:
        await ctx.send(f"❌ No top plays found for **{username}**")
        return
    
    # Create paginated view
    view = TopPlaysPaginator(scores, user, mode, per_page=10)
    await ctx.send(embed=view.get_embed(), view=view)

@bot.command(name='osuhelp')
async def help_command(ctx):
    """Show help message."""
    embed = discord.Embed(
        title="🎮 osu! Bot Commands",
        description="Get osu! player stats and scores!",
        color=discord.Color.purple()
    )
    
    embed.add_field(
        name="🔗 Account Linking",
        value="`!link <username> [mode]` - Link your osu! account\n"
              "`!unlink` - Unlink your account",
        inline=False
    )
    embed.add_field(
        name="📊 Stats Commands",
        value="`!profile [username] [mode]` - Get user profile (aliases: !osu, !p)\n"
              "`!recent [username] [mode] [limit]` - Get recent scores (aliases: !rs, !r)\n"
              "`!top [username] [mode] [limit]` - Get top plays with pages (aliases: !best, !bp)",
        inline=False
    )
    embed.add_field(
        name="🎯 Modes",
        value="osu, taiko, fruits, mania (default: osu)",
        inline=False
    )
    embed.add_field(
        name="💡 Tips",
        value="• Link your account to use commands without typing your username!\n"
              "• Use arrow buttons to navigate through pages in !top\n"
              "• You can still check other players by providing their username",
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
    
    # Initialize osu! API and user link manager
    print("Initializing osu! API...")
    osu_api = OsuAPI(OSU_CLIENT_ID, OSU_CLIENT_SECRET)
    
    print("Initializing user link manager...")
    user_links = UserLinkManager()
    
    # Start the bot
    print("Starting Discord bot...")
    bot.run(DISCORD_TOKEN)