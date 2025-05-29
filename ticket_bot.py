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

open_tickets = {}

@bot.event
async def on_ready():
    print(f'✅ Bot {bot.user} is ready!')

@bot.command()
async def setup(ctx):
    embed = discord.Embed(
        title="Support",
        description="Select a category below to open a ticket.\nTickets auto-close in 30 minutes if no reply.",
        color=discord.Color.purple()
    )
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Claims/Credits", emoji="<:Gift:1368420677648121876>", custom_id="claims"))
    view.add_item(discord.ui.Button(label="Server Boosts", emoji="<:NitroBooster:1368420676577931836>", custom_id="boosts"))
    view.add_item(discord.ui.Button(label="Premium Upgrades", emoji="<:upvote:1376850180644667462>", custom_id="premium"))
    view.add_item(discord.ui.Button(label="Reseller", emoji="<:moneywings:1377119310761427014>", custom_id="reseller"))
    await ctx.send(embed=embed, view=view)

@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        category = interaction.data.get("custom_id")
        user = interaction.user
        key = (user.id, category)

        if key in open_tickets:
            await interaction.response.send_message("❌ You already have an open ticket in this category.", ephemeral=True)
            return

        guild = interaction.guild
        category_channel = guild.get_channel(CATEGORY_ID)
        ticket_channel = await guild.create_text_channel(
            name=f"{category}-{user.name}".replace(" ", "-").lower(),
            category=category_channel
        )
        await ticket_channel.set_permissions(user, read_messages=True, send_messages=True)
        await ticket_channel.set_permissions(guild.default_role, read_messages=False)
        await ticket_channel.set_permissions(guild.get_role(STAFF_ROLE_ID), read_messages=True, send_messages=True)

        open_tickets[key] = ticket_channel.id

        await ticket_channel.send(
            f"{user.mention} has opened a ticket. <@&{STAFF_ROLE_ID}>, please assist!\n\n"
            f"📌 **Please describe your issue or request.**\n\n"
            f"💰 **Payment Methods:**\n"
            f"+ <:PayPal:137429079403548619> PayPal (F&F)\n"
            f"+ <:PurpleCashApp:1374290682835107892> Cash App\n"
            f"+ <:ApplePay:1374291211498120742> Apple Pay\n"
            f"+ <:Zelle:1374291283229698194> Zelle\n"
            f"+ <:Litecoin:1374291161166641234> Litecoin (LTC)"
        )

        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"📂 Ticket opened: {ticket_channel.mention} by {user.mention} (Category: {category})")

        async def auto_close():
            await asyncio.sleep(AUTO_CLOSE_TIME)
            if ticket_channel and ticket_channel in guild.text_channels:
                await ticket_channel.send("⏳ No response for 30 minutes. Closing ticket.")
                await ticket_channel.delete()
                open_tickets.pop(key, None)
                if log_channel:
                    await log_channel.send(f"✅ Ticket auto-closed: {ticket_channel.name}")

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
            await user.send(f"👋 Hey {user.mention}, please check your ticket for updates!")
            await ctx.send(f"✅ DM sent to {user.mention}!")
    except:
        await ctx.send("❌ Could not DM the user.")

@bot.command()
async def close(ctx):
    if ctx.channel.category_id != CATEGORY_ID:
        await ctx.send("This command can only be used in a ticket.")
        return

    class CloseView(discord.ui.View):
        @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
        async def yes(self, interaction, button):
            await interaction.response.edit_message(content="✅ Closing the ticket...", view=None)
            await ctx.channel.delete()
            key = next((k for k, v in open_tickets.items() if v == ctx.channel.id), None)
            if key:
                open_tickets.pop(key, None)
            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(f"✅ Ticket manually closed: {ctx.channel.name}")

        @discord.ui.button(label="No", style=discord.ButtonStyle.red)
        async def no(self, interaction, button):
            await interaction.response.edit_message(content="❌ Ticket close cancelled.", view=None)

        @discord.ui.button(label="Auto (30 sec)", style=discord.ButtonStyle.blurple)
        async def auto(self, interaction, button):
            await interaction.response.edit_message(content="Auto-close in 30 seconds...", view=None)
            await asyncio.sleep(30)
            await ctx.channel.delete()
            key = next((k for k, v in open_tickets.items() if v == ctx.channel.id), None)
            if key:
                open_tickets.pop(key, None)
            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(f"✅ Ticket auto-closed: {ctx.channel.name}")

    await ctx.send("Are you sure you want to close this ticket?", view=CloseView())

@bot.command()
async def pp(ctx):
    await ctx.send("💸 **PayPal (F&F):** https://www.paypal.com/paypalme/Hunter393?country.x=US&locale.x=en_US")

@bot.command()
async def cash(ctx):
    await ctx.send("💸 **Cash App:** https://cash.app/$Tripussy")

@bot.command()
async def ltc(ctx):
    await ctx.send("💸 **Litecoin (LTC):** `LeYqdR1y6EEASgV2Uf5oc1ABkeAHaMmjXx`")

bot.run(os.getenv("DISCORD_TOKEN"))