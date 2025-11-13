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
    # --- ADDED 'effects' PARAMETER ---
    def __init__(self, name, card_type, activation_cost, power=0, defense=0, hp=0, effect="", scaling=0, element="", effects=None):
        self.name = name
        self.type = card_type  # "spirit" or "spell"
        self.activation_cost = activation_cost
        self.power = power
        self.defense = defense
        self.max_hp = hp
        self.current_hp = hp
        self.effect = effect # Keep for display
        self.scaling = scaling
        self.element = element
        self.effects = effects if effects is not None else {}

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
    
    def _load_deck_for_user(self, user_id, default_deck_path):
        """
        Loads a deck for a specific user ID.
        If config/decks/USER_ID.json exists and is not empty, loads that.
        Otherwise, loads the default_deck_path.
        """
        user_deck_file = f"config/decks/{user_id}.json"
        path_to_load = default_deck_path # Default
        
        # Check if user deck exists and is not empty
        if os.path.exists(user_deck_file) and os.path.getsize(user_deck_file) > 2: # > 2 to check if it's more than just "{}"
            try:
                with open(user_deck_file, 'r') as f:
                    deck_data = json.load(f)
                    if deck_data.get("spirits") or deck_data.get("spells"):
                        path_to_load = user_deck_file # Use custom deck
                        print(f"Loading custom deck for user {user_id} from {user_deck_file}")
                    else:
                         print(f"Custom deck for {user_id} is empty. Loading default: {default_deck_path}")
            except json.JSONDecodeError:
                 print(f"Error reading custom deck for {user_id}. Loading default: {default_deck_path}")
        else:
            # Don't print for bot user
            if not str(user_id).isnumeric(): # Simple check if it's not a bot's name
                 print(f"No custom deck for {user_id}. Loading default: {default_deck_path}")


        deck = []
        if not os.path.exists(path_to_load):
            print(f"Warning: Deck file not found for user {user_id} at {path_to_load}. Using empty deck.")
            return deck

        try:
            with open(path_to_load, 'r') as f:
                deck_config = json.load(f)

            # Load spirits
            for card_id, quantity in deck_config.get("spirits", {}).items():
                for _ in range(quantity):
                    card_instance = self.card_manager.create_card_instance(card_id)
                    if card_instance:
                        deck.append(card_instance)
                    else:
                        print(f"Warning: Card ID '{card_id}' in {path_to_load} not found in card library.")
            
            # Load spells
            for card_id, quantity in deck_config.get("spells", {}).items():
                for _ in range(quantity):
                    card_instance = self.card_manager.create_card_instance(card_id)
                    if card_instance:
                        deck.append(card_instance)
                    else:
                        print(f"Warning: Card ID '{card_id}' in {path_to_load} not found in card library.")
        
        except Exception as e:
            print(f"Error loading deck from {path_to_load}: {e}")

        return deck

    def initialize_decks(self):
        """
        Initializes player decks by loading their custom deck or the default.
        """
        # Player 1 (Challenger) uses their own deck or the default player_deck.json
        self.players[self.player1_id].deck = self._load_deck_for_user(
            self.player1_id, 
            "config/player_deck.json"
        )
        
        # Player 2 (Opponent) uses their own deck or the default npc_deck.json
        self.players[self.player2_id].deck = self._load_deck_for_user(
            self.player2_id, 
            "config/npc_deck.json" # Opponents use their own deck or the NPC default
        )
        
        # Shuffle and draw starting hands
        for player_id, player in self.players.items():
            if not player.deck:
                print(f"Warning: Player {player_id} has no deck (0 cards). Check config files.")
                continue

            random.shuffle(player.deck)
            player.hand = [] # Ensure hand is empty
            draw_count = min(7, len(player.deck)) # Don't draw more than in deck
            for _ in range(draw_count):
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

        # --- Resolve spell effects using keywords ---
        spell_effects = spell.effects
        message_parts = [message]

        if spell_effects.get("aoe_damage") and spell_effects.get("target") == "enemy_spirits":
            damage = spell.scaling * copies_used
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
        
        elif spell_effects.get("heal_wizard"):
            wizard_heal = spell_effects.get("heal_wizard", 0) * copies_used
            player.wizard_hp = min(20, player.wizard_hp + wizard_heal)
            message_parts = [f"Healed {wizard_heal} HP to your wizard"]
            
            # Check for spirit heal on the same card
            if spell_effects.get("heal_spirit"):
                # TODO: Add targeting for healing spirits.
                message_parts.append(f"({spell_effects.get('heal_spirit')} spirit heal not implemented)")

            effect_applied = True
            message = ", ".join(message_parts)
        
        # --- Finalize effect ---
        if effect_applied:
            for _ in range(copies_used):
                if player.spell_slots[slot_index]:
                    discarded_spell = player.spell_slots[slot_index].pop()
                    player.discard.append(discarded_spell)
        else:
            # Refund Aether if no effect was applied
            player.aether += total_cost
            return False, f"Could not activate {spell.name} (no valid targets or effect?)"
        
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
            # --- USE KEYWORD ---
            can_attack_directly = spirit.effects.get("direct_attack", False)

            if has_guard and not can_attack_directly:
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
            
            # --- Handle spirit effects using keywords ---
            reduce_amount = spirit.effects.get("reduce_defense")
            if reduce_amount:
                # Check if target is immune
                can_be_reduced = not target_spirit.effects.get("prevent_defense_reduction", False)
                
                if can_be_reduced:
                    target_spirit.defense = max(0, target_spirit.defense - reduce_amount)
                    message_parts.append(f"and reduced its defense by {reduce_amount}")
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