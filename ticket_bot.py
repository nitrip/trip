import discord
from discord.ext import commands
import asyncio
import os

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

STAFF_ROLE_ID = 1376861623834247168  # Staff role ID
LOG_CHANNEL_ID = 1377208637029744641  # Ticket logs channel ID

@bot.event
async def on_ready():
    print(f'Bot {bot.user} is ready!')

@bot.command()
@commands.has_permissions(manage_channels=True)
async def setup(ctx):
    embed = discord.Embed(title="Support", description="Select a category below to open a ticket.\nTickets will auto-close in 30 minutes if no reply.", color=0x9b59b6)
    view = discord.ui.View()

    view.add_item(discord.ui.Button(label="Claims/Credits", emoji="<a:Gift:1368420677648121876>", custom_id="claims"))
    view.add_item(discord.ui.Button(label="Server Boosts", emoji="<a:NitroBooster:1368420767577931836>", custom_id="boosts"))
    view.add_item(discord.ui.Button(label="Premium Upgrades", emoji="<:upvote:1376850180644667462>", custom_id="premium"))
    view.add_item(discord.ui.Button(label="Reseller", emoji="<a:moneywings:1377119310761427014>", custom_id="reseller"))

    await ctx.send(embed=embed, view=view)

@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        category = interaction.data['custom_id']
        guild = interaction.guild
        category_name = f"📂 {category}-{interaction.user.name}"

        # Check for existing ticket
        for channel in guild.text_channels:
            if channel.name.startswith(f"{category}-{interaction.user.name}"):
                await interaction.response.send_message("You already have a ticket open in this category!", ephemeral=True)
                return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.get_role(1376861623834247168): discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.get_role(1368395196131442849): discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        ticket_channel = await guild.create_text_channel(category_name, overwrites=overwrites, topic=f"Ticket for {interaction.user}")

        await ticket_channel.send(
            f"{interaction.user.mention} has opened a ticket. <@&{STAFF_ROLE_ID}>, please assist!\n"
            f"📌 Please describe your issue or the service you're requesting.\n"
            f"💸 Payment Methods:\n- <a:Gift:1368420677648121876> Cash App\n- <:upvote:1376850180644667462> Apple Pay\n- <a:NitroBooster:1368420767577931836> Zelle\n- <a:moneywings:1377119310761427014> Litecoin"
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