import json
import os
from game_engine import Card # <-- Import Card here

class CardManager:
    def __init__(self):
        self.cards = {}
        self.load_cards()
    
    def load_cards(self, file_path="config/cards.json"):
        # Create default cards if file doesn't exist
        default_cards = {
            "spirits": {
                "stone_golem": {
                    "name": "Stone Golem",
                    "activation_cost": 1,
                    "power": 2,
                    "defense": 3,
                    "hp": 8,
                    "effect": "Defense cannot be reduced"
                },
                "frost_wyrm": {
                    "name": "Frost Wyrm", 
                    "activation_cost": 2,
                    "power": 4,
                    "defense": 1,
                    "hp": 12,
                    "effect": "Attack reduces target defense by 1"
                },
                "inferno_dragon": {
                    "name": "Inferno Dragon",
                    "activation_cost": 3,
                    "power": 6,
                    "defense": 0, 
                    "hp": 16,
                    "effect": "Can attack wizard directly"
                }
            },
            "spells": {
                "firestorm": {
                    "name": "Firestorm", 
                    "activation_cost": 3,
                    "effect": "Deal 3 damage to all enemy spirits",
                    "scaling": 3
                },
                "healing_wave": {
                    "name": "Healing Wave",
                    "activation_cost": 2,
                    "effect": "Heal 4 HP to spirit or 1 HP to wizard",
                    "scaling": 4
                }
            }
        }
        
        # Try to load from file, or use defaults
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    self.cards = json.load(f)
            else:
                self.cards = default_cards
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                # Save defaults
                with open(file_path, 'w') as f:
                    json.dump(default_cards, f, indent=2)
        except Exception as e:
            print(f"Error loading cards: {e}")
            self.cards = default_cards
    
    def get_card(self, card_id):
        # Search for card in spirits and spells
        for category in ["spirits", "spells"]:
            if card_id in self.cards.get(category, {}):
                return self.cards[category][card_id]
        return None
    
    def create_card_instance(self, card_id):
        """
        Finds a card by its ID in the library (spirits or spells)
        and returns a new Card object instance.
        """
        card_data = None
        card_type = None

        # Check in spirits
        if card_id in self.cards.get("spirits", {}):
            card_data = self.cards["spirits"][card_id]
            card_type = "spirit"
        # Check in spells
        elif card_id in self.cards.get("spells", {}):
            card_data = self.cards["spells"][card_id]
            card_type = "spell"

        if not card_data:
            print(f"Error: Card ID '{card_id}' not found in card library.")
            return None # Card ID not found in library
        
        # Create instance based on type
        if card_type == "spirit":
            return Card(
                name=card_data["name"],
                card_type=card_type,
                activation_cost=card_data.get("activation_cost", 0),
                power=card_data.get("power", 0),
                defense=card_data.get("defense", 0),
                hp=card_data.get("hp", 0),
                effect=card_data.get("effect", "")
            )
        else:  # spell
            return Card(
                name=card_data["name"],
                card_type=card_type,
                activation_cost=card_data.get("activation_cost", 0),
                effect=card_data.get("effect", ""),
                scaling=card_data.get("scaling", 0),
                element=card_data.get("element", "")
            )
    
    def save_cards(self, file_path="config/cards.json"):
        try:
            with open(file_path, 'w') as f:
                json.dump(self.cards, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving cards: {e}")
            return False
    
    def update_card(self, card_id, new_data, category):
        if category not in self.cards:
            self.cards[category] = {}
        
        self.cards[category][card_id] = new_data
        return self.save_cards()
    
    def get_all_card_ids(self):
        card_ids = []
        for category in ["spirits", "spells"]:
            card_ids.extend(self.cards.get(category, {}).keys())
        return card_ids