import discord
from discord.ext import commands
import asyncio
import os

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

STAFF_ROLE_ID = 1376861623834247168
OWNER_ROLE_ID = 1368395196131442849
CATEGORY_ID = 1377221670837682261
LOG_CHANNEL_ID = 1377208637029744641
AUTO_CLOSE_TIME = 1800  # 30 minutes

@bot.event
async def on_ready():
    print(f"✅ Bot {bot.user} is ready!")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def setup(ctx):
    embed = discord.Embed(title="Support", description="Select a category below to open a ticket.\nTickets auto-close in 30 minutes if no reply.", color=0x9b59b6)
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Claims/Credits", emoji="<a:Gift:1368420677648121876>", custom_id="claims"))
    view.add_item(discord.ui.Button(label="Server Boosts", emoji="<a:NitroBooster:1368420767577931836>", custom_id="boosts"))
    view.add_item(discord.ui.Button(label="Premium Upgrades", emoji="<:upvote:1376850180644667462>", custom_id="premium"))
    view.add_item(discord.ui.Button(label="Reseller", emoji="<a:moneywings:1377119310761427014>", custom_id="reseller"))
    await ctx.send(embed=embed, view=view)

@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component and interaction.data.get("custom_id") in ["claims", "boosts", "premium", "reseller"]:
        category = interaction.data['custom_id']
        guild = interaction.guild
        user = interaction.user

        category_channel = guild.get_channel(CATEGORY_ID)
        if not category_channel:
            await interaction.response.send_message("❌ Ticket category not found. Please check the configuration.", ephemeral=True)
            return

        ticket_name = f"{category}-{user.name}"

        for channel in category_channel.text_channels:
            if channel.name.startswith(f"{category}-{user.name}"):
                await interaction.response.send_message(f"❌ You already have a ticket open: {channel.mention}", ephemeral=True)
                return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.get_role(OWNER_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        ticket_channel = await guild.create_text_channel(ticket_name, category=category_channel, overwrites=overwrites, topic=f"{user.id}")

        await ticket_channel.send(
            f"{user.mention} has opened a ticket. <@&{STAFF_ROLE_ID}>, please assist!\n\n"
            "📌 Please describe your issue or request.\n"
            "💸 Payment Methods:\n"
            "- <a:Gift:1368420677648121876> Cash App\n"
            "- <:upvote:1376850180644667462> Apple Pay\n"
            "- <a:NitroBooster:1368420767577931836> Zelle\n"
            "- <a:moneywings:1377119310761427014> Litecoin"
        )

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"✅ Ticket opened: {ticket_channel.mention} by {user.mention} (Category: {category})")

        await interaction.response.send_message(f"✅ Your ticket has been created: {ticket_channel.mention}", ephemeral=True)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def ping(ctx):
    if ctx.channel.topic:
        user_id = int(ctx.channel.topic)
        user = ctx.guild.get_member(user_id)
        if user:
            try:
                await user.send(f"👋 Hi {user.name}, please check your ticket for updates or questions from the staff.")
                await ctx.send("✅ DM sent to the ticket user.")
            except discord.Forbidden:
                await ctx.send("❌ Could not send a DM. Please make sure the user has DMs open.")
        else:
            await ctx.send("❌ Could not find the user who opened this ticket.")
    else:
        await ctx.send("❌ This channel is not a ticket.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def close(ctx):
    if ctx.channel.category_id == CATEGORY_ID:
        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30)
                self.auto_task = None

            @discord.ui.button(label="Yes", style=discord.ButtonStyle.danger)
            async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.auto_task and not self.auto_task.done():
                    self.auto_task.cancel()
                await interaction.response.edit_message(content="Closing the ticket...", view=None)
                await asyncio.sleep(2)
                await ctx.channel.delete()
                log_channel = bot.get_channel(LOG_CHANNEL_ID)
                if log_channel:
                    await log_channel.send(f"✅ Ticket manually closed: {ctx.channel.name}")

            @discord.ui.button(label="No", style=discord.ButtonStyle.secondary)
            async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.auto_task and not self.auto_task.done():
                    self.auto_task.cancel()
                await interaction.response.edit_message(content="Ticket close cancelled.", view=None)
                self.stop()

            @discord.ui.button(label="Auto (30 sec)", style=discord.ButtonStyle.primary)
            async def auto(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.edit_message(content="Auto-close initiated. Ticket will close in 30 seconds.", view=None)
                self.auto_task = asyncio.create_task(self.auto_close(ctx.channel))

            async def auto_close(self, channel):
                await asyncio.sleep(30)
                try:
                    await channel.delete()
                    log_channel = bot.get_channel(LOG_CHANNEL_ID)
                    if log_channel:
                        await log_channel.send(f"✅ Ticket auto-closed: {channel.name}")
                except Exception:
                    pass

        view = ConfirmView()
        await ctx.send("Are you sure you want to close this ticket?", view=view)
    else:
        await ctx.send("❌ This command can only be used in ticket channels.")

bot.run(os.getenv("YOUR_BOT_TOKEN"))