import discord
from discord.ext import commands
import asyncio
from discord import ui

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

LOG_CHANNEL_ID = 1377208637029744641
STAFF_ROLE_ID = 1376861623834247168
OWNER_ROLE_ID = 1368395196131442849
ticket_timers = {}

CATEGORY_NAMES = {
    "claims": "<a:Gift:1368420677648121876> Claims",
    "boosts": "<a:NitroBooster:1368420767577931836> Boosts",
    "premium": "<:upvote:1376850180644667462> Premium",
    "reseller": "<a:moneywings:1377119310761427014> Reseller"
}

@bot.event
async def on_ready():
    print(f"{bot.user} is ready!")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def setup_ticket(ctx):
    embed = discord.Embed(title="Support", description="Select a category to open a ticket.", color=0x9b59b6)
    view = ui.View()
    for custom_id, label in CATEGORY_NAMES.items():
        view.add_item(discord.ui.Button(label=label, custom_id=custom_id))
    await ctx.send(embed=embed, view=view)

@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component and interaction.data['custom_id'] in CATEGORY_NAMES:
        category_id = interaction.data['custom_id']
        category_label = CATEGORY_NAMES[category_id]
        guild = interaction.guild

        ticket_category = discord.utils.get(guild.categories, name="Tickets")
        if ticket_category is None:
            ticket_category = await guild.create_category("Tickets")

        existing = discord.utils.get(ticket_category.channels, name=f"{category_id}-{interaction.user.name}".lower())
        if existing:
            await interaction.response.send_message(f"You already have an open ticket in '{category_label}'.", ephemeral=True)
            return

        channel = await ticket_category.create_text_channel(f"{category_id}-{interaction.user.name}".lower())
        await channel.set_permissions(guild.default_role, read_messages=False, send_messages=False)
        await channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
        await channel.set_permissions(guild.get_role(OWNER_ROLE_ID), read_messages=True, send_messages=True)
        await channel.set_permissions(guild.get_role(STAFF_ROLE_ID), read_messages=True, send_messages=True)

        await channel.edit(topic=str(interaction.user.id))

        await channel.send(
            f"{interaction.user.mention} has opened a ticket. <@&{STAFF_ROLE_ID}>, please assist!

Please describe your issue in detail. Abusing the ticket system (alts/fake accounts) will result in a blacklist."
        )

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"📂 Ticket opened: {channel.mention} by {interaction.user.mention} (Category: {category_label})")

        await interaction.response.send_message(f"Your ticket has been created: {channel.mention}", ephemeral=True)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def ping(ctx):
    if ctx.channel.category and ctx.channel.category.name == "Tickets":
        try:
            user_id = int(ctx.channel.topic)
            user = await bot.fetch_user(user_id)
            await user.send(f"Hey {user.name}, please check your ticket in {ctx.channel.mention}!")
            await ctx.send(f"✅ DM sent to {user.mention}!", delete_after=5)
        except Exception:
            await ctx.send("❌ Could not DM the ticket creator. They may have DMs disabled.", delete_after=5)
    else:
        await ctx.send("This command can only be used in ticket channels.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def close(ctx):
    if ctx.channel.category and ctx.channel.category.name == "Tickets":
        class ConfirmView(ui.View):
            def __init__(self):
                super().__init__(timeout=30)

            @ui.button(label="Yes", style=discord.ButtonStyle.danger)
            async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.edit_message(content="Closing the ticket...", view=None)
                await asyncio.sleep(2)
                await ctx.channel.delete()
                log_channel = bot.get_channel(LOG_CHANNEL_ID)
                if log_channel:
                    await log_channel.send(f"✅ Ticket manually closed: {ctx.channel.name}")

            @ui.button(label="No", style=discord.ButtonStyle.secondary)
            async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.edit_message(content="Ticket close cancelled.", view=None)
                self.stop()

            @ui.button(label="Auto (30 sec)", style=discord.ButtonStyle.primary)
            async def auto(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.edit_message(content="Auto-close initiated. Ticket will close in 30 seconds.", view=None)
                await asyncio.sleep(30)
                try:
                    await ctx.channel.delete()
                    log_channel = bot.get_channel(LOG_CHANNEL_ID)
                    if log_channel:
                        await log_channel.send(f"✅ Ticket auto-closed: {ctx.channel.name}")
                except Exception:
                    pass

        view = ConfirmView()
        await ctx.send("Are you sure you want to close this ticket?", view=view)
    else:
        await ctx.send("This command can only be used in ticket channels.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def add(ctx, member: discord.Member):
    if ctx.channel.category and ctx.channel.category.name == "Tickets":
        await ctx.channel.set_permissions(member, read_messages=True, send_messages=True)
        await ctx.send(f"✅ {member.mention} has been added to this ticket.")
    else:
        await ctx.send("❌ This command can only be used in ticket channels.")

bot.run(os.getenv("YOUR_BOT_TOKEN"))
