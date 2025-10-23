import importlib
import importlib.util
import sys
import os
from pathlib import Path
from tournament_core import (
    IMatchmakingStrategy,
    IPointsCalculator,
    MatchmakingStrategyRegistry,
    PointsCalculatorRegistry,
    ITournamentRepository,
)


class PluginLoader:
    """
    Loads plugins dynamically from modules or files.
    Supports hot-loading of custom strategies and calculators.
    """

    def __init__(
        self,
        strategy_registry: MatchmakingStrategyRegistry,
        calculator_registry: PointsCalculatorRegistry,
        repository: ITournamentRepository,
    ):
        self.strategy_registry = strategy_registry
        self.calculator_registry = calculator_registry
        self.repository = repository
        self.loaded_modules = {}

    def load_strategy_from_module(self, module_name: str, class_name: str) -> None:
        """
        Load a strategy class from a module.

        Example:
            loader.load_strategy_from_module('my_strategies', 'MyCustomStrategy')
        """
        try:
            module = importlib.import_module(module_name)
            strategy_class = getattr(module, class_name)

            if not issubclass(strategy_class, IMatchmakingStrategy):
                raise TypeError(f"{class_name} must implement IMatchmakingStrategy")

            # Instantiate and register
            strategy = strategy_class(self.repository)
            self.strategy_registry.register(strategy)

            print(
                f"✓ Loaded strategy: {strategy.get_strategy_name()} from {module_name}.{class_name}"
            )

        except Exception as e:
            print(f"✗ Failed to load strategy from {module_name}.{class_name}: {e}")

    def load_calculator_from_module(self, module_name: str, class_name: str) -> None:
        """
        Load a calculator class from a module.

        Example:
            loader.load_calculator_from_module('my_calculators', 'MyCustomCalculator')
        """
        try:
            module = importlib.import_module(module_name)
            calculator_class = getattr(module, class_name)

            if not issubclass(calculator_class, IPointsCalculator):
                raise TypeError(f"{class_name} must implement IPointsCalculator")

            # Instantiate and register
            calculator = calculator_class()
            self.calculator_registry.register(calculator)

            print(
                f"✓ Loaded calculator: {calculator.get_calculator_name()} from {module_name}.{class_name}"
            )

        except Exception as e:
            print(f"✗ Failed to load calculator from {module_name}.{class_name}: {e}")

    def load_strategy_from_file(self, file_path: str, class_name: str) -> None:
        """
        Load a strategy class from a Python file.

        Example:
            loader.load_strategy_from_file('./plugins/custom_strategy.py', 'CustomStrategy')
        """
        try:
            # Load module from file
            module_name = Path(file_path).stem
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Get and register strategy
            strategy_class = getattr(module, class_name)

            if not issubclass(strategy_class, IMatchmakingStrategy):
                raise TypeError(f"{class_name} must implement IMatchmakingStrategy")

            strategy = strategy_class(self.repository)
            self.strategy_registry.register(strategy)

            self.loaded_modules[module_name] = module

            print(f"✓ Loaded strategy: {strategy.get_strategy_name()} from {file_path}")

        except Exception as e:
            print(f"✗ Failed to load strategy from {file_path}: {e}")

    def load_calculator_from_file(self, file_path: str, class_name: str) -> None:
        """
        Load a calculator class from a Python file.

        Example:
            loader.load_calculator_from_file('./plugins/custom_calc.py', 'CustomCalc')
        """
        try:
            # Load module from file
            module_name = Path(file_path).stem
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Get and register calculator
            calculator_class = getattr(module, class_name)

            if not issubclass(calculator_class, IPointsCalculator):
                raise TypeError(f"{class_name} must implement IPointsCalculator")

            calculator = calculator_class()
            self.calculator_registry.register(calculator)

            self.loaded_modules[module_name] = module

            print(
                f"✓ Loaded calculator: {calculator.get_calculator_name()} from {file_path}"
            )

        except Exception as e:
            print(f"✗ Failed to load calculator from {file_path}: {e}")

    def discover_and_load_plugins(self, plugins_dir: str = "./plugins") -> None:
        """
        Discover and load all plugins from a directory.
        Looks for classes that implement the plugin interfaces.
        """
        if not os.path.exists(plugins_dir):
            print(f"Plugins directory not found: {plugins_dir}")
            return

        print(f"\nDiscovering plugins in: {plugins_dir}")

        for filename in os.listdir(plugins_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                file_path = os.path.join(plugins_dir, filename)
                self._auto_load_from_file(file_path)

    def _auto_load_from_file(self, file_path: str) -> None:
        """Automatically detect and load plugins from a file."""
        try:
            module_name = Path(file_path).stem
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Find all classes that implement our interfaces
            for attr_name in dir(module):
                attr = getattr(module, attr_name)

                # Check if it's a class
                if not isinstance(attr, type):
                    continue

                # Check if it implements our interfaces
                try:
                    if (
                        issubclass(attr, IMatchmakingStrategy)
                        and attr != IMatchmakingStrategy
                    ):
                        strategy = attr(self.repository)
                        self.strategy_registry.register(strategy)
                        print(f"  ✓ Loaded strategy: {strategy.get_strategy_name()}")

                    elif (
                        issubclass(attr, IPointsCalculator)
                        and attr != IPointsCalculator
                    ):
                        calculator = attr()
                        self.calculator_registry.register(calculator)
                        print(
                            f"  ✓ Loaded calculator: {calculator.get_calculator_name()}"
                        )

                except TypeError:
                    # Not a valid subclass
                    pass

            self.loaded_modules[module_name] = module

        except Exception as e:
            print(f"  ✗ Failed to load from {file_path}: {e}")

    def reload_plugin(self, module_name: str) -> None:
        """
        Reload a plugin module.
        Useful for development when you modify a plugin.
        """
        if module_name not in self.loaded_modules:
            print(f"Module {module_name} not loaded")
            return

        try:
            module = self.loaded_modules[module_name]
            importlib.reload(module)
            print(f"✓ Reloaded module: {module_name}")
        except Exception as e:
            print(f"✗ Failed to reload {module_name}: {e}")


# Example custom plugin that users can create:
"""
# File: plugins/my_custom_strategy.py

from tournament_core import IMatchmakingStrategy, Match, RoundConfig, generate_id, now_iso
from typing import list, Dict, Any

class RandomMatchmakingStrategy(IMatchmakingStrategy):
    '''Randomly pairs players together.'''
    
    def __init__(self, repository):
        self.repository = repository
    
    def get_strategy_name(self) -> str:
        return "random"
    
    def supports_players_per_match(self, n: int) -> bool:
        return True  # Supports any number
    
    def create_matches(self, tournament_id, round_id, available_players, config):
        import random
        players = available_players.copy()
        random.shuffle(players)
        
        matches = []
        n = config.players_per_match
        
        while len(players) >= n:
            match_players = [players.pop() for _ in range(n)]
            match = Match(
                id=generate_id(),
                round_id=round_id,
                tournament_id=tournament_id,
                player_ids=match_players,
                scheduled_at=now_iso(),
                players_per_match=n
            )
            matches.append(match)
            self.repository.save_match(match)
        
        return {
            "matches": matches,
            "waiting_players": players,
            "metadata": {"shuffled": True}
        }
"""
