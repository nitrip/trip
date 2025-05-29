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
CATEGORY_ID = 1377221670837682261
LOG_CHANNEL_ID = 1377208637029744641
AUTO_CLOSE_TIME = 1800  # 30 minutes

@bot.event
async def on_ready():
    print(f'✅ Bot {bot.user} is ready!')

@bot.command()
@commands.has_permissions(manage_channels=True)
async def setup(ctx):
    embed = discord.Embed(
        title="Support",
        description="Select a category below to open a ticket.\nTickets auto-close in 30 minutes if no reply.",
        color=0x9b59b6
    )
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

        ticket_name = f"{category}-{user.name}".lower()
        for channel in category_channel.text_channels:
            if channel.name.startswith(f"{category}-{user.name}"):
                await interaction.response.send_message(f"❌ You already have a ticket open: {channel.mention}", ephemeral=True)
                return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True),
            guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True)
        }

        channel = await category_channel.create_text_channel(ticket_name, overwrites=overwrites, topic=f"{user.id}")

        await channel.send(
            f"{user.mention} has opened a ticket. <@&{STAFF_ROLE_ID}>, please assist!\n\n"
            "📌 Please describe your issue or request.\n"
            "💸 Payment Methods:\n"
            "• <:PayPal:137429079403548619> **PayPal (F&F)**\n"
            "• <:PurpleCashApp:1374290682835107892> **Cash App**\n"
            "• <:ApplePay:1374291211498120742> **Apple Pay**\n"
            "• <:Zelle:1374291283229698194> **Zelle**\n"
            "• <:Litecoin:1374291161166641234> **Litecoin (LTC)**"
        )

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"📂 Ticket opened: {channel.mention} by {user.mention} (Category: {category})")

        async def auto_close():
            await asyncio.sleep(AUTO_CLOSE_TIME)
            if channel and channel.category == category_channel:
                await channel.send("⏰ No response received in 30 minutes. Closing the ticket.")
                await channel.delete()

        bot.loop.create_task(auto_close())

@bot.command()
async def ping(ctx):
    if ctx.channel.category_id != CATEGORY_ID:
        await ctx.send("This command can only be used in a ticket.")
        return
    try:
        user_id = int(ctx.channel.topic)
        user = ctx.guild.get_member(user_id)
        if user:
            await user.send(f"👋 Hey {user.mention}, please check your ticket for updates from the staff!")
            await ctx.send(f"✅ DM sent to {user.mention}!")
        else:
            await ctx.send("❌ Could not find the user who opened this ticket.")
    except Exception:
        await ctx.send("❌ Could not DM the ticket user. They may have DMs disabled.")

@bot.command()
async def close(ctx):
    if ctx.channel.category_id != CATEGORY_ID:
        await ctx.send("This command can only be used in a ticket.")
        return

    view = discord.ui.View()
    async def confirm(interaction):
        await interaction.response.edit_message(content="✅ Closing the ticket...", view=None)
        await asyncio.sleep(2)
        await ctx.channel.delete()
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"✅ Ticket manually closed: {ctx.channel.name}")

    async def cancel(interaction):
        await interaction.response.edit_message(content="❌ Ticket close cancelled.", view=None)

    async def auto(interaction):
        await interaction.response.edit_message(content="Auto-closing the ticket in 30 seconds.", view=None)
        await asyncio.sleep(30)
        await ctx.channel.delete()
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"✅ Ticket auto-closed: {ctx.channel.name}")

    view.add_item(discord.ui.Button(label="Yes", style=discord.ButtonStyle.green, custom_id="yes"))
    view.add_item(discord.ui.Button(label="No", style=discord.ButtonStyle.red, custom_id="no"))
    view.add_item(discord.ui.Button(label="Auto (30 sec)", style=discord.ButtonStyle.blurple, custom_id="auto"))

    message = await ctx.send("Are you sure you want to close this ticket?", view=view)

    def check(i):
        return i.user == ctx.author and i.message.id == message.id

    try:
        interaction = await bot.wait_for("interaction", check=check, timeout=60)
        if interaction.data['custom_id'] == 'yes':
            await confirm(interaction)
        elif interaction.data['custom_id'] == 'no':
            await cancel(interaction)
        elif interaction.data['custom_id'] == 'auto':
            await auto(interaction)
    except asyncio.TimeoutError:
        await message.edit(content="❌ Timeout. No action taken.", view=None)

@bot.command()
async def pp(ctx):
    await ctx.send("Here is the PayPal link: https://www.paypal.com/paypalme/Hunter393?country.x=US&locale.x=en_US")

@bot.command()
async def cash(ctx):
    await ctx.send("Here is the Cash App link: https://cash.app/$Tripussy")

@bot.command()
async def ltc(ctx):
    await ctx.send("Here is the Litecoin (LTC) address: LeYqdR1y6EEASgV2Uf5oc1ABkeAHaMmjXx")

bot.run(os.getenv("YOUR_BOT_TOKEN"))