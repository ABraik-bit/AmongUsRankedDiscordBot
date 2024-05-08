import asyncio
import difflib
import json
import logging
import io
from datetime import datetime
from typing import Union, Optional

import discord
from discord.ext import commands
from discord.ext.commands import Context
from discord import app_commands, Button, ButtonStyle

from file_processing import FileHandler
from match_class import Match

from rapidfuzz import fuzz, process
import pandas as pd
import matplotlib.pyplot as plt
import os


default_color_emojis = {
    0  : "<:R:1228193212716421130>",
    1  : "<:B:1228163812054532166>",
    2  : "<:G:1228193210032193556>",
    3  : "<:P:1228193211437023332>",
    4  : "<:O:1228163815301054564>",
    5  : "<:Y:1228193217456115722>",
    6  : "<:B:1228163811085647953>",
    7  : "<:W:1228193257339486338>",
    8  : "<:P:1228175468428005446>",
    9  : "<:B:1228163812717236225>",
    10 : "<:C:1228193206244606035>",
    11 : "<:L:1228175470290538506>",
    12 : "<:M:1228163814009077890>",
    13 : "<:R:1228193213815197717>",
    14 : "<:B:1228163809999323236>",
    15 : "<:G:1228193208060870726>",
    16 : "<:T:1228193214826020905>",
    17 : "<:C:1228193205397360670>",
    #add an offset of 100 for imp emoji 
    100  : "<a:R:1235173449907834911>",
    101  : "<a:B:1235173254566510642>",
    102  : "<a:G:1235173333583265814>",
    103  : "<a:P:1235173339429994526>",
    104  : "<a:O:1235173337861328906>",
    105  : "<a:Y:1235173456069267458>",
    106  : "<a:B:1235173253274669056>",
    107  : "<a:W:1235173454555254785>",
    108  : "<a:P:1235173340658925610>",
    109  : "<a:B:1235173255493713931>",
    110  : "<a:C:1235173258270343193>",
    111  : "<a:L:1235173335084564560>",
    112  : "<a:M:1235173336355700756>",
    113  : "<a:R:1235173451732357173>",
    114  : "<a:B:1235173251856990291>",
    115  : "<a:G:1235173259138437326>",
    116  : "<a:T:1235173453511004211>",
    117  : "<a:C:1235173257091747860>",
    #add an offset of 200 for body emoji 
    200  : "<:R:1235795306512384061>",
    201  : "<:B:1235795307883659385>",
    202  : "<:G:1235795311075659776>",
    203  : "<:P:1235795302112432191>",
    204  : "<:O:1235795300967387146>",
    205  : "<:Y:1235795299595718758>",
    206  : "<:B:1235795399374143578>",
    207  : "<:W:1235795392453672980>",
    208  : "<:P:1235795344671899698>",
    209  : "<:B:1235795394265350185>",
    210  : "<:C:1235795303148421230>",
    211  : "<:L:1235795304100528239>",
    212  : "<:M:1235795395653668924>",
    213  : "<:R:1235795391258034256>",
    214  : "<:B:1235795346022727710>",
    215  : "<:G:1235795397935366144>",
    216  : "<:T:1235795396836720650>",
    217  : "<:C:1235795305560145950>",
}

                 
kill_emoji = "<:killed:1235175579221889108>"
emergency_emoji = "<:emergency:1235713457651716178>"
report_emoji = "<:report:1235713458822053918>"
done_emoji = "✅"
voted_emoji = "<:I_voted:1235863957097414728>"

top_emojis = ["🥇", "🥈", "🥉"]
extra_emojis = ["👑", "💎", "🎖️", "🏆", "🏅"]
class DiscordBot(commands.Bot):
    def __init__(self, command_prefix='!', token = None, variables = None, **options):
        # init loggers
        logging.getLogger("discord").setLevel(logging.INFO)
        logging.getLogger("websockets").setLevel(logging.INFO)
        logging.getLogger("asyncio").setLevel(logging.INFO)
        logging.getLogger("matplotlib").setLevel(logging.INFO)
        logging.basicConfig(level=logging.INFO, encoding='utf-8', format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler("DiscordBot.log", encoding='utf-8'),logging.StreamHandler()])
        self.logger = logging.getLogger('Discord_Bot')

        # init guild variables
        self.matches_path = variables['matches_path']
        self.database_location = variables['database_location']
        self.channels = variables['ranked_channels']
        self.guild_id = variables['guild_id']
        self.match_logs = variables['match_logs_channel']
        self.bot_commands = variables['bot_commands_channel']
        self.management_role = variables['moderator_role_id']
        self.staff_role = variables['staff_role_id']
        self.cancels_channel = variables['cancels_channel']
        self.admin_logs_channel = variables['admin_logs_channel']
        self.season_name = variables['season_name']
        

        #init local variables
        self.ratio = 80
        self.fuzz_rapid = False
        self.auto_mute = True
        self.games_in_progress = []
        self.version = "v1.2"

        #init subclasses
        self.file_handler = FileHandler(self.matches_path, self.database_location)
        self.leaderboard = self.file_handler.leaderboard

        #check for unprocessed matches
        self.logger.info(f"Loading all match files from{self.matches_path}")
        match = self.file_handler.process_unprocessed_matches()
        if match:
            self.logger.info("Leaderboard has been updated")
            self.leaderboard.load_leaderboard()
        else:
            self.logger.info("Leaderboard is already up to date")

        #init bot
        self.token = token
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.voice_states = True
        super().__init__(command_prefix=command_prefix, intents=intents, help_command=None, **options)
        self.guild : discord.Guild

        self.add_commands()
        self.add_events()
        
        self.logger.info(f'Imported match files from {self.matches_path}, and Database location from {self.database_location}')
        self.logger.info(f'Imported Database location from {self.database_location}')
        self.logger.info(f'Guild ID is {self.guild_id}')


    def add_commands(self):
        @self.hybrid_command(name="stats", description = "Display Stats of yourself or a player")
        @app_commands.describe(player = "Player name or @Player")
        async def stats(ctx: Context, player: Optional[str] = None):
            if ctx.channel.id != self.bot_commands:
                await ctx.send(f"Please use https://discord.com/channels/{self.guild_id}/{self.bot_commands}",delete_after=5)
                await ctx.message.delete(delay=1)
                return

            thumbnail = self.guild.icon.url
            if player is None:
                player_name = ctx.author.display_name
                player_row = self.leaderboard.get_player_by_discord(ctx.author.id)
                thumbnail = ctx.author.avatar.url

            elif player.startswith("<@"):
                player_id = player[2:-1]
                player_row = self.leaderboard.get_player_by_discord(player_id)
                member = self.guild.get_member(int(player_id))
                player_name = member.display_name
                thumbnail = member.avatar.url

            else:
                player_name = player
                player_row = self.leaderboard.get_player_row(player_name)
                if player_row is not None:
                    try:
                        discord_id = int(self.leaderboard.get_player_discord(player_row))
                        player = self.guild.get_member(discord_id)
                        thumbnail = player.avatar.url
                    except:
                        self.logger.warning(f"Can't find discord for {player_name}")
                else:
                    await ctx.send(f"Player {player_name} not found.")
                    return
                
            if player_row is None:

                player_row = self.leaderboard.get_player_row(player_name)
                if player_row is None:
                    await ctx.send(f"Player {player_name} not found.")
                    return

            player_stats = {
                'Rank': self.leaderboard.get_player_ranking(player_row),
                'Player Name': player_name,
                'Voting Accuracy': f"{round(self.leaderboard.get_player_voting_accuracy(player_row) * 100, 1)}%",

                'MMR': self.leaderboard.get_player_mmr(player_row),
                'Crewmate MMR': self.leaderboard.get_player_crew_mmr(player_row),
                'Impostor MMR': self.leaderboard.get_player_imp_mmr(player_row),
                
                'Games Played': player_row['Total Number Of Games Played'],
                'Games Won': player_row['Number Of Games Won'],
                'Win Rate': f"{round(self.leaderboard.get_player_win_rate(player_row), 1)}%",
                
                'Crew Games Played': player_row['Number Of Crewmate Games Played'],
                'Crew Games Won': player_row['Number Of Crewmate Games Won'],
                'Crewmate Win Rate': f"{round(self.leaderboard.get_player_crew_win_rate(player_row), 1)}%",

                'Imp Games Played': player_row['Number Of Impostor Games Played'],
                'Imp Games Won': player_row['Number Of Impostor Games Won'],
                'Impostor Win Rate': f"{round(self.leaderboard.get_player_imp_win_rate(player_row), 1)}%"
            }

            embed = discord.Embed(title=f'{player_name} Player Stats', color=discord.Color.purple())
            embed.set_thumbnail(url=thumbnail)

            for stat_name, stat_value in player_stats.items():
                embed.add_field(name=stat_name, value=stat_value, inline=True)

            player_mmr = self.leaderboard.get_player_mmr(player_row)

            if player_mmr < 900:
                embed_url = "https://i.ibb.co/dc4QjkX/Bronze.jpg"
            elif player_mmr < 1050:
                embed_url = "https://i.ibb.co/WxtrhwJ/Silver.jpg"
            elif player_mmr < 1200:
                embed_url = "https://i.ibb.co/jHtsj2h/Gold.jpg"
            else:
                embed_url = "https://i.ibb.co/0s1xM4v/Diamond.jpg"

            if self.leaderboard.is_player_sherlock(player_name):
                embed.title = "Stats of **Sherlock Crewmate**"
                embed_url = "https://static.wikia.nocookie.net/deathnote/images/8/83/Lawliet-L-Cole.png/revision/latest?cb=20170907105910"
            elif self.leaderboard.is_player_jack_the_ripper(player_name):
                embed.title = "Stats of **Jack The Ripper Impostor**"
                embed_url = "https://static.wikia.nocookie.net/9a57a21c-6c64-4876-aade-d64dfddaf740/scale-to-width-down/800"

            embed.set_image(url=embed_url)
            embed.set_footer(text=f"{self.season_name} Data - Bot Programmed by Aiden | Version: {self.version}", icon_url=self.user.avatar.url)
            await ctx.channel.send(embed=embed)
            self.logger.info(f'Sent stats of {player_name} to Channel {ctx.channel.name}')


        @self.hybrid_command(name="lb", description = "Display Leaderboard of the top players")
        @app_commands.describe(length = "length of the leaderboard")
        @app_commands.describe(type = "[crew/imp/None]")
        async def lb(ctx:Context, length: Optional[int] = None, type: Optional[str] = None):
            if ctx.channel.id != self.bot_commands:
                await ctx.send(f"Please use https://discord.com/channels/{self.guild_id}/{self.bot_commands}", delete_after=5)
                await ctx.message.delete(delay=1)
                return
            players_per_field = 20

            if type:
                if type.startswith('imp'):
                    top_players = self.leaderboard.top_players_by_impostor_mmr(length or 10)  
                    title = f"{length or 10} Top Impostors"
                    color = discord.Color.red()

                elif type.startswith('crew'):
                    top_players = self.leaderboard.top_players_by_crewmate_mmr(length or 10)
                    title = f"{length or 10} Top Crewmates"
                    color = discord.Color.green()

            else:
                top_players = self.leaderboard.top_players_by_mmr(length or 10)
                title = f"{length or 10} Top Players Overall"
                color = discord.Color.blue()


            embed = discord.Embed(title=title, color=color)
            embed.set_thumbnail(url=self.guild.icon.url)

            chunks = [top_players[i:i + players_per_field] for i in range(0, len(top_players), players_per_field)]

            for i, chunk in enumerate(chunks):
                leaderboard_text = ""
                for index, row in chunk.iterrows():
                    rank = top_emojis[index] if index < len(top_emojis) else f"**{index + 1}.**"
                    leaderboard_text += f"{rank} **{row['Player Name']}**\n"
                    leaderboard_text += f"MMR: {row.iloc[1]}\n"
                embed.add_field(name=f"", value=leaderboard_text, inline=False)

            embed.set_footer(text=f"{self.season_name} Data - Bot Programmed by Aiden | Version: {self.version}", icon_url=self.user.avatar.url)
            await ctx.send(embed=embed)
            self.logger.info(f'Sent stats of {length or 10} {title} to Channel {ctx.channel.name}')


        @self.hybrid_command(name="graph_mmr", description = "Graph MMR change of yourself or a player")
        @app_commands.describe(player = "Player name or @Player")
        async def graph_mmr(ctx:Context, player: Optional[str]):
            if ctx.channel.id != self.bot_commands:
                await ctx.send(f"Please use https://discord.com/channels/{self.guild_id}/{self.bot_commands}",delete_after=5)
                await ctx.message.delete(delay=1)
                return
            member = None
            player_name = None 
            player_row = None

            if player is None:  # If no argument is provided
                member = ctx.author
                discord_id = ctx.author.id
                player_name = ctx.author.display_name
                player_row = self.leaderboard.get_player_by_discord(discord_id)
                
            elif player.startswith('<@'):  # If a mention is provided
                try:
                    mentioned_id = int(player[2:-1])
                    member = ctx.guild.get_member(mentioned_id)
                    player_name = member.display_name
                    player_row = self.leaderboard.get_player_by_discord(mentioned_id)
                    
                except Exception as e:
                    self.logger.error(e, mentioned_id)
                    await ctx.send(f"Invalid mention provided: {player}")
                    return
                
            else:  # If a display name is provided
                player_name = player
                player_row = self.leaderboard.get_player_row(player_name)
                if player_row is None:
                    player_row = self.leaderboard.get_player_row_lookslike(player_name)
                    if player_row is None:
                            await ctx.channel.send(f"Player {player_name} not found.")
                            return
                discord_id = self.leaderboard.get_player_discord(player_row)
                    
            if player_row is None:
                player_row = self.leaderboard.get_player_row(player_name)
                if player_row is None:
                    player_row = self.leaderboard.get_player_row_lookslike(player_name)
                    if player_row is None:
                        await ctx.channel.send(f"Player {player_name} not found.")
                        return
            mmr_changes = player_row['Change In MMR']
            crew_changes = player_row['Change In Crewmate MMR']
            imp_changes = player_row['Change In Impostor MMR']
            impostor_mmr = 1000
            crew_mmr = 1000
            total_mmr = 1000
            impostor_mmrs = [impostor_mmr]
            crew_mmrs = [crew_mmr]
            total_mmrs = [total_mmr]
            for i in range(len(mmr_changes)):
                impostor_mmr += imp_changes[i]
                crew_mmr += crew_changes[i]
                total_mmr += mmr_changes[i]
                impostor_mmrs.append(impostor_mmr)
                crew_mmrs.append(crew_mmr)
                total_mmrs.append(total_mmr)
            plt.plot(impostor_mmrs, color='red', label='Impostor MMR')
            plt.plot(crew_mmrs, color='blue', label='Crew MMR')
            plt.plot(total_mmrs, color='purple', label='Total MMR')
            plt.xlabel(player_name)
            plt.ylabel('MMR')
            plt.title('MMR Changes Over Time')
            plt.legend()
            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            await ctx.send(file=discord.File(buf, filename='mmr_changes.png'))
            plt.clf()


        @self.hybrid_command(name="link", description="Link a player or yourself to the bot")
        @app_commands.describe(player="Player name in game")
        @app_commands.describe(discord="Discord mention @Player")
        async def link(ctx: Context, player: str, discord: Optional[discord.Member] = None):
            if not player:
                await ctx.send("Please provide a player name.")
                return

            player_row = self.leaderboard.get_player_row(player)
            player_discord = self.leaderboard.get_player_discord(player_row)

            if discord is None:
                discord_id = ctx.author.id
            else:
                discord_id = discord.id

            if player_discord:
                await ctx.send(f"{player} is already linked to <@{int(player_discord)}>.")
                return

            if player_row is None:
                await ctx.send(f"Player {player} not found in the database.")
                return

            if self.leaderboard.add_player_discord(player, discord_id):
                await ctx.send(f"Linked {player} to <@{discord_id}> in the leaderboard.")
            else:
                await ctx.send("Failed to link the player. Please try again later.")


        @self.hybrid_command(name="unlink", description="Unlink a player from the bot")
        @app_commands.describe(player="Player name in game or @mention")
        async def unlink(ctx: Context, player: str):
            if self.staff_role not in [role.id for role in ctx.author.roles]:
                await ctx.channel.send("You don't have permission to unlink players.")
                return

            if player.startswith('<@'):  # unlinking a mention
                discord_id = int(player[2:-1])
                player_row = self.leaderboard.get_player_by_discord(discord_id)
                if player_row is not None:
                    self.leaderboard.delete_player_discord(player_row['Player Name'])
                    await ctx.send(f"Unlinked {player_row['Player Name']} from <@{discord_id}>")
                else:
                    await ctx.send(f"{player} is not linked to any account")

            else:  # unlinking a player name
                player_row = self.leaderboard.get_player_row(player)
                if player_row is not None:
                    discord_id = self.leaderboard.get_player_discord(player_row)
                    if discord_id is not None:
                        self.leaderboard.delete_player_discord(player)
                        await ctx.send(f"Unlinked {player} from <@{discord_id}>")
                    else:
                        await ctx.send(f"Player {player} is not linked to any account")
                else:
                    await ctx.send(f"Player {player} not found in the database.")
        
        
        @self.hybrid_command(name="change_match", description="Change a match outcome")
        @app_commands.describe(match_id="Match ID")      
        @app_commands.describe(result="Result (cancel/crew/imp)")
        async def change_match(ctx: Context, match_id: int, result: str):
            if self.staff_role not in [role.id for role in ctx.author.roles]:
                await ctx.send("You don't have permission to use this command.")
                return

            if match_id is None:
                await ctx.send("Please specify a valid match ID.")
                return

            if result is None or result.lower() not in ['cancel', 'crew', 'imp']:
                await ctx.send("Please specify a valid result: 'cancel', 'crew', or 'imp'.")
                return

            match_info = self.file_handler.match_info_by_id(match_id)
            if match_info is None:
                await ctx.send(f"Cannot find match with ID: {match_id}")
                return

            result_text = ""
            if result.startswith("cancel"):
                changed_match = self.file_handler.change_result_to_cancelled(match_id)
                result_text = "Cancelled"
            elif result.startswith("crew"):
                changed_match = self.file_handler.change_result_to_crew_win(match_id)
                result_text = "Crewmates Win"
            elif result.startswith("imp"):
                changed_match = self.file_handler.change_result_to_imp_win(match_id)
                result_text = "Impostors Win"

            if changed_match:
                mentions = ""
                for player in changed_match.players.players:
                    try:
                        member = self.guild.get_member(int(player.discord))
                        mentions += f"{member.mention} "
                    except:
                        self.logger.warning(f"Player {player.name} has a wrong discord ID {player.discord}")

                await ctx.send(f"Match {match_id} changed to {result_text}! {mentions}")
                await self.get_channel(self.cancels_channel).send(f"Member {ctx.author.display_name} changed match {match_id} to {result_text}! {mentions}")
            else:
                await ctx.send(f"Match {match_id} is already a {result_text}")


        @self.hybrid_command(name="m", description="Mute all players but yourself in a Voice Channel")
        async def m(ctx:Context):
            if self.management_role not in [role.id for role in ctx.author.roles]:
                await ctx.send("You don't have permission to use this command.")
                return
            member = ctx.author
            voice_state = member.voice  # Get the voice state of the member
            if voice_state is not None and voice_state.channel is not None:
                channel = voice_state.channel
                tasks = []
                for vc_member in channel.members:
                    if vc_member != member:
                        tasks.append(vc_member.edit(mute=True, deafen=False))
                await asyncio.gather(*tasks)


        @self.hybrid_command(name="um", description="Unmute all players but yourself in a Voice Channel")
        async def um(ctx:Context):
            if self.management_role not in [role.id for role in ctx.author.roles]:
                await ctx.send("You don't have permission to use this command.")
                return
            member = ctx.author
            voice_state = member.voice  # Get the voice state of the member
            if voice_state is not None and voice_state.channel is not None:
                channel = voice_state.channel
                tasks = []
                for vc_member in channel.members:
                    tasks.append(vc_member.edit(mute=False, deafen=False))
                await asyncio.gather(*tasks)


        @self.hybrid_command(name="automute", description="Toggle automute from the server side")
        @app_commands.describe(toggle="On/Off")  
        async def automute(ctx:Context, toggle : str):
            if self.staff_role not in [role.id for role in ctx.author.roles]:
                await ctx.channel.send("You don't have permission to turn off automute.")
                return
            
            if toggle.lower() == "on":
                await ctx.channel.send("Automute is turned ON from the server side!")
                self.logger.info("Automute has been turned ON")
                await self.get_channel(self.admin_logs_channel).send(f"{ctx.author.mention} turned Automute ON")

                self.auto_mute = True

            elif toggle.lower() == "off":
                await ctx.channel.send("Automute is turned OFF from the server side!")
                self.logger.info("Automute has been turned OFF")
                await self.get_channel(self.admin_logs_channel).send(f"{ctx.author.mention} turned Automute OFF")
                self.auto_mute = False

            else:
                await ctx.channel.send("Please use !automute On or !automute Off to toggle serve-side automute")
                

        @self.hybrid_command(name="rules", description="Displays the rules for calculating MMR in this bot")
        async def rules(ctx:Context):
            embed = discord.Embed(title="Among Us Game Info", color=discord.Color.blurple())
            embed.add_field(name="Impostors", value="""
        If the impostor is **ejected** on **8, 9, 10** __THEN__ they will **lose 15%** performance.
        The other impostor who is a **solo** impostor will **gain 15%** performance.
        If an impostor got a crewmate __voted out__ in a meeting they will **gain 10%** for every crewmate voted out.
        For every kill you do as a **solo** impostor, you will **gain 7%** performance.
        If you win as a solo Impostor, you will **gain 20%** performance.
        """, inline=False)
            embed.add_field(name="Crewmates", value="""
        If the crewmate voted wrong on **__crit__(3, 4) players alive** or **(5, 6, 7) players alive with 2 imps** __THEN__ they will **LOSE 30%** performance.
        If the crewmate votes out an impostor they will **gain 10%** performance.
        If the crewmate votes correct on crit but loses then they will **gain 20%** performance.
        """, inline=False)
            embed.add_field(name="Winning Percentage", value="The percentage of winning is calculated by a logaritmic regression machine learning module trained on pre-season data.",inline=False)
            embed.add_field(name="MMR Gained", value="Your MMR gain will be your team's winning percentage * your performance * K(32)",inline=False)
            embed.set_footer(text=f"Bot Programmed by Aiden | Version: {self.version}", icon_url=self.user.avatar.url)
            await ctx.send(embed=embed)
            self.logger.info(f'Sent game info to Channel {ctx.channel}')


        @self.hybrid_command(name="match_info", description="Display match details of all the players in match")
        @app_commands.describe(match_id="Match ID")
        async def match_info(ctx:Context, match_id : int):
            if match_id == None: 
                return
            match_file = self.file_handler.find_matchfile_by_id(int(match_id))
            match = self.file_handler.match_from_file(match_file)
            if not (match.result == "Canceled" or match.result == "Unknown"):
                self.file_handler.calculate_mmr_gain_loss(match)
            await ctx.send(f"`{match.match_details()}`")
            self.logger.info(f"{ctx.author.display_name} Recieved Match {int(match_id)} Info")
        
        
        @self.hybrid_command(name="mmr_change", description="Change MMR of a Player")
        @app_commands.describe(player="Player name or @player")
        @app_commands.describe(value="Value to add/subtract (-10/10)")
        @app_commands.describe(change_type="Crew/Imp/None")
        async def mmr_change(ctx: Context, player: str, value: float, change_type: Optional[str] = None, reason : str = None):
            if self.staff_role not in [role.id for role in ctx.author.roles]:
                await ctx.send("You don't have permission to change a player's MMR.")
                return

            if not player or value is None:
                await ctx.send("Please provide a player name and the value argument.")
                return

            change_type = change_type.lower() if change_type else None
            if change_type and not change_type.startswith(("crew", "imp")):
                await ctx.send("Invalid change_type. It must start with 'crew', 'imp', or None.")
                return
            
            if player.startswith('<@'):  # unlinking a mention
                discord_id = int(player[2:-1])
                player_row = self.leaderboard.get_player_by_discord(discord_id)
            else:
                player_row = self.leaderboard.get_player_row(player)

            if player_row is None:
                await ctx.send(f"Player {player} not found.")
                return

            try:
                mmr_change_value = float(value)
            except ValueError:
                await ctx.send("Please input a correct MMR change value.")
                return

            mmr_change_text = ""
            if change_type and change_type.startswith("crew"):
                self.file_handler.leaderboard.mmr_change_crew(player_row, mmr_change_value)
                mmr_change_text = "Crew "
            elif change_type and change_type.startswith("imp"):
                self.file_handler.leaderboard.mmr_change_imp(player_row, mmr_change_value)
                mmr_change_text = "Impostor "
            else:
                self.file_handler.leaderboard.mmr_change(player_row, mmr_change_value)

            if mmr_change_value > 0:
                await ctx.send(f"Added {mmr_change_value} {mmr_change_text} MMR to Player {player}")
                await self.get_channel(self.admin_logs_channel).send(f"{ctx.author.mention} Added {mmr_change_value} {mmr_change_text}MMR to Player {player} because {reason}")
            elif mmr_change_value < 0:
                await ctx.send(f"Subtracted {-mmr_change_value} {mmr_change_text} MMR from Player {player}")
                await self.get_channel(self.admin_logs_channel).send(f"{ctx.author.mention} Subtracted {mmr_change_value} {mmr_change_text}MMR to Player {player} because {reason}")


        @self.hybrid_command(name="help", description="Display help for using the bot")
        async def help(ctx:Context):
            embed = discord.Embed(title="Among Us Bot Commands", color=discord.Color.gold())
            embed.add_field(name="**stats** [none/player/@mention]", value="Display stats of a player.", inline=False)
            embed.add_field(name="**lb** [none/number]", value="Display the leaderboard for top Players.", inline=False)
            embed.add_field(name="**lb imp** [none/number]", value="Display the leaderboard for top Impostors.", inline=False)
            embed.add_field(name="**lb crew** [none/number]", value="Display the leaderboardfor top Crewmates.", inline=False)
            embed.add_field(name="**graph_mmr** [none/player/@mention]", value="Display MMR Graph of a player.", inline=False)
            embed.add_field(name="**match_info** [match_id]", value="Display match info from the given ID", inline=False)
            embed.add_field(name="**rules**", value="Explains how the bot calculates MMR", inline=False)
            embed.add_field(name="**mmr_change** [player/@mention] [value] [Crew/Imp/None]", value="add or subtract mmr from the player", inline=False)
            embed.add_field(name="**name_change** [old_name]**__,__** [new_name]", value="change a player name(COMMA SEPERATOR , )", inline=False)
            embed.add_field(name="**automute** [on/off]", value="Turn on/off server-side automute.", inline=False)
            embed.add_field(name="**link** [player] [none/@mention]", value="Link a Discord user to a player name.", inline=False)
            embed.add_field(name="**unlink** [player/@mention]", value="Unlink a Discord user from a player name.", inline=False)
            embed.add_field(name="**change_match** [match_id] [cancel/crew/imp]", value="Change match result.", inline=False)
            embed.add_field(name="**m**", value="Mute everyone in your VC.", inline=False)
            embed.add_field(name="**um**", value="Unmute everyone in your VC.", inline=False)
            embed.set_footer(text=f"Bot Programmed by Aiden | Version: {self.version}", icon_url=self.user.avatar.url)
            await ctx.send(embed=embed)
            self.logger.info(f'Sent help command to Channel {ctx.channel}')


        @self.hybrid_command(name="name_change", description="Change the name of a player in all matches and leaderboard")
        @app_commands.describe(old_name="Player old name")
        @app_commands.describe(new_name="Player new name")
        async def name_change(ctx: commands.Context, old_name : str, new_name : str):
            if not any(role.id == self.staff_role for role in ctx.author.roles):
                await ctx.send("You don't have permission to change a player's name.")
                return
            self.file_handler.change_player_name(old_name, new_name)
            await ctx.send(f'Changed player name from "{old_name}" to "{new_name}"')
            await self.get_channel(self.admin_logs_channel).send(f'Changed player name from "{old_name}" to "{new_name}"')


        @self.hybrid_command(name="rank_block", description="Rank block a player for a duration of time")
        @app_commands.describe(player="@Player")
        @app_commands.describe(duration="Duration [30m/12h/5d..]")
        @app_commands.describe(reason="Reason for the rankblock")
        async def rank_block(ctx: commands.Context, player : str, duration : str, reason : str):
            if not any(role.id == self.staff_role for role in ctx.author.roles):
                await ctx.send("You don't have permission to rankblock a player")
                return
            await ctx.send(f"$temprole c {player} {duration} -<@&1129417731779858592> +<@&1199465496924393502>")
            await ctx.send(f"Player {player} was rankblocked for {duration} because {reason}")



        # @self.command()
        # async def test(ctx: Context, num):
        #     if self.staff_role not in [role.id for role in ctx.author.roles]:
        #         return
        #     json_end = '{"EventName":"GameEnd","MatchID":1780,"GameCode":"ZBQSDY","Players":["Aiden","zurg","real matt","Mantis","Sai","MaxKayn","Irish","Trav","xer","Nutty"],"PlayerColors":[6,14,0,15,12,10,7,2,4,9],"DeadPlayers":["Aiden","zurg","Mantis","Sai","MaxKayn","Irish","Trav","xer"],"Impostors":["zurg","real matt"],"Crewmates":["Aiden","Mantis","Sai","MaxKayn","Irish","Trav","xer","Nutty"],"Result":3}'
        #     json_data = json.loads(json_end)
        #     player_colors = json_data.get("PlayerColors")
        #     match = self.file_handler.process_match_by_id(num)
        #     match.players.set_player_colors_in_match(player_colors)
        #     self.file_handler.calculate_mmr_gain_loss(match)
        #     end_embed = self.end_game_embed(json_data, match)
        #     events_embed = self.events_embed(match)
        #     view = VotesView(embed=events_embed)
        #     await ctx.send(embed=end_embed, view=view)
       

    def add_events(self):
        @self.event
        async def on_ready():
            self.logger.info(f'{self.user} has connected to Discord!')
            self.guild = self.get_guild(self.guild_id)
            await self.get_members_in_channel()
            await self.update_leaderboard_discords()
            await self.tree.sync()
            
            self.logger.info(f'Ranked Among Us Bot has started!')
        

        @self.event
        async def on_voice_state_update(member, before, after):
            voice_channel_ids = [channel['voice_channel_id'] for channel in self.channels.values()]
            if (before.channel != after.channel) and \
                    ((before.channel and before.channel.id in voice_channel_ids) or (after.channel and after.channel.id in voice_channel_ids)):
                for channel in self.channels.values():
                    if before.channel and before.channel.id == channel['voice_channel_id']:
                        if member in channel['members']:
                            channel['members'].remove(member)
                            self.logger.info(f'{member.display_name} left {before.channel.name}')
                    elif after.channel and after.channel.id == channel['voice_channel_id']:
                        if member not in channel['members']:
                            channel['members'].append(member)
                            self.logger.info(f'{member.display_name} joined {after.channel.name}')
    

    async def get_members_in_channel(self):
        for channel in self.channels.values():
            voice_channel = self.get_channel(channel['voice_channel_id'])
            if voice_channel:
                members = voice_channel.members
                channel['members'] = [member for member in members]


    async def update_leaderboard_discords(self):
        players_to_remove = []
        for index, player_row in self.leaderboard.leaderboard.iterrows():
            player_name = player_row['Player Name']
            discord_id = player_row['Player Discord']
            if pd.notnull(discord_id):
                try:
                    discord_id = int(discord_id)
                    member = self.guild.get_member(discord_id)
                    if member is None and discord_id !=0:
                        players_to_remove.append(player_name)
                except Exception as e:
                    self.logger.error(f"Encountered exception {e}, {type(discord_id)}, {discord_id}")

        for player_name in players_to_remove:
            player_row = self.leaderboard.get_player_row(player_name)
            self.logger.info(f"Removing player {player_name} discord {player_row['Player Discord']} (wrong discord)")
            self.leaderboard.delete_player_discord(player_name)

        if players_to_remove:
            self.logger.info(f"Removed Discord IDs for players not found in the guild: {', '.join(players_to_remove)}")
        else:
            self.logger.info("All Discord IDs in the leaderboard are valid.")

        for member in self.guild.members:
            player_name = member.display_name
            player_row = self.leaderboard.get_player_row(player_name)
            if player_row is not None:  # Check if Discord ID is empty
                if self.leaderboard.get_player_discord(player_row) is None:
                    self.leaderboard.add_player_discord(player_name, member.id)
                    self.logger.info(f"Added {member.display_name} to {player_name} in leaderboard")

        players_with_empty_discord = self.leaderboard.players_with_empty_discord()

        for _, player_row in players_with_empty_discord.iterrows():
            player_name = player_row['Player Name']
            best_match = None
            best_score = 0
            for member in self.guild.members:
                member_display_name = member.display_name.lower().replace(" ","")
                player_name_normalized = player_name.lower().replace(" ","")
                match_score = fuzz.token_sort_ratio(player_name_normalized, member_display_name)
                if match_score > best_score and match_score >= 80:
                    best_match = member
                    best_score = match_score
            if best_match:
                discord_id = best_match.id
                self.leaderboard.add_player_discord(player_name, discord_id)
                self.logger.info(f"Added {best_match.display_name} to {player_name} in leaderboard (#2)")
            else:
                self.logger.warning(f"Can't find a discord match for player {player_name} in {self.guild.name}")
        self.leaderboard.save_leaderboard()


    def start_game_embed(self, json_data) -> discord.Embed:
        players = json_data.get("Players", [])
        player_colors = json_data.get("PlayerColors", [])
        match_id = json_data.get("MatchID", "")
        game_code = json_data["GameCode"] 
        self.logger.info(f'Creating an embed for game start MatchId={match_id}')
        
        embed = discord.Embed(title=f"Ranked Match Started", description=f"Match ID: {match_id} - Code: {game_code}\n Players:", color=discord.Color.dark_purple())

        for player_name, player_color in zip(players, player_colors): 
            player_row = self.leaderboard.get_player_row(player_name)
            player_discord_id = self.leaderboard.get_player_discord(player_row)
            color_emoji = default_color_emojis.get(player_color, ":question:")
            value = color_emoji
            try:
                player_discord = self.guild.get_member(int(player_discord_id))
                value += f" {player_discord.mention}"
            except:
                value += f" @{player_name}"
            player_mmr = self.leaderboard.get_player_mmr(player_row)
            value += "\nMMR: " + f" {player_mmr if player_mmr else 'New Player'}"
            embed.add_field(name=player_name, value=value, inline=True)
        
        current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S %Z')
        embed.set_image(url='https://www.essentiallysports.com/stories/the-best-among-us-mods-news-esports-sheriff-doctor-minecraft/assets/24.jpeg')
        embed.set_thumbnail(url=self.guild.icon.url)
        embed.set_footer(text=f"Match Started: {current_time} - Bot Programmed by Aiden", icon_url=self.guild.icon.url)
        return embed


    def end_game_embed(self, json_data, match: Match) -> discord.Embed:

        player_colors = json_data.get("PlayerColors", [])
        game_code = json_data["GameCode"]
        match.players.set_player_colors_in_match(player_colors)
        self.logger.info(f'Creating an embed for game End MatchId={match.id}')


        if match.result.lower() == "impostors win":
            embed_color = discord.Color.red()
        elif match.result.lower() == "canceled":
            embed_color = discord.Color.orange()
        else:
            embed_color = discord.Color.green()
        embed = discord.Embed(title=f"Ranked Match Ended - {match.result}", 
                      description=f"Match ID: {match.id} Code: {game_code}\nPlayers:", color=embed_color)
        
        members_discord = [(member.display_name.lower().strip(), member) for member in self.guild.members]

        for player in match.players.players:
            if player.discord == 0: 
                best_match = None
                best_match, score = process.extractOne(player.name.lower().strip(), [member_name for member_name, _ in members_discord])
                if score > self.ratio:  # Adjust the threshold score as needed
                    player.discord = next(member_id for member_name, member_id in members_discord if member_name == best_match)

        for player in match.players.get_players_by_team("impostor"):
            self.logger.info(f"processing impostor:{player.name}")
            value = "" 
            color_emoji = default_color_emojis.get(player.color, ":question:")
            
            value = color_emoji
            try:
                player_in_discord = self.guild.get_member(int(player.discord))
                value += f" {player_in_discord.mention}"
            except:
                self.logger.error(f"Can't find discord for player {player.name}, please link")
            value += "\nMMR: " + f" {round(player.current_mmr, 1) if player.current_mmr else 'New Player'}"
            value += f"\nImp MMR: {'+' if player.impostor_mmr_gain >= 0 else ''}{round(player.impostor_mmr_gain, 1)}"
            embed.add_field(name=f"{player.name} __**(Imp)**__", value=value, inline=True)

        embed.add_field(name=f"Imp Win rate: {round(match.players.impostor_win_rate*100,2)}%\nCrew Win Rate: {round(match.players.crewmate_win_rate*100,2)}%", value=" ", inline=True) 

        for player in match.players.get_players_by_team("crewmate"):
            value = "" 
            self.logger.info(f"processing crewmate:{player.name}")
            color_emoji = default_color_emojis.get(player.color, ":question:")
            value = color_emoji
            try:
                player_in_discord = self.guild.get_member(int(player.discord))
                value += f" {player_in_discord.mention}"
            except:
                self.logger.error(f"Can't find discord for player {player.name}, please link")
            value += "\nMMR: " + f" {round(player.current_mmr, 1) if player.current_mmr else 'New Player'}"
            value += f"\nCrew MMR: {'+' if player.crewmate_mmr_gain >= 0 else ''}{round(player.crewmate_mmr_gain, 1)}"
            value += f"\nTasks: {player.tasks}/10"
            embed.add_field(name=f"{player.name}", value=value, inline=True)

        current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S %Z')
        if match.result == "Impostors Win":
            embed.set_image(url="https://i.ibb.co/SwMNJPY/New-Imposters-Win-Image.jpg")
        elif match.result in ["Crewmates Win", "HumansByVote"]:
            embed.set_image(url="https://i.ibb.co/NSWZCRJ/New-among-us-Victory.jpg")
        else:
            embed.set_image(url="https://i.ibb.co/SXs9Rwr/New-among-us-Cancel.png")
            
        embed.set_thumbnail(url=self.guild.icon.url)
        embed.set_footer(text=f"Match Started: {current_time} - Bot Programmed by Aiden", icon_url=self.guild.icon.url)
        return embed  


    def events_embed(self, match) -> discord.Embed:
        for player in match.players.players:
            player.tasks = 0
            if player.team == "impostor": 
                player.color +=100
        votes_embed = discord.Embed(title=f"Match ID: {match.id} - Events", description="")
        events_df = pd.read_json(os.path.join(self.matches_path, match.event_file_name), typ='series')
        
        meeting_count = 0
        meeting_end = False
        meeting_start = False

        events_embed = f"__**Round {meeting_count+1} Actions**__\n"
        for event in events_df:
            event_type = event.get('Event')
            for key in ['Name', 'Player', 'Target', 'Killer']:
                if key in event:
                    if event[key].endswith(" |"):
                        event[key] = event[key][:-2] 
                
            if event_type == "Task":
                player = match.players.get_player_by_name(event.get('Name'))
                player.finished_task()
                if player.tasks == 10:
                    color_emoji = default_color_emojis.get(player.color, "?")
                    events_embed += f"{color_emoji} Tasks {done_emoji} {'Alive' if player.alive else 'Dead'}\n"

            elif event_type == "PlayerVote":
                player = match.players.get_player_by_name(event.get('Player'))
                target = match.players.get_player_by_name(event.get('Target'))
                player_emoji = default_color_emojis.get(player.color, "?")
                if target == None:
                    events_embed += f" {player_emoji} Skipped\n"
                else:
                    target_emoji = default_color_emojis.get(target.color, "?")
                    events_embed += f" {player_emoji} voted {target_emoji}\n"
                    
            elif event_type == "Death":
                player = match.players.get_player_by_name(event.get('Name'))
                killer = match.players.get_player_by_name(event.get('Killer'))
                player_emoji = default_color_emojis.get(player.color+200, "?")
                killer_emoji = default_color_emojis.get(killer.color, "?")
                events_embed += f" {killer_emoji} {kill_emoji} {player_emoji}\n"
                
            elif event_type == "BodyReport":
                player = match.players.get_player_by_name(event.get('Player'))
                dead_player = match.players.get_player_by_name(event.get('DeadPlayer'))
                player_emoji = default_color_emojis.get(player.color, "?")
                dead_emoji = default_color_emojis.get(dead_player.color+200, "?")
                events_embed += f" {player_emoji} {report_emoji} {dead_emoji}\n"
                meeting_start = True
                meeting_count+=1
                
            elif event_type == "MeetingStart":
                player = match.players.get_player_by_name(event.get('Player'))
                player_emoji = default_color_emojis.get(player.color, "?")
                events_embed += f" {player_emoji} {emergency_emoji} Meeting\n"
                meeting_start = True
                meeting_count+=1
                
            elif event_type == "Exiled":
                ejected_player = match.players.get_player_by_name(event.get('Player'))
                ejected_emoji = default_color_emojis.get(ejected_player.color, "?")
                events_embed += f"{ejected_emoji} __was **Ejected**__\n"
                meeting_end = True
                events_embed += f"Meeting End\n"
            
            elif event_type == "GameCancel":
                events_embed += f"__**Game {match.id} Canceled**__\n"
                
          
            elif event_type == "ManualGameEnd":
                events_embed += f"__**Manual End**__\n"
                break

            elif event_type == "Disconnect":
                disconnected_player = match.players.get_player_by_name(event.get('Name'))
                disconnected_emoji = default_color_emojis.get(disconnected_player.color, "?")
                events_embed += f"{disconnected_emoji}{'__** Disconnected Alive**__' if disconnected_player.alive else 'Disconnected Dead'}\n"
                
            elif event_type == "MeetingEnd":
                if (event.get("Result") == "Exiled"):
                    continue

                elif (event.get("Result") == "Tie"):
                    events_embed += f"__**Votes Tied**__\n"
                else:
                    events_embed += f"__**Skipped**__\n"
                meeting_end = True
                events_embed += f"Meeting End\n"

            if meeting_end == True:
                if len(events_embed) >= 1023:
                    self.logger.error(events_embed)
                votes_embed.add_field(name = "", value=events_embed, inline=True)
                events_embed = ""
                events_embed += f"__**Round {meeting_count+1} Actions**__\n"
                meeting_end = False 

            elif meeting_start == True:
                events_embed += f"__Meeting #{meeting_count}__\n"
                meeting_start = False

        
        events_embed += f"**Match {match.id} Ended**\n"
        events_embed += f"**{match.result}**"
        votes_embed.add_field(name = "", value=events_embed, inline=True)
        votes_embed.set_footer(text=f"Bot Programmed by Aiden | Version: {self.version}", icon_url=self.guild.icon.url)
        return votes_embed


    def find_most_matched_channel(self, json_data):
        players = json_data.get("Players", [])
        max_matches = 0
        most_matched_channel_name = None
        players = {player.lower().strip() for player in players} #normalize
        
        for channel_name, channel_data in self.channels.items():
            channel_members = channel_data['members']
            matches = 0
            for player in players:
                for member in channel_members:
                    # Compare cropped strings of player name and member display name
                    cropped_player_name = player[:min(len(player), len(member.display_name))]
                    cropped_member_name = member.display_name.lower().strip()[:min(len(player), len(member.display_name))]
                    similarity_ratio = fuzz.ratio(cropped_player_name, cropped_member_name)
                    if similarity_ratio >= self.ratio:  # Adjust threshold as needed
                        matches += 1
                        break  # Exit inner loop once a match is found
            if matches > max_matches:
                max_matches = matches
                most_matched_channel_name = channel_name
            if matches >= 4:
                return self.channels.get(most_matched_channel_name)
        return self.channels.get(most_matched_channel_name)


    async def add_players_discords(self, json_data, game_channel):
        players = json_data.get("Players", [])
        match_id = json_data.get("MatchID", "")
        self.logger.info(f'Adding discords from match={match_id} to the leaderboard if missing and creating new players')
        members_started_the_game = game_channel['members_in_match']

        for member in members_started_the_game:
            best_match = None
            best_similarity_ratio = 0
            for player in players:
                cropped_player_name = player.lower().strip()[:min(len(player), len(member.display_name.strip()))]
                cropped_member_name = member.display_name.lower().strip()[:min(len(player), len(member.display_name.strip()))]
                similarity_ratio = fuzz.ratio(cropped_player_name, cropped_member_name)
                if similarity_ratio >= self.ratio and similarity_ratio > best_similarity_ratio:
                    best_similarity_ratio = similarity_ratio
                    best_match = (player, member)
            if best_match is not None:
                self.logger.info(f"found {best_match[1].display_name}")
                player_name, member = best_match
                player_row = self.leaderboard.get_player_row(player_name)

                if player_row is None:
                    self.logger.info(f"Player {player_name} was not found in the leaderboard, creating a new player")
                    self.leaderboard.new_player(player_name)
                    self.leaderboard.add_player_discord(player_name, member.id)
                    self.leaderboard.save_leaderboard()

                if self.leaderboard.get_player_discord(player_row) is None:
                    self.logger.info(f"Player {player_name} has no discord in the leaderboard, adding discord {member.id}")
                    self.leaderboard.add_player_discord(player_name, member.id)
                    self.leaderboard.save_leaderboard()
            else:
                self.logger.error(f"Can't find a match a player for member {member.display_name}")


    async def handle_game_start(self, json_data):
        match_id = json_data.get("MatchID", "")
        game_code = json_data.get("GameCode", "")
        players = set(json_data.get("Players", []))
        game = {"GameCode":game_code, "MatchID": match_id, "Players": players}
        self.games_in_progress.append(game)
        self.logger.info(f"Game {game} added to games in progress.")
        game_channel = self.find_most_matched_channel(json_data)
        if game_channel:
            game_channel['members_in_match'] = game_channel.get('members')
            if self.auto_mute:
                await self.game_start_automute(game_channel)
            text_channel_id = game_channel['text_channel_id']
            await self.add_players_discords(json_data, game_channel)
            embed = self.start_game_embed(json_data)
            text_channel = self.get_channel(text_channel_id)
            if text_channel:
                await text_channel.send(embed=embed)
            else:
                self.logger.error(f"Text channel with ID {text_channel_id} not found.")
        else:
            self.logger.error(f"Could not find a matching game channel to the game not found.")


    async def game_start_automute(self, game_channel):
        voice_channel_id = game_channel['voice_channel_id']
        voice_channel = self.get_channel(voice_channel_id)
        if voice_channel is not None:
            tasks = []
            for member in voice_channel.members:
                tasks.append(member.edit(mute=True, deafen=True))
                self.logger.info(f"Deafened and Muted {member.display_name}")
            try:
                await asyncio.gather(*tasks)  # undeafen all players concurrently
            except:
                self.logger.warning("Some players left the VC on Game Start")
        else:
            self.logger.error(f"Voice channel with ID {voice_channel_id} not found.")


    async def handle_meeting_start(self, json_data):
        players = set(json_data.get("Players", []))
        dead_players = set(json_data.get("DeadPlayers", []))
        alive_players = players - dead_players
        dead_players_normalized = {player.lower().replace(" ", "") for player in dead_players}
        alive_players_normalized = {player.lower().replace(" ", "") for player in alive_players}
        tasks = []
            
        game_channel = self.find_most_matched_channel(json_data)
        if game_channel:
            voice_channel_id = game_channel.get('voice_channel_id')
            text_channel_id = game_channel.get('text_channel_id')
            voice_channel = self.get_channel(voice_channel_id)
            text_channel = self.get_channel(text_channel_id)

            if voice_channel is not None:
                members_in_vc = {(member_in_vc.display_name.lower().replace(" ", ""), member_in_vc) for member_in_vc in voice_channel.members}
                remaining_members = []
                for element in members_in_vc:
                    match_found = False
                    display_name, member = element

                    best_match = difflib.get_close_matches(display_name, dead_players_normalized, cutoff=1.0)
                    if len(best_match) == 1:
                        tasks.append(member.edit(mute=True, deafen=False))
                        dead_players_normalized.remove(best_match[0])
                        self.logger.info(f"undeafened and muted {member.display_name}")
                        match_found = True 
                        continue

                    best_match = difflib.get_close_matches(display_name, alive_players_normalized, cutoff=1.0)
                    if len(best_match) == 1:
                        tasks.append(member.edit(mute=False, deafen=False))
                        alive_players_normalized.remove(best_match[0])
                        self.logger.info(f"undeafened and unmuted {member.display_name}")
                        match_found = True 

                    if not match_found:
                        remaining_members.append(element)

                remaining_members_final = []
                for element in remaining_members:
                    display_name, member = element
                    match_found = False

                    best_match = difflib.get_close_matches(display_name, dead_players_normalized, cutoff=0.9)
                    if len(best_match) == 1:
                        tasks.append(member.edit(mute=True, deafen=False))
                        dead_players_normalized.remove(best_match[0])
                        self.logger.info(f"deafened and unmuted {member.display_name}")
                        match_found = True
                    
                    best_match = difflib.get_close_matches(display_name, alive_players_normalized, cutoff=0.9)
                    if len(best_match) == 1:
                        tasks.append(member.edit(mute=False, deafen=False))
                        alive_players_normalized.remove(best_match[0])
                        self.logger.info(f"undeafened and unmuted {member.display_name}")
                        match_found = True

                    if not match_found:
                        remaining_members_final.append(element)

                for element in remaining_members_final:
                    display_name, member = element
                    match_found = False
                    best_match = difflib.get_close_matches(display_name, dead_players_normalized, cutoff=0.75)
                    if len(best_match) == 1:
                        tasks.append(member.edit(mute=True, deafen=False))
                        dead_players_normalized.remove(best_match[0])
                        self.logger.info(f"undeafened and muted {member.display_name}")
                        match_found = True
                    
                    best_match = difflib.get_close_matches(display_name, alive_players_normalized, cutoff=0.75)
                    if len(best_match) == 1:
                        tasks.append(member.edit(mute=False, deafen=False))
                        alive_players_normalized.remove(best_match[0])
                        self.logger.info(f"undeafened and unmuted {member.display_name}")
                        match_found = True

                    if not match_found:
                        self.logger.error(f"Could not perform automute on {member.display_name}")
                        await text_channel.send(f"Could not perform automute on{member.display_name}")
                try: 
                    await asyncio.gather(*tasks)
                except:
                    self.logger.warning("Some players left the VC on Meeting Start")
            else:
                self.logger.error(f"Voice channel with ID {voice_channel_id} not found.")
        else:
            self.logger.error("No suitable game channel found for the players.")


    async def handle_meeting_end(self, json_data):
        players = set(json_data.get("Players", []))
        impostors = set(json_data.get("Impostors", []))
        dead_players = set(json_data.get("DeadPlayers", []))
        alive_players = players - dead_players
        dead_players_normalized = {player.lower().replace(" ", "") for player in dead_players}
        alive_players_normalized = {player.lower().replace(" ", "") for player in alive_players}
        game_channel = self.find_most_matched_channel(json_data)
        game_ended = impostors.issubset(dead_players)
        if game_ended:
            self.logger.info(f"Skipping MeetingEnd Automute because all impostors are dead.")
            return
        if game_channel:
            voice_channel_id = game_channel.get('voice_channel_id')
            text_channel_id = game_channel.get('text_channel_id')
            voice_channel = self.get_channel(voice_channel_id)
            text_channel = self.get_channel(text_channel_id)

            if voice_channel is not None:
                members_in_vc = {(member_in_vc.display_name.lower().replace(" ", ""), member_in_vc) for member_in_vc in voice_channel.members}
                remaining_members = []
                tasks = []
                for element in members_in_vc:
                    match_found = False
                    display_name, member = element

                    best_match = difflib.get_close_matches(display_name, dead_players_normalized, cutoff=1.0)
                    if len(best_match) == 1:
                        self.logger.info(f"undeafened and unmuted {member.display_name}")
                        tasks.append(member.edit(mute=False, deafen=False))
                        dead_players_normalized.remove(best_match[0])
                        match_found = True

                    best_match = difflib.get_close_matches(display_name, alive_players_normalized, cutoff=1.0)
                    if len(best_match) == 1:
                        tasks.append(member.edit(mute=True, deafen=True))
                        alive_players_normalized.remove(best_match[0])
                        self.logger.info(f"deafened and muted {member.display_name}")
                        match_found = True

                    if not match_found:
                        remaining_members.append(element)

                remaining_members_final = []
                for element in remaining_members:
                    display_name, member = element
                    match_found = False

                    best_match = difflib.get_close_matches(display_name, dead_players_normalized, cutoff=0.9)
                    if len(best_match) == 1:
                        tasks.append(member.edit(mute=False, deafen=False))
                        dead_players_normalized.remove(best_match[0])
                        self.logger.info(f"undeafened and unmuted {member.display_name}")
                        match_found = True
                    
                    best_match = difflib.get_close_matches(display_name, alive_players_normalized, cutoff=0.9)
                    if len(best_match) == 1:
                        tasks.append(member.edit(mute=True, deafen=True))
                        alive_players_normalized.remove(best_match[0])
                        self.logger.info(f"deafened and muted {member.display_name}")
                        match_found = True

                    if not match_found:
                        remaining_members_final.append(element)
                        
                for element in remaining_members_final:
                    display_name, member = element
                    match_found = False
                    best_match = difflib.get_close_matches(display_name, dead_players_normalized, cutoff=0.75)
                    if len(best_match) == 1:
                        tasks.append(member.edit(mute=False, deafen=False))
                        dead_players_normalized.remove(best_match[0])
                        self.logger.info(f"undeafened and muted {member.display_name}")
                        match_found = True
                    
                    best_match = difflib.get_close_matches(display_name, alive_players_normalized, cutoff=0.75)
                    if len(best_match) == 1:
                        tasks.append(member.edit(mute=True, deafen=True))
                        alive_players_normalized.remove(best_match[0])
                        self.logger.info(f"deafened and muted {member.display_name}")
                        match_found = True

                    if not match_found:
                        self.logger.error(f"Could not perform automute on {member.display_name}")
                        await text_channel.send(f"Could not perform automute on {member.display_name}")

                await asyncio.sleep(6) 
                try:
                    await asyncio.gather(*tasks)
                except:
                    self.logger.warning("Some players left the VC on Meeting End")
            else:
                self.logger.error(f"Voice channel with ID {voice_channel_id} not found.")
        else:
            self.logger.error(f"Could not find a matching game channel to the game not found.")


    async def game_end_automute(self, voice_channel, voice_channel_id):
        if voice_channel is not None:
            tasks = []
            for member in voice_channel.members:
                tasks.append(member.edit(mute=False, deafen=False))
            try:
                await asyncio.gather(*tasks)  # undeafen all players concurrently
            except:
                self.logger.warning("Some players left the VC on Game End")
        else:
            self.logger.error(f"Voice channel with ID {voice_channel_id} not found.")


    async def change_player_roles(self, members):
        ranked_roles = [role for role in self.guild.roles if role.name.startswith("Ranked |")]
        role_ranges = {
            "Iron": (None, 850),
            "Bronze": (851, 950),
            "Silver": (951, 1050),
            "Gold": (1051, 1150),
            "Platinum": (1151, 1250),
            "Diamond": (1251, 1350),
            "Master": (1351, 1450),
            "Warrior": (1451, None)
        }

        for member in members:
            player_row = self.leaderboard.get_player_by_discord(member.id)
            if player_row is not None:
                player_mmr = player_row['MMR']
                current_ranked_roles = [role for role in member.roles if role.name.startswith("Ranked |")]

                # Check if member already has a ranked role within the desired range
                for role in current_ranked_roles:
                    for rank, (lower, upper) in role_ranges.items():
                        if lower is None and player_mmr <= upper:
                            if f"Ranked | {rank}" == role.name:
                                break
                        elif upper is None and player_mmr >= lower:
                            if f"Ranked | {rank}" == role.name:
                                break
                        elif lower is not None and upper is not None and lower <= player_mmr <= upper:
                            if f"Ranked | {rank}" == role.name:
                                break
                    else:
                        continue  # No matching role found within the desired range
                    break  # Matching role found within the desired range, no action needed
                else:
                    # Determine the desired role based on MMR
                    desired_role_name = None
                    for rank, (lower, upper) in role_ranges.items():
                        if lower is None and player_mmr <= upper:
                            desired_role_name = f"Ranked | {rank}"
                            break
                        elif upper is None and player_mmr >= lower:
                            desired_role_name = f"Ranked | {rank}"
                            break
                        elif lower is not None and upper is not None and lower <= player_mmr <= upper:
                            desired_role_name = f"Ranked | {rank}"
                            break
                    else:
                        desired_role_name = None  # No matching role found

                    if desired_role_name:
                        desired_role = discord.utils.get(ranked_roles, name=desired_role_name)
                        if desired_role:
                            if desired_role not in current_ranked_roles:  # Check if member already has the desired role
                                self.logger.info(f"removed {current_ranked_roles} from {member.display_name}")
                                await member.remove_roles(*current_ranked_roles)
                                self.logger.info(f"added {desired_role} to {member.display_name}")
                                await member.add_roles(desired_role)


    async def handle_game_end(self, json_data):
        match_id = json_data.get("MatchID", "")
        game_code = json_data.get("GameCode", "")
        for game in self.games_in_progress:
            if game.get("GameCode") == game_code:
                match_id = game.get("MatchID")
                self.logger.info(f"Game {game} removed from games in progress.")
                self.games_in_progress.remove(game)

        game_channel = self.find_most_matched_channel(json_data)
        voice_channel_id = game_channel['voice_channel_id']
        text_channel_id = game_channel['text_channel_id']
        voice_channel = self.get_channel(voice_channel_id)
        if self.auto_mute:
            await self.game_end_automute(voice_channel, voice_channel_id)

        last_match = self.file_handler.process_match_by_id(match_id)
        for i in range(10):
            if last_match.result == "Unknown":
                await asyncio.sleep(1)
                last_match = self.file_handler.process_match_by_id(match_id)
                if i == 9:
                    self.logger.warning(f"Match {match_id} was not loaded correctly")
            else:
                break

        end_embed = self.end_game_embed(json_data, last_match)
        events_embed = self.events_embed(last_match)
        view = VotesView(embed=events_embed)

        await self.get_channel(text_channel_id).send(embed=end_embed, view=view)
        await self.get_channel(self.match_logs).send(embed=end_embed)

        await self.change_player_roles(game_channel['members_in_match'])

        game_channel['members_in_match'] = []
        

    async def handle_client(self, reader, writer):
        data = await reader.read(1024)
        message = data.decode('utf-8')
        self.logger.debug(f"Received: {message}") 

        try:
            json_data = json.loads(message)
            event_name = json_data.get("EventName")
            match_id = json_data.get("MatchID", "")
            game_code = json_data["GameCode"]

            if event_name == "GameStart":
                self.logger.info(f"Game ID:{match_id} Started. - Code({game_code})")
                await self.handle_game_start(json_data)

            elif event_name == "MeetingStart":
                self.logger.info(f"Game Code:{game_code} Meeting Started.")
                if self.auto_mute:
                    await self.handle_meeting_start(json_data) #this is automute

            elif event_name == "MeetingEnd":
                self.logger.info(f"Game Code:{game_code} Meeting Endded.")
                if self.auto_mute:
                    await self.handle_meeting_end(json_data) #this is automute

            elif event_name == "GameEnd":
                self.logger.info(f"Game ID:{match_id} Endded. - Code({game_code})")
                await self.handle_game_end(json_data)
                
            else:
                self.logger.info("Unsupported event:", event_name)

        except json.JSONDecodeError as e:
            self.logger.error("Error decoding JSON:", e)
        except Exception as e:
            self.logger.error("Error processing event:", e, message)
    
    
    async def start_server(self):
        server = await asyncio.start_server(self.handle_client, 'localhost', 5000)
        async with server:
            self.logger.info("Socket server is listening on localhost:5000...")
            await server.serve_forever()


    async def start_bot(self):
        await asyncio.gather(
            self.start_server(),
            super().start(self.token)
        )

class VotesView(discord.ui.View):
    def __init__(self, *, timeout=None, embed=None):
        super().__init__(timeout=timeout)
        self.embed = embed
    @discord.ui.button(label="Show Events", style=discord.ButtonStyle.blurple, custom_id="events_button")
    async def gray_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.data.get("custom_id") == "events_button": 
            await interaction.response.send_message(embed=self.embed, ephemeral=True)


if __name__ == "__main__":
    token = "/////"

    ranked_channels = {
        'ranked1': {'voice_channel_id': 1200119601627926629, 'text_channel_id': 1200120470616428545, 'members': [], 'members_in_match': [], 'lobby_code': ""},
        'ranked2': {'voice_channel_id': 1200119662680219658, 'text_channel_id': 1200120538341834782, 'members': [], 'members_in_match': [], 'lobby_code': ""},
        'ranked3': {'voice_channel_id': 1200119714920276168, 'text_channel_id': 1200120699264704533, 'members': [], 'members_in_match': [], 'lobby_code': ""},
        'ranked4': {'voice_channel_id': 1217501389366890576, 'text_channel_id': 1217951844156833854, 'members': [], 'members_in_match': [], 'lobby_code': ""},
        'rankedvip': {'voice_channel_id': 1232273109483130961, 'text_channel_id': 1232273701450285077, 'members': [], 'members_in_match': [], 'lobby_code': ""}
    }
    variables = {
        'ranked_channels' : ranked_channels,
        'guild_id' : 1116951598422315048,
        'match_logs_channel' : 1220864275581767681,
        'staff_role_id' : 1122822702990905354,
        'moderator_role_id' : 1199319511011180575, 
        'cancels_channel' : 1199323422631657512,
        'bot_commands_channel' : 1229050249159512179,
        'admin_logs_channel' : 1236981166461157417,
        'matches_path' : "~/impServer/plugins/MatchLogs/Preseason/",
        'database_location' : "leaderboard_preseason.csv",
        'season_name' : "Pre-Season"
    }
    bot = DiscordBot(token=token, variables=variables)

    # test_token = "///"
    # test_channels = {
    # 'ranked1': {'voice_channel_id': 1229151012221354076, 'text_channel_id': 1229150964213219430, 'members': [], 'members_in_match': []}
    # }
    # test_variables = {
    #     'ranked_channels' : test_channels,
    #     'guild_id' : 1229122991330426990,
    #     'match_logs_channel' : 1229808964137648239,
    #     'staff_role_id' : 1229221887918346321,
    #     'moderator_role_id' : 1229221887918346321, 
    #     'cancels_channel' : 1229808964137648239,
    #     'bot_commands_channel' : 1229830685175451688,
    #     'matches_path' : "~/Resistance/Preseason/",
    #     'database_location' : "leaderboard_full.csv",
    #     'season_name' : "Pre-Season"
    # }
    # bot = DiscordBot(token=test_token, variables=test_variables)
    asyncio.run(bot.start_bot())
