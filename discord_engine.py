import json
import random
import os
from enum import Enum

# Note: This file requires card_manager.py to be present
# but does not import it directly at the top.
# The CardManager instance is passed into the ArcanaGame constructor.

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
        self.placed_card_this_turn = False

class ArcanaGame:
    def __init__(self, card_manager, player1_id, player2_id):
        self.card_manager = card_manager
        self.player1_id = player1_id
        self.player2_id = player2_id
        
        self.players = {
            player1_id: PlayerState(str(player1_id)), # Use ID as name for now
            player2_id: PlayerState(str(player2_id))
        }
        self.current_player_id = player1_id # Player 1 (challenger) starts
        self.current_phase = Phase.ATTAINMENT
        self.turn_count = 1
        self.game_over = False
        self.winner = None
        
        # Initialize decks from JSON files
        self.initialize_decks()
    
    def _load_deck_from_file(self, file_path):
        """
        Loads a deck list from a .json file, creates card instances,
        and returns them as a list.
        """
        deck = []
        if not os.path.exists(file_path):
            print(f"Warning: Deck file not found: {file_path}")
            return deck

        try:
            with open(file_path, 'r') as f:
                deck_config = json.load(f)

            # Load spirits
            for card_id, quantity in deck_config.get("spirits", {}).items():
                for _ in range(quantity):
                    card_instance = self.card_manager.create_card_instance(card_id)
                    if card_instance:
                        deck.append(card_instance)
                    else:
                        print(f"Warning: Card ID '{card_id}' not found in card library.")
            
            # Load spells
            for card_id, quantity in deck_config.get("spells", {}).items():
                for _ in range(quantity):
                    card_instance = self.card_manager.create_card_instance(card_id)
                    if card_instance:
                        deck.append(card_instance)
                    else:
                        print(f"Warning: Card ID '{card_id}' not found in card library.")
        
        except Exception as e:
            print(f"Error loading deck from {file_path}: {e}")

        return deck

    def initialize_decks(self):
        """
        Initializes player decks by loading from their JSON config files.
        Player 1 (challenger) gets player_deck.json
        Player 2 (opponent) gets npc_deck.json
        """
        player_deck_file = "config/player_deck.json"
        opponent_deck_file = "config/npc_deck.json" # Player 2 uses the "npc" deck

        # Load decks
        self.players[self.player1_id].deck = self._load_deck_from_file(player_deck_file)
        self.players[self.player2_id].deck = self._load_deck_from_file(opponent_deck_file)
        
        # Shuffle and draw starting hands
        for player in self.players.values():
            if not player.deck:
                print(f"Warning: {player.name} has no deck. Check config files.")
                continue

            random.shuffle(player.deck)
            player.hand = [] # Ensure hand is empty
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
            self.current_player_id = self.get_opponent_id(self.current_player_id)
            self.current_phase = Phase.ATTAINMENT
            
            if self.current_player_id == self.player1_id: # Back to player 1
                self.turn_count += 1
            
            # Handle phase-specific logic (Attunement)
            self.handle_attunement_phase()

        else:
            self.current_phase = phases[current_index + 1]
    
    def handle_attunement_phase(self):
        player = self.players[self.current_player_id]
        
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
        
        # Reset turn flags
        player.wizard_ability_used = False
        player.placed_card_this_turn = False
    
    def get_opponent_id(self, player_id):
        """Returns the ID of the opponent."""
        return self.player2_id if player_id == self.player1_id else self.player1_id

    def summon_spirit(self, player_id, spirit_name, slot_index):
        if self.current_phase != Phase.MEMORIZATION:
            return False, "Can only summon during memorization phase"
        
        player = self.players[player_id]

        if player.placed_card_this_turn:
            return False, "Already placed a card this turn"
        
        # Find the spirit in hand
        spirit_card = None
        card_index_in_hand = -1
        for i, card in enumerate(player.hand):
            if card.type == "spirit" and card.name == spirit_name:
                spirit_card = card
                card_index_in_hand = i
                break
        
        if not spirit_card:
            return False, f"No {spirit_name} in hand"
        
        if not (0 <= slot_index < len(player.spirit_slots)):
            return False, "Invalid slot index"

        if player.spirit_slots[slot_index] is not None:
            return False, "Spirit slot is occupied"
        
        player.hand.pop(card_index_in_hand)
        player.spirit_slots[slot_index] = spirit_card
        
        player.placed_card_this_turn = True
        return True, f"Summoned {spirit_name} to slot {slot_index + 1}"
    
    def prepare_spell(self, player_id, spell_name, slot_index):
        if self.current_phase != Phase.MEMORIZATION:
            return False, "Can only prepare spells during memorization phase"
        
        player = self.players[player_id]
        
        if player.placed_card_this_turn:
            return False, "Already placed a card this turn"

        # Find the spell in hand
        spell_card = None
        card_index_in_hand = -1
        for i, card in enumerate(player.hand):
            if card.type == "spell" and card.name == spell_name:
                spell_card = card
                card_index_in_hand = i
                break
        
        if not spell_card:
            return False, f"No {spell_name} in hand"
        
        if not (0 <= slot_index < len(player.spell_slots)):
            return False, "Invalid slot index"
        
        if len(player.spell_slots[slot_index]) >= 3:
            return False, "Spell slot is full (max 3)"
        
        if player.spell_slots[slot_index] and player.spell_slots[slot_index][0].name != spell_name:
            return False, "Can only stack identical spells"
        
        player.hand.pop(card_index_in_hand)
        player.spell_slots[slot_index].append(spell_card)
        
        player.placed_card_this_turn = True
        return True, f"Prepared {spell_name} in slot {slot_index + 1}"

    def replace_spell(self, player_id, spell_name, slot_index):
        """Discards an entire spell stack and replaces it with a new spell from hand."""
        if self.current_phase != Phase.MEMORIZATION:
            return False, "Can only replace spells during memorization phase"
        
        player = self.players[player_id]
        
        if player.placed_card_this_turn:
            return False, "Already placed a card this turn"

        # Find the spell in hand
        spell_card = None
        card_index_in_hand = -1
        for i, card in enumerate(player.hand):
            if card.type == "spell" and card.name == spell_name:
                spell_card = card
                card_index_in_hand = i
                break
        
        if not spell_card:
            return False, f"No {spell_name} in hand"
        
        if not (0 <= slot_index < len(player.spell_slots)):
            return False, "Invalid spell slot index"
            
        # Discard all cards currently in that slot
        old_stack = player.spell_slots[slot_index]
        discard_count = 0
        if old_stack:
            for old_spell in old_stack:
                player.discard.append(old_spell)
                discard_count += 1
            
        player.hand.pop(card_index_in_hand)
        player.spell_slots[slot_index] = [spell_card] # Start a new stack
        
        player.placed_card_this_turn = True
        return True, f"Replaced slot {slot_index + 1} (discarded {discard_count}) with {spell_name}"

    def use_wizard_ability(self, player_id):
        """Uses the player's wizard ability (stubbed)."""
        if self.current_phase != Phase.MEMORIZATION:
            return False, "Can only use ability during memorization phase"
        
        player = self.players[player_id]

        if player.placed_card_this_turn:
            return False, "Already placed a card this turn"
        if player.wizard_ability_used:
            return False, "Wizard ability already used this turn"
        
        # TODO: Implement ability logic
        # For now, just mark as used and give 1 Aether
        player.aether = min(player.aether + 1, player.max_aether)
        player.wizard_ability_used = True
        player.placed_card_this_turn = True # Counts as the action
        return True, "Wizard ability used! (Gained 1 Aether)"

    def activate_spell(self, player_id, slot_index, copies_used):
        if self.current_phase != Phase.INVOCATION:
            return False, "Can only activate spells during invocation phase"
        
        player = self.players[player_id]
        opponent = self.players[self.get_opponent_id(player_id)]
        
        if not (0 <= slot_index < len(player.spell_slots)):
            return False, "Invalid slot index"
        
        if not player.spell_slots[slot_index]:
            return False, "No spells in that slot"
        
        if copies_used > len(player.spell_slots[slot_index]):
            copies_used = len(player.spell_slots[slot_index])
            if copies_used == 0:
                return False, "No copies in stack."

        spell = player.spell_slots[slot_index][0]
        total_cost = spell.activation_cost * copies_used
        
        if player.aether < total_cost:
            return False, f"Not enough Aether (have {player.aether}, need {total_cost})"
        
        player.aether -= total_cost
        
        effect_applied = False
        message = f"Activated {spell.name} x{copies_used}"

        # --- Resolve spell effects ---
        if spell.name in ["Firestorm", "Earthquake", "Wind Blade"]:
            damage = spell.scaling * copies_used
            message_parts = [message]
            targets_hit = 0
            for i, spirit in enumerate(opponent.spirit_slots):
                if spirit:
                    targets_hit += 1
                    actual_damage = max(0, damage - spirit.defense)
                    spirit.current_hp -= actual_damage
                    message_parts.append(f"{spirit.name} takes {actual_damage}")
                    if spirit.current_hp <= 0:
                        opponent.discard.append(spirit)
                        opponent.spirit_slots[i] = None
                        message_parts.append(f"{spirit.name} destroyed")
            
            effect_applied = True
            if targets_hit == 0:
                message = f"{spell.name} cast, but no enemy spirits."
            else:
                message = ", ".join(message_parts)
        
        elif spell.name == "Healing Wave":
            # Effect: "Heal 4 HP to spirit and 2 HP to wizard"
            # TODO: Add targeting for healing spirits.
            # For now, we'll just apply the wizard heal.
            wizard_heal = 2 * copies_used
            player.wizard_hp = min(20, player.wizard_hp + wizard_heal)
            effect_applied = True
            message = f"Healed {wizard_heal} HP to your wizard"
        
        # --- Finalize effect ---
        if effect_applied:
            for _ in range(copies_used):
                if player.spell_slots[slot_index]:
                    discarded_spell = player.spell_slots[slot_index].pop()
                    player.discard.append(discarded_spell)
        else:
            # Refund Aether if no effect was applied
            player.aether += total_cost
            return False, f"Could not activate {spell.name} (no valid targets?)"
        
        return effect_applied, message
    
    def attack_with_spirit(self, player_id, spirit_slot_index, target_type, target_index=None):
        if self.current_phase != Phase.INVOCATION:
            return False, "Can only attack during invocation phase"
        
        player = self.players[player_id]
        opponent = self.players[self.get_opponent_id(player_id)]
        
        if not (0 <= spirit_slot_index < len(player.spirit_slots)):
            return False, "Invalid attacker slot"

        spirit = player.spirit_slots[spirit_slot_index]
        if not spirit:
            return False, "No spirit in that slot"
        
        if player.aether < spirit.activation_cost:
            return False, f"Not enough Aether for {spirit.name}"
        
        player.aether -= spirit.activation_cost
        
        # --- Target: Wizard ---
        if target_type == "wizard":
            has_guard = any(opponent.spirit_slots)
            if has_guard and "directly" not in spirit.effect.lower():
                player.aether += spirit.activation_cost # Refund cost
                return False, "Cannot attack wizard (Guard Rule)"
            
            damage = max(0, spirit.power)
            opponent.wizard_hp -= damage
            message = f"{spirit.name} attacked wizard for {damage} damage"
            
            if opponent.wizard_hp <= 0:
                opponent.wizard_hp = 0
                self.game_over = True
                self.winner = player_id
            
        # --- Target: Spirit ---
        elif target_type == "spirit":
            if not (0 <= target_index < len(opponent.spirit_slots)):
                player.aether += spirit.activation_cost # Refund cost
                return False, "Invalid target slot"

            target_spirit = opponent.spirit_slots[target_index]
            if not target_spirit:
                player.aether += spirit.activation_cost # Refund cost
                return False, "No spirit in target slot"
            
            damage = max(0, spirit.power - target_spirit.defense)
            target_spirit.current_hp -= damage
            
            message_parts = [f"{spirit.name} attacked {target_spirit.name} for {damage} damage"]
            
            # Handle spirit effects
            if "reduce" in spirit.effect.lower() and "defense" in spirit.effect.lower():
                if "cannot be reduced" not in target_spirit.effect.lower():
                    target_spirit.defense = max(0, target_spirit.defense - 1)
                    message_parts.append("and reduced its defense by 1")
                else:
                    message_parts.append("but its defense cannot be reduced")
            
            if target_spirit.current_hp <= 0:
                opponent.discard.append(target_spirit)
                opponent.spirit_slots[target_index] = None
                message_parts.append("and destroyed it")
            
            message = " ".join(message_parts)
        
        else:
             player.aether += spirit.activation_cost # Refund cost
             return False, "Invalid target type"

        return True, message