import discord
from discord.ext import commands
import asyncio

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

STAFF_ROLE_ID = 1376861623834247168
LOG_CHANNEL_ID = 1368426352662937630
AUTO_CLOSE_TIME = 1800  # 30 minutes

@bot.event
async def on_ready():
    print(f'Bot {bot.user} is ready!')

@bot.command()
@commands.has_permissions(manage_channels=True)
async def setup_ticket(ctx):
    embed = discord.Embed(title="Support", description="Select a category below to open a ticket.", color=0x9b59b6)
    embed.set_footer(text="Tickets will auto-close in 30 minutes if no reply.")

    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Claims/Credits", emoji="<a:Gift:1368420677648121876>", custom_id="claims"))
    view.add_item(discord.ui.Button(label="Server Boosts", emoji="<a:NitroBooster:1368420767577931836>", custom_id="boosts"))
    view.add_item(discord.ui.Button(label="Premium Upgrades", emoji="<:upvote:1376850180644667462>", custom_id="premium"))
    view.add_item(discord.ui.Button(label="Billing", emoji="<:shopping_cart_green12:1376614180869898311>", custom_id="billing"))

    await ctx.send(embed=embed, view=view)

@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        category = interaction.data['custom_id']
        guild = interaction.guild

        ticket_category = discord.utils.get(guild.categories, name="Tickets")
        if ticket_category is None:
            ticket_category = await guild.create_category("Tickets")

        channel = await ticket_category.create_text_channel(f"{category}-{interaction.user.name}")
        await channel.set_permissions(interaction.user, read_messages=True, send_messages=True)

        # Staff Role Access + Ping
        await channel.set_permissions(guild.get_role(STAFF_ROLE_ID), read_messages=True, send_messages=True)
        await channel.send(f"{interaction.user.mention} has opened a ticket. <@&{STAFF_ROLE_ID}>, please assist!")

        # Auto-Close Warning
        await channel.send("⚠️ This ticket will auto-close in 30 minutes if no one responds.")

        # Billing Ticket - Payment Methods
        if category == "billing":
            await channel.send(
                "**💳 Payment Methods:**\n"
                "- **Cash App:** <:PurpleCashApp:1374290682835107892>\n"
                "- **Apple Pay:** <:Apple_Pay_Logo:1374291214983102474>\n"
                "- **LTC:** <:emojigg_ltc:1374291116966412348>\n"
                "- **Zelle:** <:Zelle:1374291283329286194>\n"
                "- **PayPal:** <:Paypal:1374290794340548619>"
            )

        # Log Ticket Creation
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"📂 Ticket opened: {channel.mention} by {interaction.user.mention} (Category: {category})")

        # Auto-Close Logic
        await asyncio.sleep(AUTO_CLOSE_TIME)
        messages = [msg async for msg in channel.history(limit=10)]
        if len(messages) <= 1:
            await channel.send("No response detected. Closing ticket.")
            await channel.delete()
            if log_channel:
                await log_channel.send(f"❌ Ticket auto-closed due to inactivity: {channel.name}")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def close(ctx):
    if ctx.channel.category and ctx.channel.category.name == "Tickets":
        await ctx.send("Closing this ticket...")
        await asyncio.sleep(2)
        await ctx.channel.delete()

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"✅ Ticket manually closed: {ctx.channel.name}")
    else:
        await ctx.send("This command can only be used in ticket channels.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def reopen(ctx, user: discord.Member, category: str):
    category = category.lower()
    allowed = ["claims", "boosts", "premium", "billing"]
    if category not in allowed:
        await ctx.send(f"Invalid category. Choose from: {', '.join(allowed)}")
        return

    guild = ctx.guild
    ticket_category = discord.utils.get(guild.categories, name="Tickets")
    if ticket_category is None:
        ticket_category = await guild.create_category("Tickets")

    channel = await ticket_category.create_text_channel(f"{category}-{user.name}")
    await channel.set_permissions(user, read_messages=True, send_messages=True)
    await channel.set_permissions(guild.get_role(STAFF_ROLE_ID), read_messages=True, send_messages=True)
    await channel.send(f"Ticket reopened for {user.mention}. <@&{STAFF_ROLE_ID}>, please assist!")

    if category == "billing":
        await channel.send(
            "**💳 Payment Methods:**\n"
            "- **Cash App:** <:PurpleCashApp:1374290682835107892>\n"
            "- **Apple Pay:** <:Apple_Pay_Logo:1374291214983102474>\n"
            "- **LTC:** <:emojigg_ltc:1374291116966412348>\n"
            "- **Zelle:** <:Zelle:1374291283329286194>\n"
            "- **PayPal:** <:Paypal:1374290794340548619>"
        )

    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f"🔄 Ticket reopened for {user.mention} in {channel.mention} (Category: {category})")

    await ctx.send(f"Reopened a ticket for {user.mention} in {channel.mention}.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def ping(ctx):
    try:
        await ctx.author.send(f"Hey {ctx.author.name}, please check your ticket for updates or questions from the staff. 🚀")
        await ctx.send("✅ I've sent you a DM to check your ticket!", delete_after=5)
    except discord.Forbidden:
        await ctx.send("❌ I couldn't DM you. Please enable DMs from server members.")

@bot.command()
async def ltc(ctx):
    await ctx.send("🚀 Here’s the Litecoin address: `LeYqdR1y6EEASgV2Uf5oc1ABkeAHaMmjXx`")

bot.run("")
