import random
from discord_engine import Phase

class DiscordAIController:
    def __init__(self, bot_id, difficulty="medium"):
        self.difficulty = difficulty
        self.bot_id = bot_id # <-- Store the bot's user ID
        self.last_action = None
    
    def get_move(self, game):
        """Returns the next move for the NPC based on current game state"""
        player_state = game.players[self.bot_id]
        opponent_id = game.get_opponent_id(self.bot_id)
        opponent_state = game.players[opponent_id]
        
        if game.current_phase == Phase.MEMORIZATION:
            if player_state.placed_card_this_turn:
                return {"type": "advance_phase"}
            return self.get_memorization_move(game, player_state, opponent_state)
        elif game.current_phase == Phase.INVOCATION:
            return self.get_invocation_move(game, player_state, opponent_state)
        else:
            return {"type": "advance_phase"}
    
    def get_memorization_move(self, game, player, opponent):
        """Decide what to do during memorization phase"""
        
        # 1. Try to summon spirits if we have empty slots
        empty_spirit_slots = [i for i, spirit in enumerate(player.spirit_slots) if spirit is None]
        if empty_spirit_slots and player.hand:
            spirits_in_hand = [card for card in player.hand if card.type == "spirit"]
            if spirits_in_hand:
                spirit = self.choose_best_spirit(spirits_in_hand)
                slot = empty_spirit_slots[0]
                return {"type": "summon_spirit", "spirit_name": spirit.name, "slot_index": slot}
        
        # 2. Try to prepare spells
        if player.hand:
            spells_in_hand = [card for card in player.hand if card.type == "spell"]
            if spells_in_hand:
                # Try to stack existing spells first
                for slot_idx, spell_stack in enumerate(player.spell_slots):
                    if spell_stack and len(spell_stack) < 3:
                        stack_spell_name = spell_stack[0].name
                        for spell in spells_in_hand:
                            if spell.name == stack_spell_name:
                                return {"type": "prepare_spell", "spell_name": spell.name, "slot_index": slot_idx}
                
                # No stacks to add to, find empty slot
                empty_spell_slots = [i for i, stack in enumerate(player.spell_slots) if not stack]
                if empty_spell_slots:
                    spell = self.choose_best_spell(spells_in_hand, game, opponent)
                    slot = empty_spell_slots[0]
                    return {"type": "prepare_spell", "spell_name": spell.name, "slot_index": slot}
        
        # 3. Replace weak spells if no other options
        spells_in_hand = [card for card in player.hand if card.type == "spell"]
        if player.spell_slots and spells_in_hand:
            weakest_slot = self.find_weakest_spell_slot(player.spell_slots)
            if weakest_slot is not None:
                better_spell = self.find_better_spell(spells_in_hand, player.spell_slots[weakest_slot][0])
                if better_spell:
                    return {"type": "replace_spell", "slot_index": weakest_slot, "new_spell_name": better_spell.name}
        
        # 4. No valid moves, advance phase
        return {"type": "advance_phase"}
    
    def get_invocation_move(self, game, player, opponent):
        """Decide what to do during invocation phase"""
        
        # 1. Activate damaging spells if opponent has spirits
        opponent_has_spirits = any(opponent.spirit_slots)
        if opponent_has_spirits:
            for slot_idx, spell_stack in enumerate(player.spell_slots):
                # Use new effects logic
                if spell_stack and spell_stack[0].effects.get("aoe_damage"):
                    spell = spell_stack[0]
                    if player.aether >= spell.activation_cost:
                        max_copies = min(len(spell_stack), player.aether // spell.activation_cost)
                        if max_copies > 0:
                            return {"type": "activate_spell", "slot_index": slot_idx, "copies_used": max_copies}
        
        # 2. Activate healing spells if we're low on HP
        if player.wizard_hp <= 10:
            for slot_idx, spell_stack in enumerate(player.spell_slots):
                # Use new effects logic
                if spell_stack and spell_stack[0].effects.get("heal_wizard"):
                    spell = spell_stack[0]
                    if player.aether >= spell.activation_cost:
                        max_copies = min(len(spell_stack), player.aether // spell.activation_cost)
                        if max_copies > 0:
                            return {"type": "activate_spell", "slot_index": slot_idx, "copies_used": max_copies}
        
        # 3. Attack with spirits
        for slot_idx, spirit in enumerate(player.spirit_slots):
            if spirit and player.aether >= spirit.activation_cost:
                # Use new effects logic
                can_attack_directly = (not opponent_has_spirits) or spirit.effects.get("direct_attack")
                
                if can_attack_directly:
                    if spirit.power >= opponent.wizard_hp or spirit.power >= 4:
                        return {"type": "attack", "spirit_slot": slot_idx, "target_type": "wizard"}
                
                if opponent_has_spirits:
                    target_info = self.find_best_attack_target(spirit, opponent.spirit_slots)
                    if target_info:
                        target_slot, can_kill = target_info
                        if can_kill or self.difficulty == "easy":
                            return {"type": "attack", "spirit_slot": slot_idx, "target_type": "spirit", "target_index": target_slot}
        
        # 4. No valid moves, advance phase
        return {"type": "advance_phase"}
    
    def choose_best_spirit(self, spirits):
        if not spirits: return None
        def score_spirit(spirit):
            score = spirit.power + spirit.defense + (spirit.max_hp / 4)
            if spirit.effects.get("direct_attack"): score += 2
            if spirit.effects.get("reduce_defense"): score += 1
            return score
        return max(spirits, key=score_spirit)
    
    def choose_best_spell(self, spells, game, opponent):
        if not spells: return None
        opponent_has_spirits = any(opponent.spirit_slots)
        def score_spell(spell):
            score = 0
            if spell.effects.get("aoe_damage") and opponent_has_spirits:
                score += spell.scaling * 2
            elif spell.effects.get("heal_wizard"):
                score += spell.effects.get("heal_wizard", 0)
            score -= spell.activation_cost
            return score
        return max(spells, key=score_spell)
    
    def find_weakest_spell_slot(self, spell_slots):
        weakest_score = float('inf')
        weakest_slot = None
        for slot_idx, stack in enumerate(spell_slots):
            if stack:
                spell = stack[0]
                score = spell.activation_cost
                if spell.effects.get("heal_wizard"): score += 1
                if score < weakest_score:
                    weakest_score = score
                    weakest_slot = slot_idx
        return weakest_slot
    
    def find_better_spell(self, hand, current_spell):
        for card in hand:
            if card.type == "spell":
                if (card.activation_cost < current_spell.activation_cost or 
                    (card.scaling > current_spell.scaling)):
                    return card
        return None
    
    def find_best_attack_target(self, attacker, opponent_spirits):
        best_target = None
        best_score = -1
        for slot_idx, defender in enumerate(opponent_spirits):
            if defender:
                damage = max(0, attacker.power - defender.defense)
                can_kill = damage >= defender.current_hp
                score = 0
                if can_kill: score += 10
                score += damage
                score -= defender.power
                if score > best_score:
                    best_score = score
                    best_target = (slot_idx, can_kill)
        return best_target
    
    def execute_ai_turn(self, game):
        """Execute the AI's turn by making moves until phase advances"""
        max_actions = 10
        action_count = 0
        
        # The game state is passed from bot.py, so we just check the current player
        while (game.current_player_id == self.bot_id and 
               not game.game_over and
               action_count < max_actions):
            
            if game.current_phase in [Phase.ATTAINMENT, Phase.RESPITE]:
                game.next_phase()
                continue

            move = self.get_move(game)
            
            # Use self.bot_id for all actions
            if move["type"] == "advance_phase":
                game.next_phase()
                if game.current_phase == Phase.RESPITE:
                    game.next_phase()
                    break
            
            elif move["type"] == "summon_spirit":
                success, message = game.summon_spirit(self.bot_id, move["spirit_name"], move["slot_index"])
                game.next_phase()
                continue # <-- *** FIX: Was 'break', now 'continue' ***
            elif move["type"] == "prepare_spell":
                success, message = game.prepare_spell(self.bot_id, move["spell_name"], move["slot_index"])
                game.next_phase()
                continue # <-- *** FIX: Was 'break', now 'continue' ***
            elif move["type"] == "replace_spell":
                success, message = game.replace_spell(self.bot_id, move["new_spell_name"], move["slot_index"])
                game.next_phase()
                continue # <-- Was 'break', now 'continue'
            
            elif move["type"] == "activate_spell":
                success, message = game.activate_spell(self.bot_id, move["slot_index"], move["copies_used"])
            
            elif move["type"] == "attack":
                if move["target_type"] == "wizard":
                    success, message = game.attack_with_spirit(self.bot_id, move["spirit_slot"], "wizard")
                else:
                    success, message = game.attack_with_spirit(self.bot_id, move["spirit_slot"], "spirit", move["target_index"])
            
            action_count += 1
            if game.game_over:
                break
        
        if game.current_player_id == self.bot_id and not game.game_over:
            if game.current_phase != Phase.ATTAINMENT:
                game.current_phase = Phase.RESPITE
                game.next_phase()