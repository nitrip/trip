import discord
from discord.ext import commands
import asyncio
import os
import sys
import traceback

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

STAFF_ROLE_ID = 1376861623834247168
OWNER_ROLE_ID = 1368395196131442849
LOG_CHANNEL_ID = 1377208637029744641
AUTO_CLOSE_TIME = 1800  # 30 minutes

ticket_timers = {}
TICKET_CREATOR = {}

# --- MODIFIED: Integrated emoji IDs directly into CATEGORIES_DATA ---
CATEGORIES_DATA = {
    "claims": {"label": "Claims/Credits", "emoji_id": "<a:Gift:1368420677648121876>"},
    "boosts": {"label": "Server Boosts", "emoji_id": "<a:NitroBooster:1368420767577931836>"},
    "premium": {"label": "Premium Upgrades", "emoji_id": "<:upvote:1376850180644667462>"},
    "reseller": {"label": "Reseller", "emoji_id": "<a:moneywings:1377119310761427014>"}
}
# --- IMPORTANT: If you want to create tickets in a specific category by ID, define it here:
# TICKET_PARENT_CATEGORY_ID = YOUR_TICKET_CATEGORY_ID # e.g., 1234567890123456789
# If you prefer to find it by name as in your original script ("Tickets"), the code below will handle it.

@bot.event
async def on_ready():
    print(f'Bot {bot.user} is ready!')

# --- ADDED: Global Error Handler ---
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ That command does not exist. Please check your spelling.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing a required argument: `{error.param.name}`.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have the necessary permissions to use this command.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Invalid argument provided: {error}")
    elif isinstance(error, commands.NoPrivateMessage):
        await ctx.send("❌ This command cannot be used in private messages.")
    else:
        print(f"Ignoring exception in command {ctx.command}:", file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
        await ctx.send("An unexpected error occurred while running this command. Check the console for details.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def setup(ctx):
    embed = discord.Embed(
        title="Support Ticket System",
        description=(
            "Click on a category button below to open a new support ticket.\n"
            f"Tickets will automatically close after {AUTO_CLOSE_TIME // 60} minutes of inactivity."
        ),
        color=discord.Color.purple()
    )
    view = discord.ui.View(timeout=None)

    for custom_id, data in CATEGORIES_DATA.items():
        button = discord.ui.Button(
            label=data["label"],
            custom_id=custom_id,
            emoji=data["emoji_id"]
        )
        view.add_item(button)

    await ctx.send(embed=embed, view=view)

@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component and interaction.data['custom_id'] in CATEGORIES_DATA:
        category_id_key = interaction.data['custom_id']
        category_label = CATEGORIES_DATA[category_id_key]["label"]
        guild = interaction.guild

        ticket_category = discord.utils.get(guild.categories, name="Tickets")
        if ticket_category is None:
            try:
                ticket_category = await guild.create_category("Tickets", overwrites={
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                })
                log_channel = bot.get_channel(LOG_CHANNEL_ID)
                if log_channel:
                    await log_channel.send(f"Created new ticket category: {ticket_category.mention}")
            except discord.Forbidden:
                await interaction.response.send_message(
                    "I don't have permission to create categories. Please contact an administrator.", ephemeral=True
                )
                return
            except Exception as e:
                await interaction.response.send_message(
                    f"An error occurred creating the ticket category: {e}", ephemeral=True
                )
                print(f"Error creating ticket category: {e}", file=sys.stderr)
                traceback.print_exc()
                return

        existing_channel_name = f"{category_id_key}-{interaction.user.name}".replace(" ", "-").lower()
        for channel in guild.channels:
            if isinstance(channel, discord.TextChannel) and channel.name == existing_channel_name:
                if TICKET_CREATOR.get(channel.id) == interaction.user.id:
                    await interaction.response.send_message(
                        f"You already have an open ticket: {channel.mention}. Please close that one first.", ephemeral=True
                    )
                    return

        channel_name = f"{category_id_key}-{interaction.user.name}".replace(" ", "-").lower()
        try:
            channel = await ticket_category.create_text_channel(channel_name)

            await channel.set_permissions(guild.default_role, read_messages=False, send_messages=False)
            await channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
            await channel.set_permissions(guild.get_role(OWNER_ROLE_ID), read_messages=True, send_messages=True)
            await channel.set_permissions(guild.get_role(STAFF_ROLE_ID), read_messages=True, send_messages=True)

            TICKET_CREATOR[channel.id] = interaction.user.id

            msg = (
                f"{interaction.user.mention} has opened a ticket. <@&{STAFF_ROLE_ID}>, please assist! 🛠️\n\n"
                f"📌 **Please describe your issue or request.**\n"
                f"💳 **Payment Methods:**\n"
                f"+ <:Paypal:1374290794340548619> PayPal (F&F)\n"
                f"+ <:PurpleCashApp:1374290682835107892> Cash App\n"
                f"+ <:Apple_Pay_Logo:1374291214983102474> Apple Pay\n"
                f"+ <:Zelle:1374291283329286194> Zelle\n"
                f"+ <:emojigg_ltc:1374291116966412348> Litecoin (LTC)\n"
                f"\nA staff member will assist you shortly. Thank you for your patience! 💙"
            )
            await channel.send(msg)

            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(f"📂 Ticket opened: {channel.mention} by {interaction.user.mention} (Category: {category_label})")

            task = asyncio.create_task(auto_close_ticket(channel.id, guild.id))
            ticket_timers[channel.id] = task

            await interaction.response.send_message(f"✅ Your ticket has been opened: {channel.mention}", ephemeral=True)

        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to create channels in that category or set permissions. Please contact an administrator.", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"An unexpected error occurred: {e}", ephemeral=True)
            print(f"Error creating ticket channel: {e}", file=sys.stderr)
            traceback.print_exc()

async def auto_close_ticket(channel_id, guild_id):
    try:
        await asyncio.sleep(AUTO_CLOSE_TIME)
        guild = bot.get_guild(guild_id)
        if not guild:
            print(f"Guild {guild_id} not found for auto-close task.")
            return

        channel = guild.get_channel(channel_id)
        if channel:
            messages = [msg async for msg in channel.history(limit=10)]
            if len(messages) <= 1:
                ticket_creator_id = TICKET_CREATOR.pop(channel.id, "Unknown")
                ticket_creator_mention = f"<@{ticket_creator_id}>" if ticket_creator_id != "Unknown" else "Unknown User"

                close_reason = "No activity for 30 minutes (auto-closed)."
                close_message = (
                    f"This ticket has been automatically closed due to inactivity ({AUTO_CLOSE_TIME // 60} minutes).\n"
                    f"Reason: {close_reason}\n"
                    f"Ticket created by: {ticket_creator_mention}"
                )
                await channel.send(close_message)
                await channel.delete(reason=close_reason)

                log_channel = bot.get_channel(LOG_CHANNEL_ID)
                if log_channel:
                    await log_channel.send(f"❌ Ticket `{channel.name}` (ID: {channel_id}) created by {ticket_creator_mention} has been **auto-closed** due to inactivity.")
                print(f"Auto-closed ticket: {channel.name} ({channel_id})")
            else:
                print(f"Ticket {channel.name} has activity, not auto-closing.")
        else:
            print(f"Ticket channel {channel_id} not found for auto-close (might have been deleted manually).")
    except asyncio.CancelledError:
        print(f"Auto-close task for channel {channel_id} was cancelled.")
    except discord.NotFound:
        print(f"Channel or message for {channel_id} not found during auto-close (already deleted?).")
    except Exception as e:
        print(f"Error during auto-close of ticket {channel_id}: {e}", file=sys.stderr)
        traceback.print_exc()
    finally:
        ticket_timers.pop(channel_id, None)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def close(ctx):
    if ctx.channel.category and ctx.channel.category.name == "Tickets":
        class ConfirmView(discord.ui.View):
            def __init__(self, original_author_id):
                super().__init__(timeout=30)
                self.original_author_id = original_author_id
                self.value = None

            @discord.ui.button(label="Confirm Close", style=discord.ButtonStyle.danger)
            async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.original_author_id:
                    await interaction.response.send_message("You are not authorized to confirm this action.", ephemeral=True)
                    return
                self.value = True
                await interaction.response.defer()
                self.stop()

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.original_author_id:
                    await interaction.response.send_message("You are not authorized to cancel this action.", ephemeral=True)
                    return
                self.value = False
                await interaction.response.defer()
                self.stop()
            
            async def on_timeout(self):
                for item in self.children:
                    item.disabled = True
                if self.message:
                    await self.message.edit(content="Ticket close confirmation timed out.", view=self)

        original_message_sent = await ctx.send("Are you sure you want to close this ticket?")
        view = ConfirmView(ctx.author.id)
        await original_message_sent.edit(view=view)
        await view.wait()

        if view.value is True:
            task = ticket_timers.pop(ctx.channel.id, None)
            if task:
                task.cancel()

            ticket_creator_id = TICKET_CREATOR.pop(ctx.channel.id, "Unknown")
            ticket_creator_mention = f"<@{ticket_creator_id}>" if ticket_creator_id != "Unknown" else "Unknown User"

            await asyncio.sleep(1)
            await ctx.channel.delete(reason=f"Ticket closed by {ctx.author.name}")
            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(f"✅ Ticket `{ctx.channel.name}` (ID: {ctx.channel.id}) created by {ticket_creator_mention} has been **manually closed** by {ctx.author.mention}.")
            print(f"Manually closed ticket: {ctx.channel.name} ({ctx.channel.id})")
        elif view.value is False:
            await original_message_sent.edit(content="Ticket close canceled.", view=None)
        else:
            await original_message_sent.edit(content="Ticket close confirmation timed out.", view=None)

    else:
        await ctx.send("This command can only be used in ticket channels.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def ping(ctx):
    if ctx.channel.id in TICKET_CREATOR:
        user_id = TICKET_CREATOR[ctx.channel.id]
        user = ctx.guild.get_member(user_id)
        if user:
            try:
                await user.send(f"👋 {ctx.author.mention} asked you to check your ticket in {ctx.channel.mention}. Please review your ticket channel.")
                await ctx.send("✅ DM sent to the ticket creator to check the ticket!")
            except discord.Forbidden:
                await ctx.send("❌ I couldn't DM the user. They might have DMs disabled or blocked me.")
            except Exception as e:
                await ctx.send(f"❌ An error occurred while trying to DM the user: {e}")
        else:
            await ctx.send("❌ The ticket creator could not be found in this server.")
    else:
        await ctx.send("❌ No ticket creator data found for this channel.")

@bot.command()
async def pp(ctx):
    await ctx.send("💸 **PayPal**: https://www.paypal.com/paypalme/Hunter393?country.x=US&locale.x=en_US")

@bot.command()
async def cash(ctx):
    await ctx.send("💸 **Cash App**: https://cash.app/$Tripussy")

@bot.command()
async def ltc(ctx):
    await ctx.send("🚀 **Litecoin Address**: LeYqdR1y6EEASgV2Uf5oc1ABkeAHaMmjXx")

if __name__ == '__main__':
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Error: DISCORD_TOKEN environment variable not set. Please set it before running the bot.")
