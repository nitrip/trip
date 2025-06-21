import discord
from discord.ext import commands
import asyncio
import os
import sys
import traceback
import json

# --- Configuration ---
# It's highly recommended to use environment variables or a separate config file
# for sensitive information and configurable parameters in a production environment.
STAFF_ROLE_ID = 1376861623834247168
OWNER_ROLE_ID = 1368395196131442849
LOG_CHANNEL_ID = 1377208637029744641
AUTO_CLOSE_TIME = 1800  # 30 minutes in seconds

# Persistent storage for active tickets
TICKET_DATA_FILE = 'ticket_data.json'
TICKET_CREATOR = {}  # This will be loaded from/saved to TICKET_DATA_FILE
ticket_timers = {}  # In-memory for active auto-close tasks

# Define your categories with labels, emojis, and button styles.
CATEGORIES_DATA = {
    "claims": {"label": "Claims/Credits", "emoji_id": "<a:Gift:1368420677648121876>", "style": discord.ButtonStyle.success},
    "boosts": {"label": "Server Boosts", "emoji_id": "<a:NitroBooster:1368420767577931836>", "style": discord.ButtonStyle.primary},
    "premium": {"label": "Premium Upgrades", "emoji_id": "<:upvote:1376850180644667462>", "style": discord.ButtonStyle.secondary},
    "aged_acc": {"label": "Aged Accounts", "emoji_id": "<:Box:1375787598240284804>", "style": discord.ButtonStyle.secondary},
    "others": {"label": "Others", "emoji_id": "<:shopping_cart_green12:1376614180869898311>", "style": discord.ButtonStyle.secondary}
}

# Payment methods configuration
PAYMENT_METHODS = {
    "paypal": {
        "label": "PayPal",
        "emoji": "<:Paypal:1374290794340548619>",
        "link": "https://www.paypal.com/paypalme/Hunter393?country.x=US&locale.x=en_US",
        "style": discord.ButtonStyle.primary  # Blue
    },
    "cashapp": {
        "label": "Cash App", 
        "emoji": "<:PurpleCashApp:1374290682835107892>",
        "link": "https://cash.app/$Tripussy",
        "style": discord.ButtonStyle.success  # Green
    },
    "litecoin": {
        "label": "Litecoin (LTC)",
        "emoji": "<:emojigg_ltc:1374291116966412348>",
        "link": "LeYqdR1y6EEASgV2Uf5oc1ABkeAHaMmjXx",
        "style": discord.ButtonStyle.secondary  # Black/Gray
    },
    "solana": {
        "label": "Solana (SOL)",
        "emoji": "<:emojigg_SOL:1378135240056246382>",
        "link": "Dahr82ChqvzB7Rgcq4F8x1XCrLjJojRPXdJfrsHcfhwr",
        "style": discord.ButtonStyle.secondary  # Black/Gray
    }
}

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Required for fetching members and their roles reliably
bot = commands.Bot(command_prefix='!', intents=intents)

# --- Helper function to update bot status ---
async def update_bot_status():
    """Updates the bot's status to show how many tickets it's watching."""
    ticket_count = len(TICKET_CREATOR)
    if ticket_count == 0:
        activity = discord.Activity(type=discord.ActivityType.watching, name="for new tickets")
    elif ticket_count == 1:
        activity = discord.Activity(type=discord.ActivityType.watching, name="1 ticket")
    else:
        activity = discord.Activity(type=discord.ActivityType.watching, name=f"{ticket_count} tickets")
    
    await bot.change_presence(activity=activity)

# --- Helper Functions for Persistence ---
def load_ticket_data():
    """Loads ticket data from the JSON file into TICKET_CREATOR."""
    global TICKET_CREATOR
    if os.path.exists(TICKET_DATA_FILE):
        with open(TICKET_DATA_FILE, 'r') as f:
            try:
                TICKET_CREATOR = json.load(f)
                # Convert string keys (channel IDs from JSON) back to int for consistent use
                TICKET_CREATOR = {int(k): v for k, v in TICKET_CREATOR.items()}
                print(f"Loaded ticket data: {TICKET_CREATOR}")
            except json.JSONDecodeError:
                print("Error decoding ticket_data.json, starting with empty data.")
                TICKET_CREATOR = {}
    else:
        TICKET_CREATOR = {}

def save_ticket_data():
    """Saves current ticket data from TICKET_CREATOR to the JSON file."""
    with open(TICKET_DATA_FILE, 'w') as f:
        # Convert int keys (channel IDs) to string for JSON serialization
        json.dump({str(k): v for k, v in TICKET_CREATOR.items()}, f, indent=4)
        print(f"Saved ticket data: {TICKET_CREATOR}")
    
    # Update bot status after saving data
    asyncio.create_task(update_bot_status())

# --- Payment Methods View ---
class PaymentMethodsView(discord.ui.View):
    """A view for displaying payment method buttons."""
    
    def __init__(self):
        super().__init__(timeout=None)
        
        # Add payment method buttons
        for method_id, method_data in PAYMENT_METHODS.items():
            button = discord.ui.Button(
                label=method_data["label"],
                emoji=method_data["emoji"],
                style=method_data["style"],
                custom_id=f"payment_{method_id}"
            )
            
            # Create a proper callback function with closure
            def make_callback(method_link):
                async def payment_callback(interaction):
                    await interaction.response.send_message(method_link, ephemeral=True)
                return payment_callback
            
            button.callback = make_callback(method_data["link"])
            self.add_item(button)

# --- Ticket Control View ---
class TicketControlView(discord.ui.View):
    """A view for ticket control buttons (close and payment methods)."""
    
    def __init__(self):
        super().__init__(timeout=None)
        
        # Close ticket button
        close_button = discord.ui.Button(
            label="Close Ticket", 
            style=discord.ButtonStyle.danger, 
            custom_id="close_ticket_button", 
            emoji="🔒"
        )
        close_button.callback = self.close_ticket_callback
        self.add_item(close_button)
        
        # Payment methods button
        payment_button = discord.ui.Button(
            label="Payment Methods",
            style=discord.ButtonStyle.secondary,
            custom_id="payment_methods_button",
            emoji="💳"
        )
        payment_button.callback = self.payment_methods_callback
        self.add_item(payment_button)
    
    async def close_ticket_callback(self, interaction: discord.Interaction):
        """Handles the close ticket button click."""
        # Check if user has any of the required roles, not just top role
        member = interaction.guild.get_member(interaction.user.id)
        is_staff_or_owner = any(role.id in [STAFF_ROLE_ID, OWNER_ROLE_ID] for role in member.roles)
        is_ticket_creator_user = TICKET_CREATOR.get(interaction.channel.id) == interaction.user.id

        if is_ticket_creator_user or is_staff_or_owner:
            await interaction.response.send_message("🔒 Closing ticket... Starting countdown to deletion.", ephemeral=True)
            
            # Cancel auto-close timer
            task = ticket_timers.pop(interaction.channel.id, None)
            if task:
                task.cancel()
            
            # Create transcript before deletion
            await create_transcript(interaction.channel, interaction.user)
            
            # 10-second countdown
            countdown_embed = discord.Embed(
                title="🔒 Ticket Closed",
                description=f"This ticket has been closed by {interaction.user.mention}.\n\n**⏱️ Deleting in 10 seconds...**",
                color=discord.Color.red()
            )
            countdown_message = await interaction.channel.send(embed=countdown_embed)
            
            # Update countdown every second
            for i in range(9, 0, -1):
                await asyncio.sleep(1)
                countdown_embed.description = f"This ticket has been closed by {interaction.user.mention}.\n\n**⏱️ Deleting in {i} seconds...**"
                try:
                    await countdown_message.edit(embed=countdown_embed)
                except:
                    break  # Message might be deleted or channel gone
            
            await asyncio.sleep(1)
            
            # Final cleanup and deletion
            ticket_creator_id_val = TICKET_CREATOR.pop(interaction.channel.id, "Unknown")
            save_ticket_data()
            ticket_creator_mention = f"<@{ticket_creator_id_val}>" if ticket_creator_id_val != "Unknown" else "Unknown User"
            
            # Log the deletion
            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                embed = discord.Embed(
                    title="✅ Ticket Closed and Deleted",
                    description=f"Ticket `{interaction.channel.name}` has been closed and deleted.",
                    color=discord.Color.green()
                )
                embed.add_field(name="Created By", value=ticket_creator_mention, inline=True)
                embed.add_field(name="Closed By", value=interaction.user.mention, inline=True)
                embed.add_field(name="Closure Method", value="Button + Auto-Delete", inline=True)
                await log_channel.send(embed=embed)
            
            await interaction.channel.delete(reason=f"Ticket closed by {interaction.user.name} - auto-deleted after 10s countdown")
            print(f"Closed and deleted ticket: {interaction.channel.name} ({interaction.channel.id}) by {interaction.user.name}")
        else:
            await interaction.response.send_message("You are not authorized to close this ticket.", ephemeral=True)
    
    async def payment_methods_callback(self, interaction: discord.Interaction):
        """Handles the payment methods button click."""
        embed = discord.Embed(
            title="💳 Payment Methods",
            description="Choose your preferred payment method below:",
            color=discord.Color.blue()
        )
        
        payment_view = PaymentMethodsView()
        await interaction.response.send_message(embed=embed, view=payment_view, ephemeral=True)

# --- Core Ticket Management Function ---
async def create_new_ticket(guild: discord.Guild, user: discord.Member, category_id_key: str):
    """
    Handles the creation of a new ticket channel.

    Args:
        guild (discord.Guild): The guild where the ticket is being created.
        user (discord.Member): The user for whom the ticket is being created.
        category_id_key (str): The key from CATEGORIES_DATA for the ticket category.

    Returns:
        tuple: A tuple containing (discord.TextChannel, str) if successful,
               otherwise (None, str) with an error message.
    """
    category_label = CATEGORIES_DATA[category_id_key]["label"]
    log_channel = bot.get_channel(LOG_CHANNEL_ID)

    # Check for existing tickets by the user within the specific category
    for channel_id, creator_id in TICKET_CREATOR.items():
        if creator_id == user.id:
            existing_channel = guild.get_channel(channel_id)
            if existing_channel and existing_channel.category and existing_channel.category.name == "Tickets":
                channel_name_parts = existing_channel.name.split('-')
                if channel_name_parts and channel_name_parts[0] == category_id_key:
                    return None, f"You already have an open ticket in the '{category_label}' category: {existing_channel.mention}. Please close that one first."

    # Find or create "Tickets" category
    ticket_category = discord.utils.get(guild.categories, name="Tickets")
    if ticket_category is None:
        try:
            ticket_category = await guild.create_category("Tickets", overwrites={
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            })
            if log_channel:
                embed = discord.Embed(
                    title="🆕 New Ticket Category Created",
                    description=f"Created new ticket category: {ticket_category.mention}",
                    color=discord.Color.blue()
                )
                await log_channel.send(embed=embed)
        except discord.Forbidden:
            return None, "I don't have permission to create categories. Please contact an administrator."
        except Exception as e:
            print(f"Error creating ticket category: {e}", file=sys.stderr)
            traceback.print_exc()
            return None, f"An error occurred creating the ticket category: {e}"

    # Create ticket channel
    channel_name_base = f"{category_id_key}-{user.display_name}".replace(" ", "-").lower()
    channel_name = channel_name_base
    counter = 0
    while discord.utils.get(ticket_category.channels, name=channel_name):
        counter += 1
        channel_name = f"{channel_name_base}-{counter}"

    try:
        channel = await ticket_category.create_text_channel(channel_name)

        # Set permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, embed_links=True, attach_files=True),
            guild.get_role(OWNER_ROLE_ID): discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        await channel.edit(overwrites=overwrites)

        TICKET_CREATOR[channel.id] = user.id
        save_ticket_data()

        # Ticket initial message (removed payment methods from embed)
        embed = discord.Embed(
            title=f"Welcome to your {category_label} Ticket!",
            description=(
                f"{user.mention} has opened a ticket. <@&{STAFF_ROLE_ID}>, please assist! 🛠️\n\n"
                f"📌 **Please describe your issue or request in detail.**\n"
                f"When communicating, please be clear and provide all necessary information."
            ),
            color=discord.Color.blue()
        )
        embed.set_footer(text="A staff member will assist you shortly. Thank you for your patience! 💙")

        # Create the ticket control view with close and payment buttons
        ticket_view = TicketControlView()
        await channel.send(embed=embed, view=ticket_view)

        if log_channel:
            embed = discord.Embed(
                title="📂 Ticket Opened",
                description=f"A new ticket has been opened: {channel.mention}",
                color=discord.Color.green()
            )
            embed.add_field(name="Ticket Creator", value=user.mention, inline=True)
            embed.add_field(name="Category", value=category_label, inline=True)
            embed.add_field(name="Channel Name", value=channel.name, inline=False)
            await log_channel.send(embed=embed)

        # Start auto-close timer
        task = asyncio.create_task(auto_close_ticket(channel.id, guild.id))
        ticket_timers[channel.id] = task

        return channel, None

    except discord.Forbidden:
        return None, "I don't have permission to create channels in that category or set permissions. Please contact an administrator."
    except Exception as e:
        print(f"Error creating ticket channel: {e}", file=sys.stderr)
        traceback.print_exc()
        return None, f"An unexpected error occurred: {e}"

# --- Bot Events ---
@bot.event
async def on_ready():
    """Event that fires when the bot is ready."""
    print(f'Bot {bot.user} is ready!')
    load_ticket_data()  # Load data on startup
    
    # Update bot status on startup
    await update_bot_status()
    
    # Re-launch auto-close timers for existing tickets
    for channel_id, creator_id in TICKET_CREATOR.items():
        guild_id = None
        for guild in bot.guilds:
            if guild.get_channel(channel_id):
                guild_id = guild.id
                break
        if guild_id:
            print(f"Restarting timer for ticket channel {channel_id} in guild {guild_id}")
            task = asyncio.create_task(auto_close_ticket(channel_id, guild_id))
            ticket_timers[channel_id] = task
        else:
            print(f"Could not find guild for channel {channel_id}. Skipping timer restart and cleaning up.")
            TICKET_CREATOR.pop(channel_id, None)
            save_ticket_data()

@bot.event
async def on_command_error(ctx, error):
    """Global command error handler."""
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
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Member not found. Please provide a valid user or ID.")
    else:
        print(f"Ignoring exception in command {ctx.command}:", file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
        await ctx.send("An unexpected error occurred while running this command. Check the console for details.")

# --- Setup Command ---
@bot.command()
@commands.has_permissions(manage_channels=True)
async def setup(ctx):
    """Sets up the ticket system message with category buttons."""
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
            emoji=data["emoji_id"],
            style=data["style"]
        )
        view.add_item(button)

    try:
        await ctx.send(embed=embed, view=view)
        await ctx.message.delete()
    except discord.Forbidden:
        await ctx.author.send("I don't have permission to send messages in that channel or delete commands. Please check my permissions.")
    except Exception as e:
        await ctx.send(f"An error occurred during setup: {e}")
        print(f"Error during setup command: {e}", file=sys.stderr)
        traceback.print_exc()

# --- Premium Upgrade Form Modal ---
class PremiumUpgradeModal(discord.ui.Modal):
    """Modal form for premium upgrade ticket details."""
    
    def __init__(self):
        super().__init__(title="Premium Upgrade Details")
        
        # Service type
        self.service_type = discord.ui.TextInput(
            label="Service (YouTube or Spotify)",
            placeholder="Enter YouTube or Spotify",
            required=False,
            max_length=50
        )
        self.add_item(self.service_type)
        
        # Payment method
        self.payment_method = discord.ui.TextInput(
            label="Payment Method",
            placeholder="PayPal, Cash App, Litecoin, Solana, or Other",
            required=False,
            max_length=50
        )
        self.add_item(self.payment_method)
        
        # Additional details
        self.additional_details = discord.ui.TextInput(
            label="Additional Details (Optional)",
            placeholder="Any specific requirements or questions...",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )
        self.add_item(self.additional_details)
    
    async def on_submit(self, interaction: discord.Interaction):
        # Create the ticket
        guild = interaction.guild
        user = interaction.user
        
        channel, error_message = await create_new_ticket(guild, user, "premium")
        
        if channel:
            # Send the form details to the ticket channel
            details_embed = discord.Embed(
                title="<:Aired:1378505206182051850> Premium Upgrade Request Details",
                color=discord.Color.blue()
            )
            
            if self.service_type.value:
                service = self.service_type.value.lower().strip()
                if "youtube" in service:
                    service_formatted = "YouTube Premium"
                elif "spotify" in service:
                    service_formatted = "Spotify Premium"
                else:
                    service_formatted = self.service_type.value
                details_embed.add_field(name="Service", value=service_formatted, inline=True)
            
            if self.payment_method.value:
                details_embed.add_field(name="Payment Method", value=self.payment_method.value, inline=True)
            
            details_embed.add_field(name="Requested By", value=user.mention, inline=True)
            
            if self.additional_details.value:
                details_embed.add_field(name="Additional Details", value=self.additional_details.value, inline=False)
            
            await channel.send(embed=details_embed)
            await interaction.response.send_message(f"✅ Your premium upgrade ticket has been opened: {channel.mention}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {error_message}", ephemeral=True)

# --- Server Boost Form Modal ---
class ServerBoostModal(discord.ui.Modal):
    """Modal form for server boost ticket details."""
    
    def __init__(self):
        super().__init__(title="Server Boost Details")
        
        # Boost duration
        self.boost_duration = discord.ui.TextInput(
            label="Boost Duration (1 or 3 months)",
            placeholder="Enter 1 or 3",
            required=False,
            max_length=10
        )
        self.add_item(self.boost_duration)
        
        # Payment method
        self.payment_method = discord.ui.TextInput(
            label="Payment Method",
            placeholder="PayPal, Cash App, Litecoin, Solana, or Other",
            required=False,
            max_length=50
        )
        self.add_item(self.payment_method)
        
        # Server link (optional)
        self.server_link = discord.ui.TextInput(
            label="Server Link (Optional)",
            placeholder="https://discord.gg/yourserver or leave blank",
            required=False,
            max_length=200
        )
        self.add_item(self.server_link)
        
        # Additional details
        self.additional_details = discord.ui.TextInput(
            label="Additional Details (Optional)",
            placeholder="Any specific requirements or questions...",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )
        self.add_item(self.additional_details)
    
    async def on_submit(self, interaction: discord.Interaction):
        # Create the ticket
        guild = interaction.guild
        user = interaction.user
        
        channel, error_message = await create_new_ticket(guild, user, "boosts")
        
        if channel:
            # Send the form details to the ticket channel
            details_embed = discord.Embed(
                title="<:Aired:1378505206182051850> Server Boost Request Details",
                color=discord.Color.blue()
            )
            
            if self.boost_duration.value:
                duration = self.boost_duration.value.strip()
                if duration in ["1", "3"]:
                    duration_text = f"{duration} month{'s' if duration == '3' else ''}"
                else:
                    duration_text = self.boost_duration.value
                details_embed.add_field(name="Boost Duration", value=duration_text, inline=True)
            
            if self.payment_method.value:
                details_embed.add_field(name="Payment Method", value=self.payment_method.value, inline=True)
            
            details_embed.add_field(name="Requested By", value=user.mention, inline=True)
            
            if self.server_link.value:
                details_embed.add_field(name="Server Link", value=self.server_link.value, inline=False)
            
            if self.additional_details.value:
                details_embed.add_field(name="Additional Details", value=self.additional_details.value, inline=False)
            
            await channel.send(embed=details_embed)
            await interaction.response.send_message(f"✅ Your server boost ticket has been opened: {channel.mention}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {error_message}", ephemeral=True)

# --- Claims Form Modal ---
class ClaimsModal(discord.ui.Modal):
    """Modal form for claims/credits ticket details."""
    
    def __init__(self):
        super().__init__(title="Claims/Credits Details")
        
        # Number of claims
        self.claims_count = discord.ui.TextInput(
            label="How many claims do you need?",
            placeholder="Enter number (e.g., 5)",
            required=False,
            max_length=10
        )
        self.add_item(self.claims_count)
        
        # Payment method
        self.payment_method = discord.ui.TextInput(
            label="Payment Method",
            placeholder="PayPal, Cash App, Litecoin, Solana, or Other",
            required=False,
            max_length=50
        )
        self.add_item(self.payment_method)
        
        # Additional details
        self.additional_details = discord.ui.TextInput(
            label="Additional Details (Optional)",
            placeholder="Any specific requirements or questions...",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )
        self.add_item(self.additional_details)
    
    async def on_submit(self, interaction: discord.Interaction):
        # Create the ticket
        guild = interaction.guild
        user = interaction.user
        
        channel, error_message = await create_new_ticket(guild, user, "claims")
        
        if channel:
            # Send the form details to the ticket channel
            details_embed = discord.Embed(
                title="<:Aired:1378505206182051850> Claims/Credits Request Details",
                color=discord.Color.blue()
            )
            
            if self.claims_count.value:
                try:
                    claims_num = int(self.claims_count.value)
                    if claims_num > 0:
                        details_embed.add_field(name="Number of Claims", value=str(claims_num), inline=True)
                    else:
                        details_embed.add_field(name="Number of Claims", value=self.claims_count.value, inline=True)
                except ValueError:
                    details_embed.add_field(name="Number of Claims", value=self.claims_count.value, inline=True)
            
            if self.payment_method.value:
                details_embed.add_field(name="Payment Method", value=self.payment_method.value, inline=True)
            
            details_embed.add_field(name="Requested By", value=user.mention, inline=True)
            
            if self.additional_details.value:
                details_embed.add_field(name="Additional Details", value=self.additional_details.value, inline=False)
            
            await channel.send(embed=details_embed)
            await interaction.response.send_message(f"✅ Your claims/credits ticket has been opened: {channel.mention}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {error_message}", ephemeral=True)

# --- Aged Account Form Modal ---
class AgedAccountModal(discord.ui.Modal):
    """Modal form for aged account ticket details."""
    
    def __init__(self):
        super().__init__(title="Aged Account Details")
        
        # Year selection
        self.year_select = discord.ui.TextInput(
            label="Account Year (2015-2020)",
            placeholder="Enter the year (e.g., 2017)",
            required=False,
            max_length=10
        )
        self.add_item(self.year_select)
        
        # Nitro status
        self.nitro_select = discord.ui.TextInput(
            label="Nitro Status",
            placeholder="Type 'with nitro' or 'without nitro'",
            required=False,
            max_length=50
        )
        self.add_item(self.nitro_select)
        
        # Additional details
        self.additional_details = discord.ui.TextInput(
            label="Additional Details (Optional)",
            placeholder="Any specific requirements or questions...",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )
        self.add_item(self.additional_details)
    
    async def on_submit(self, interaction: discord.Interaction):
        # Create the ticket
        guild = interaction.guild
        user = interaction.user
        
        channel, error_message = await create_new_ticket(guild, user, "aged_acc")
        
        if channel:
            # Send the form details to the ticket channel
            details_embed = discord.Embed(
                title="<:emoji_1736873097239:1385896691642929243> Aged Account Request Details",
                color=discord.Color.blue()
            )
            
            if self.year_select.value:
                try:
                    year = int(self.year_select.value)
                    if 2015 <= year <= 2020:
                        details_embed.add_field(name="Account Year", value=str(year), inline=True)
                    else:
                        details_embed.add_field(name="Account Year", value=self.year_select.value, inline=True)
                except ValueError:
                    details_embed.add_field(name="Account Year", value=self.year_select.value, inline=True)
            
            if self.nitro_select.value:
                nitro_status = self.nitro_select.value.lower().strip()
                if "with" in nitro_status and "nitro" in nitro_status:
                    nitro_formatted = "With Nitro"
                elif "without" in nitro_status and "nitro" in nitro_status:
                    nitro_formatted = "Without Nitro"
                else:
                    nitro_formatted = self.nitro_select.value
                details_embed.add_field(name="Nitro Status", value=nitro_formatted, inline=True)
            
            details_embed.add_field(name="Requested By", value=user.mention, inline=True)
            
            if self.additional_details.value:
                details_embed.add_field(name="Additional Details", value=self.additional_details.value, inline=False)
            
            await channel.send(embed=details_embed)
            await interaction.response.send_message(f"✅ Your aged account ticket has been opened: {channel.mention}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {error_message}", ephemeral=True)

# --- Interaction Handling (Ticket Creation via Button) ---
@bot.event
async def on_interaction(interaction):
    """Handles interactions, specifically button clicks for ticket creation."""
    if interaction.type == discord.InteractionType.component and interaction.data['custom_id'] in CATEGORIES_DATA:
        category_id_key = interaction.data['custom_id']
        guild = interaction.guild
        user = interaction.user

        if not guild:
            await interaction.response.send_message("This action can only be performed in a server.", ephemeral=True)
            return

        # Special handling for specific categories with forms
        if category_id_key == "aged_acc":
            modal = AgedAccountModal()
            await interaction.response.send_modal(modal)
            return
        elif category_id_key == "claims":
            modal = ClaimsModal()
            await interaction.response.send_modal(modal)
            return
        elif category_id_key == "boosts":
            modal = ServerBoostModal()
            await interaction.response.send_modal(modal)
            return
        elif category_id_key == "premium":
            modal = PremiumUpgradeModal()
            await interaction.response.send_modal(modal)
            return
        
        # Regular ticket creation for other categories
        channel, error_message = await create_new_ticket(guild, user, category_id_key)

        if channel:
            await interaction.response.send_message(f"✅ Your ticket has been opened: {channel.mention}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {error_message}", ephemeral=True)

# --- New Ticket Command ---
@bot.command()
@commands.has_permissions(manage_channels=True)
async def openticket(ctx, member: discord.Member, category_key: str):
    """
    Opens a new ticket for a specified member in a given category.
    Usage: !openticket <@member> <category_key>
    Example: !openticket @User claims
    """
    if category_key not in CATEGORIES_DATA:
        available_categories = ", ".join(CATEGORIES_DATA.keys())
        await ctx.send(f"❌ Invalid category key. Available categories: {available_categories}")
        return

    # Check if the command is used in a guild
    if not ctx.guild:
        await ctx.send("This command can only be used in a server.")
        return

    channel, error_message = await create_new_ticket(ctx.guild, member, category_key)

    if channel:
        await ctx.send(f"✅ Ticket opened for {member.mention}: {channel.mention}")
    else:
        await ctx.send(f"❌ Could not open ticket for {member.mention}: {error_message}")

# --- Auto-Close Function ---
async def auto_close_ticket(channel_id, guild_id):
    """Automatically closes a ticket after a period of inactivity."""
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    try:
        await asyncio.sleep(AUTO_CLOSE_TIME)
        guild = bot.get_guild(guild_id)
        if not guild:
            print(f"Guild {guild_id} not found for auto-close task. Ticket {channel_id} might be from a removed guild. Cleaning up data.")
            TICKET_CREATOR.pop(channel_id, None)
            save_ticket_data()
            return

        channel = guild.get_channel(channel_id)
        if channel:
            messages = []
            async for msg in channel.history(limit=5, oldest_first=False):
                messages.append(msg)

            user_messages = [msg for msg in messages if msg.author != bot.user]

            if not user_messages:
                ticket_creator_id_val = TICKET_CREATOR.pop(channel.id, "Unknown")
                save_ticket_data()
                ticket_creator_mention = f"<@{ticket_creator_id_val}>" if ticket_creator_id_val != "Unknown" else "Unknown User"

                close_reason = f"No activity for {AUTO_CLOSE_TIME // 60} minutes (auto-closed)."

                await create_transcript(channel, bot.user, auto_closed=True)

                close_message = (
                    f"This ticket has been automatically closed due to inactivity ({AUTO_CLOSE_TIME // 60} minutes).\n"
                    f"Reason: {close_reason}\n"
                    f"Ticket created by: {ticket_creator_mention}"
                )
                await channel.send(close_message)
                await asyncio.sleep(5)
                await channel.delete(reason=close_reason)

                if log_channel:
                    embed = discord.Embed(
                        title="❌ Ticket Auto-Closed",
                        description=f"Ticket `{channel.name}` has been auto-closed due to inactivity.",
                        color=discord.Color.red()
                    )
                    embed.add_field(name="Created By", value=ticket_creator_mention, inline=True)
                    embed.add_field(name="Reason", value=close_reason, inline=False)
                    embed.add_field(name="Ticket Creator User ID", value=ticket_creator_id_val, inline=False)
                    await log_channel.send(embed=embed)
                print(f"Auto-closed ticket: {channel.name} ({channel.id})")
            else:
                print(f"Ticket {channel.name} has activity, resetting auto-close timer.")
                task = asyncio.create_task(auto_close_ticket(channel.id, guild.id))
                ticket_timers[channel.id] = task
        else:
            print(f"Ticket channel {channel_id} not found for auto-close (might have been deleted manually or bot restarted). Cleaning up data.")
            TICKET_CREATOR.pop(channel_id, None)
            save_ticket_data()
    except asyncio.CancelledError:
        print(f"Auto-close task for channel {channel_id} was cancelled.")
        TICKET_CREATOR.pop(channel_id, None)
        save_ticket_data()
    except discord.NotFound:
        print(f"Channel or message for {channel_id} not found during auto-close (already deleted?). Cleaning up data.")
        TICKET_CREATOR.pop(channel_id, None)
        save_ticket_data()
    except Exception as e:
        print(f"Error during auto-close of ticket {channel_id}: {e}", file=sys.stderr)
        traceback.print_exc()
    finally:
        ticket_timers.pop(channel_id, None)

# --- Close Command View ---
class ConfirmView(discord.ui.View):
    """A view for confirming ticket closure."""
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

# --- Close Command ---
@bot.command()
@commands.has_permissions(manage_channels=True)
async def close(ctx):
    """Closes the current ticket channel."""
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if ctx.channel.category and ctx.channel.category.name == "Tickets":
        staff_role = ctx.guild.get_role(STAFF_ROLE_ID)
        owner_role = ctx.guild.get_role(OWNER_ROLE_ID)
        is_staff_or_owner = staff_role in ctx.author.roles or owner_role in ctx.author.roles
        is_ticket_creator = TICKET_CREATOR.get(ctx.channel.id) == ctx.author.id

        if not (is_staff_or_owner or is_ticket_creator):
            await ctx.send("❌ You do not have permission to close this ticket.")
            return

        original_message_sent = await ctx.send(f"Are you sure you want to close this ticket?")
        view = ConfirmView(ctx.author.id)
        await original_message_sent.edit(view=view)
        await view.wait()

        if view.value is True:
            task = ticket_timers.pop(ctx.channel.id, None)
            if task:
                task.cancel()

            # Create transcript before deletion
            await create_transcript(ctx.channel, ctx.author)
            
            # 10-second countdown
            countdown_embed = discord.Embed(
                title="🔒 Ticket Closed",
                description=f"This ticket has been closed by {ctx.author.mention}.\n\n**⏱️ Deleting in 10 seconds...**",
                color=discord.Color.red()
            )
            countdown_message = await ctx.channel.send(embed=countdown_embed)
            
            # Update countdown every second
            for i in range(9, 0, -1):
                await asyncio.sleep(1)
                countdown_embed.description = f"This ticket has been closed by {ctx.author.mention}.\n\n**⏱️ Deleting in {i} seconds...**"
                try:
                    await countdown_message.edit(embed=countdown_embed)
                except:
                    break  # Message might be deleted or channel gone
            
            await asyncio.sleep(1)
            
            # Final cleanup and deletion
            ticket_creator_id_val = TICKET_CREATOR.pop(ctx.channel.id, "Unknown")
            save_ticket_data()
            ticket_creator_mention = f"<@{ticket_creator_id_val}>" if ticket_creator_id_val != "Unknown" else "Unknown User"

            # Delete the channel
            await ctx.channel.delete(reason=f"Ticket closed by {ctx.author.name} - auto-deleted after 10s countdown")

            if log_channel:
                embed = discord.Embed(
                    title="✅ Ticket Closed and Deleted",
                    description=f"Ticket `{ctx.channel.name}` has been closed and deleted.",
                    color=discord.Color.green()
                )
                embed.add_field(name="Created By", value=ticket_creator_mention, inline=True)
                embed.add_field(name="Closed By", value=ctx.author.mention, inline=True)
                embed.add_field(name="Closure Method", value="Command + Auto-Delete", inline=True)
                await log_channel.send(embed=embed)
            print(f"Closed and deleted ticket: {ctx.channel.name} ({ctx.channel.id}) by {ctx.author.name}")
        elif view.value is False:
            await original_message_sent.edit(content="Ticket close canceled.", view=None)
        else:
            await original_message_sent.edit(content="Ticket close confirmation timed out.", view=None)
    else:
        await ctx.send("This command can only be used in ticket channels.")

# --- Add User to Ticket Command ---
@bot.command()
@commands.has_permissions(manage_channels=True)
async def add(ctx, member: discord.Member):
    """Adds a specified member to the current ticket channel."""
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if ctx.channel.category and ctx.channel.category.name == "Tickets":
        try:
            await ctx.channel.set_permissions(member, read_messages=True, send_messages=True, embed_links=True, attach_files=True)
            await ctx.send(f"✅ {member.mention} has been added to this ticket.")
            if log_channel:
                embed = discord.Embed(
                    title="➕ User Added to Ticket",
                    description=f"{member.mention} has been added to {ctx.channel.mention}.",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Action By", value=ctx.author.mention, inline=True)
                embed.add_field(name="Ticket Channel", value=ctx.channel.name, inline=True)
                await log_channel.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to add users to this channel.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {e}")
            print(f"Error adding user to ticket: {e}", file=sys.stderr)
            traceback.print_exc()
    else:
        await ctx.send("❌ This command can only be used in ticket channels.")

# --- Remove User from Ticket Command ---
@bot.command()
@commands.has_permissions(manage_channels=True)
async def remove(ctx, member: discord.Member):
    """Removes a specified member from the current ticket channel."""
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if ctx.channel.category and ctx.channel.category.name == "Tickets":
        member_is_staff = any(role.id == STAFF_ROLE_ID for role in member.roles)
        member_is_owner = any(role.id == OWNER_ROLE_ID for role in member.roles)

        if member_is_staff or member_is_owner or TICKET_CREATOR.get(ctx.channel.id) == member.id:
            await ctx.send("❌ You cannot remove a staff member, owner, or the original ticket creator from the ticket using this command.")
            return

        try:
            await ctx.channel.set_permissions(member, read_messages=False, send_messages=False)
            await ctx.send(f"✅ {member.mention} has been removed from this ticket.")
            if log_channel:
                embed = discord.Embed(
                    title="➖ User Removed from Ticket",
                    description=f"{member.mention} has been removed from {ctx.channel.mention}.",
                    color=discord.Color.orange()
                )
                embed.add_field(name="Action By", value=ctx.author.mention, inline=True)
                embed.add_field(name="Ticket Channel", value=ctx.channel.name, inline=True)
                await log_channel.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to remove users from this channel.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {e}")
            print(f"Error removing user from ticket: {e}", file=sys.stderr)
            traceback.print_exc()
    else:
        await ctx.send("❌ This command can only be used in ticket channels.")

# --- Transcript Function ---
async def create_transcript(channel, closer, auto_closed=False):
    """Creates a transcript of the ticket channel and sends it to the log channel."""
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if not log_channel:
        print("Log channel not found for transcript.")
        return

    if not bot.get_channel(channel.id):
        print(f"Channel {channel.id} no longer exists, cannot create transcript.")
        return

    transcript_content = []
    transcript_content.append(f"--- Ticket Transcript for #{channel.name} (ID: {channel.id}) ---")
    ticket_creator_id_val = TICKET_CREATOR.get(channel.id)
    if ticket_creator_id_val:
        creator_member = channel.guild.get_member(ticket_creator_id_val)
        creator_name = creator_member.display_name if creator_member else f"Unknown User (ID: {ticket_creator_id_val})"
        transcript_content.append(f"Opened by: {creator_name} (ID: {ticket_creator_id_val})")
    else:
        transcript_content.append(f"Opened by: Unknown User (ID not found in TICKET_CREATOR)")

    transcript_content.append(f"Closed by: {closer.name} (ID: {closer.id})")
    transcript_content.append(f"Timestamp: {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")

    try:
        async for msg in channel.history(limit=None, oldest_first=True):
            attachments = "\n".join([f"Attachment: {att.url}" for att in msg.attachments])
            embed_info = []
            for embed in msg.embeds:
                embed_title = f"Title: {embed.title}" if embed.title else "No Title"
                embed_description = f"Description: {embed.description}" if embed.description else "No Description"
                embed_url = f"URL: {embed.url}" if embed.url else "No URL"
                embed_info.append(f"Embed: ({embed_title}, {embed_description}, {embed_url})")
            embeds = "\n".join(embed_info)

            content = f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {msg.author.display_name} ({msg.author.id}): {msg.clean_content}"
            if attachments:
                content += f"\n{attachments}"
            if embeds:
                content += f"\n{embeds}"
            transcript_content.append(content)

        transcript_filename = f"transcript-{channel.name}-{channel.id}.txt"
        with open(transcript_filename, 'w', encoding='utf-8') as f:
            f.write("\n".join(transcript_content))

        file = discord.File(transcript_filename)
        ticket_creator_mention = f"<@{ticket_creator_id_val}>" if ticket_creator_id_val else "Unknown User"

        embed = discord.Embed(
            title=f"Ticket Transcript: #{channel.name}",
            description=f"Ticket created by: {ticket_creator_mention}\nClosed by: {closer.mention}",
            color=discord.Color.blue()
        )
        if auto_closed:
            embed.add_field(name="Closure Type", value="Auto-Closed (Inactivity)", inline=True)
        else:
            embed.add_field(name="Closure Type", value="Manually Closed", inline=True)

        await log_channel.send(embed=embed, file=file)
        os.remove(transcript_filename)

    except discord.Forbidden:
        print(f"I don't have permission to read message history or send files in {log_channel.name}.")
    except Exception as e:
        print(f"Error creating or sending transcript for {channel.name}: {e}", file=sys.stderr)
        traceback.print_exc()

# --- Ping Ticket Creator Command ---
@bot.command()
@commands.has_permissions(manage_channels=True)
async def ping(ctx):
    """Pings the creator of the current ticket."""
    if ctx.channel.id in TICKET_CREATOR:
        user_id = TICKET_CREATOR[ctx.channel.id]
        user = ctx.guild.get_member(user_id)

        if user is None:
            try:
                user = await bot.fetch_user(user_id)
            except discord.NotFound:
                await ctx.send("❌ The ticket creator could not be found.")
                return
            except Exception as e:
                await ctx.send(f"❌ An error occurred while trying to fetch the user: {e}")
                return

        if user:
            try:
                await user.send(f"👋 {ctx.author.mention} asked you to check your ticket in {ctx.channel.mention}. Please review your ticket channel.")
                await ctx.send(f"✅ DM sent to the ticket creator ({user.mention})!")
            except discord.Forbidden:
                await ctx.send("❌ I couldn't DM the user. They might have DMs disabled or blocked me.")
            except Exception as e:
                await ctx.send(f"❌ An error occurred while trying to DM the user: {e}")
        else:
            await ctx.send("❌ The ticket creator could not be found.")
    else:
        await ctx.send("❌ No ticket creator data found for this channel. This command must be used in a ticket channel.")

# --- New General Ping Command ---
@bot.command()
@commands.has_permissions(manage_channels=True)
async def ticketping(ctx, member: discord.Member):
    """Pings a specified member regarding the current ticket channel.
    The user will receive a DM and a message in the ticket channel.
    Usage: !ticketping <@user_mention>
    """
    if not ctx.channel.category or ctx.channel.category.name != "Tickets":
        await ctx.send("❌ This command can only be used in ticket channels.")
        return

    try:
        # DM the user
        await member.send(
            f"👋 {ctx.author.mention} from **{ctx.guild.name}** asked you to check the ticket "
            f"{ctx.channel.mention}. Please review the ticket channel."
        )
        # Confirm in the ticket channel
        await ctx.send(f"✅ DM sent to {member.mention} regarding this ticket!")
    except discord.Forbidden:
        await ctx.send(f"❌ I couldn't DM {member.mention}. They might have DMs disabled or blocked me.")
    except Exception as e:
        await ctx.send(f"❌ An error occurred while trying to ping {member.mention}: {e}")
        print(f"Error pinging user {member.id} in ticket {ctx.channel.id}: {e}", file=sys.stderr)
        traceback.print_exc()

# --- Ticket Statistics Command ---
@bot.command()
@commands.has_permissions(manage_channels=True)
async def ticketstats(ctx):
    """Displays current ticket statistics and what the bot is monitoring."""
    active_tickets = len(TICKET_CREATOR)
    active_timers = len(ticket_timers)
    
    embed = discord.Embed(
        title="🎫 Ticket System Statistics",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="Active Tickets", value=str(active_tickets), inline=True)
    embed.add_field(name="Active Timers", value=str(active_timers), inline=True)
    embed.add_field(name="Auto-Close Time", value=f"{AUTO_CLOSE_TIME // 60} minutes", inline=True)
    
    if active_tickets > 0:
        ticket_list = []
        for channel_id, creator_id in TICKET_CREATOR.items():
            channel = bot.get_channel(channel_id)
            if channel:
                creator = channel.guild.get_member(creator_id)
                creator_name = creator.display_name if creator else f"Unknown (ID: {creator_id})"
                ticket_list.append(f"• {channel.mention} - {creator_name}")
            else:
                ticket_list.append(f"• Channel {channel_id} - Not Found")
        
        # Limit to first 10 tickets to avoid embed limits
        if len(ticket_list) > 10:
            ticket_list = ticket_list[:10]
            ticket_list.append(f"... and {len(TICKET_CREATOR) - 10} more")
        
        embed.add_field(
            name="Current Tickets", 
            value="\n".join(ticket_list) if ticket_list else "None", 
            inline=False
        )
    
    embed.set_footer(text=f"Bot monitoring {active_tickets} ticket{'s' if active_tickets != 1 else ''}")
    await ctx.send(embed=embed)

# --- Payment Commands (Simple link only) ---
@bot.command()
async def pp(ctx):
    """Displays PayPal payment link only."""
    await ctx.send(PAYMENT_METHODS["paypal"]["link"])

@bot.command()
async def cash(ctx):
    """Displays Cash App payment link only."""
    await ctx.send(PAYMENT_METHODS["cashapp"]["link"])

@bot.command()
async def ltc(ctx):
    """Displays Litecoin address only."""
    await ctx.send(PAYMENT_METHODS["litecoin"]["link"])

@bot.command()
async def sol(ctx):
    """Displays Solana address only."""
    await ctx.send(PAYMENT_METHODS["solana"]["link"])

# --- Main Execution ---
if __name__ == '__main__':
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        try:
            bot.run(TOKEN)
        except discord.HTTPException as e:
            if e.code == 40041:
                print("Error: Invalid Discord bot token. Please check your DISCORD_TOKEN environment variable.")
            else:
                print(f"An HTTP error occurred: {e}", file=sys.stderr)
                traceback.print_exc()
        except Exception as e:
            print(f"An unexpected error occurred during bot execution: {e}", file=sys.stderr)
            traceback.print_exc()
    else:
        print("Error: DISCORD_TOKEN environment variable not set. Please set it before running the bot.")
