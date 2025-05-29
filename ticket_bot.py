import discord
from discord.ext import commands
import asyncio
import os

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

STAFF_ROLE_ID = 1376861623834247168
OWNER_ROLE_ID = 1368395196131442849
LOG_CHANNEL_ID = 1377208637029744641
AUTO_CLOSE_TIME = 1800  # 30 minutes

ticket_timers = {}

CATEGORIES = {
    "claims": "Claims/Credits",
    "boosts": "Server Boosts",
    "premium": "Premium Upgrades",
    "reseller": "Reseller"
}

@bot.event
async def on_ready():
    print(f'Bot {bot.user} is ready!')

@bot.command()
@commands.has_permissions(manage_channels=True)
async def setup_ticket(ctx):
    embed = discord.Embed(title="Support", description="Select a category below to open a ticket.", color=0x9b59b6)
    embed.set_footer(text="Tickets will auto-close in 30 minutes if no reply.")
    view = discord.ui.View()
    for custom_id, label in CATEGORIES.items():
        emoji = {
            "claims": "<a:Gift:1368420677648121876>",
            "boosts": "<a:NitroBooster:1368420767577931836>",
            "premium": "<:upvote:1376850180644667462>",
            "reseller": "<a:moneywings:1377119310761427014>"
        }[custom_id]
        view.add_item(discord.ui.Button(label=label, emoji=emoji, custom_id=custom_id))
    await ctx.send(embed=embed, view=view)

@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component and interaction.data['custom_id'] in CATEGORIES:
        category_id = interaction.data['custom_id']
        category_label = CATEGORIES[category_id]
        guild = interaction.guild

        ticket_category = discord.utils.get(guild.categories, name="Tickets")
        if ticket_category is None:
            ticket_category = await guild.create_category("Tickets")

        channel_name = f"{category_id}-{interaction.user.name}".replace(" ", "-").lower()
        channel = await ticket_category.create_text_channel(channel_name, topic=str(interaction.user.id))  # 🛠️ Set user ID in topic

        await channel.set_permissions(guild.default_role, read_messages=False, send_messages=False)
        await channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
        await channel.set_permissions(guild.get_role(OWNER_ROLE_ID), read_messages=True, send_messages=True)
        await channel.set_permissions(guild.get_role(STAFF_ROLE_ID), read_messages=True, send_messages=True)

        msg = (
            f"{interaction.user.mention} has opened a ticket. <@&{STAFF_ROLE_ID}>, please assist! 🛠️\n\n"
            f"📌 {interaction.user.mention}, please describe your issue or the service you're requesting.\n"
        )
        if category_id == "reseller":
            msg += (
                f"💸 **Payment Methods:**\n"
                f"+ <:Paypal:1374290794340548619> PayPal (F&F)\n"
                f"+ <:PurpleCashApp:1374290682835107892> Cash App\n"
                f"+ <:Apple_Pay_Logo:1374291214983102474> Apple Pay\n"
                f"+ <:Zelle:1374291283329286194> Zelle\n"
                f"+ <:emojigg_ltc:1374291116966412348> Litecoin (LTC)\n"
            )
        msg += "\nA staff member will assist you shortly. Thank you for your patience! 💙"
        await channel.send(msg)

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"📂 Ticket opened: {channel.mention} by {interaction.user.mention} (Category: {category_label})")

        task = asyncio.create_task(auto_close_ticket(channel, interaction.user, log_channel))
        ticket_timers[channel.id] = task

async def auto_close_ticket(channel, user, log_channel):
    try:
        await asyncio.sleep(AUTO_CLOSE_TIME)
        messages = [msg async for msg in channel.history(limit=10)]
        if len(messages) <= 1:
            await channel.send("No response detected. Closing ticket.")
            await channel.delete()
            if log_channel:
                await log_channel.send(f"❌ Ticket auto-closed due to inactivity: {channel.name}")
    except Exception:
        pass
    finally:
        ticket_timers.pop(channel.id, None)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def close(ctx):
    if ctx.channel.category and ctx.channel.category.name == "Tickets":
        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30)

            @discord.ui.button(label="Yes", style=discord.ButtonStyle.danger)
            async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You are not authorized to confirm this action.", ephemeral=True)
                    return
                await interaction.response.edit_message(content="Closing the ticket...", view=None)
                task = ticket_timers.pop(ctx.channel.id, None)
                if task:
                    task.cancel()
                await asyncio.sleep(2)
                await ctx.channel.delete()
                log_channel = bot.get_channel(LOG_CHANNEL_ID)
                if log_channel:
                    await log_channel.send(f"✅ Ticket manually closed: {ctx.channel.name}")

            @discord.ui.button(label="No", style=discord.ButtonStyle.secondary)
            async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You are not authorized to cancel this action.", ephemeral=True)
                    return
                await interaction.response.edit_message(content="Ticket close canceled.", view=None)
                self.stop()

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

@bot.command()
@commands.has_permissions(manage_channels=True)
async def ping(ctx):
    if ctx.channel.category and ctx.channel.category.name == "Tickets":
        try:
            user_id = int(ctx.channel.topic)
            user = ctx.guild.get_member(user_id)
            if user:
                await user.send(f"👋 Hey {user.mention}, please check your ticket for updates. You have been pinged by staff.")
                await ctx.send(f"✅ DM sent to {user.mention}!")
            else:
                await ctx.send("❌ Could not find the ticket creator.")
        except:
            await ctx.send("❌ Could not DM the user. They may have DMs disabled.")
    else:
        await ctx.send("❌ This command can only be used in a ticket channel.")

@bot.command()
async def ltc(ctx):
    await ctx.send("🚀 Here’s the Litecoin address: `LeYqdR1y6EEASgV2Uf5oc1ABkeAHaMmjXx`")

bot.run(os.getenv("DISCORD_TOKEN"))