import json
import os

# We need to dynamically import the Card class from one of the engines
# It's defined in both, so we can just pick one.
# This is a bit of a workaround for sharing the class definition.
try:
    from game_engine import Card
except ImportError:
    print("Could not import Card from game_engine, trying discord_engine...")
    try:
        from discord_engine import Card
    except ImportError:
        print("CRITICAL: Could not import Card class from game_engine or discord_engine.")
        # Define a fallback class so the file can at least be imported
        class Card:
             def __init__(self, name, card_type, activation_cost, power=0, defense=0, hp=0, effect="", scaling=0, element="", effects=None):
                self.name = name
                self.type = card_type
                self.activation_cost = activation_cost
                self.power = power
                self.defense = defense
                self.max_hp = hp
                self.current_hp = hp
                self.effect = effect
                self.scaling = scaling
                self.element = element
                self.effects = effects if effects is not None else {}
                print("Using fallback Card class")


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
                    "effect": "Defense cannot be reduced",
                    "effects": {"prevent_defense_reduction": True}
                },
                "frost_wyrm": {
                    "name": "Frost Wyrm", 
                    "activation_cost": 2,
                    "power": 4,
                    "defense": 1,
                    "hp": 12,
                    "effect": "Attack reduces target defense by 1",
                    "effects": {"reduce_defense": 1}
                },
                "inferno_dragon": {
                    "name": "Inferno Dragon",
                    "activation_cost": 3,
                    "power": 6,
                    "defense": 0, 
                    "hp": 16,
                    "effect": "Can attack wizard directly",
                    "effects": {"direct_attack": True}
                }
            },
            "spells": {
                "firestorm": {
                    "name": "Firestorm", 
                    "activation_cost": 3,
                    "effect": "Deal 3 damage to all enemy spirits",
                    "scaling": 3,
                    "effects": {"aoe_damage": True, "target": "enemy_spirits"}
                },
                "healing_wave": {
                    "name": "Healing Wave",
                    "activation_cost": 2,
                    "effect": "Heal 4 HP to spirit or 1 HP to wizard",
                    "scaling": 0,
                    "effects": {"heal_wizard": 1, "heal_spirit": 4}
                }
            }
        }
        
        # Try to load from file, or use defaults
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    self.cards = json.load(f)
            else:
                print(f"Warning: {file_path} not found. Creating with default cards.")
                self.cards = default_cards
                # Create directory if it doesn't exist
                config_dir = os.path.dirname(file_path)
                if config_dir and not os.path.exists(config_dir):
                    os.makedirs(config_dir, exist_ok=True)
                # Save defaults
                with open(file_path, 'w') as f:
                    json.dump(default_cards, f, indent=2)
        except Exception as e:
            print(f"Error loading cards: {e}")
            self.cards = default_cards
    
    def get_card(self, card_id):
        """Gets the raw data for a card from the library."""
        for category in ["spirits", "spells"]:
            if card_id in self.cards.get(category, {}):
                return self.cards[category][card_id]
        return None

    def get_card_type(self, card_id) -> str | None:
        """Returns the category ('spirits' or 'spells') of a card ID."""
        if card_id in self.cards.get("spirits", {}):
            return "spirits"
        if card_id in self.cards.get("spells", {}):
            return "spells"
        return None
    
    def create_card_instance(self, card_id):
        """
        Finds a card by its ID in the library (spirits or spells)
        and returns a new Card object instance.
        """
        card_data = self.get_card(card_id)
        card_type = self.get_card_type(card_id)

        if not card_data or not card_type:
            # print(f"Error: Card ID '{card_id}' not found in card library.")
            return None # Card ID not found in library
        
        # Create instance based on type
        if card_type == "spirits":
            return Card(
                name=card_data["name"],
                card_type="spirit", # Use singular 'spirit'
                activation_cost=card_data.get("activation_cost", 0),
                power=card_data.get("power", 0),
                defense=card_data.get("defense", 0),
                hp=card_data.get("hp", 0),
                effect=card_data.get("effect", ""),
                effects=card_data.get("effects", {})
            )
        else:  # spells
            return Card(
                name=card_data["name"],
                card_type="spell", # Use singular 'spell'
                activation_cost=card_data.get("activation_cost", 0),
                effect=card_data.get("effect", ""),
                scaling=card_data.get("scaling", 0),
                element=card_data.get("element", ""),
                effects=card_data.get("effects", {})
            )
    
    def save_cards(self, file_path="config/cards.json"):
        try:
            with open(file_path, 'w') as f:
                json.dump(self.cards, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving cards: {e}")
            return False
    
    def update_card(self, card_id, new_data, category: str):
        """
        Adds or updates a card in the loaded library and saves to cards.json.
        Category should be 'spirits' or 'spells'.
        """
        if category not in self.cards:
            self.cards[category] = {}
        
        self.cards[category][card_id] = new_data
        
        # Reload the cards in the manager after saving
        success = self.save_cards()
        self.load_cards() # Reload to ensure consistency
        return success
    
    def get_all_card_ids(self) -> list[str]:
        """Gets a list of all card IDs from both spirits and spells."""
        card_ids = []
        for category in ["spirits", "spells"]:
            card_ids.extend(self.cards.get(category, {}).keys())
        return card_ids