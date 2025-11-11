import random
from game_engine import Phase

class AIController:
    def __init__(self, difficulty="medium"):
        self.difficulty = difficulty
        self.last_action = None
    
    def get_move(self, game):
        """Returns the next move for the NPC based on current game state"""
        player_state = game.players["npc"]
        opponent_state = game.players["player"]
        
        if game.current_phase == Phase.MEMORIZATION:
            # --- ADDED: Check one card rule ---
            if player_state.placed_card_this_turn:
                return {"type": "advance_phase"}
            return self.get_memorization_move(game, player_state, opponent_state)
        elif game.current_phase == Phase.INVOCATION:
            return self.get_invocation_move(game, player_state, opponent_state)
        else:
            return {"type": "advance_phase"}
    
    def get_memorization_move(self, game, player, opponent):
        """Decide what to do during memorization phase"""
        moves = []
        
        # 1. Try to summon spirits if we have empty slots
        empty_spirit_slots = [i for i, spirit in enumerate(player.spirit_slots) if spirit is None]
        if empty_spirit_slots and player.hand:
            # Find spirits in hand
            spirits_in_hand = [card for card in player.hand if card.type == "spirit"]
            if spirits_in_hand:
                spirit = self.choose_best_spirit(spirits_in_hand)
                slot = empty_spirit_slots[0]
                return {"type": "summon_spirit", "spirit_name": spirit.name, "slot_index": slot}
        
        # 2. Try to prepare spells
        if player.hand:
            # Find spells in hand
            spells_in_hand = [card for card in player.hand if card.type == "spell"]
            if spells_in_hand:
                # Try to stack existing spells first
                for slot_idx, spell_stack in enumerate(player.spell_slots):
                    if spell_stack and len(spell_stack) < 3:  # Stack not full
                        stack_spell_name = spell_stack[0].name
                        # Check if we have more of this spell in hand
                        for spell in spells_in_hand:
                            if spell.name == stack_spell_name:
                                return {"type": "prepare_spell", "spell_name": spell.name, "slot_index": slot_idx}
                
                # No stacks to add to, find empty slot
                empty_spell_slots = [i for i, stack in enumerate(player.spell_slots) if not stack]
                if empty_spell_slots:
                    spell = self.choose_best_spell(spells_in_hand, game)
                    slot = empty_spell_slots[0]
                    return {"type": "prepare_spell", "spell_name": spell.name, "slot_index": slot}
        
        # 3. Replace weak spells if no other options
        spells_in_hand = [card for card in player.hand if card.type == "spell"]
        if player.spell_slots and spells_in_hand:
            # Find weakest spell stack (lowest activation cost or damage)
            weakest_slot = self.find_weakest_spell_slot(player.spell_slots)
            if weakest_slot is not None:
                # Check if we have a better spell in hand
                better_spell = self.find_better_spell(spells_in_hand, player.spell_slots[weakest_slot][0])
                if better_spell:
                    return {"type": "replace_spell", "slot_index": weakest_slot, "new_spell_name": better_spell.name}
        
        # 4. No valid moves, advance phase
        return {"type": "advance_phase"}
    
    def get_invocation_move(self, game, player, opponent):
        """Decide what to do during invocation phase"""
        moves = []
        
        # 1. Activate damaging spells if opponent has spirits
        opponent_has_spirits = any(opponent.spirit_slots)
        if opponent_has_spirits:
            for slot_idx, spell_stack in enumerate(player.spell_slots):
                if spell_stack and "damage" in spell_stack[0].effect.lower():
                    spell = spell_stack[0]
                    # Check if we can afford to use at least one copy
                    if player.aether >= spell.activation_cost:
                        # Use all copies if we can afford it
                        max_copies = min(len(spell_stack), player.aether // spell.activation_cost)
                        if max_copies > 0:
                            return {"type": "activate_spell", "slot_index": slot_idx, "copies_used": max_copies}
        
        # 2. Activate healing spells if we're low on HP
        if player.wizard_hp <= 10:  # Below 50% HP
            for slot_idx, spell_stack in enumerate(player.spell_slots):
                if spell_stack and "heal" in spell_stack[0].effect.lower():
                    spell = spell_stack[0]
                    if player.aether >= spell.activation_cost:
                        max_copies = min(len(spell_stack), player.aether // spell.activation_cost)
                        if max_copies > 0:
                            return {"type": "activate_spell", "slot_index": slot_idx, "copies_used": max_copies}
        
        # 3. Attack with spirits
        for slot_idx, spirit in enumerate(player.spirit_slots):
            if spirit and player.aether >= spirit.activation_cost:
                # Check if we can attack wizard directly
                can_attack_directly = (not opponent_has_spirits) or ("directly" in spirit.effect.lower())
                
                if can_attack_directly:
                    # Attack wizard if we can kill or do significant damage
                    if spirit.power >= opponent.wizard_hp or spirit.power >= 4:
                        return {"type": "attack", "spirit_slot": slot_idx, "target_type": "wizard"}
                
                # Otherwise, attack enemy spirits
                if opponent_has_spirits:
                    # Find the best target (weakest spirit we can kill)
                    target_info = self.find_best_attack_target(spirit, opponent.spirit_slots)
                    if target_info:
                        target_slot, can_kill = target_info
                        if can_kill or self.difficulty == "easy":  # Easy AI attacks regardless
                            return {"type": "attack", "spirit_slot": slot_idx, "target_type": "spirit", "target_index": target_slot}
        
        # 4. No valid moves, advance phase
        return {"type": "advance_phase"}
    
    def choose_best_spirit(self, spirits):
        """Choose the best spirit to summon based on stats and abilities"""
        if not spirits:
            return None
        
        # Simple scoring system
        def score_spirit(spirit):
            score = spirit.power + spirit.defense + (spirit.max_hp / 4)
            if "directly" in spirit.effect.lower():
                score += 2  # Bonus for overwhelm ability
            if "reduce" in spirit.effect.lower():
                score += 1  # Bonus for debuff ability
            return score
        
        return max(spirits, key=score_spirit)
    
    def choose_best_spell(self, spells, game):
        """Choose the best spell to prepare"""
        if not spells:
            return None
        
        opponent_has_spirits = any(game.players["player"].spirit_slots)
        
        def score_spell(spell):
            score = 0
            if "damage" in spell.effect.lower() and opponent_has_spirits:
                score += spell.scaling * 2  # Higher value for damage when opponent has spirits
            elif "heal" in spell.effect.lower():
                score += spell.scaling  # Healing is
            score -= spell.activation_cost  # Lower cost is better
            return score
        
        return max(spells, key=score_spell)
    
    def find_weakest_spell_slot(self, spell_slots):
        """Find the spell slot with the weakest spell"""
        weakest_score = float('inf')
        weakest_slot = None
        
        for slot_idx, stack in enumerate(spell_slots):
            if stack:
                spell = stack[0]
                # Score based on cost and effect
                score = spell.activation_cost
                if "heal" in spell.effect.lower():
                    score += 1  # Slightly prefer to keep healing spells
                if score < weakest_score:
                    weakest_score = score
                    weakest_slot = slot_idx
        
        return weakest_slot
    
    def find_better_spell(self, hand, current_spell):
        """Find a spell in hand that's better than the current one"""
        for card in hand:
            if card.type == "spell":
                # Simple comparison: lower cost or higher scaling is better
                if (card.activation_cost < current_spell.activation_cost or 
                    (hasattr(card, 'scaling') and hasattr(current_spell, 'scaling') and 
                     card.scaling > current_spell.scaling)):
                    return card
        return None
    
    def find_best_attack_target(self, attacker, opponent_spirits):
        """Find the best spirit for this attacker to target"""
        best_target = None
        best_score = -1
        
        for slot_idx, defender in enumerate(opponent_spirits):
            if defender:
                # Calculate if we can kill it
                damage = max(0, attacker.power - defender.defense)
                can_kill = damage >= defender.current_hp
                
                # Score target (higher is better)
                score = 0
                if can_kill:
                    score += 10  # Big bonus for killing
                score += damage  # Prefer higher damage
                score -= defender.power  # Prefer weaker attackers
                
                if score > best_score:
                    best_score = score
                    best_target = (slot_idx, can_kill)
        
        return best_target
    
    def execute_ai_turn(self, game):
        """Execute the AI's turn by making moves until phase advances"""
        max_actions = 10  # Prevent infinite loops
        action_count = 0
        
        while (game.current_player == "npc" and 
               not game.game_over and
               action_count < max_actions):
            
            # Auto-advance attunement and respite
            if game.current_phase in [Phase.ATTAINMENT, Phase.RESPITE]:
                game.next_phase()
                continue # Loop again to process next phase

            move = self.get_move(game)
            
            if move["type"] == "advance_phase":
                game.next_phase()
                # If we're advancing from invocation, the turn is over
                if game.current_phase == Phase.RESPITE:
                    game.next_phase() # End the turn
                    break
            
            # --- MODIFIED: Stop after one placement move ---
            elif move["type"] == "summon_spirit":
                success, message = game.summon_spirit("npc", move["spirit_name"], move["slot_index"])
                game.next_phase() # Advance to Invocation after the one action
                break
            elif move["type"] == "prepare_spell":
                success, message = game.prepare_spell("npc", move["spell_name"], move["slot_index"])
                game.next_phase() # Advance to Invocation after the one action
                break
            elif move["type"] == "replace_spell":
                success, message = game.replace_spell("npc", move["new_spell_name"], move["slot_index"])
                game.next_phase() # Advance to Invocation after the one action
                break
            # --- End of placement moves ---

            elif move["type"] == "activate_spell":
                success, message = game.activate_spell("npc", move["slot_index"], move["copies_used"])
                # Continue even if activation fails (might be other moves)
            elif move["type"] == "attack":
                if move["target_type"] == "wizard":
                    success, message = game.attack_with_spirit("npc", move["spirit_slot"], "wizard")
                else:
                    success, message = game.attack_with_spirit("npc", move["spirit_slot"], "spirit", move["target_index"])
                # Continue even if attack fails
            
            action_count += 1
            
            # Check if game ended
            if game.game_over:
                break
        
        # Ensure turn ends if loop finishes
        if game.current_player == "npc" and not game.game_over:
            if game.current_phase != Phase.ATTAINMENT: # If we are not already on the next player's turn
                game.current_phase = Phase.RESPITE
                game.next_phase() # This will pass the turn