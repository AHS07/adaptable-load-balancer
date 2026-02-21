import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from load_balancer.strategies import BETA1Strategy

# Test 1: Direct instantiation
strategy1 = BETA1Strategy(capacity_factor=2.5)
print(f"Direct: capacity_factor = {strategy1.capacity_factor}")

# Test 2: Lambda
strategy_cls = lambda: BETA1Strategy(capacity_factor=2.5)
strategy2 = strategy_cls()
print(f"Lambda: capacity_factor = {strategy2.capacity_factor}")

# Test 3: Class reference
strategy_cls2 = BETA1Strategy
strategy3 = strategy_cls2()
print(f"Class: capacity_factor = {strategy3.capacity_factor}")
