import discord
from discord.ext import commands
import asyncio
import os

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

STAFF_ROLE_ID = 1376861623834247168
CATEGORY_ID = 1377221670837682261
LOG_CHANNEL_ID = 1377208637029744641
AUTO_CLOSE_TIME = 1800  # 30 minutes

open_tickets = {}

@bot.event
async def on_ready():
    print(f'{bot.user} is online.')

@bot.command()
async def setup(ctx):
    embed = discord.Embed(
        title="Support",
        description="Select a category below to open a ticket.\nTickets auto-close in 30 minutes if no reply.",
        color=discord.Color.purple()
    )
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Claims/Credits", emoji="🎁", custom_id="claims"))
    view.add_item(discord.ui.Button(label="Server Boosts", emoji="💎", custom_id="boosts"))
    view.add_item(discord.ui.Button(label="Premium Upgrades", emoji="🟢", custom_id="premium"))
    view.add_item(discord.ui.Button(label="Reseller", emoji="💸", custom_id="reseller"))
    await ctx.send(embed=embed, view=view)

@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        category = interaction.data['custom_id']
        guild = interaction.guild
        user = interaction.user

        if (category, user.id) in open_tickets:
            await interaction.response.send_message("You already have an open ticket in this category.", ephemeral=True)
            return

        category_channel = discord.utils.get(guild.categories, id=CATEGORY_ID)
        ticket_channel = await guild.create_text_channel(
            name=f"{category}-{user.name}",
            category=category_channel,
            topic=f"Ticket for {user.name}"
        )
        await ticket_channel.set_permissions(user, read_messages=True, send_messages=True)
        await ticket_channel.set_permissions(guild.get_role(STAFF_ROLE_ID), read_messages=True, send_messages=True)
        await ticket_channel.set_permissions(guild.default_role, read_messages=False)

        open_tickets[(category, user.id)] = ticket_channel.id

        payment_methods = (
            "📌 **Please describe your issue or request.**\n"
            "💵 **Payment Methods:**\n"
            "• <:PayPal:> PayPal (F&F)\n"
            "• <:CashApp:> Cash App\n"
            "• <:ApplePay:> Apple Pay\n"
            "• <:Zelle:> Zelle\n"
            "• <:Litecoin:> Litecoin (LTC)"
        )

        await ticket_channel.send(
            f"{user.mention} has opened a ticket. <@&{STAFF_ROLE_ID}>, please assist!\n\n{payment_methods}"
        )

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"📂 Ticket opened: {ticket_channel.mention} by {user.mention} (Category: {category})")

        # Auto-close logic
        async def auto_close():
            await asyncio.sleep(AUTO_CLOSE_TIME)
            if ticket_channel:
                await ticket_channel.send("No response for 30 minutes. Closing ticket.")
                await ticket_channel.delete()
                open_tickets.pop((category, user.id), None)
                if log_channel:
                    await log_channel.send(f"✅ Ticket auto-closed: {ticket_channel.name}")

        bot.loop.create_task(auto_close())

@bot.command()
async def ping(ctx):
    if ctx.channel.category_id == CATEGORY_ID:
        user = ctx.channel.topic.split("Ticket for ")[-1]
        await ctx.send(f"DM sent to `{user}`")
        try:
            member = discord.utils.get(ctx.guild.members, name=user)
            if member:
                await member.send(f"👋 Please check your ticket in `{ctx.channel.name}`")
        except:
            await ctx.send("Couldn't DM the user.")

@bot.command()
async def close(ctx):
    if ctx.channel.category_id != CATEGORY_ID:
        await ctx.send("This command can only be used in a ticket.")
        return

    class CloseConfirm(discord.ui.View):
        @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
        async def yes(self, interaction, button):
            await ctx.channel.delete()
            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(f"✅ Ticket manually closed: {ctx.channel.name}")

        @discord.ui.button(label="No", style=discord.ButtonStyle.red)
        async def no(self, interaction, button):
            await interaction.response.send_message("Ticket closure cancelled.", ephemeral=True)

        @discord.ui.button(label="Auto (30s)", style=discord.ButtonStyle.blurple)
        async def auto(self, interaction, button):
            await interaction.response.send_message("Ticket will close in 30 seconds.", ephemeral=True)
            await asyncio.sleep(30)
            await ctx.channel.delete()
            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(f"✅ Ticket auto-closed: {ctx.channel.name}")

    await ctx.send("Do you want to close the ticket?", view=CloseConfirm())

@bot.command()
async def pp(ctx):
    await ctx.send("Here is the PayPal address: https://www.paypal.com/paypalme/Hunter393?country.x=US&locale.x=en_US")

@bot.command()
async def cash(ctx):
    await ctx.send("Here is the Cash App: https://cash.app/$Tripussy")

@bot.command()
async def ltc(ctx):
    await ctx.send("Here is the Litecoin address: `LeYqRdiLy5EFAgQ2uF5ocLABkAeWawJxX`")

bot.run(os.getenv("DISCORD_TOKEN"))