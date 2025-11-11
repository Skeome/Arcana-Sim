# This will act as a simulator for quickly testing and balancing game mechanics
# PyGame vizualization and input loop
import pygame
import sys
from game_engine import ArcanaGame, Phase
from card_manager import CardManager
from ai_controller import AIController

class ArcanaVisualizer:
    def __init__(self):
        pygame.init()
        self.screen_width = 1300
        self.screen_height = 900
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Arcana Simulator")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont('Noto-Sans', 18, bold=False, italic=False)
        self.game = ArcanaGame()
        self.card_manager = CardManager()
        self.ai = AIController()
        self.last_message = "Welcome to Arcana! Your turn."

        # Color scheme
        self.colors = {
            'background': (30, 30, 40),
            'player_slots': (60, 90, 120),
            'npc_slots': (120, 60, 60),
            'text': (230, 230, 230),
            'hp_track': (180, 50, 50),
            'aether_track': (50, 100, 180),
            'log_text': (200, 200, 100),
            'game_over': (255, 0, 0),
            'prompt_text': (100, 255, 100), # Green for prompts
            'highlight': (255, 255, 0), # Yellow for selection
        }

        # --- NEW: State machine for player input ---
        self.input_mode = "NORMAL" # "NORMAL", "SUMMON_CARD", "SUMMON_SLOT", "PREPARE_CARD", "PREPARE_SLOT", etc.
        self.selected_card = None
        self.selected_slot = None
        self.action_prompt = "" # Will show messages like "Select a Spirit card from hand [1-9]"

    def reset_input_state(self):
        """Helper to cancel actions and return to normal."""
        self.input_mode = "NORMAL"
        self.selected_card = None
        self.selected_slot = None
        self.action_prompt = ""

    def get_centered_start_x(self, num_slots, slot_width, gap):
        """Calculates the starting X to center a row of slots."""
        total_width = (num_slots * slot_width) + ((num_slots - 1) * gap)
        return (self.screen_width - total_width) // 2

    def draw_board(self):
        self.screen.fill(self.colors['background'])

        # Draw Center Line (Optional visual guide)
        pygame.draw.line(self.screen, (50, 50, 60), (0, self.screen_height // 2), (self.screen_width, self.screen_height // 2), 2)

        # Draw Player Side
        self.draw_player_side()

        # Draw NPC Side
        self.draw_npc_side()

        # Draw turn info
        self.draw_game_info()

        # Draw Game Over
        if self.game.game_over:
            self.draw_text(f"GAME OVER - {self.game.winner.upper()} WINS!", self.screen_width // 2 - 150, self.screen_height // 2 - 20, color=self.colors['game_over'])
            self.draw_text("Press [R] to play again", self.screen_width // 2 - 100, self.screen_height // 2 + 10, color=self.colors['game_over'])

        pygame.display.flip()

    def draw_player_side(self):
        player = self.game.players["player"]
        slot_width = 140
        slot_height = 110
        gap = 30
        
        # --- ROW 1: SPIRIT FIELD (Front Row - Closer to Center) ---
        # Y position: Center (450) + offset (e.g., 50px)
        spirit_y = 500
        spirit_x_start = self.get_centered_start_x(3, slot_width, gap)

        for i in range(3):
            x = spirit_x_start + i * (slot_width + gap)
            y = spirit_y
            
            # Highlight Logic
            is_valid_summon_slot = (self.input_mode == "SUMMON_SLOT" and player.spirit_slots[i] is None)
            is_valid_attacker_slot = (self.input_mode == "ATTACK_SLOT" and player.spirit_slots[i] is not None and player.aether >= player.spirit_slots[i].activation_cost)

            if is_valid_summon_slot or is_valid_attacker_slot:
                pygame.draw.rect(self.screen, self.colors['highlight'], (x-3, y-3, slot_width+6, slot_height+6), border_radius=5)

            pygame.draw.rect(self.screen, self.colors['player_slots'], (x, y, slot_width, slot_height), border_radius=5)
            spirit = player.spirit_slots[i]
            if spirit:
                self.draw_text(f"[{i+1}] {spirit.name}", x+5, y+5)
                self.draw_text(f"HP: {spirit.current_hp}/{spirit.max_hp}", x+5, y+25)
                self.draw_text(f"P:{spirit.power} D:{spirit.defense}", x+5, y+45)
                self.draw_text(f"Cost:{spirit.activation_cost}", x+5, y+65)
            else:
                self.draw_text(f"Spirit [{i+1}]", x+5, y+5)

        # --- ROW 2: SPELL FIELD (Back Row - Further from Center) ---
        spell_y = 640
        spell_x_start = self.get_centered_start_x(4, slot_width, gap)

        for i in range(4):
            x = spell_x_start + i * (slot_width + gap)
            y = spell_y

            # Highlight Logic
            is_valid_prepare_slot = self.input_mode == "PREPARE_SLOT" and \
                                    (not player.spell_slots[i] or \
                                    (player.spell_slots[i][0].name == self.selected_card.name and len(player.spell_slots[i]) < 3))
            is_valid_activate_slot = self.input_mode == "ACTIVATE_SLOT" and player.spell_slots[i]

            if is_valid_prepare_slot or is_valid_activate_slot:
                 pygame.draw.rect(self.screen, self.colors['highlight'], (x-3, y-3, slot_width+6, 106), border_radius=5)

            pygame.draw.rect(self.screen, self.colors['player_slots'], (x, y, slot_width, 100), border_radius=5)
            spell_stack = player.spell_slots[i]
            if spell_stack:
                spell = spell_stack[0]
                self.draw_text(f"[{i+1}] {spell.name} x{len(spell_stack)}", x+5, y+5)
                self.draw_text(f"Cost: {spell.activation_cost}", x+5, y+25)
                self.draw_text(f"{spell.effect}", x+5, y+45, wrap=True, max_width=130)
            else:
                self.draw_text(f"Spell [{i+1}]", x+5, y+5)

        # --- TRACKS (Bottom) ---
        track_y = 780
        pygame.draw.rect(self.screen, self.colors['hp_track'], (50, track_y, 200, 30))
        hp_text = f"HP: {player.wizard_hp}/20"
        self.draw_text(hp_text, 60, track_y+5)

        pygame.draw.rect(self.screen, self.colors['aether_track'], (300, track_y, 200, 30))
        aether_text = f"Aether: {player.aether}/16"
        self.draw_text(aether_text, 310, track_y+5)

        # --- Draw player hand (Moved from draw_game_info) ---
        hand_x = 1050
        hand_y_start = 500 # Align with top of spirit slots
        
        self.draw_text("Player Hand:", hand_x, hand_y_start)
        
        for i, card in enumerate(player.hand):
            hand_text = f"[{i+1}] {card.name} ({card.type})"
            hand_y = hand_y_start + 30 + i * 20 # Start list 30px below title

            # Highlight logic
            is_valid_card = (self.input_mode == "SUMMON_CARD" and card.type == "spirit") or \
                            (self.input_mode == "PREPARE_CARD" and card.type == "spell")

            if is_valid_card:
                self.draw_text(hand_text, hand_x, hand_y, color=self.colors['highlight'])
            else:
                self.draw_text(hand_text, hand_x, hand_y)


    def draw_npc_side(self):
        npc = self.game.players["npc"]
        slot_width = 140
        slot_height = 110
        gap = 30

        # --- ROW 1: SPELL FIELD (Back Row - Furthest from Center/Top of screen) ---
        # Note: In your previous code, Spell was Y=270 and Spirit Y=150.
        # To swap them so Spirit is "Front" (closer to center/450) and Spell is "Back" (closer to 0):
        # Spell should have small Y, Spirit should have large Y.
        
        spell_y = 100
        spell_x_start = self.get_centered_start_x(4, slot_width, gap)

        for i in range(4):
            x = spell_x_start + i * (slot_width + gap)
            y = spell_y
            pygame.draw.rect(self.screen, self.colors['npc_slots'], (x, y, slot_width, 100), border_radius=5)
            spell_stack = npc.spell_slots[i]
            if spell_stack:
                spell = spell_stack[0]
                self.draw_text(f"[{i+1}] {spell.name} x{len(spell_stack)}", x+5, y+5)
                self.draw_text(f"Cost: {spell.activation_cost}", x+5, y+25)
                self.draw_text(f"{spell.effect}", x+5, y+45, wrap=True, max_width=130)
            else:
                self.draw_text(f"Spell [{i+1}]", x+5, y+5)

        # --- ROW 2: SPIRIT FIELD (Front Row - Closer to Center) ---
        spirit_y = 240
        spirit_x_start = self.get_centered_start_x(3, slot_width, gap)

        for i in range(3):
            x = spirit_x_start + i * (slot_width + gap)
            y = spirit_y

            # Highlight Logic
            is_valid_target = (self.input_mode == "ATTACK_TARGET" and npc.spirit_slots[i] is not None)

            if is_valid_target:
                pygame.draw.rect(self.screen, self.colors['highlight'], (x-3, y-3, slot_width+6, slot_height+6), border_radius=5)

            pygame.draw.rect(self.screen, self.colors['npc_slots'], (x, y, slot_width, slot_height), border_radius=5)
            spirit = npc.spirit_slots[i]
            if spirit:
                self.draw_text(f"[{i+1}] {spirit.name}", x+5, y+5)
                self.draw_text(f"HP: {spirit.current_hp}/{spirit.max_hp}", x+5, y+25)
                self.draw_text(f"P:{spirit.power} D:{spirit.defense}", x+5, y+45)
                self.draw_text(f"Cost:{spirit.activation_cost}", x+5, y+65)
            else:
                self.draw_text(f"Spirit [{i+1}]", x+5, y+5)

        # --- TRACKS (Top) ---
        pygame.draw.rect(self.screen, self.colors['hp_track'], (50, 40, 200, 30))
        hp_text = f"NPC HP: {npc.wizard_hp}/20"
        self.draw_text(hp_text, 60, 45)

        pygame.draw.rect(self.screen, self.colors['aether_track'], (300, 40, 200, 30))
        aether_text = f"Aether: {npc.aether}/16"
        self.draw_text(aether_text, 310, 45)


    def draw_game_info(self):
        phase_text = f"Turn {self.game.turn_count} - {self.game.current_player.upper()} - Phase: {self.game.current_phase.value}"
        self.draw_text(phase_text, 50, 820)

        # --- MODIFIED: Show contextual prompt ---
        if self.action_prompt:
             self.draw_text(self.action_prompt, 50, 850, color=self.colors['prompt_text'])
        else:
            commands = "Actions: [1]Summon [2]Prepare [3]Activate [4]Attack [5]End Phase [R]New Game"
            self.draw_text(commands, 50, 850)

        # Draw player hand
        # --- (This section has been removed and moved to draw_player_side) ---

        # Draw last message
        self.draw_text(f"Log: {self.last_message}", 50, 880, color=self.colors['log_text'], wrap=True, max_width=900) # --- Adjusted Y from 850 to 880 and X from 300 to 50 ---

    def draw_text(self, text, x, y, color=None, wrap=False, max_width=110):
        if color is None:
            color = self.colors['text']

        if not wrap:
            text_surface = self.font.render(text, True, color)
            self.screen.blit(text_surface, (x, y))
            return

        # --- Word wrap logic ---
        words = text.split(' ')
        line_spacing = 2
        line_height = self.font.get_linesize() + line_spacing

        lines = []
        current_line = ""

        if " " not in text:
            if self.font.size(text)[0] > max_width:
                est_chars = max(1, max_width // self.font.size('a')[0])
                lines.append(text[:est_chars] + '...')
            else:
                lines.append(text)
        else:
            for word in words:
                test_line = current_line
                if test_line:
                    test_line += " " + word
                else:
                    test_line = word

                if self.font.size(test_line)[0] <= max_width:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word
            lines.append(current_line)

        for i, line in enumerate(lines):
            text_surface = self.font.render(line, True, color)
            self.screen.blit(text_surface, (x, y + i * line_height))

    # --- THIS IS THE NEW INPUT HANDLER ---
    def handle_input(self):
        player = self.game.players["player"]

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            # Global keys
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.input_mode != "NORMAL":
                        self.reset_input_state()
                        self.last_message = "Action canceled."
                    else:
                        return False # Quit
                if event.key == pygame.K_r:
                    self.game = ArcanaGame()
                    self.last_message = "New game started!"
                    self.reset_input_state()
                    return True 

            if self.game.game_over or self.game.current_player != "player":
                if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                    self.game = ArcanaGame()
                    self.last_message = "New game started!"
                    self.reset_input_state()
                    return True
                continue 

            # --- State Machine Logic ---
            if event.type == pygame.KEYDOWN:
                key = event.key

                # 0-9 number keys
                num_key = -1
                if pygame.K_0 <= key <= pygame.K_9:
                    num_key = key - pygame.K_0
                if pygame.K_KP0 <= key <= pygame.K_KP9:
                    num_key = key - pygame.K_KP0

                # --- NORMAL MODE: Select an action ---
                if self.input_mode == "NORMAL":
                    if key == pygame.K_1: # Summon
                        if self.game.current_phase != Phase.MEMORIZATION:
                            self.last_message = "Can only summon in Memorization phase."
                            continue
                        self.input_mode = "SUMMON_CARD"
                        self.action_prompt = "Select a Spirit from hand [1-9] (ESC to cancel)"
                    elif key == pygame.K_2: # Prepare
                        if self.game.current_phase != Phase.MEMORIZATION:
                            self.last_message = "Can only prepare in Memorization phase."
                            continue
                        self.input_mode = "PREPARE_CARD"
                        self.action_prompt = "Select a Spell from hand [1-9] (ESC to cancel)"
                    elif key == pygame.K_3: # Activate
                        if self.game.current_phase != Phase.INVOCATION:
                            self.last_message = "Can only activate in Invocation phase."
                            continue
                        self.input_mode = "ACTIVATE_SLOT"
                        self.action_prompt = "Select a Spell slot to activate [1-4] (ESC to cancel)"
                    elif key == pygame.K_4: # Attack
                        if self.game.current_phase != Phase.INVOCATION:
                            self.last_message = "Can only attack in Invocation phase."
                            continue
                        self.input_mode = "ATTACK_SLOT"
                        self.action_prompt = "Select your Spirit to attack with [1-3] (ESC to cancel)"
                    elif key == pygame.K_5: # End Phase
                        self.game.next_phase()
                        self.last_message = f"Phase advanced to {self.game.current_phase.value}"

                # --- SUMMON MODE ---
                elif self.input_mode == "SUMMON_CARD":
                    if 1 <= num_key <= len(player.hand):
                        card = player.hand[num_key - 1]
                        if card.type == "spirit":
                            self.selected_card = card
                            self.input_mode = "SUMMON_SLOT"
                            self.action_prompt = f"Select slot for {card.name} [1-3] (ESC to cancel)"
                        else:
                            self.last_message = f"{card.name} is not a Spirit. Select a Spirit."
                    else:
                        self.last_message = "Invalid hand number."

                elif self.input_mode == "SUMMON_SLOT":
                    if 1 <= num_key <= 3:
                        slot_index = num_key - 1
                        success, message = self.game.summon_spirit("player", self.selected_card.name, slot_index)
                        self.last_message = message
                        self.reset_input_state()
                    else:
                        self.last_message = "Invalid slot number. Select [1-3]."

                # --- PREPARE MODE ---
                elif self.input_mode == "PREPARE_CARD":
                    if 1 <= num_key <= len(player.hand):
                        card = player.hand[num_key - 1]
                        if card.type == "spell":
                            self.selected_card = card
                            self.input_mode = "PREPARE_SLOT"
                            self.action_prompt = f"Select slot for {card.name} [1-4] (ESC to cancel)"
                        else:
                            self.last_message = f"{card.name} is not a Spell. Select a Spell."
                    else:
                        self.last_message = "Invalid hand number."

                elif self.input_mode == "PREPARE_SLOT":
                    if 1 <= num_key <= 4:
                        slot_index = num_key - 1
                        success, message = self.game.prepare_spell("player", self.selected_card.name, slot_index)
                        self.last_message = message
                        self.reset_input_state()
                    else:
                        self.last_message = "Invalid slot number. Select [1-4]."

                # --- ACTIVATE MODE ---
                elif self.input_mode == "ACTIVATE_SLOT":
                    if 1 <= num_key <= 4:
                        slot_index = num_key - 1
                        if not player.spell_slots[slot_index]:
                            self.last_message = "That slot is empty."
                            continue
                        success, message = self.game.activate_spell("player", slot_index, 1)
                        self.last_message = message
                        self.reset_input_state()
                    else:
                        self.last_message = "Invalid slot number. Select [1-4]."

                # --- ATTACK MODE ---
                elif self.input_mode == "ATTACK_SLOT":
                    if 1 <= num_key <= 3:
                        slot_index = num_key - 1
                        spirit = player.spirit_slots[slot_index]
                        if not spirit:
                            self.last_message = "That slot is empty."
                            continue
                        if player.aether < spirit.activation_cost:
                            self.last_message = f"Not enough Aether for {spirit.name}."
                            continue

                        self.selected_slot = slot_index
                        self.input_mode = "ATTACK_TARGET"
                        self.action_prompt = f"Select target for {spirit.name} [1-3], or [0] for Wizard (ESC to cancel)"
                    else:
                        self.last_message = "Invalid slot number. Select [1-3]."

                elif self.input_mode == "ATTACK_TARGET":
                    if 0 <= num_key <= 3:
                        attacker_slot = self.selected_slot
                        if num_key == 0: # Target Wizard
                            success, message = self.game.attack_with_spirit("player", attacker_slot, "wizard")
                        else: # Target Spirit
                            target_slot = num_key - 1
                            success, message = self.game.attack_with_spirit("player", attacker_slot, "spirit", target_slot)

                        self.last_message = message
                        self.reset_input_state()
                    else:
                        self.last_message = "Invalid target. Select NPC spirit [1-3] or Wizard [0]."

        return True

    def run(self):
        running = True
        while running:
            running = self.handle_input()

            # AI turn logic
            if self.game.current_player == "npc" and not self.game.game_over:
                pygame.time.delay(250) # Short pause
                self.ai.execute_ai_turn(self.game)
                self.last_message = "NPC turn finished. Your turn."
                self.reset_input_state()

            self.draw_board()
            self.clock.tick(30)

        pygame.quit()

if __name__ == "__main__":
    visualizer = ArcanaVisualizer()
    visualizer.run()