import discord
from discord.ext import commands
from discord.ui import Button, View
import asyncio
import os

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

STAFF_ROLE_ID = 1376861623834247168  # Staff role ID
TICKET_CATEGORY_ID = 1377221670837682261  # Category ID where tickets go
LOG_CHANNEL_ID = 1377208637029744641  # Log channel ID
AUTO_CLOSE_TIME = 1800  # 30 minutes in seconds

active_tickets = {}

# --- Payment Methods Message ---
def get_payment_methods():
    return (
        "📌 **Please describe your issue or request.**\n"
        "💸 **Payment Methods:**\n"
        "• <:PayPal:137429079403548619> **PayPal (F&F)**\n"
        "• <:PurpleCashApp:1374290682835107892> **Cash App**\n"
        "• <:ApplePay:1374291211498120742> **Apple Pay**\n"
        "• <:Zelle:1374291283229698194> **Zelle**\n"
        "• <:Litecoin:1374291161166641234> **Litecoin (LTC)**"
    )

# --- Open Ticket Command ---
@bot.command()
@commands.has_permissions(manage_channels=True)
async def setup(ctx):
    embed = discord.Embed(
        title="Support",
        description="Select a category below to open a ticket.\nTickets auto-close in 30 minutes if no reply.",
        color=0x9b59b6
    )
    view = View()
    view.add_item(Button(label="Claims/Credits", custom_id="claims", emoji="<:PayPal:137429079403548619>"))
    view.add_item(Button(label="Server Boosts", custom_id="boosts", emoji="<:PurpleCashApp:1374290682835107892>"))
    view.add_item(Button(label="Premium Upgrades", custom_id="premium", emoji="<:ApplePay:1374291211498120742>"))
    view.add_item(Button(label="Reseller", custom_id="reseller", emoji="<:Litecoin:1374291161166641234>"))
    await ctx.send(embed=embed, view=view)

# --- Handle Button Interaction ---
@bot.event
async def on_interaction(interaction):
    if not interaction.data.get("custom_id"):
        return
    category = interaction.data["custom_id"]
    user = interaction.user

    # Check if user has a ticket in this category
    key = (user.id, category)
    if key in active_tickets:
        await interaction.response.send_message("You already have an open ticket in this category.", ephemeral=True)
        return

    # Create ticket
    guild = interaction.guild
    category_channel = guild.get_channel(TICKET_CATEGORY_ID)
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True)
    }
    channel = await guild.create_text_channel(
        name=f"{category}-{user.name}".replace(" ", "-"),
        category=category_channel,
        overwrites=overwrites
    )

    active_tickets[key] = channel.id

    # Log and send payment message
    log_channel = guild.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f"📂 Ticket opened: {channel.mention} by {user.mention} (Category: {category})")
    await channel.send(f"{user.mention} has opened a ticket. <@&{STAFF_ROLE_ID}>, please assist!\n\n{get_payment_methods()}")

    # Auto-close timer
    async def auto_close():
        await asyncio.sleep(AUTO_CLOSE_TIME)
        if channel and channel.id in [c.id for c in guild.text_channels]:
            await channel.send("⏳ No response for 30 minutes. Closing ticket automatically.")
            await channel.delete()
            if log_channel:
                await log_channel.send(f"✅ Ticket auto-closed: {channel.name}")
            active_tickets.pop(key, None)
    bot.loop.create_task(auto_close())

# --- Ping Command ---
@bot.command()
async def ping(ctx):
    if ctx.channel.category and ctx.channel.category.id == TICKET_CATEGORY_ID:
        opener = ctx.channel.name.split('-')[-1]
        member = discord.utils.get(ctx.guild.members, name=opener)
        if member:
            await member.send(f"📬 **You have a message in your ticket!**")
            await ctx.send(f"✅ DM sent to {member.mention}")
        else:
            await ctx.send("❌ Could not find the ticket opener.")
    else:
        await ctx.send("This command can only be used in ticket channels.")

# --- Close Command ---
@bot.command()
async def close(ctx):
    if ctx.channel.category and ctx.channel.category.id == TICKET_CATEGORY_ID:
        view = View()
        async def confirm(interaction):
            await ctx.channel.delete()
            key = next((k for k, v in active_tickets.items() if v == ctx.channel.id), None)
            if key:
                active_tickets.pop(key, None)
            log_channel = ctx.guild.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(f"✅ Ticket manually closed: {ctx.channel.name}")
        async def cancel(interaction):
            await interaction.response.send_message("❌ Ticket closure cancelled.", ephemeral=True)
        async def auto(interaction):
            await interaction.response.send_message("⏳ Auto-closing in 30 seconds...")
            await asyncio.sleep(30)
            await ctx.channel.delete()
            key = next((k for k, v in active_tickets.items() if v == ctx.channel.id), None)
            if key:
                active_tickets.pop(key, None)
            log_channel = ctx.guild.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(f"✅ Ticket auto-closed via !close: {ctx.channel.name}")

        view.add_item(Button(label="Yes", style=discord.ButtonStyle.green, custom_id="yes"))
        view.add_item(Button(label="No", style=discord.ButtonStyle.red, custom_id="no"))
        view.add_item(Button(label="Auto", style=discord.ButtonStyle.gray, custom_id="auto"))

        async def handle(interaction):
            if interaction.data["custom_id"] == "yes":
                await confirm(interaction)
            elif interaction.data["custom_id"] == "no":
                await cancel(interaction)
            elif interaction.data["custom_id"] == "auto":
                await auto(interaction)

        view.on_timeout = lambda: None
        view.on_click = handle
        await ctx.send("Are you sure you want to close the ticket?", view=view)
    else:
        await ctx.send("This command can only be used in ticket channels.")

# --- Payment Commands ---
@bot.command()
async def ltc(ctx):
    await ctx.send("💸 **Litecoin (LTC)** Address: `LeYqdR1y6EEASgV2Uf5oc1ABkeAHaMmjXx`")

@bot.command()
async def cash(ctx):
    await ctx.send("💸 **Cash App**: https://cash.app/$Tripussy")

@bot.command()
async def pp(ctx):
    await ctx.send("💸 **PayPal**: https://www.paypal.com/paypalme/Hunter393?country.x=US&locale.x=en_US")

# --- Run Bot ---
bot.run(os.getenv("DISCORD_TOKEN"))