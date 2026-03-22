# Refactor Plan: Tamagotchi God-Mode

## Objective
Refactor the "Jerry-slop" Tamagotchi implementation into a Senior Principal Engineering level architecture.

## Strategy
1. **Decouple Logic from UI**: Create a pure `TamagotchiEngine` class with zero print statements.
2. **Abstract the View**: Create a `TamagotchiRenderer` for ASCII art and status display.
3. **Externalize Constants**: Move all "magic numbers" (decay, boosts, max stats) to a `GameConfig` dataclass.
4. **Enforce Types**: Add full type hinting for better tooling support.
5. **Optimize ASCII Logic**: Replace the nested if-elif chain with a priority-based mapping or specialized lookup.
6. **Improve Testability**: Ensure the main loop and engine can be tested in isolation.

## Kill List
- `Tamagotchi.display_status` (coupled)
- `Tamagotchi.get_status_art` (nested mess)
- Hardcoded ANSI escape codes in methods
- Redundant comments

## Verification
- 1:1 functional parity with existing tests.
- New integration tests for the decoupled architecture.
- Full type checking with `mypy`.
