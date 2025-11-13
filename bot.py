import discord
from discord.ext import commands
from discord import app_commands
import os
import json # Import json for deck management
from io import BytesIO
from dotenv import load_dotenv
import asyncio
import aiohttp # For async web requests (Stability AI)
import base64 # For handling Stability AI response

# --- Load .env variables ---
load_dotenv()

DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
ADMIN_IDS_STR = os.environ.get("ADMIN_USER_IDS", "")
TEST_GUILD_ID_STR = os.environ.get("TEST_GUILD_ID", "") # Default to empty string

# --- NEW: Load AI API Keys ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
STABILITY_API_KEY = os.environ.get("STABILITY_API_KEY")
STABILITY_MODEL_ID = os.environ.get("STABILITY_MODEL_ID", "stable-diffusion-v1-6") # Default model

# Process the loaded variables
ADMIN_USER_IDS = [int(id.strip()) for id in ADMIN_IDS_STR.split(',') if id.strip()]

# --- MODIFIED: Process multiple guild IDs ---
TEST_GUILD_IDS = [int(id.strip()) for id in TEST_GUILD_ID_STR.split(',') if id.strip()]
TEST_GUILDS = [discord.Object(id=gid) for gid in TEST_GUILD_IDS]
# --- End of MODIFICATION ---

if not TEST_GUILDS:
    print("Warning: TEST_GUILD_ID not set in .env. Slash commands will sync globally (slow).")
if not ADMIN_USER_IDS:
    print("Warning: ADMIN_USER_IDS not set in .env. Admin commands will not be available.")
# ---------------------------

# Import your new DISCORD game logic and card manager
from discord_engine import ArcanaGame, Phase
from card_manager import CardManager
from discord_ai_controller import DiscordAIController

# --- PIL (Python Imaging Library) is needed to create images ---
# You'll need to install it: pip install Pillow
from PIL import Image, ImageDraw, ImageFont, ImageOps

# --- NEW: Import Gemini ---
# You'll need to install it: pip install google-generativeai
try:
    import google.generativeai as genai
    print("Gemini AI SDK loaded.")
except ImportError:
    print("Warning: `google-generativeai` not installed. AI commands will fail.")
    genai = None

# --- Bot Setup ---
# You must enable "Message Content Intent" in your Discord Developer Portal
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True # Make sure members intent is on

bot = commands.Bot(command_prefix="!", intents=intents)

# This dictionary will hold all active games, using the channel ID as the key
# active_games = { channel_id: ArcanaGame_instance }
active_games = {}
card_manager = CardManager() # Load the card library once
ai_controller_instance = None # Will be initialized on_ready
http_session = None # For AI requests

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
        print(f"Error: Corrupted deck file for user {user_id}. Returning empty deck.")
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

# --- NEW: Image Generation Constants and Helpers ---
# Color Palette
COLORS = {
    'bg': (30, 30, 40),
    'bg_player': (40, 40, 55),
    'bg_opponent': (55, 40, 40),
    'slot_empty': (60, 60, 70),
    'slot_spirit': (60, 90, 120),
    'slot_spell': (120, 60, 60),
    'text': (230, 230, 230),
    'text_dim': (180, 180, 180),
    'hp': (210, 70, 70),
    'aether': (70, 100, 210),
    'white': (255, 255, 255),
    'black': (0, 0, 0),
}

# Load Fonts
def get_font(size):
    """Tries to load a preferred font, falling back to default."""
    font_paths = [
        "/usr/share/fonts/TTF/CaskaydiaCoveNerdFontMono-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "arial.ttf" # Common on Windows
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except IOError:
            continue
    print(f"Could not find preferred fonts. Using default font for size {size}.")
    # Fallback to default PIL font if no paths work
    try:
        return ImageFont.load_default()
    except IOError:
        # A very basic fallback font if load_default fails in some weird env
        return ImageFont.load_default()


FONTS = {
    'small': get_font(14),
    'medium': get_font(16),
    'large': get_font(20),
    'title': get_font(24),
}

def draw_text(draw, text, x, y, font, color, max_width=None):
    """Draws text, wrapping if max_width is provided. Returns the Y position after drawing."""
    
    # Handle potential fallback font
    if not hasattr(font, 'getbbox'):
        # This is the old PIL 'load_default()' font
        line_height = font.getsize("Tg")[1] + 2
    else:
        # This is a modern truetype font
        bbox = font.getbbox("Tg")
        line_height = (bbox[3] - bbox[1]) + 2
    
    if max_width:
        words = text.split(' ')
        lines = []
        current_line = ""
        for word in words:
            if not current_line:
                test_line = word
            else:
                test_line = f"{current_line} {word}"
            
            # Check width
            if hasattr(font, 'getbbox'):
                bbox = font.getbbox(test_line)
                line_width = bbox[2] - bbox[0]
            else:
                line_width = font.getsize(test_line)[0]

            if line_width <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line) # Add the last line
        
        # Draw the wrapped lines
        for i, line in enumerate(lines):
            draw.text((x, y + i * line_height), line, fill=color, font=font)
        
        return y + (len(lines) * line_height) # Return new Y
    else:
        draw.text((x, y), text, fill=color, font=font)
        return y + line_height # Return new Y

def draw_card(draw, card, x, y, w, h, is_spirit):
    """Draws a representation of a single card."""
    if is_spirit:
        bg_color = COLORS['slot_spirit']
        draw.rectangle([x, y, x + w, y + h], fill=bg_color, outline=COLORS['text'], width=1)
        if card:
            # Store the next Y position
            next_y = draw_text(draw, card.name, x + 5, y + 5, FONTS['medium'], COLORS['white'], max_width=w - 10)
            
            # Use next_y as the base for subsequent draws
            next_y = draw_text(draw, f"HP: {card.current_hp}/{card.max_hp}", x + 5, next_y, FONTS['small'], COLORS['text'])
            next_y = draw_text(draw, f"P: {card.power} D: {card.defense}", x + 5, next_y, FONTS['small'], COLORS['text'])
            draw_text(draw, f"Cost: {card.activation_cost}", x + 5, next_y, FONTS['small'], COLORS['text'])
        else:
            draw_text(draw, "[Empty Spirit]", x + 10, y + h//2 - 10, FONTS['small'], COLORS['text_dim'])
    else: # Spell
        bg_color = COLORS['slot_spell']
        draw.rectangle([x, y, x + w, y + h], fill=bg_color, outline=COLORS['text'], width=1)
        if card: # card is a list of stacked spells
            spell = card[0]
            stack_size = len(card)
            
            next_y = draw_text(draw, f"{spell.name} x{stack_size}", x + 5, y + 5, FONTS['medium'], COLORS['white'], max_width=w - 10)
            next_y = draw_text(draw, f"Cost: {spell.activation_cost}", x + 5, next_y, FONTS['small'], COLORS['text'])
            draw_text(draw, spell.effect, x + 5, next_y, FONTS['small'], COLORS['text'], max_width=w - 10)
        else:
            draw_text(draw, "[Empty Spell]", x + 10, y + h//2 - 10, FONTS['small'], COLORS['text_dim'])

def draw_player_area(draw, player_state, user_name, y_start, is_opponent):
    """Draws one player's entire side of the board."""
    # --- MODIFIED: Canvas size ---
    w, h = 1920, 540 # Main image dimensions
    
    # --- MODIFIED: Card dimensions ---
    card_w, card_h = 150, 210 # Portrait and larger
    gap = 20

    # Draw player bg
    bg_color = COLORS['bg_opponent'] if is_opponent else COLORS['bg_player']
    draw.rectangle([0, y_start, w, y_start + h], fill=bg_color)
    
    # Player Info (HP and Aether)
    info_x = 20
    info_y = y_start + 20
    draw_text(draw, user_name, info_x, info_y, FONTS['large'], COLORS['white'])
    draw.rectangle([info_x, info_y + 30, info_x + 200, info_y + 55], fill=COLORS['hp'])
    draw_text(draw, f"HP: {player_state.wizard_hp} / 20", info_x + 5, info_y + 33, FONTS['medium'], COLORS['white'])
    draw.rectangle([info_x, info_y + 60, info_x + 200, info_y + 85], fill=COLORS['aether'])
    draw_text(draw, f"Aether: {player_state.aether} / 16", info_x + 5, info_y + 63, FONTS['medium'], COLORS['white'])
    
    # Hand
    # --- MODIFIED: Hand X positions ---
    player_hand_x = 1500  # Player's hand on the right
    opponent_hand_x = 1500 # Opponent's hand closer to the center
    
    hand_x = opponent_hand_x if is_opponent else player_hand_x
    # --- MODIFIED: Y value for hand text (to fix clipping) ---
    hand_y = y_start + 30 
    draw_text(draw, "Hand:", hand_x, hand_y, FONTS['medium'], COLORS['white'])
    if is_opponent:
        draw_text(draw, f"{len(player_state.hand)} Cards", hand_x + 5, hand_y + 30, FONTS['small'], COLORS['text_dim'])
    else:
        for i, card in enumerate(player_state.hand):
            if i > 12: # Limit display
                draw_text(draw, "...", hand_x + 5, hand_y + 30 + i * 20, FONTS['small'], COLORS['text_dim'])
                break
            draw_text(draw, f"• {card.name} ({card.type})", hand_x + 5, hand_y + 30 + i * 20, FONTS['small'], COLORS['text'])
            
    # Deck/Discard
    draw_text(draw, f"Deck: {len(player_state.deck)}", info_x, y_start + 120, FONTS['small'], COLORS['text_dim'])
    draw_text(draw, f"Discard: {len(player_state.discard)}", info_x, y_start + 140, FONTS['small'], COLORS['text_dim'])

    # --- MODIFIED: Y coordinates and X start positions for new card size ---
    
    # Spirit Slots
    # Opponent: spirit_y = 0 + (540 - 210 - 20) = 310
    # Player:   spirit_y = 540 + 20 = 560
    spirit_y = y_start + (h - card_h - 50 if is_opponent else 50)
    total_spirit_width = (3 * card_w) + (2 * gap)
    spirit_x_start = (w - total_spirit_width) // 2
    
    for i in range(3):
        x = spirit_x_start + i * (card_w + gap)
        draw_card(draw, player_state.spirit_slots[i], x, spirit_y, card_w, card_h, is_spirit=True)
        
    # Spell Slots
    # Opponent: spell_y = 0 + 20 = 20
    # Player:   spell_y = 540 + (540 - 210 - 20) = 850
    spell_y = y_start + (20 if is_opponent else h - card_h - 20)
    total_spell_width = (4 * card_w) + (3 * gap)
    spell_x_start = (w - total_spell_width) // 2

    for i in range(4):
        x = spell_x_start + i * (card_w + gap)
        draw_card(draw, player_state.spell_slots[i], x, spell_y, card_w, card_h, is_spirit=False)


async def generate_board_image(game: ArcanaGame) -> BytesIO:
    """
    Creates an image of the current board state and returns it as a BytesIO object.
    This is the direct replacement for your Pygame draw_board function.
    """
    
    # 1. Create a blank image
    # --- MODIFIED: Canvas size ---
    img_width = 1920
    img_height = 1080
    img = Image.new('RGB', (img_width, img_height), color=COLORS['bg'])
    d = ImageDraw.Draw(img)

    # 2. Get player display names (async)
    try:
        p1_user = await bot.fetch_user(game.player1_id)
        p1_name = p1_user.display_name
    except:
        p1_name = f"Player 1 ({game.player1_id})"

    try:
        if game.player2_id == bot.user.id:
            p2_name = "Arcana Bot"
        else:
            p2_user = await bot.fetch_user(game.player2_id)
            p2_name = p2_user.display_name
    except:
        p2_name = f"Player 2 ({game.player2_id})"

    # 3. Determine who is opponent (top) and player (bottom)
    # For now, let's assume player1 is always bottom
    player_state = game.players[game.player1_id]
    opponent_state = game.players[game.player2_id]
    
    # Draw Opponent Area (Top)
    draw_player_area(d, opponent_state, p2_name, y_start=0, is_opponent=True)
    
    # Draw Player Area (Bottom)
    # --- MODIFIED: y_start for player area ---
    draw_player_area(d, player_state, p1_name, y_start=540, is_opponent=False)
    
    # Draw Center Line (Turn Info)
    # --- MODIFIED: Center line position ---
    d.rectangle([0, 535, img_width, 545], fill=COLORS['text_dim'])
    
    if game.game_over:
        winner_id = game.winner
        winner_name = p1_name if winner_id == game.player1_id else p2_name
        text = f"GAME OVER - {winner_name} WINS!"
        
        # Calculate text size
        if hasattr(FONTS['title'], 'getbbox'):
            bbox = FONTS['title'].getbbox(text)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
        else:
            size = FONTS['title'].getsize(text)
            text_w = size[0]
            text_h = size[1]
            
        d.rectangle([(img_width-text_w)//2 - 10, (img_height-text_h)//2 - 10, (img_width+text_w)//2 + 10, (img_height+text_h)//2 + 10], fill=COLORS['hp'])
        draw_text(d, text, (img_width-text_w)//2, (img_height-text_h)//2 - 5, FONTS['title'], COLORS['white'])
    else:
        current_player_name = p1_name if game.current_player_id == game.player1_id else p2_name
        text = f"Turn {game.turn_count} - {current_player_name}'s Turn - {game.current_phase.value} Phase"
        
        # Calculate text size
        if hasattr(FONTS['medium'], 'getbbox'):
            bbox = FONTS['medium'].getbbox(text)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
        else:
            size = FONTS['medium'].getsize(text)
            text_w = size[0]
            text_h = size[1]
        
        # --- MODIFIED: Y coordinate for turn text ---
        # Draw 5px *above* the center line (535)
        draw_text(d, text, (img_width-text_w)//2, 535 - text_h - 5, FONTS['medium'], COLORS['white'])


    # 5. Save the image to a in-memory file
    image_buffer = BytesIO()
    img.save(image_buffer, format='PNG')
    image_buffer.seek(0)
    return image_buffer


# --- Game Action Views ---

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
            # Check if winner is the bot
            if self.game.winner == bot.user.id:
                winner_user_mention = bot.user.mention
            else:
                winner_user = await bot.fetch_user(self.game.winner)
                winner_user_mention = winner_user.mention
                
            content = f"**GAME OVER! {winner_user_mention} WINS!**"
            
            # Create final board image
            board_image = await generate_board_image(self.game)
            file = discord.File(board_image, "board.png")
            
            # Edit the original message to show winner and stop buttons
            await self.original_interaction.edit_original_response(content=content, attachments=[file], view=None)
            
            # Clean up the game
            if interaction.channel.id in active_games:
                del active_games[interaction.channel.id]
            return

        # If game is not over, update the board normally
        # Check if current player is the bot
        if self.game.current_player_id == bot.user.id:
            current_player_name = bot.user.display_name
        else:
            current_player_user = await bot.fetch_user(self.game.current_player_id)
            current_player_name = current_player_user.display_name
        
        board_image = await generate_board_image(self.game)
        file = discord.File(board_image, "board.png")
        
        content = f"Turn {self.game.turn_count} - {current_player_name}'s Turn - {self.game.current_phase.value} Phase"
        
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
        
        # TODO: This needs to be implemented similar to Summon/Prepare
        await interaction.response.send_message("Attack logic not fully implemented yet.", ephemeral=True) # TODO: Add view


    @discord.ui.button(label="End Phase", style=discord.ButtonStyle.secondary, custom_id="end_phase")
    async def end_phase(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_turn(interaction): return

        # Defer immediately, as AI turn might take a moment
        await interaction.response.defer()

        current_player_name = interaction.user.display_name
        self.game.next_phase()
        
        message_prefix = f"{current_player_name} ended their phase."
        
        if self.game.current_player_id == bot.user.id and not self.game.game_over:
            if ai_controller_instance:
                # Send a "thinking" message. Use followup since we deferred.
                await interaction.followup.send("Arcana Bot is thinking...", ephemeral=True)
                
                # Run the AI turn (this is a synchronous function)
                # In a real-world scenario, you might run this in an executor
                # await asyncio.to_thread(ai_controller_instance.execute_ai_turn, self.game)
                ai_controller_instance.execute_ai_turn(self.game) # Assuming this is fast enough
                
                # The AI turn *ends itself* by calling next_phase() until it's the player's turn again.
                message_prefix = "Arcana Bot has finished its turn."
            else:
                # Fallback if AI fails to load
                self.game.next_phase() # Skip bot turn
                message_prefix = "AI failed to load, skipping turn."
                print("Error: ai_controller_instance is None!")

        # Send a ping to the next player (if it's a human)
        # Check that the new player isn't the user who just clicked, AND isn't the bot
        if (self.game.current_player_id != interaction.user.id and 
            self.game.current_player_id != bot.user.id and
            not self.game.game_over):
            
            opponent_user = await bot.fetch_user(self.game.current_player_id)
            await interaction.channel.send(f"Your turn, {opponent_user.mention}!")
            message_prefix = f"{current_player_name}'s turn has ended."

        # Update the public board message
        await self._update_board(interaction, message_prefix)


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
            # We deferred in the main_view.end_phase, but this is a separate interaction
            # We just need to edit the ephemeral message and let _update_board do its thing
            await interaction.response.edit_message(content=message, view=None) # Edit the ephemeral message
            await self.main_view._update_board(interaction, f"{interaction.user.display_name} {message}.")
        else:
            # Action failed, just tell the user why
            await interaction.response.edit_message(content=message, view=None)


# --- Bot Commands ---

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')
    
    # --- Initialize AI Controller ---
    global ai_controller_instance
    ai_controller_instance = DiscordAIController(bot.user.id)
    print(f"AI Controller initialized for bot ID {bot.user.id}")
    
    # --- Initialize HTTP Session for AI ---
    global http_session
    http_session = aiohttp.ClientSession()
    print("aiohttp session initialized.")

    # --- Configure Gemini ---
    if genai and GEMINI_API_KEY:
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            print("Gemini AI configured.")
        except Exception as e:
            print(f"Error configuring Gemini: {e}")
    elif not GEMINI_API_KEY:
        print("Warning: GEMINI_API_KEY not set in .env. AI description command will fail.")
    # -----------------------------

    # --- MODIFIED: Sync logic for multiple guilds ---
    try:
        if TEST_GUILDS:
            print(f"Syncing commands to {len(TEST_GUILDS)} test guild(s)...")
            for guild in TEST_GUILDS:
                try:
                    # --- MODIFIED: Comment description is more accurate ---
                    # Sync all guild-specific commands to this guild
                    synced = await bot.tree.sync(guild=guild)
                    print(f"Synced {len(synced)} command(s) to Guild (ID: {guild.id}).")
                except discord.errors.Forbidden:
                    print(f"Failed to sync to Guild {guild.id} (Forbidden). Make sure bot has 'applications.commands' scope.")
                except Exception as e:
                    print(f"Failed to sync to Guild {guild.id}: {e}")
        else:
            print("No test guilds set. Syncing commands globally (this may take an hour)...")
            # This syncs all global commands
            synced = await bot.tree.sync()
            print(f"Synced {len(synced)} global command(s).")
    except Exception as e:
        print(f"An error occurred during command sync: {e}")
    # --- End of MODIFICATION ---

@bot.event
async def on_close():
    """Clean up the http session when bot closes."""
    if http_session:
        await http_session.close()
        print("aiohttp session closed.")

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

# --- MODIFIED: Reverted to guild-specific commands using 'guilds' (plural) ---
@bot.tree.command(name="challenge", description="Challenge another player (or the bot) to a game", guilds=TEST_GUILDS)
@app_commands.describe(opponent="The player you want to challenge (select me to play solo!)")
async def challenge(interaction: discord.Interaction, opponent: discord.User):
    # --- MODIFIED: Allow challenging self or bot ---
    # if opponent.bot and opponent.id != bot.user.id:
    #     await interaction.response.send_message("You can't challenge other bots!", ephemeral=True)
    #     return
    if opponent.id == interaction.user.id:
        await interaction.response.send_message("You can't challenge yourself!", ephemeral=True)
        return
    if interaction.channel.id in active_games:
        await interaction.response.send_message("A game is already in progress in this channel!", ephemeral=True)
        return
        
    await interaction.response.defer()

    # --- Start the game ---
    player1_id = interaction.user.id
    player2_id = opponent.id
    
    # Create and store the new game instance
    game = ArcanaGame(card_manager, player1_id, player2_id)
    active_games[interaction.channel.id] = game
    
    # --- Send the initial board state ---
    board_image = await generate_board_image(game)
    
    game_start_message = f"A game has begun between {interaction.user.mention} and {opponent.mention}!\n"
    if opponent.id == bot.user.id:
        game_start_message = f"{interaction.user.mention} has challenged the bot to a solo game!\n"

    # Send the first message (which is public)
    await interaction.followup.send(
        f"{game_start_message}"
        f"Turn {game.turn_count} - {interaction.user.display_name}'s Turn - {game.current_phase.value} Phase",
        file=discord.File(board_image, "board.png"),
        view=GameActionView(game, interaction) # Pass the interaction so we can edit it later
    )

# --- View Card Command ---
# --- MODIFIED: Reverted to guild-specific commands using 'guilds' (plural) ---
@bot.tree.command(name="viewcard", description="Look up a card from the library", guilds=TEST_GUILDS)
@app_commands.autocomplete(card_id=card_autocomplete)
@app_commands.describe(card_id="The ID of the card you want to view")
async def viewcard(interaction: discord.Interaction, card_id: str):
    card_data = card_manager.get_card(card_id)
    if not card_data:
        await interaction.response.send_message(f"Card '{card_id}' not found in the card library.", ephemeral=True)
        return

    card_type = card_manager.get_card_type(card_id)
    
    embed = discord.Embed(
        title=f"[{card_data.get('name', 'Unknown')}]",
        description=card_data.get('effect', '*No effect description.*'),
        color=discord.Color.blue() if card_type == "spells" else discord.Color.red()
    )
    
    embed.add_field(name="Card ID", value=f"`{card_id}`", inline=True)
    embed.add_field(name="Type", value=card_type.capitalize(), inline=True)
    embed.add_field(name="Cost", value=f"{card_data.get('activation_cost', 0)} Aether", inline=True)
    
    if card_type == "spirits":
        embed.add_field(name="Power", value=card_data.get('power', 0), inline=True)
        embed.add_field(name="Defense", value=card_data.get('defense', 0), inline=True)
        embed.add_field(name="HP", value=card_data.get('hp', 0), inline=True)
    else: # Spells
        embed.add_field(name="Scaling", value=card_data.get('scaling', 0), inline=True)
        
    embed.set_footer(text="Use /deck to manage your cards")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# --- NEW: List Cards Command ---
# --- MODIFIED: Reverted to guild-specific commands using 'guilds' (plural) ---
@bot.tree.command(name="listcards", description="Lists all cards in the library", guilds=TEST_GUILDS)
async def listcards(interaction: discord.Interaction):
    spirits = card_manager.cards.get("spirits", {})
    spells = card_manager.cards.get("spells", {})

    embed = discord.Embed(title="Card Library", color=discord.Color.gold())

    # Format lists
    spirit_list = [f"`{cid}`: {data.get('name', 'N/A')}" for cid, data in spirits.items()]
    spell_list = [f"`{cid}`: {data.get('name', 'N/A')}" for cid, data in spells.items()]

    # Add fields, handling potential for long lists (Discord field limit 1024 chars)
    if spirit_list:
        s_list_str = "\n".join(spirit_list)
        if len(s_list_str) > 1024:
            s_list_str = s_list_str[:1020] + "\n..."
        embed.add_field(name="Spirits", value=s_list_str or "None", inline=False)
    else:
        embed.add_field(name="Spirits", value="None", inline=False)
        
    if spell_list:
        s_list_str = "\n".join(spell_list)
        if len(s_list_str) > 1024:
            s_list_str = s_list_str[:1020] + "\n..."
        embed.add_field(name="Spells", value=s_list_str or "None", inline=False)
    else:
        embed.add_field(name="Spells", value="None", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


# --- Deck Management Commands ---

# --- MODIFIED: Removed guild_ids from the group definition ---
deck_group = app_commands.Group(name="deck", description="Manage your custom deck")

# Add commands to the group
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
        if card_id in deck[card_type]: # Check existence before deleting
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

# --- MODIFIED: Added guilds parameter to the add_command call ---
bot.tree.add_command(deck_group, guilds=TEST_GUILDS)


# --- Admin Commands ---

# --- MODIFIED: Removed guild_ids from the group definition ---
admin_group = app_commands.Group(name="admin", description="Admin-only commands")

# --- NEW: Group-level error handler ---
@admin_group.error
async def on_admin_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Handles errors for all commands in the admin group."""
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
    else:
        print(f"Unhandled error in admin command: {error}")
        await interaction.response.send_message(f"An unexpected error occurred: {error}", ephemeral=True)
# --- End of NEW code ---

# Add commands to the group
@admin_group.command(name="addspirit", description="[Admin] Add a new spirit to the card library")
@is_admin()
@app_commands.describe(
    card_id="The unique ID (e.g., 'fire_lizard')",
    name="The display name (e.g., 'Fire Lizard')",
    cost="Activation cost (Aether)",
    power="Attack power",
    defense="Defense value",
    hp="Health points",
    effect="Card effect text (optional)",
    effects_json="JSON string for effects (e.g., '{\"direct_attack\": true}')"
)
async def add_spirit(interaction: discord.Interaction, card_id: str, name: str, cost: int, power: int, defense: int, hp: int, effect: str = "", effects_json: str = "{}"):
    if card_manager.get_card(card_id):
        await interaction.response.send_message(f"Error: Card ID '{card_id}' already exists! Use /admin updatefield to modify.", ephemeral=True)
        return
    
    try:
        effects_dict = json.loads(effects_json)
    except json.JSONDecodeError:
        await interaction.response.send_message("Error: Invalid JSON format in `effects_json`.", ephemeral=True)
        return

    new_card_data = {
        "name": name,
        "activation_cost": cost,
        "power": power,
        "defense": defense,
        "hp": hp,
        "effect": effect,
        "effects": effects_dict # Add the new effects
    }
    
    if card_manager.update_card(card_id, new_card_data, "spirits"):
        await interaction.response.send_message(f"Successfully added spirit: {name} (`{card_id}`). The card library is reloaded.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Error: Failed to save card to `cards.json`.", ephemeral=True)


@admin_group.command(name="addspell", description="[Admin] Add a new spell to the card library")
@is_admin()
@app_commands.describe(
    card_id="The unique ID (e.g., 'ice_blast')",
    name="The display name (e.g., 'Ice Blast')",
    cost="Activation cost (Aether)",
    effect="Card effect text",
    scaling="Damage/Heal/etc. value (optional)",
    effects_json="JSON string for effects (e.g., '{\"aoe_damage\": true}')"
)
async def add_spell(interaction: discord.Interaction, card_id: str, name: str, cost: int, effect: str, scaling: int = 0, effects_json: str = "{}"):
    if card_manager.get_card(card_id):
        await interaction.response.send_message(f"Error: Card ID '{card_id}' already exists! Use /admin updatefield to modify.", ephemeral=True)
        return

    try:
        effects_dict = json.loads(effects_json)
    except json.JSONDecodeError:
        await interaction.response.send_message("Error: Invalid JSON format in `effects_json`.", ephemeral=True)
        return

    new_card_data = {
        "name": name,
        "activation_cost": cost,
        "effect": effect,
        "scaling": scaling,
        "effects": effects_dict
    }
    
    if card_manager.update_card(card_id, new_card_data, "spells"):
        await interaction.response.send_message(f"Successfully added spell: {name} (`{card_id}`). The card library is reloaded.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Error: Failed to save card to `cards.json`.", ephemeral=True)

# --- NEW: Admin Remove Card ---
@admin_group.command(name="removecard", description="[Admin] Remove a card from the library")
@is_admin()
@app_commands.autocomplete(card_id=card_autocomplete)
@app_commands.describe(card_id="The ID of the card to remove")
async def remove_card(interaction: discord.Interaction, card_id: str):
    success, message = card_manager.remove_card(card_id)
    if success:
        await interaction.response.send_message(f"Successfully removed card `{card_id}`. Library reloaded.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Error: {message}", ephemeral=True)

# --- NEW: Admin Update Card ---
@admin_group.command(name="updatefield", description="[Admin] Update a specific field for a card")
@is_admin()
@app_commands.autocomplete(card_id=card_autocomplete)
@app_commands.describe(
    card_id="The ID of the card to update",
    field="The field to update (e.g., 'power', 'effect', 'effects.direct_attack')",
    value="The new value for the field"
)
async def update_field(interaction: discord.Interaction, card_id: str, field: str, value: str):
    success, message = card_manager.update_card_field(card_id, field, value)
    if success:
        await interaction.response.send_message(f"Successfully updated `{field}` for `{card_id}`. Library reloaded.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Error: {message}", ephemeral=True)

# --- NEW: Admin AI Commands ---
@admin_group.command(name="generatedescription", description="[Admin] Generate a new card description with Gemini AI")
@is_admin()
@app_commands.autocomplete(card_id=card_autocomplete)
@app_commands.describe(card_id="The card to generate a description for")
async def generate_description(interaction: discord.Interaction, card_id: str):
    if not genai or not GEMINI_API_KEY:
        await interaction.response.send_message("Gemini AI is not configured. Check .env and imports.", ephemeral=True)
        return

    card_data = card_manager.get_card(card_id)
    if not card_data:
        await interaction.response.send_message(f"Card '{card_id}' not found.", ephemeral=True)
        return
        
    await interaction.response.defer(ephemeral=True)

    try:
        model = genai.GenerativeModel('gemini-pro')
        prompt = (
            f"You are a trading card game designer. Write a cool, concise (1-2 lines) "
            f"effect description for a card named '{card_data.get('name', 'Unknown')}'."
            f"The card's stats are: {card_data}. "
            f"The card's internal effect keywords are: {card_data.get('effects', {})}. "
            f"Do not include the card name in the description."
        )
        
        response = await model.generate_content_async(prompt)
        
        new_description = response.text.strip().replace("\"", "")
        
        # Update the card
        success, message = card_manager.update_card_field(card_id, "effect", new_description)
        
        if success:
            await interaction.followup.send(f"Generated and updated description for `{card_id}`:\n\n{new_description}")
        else:
            await interaction.followup.send(f"Generated description, but failed to save: {message}\n\n{new_description}")
            
    except Exception as e:
        await interaction.followup.send(f"An error occurred while generating description: {e}")

@admin_group.command(name="generateart", description="[Admin] Generate new card art with Stability AI")
@is_admin()
@app_commands.autocomplete(card_id=card_autocomplete)
@app_commands.describe(card_id="The card to generate art for")
async def generate_art(interaction: discord.Interaction, card_id: str):
    if not STABILITY_API_KEY or not http_session:
        await interaction.response.send_message("Stability AI is not configured. Check .env and `on_ready`.", ephemeral=True)
        return
        
    card_data = card_manager.get_card(card_id)
    if not card_data:
        await interaction.response.send_message(f"Card '{card_id}' not found.", ephemeral=True)
        return
        
    await interaction.response.defer(ephemeral=True)
    
    card_name = card_data.get('name', card_id)
    card_type = card_manager.get_card_type(card_id)
    
    prompt = (
        f"Epic fantasy trading card art of a {card_name}. "
        f"Type: {card_type}. "
        f"{card_data.get('effect', '')}. "
        f"Style: digital painting, vibrant, detailed, centered."
    )
    
    STABILITY_API_URL = f"https://api.stability.ai/v1/generation/{STABILITY_MODEL_ID}/text-to-image"
    headers = {
        "Authorization": f"Bearer {STABILITY_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "text_prompts": [{"text": prompt}],
        "cfg_scale": 7,
        "height": 1024, # Use allowed SDXL dimension
        "width": 1024,  # Use allowed SDXL dimension
        "samples": 1,
        "steps": 30,
    }

    try:
        async with http_session.post(STABILITY_API_URL, headers=headers, json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Stability AI API error ({response.status}): {error_text}")
                
            data = await response.json()
            image_b64 = data["artifacts"][0]["base64"]
            
            # Correction:
            image_data = BytesIO(base64.b64decode(image_b64))
            file = discord.File(image_data, filename=f"{card_id}_art.png")
            
            await interaction.followup.send(f"Generated art for `{card_id}` ({card_name}):", file=file)

    except Exception as e:
        await interaction.followup.send(f"An error occurred while generating art: {e}")


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

# --- MODIFIED: Added guilds parameter to the add_command call ---
bot.tree.add_command(admin_group, guilds=TEST_GUILDS)


# --- Run the Bot ---
if not DISCORD_BOT_TOKEN:
    print("="*30)
    print("ERROR: DISCORD_BOT_TOKEN not found in .env file.")
    print("="*30)
else:
    bot.run(DISCORD_BOT_TOKEN)