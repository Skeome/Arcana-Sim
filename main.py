# This will act as a simulator for quickly testing and balancing game mechanics
# PyGame vizualization and input loop
import pygame
import sys
from game_engine import ArcanaGame
from card_manager import CardManager
from ai_controller import AIController

class ArcanaVisualizer:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode(1200, 800)
        pygame.display.pygame.display.set_caption("Arcana Simulator")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.pygame.font.SysFont('Noto-Sans', 16, bold=False, italic=False)
        self.game = ArcanaGame()
        self.card_manager = CardManager()
        self.ai = AIController()

        # Color scheme
        self.colors = {
            'background': (240, 240, 240),
            'player_slots': (200, 230, 255),
            'npc_slots': (255, 200, 200),
            'text': (0, 0, 0),
            'hp_track': (255, 100, 100),
            'aether_track': (100, 100, 255)
        }
    
    def draw_board(self):
        self.screen.fill(self.colors['background'])

        # Draw Player Side
        self.draw_player_side()

        # Draw NPC Side
        self.draw_npc_side()

        # Draw turn info
        self.draw_game_info()

        pygame.display.flip()

    def draw_player_side(self):
        # Player HP and Aether tracks
        pygame.draw.rect(self.screen, self.colors['hp_track'], (50, 650, 200, 30))
        hp_text = f"HP: {self.game.player.wizard_hp}/20"
        self.draw_text(hp_text, 60, 665)

        pygame.draw.rect(self.screen, self.colors['aether_track'], (300, 650, 200, 30))
        aether_text = f"Aether: {self.game.player.aether}/16"
        self.draw_text(aether_text, 310, 655)

        # Player Spirit Slots (3)
        for i in range(3):
            x, y = 100 + i * 150, 450
            pygame.draw.rect(self.screen, self.colors['player_slots'], (x, y, 120, 80))
            spirit = self.game.player.spirit_slots[i]
            if spirit:
                self.draw_text(f"Spirit {i+1}: {spirit.name}", x+5, y+5)
                self.draw_text(f"P:{spirit.power} D:{spirit.defense} HP:{spirit.current_hp}/{spirit.max_hp}", x+5, y+25)
                self.draw_text(f"Cost:{spirit.activation_cost}", x+5, y+45)

        # Player Spell Slots (4)
        for i in range(4):
            x, y = 100 + i * 150, 550
            pygame.draw.rect(self.screen, self.colors['player_slots'], (x, y, 120, 80))
            spell_stack = self.game.player.spell_slots[i]
            if spell_stack:
                spell = spell_stack[0] # First card in stack
                self.draw_text(f"Spell {i+1}: {spell.name} x{len(spell_stack)}", x+5, y+5)
                self.draw_text(f"Cost: {spell.activation_cost}", x+5, y+25)
                self.draw_text(f"Effect: {spell.effect_desc}", x+5, y+45)

    def draw_npc_side(self):
        # Similar to player side, but positioned at top
        # NPC HP and Aether
        pygame.draw.rect(self.screen, self.colors['hp_track'], (50, 50, 200, 30))
        hp_text = f"NPC HP: {self.game.npc.wizard_hp}/20"
        self.draw_text(hp_text, 60, 55)

        pygame.draw.rect(self.screen, self.colors['aether_track'], (300, 650, 200, 30))
        aether_text = f"Aether: {self.game.npc.aether}/16"
        self.draw_text(aether_text, 310, 655)

        # NPC Spirit Slots (3)
        for i in range(3):
            x, y = 100 + i * 150, 150
            pygame.draw.rect(self.screen, self.colors['npc_slots'], (x, y, 120, 80))
            spirit = self.game.npc.spirit_slots[i]
            if spirit:
                self.draw_text(f"Spirit {i+1}: {spirit.name}", x+5, y+5)
                self.draw_text(f"P:{spirit.power} D:{spirit.defense} HP:{spirit.current_hp}/{spirit.max_hp}", x+5, y+25)
                self.draw_text(f"Cost:{spirit.activation_cost}", x+5, y+45)

        # NPC Spell Slots (4)
        for i in range(4):
            x, y = 100 + i * 150, 250
            pygame.draw.rect(self.screen, self.colors['npc_slots'], (x, y, 120, 80))
            spell_stack = self.game.npc.spell_slots[i]
            if spell_stack:
                spell = spell_stack[0] # First card in stack
                self.draw_text(f"Spell {i+1}: {spell.name} x{len(spell_stack)}", x+5, y+5)
                self.draw_text(f"Cost: {spell.activation_cost}", x+5, y+25)
                self.draw_text(f"Effect: {spell.effect_desc}", x+5, y+45)

    def draw_game_info(self):
        phase_text = f"Turn {self.game.turn_count} - {self.game.current_player} - Phase: {self.game.current_phase}"
        self.draw_text(phase_text, 50, 700)

        # Available commands
        commands = "Commands: [1]Summon [2]Prepare [3]Activate [4]Attack [5]End Turn [6]New Game"
        self.draw_text(commands, 50, 720)

    def draw_text(self, text, x, y):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if self.game.current_player == "player":
                    if event.key == pygame.K_1:
                        self.summon_spirit()
                    elif event.key == pygame.K_2:
                        self.prepare_spell()
                    elif event.key == pygame.K_3:
                        self.activate_spell()
                    elif event.key == pygame.K_4:
                        self.attack()
                    elif event.key == pygame.K_5:
                        self.end_turn()
                    elif event.key == pygame.K_6:
                        self.game = ArcanaGame()    # Reset game
                elif event.key == pygame.K_ESCAPE:
                    return False
        return True
    
    def summon_spirit(self):
        if self.game.current_phase == "memorization":
            # Simple text input for which Spirit to summon
            spirit_name = input("Enter Spirit name to summon: ")
            slot = int(input("Enter slot (1-3): ")) - 1
            self.game.summon_spirit("player", spirit_name, slot)

    def prepare_spell(self):
        if self.game.current_phase == "memorization":
            spell_name = input("Enter spell name to prepare: ")
            slot = int(input("Enter slot (1-4): ")) - 1
            self.game.prepare_spell("player", spell_name, slot)

    def run(self):
        running = True
        while running:
            running = self.handle_input()
            self.draw_board()
            self.clock.tick(30)

            # Auto advance NPC turns
            #if self.game.current_player == "npc" and self.game.current_phase == "attunement":
            if self.game.current_player == "npc" and not self.game.game_over:
                pygame.time.delay(1000) # Brief pause to see NPC actions
                #self.game.execute_npc_turn()
                self.ai.execute_ai_turn(self.game)
        
        pygame.quit()

if __name__ == "__main__":
    visualizer = ArcanaVisualizer()
    visualizer.run()