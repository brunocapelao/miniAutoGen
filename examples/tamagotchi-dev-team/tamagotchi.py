import sys
from dataclasses import dataclass
from typing import Optional, Tuple

@dataclass(frozen=True)
class GameConfig:
    MAX_STAT: int = 100
    MIN_STAT: int = 0
    START_STAT: int = 50
    DECAY_RATE: int = 5
    FEED_BOOST: int = 20
    PLAY_BOOST: int = 20
    SLEEP_BOOST: int = 30
    SLEEP_HUNGER_COST: int = 10
    PLAY_ENERGY_COST: int = 10

class TamagotchiEngine:
    def __init__(self, name: str, config: GameConfig = GameConfig()):
        self.name = name
        self.config = config
        self.hunger = config.START_STAT
        self.happiness = config.START_STAT
        self.energy = config.START_STAT
        self.is_alive = True
        self.turns = 0

    def _clamp(self, value: int) -> int:
        return max(self.config.MIN_STAT, min(self.config.MAX_STAT, value))

    def _check_alive(self) -> bool:
        if self.hunger <= self.config.MIN_STAT or \
           self.happiness <= self.config.MIN_STAT or \
           self.energy <= self.config.MIN_STAT:
            self.is_alive = False
            return False
        return True

    def process_turn(self) -> None:
        self.turns += 1
        self.hunger = self._clamp(self.hunger - self.config.DECAY_RATE)
        self.happiness = self._clamp(self.happiness - self.config.DECAY_RATE)
        self.energy = self._clamp(self.energy - self.config.DECAY_RATE)
        self._check_alive()

    def feed(self) -> None:
        self.hunger = self._clamp(self.hunger + self.config.FEED_BOOST)
        self.process_turn()

    def play(self) -> None:
        self.happiness = self._clamp(self.happiness + self.config.PLAY_BOOST)
        self.energy = self._clamp(self.energy - self.config.PLAY_ENERGY_COST)
        self.process_turn()

    def sleep(self) -> None:
        self.energy = self._clamp(self.energy + self.config.SLEEP_BOOST)
        self.hunger = self._clamp(self.hunger - self.config.SLEEP_HUNGER_COST)
        self.process_turn()

class TamagotchiRenderer:
    # ANSI color codes
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"

    ART_DEAD = r"""
     _______
    /       \
   /  R.I.P  \
   |  X   X  |
   |    ^    |
   |  _____  |
   \_________/
    """
    
    ART_TIRED = r"""
     _______
    /       \
   /  -   -  \
   |    ^    |
   |  ~~~~~  |
   \_________/
   ( I'm tired... )
    """
    
    ART_HUNGRY = r"""
     _______
    /       \
   /  o   o  \
   |    ^    |
   |    O    |
   \_________/
   ( So hungry! )
    """
    
    ART_SAD = r"""
     _______
    /       \
   /  ;   ;  \
   |    ^    |
   |    -    |
   \_________/
   ( I'm sad... )
    """
    
    ART_HAPPY = r"""
     _______
    /       \
   /  ^   ^  \
   |    v    |
   |  \___/  |
   \_________/
   ( Feeling great! )
    """
    
    ART_OKAY = r"""
     _______
    /       \
   /  o   o  \
   |    ^    |
   |  -----  |
   \_________/
   ( Doing okay. )
    """

    @classmethod
    def get_art(cls, engine: TamagotchiEngine) -> Tuple[str, str]:
        if not engine.is_alive:
            return cls.ART_DEAD, cls.RED
        
        # Priority mapping for mood
        if engine.energy < 20:
            return cls.ART_TIRED, cls.YELLOW
        if engine.hunger < 20:
            return cls.ART_HUNGRY, cls.YELLOW
        if engine.happiness < 20:
            return cls.ART_SAD, cls.YELLOW
        
        avg = (engine.hunger + engine.happiness + engine.energy) / 3
        if avg > 70:
            return cls.ART_HAPPY, cls.CYAN
        
        return cls.ART_OKAY, cls.CYAN

    @classmethod
    def render_bar(cls, value: int, color: str) -> str:
        filled = int(value / 5)
        return f"{color}[{'#' * filled}{' ' * (20 - filled)}]{cls.RESET} {value}/100"

    @classmethod
    def display_status(cls, engine: TamagotchiEngine) -> None:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()
        print(f"\n{cls.BOLD}{cls.CYAN}{'=' * 45}{cls.RESET}")
        print(f" {cls.BOLD}{engine.name}'s Status (Turn: {engine.turns}){cls.RESET}")
        print(f"{cls.BOLD}{cls.CYAN}{'=' * 45}{cls.RESET}")
        
        print(f" {cls.BOLD}Hunger:   {cls.RESET} {cls.render_bar(engine.hunger, cls.RED)}")
        print(f" {cls.BOLD}Happiness:{cls.RESET} {cls.render_bar(engine.happiness, cls.YELLOW)}")
        print(f" {cls.BOLD}Energy:   {cls.RESET} {cls.render_bar(engine.energy, cls.GREEN)}")
        
        art, color = cls.get_art(engine)
        print(f"{color}{art}{cls.RESET}")
        print(f"{cls.BOLD}{cls.CYAN}{'=' * 45}{cls.RESET}")

class TamagotchiApp:
    def __init__(self, name: Optional[str] = None):
        self.engine = TamagotchiEngine(name or "Tama")
        self.renderer = TamagotchiRenderer()

    def run(self) -> None:
        print(f"{self.renderer.BOLD}{self.renderer.CYAN}Welcome to Terminal Tamagotchi!{self.renderer.RESET}")
        if self.engine.name == "Tama":
            self.engine.name = input("What would you like to name your pet? ").strip() or "Tama"
        
        while self.engine.is_alive:
            self.renderer.display_status(self.engine)
            print(f"\n{self.renderer.BOLD}Actions:{self.renderer.RESET}")
            print(f"1. {self.renderer.RED}Feed{self.renderer.RESET}  (+20 Hunger, all stats -5 Decay)")
            print(f"2. {self.renderer.YELLOW}Play{self.renderer.RESET}  (+20 Happiness, -10 Energy, all stats -5 Decay)")
            print(f"3. {self.renderer.GREEN}Sleep{self.renderer.RESET} (+30 Energy, -10 Hunger, all stats -5 Decay)")
            print(f"4. {self.renderer.CYAN}Quit{self.renderer.RESET}")
            
            try:
                choice = input(f"\n{self.renderer.BOLD}Choose an action (1-4): {self.renderer.RESET}").strip()
                if choice == '1':
                    print(f"\n>> You fed {self.engine.name}. Yummy!")
                    self.engine.feed()
                elif choice == '2':
                    print(f"\n>> You played with {self.engine.name}! Fun!")
                    self.engine.play()
                elif choice == '3':
                    print(f"\n>> {self.engine.name} is sleeping... Zzzzz.")
                    self.engine.sleep()
                elif choice == '4':
                    print("Thanks for playing!")
                    return
                else:
                    print("Invalid input. Please choose 1-4.")
                    input("Press Enter to continue...")
            except KeyboardInterrupt:
                print("\nThanks for playing!")
                return

        self.renderer.display_status(self.engine)
        self.display_game_over()

    def display_game_over(self) -> None:
        r = self.renderer
        print(f"\n{r.BOLD}{r.RED}GAME OVER. {self.engine.name} has passed away.{r.RESET}")
        
        reason = "Starvation" if self.engine.hunger <= 0 else \
                 "Sadness" if self.engine.happiness <= 0 else \
                 "Exhaustion"
        
        print(f"{r.BOLD}Reason: {reason}.{r.RESET}")
        print(f"{r.BOLD}Total turns survived: {self.engine.turns}{r.RESET}")

# For backward compatibility (legacy Jerry-interface)
class Tamagotchi(TamagotchiEngine):
    def __init__(self, name: str):
        super().__init__(name)
    
    def clamp(self, value: int) -> int:
        return self._clamp(value)
    
    def check_alive(self) -> bool:
        return self._check_alive()
    
    def display_status(self) -> None:
        TamagotchiRenderer.display_status(self)

def main() -> None:
    app = TamagotchiApp()
    app.run()

if __name__ == "__main__":
    main()
