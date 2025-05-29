import discord
from discord.ext import commands
import asyncio
import os

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Your server-specific IDs
STAFF_ROLE_ID = 1376861623834247168
OWNER_ROLE_ID = 1368395196131442849
LOG_CHANNEL_ID = 1377208637029744641
TICKET_CATEGORY_ID = 1377221670837682261

@bot.event
async def on_ready():
    print(f'Bot {bot.user} is ready!')

@bot.command()
@commands.has_permissions(manage_channels=True)
async def setup(ctx):
    embed = discord.Embed(
        title="Support",
        description="Select a category below to open a ticket.\nTickets will auto-close in 30 minutes if no reply.",
        color=0x9b59b6
    )
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(label="Claims/Credits", emoji="<a:Gift:1368420677648121876>", custom_id="claims"))
    view.add_item(discord.ui.Button(label="Server Boosts", emoji="<a:NitroBooster:1368420767577931836>", custom_id="boosts"))
    view.add_item(discord.ui.Button(label="Premium Upgrades", emoji="<:upvote:1376850180644667462>", custom_id="premium"))
    view.add_item(discord.ui.Button(label="Reseller", emoji="<a:moneywings:1377119310761427014>", custom_id="reseller"))

    await ctx.send(embed=embed, view=view)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component and interaction.data.get("custom_id") in ["claims", "boosts", "premium", "reseller"]:
        category = interaction.data['custom_id']
        guild = interaction.guild
        ticket_category = guild.get_channel(TICKET_CATEGORY_ID)

        if ticket_category is None:
            await interaction.response.send_message("❌ Ticket category not found. Please check the configuration.", ephemeral=True)
            return

        ticket_name = f"{category}-{interaction.user.name}"

        for channel in ticket_category.text_channels:
            if channel.name.startswith(f"{category}-{interaction.user.name}"):
                await interaction.response.send_message("❌ You already have a ticket open in this category!", ephemeral=True)
                return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.get_role(OWNER_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        ticket_channel = await guild.create_text_channel(ticket_name, category=ticket_category, overwrites=overwrites, topic=f"Ticket for {interaction.user.id}")

        await ticket_channel.send(
            f"{interaction.user.mention} has opened a ticket. <@&{STAFF_ROLE_ID}>, please assist!\n"
            f"📌 Please describe your issue or the service you're requesting.\n"
            f"💸 Payment Methods:\n"
            f"- <a:Gift:1368420677648121876> Cash App\n"
            f"- <:upvote:1376850180644667462> Apple Pay\n"
            f"- <a:NitroBooster:1368420767577931836> Zelle\n"
            f"- <a:moneywings:1377119310761427014> Litecoin"
        )

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"✅ Ticket opened: {ticket_channel.mention} by {interaction.user.mention} (Category: {category})")

        await interaction.response.send_message(f"✅ Your ticket has been created: {ticket_channel.mention}", ephemeral=True)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def ping(ctx):
    if ctx.channel.topic:
        user_id = int(ctx.channel.topic.split()[-1])
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

bot.run(os.getenv("YOUR_BOT_TOKEN"))