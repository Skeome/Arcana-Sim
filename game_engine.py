import json
import random # Import at top
from enum import Enum

class Phase(Enum):
    ATTAINMENT = "attunement"
    MEMORIZATION = "memorization"
    INVOCATION = "invocation"
    RESPITE = "respite"

class Card:
    def __init__(self, name, card_type, activation_cost, power=0, defense=0, hp=0, effect="", scaling=0, element=""):
        self.name = name
        self.type = card_type  # "spirit" or "spell"
        self.activation_cost = activation_cost
        self.power = power
        self.defense = defense
        self.max_hp = hp
        self.current_hp = hp
        self.effect = effect
        self.scaling = scaling
        self.element = element

class PlayerState:
    def __init__(self, name):
        self.name = name
        self.wizard_hp = 20
        self.aether = 0
        self.max_aether = 16
        self.hand = []
        self.deck = []
        self.discard = []
        self.spirit_slots = [None, None, None]  # 3 slots
        self.spell_slots = [[], [], [], []]     # 4 slots, each can hold a stack
        self.wizard_ability_used = False

class ArcanaGame:
    def __init__(self):
        self.players = {
            "player": PlayerState("player"),
            "npc": PlayerState("npc")
        }
        self.current_player = "player"
        self.current_phase = Phase.ATTAINMENT
        self.turn_count = 1
        self.game_over = False
        self.winner = None
        
        # Initialize with some test cards
        self.initialize_test_decks()
    
    def initialize_test_decks(self):
        # Simple test decks for both players
        test_spirits = [
            Card("Stone Golem", "spirit", 1, 2, 3, 8, "Defense cannot be reduced"),
            Card("Frost Wyrm", "spirit", 2, 4, 1, 12, "Reduce target defense by 1"),
            Card("Inferno Dragon", "spirit", 3, 6, 0, 16, "Can attack wizard directly")
        ]
        
        test_spells = [
            Card("Firestorm", "spell", 3, effect="Deal 3 damage to all enemy spirits", scaling=3),
            Card("Healing Wave", "spell", 2, effect="Heal 4 HP to wizard", scaling=4)
        ]
        
        # Give each player 3 of each spirit and 2 of each spell
        for player in self.players.values():
            for spirit in test_spirits:
                for _ in range(3):
                    player.deck.append(Card(spirit.name, spirit.type, spirit.activation_cost, 
                                          spirit.power, spirit.defense, spirit.max_hp, spirit.effect))
            for spell in test_spells:
                for _ in range(2):
                    player.deck.append(Card(spell.name, spell.type, spell.activation_cost, 
                                          effect=spell.effect, scaling=spell.scaling))
            
            # Shuffle and draw starting hand of 7
            random.shuffle(player.deck)
            for _ in range(7):
                if player.deck:
                    player.hand.append(player.deck.pop())
    
    def next_phase(self):
        if self.game_over:
            return

        phases = list(Phase)
        current_index = phases.index(self.current_phase)
        
        if current_index == len(phases) - 1:
            # End of turn, switch players
            self.current_player = "npc" if self.current_player == "player" else "player"
            self.current_phase = Phase.ATTAINMENT
            if self.current_player == "player":
                self.turn_count += 1
            
            # Handle phase-specific logic (Attunement)
            self.handle_attunement_phase()

        else:
            self.current_phase = phases[current_index + 1]
        
        # Handle phase-specific logic (e.g., if we just entered Attunement)
        # This was slightly bugged, logic should be at start of phase
        # if self.current_phase == Phase.ATTAINMENT:
        #     self.handle_attunement_phase()
    
    def handle_attunement_phase(self):
        player = self.players[self.current_player]
        
        # Draw 1 card
        if player.deck:
            player.hand.append(player.deck.pop())
        elif player.discard: # Reshuffle discard pile if deck is empty
            print(f"{player.name} reshuffling discard pile!")
            player.deck = player.discard
            player.discard = []
            random.shuffle(player.deck)
            if player.deck:
                player.hand.append(player.deck.pop())
        
        # Gain 2 Aether
        player.aether = min(player.aether + 2, player.max_aether)
        
        # Reset wizard ability
        player.wizard_ability_used = False
    
    def get_opponent_name(self, player_name):
        return "npc" if player_name == "player" else "player"

    def summon_spirit(self, player_name, spirit_name, slot_index):
        if self.current_phase != Phase.MEMORIZATION:
            return False, "Can only summon during memorization phase"
        
        player = self.players[player_name]
        
        # Find the spirit in hand
        spirit_card = None
        for card in player.hand:
            if card.type == "spirit" and card.name == spirit_name:
                spirit_card = card
                break
        
        if not spirit_card:
            return False, f"No {spirit_name} in hand"
        
        # Check if slot is empty
        if player.spirit_slots[slot_index] is not None:
            return False, "Spirit slot is occupied"
        
        # Remove from hand and place in slot
        player.hand.remove(spirit_card)
        player.spirit_slots[slot_index] = spirit_card
        
        return True, f"Summoned {spirit_name} to slot {slot_index + 1}"
    
    def prepare_spell(self, player_name, spell_name, slot_index):
        if self.current_phase != Phase.MEMORIZATION:
            return False, "Can only prepare spells during memorization phase"
        
        player = self.players[player_name]
        
        # Find the spell in hand
        spell_card = None
        for card in player.hand:
            if card.type == "spell" and card.name == spell_name:
                spell_card = card
                break
        
        if not spell_card:
            return False, f"No {spell_name} in hand"
        
        # Check if we can add to stack (max 3)
        if len(player.spell_slots[slot_index]) >= 3:
            return False, "Spell slot is full (max 3)"
        
        # Check if adding to existing stack, must be same spell
        if player.spell_slots[slot_index] and player.spell_slots[slot_index][0].name != spell_name:
            return False, "Can only stack identical spells"
        
        # Remove from hand and add to slot
        player.hand.remove(spell_card)
        player.spell_slots[slot_index].append(spell_card)
        
        return True, f"Prepared {spell_name} in slot {slot_index + 1}"

    def replace_spell(self, player_name, spell_name, slot_index):
        """Discards an entire spell stack and replaces it with a new spell from hand."""
        if self.current_phase != Phase.MEMORIZATION:
            return False, "Can only replace spells during memorization phase"
        
        player = self.players[player_name]
        
        # Find the spell in hand
        spell_card = None
        for card in player.hand:
            if card.type == "spell" and card.name == spell_name:
                spell_card = card
                break
        
        if not spell_card:
            return False, f"No {spell_name} in hand"
        
        # Check if slot index is valid
        if not (0 <= slot_index < len(player.spell_slots)):
            return False, "Invalid spell slot index"
            
        # Discard all cards currently in that slot
        old_stack = player.spell_slots[slot_index]
        discard_count = 0
        if old_stack:
            for old_spell in old_stack:
                player.discard.append(old_spell)
                discard_count += 1
            
        # Remove from hand and place in slot
        player.hand.remove(spell_card)
        player.spell_slots[slot_index] = [spell_card] # Start a new stack
        
        return True, f"Replaced slot {slot_index + 1} (discarded {discard_count}) with {spell_name}"

    def use_wizard_ability(self, player_name):
        """Uses the player's wizard ability (stubbed)."""
        if self.current_phase != Phase.MEMORIZATION:
            return False, "Can only use ability during memorization phase"
        
        player = self.players[player_name]
        if player.wizard_ability_used:
            return False, "Wizard ability already used this turn"
        
        # TODO: Implement ability logic
        # For now, just mark as used and give 1 Aether
        player.aether = min(player.aether + 1, player.max_aether)
        player.wizard_ability_used = True
        return True, "Wizard ability used! (Gained 1 Aether)"

    def activate_spell(self, player_name, slot_index, copies_used):
        if self.current_phase != Phase.INVOCATION:
            return False, "Can only activate spells during invocation phase"
        
        player = self.players[player_name]
        opponent = self.players[self.get_opponent_name(player_name)]
        
        # Check if slot has spells
        if not player.spell_slots[slot_index]:
            return False, "No spells in that slot"
        
        # Check if we're trying to use more copies than available
        if copies_used > len(player.spell_slots[slot_index]):
            return False, f"Not enough copies in stack (have {len(player.spell_slots[slot_index])}, need {copies_used})"
        
        spell = player.spell_slots[slot_index][0]
        total_cost = spell.activation_cost * copies_used
        
        # Check if player has enough Aether
        if player.aether < total_cost:
            return False, f"Not enough Aether (have {player.aether}, need {total_cost})"
        
        # Pay cost
        player.aether -= total_cost
        
        # Resolve effect based on spell name
        effect_applied = False
        message = f"Activated {spell.name} x{copies_used}"

        if spell.name == "Firestorm":
            damage = spell.scaling * copies_used
            message_parts = []
            for i, spirit in enumerate(opponent.spirit_slots): # Use enumerate to get index
                if spirit:
                    # Calculate damage after defense
                    actual_damage = max(0, damage - spirit.defense)
                    spirit.current_hp -= actual_damage
                    message_parts.append(f"{spirit.name} takes {actual_damage}")
                    # Check if spirit died
                    if spirit.current_hp <= 0:
                        opponent.discard.append(spirit)
                        opponent.spirit_slots[i] = None # <-- Correct way to remove
                        message_parts.append(f"{spirit.name} destroyed")
            
            effect_applied = True
            if not message_parts:
                message = f"Firestorm cast, but no enemy spirits."
            else:
                message = ", ".join(message_parts)
        
        elif spell.name == "Healing Wave":
            # Simple logic: Heal wizard (as per your test card)
            healing = spell.scaling * copies_used
            player.wizard_hp = min(20, player.wizard_hp + healing)
            effect_applied = True
            message = f"Healed {healing} HP to your wizard"
        
        # Remove used copies
        for _ in range(copies_used):
            discarded_spell = player.spell_slots[slot_index].pop()
            player.discard.append(discarded_spell)
        
        return effect_applied, message
    
    def attack_with_spirit(self, player_name, spirit_slot_index, target_type, target_index=None):
        if self.current_phase != Phase.INVOCATION:
            return False, "Can only attack during invocation phase"
        
        player = self.players[player_name]
        opponent = self.players[self.get_opponent_name(player_name)]
        
        # Get attacking spirit
        spirit = player.spirit_slots[spirit_slot_index]
        if not spirit:
            return False, "No spirit in that slot"
        
        # Check activation cost
        if player.aether < spirit.activation_cost:
            return False, f"Not enough Aether for {spirit.name}"
        
        # Pay cost
        player.aether -= spirit.activation_cost
        
        # Determine target
        if target_type == "wizard":
            # Check Guard Rule
            has_guard = any(opponent.spirit_slots)
            if has_guard and "directly" not in spirit.effect.lower():
                return False, "Cannot attack wizard (Guard Rule)"
            
            # Attack wizard
            damage = max(0, spirit.power)  # Wizard has 0 defense
            opponent.wizard_hp -= damage
            message = f"{spirit.name} attacked wizard for {damage} damage"
            
            # Check for win condition
            if opponent.wizard_hp <= 0:
                opponent.wizard_hp = 0
                self.game_over = True
                self.winner = player_name
            
        elif target_type == "spirit":
            target_spirit = opponent.spirit_slots[target_index]
            if not target_spirit:
                return False, "No spirit in target slot"
            
            # Calculate damage
            damage = max(0, spirit.power - target_spirit.defense)
            target_spirit.current_hp -= damage
            
            # Handle spirit effects
            if "reduce target defense by 1" in spirit.effect.lower():
                target_spirit.defense = max(0, target_spirit.defense - 1)
            
            message = f"{spirit.name} attacked {target_spirit.name} for {damage} damage"
            
            # Check if target died
            if target_spirit.current_hp <= 0:
                opponent.discard.append(target_spirit)
                opponent.spirit_slots[target_index] = None
                message += f" and destroyed it"
        
        return True, message
    
    def execute_npc_turn(self):
        # This is now deprecated, AIController.execute_ai_turn is used instead
        from ai_controller import AIController
        ai = AIController()
        ai.execute_ai_turn(self)