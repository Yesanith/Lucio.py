import discord
from discord import app_commands
from discord.ext import commands, tasks
import yt_dlp as youtube_dl
import asyncio
import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Lucio-themed settings
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'quiet': True,
    'geo-bypass': True,
    'source_address': '0.0.0.0',
    'default_search': 'auto'
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

class LucioMusic(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.last_activity = {}
        self.control_messages = {}
        self.check_inactivity.start()

    def get_queue(self, guild_id):
        return self.queues.setdefault(guild_id, [])

    async def search_youtube(self, query):
        try:
            with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
                info = ydl.extract_info(f"ytsearch:{query}", download=False)
                return {
                    'source': info['entries'][0]['url'],
                    'title': info['entries'][0]['title']
                } if 'entries' in info else {
                    'source': info['url'],
                    'title': info['title']
                }
        except Exception as e:
            print(f"Search error: {e}")
            return None

    async def lucio_say(self, message):
        return f"🎶 **LÚCIO:** {message} 🎧"

    async def update_control_panel(self, guild_id):
        if guild_id not in self.control_messages:
            return

        channel_id, message_id = self.control_messages[guild_id]
        channel = self.bot.get_channel(channel_id)
        
        try:
            message = await channel.fetch_message(message_id)
            queue = self.get_queue(guild_id)
            
            content = await self.lucio_say("**Live Mix:**\n")
            content += f"**Now Dropping:** {queue[0]['title']}\n\n" if queue else "**Silent moment...**\n\n"
            content += "**Track Controls:** ⏯️ ⏭️ ⏹️ 🔄\n"
            content += "**Next in line:**\n" + "\n".join([f"▸ {song['title']}" for song in queue[1:4]]) if len(queue) > 1 else "**Queue is clear!**\n"
            content += "\n\n*Let's turn up the beats!* 🎶"
            
            await message.edit(content=content)
        except Exception as e:
            print(f"Control panel update error: {e}")

    async def create_control_panel(self, interaction):
        try:
            queue = self.get_queue(interaction.guild.id)
            content = await self.lucio_say("**Live Mix Control Panel** 🎛️\n")
            content += f"**Now Dropping:** {queue[0]['title']}\n\n" if queue else "**Silent moment...**\n\n"
            content += "**Track Controls:** ⏯️ ⏭️ ⏹️ 🔄\n"
            content += "**Next in line:**\n" + "\n".join([f"▸ {song['title']}" for song in queue[1:4]]) if len(queue) > 1 else "**Queue is clear!**\n"
            content += "\n\n*Let's turn up the beats!* 🎶"
            
            message = await interaction.channel.send(content)
            self.control_messages[interaction.guild.id] = (interaction.channel.id, message.id)
            
            controls = ['⏯️', '⏭️', '⏹️', '🔄']
            for emoji in controls:
                await message.add_reaction(emoji)
                
        except Exception as e:
            print(f"Control panel creation error: {e}")

    async def play_next(self, interaction):
        guild_id = interaction.guild.id
        queue = self.get_queue(guild_id)
        
        if queue:
            interaction.guild.voice_client.stop()
            current = queue.pop(0)
            
            interaction.guild.voice_client.play(
                discord.FFmpegPCMAudio(current['source'], **FFMPEG_OPTIONS),
                after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(interaction), self.bot.loop)
            )
            
            await interaction.channel.send(await self.lucio_say(f"New track dropping! **{current['title']}** 🎵"))
            
            if guild_id in self.control_messages:
                await self.update_control_panel(guild_id)
            else:
                await self.create_control_panel(interaction)
        else:
            if guild_id in self.control_messages:
                await self.update_control_panel(guild_id)
            await interaction.channel.send(await self.lucio_say("Queue empty! Time for an encore? 🎤"))

    @tasks.loop(seconds=30)
    async def check_inactivity(self):
        for guild in self.bot.guilds:
            voice_client = guild.voice_client
            if voice_client and voice_client.is_connected():
                is_playing = voice_client.is_playing() or voice_client.is_paused()
                has_queue = len(self.get_queue(guild.id)) > 0
                
                if not is_playing and not has_queue:
                    last_active = self.last_activity.get(guild.id, datetime.datetime.min)
                    if (datetime.datetime.now() - last_active).total_seconds() > 120:
                        await voice_client.disconnect()
                        self.queues[guild.id].clear()
                        if guild.id in self.control_messages:
                            channel_id, message_id = self.control_messages[guild.id]
                            channel = self.bot.get_channel(channel_id)
                            try:
                                message = await channel.fetch_message(message_id)
                                await message.delete()
                            except:
                                pass
                            del self.control_messages[guild.id]
                        await voice_client.channel.send(await self.lucio_say("Peace out! Catch you on the flip side! ✌️"))
                else:
                    self.last_activity[guild.id] = datetime.datetime.now()

    @app_commands.command(name="help", description="Show Lucio's command list")
    async def help_command(self, interaction: discord.Interaction):
        help_embed = discord.Embed(title="🎧 Lucio's Mix Station", color=0x00ff00)
        help_embed.set_thumbnail(url="https://i.imgur.com/3KbU5eN.png")
        help_embed.add_field(
            name="Track Controls:",
            value=(
                "`/play <song>` - Drop a new track\n"
                "`/queue` - Check the lineup\n"
                "`/skip` - Next track!\n"
                "`/pause` - Break time\n"
                "`/resume` - Back in action\n"
                "`/stop` - Shut it down\n"
                "`/help` - This menu"
            ),
            inline=False
        )
        help_embed.set_footer(text="Let's turn up the beats! 🎶")
        await interaction.response.send_message(embed=help_embed)

    @app_commands.command(name="play", description="Play a song or add to queue")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        self.last_activity[interaction.guild.id] = datetime.datetime.now()
        
        if not interaction.user.voice:
            return await interaction.followup.send(await self.lucio_say("Hey! Jump in the mix channel first! 🎧"))

        voice_client = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
        
        async with interaction.channel.typing():
            song = await self.search_youtube(query)
            if not song:
                return await interaction.followup.send(await self.lucio_say("Track not found! Let's try another vibe? 🎛️"))

            queue = self.get_queue(interaction.guild.id)
            queue.append(song)
            
            if not voice_client.is_playing():
                await self.play_next(interaction)
            else:
                await interaction.followup.send(await self.lucio_say(f"Added to lineup: **{song['title']}** ➕"))

    @app_commands.command(name="queue", description="Show current queue")
    async def show_queue(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild.id)
        if not queue:
            return await interaction.response.send_message(await self.lucio_say("No tracks in the lineup! Time to drop some beats! 🎧"))
        
        queue_list = "\n".join([f"**{i+1}.** {song['title']}" for i, song in enumerate(queue[:8])])
        await interaction.response.send_message(await self.lucio_say(f"Current Mix Lineup:\n{queue_list}"))

    @app_commands.command(name="skip", description="Skip current song")
    async def skip(self, interaction: discord.Interaction):
        if interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.stop()
            await interaction.response.send_message(await self.lucio_say("Skipping track! Next beat dropping! ⏭️"))

    @app_commands.command(name="pause", description="Pause playback")
    async def pause(self, interaction: discord.Interaction):
        if interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.pause()
            await interaction.response.send_message(await self.lucio_say("Music paused! Catch your breath... ⏸️"))

    @app_commands.command(name="resume", description="Resume playback")
    async def resume(self, interaction: discord.Interaction):
        if interaction.guild.voice_client.is_paused():
            interaction.guild.voice_client.resume()
            await interaction.response.send_message(await self.lucio_say("And we're back! Let's go! ▶️"))

    @app_commands.command(name="stop", description="Stop the bot")
    async def stop(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            self.queues[interaction.guild.id].clear()
            if interaction.guild.id in self.control_messages:
                channel_id, message_id = self.control_messages[interaction.guild.id]
                channel = self.bot.get_channel(channel_id)
                try:
                    message = await channel.fetch_message(message_id)
                    await message.delete()
                except:
                    pass
                del self.control_messages[interaction.guild.id]
            await interaction.response.send_message(await self.lucio_say("Shutting down! Keep the rhythm alive! 🎶"))

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot or reaction.message.id not in [msg[1] for msg in self.control_messages.values()]:
            return

        guild = reaction.message.guild
        voice_client = guild.voice_client
        
        try:
            if str(reaction.emoji) == '⏯️':
                if voice_client.is_paused():
                    voice_client.resume()
                else:
                    voice_client.pause()
                await self.update_control_panel(guild.id)
                
            elif str(reaction.emoji) == '⏭️':
                voice_client.stop()
                
            elif str(reaction.emoji) == '⏹️':
                await voice_client.disconnect()
                self.queues[guild.id].clear()
                await reaction.message.delete()
                del self.control_messages[guild.id]
                
            elif str(reaction.emoji) == '🔄':
                await self.update_control_panel(guild.id)
            
            await reaction.remove(user)
            
        except Exception as e:
            print(f"Reaction error: {e}")

# Bot setup
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='?', intents=intents)

@bot.event
async def on_ready():
    await bot.add_cog(LucioMusic(bot))
    await bot.tree.sync()
    print(f'🎧 {bot.user.name} is live!')

bot.run(os.getenv('DISCORD_TOKEN'))