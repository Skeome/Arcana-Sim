import discord
from discord.ext import commands
from discord import app_commands
import os
import json # Import json for deck management
from io import BytesIO
from dotenv import load_dotenv # <-- Import dotenv

# --- Load .env variables ---
load_dotenv()

DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
ADMIN_IDS_STR = os.environ.get("ADMIN_USER_IDS", "")
TEST_GUILD_ID_STR = os.environ.get("TEST_GUILD_ID")

# Process the loaded variables
ADMIN_USER_IDS = [int(id.strip()) for id in ADMIN_IDS_STR.split(',') if id.strip()]
TEST_GUILD = discord.Object(id=int(TEST_GUILD_ID_STR)) if TEST_GUILD_ID_STR else None

if not TEST_GUILD:
    print("Warning: TEST_GUILD_ID not set in .env. Slash commands will sync globally (slow).")
if not ADMIN_USER_IDS:
    print("Warning: ADMIN_USER_IDS not set in .env. Admin commands will not be available.")
# ---------------------------

# Import your new DISCORD game logic and card manager
from discord_engine import ArcanaGame, Phase # <-- Using the new engine
from card_manager import CardManager

# --- PIL (Python Imaging Library) is needed to create images ---
# You'll need to install it: pip install Pillow
from PIL import Image, ImageDraw, ImageFont

# --- Bot Setup ---
# You must enable "Message Content Intent" in your Discord Developer Portal
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# This dictionary will hold all active games, using the channel ID as the key
# active_games = { channel_id: ArcanaGame_instance }
active_games = {}
card_manager = CardManager() # Load the card library once

# --- Deck Management Helpers ---
DECK_DIR = "config/decks"
if not os.path.exists(DECK_DIR):
    os.makedirs(DECK_DIR) # Create the /decks folder if it doesn't exist

def get_user_deck_path(user_id: int) -> str:
    """Returns the file path for a user's custom deck."""
    return os.path.join(DECK_DIR, f"{user_id}.json")

def load_user_deck(user_id: int) -> dict:
    """Loads a user's custom deck from their JSON file."""
    deck_path = get_user_deck_path(user_id)
    if not os.path.exists(deck_path):
        return {"spirits": {}, "spells": {}} # Return empty deck
    
    try:
        with open(deck_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"spirits": {}, "spells": {}} # Return empty on corrupted file

def save_user_deck(user_id: int, deck_data: dict):
    """Saves a user's custom deck to their JSON file."""
    deck_path = get_user_deck_path(user_id)
    try:
        with open(deck_path, 'w') as f:
            json.dump(deck_data, f, indent=2)
    except Exception as e:
        print(f"Error saving deck for user {user_id}: {e}")

# --- Image Generation (The new "View") ---

def generate_board_image(game: ArcanaGame) -> BytesIO:
    """
    Creates an image of the current board state and returns it as a BytesIO object.
    This is the direct replacement for your Pygame draw_board function.
    """
    
    # --- This is where you will use PIL to draw the board ---
    # This is a complex function you'll need to build out.
    
    # 1. Create a blank image
    # Example: img = Image.new('RGB', (1000, 800), color=(30, 30, 40))
    # d = ImageDraw.Draw(img)
    # font = ImageFont.truetype("arial.ttf", 15)

    # 2. Draw Player 1's side (bottom)
    # d.text((10, 750), f"Player 1 (HP: {game.players[game.player1_id].wizard_hp})", fill=(255,255,255), font=font)
    # for i, spirit in enumerate(game.players[game.player1_id].spirit_slots):
    #     d.rectangle([100 + i*120, 600, 200 + i*120, 700], fill=(60, 90, 120))
    #     if spirit:
    #         d.text((105 + i*120, 605), spirit.name, fill=(255,255,255), font=font)

    # 3. Draw Player 2's side (top, perhaps rotated or just mirrored)
    # ...

    # 4. For now, we'll just create a placeholder image
    img = Image.new('RGB', (1000, 800), color=(30, 30, 40))
    d = ImageDraw.Draw(img)
    try:
        # You may need to provide a path to a real .ttf font file
        # On Windows: "arial.ttf"
        # On Linux: You might need to find the path, e.g., "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        font = ImageFont.truetype("arial.ttf", 20)
    except IOError:
        print("Arial font not found, using default. Image text will look blocky.")
        font = ImageFont.load_default()

    d.text((300, 350), "This is a placeholder for the board image.", fill=(255, 255, 255), font=font)
    d.text((300, 400), "You need to build `generate_board_image` in bot.py!", fill=(255, 255, 0), font=font)

    # 5. Save the image to a in-memory file
    image_buffer = BytesIO()
    img.save(image_buffer, format='PNG')
    image_buffer.seek(0)
    return image_buffer


# --- Game Action Views (The new "Controller") ---

class GameActionView(discord.ui.View):
    """
    The main UI view with buttons for actions.
    This is attached to the public board message.
    """
    def __init__(self, game: ArcanaGame, original_interaction: discord.Interaction):
        super().__init__(timeout=None) # Persistent view
        self.game = game
        self.original_interaction = original_interaction

    async def _check_turn(self, interaction: discord.Interaction) -> bool:
        """Helper to check if it's the user's turn."""
        if interaction.user.id != self.game.current_player_id:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return False
        return True

    async def _update_board(self, interaction: discord.Interaction, message_prefix: str = ""):
        """Helper to update the public board message."""
        
        # Check for game over
        if self.game.game_over:
            winner_user = await bot.fetch_user(self.game.winner)
            content = f"**GAME OVER! {winner_user.mention} WINS!**"
            
            # Create final board image
            board_image = generate_board_image(self.game)
            file = discord.File(board_image, "board.png")
            
            # Edit the original message to show winner and stop buttons
            await self.original_interaction.edit_original_response(content=content, attachments=[file], view=None)
            
            # Clean up the game
            if interaction.channel.id in active_games:
                del active_games[interaction.channel.id]
            return

        # If game is not over, update the board normally
        current_player_user = await bot.fetch_user(self.game.current_player_id)
        
        board_image = generate_board_image(self.game)
        file = discord.File(board_image, "board.png")
        
        content = f"Turn {self.game.turn_count} - {current_player_user.display_name}'s Turn - {self.game.current_phase.value} Phase"
        
        if message_prefix:
            content = f"{message_prefix}\n{content}"

        await self.original_interaction.edit_original_response(
            content=content,
            attachments=[file],
            view=self
        )

    @discord.ui.button(label="Summon", style=discord.ButtonStyle.green, custom_id="summon_spirit")
    async def summon(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_turn(interaction): return

        if self.game.current_phase != Phase.MEMORIZATION:
            await interaction.response.send_message("You can only summon in the Memorization phase.", ephemeral=True)
            return

        player_hand = self.game.players[interaction.user.id].hand
        spirit_cards = [card for card in player_hand if card.type == "spirit"]

        if not spirit_cards:
            await interaction.response.send_message("You have no spirits in your hand to summon.", ephemeral=True)
            return
        
        # Send an ephemeral message with buttons for each spirit in hand
        await interaction.response.send_message(
            "Select a Spirit to Summon:",
            view=SelectCardToPlayView(self.game, "summon", self),
            ephemeral=True
        )

    @discord.ui.button(label="Prepare", style=discord.ButtonStyle.primary, custom_id="prepare_spell")
    async def prepare(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_turn(interaction): return

        if self.game.current_phase != Phase.MEMORIZATION:
            await interaction.response.send_message("You can only prepare in the Memorization phase.", ephemeral=True)
            return
        
        player_hand = self.game.players[interaction.user.id].hand
        spell_cards = [card for card in player_hand if card.type == "spell"]

        if not spell_cards:
            await interaction.response.send_message("You have no spells in your hand to prepare.", ephemeral=True)
            return
            
        await interaction.response.send_message(
            "Select a Spell to Prepare:",
            view=SelectCardToPlayView(self.game, "prepare", self),
            ephemeral=True
        )

    @discord.ui.button(label="Attack", style=discord.ButtonStyle.danger, custom_id="attack_spirit")
    async def attack(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_turn(interaction): return
        
        if self.game.current_phase != Phase.INVOCATION:
            await interaction.response.send_message("You can only attack in the Invocation phase.", ephemeral=True)
            return
        
        # This will be similar to SelectCardToPlayView, but for your spirits on board
        await interaction.response.send_message("Attack logic not fully implemented yet.", ephemeral=True) # TODO: Add view


    @discord.ui.button(label="End Phase", style=discord.ButtonStyle.secondary, custom_id="end_phase")
    async def end_phase(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_turn(interaction): return

        current_player_name = interaction.user.display_name
        self.game.next_phase()
        
        message_prefix = f"{current_player_name} ended their phase."
        
        # Send a ping to the next player
        if self.game.current_player_id != interaction.user.id:
            opponent_user = await bot.fetch_user(self.game.current_player_id)
            await interaction.channel.send(f"Your turn, {opponent_user.mention}!")
            message_prefix = f"{current_player_name}'s turn has ended."

        # Update the public board message
        await self._update_board(interaction, message_prefix)
        
        # Acknowledge the button press
        await interaction.response.defer()


class SelectCardToPlayView(discord.ui.View):
    """
    An ephemeral view showing buttons for cards in hand.
    """
    def __init__(self, game: ArcanaGame, action_type: str, main_view: GameActionView):
        super().__init__(timeout=180)
        self.game = game
        self.action_type = action_type # "summon" or "prepare"
        self.main_view = main_view
        
        # Dynamically create buttons based on hand
        player_hand = self.game.players[self.game.current_player_id].hand
        card_type = "spirit" if action_type == "summon" else "spell"
        
        # Get unique card names
        valid_cards = {card.name: card for card in player_hand if card.type == card_type}.values()
        
        for card in valid_cards:
            self.add_item(CardButton(game, card, action_type, main_view))

class CardButton(discord.ui.Button):
    """
    A button representing a single card.
    """
    def __init__(self, game: ArcanaGame, card, action_type: str, main_view: GameActionView):
        super().__init__(label=card.name, style=discord.ButtonStyle.primary)
        self.game = game
        self.card = card
        self.action_type = action_type
        self.main_view = main_view

    async def callback(self, interaction: discord.Interaction):
        # Now that a card is selected, show the slots
        if self.action_type == "summon":
            await interaction.response.edit_message(
                content=f"Select slot for {self.card.name}:",
                view=SelectSlotView(self.game, self.card, "summon_slot", self.main_view)
            )
        elif self.action_type == "prepare":
            await interaction.response.edit_message(
                content=f"Select slot for {self.card.name}:",
                view=SelectSlotView(self.game, self.card, "prepare_slot", self.main_view)
            )

class SelectSlotView(discord.ui.View):
    """
    An ephemeral view showing buttons for spirit or spell slots.
    """
    def __init__(self, game: ArcanaGame, card, action: str, main_view: GameActionView):
        super().__init__(timeout=180)
        self.game = game
        self.card = card
        self.action = action # "summon_slot" or "prepare_slot"
        self.main_view = main_view

        if self.action == "summon_slot":
            num_slots = 3
            slot_type = "Spirit"
            slots = self.game.players[self.game.current_player_id].spirit_slots
        else: # "prepare_slot"
            num_slots = 4
            slot_type = "Spell"
            slots = self.game.players[self.game.current_player_id].spell_slots

        for i in range(num_slots):
            is_disabled = False
            label = f"{slot_type} Slot {i+1}"
            
            # Check if slot is full/occupied
            if self.action == "summon_slot" and slots[i] is not None:
                is_disabled = True
                label += " (Full)"
            elif self.action == "prepare_slot":
                if len(slots[i]) >= 3:
                    is_disabled = True
                    label += " (Full)"
                elif slots[i] and slots[i][0].name != self.card.name:
                    is_disabled = True
                    label += " (Mismatch)"

            self.add_item(SlotButton(game, card, action, i, label, is_disabled, self.main_view))

class SlotButton(discord.ui.Button):
    """
    A button representing a single slot on the board.
    This is the final step in the action chain.
    """
    def __init__(self, game: ArcanaGame, card, action: str, slot_index: int, label: str, is_disabled: bool, main_view: GameActionView):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, disabled=is_disabled)
        self.game = game
        self.card = card
        self.action = action
        self.slot_index = slot_index
        self.main_view = main_view

    async def callback(self, interaction: discord.Interaction):
        player_id = interaction.user.id
        
        if self.action == "summon_slot":
            success, message = self.game.summon_spirit(player_id, self.card.name, self.slot_index)
        elif self.action == "prepare_slot":
            success, message = self.game.prepare_spell(player_id, self.card.name, self.slot_index)
        else:
            success, message = False, "Unknown action"
        
        if success:
            # Action was successful, update the main board
            await self.main_view._update_board(interaction, f"{interaction.user.display_name} {message}.")
            await interaction.response.edit_message(content=message, view=None) # Edit the ephemeral message
        else:
            # Action failed, just tell the user why
            await interaction.response.edit_message(content=message, view=None)


# --- Bot Commands ---

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')
    try:
        if TEST_GUILD:
            print(f"Syncing commands to Test Guild (ID: {TEST_GUILD.id})...")
            # This copies global commands to the guild and syncs them.
            bot.tree.copy_global_to_guild(TEST_GUILD)
            synced = await bot.tree.sync(guild=TEST_GUILD)
        else:
            print("Syncing commands globally (this may take an hour)...")
            synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# --- Admin Check ---
def is_admin():
    """Custom check to see if the user is in the ADMIN_USER_IDS list."""
    def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.id in ADMIN_USER_IDS
    return app_commands.check(predicate)

# --- Card Name Autocomplete ---
async def card_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocompletes card IDs from the card manager."""
    all_card_ids = card_manager.get_all_card_ids()
    return [
        app_commands.Choice(name=card_id, value=card_id)
        for card_id in all_card_ids if current.lower() in card_id.lower()
    ][:25] # Discord limit of 25 choices

# --- Game Commands ---

@bot.tree.command(name="challenge", description="Challenge another player to a game of Arcana", guild=TEST_GUILD)
@app_commands.describe(opponent="The player you want to challenge")
async def challenge(interaction: discord.Interaction, opponent: discord.User):
    if opponent.bot:
        await interaction.response.send_message("You can't challenge a bot!", ephemeral=True)
        return
    if opponent.id == interaction.user.id:
        await interaction.response.send_message("You can't challenge yourself!", ephemeral=True)
        return
    if interaction.channel.id in active_games:
        await interaction.response.send_message("A game is already in progress in this channel!", ephemeral=True)
        return
        
    # --- Start the game ---
    player1_id = interaction.user.id
    player2_id = opponent.id
    
    # Create and store the new game instance
    game = ArcanaGame(card_manager, player1_id, player2_id)
    active_games[interaction.channel.id] = game
    
    # --- Send the initial board state ---
    board_image = generate_board_image(game)
    
    # Send the first message (which is public)
    await interaction.response.send_message(
        f"A game has begun between {interaction.user.mention} and {opponent.mention}!\n"
        f"Turn {game.turn_count} - {interaction.user.display_name}'s Turn - {game.current_phase.value} Phase",
        file=discord.File(board_image, "board.png"),
        view=GameActionView(game, interaction) # Pass the interaction so we can edit it later
    )

# --- Deck Management Commands ---

deck_group = app_commands.Group(name="deck", description="Manage your custom deck", guild=TEST_GUILD)

@deck_group.command(name="view", description="View your current custom deck")
async def deck_view(interaction: discord.Interaction):
    deck = load_user_deck(interaction.user.id)
    if not deck["spirits"] and not deck["spells"]:
        await interaction.response.send_message(
            "You don't have a custom deck. Your deck will be the default `player_deck.json`.\n"
            "Use `/deck add` to start building one!",
            ephemeral=True
        )
        return

    embed = discord.Embed(title=f"{interaction.user.display_name}'s Deck", color=discord.Color.blue())
    
    spirit_list = "\n".join([f"{card_id}: {qty}" for card_id, qty in deck["spirits"].items()])
    spell_list = "\n".join([f"{card_id}: {qty}" for card_id, qty in deck["spells"].items()])
    
    embed.add_field(name="Spirits", value=spirit_list or "None", inline=True)
    embed.add_field(name="Spells", value=spell_list or "None", inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@deck_group.command(name="add", description="Add a card to your custom deck (max 3 copies)")
@app_commands.autocomplete(card_id=card_autocomplete)
@app_commands.describe(card_id="The ID of the card to add", quantity="How many copies to add (default 1)")
async def deck_add(interaction: discord.Interaction, card_id: str, quantity: int = 1):
    card_data = card_manager.get_card(card_id)
    if not card_data:
        await interaction.response.send_message(f"Card '{card_id}' not found in the card library.", ephemeral=True)
        return

    card_type = card_manager.get_card_type(card_id) # "spirits" or "spells"
    deck = load_user_deck(interaction.user.id)
    
    current_qty = deck[card_type].get(card_id, 0)
    new_qty = min(3, current_qty + quantity) # Enforce 3-copy limit
    
    deck[card_type][card_id] = new_qty
    save_user_deck(interaction.user.id, deck)
    
    await interaction.response.send_message(f"Added {quantity}x {card_id}. You now have {new_qty} copies.", ephemeral=True)

@deck_group.command(name="remove", description="Remove a card from your custom deck")
@app_commands.autocomplete(card_id=card_autocomplete)
@app_commands.describe(card_id="The ID of the card to remove", quantity="How many copies to remove (default 1)")
async def deck_remove(interaction: discord.Interaction, card_id: str, quantity: int = 1):
    card_type = card_manager.get_card_type(card_id)
    if not card_type:
        await interaction.response.send_message(f"Card '{card_id}' not found in the card library.", ephemeral=True)
        return

    deck = load_user_deck(interaction.user.id)
    
    current_qty = deck[card_type].get(card_id, 0)
    if current_qty == 0:
        await interaction.response.send_message(f"You don't have any '{card_id}' in your deck.", ephemeral=True)
        return

    new_qty = max(0, current_qty - quantity)
    
    if new_qty == 0:
        del deck[card_type][card_id]
    else:
        deck[card_type][card_id] = new_qty
        
    save_user_deck(interaction.user.id, deck)
    await interaction.response.send_message(f"Removed {quantity}x {card_id}. You have {new_qty} remaining.", ephemeral=True)

@deck_group.command(name="reset", description="Delete your custom deck and revert to the default deck")
async def deck_reset(interaction: discord.Interaction):
    deck_path = get_user_deck_path(interaction.user.id)
    if os.path.exists(deck_path):
        os.remove(deck_path)
        await interaction.response.send_message("Your custom deck has been deleted. You will now use the default player deck.", ephemeral=True)
    else:
        await interaction.response.send_message("You don't have a custom deck to delete.", ephemeral=True)

bot.tree.add_command(deck_group)

# --- Admin Commands ---

admin_group = app_commands.Group(name="admin", description="Admin-only commands", guild=TEST_GUILD, default_permissions=discord.Permissions(administrator=True))

@admin_group.command(name="addspirit", description="[Admin] Add a new spirit to the card library")
@is_admin()
@app_commands.describe(
    card_id="The unique ID (e.g., 'fire_lizard')",
    name="The display name (e.g., 'Fire Lizard')",
    cost="Activation cost (Aether)",
    power="Attack power",
    defense="Defense value",
    hp="Health points",
    effect="Card effect text (optional)"
)
async def add_spirit(interaction: discord.Interaction, card_id: str, name: str, cost: int, power: int, defense: int, hp: int, effect: str = ""):
    if card_manager.get_card(card_id):
        await interaction.response.send_message(f"Error: Card ID '{card_id}' already exists!", ephemeral=True)
        return

    new_card_data = {
        "name": name,
        "activation_cost": cost,
        "power": power,
        "defense": defense,
        "hp": hp,
        "effect": effect
    }
    
    card_manager.update_card(card_id, new_card_data, "spirits")
    await interaction.response.send_message(f"Successfully added spirit: {name} (`{card_id}`). The card library is reloaded.", ephemeral=True)

@admin_group.command(name="addspell", description="[Admin] Add a new spell to the card library")
@is_admin()
@app_commands.describe(
    card_id="The unique ID (e.g., 'ice_blast')",
    name="The display name (e.g., 'Ice Blast')",
    cost="Activation cost (Aether)",
    effect="Card effect text",
    scaling="Damage/Heal/etc. value (optional)"
)
async def add_spell(interaction: discord.Interaction, card_id: str, name: str, cost: int, effect: str, scaling: int = 0):
    if card_manager.get_card(card_id):
        await interaction.response.send_message(f"Error: Card ID '{card_id}' already exists!", ephemeral=True)
        return

    new_card_data = {
        "name": name,
        "activation_cost": cost,
        "effect": effect,
        "scaling": scaling
    }
    
    card_manager.update_card(card_id, new_card_data, "spells")
    await interaction.response.send_message(f"Successfully added spell: {name} (`{card_id}`). The card library is reloaded.", ephemeral=True)

@admin_group.command(name="shutdown", description="[Admin] Shuts down the bot.")
@is_admin()
async def shutdown(interaction: discord.Interaction):
    """Admin-only command to shut down the bot."""
    await interaction.response.send_message("Shutting down...", ephemeral=True)
    print(f"Shutdown command issued by admin: {interaction.user.id}")
    await bot.close()

@shutdown.error
async def shutdown_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Error handler for the shutdown command."""
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
    else:
        await interaction.response.send_message(f"An error occurred: {error}", ephemeral=True)

bot.tree.add_command(admin_group)


# --- Run the Bot ---
if not DISCORD_BOT_TOKEN:
    print("="*30)
    print("ERROR: DISCORD_BOT_TOKEN not found in .env file.")
    print("="*30)
else:
    bot.run(DISCORD_BOT_TOKEN)