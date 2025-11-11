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
        self.screen = pygame.display.set_mode((1200, 800))
        pygame.display.set_caption("Arcana Simulator") # Fixed typo
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont('Noto-Sans', 18, bold=False, italic=False) # Fixed typo and increased size
        self.game = ArcanaGame()
        self.card_manager = CardManager()
        self.ai = AIController()
        self.last_message = "Welcome to Arcana! Press [5] to start your turn."

        # Color scheme
        self.colors = {
            'background': (30, 30, 40),
            'player_slots': (60, 90, 120),
            'npc_slots': (120, 60, 60),
            'text': (230, 230, 230),
            'hp_track': (180, 50, 50),
            'aether_track': (50, 100, 180),
            'log_text': (200, 200, 100),
            'game_over': (255, 0, 0)
        }
    
    def draw_board(self):
        self.screen.fill(self.colors['background'])

        # Draw Player Side
        self.draw_player_side()

        # Draw NPC Side
        self.draw_npc_side()

        # Draw turn info
        self.draw_game_info()
        
        # Draw Game Over
        if self.game.game_over:
            self.draw_text(f"GAME OVER - {self.game.winner.upper()} WINS!", 400, 350, color=self.colors['game_over'])
            self.draw_text("Press [6] to play again", 400, 380, color=self.colors['game_over'])

        pygame.display.flip()

    def draw_player_side(self):
        player = self.game.players["player"] # Fixed state access

        # Player HP and Aether tracks
        pygame.draw.rect(self.screen, self.colors['hp_track'], (50, 650, 200, 30))
        hp_text = f"HP: {player.wizard_hp}/20"
        self.draw_text(hp_text, 60, 655)

        pygame.draw.rect(self.screen, self.colors['aether_track'], (300, 650, 200, 30))
        aether_text = f"Aether: {player.aether}/16"
        self.draw_text(aether_text, 310, 655)

        # Player Spirit Slots (3)
        for i in range(3):
            x, y = 100 + i * 160, 450
            pygame.draw.rect(self.screen, self.colors['player_slots'], (x, y, 120, 100), border_radius=5)
            spirit = player.spirit_slots[i]
            if spirit:
                self.draw_text(f"{spirit.name}", x+5, y+5)
                self.draw_text(f"HP: {spirit.current_hp}/{spirit.max_hp}", x+5, y+25)
                self.draw_text(f"P:{spirit.power} D:{spirit.defense}", x+5, y+45)
                self.draw_text(f"Cost:{spirit.activation_cost}", x+5, y+65)

        # Player Spell Slots (4)
        for i in range(4):
            x, y = 100 + i * 160, 560
            pygame.draw.rect(self.screen, self.colors['player_slots'], (x, y, 120, 80), border_radius=5)
            spell_stack = player.spell_slots[i]
            if spell_stack:
                spell = spell_stack[0] # First card in stack
                self.draw_text(f"{spell.name} x{len(spell_stack)}", x+5, y+5)
                self.draw_text(f"Cost: {spell.activation_cost}", x+5, y+25)
                self.draw_text(f"{spell.effect}", x+5, y+45) # Fixed attribute name

    def draw_npc_side(self):
        npc = self.game.players["npc"] # Fixed state access

        # NPC HP and Aether
        pygame.draw.rect(self.screen, self.colors['hp_track'], (50, 50, 200, 30))
        hp_text = f"NPC HP: {npc.wizard_hp}/20"
        self.draw_text(hp_text, 60, 55)

        pygame.draw.rect(self.screen, self.colors['aether_track'], (300, 50, 200, 30)) # Fixed y-position
        aether_text = f"Aether: {npc.aether}/16"
        self.draw_text(aether_text, 310, 55)

        # NPC Spirit Slots (3)
        for i in range(3):
            x, y = 100 + i * 160, 150
            pygame.draw.rect(self.screen, self.colors['npc_slots'], (x, y, 120, 100), border_radius=5)
            spirit = npc.spirit_slots[i]
            if spirit:
                self.draw_text(f"{spirit.name}", x+5, y+5)
                self.draw_text(f"HP: {spirit.current_hp}/{spirit.max_hp}", x+5, y+25)
                self.draw_text(f"P:{spirit.power} D:{spirit.defense}", x+5, y+45)
                self.draw_text(f"Cost:{spirit.activation_cost}", x+5, y+65)

        # NPC Spell Slots (4)
        for i in range(4):
            x, y = 100 + i * 160, 260
            pygame.draw.rect(self.screen, self.colors['npc_slots'], (x, y, 120, 80), border_radius=5)
            spell_stack = npc.spell_slots[i]
            if spell_stack:
                spell = spell_stack[0] # First card in stack
                self.draw_text(f"{spell.name} x{len(spell_stack)}", x+5, y+5)
                self.draw_text(f"Cost: {spell.activation_cost}", x+5, y+25)
                self.draw_text(f"{spell.effect}", x+5, y+45) # Fixed attribute name

    def draw_game_info(self):
        phase_text = f"Turn {self.game.turn_count} - {self.game.current_player.upper()} - Phase: {self.game.current_phase.value}"
        self.draw_text(phase_text, 50, 700)

        # Available commands
        commands = "Player Actions: [1]Summon [2]Prepare [3]Activate [4]Attack [5]End Phase [6]New Game"
        self.draw_text(commands, 50, 720)
        
        # Draw player hand
        self.draw_text("Player Hand:", 700, 450)
        player = self.game.players["player"]
        for i, card in enumerate(player.hand):
            hand_text = f"[{i+1}] {card.name} ({card.type})"
            self.draw_text(hand_text, 700, 480 + i * 20)

        # Draw last message
        self.draw_text(f"Log: {self.last_message}", 50, 750, color=self.colors['log_text'])

    # This is the new, correctly-named draw_text function
    def draw_text(self, text, x, y, color=None):
        if color is None:
            color = self.colors['text']
        
        # Simple word wrapping
        words = text.split(' ')
        line_spacing = 2
        max_width = 110 # Max width for card text
        line_height = self.font.get_linesize() + line_spacing
        
        lines = []
        current_line = ""
        
        # Handle the case where the input text is already just one word
        if " " not in text:
            lines.append(text)
        else:
            for word in words:
                if self.font.size(current_line + " " + word)[0] <= max_width:
                    current_line += " " + word
                else:
                    lines.append(current_line.strip())
                    current_line = word
            lines.append(current_line.strip())
        
        for i, line in enumerate(lines):
            text_surface = self.font.render(line, True, color)
            self.screen.blit(text_surface, (x, y + i * line_height))

    # This is the renamed input handling function
    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if self.game.game_over:
                    if event.key == pygame.K_6:
                        self.game = ArcanaGame()
                        self.last_message = "New game started!"
                    continue # Ignore other keys if game is over

                if self.game.current_player == "player":
                    if event.key == pygame.K_1:
                        self.player_action_summon()
                    elif event.key == pygame.K_2:
                        self.player_action_prepare()
                    elif event.key == pygame.K_3:
                        self.player_action_activate()
                    elif event.key == pygame.K_4:
                        self.player_action_attack()
                    elif event.key == pygame.K_5:
                        self.game.next_phase()
                        self.last_message = f"Phase advanced to {self.game.current_phase.value}"
                    elif event.key == pygame.K_6:
                        self.game = ArcanaGame()
                        self.last_message = "New game started!"
                
                if event.key == pygame.K_ESCAPE:
                    return False
        return True
    
    # --- New Player Action Handlers ---
    # These replace the old CLI input() functions
    
    def player_action_summon(self):
        """Summons the first available spirit from hand to the first empty slot."""
        if self.game.current_phase != Phase.MEMORIZATION:
            self.last_message = "Cannot summon outside Memorization phase."
            return
        
        player = self.game.players["player"]
        
        # Find first spirit in hand
        spirit_to_summon = None
        for card in player.hand:
            if card.type == "spirit":
                spirit_to_summon = card
                break
        
        # Find first empty slot
        slot = -1
        for i in range(len(player.spirit_slots)):
            if player.spirit_slots[i] is None:
                slot = i
                break
                
        if spirit_to_summon and slot != -1:
            success, message = self.game.summon_spirit("player", spirit_to_summon.name, slot)
            self.last_message = message
        elif not spirit_to_summon:
            self.last_message = "No spirits in hand to summon."
        else:
            self.last_message = "No empty spirit slots."
    
    def player_action_prepare(self):
        """Prepares the first available spell from hand to the first valid slot."""
        if self.game.current_phase != Phase.MEMORIZATION:
            self.last_message = "Cannot prepare outside Memorization phase."
            return

        player = self.game.players["player"]
        
        # Find first spell in hand
        spell_to_prepare = None
        for card in player.hand:
            if card.type == "spell":
                spell_to_prepare = card
                break
        
        if not spell_to_prepare:
            self.last_message = "No spells in hand to prepare."
            return

        # Find first available slot (empty or stackable)
        slot = -1
        for i in range(len(player.spell_slots)):
            stack = player.spell_slots[i]
            if not stack: # Empty slot
                slot = i
                break
            if stack and stack[0].name == spell_to_prepare.name and len(stack) < 3: # Stackable slot
                slot = i
                break
        
        if slot != -1:
            success, message = self.game.prepare_spell("player", spell_to_prepare.name, slot)
            self.last_message = message
        else:
            self.last_message = f"No valid slot for {spell_to_prepare.name}."

    def player_action_activate(self):
        """Activates 1 copy of the first available spell."""
        if self.game.current_phase != Phase.INVOCATION:
            self.last_message = "Cannot activate outside Invocation phase."
            return

        player = self.game.players["player"]

        # Find first non-empty spell slot
        slot = -1
        for i in range(len(player.spell_slots)):
            if player.spell_slots[i]:
                slot = i
                break
        
        if slot != -1:
            # Activate 1 copy
            success, message = self.game.activate_spell("player", slot, 1)
            self.last_message = message
        else:
            self.last_message = "No prepared spells to activate."
    
    def player_action_attack(self):
        """Attacks with the first available spirit."""
        if self.game.current_phase != Phase.INVOCATION:
            self.last_message = "Cannot attack outside Invocation phase."
            return

        player = self.game.players["player"]
        opponent = self.game.players["npc"]
        
        # Find first spirit that can attack
        attacker_slot = -1
        for i, spirit in enumerate(player.spirit_slots):
            if spirit and player.aether >= spirit.activation_cost:
                attacker_slot = i
                break
        
        if attacker_slot == -1:
            self.last_message = "No spirits ready (or not enough Aether)."
            return
        
        # Find target
        opponent_has_spirits = any(opponent.spirit_slots)
        attacker = player.spirit_slots[attacker_slot]
        
        if not opponent_has_spirits or "directly" in attacker.effect.lower():
            # Attack wizard
            success, message = self.game.attack_with_spirit("player", attacker_slot, "wizard")
            self.last_message = message
        else:
            # Attack first enemy spirit
            target_slot = -1
            for i, spirit in enumerate(opponent.spirit_slots):
                if spirit:
                    target_slot = i
                    break
            
            if target_slot != -1:
                success, message = self.game.attack_with_spirit("player", attacker_slot, "spirit", target_slot)
                self.last_message = message
            else:
                self.last_message = "Error: Opponent has spirits, but none found?"

    def run(self):
        running = True
        while running:
            running = self.handle_input()
            
            # AI turn logic
            if self.game.current_player == "npc" and not self.game.game_over:
                pygame.time.delay(500) # Brief pause to see NPC actions
                self.ai.execute_ai_turn(self.game)
                self.last_message = "NPC turn finished."

            self.draw_board()
            self.clock.tick(30)
        
        pygame.quit()

if __name__ == "__main__":
    visualizer = ArcanaVisualizer()
    visualizer.run()