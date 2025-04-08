import discord
from discord import app_commands
from discord.ext import commands, tasks
import yt_dlp as youtube_dl
import asyncio
import datetime
import os
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

# Optimized Lucio settings
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'quiet': True,
    'geo-bypass': True,
    'source_address': '0.0.0.0',
    'default_search': 'ytsearch',
    'socket_timeout': 10
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -threads 2',
    'options': '-vn -loglevel warning'
}

class LucioMusic(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = defaultdict(list)
        self.last_activity = {}
        self.control_messages = {}  # {message_id: guild_id}
        self.pending_updates = {}
        self.check_inactivity.start()

    def get_queue(self, guild_id):
        return self.queues[guild_id]

    async def search_youtube(self, query):
        try:
            ydl = youtube_dl.YoutubeDL(YDL_OPTIONS)
            info = await asyncio.to_thread(ydl.extract_info, query, download=False)
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
        if guild_id not in self.control_messages.values():
            return

        message_id = next((k for k, v in self.control_messages.items() if v == guild_id), None)
        if not message_id:
            return

        channel = self.bot.get_channel(self.bot.get_guild(guild_id).text_channels[0].id)
        
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

    async def schedule_panel_update(self, guild_id):
        if guild_id in self.pending_updates:
            self.pending_updates[guild_id].cancel()
        
        async def do_update():
            await self.update_control_panel(guild_id)
            del self.pending_updates[guild_id]
        
        self.pending_updates[guild_id] = asyncio.create_task(do_update())

    async def create_control_panel(self, interaction):
        try:
            queue = self.get_queue(interaction.guild.id)
            content = await self.lucio_say("**Live Mix Control Panel** 🎛️\n")
            content += f"**Now Dropping:** {queue[0]['title']}\n\n" if queue else "**Silent moment...**\n\n"
            content += "**Track Controls:** ⏯️ ⏭️ ⏹️ 🔄\n"
            content += "**Next in line:**\n" + "\n".join([f"▸ {song['title']}" for song in queue[1:4]]) if len(queue) > 1 else "**Queue is clear!**\n"
            content += "\n\n*Let's turn up the beats!* 🎶"
            
            message = await interaction.channel.send(content)
            self.control_messages[message.id] = interaction.guild.id
            
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
            
            await self.schedule_panel_update(guild_id)
        else:
            await self.schedule_panel_update(guild_id)
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
                        message_ids = [k for k, v in self.control_messages.items() if v == guild.id]
                        for msg_id in message_ids:
                            del self.control_messages[msg_id]
                            try:
                                channel = self.bot.get_channel(guild.text_channels[0].id)
                                await (await channel.fetch_message(msg_id)).delete()
                            except:
                                pass
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
            song = await self.search_youtube(f"ytsearch:{query}")
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
            message_ids = [k for k, v in self.control_messages.items() if v == interaction.guild.id]
            for msg_id in message_ids:
                del self.control_messages[msg_id]
                try:
                    channel = self.bot.get_channel(interaction.channel.id)
                    await (await channel.fetch_message(msg_id)).delete()
                except:
                    pass
            await interaction.response.send_message(await self.lucio_say("Shutting down! Keep the rhythm alive! 🎶"))

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot or reaction.message.id not in self.control_messages:
            return

        guild_id = self.control_messages[reaction.message.id]
        guild = self.bot.get_guild(guild_id)
        voice_client = guild.voice_client
        
        try:
            if str(reaction.emoji) == '⏯️':
                if voice_client.is_paused():
                    voice_client.resume()
                else:
                    voice_client.pause()
                await self.schedule_panel_update(guild_id)
                
            elif str(reaction.emoji) == '⏭️':
                voice_client.stop()
                
            elif str(reaction.emoji) == '⏹️':
                await voice_client.disconnect()
                self.queues[guild_id].clear()
                await reaction.message.delete()
                del self.control_messages[reaction.message.id]
                
            elif str(reaction.emoji) == '🔄':
                await self.schedule_panel_update(guild_id)
            
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
