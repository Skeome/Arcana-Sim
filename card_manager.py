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
             def __init__(self, **kwargs):
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
                print(f"Warning: {file_path} not found. Creating with default cards.")
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
            print(f"Error: Card ID '{card_id}' not found in card library.")
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
                effect=card_data.get("effect", "")
            )
        else:  # spells
            return Card(
                name=card_data["name"],
                card_type="spell", # Use singular 'spell'
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