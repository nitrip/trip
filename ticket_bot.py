import discord
from discord.ext import commands
import asyncio
import os
import sys
import traceback

# --- Configuration ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# IMPORTANT: These IDs are from your original script. Please VERIFY they are correct for your Discord server.
STAFF_ROLE_ID = 1376861623834247168
OWNER_ROLE_ID = 1368395196131442849
LOG_CHANNEL_ID = 1377208637029744641 # Used for logging closed/opened tickets

# This ID needs to be the ID of the Discord CATEGORY where you want new ticket channels to be created.
# This was not explicitly defined in your original snippet as a top-level variable,
# so you MUST ensure this is set to your desired category ID.
TICKET_PARENT_CATEGORY_ID = 1377208637029744641 # Placeholder: You might want a dedicated category for tickets.
                                             # Currently using LOG_CHANNEL_ID as a temporary example.

AUTO_CLOSE_TIME = 1800  # 30 minutes in seconds

# --- In-memory storage (consider persistence for production) ---
ticket_timers = {}  # Stores asyncio.Task objects for auto-closing
TICKET_CREATOR = {} # Maps channel ID to user ID of the ticket creator

# --- Ticket Categories and Emojis ---
# Emojis from your original script are integrated here.
CATEGORIES_DATA = {
    "claims": {"label": "Claims/Credits", "emoji_id": "<a:Gift:1368420677648121876>"},
    "boosts": {"label": "Server Boosts", "emoji_id": "<:servers:1368420678663297054>"},
    "premium": {"label": "Premium Upgrades", "emoji_id": "<a:Gold:1368420678977792010>"},
    "reseller": {"label": "Reseller", "emoji_id": "<:reseller:1368420678822557736>"}
}

# --- Event Listeners ---
@bot.event
async def on_ready():
    """Confirms when the bot successfully connects to Discord."""
    print(f'Bot {bot.user} is ready!')
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    print('------')

@bot.event
async def on_command_error(ctx, error):
    """Global error handler for commands."""
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
        # Log other unexpected errors for debugging
        print(f"Ignoring exception in command {ctx.command}:", file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
        await ctx.send("An unexpected error occurred while running this command.")

# --- Helper Functions ---
async def create_ticket_channel(guild, member, category_name, category_id):
    """Creates a new ticket channel in the specified category."""
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }

    staff_role = guild.get_role(STAFF_ROLE_ID)
    owner_role = guild.get_role(OWNER_ROLE_ID)
    if staff_role:
        overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    if owner_role:
        overwrites[owner_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    channel_name = f"ticket-{member.name.lower().replace(' ', '-')}-{category_name.lower().replace(' ', '-')}"
    category = discord.utils.get(guild.categories, id=category_id)

    if not category:
        print(f"Error: Category with ID {category_id} not found.")
        return None, "Error: Ticket category not found on the server. Please contact an administrator."

    try:
        channel = await guild.create_text_channel(channel_name, category=category, overwrites=overwrites)
        return channel, None
    except discord.Forbidden:
        return None, "Error: I don't have permission to create channels or set permissions in that category."
    except Exception as e:
        print(f"Error creating channel: {e}")
        return None, f"An unexpected error occurred while creating the channel: {e}"

async def auto_close_ticket(channel_id, guild_id):
    """Automatically closes a ticket after a specified time."""
    await asyncio.sleep(AUTO_CLOSE_TIME)
    try:
        guild = bot.get_guild(guild_id)
        if not guild:
            print(f"Guild {guild_id} not found for auto-close.")
            return

        channel = guild.get_channel(channel_id)
        if channel:
            log_channel = guild.get_channel(LOG_CHANNEL_ID)
            ticket_creator_id = TICKET_CREATOR.pop(channel_id, "Unknown")
            ticket_creator_mention = f"<@{ticket_creator_id}>" if ticket_creator_id != "Unknown" else "Unknown User"

            close_reason = "No activity for 30 minutes (auto-closed)."
            close_message = (
                f"This ticket has been automatically closed due to inactivity ({AUTO_CLOSE_TIME // 60} minutes).\n"
                f"Reason: {close_reason}\n"
                f"Ticket created by: {ticket_creator_mention}"
            )
            await channel.send(close_message)
            await channel.delete(reason=close_reason)

            if log_channel:
                await log_channel.send(
                    f"Ticket `{channel.name}` (ID: {channel_id}) created by {ticket_creator_mention} has been **auto-closed**."
                )
            print(f"Auto-closed ticket: {channel.name} ({channel_id})")
        else:
            print(f"Ticket channel {channel_id} not found for auto-close.")
    except discord.NotFound:
        print(f"Channel or message for {channel_id} not found during auto-close (already deleted?).")
    except Exception as e:
        print(f"Error during auto-close of ticket {channel_id}: {e}", file=sys.stderr)
        traceback.print_exc()

# --- Discord UI Views ---
class TicketCreateView(discord.ui.View):
    """View for selecting a ticket category."""
    def __init__(self):
        super().__init__(timeout=None) # Keep view persistent until bot restart

        for custom_id, data in CATEGORIES_DATA.items():
            button = discord.ui.Button(
                label=data["label"],
                custom_id=custom_id,
                emoji=data["emoji_id"]
            )
            self.add_item(button)

    @discord.ui.button(label="Open Ticket", style=discord.ButtonStyle.primary, custom_id="open_ticket_placeholder", row=0)
    async def open_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # This button is just a placeholder; actual logic is in on_interaction
        # We process the interaction for the category buttons.
        pass

    async def on_interaction(self, interaction: discord.Interaction):
        """Handles button clicks for ticket creation."""
        custom_id = interaction.data["custom_id"]
        if custom_id in CATEGORIES_DATA:
            category_data = CATEGORIES_DATA[custom_id]
            category_name = category_data["label"]

            # Check if user already has an open ticket of this type (optional)
            # You'd need more sophisticated tracking for this, e.g., in a database.
            for channel_id, creator_id in TICKET_CREATOR.items():
                if creator_id == interaction.user.id:
                    channel = interaction.guild.get_channel(channel_id)
                    if channel and category_name.lower().replace(' ', '-') in channel.name:
                        await interaction.response.send_message(
                            f"You already have an open ticket for {category_name}: {channel.mention}. Please close that one first.",
                            ephemeral=True
                        )
                        return

            await interaction.response.defer(ephemeral=True) # Acknowledge interaction

            channel, error_message = await create_ticket_channel(
                interaction.guild,
                interaction.user,
                category_name,
                TICKET_PARENT_CATEGORY_ID # Use the appropriate parent category ID
            )

            if channel:
                TICKET_CREATOR[channel.id] = interaction.user.id
                await channel.send(
                    f"Welcome {interaction.user.mention} to your ticket for **{category_name}**!\n"
                    f"A staff member will be with you shortly. "
                    f"This ticket will auto-close in {AUTO_CLOSE_TIME // 60} minutes if there's no activity."
                )
                log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
                if log_channel:
                    await log_channel.send(
                        f"Ticket `{channel.name}` opened by {interaction.user.mention} for category **{category_name}**."
                    )
                await interaction.followup.send(f"✅ Your ticket has been opened: {channel.mention}", ephemeral=True)

                # Start auto-close timer
                if channel.id in ticket_timers:
                    ticket_timers[channel.id].cancel() # Cancel existing timer if any
                ticket_timers[channel.id] = bot.loop.create_task(
                    auto_close_ticket(channel.id, interaction.guild.id)
                )
            else:
                await interaction.followup.send(error_message, ephemeral=True)
        else:
            await interaction.response.send_message("Invalid ticket category selected.", ephemeral=True)

class ConfirmView(discord.ui.View):
    """View for confirming ticket closure."""
    def __init__(self, original_message_id):
        super().__init__(timeout=60) # Timeout for the confirmation buttons
        self.value = None
        self.original_message_id = original_message_id # To delete the original message

    @discord.ui.button(label="Confirm Close", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        await interaction.response.defer() # Acknowledge the interaction
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.defer() # Acknowledge the interaction
        self.stop()

    async def on_timeout(self):
        # Disable buttons after timeout
        for item in self.children:
            item.disabled = True
        message = await self.message.channel.fetch_message(self.original_message_id)
        if message:
            await message.edit(content="Ticket close confirmation timed out.", view=self)

# --- Commands ---
@bot.command()
@commands.has_permissions(manage_channels=True)
async def setup(ctx):
    """Sets up the ticket creation message."""
    embed = discord.Embed(
        title="Support Ticket System",
        description=(
            "Click on a category button below to open a new support ticket.\n"
            f"Tickets will automatically close after {AUTO_CLOSE_TIME // 60} minutes of inactivity."
        ),
        color=discord.Color.purple() # Using discord.Color.purple() for a standard color
    )
    view = TicketCreateView()
    await ctx.send(embed=embed, view=view)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def close(ctx):
    """Closes the current ticket channel."""
    if ctx.channel.id in TICKET_CREATOR:
        original_message = await ctx.send("Are you sure you want to close this ticket?")
        view = ConfirmView(original_message.id)
        await original_message.edit(view=view) # Attach the view to the sent message
        await view.wait() # Wait for user interaction

        if view.value is True:
            # Stop any pending auto-close timer for this channel
            if ctx.channel.id in ticket_timers:
                ticket_timers[ctx.channel.id].cancel()
                del ticket_timers[ctx.channel.id]

            ticket_creator_id = TICKET_CREATOR.pop(ctx.channel.id, "Unknown")
            ticket_creator_mention = f"<@{ticket_creator_id}>" if ticket_creator_id != "Unknown" else "Unknown User"

            log_channel = ctx.guild.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(
                    f"Ticket `{ctx.channel.name}` (ID: {ctx.channel.id}) created by {ticket_creator_mention} has been **manually closed** by {ctx.author.mention}."
                )
            await ctx.channel.delete(reason=f"Ticket closed by {ctx.author.name}")
            print(f"Manually closed ticket: {ctx.channel.name} ({ctx.channel.id})")
        elif view.value is False:
            await original_message.edit(content="Ticket close canceled.", view=None) # Remove buttons
        else: # Timeout
            await original_message.edit(content="Ticket close confirmation timed out.", view=None) # Remove buttons
    else:
        await ctx.send("❌ This command can only be used in ticket channels.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def ping(ctx):
    """Pings the ticket creator to check their ticket."""
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
    """Sends the PayPal link."""
    await ctx.send("💸 **PayPal**: https://www.paypal.com/paypalme/Hunter393?country.x=US&locale.x=en_US")

@bot.command()
async def cash(ctx):
    """Sends the Cash App link."""
    await ctx.send("💸 **Cash App**: https://cash.app/$Tripussy")

# --- Run the bot ---
if __name__ == '__main__':
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Error: DISCORD_TOKEN environment variable not set. Please set it before running the bot.")
