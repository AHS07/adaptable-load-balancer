import sys
import os
import time
import threading
import statistics
import random
from collections import defaultdict, deque

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from load_balancer.server_pool import ServerPool
from load_balancer.strategies import (
    RoundRobinStrategy,
    LeastConnectionsStrategy,
    ResponseTimeBasedStrategy,
    ALPHA1Strategy,
    BETA1Strategy
)
from workload_generator import WorkloadGenerator
from mock_server import MockServer

class RealisticSimulationSuite:
    def __init__(self):
        # Configuration matches SimulationRunner but focused on scenarios
        self.base_num_requests = 5000  # Per scenario
        self.concurrent_clients = 20
        self.results = {}

    def setup_environment(self, scenario_name):
        """Setup servers and pool based on scenario requirements"""
        print(f"\n[{scenario_name}] Setting up environment...")
        
        pool = ServerPool()
        servers = []
        
        if scenario_name == "Heterogeneous":
            # Scenario 1: Heterogeneous Servers
            # Server A: 1x, B: 0.7x, C: 1.3x, D: Random Spikes
            configs = [
                (8001, 1.0, 0.0),   # Server A: 1x Speed
                (8002, 0.7, 0.0),   # Server B: 0.7x Speed (Slower)
                (8003, 1.3, 0.0),   # Server C: 1.3x Speed (Faster)
                (8004, 1.0, 0.3),   # Server D: 1x Speed + 30% Interference (Spikes)
                (8005, 1.0, 0.0)    # Normal backup
            ]
            for port, speed, interference in configs:
                srv = MockServer('127.0.0.1', port, speed_multiplier=speed, interference_level=interference)
                servers.append(srv)
                pool.add_server('127.0.0.1', port)
                
        elif scenario_name == "HeavyTailed":
            # Scenario 2: Heavy-Tailed Latency
            # All servers similiar, but workload will be heavy-tailed (configured in workload gen)
            # Servers have high interference to simulate stragglers even more
            for port in range(8001, 8006):
                srv = MockServer('127.0.0.1', port, interference_level=0.1) # Baseline interference
                servers.append(srv)
                pool.add_server('127.0.0.1', port)
                
        elif scenario_name == "BurstTraffic":
            # Scenario 3: Burst Traffic
            # Standard servers
            for port in range(8001, 8006):
                srv = MockServer('127.0.0.1', port)
                servers.append(srv)
                pool.add_server('127.0.0.1', port)
                
        elif scenario_name == "PartialFailures":
            # Scenario 4: Partial Failures
            # Servers will experience injected faults during run
            for port in range(8001, 8006):
                srv = MockServer('127.0.0.1', port)
                servers.append(srv)
                pool.add_server('127.0.0.1', port)
                
        elif scenario_name == "CacheLocality":
            # Scenario 5: Cache Locality
            # Small caches, high cache miss penalty
            for port in range(8001, 8006):
                # Small cache size to force eviction if not efficient
                srv = MockServer('127.0.0.1', port, cache_size=20) 
                servers.append(srv)
                pool.add_server('127.0.0.1', port)
        
        return pool, servers

    def run_scenario(self, scenario_name, strategies_to_test):
        print(f"\n{'='*20} Running Scenario: {scenario_name} {'='*20}")
        
        scenario_results = []
        
        for strat_name, strat_cls in strategies_to_test:
            # 1. Setup
            pool, servers = self.setup_environment(scenario_name)
            server_map = {f"{s.host}:{s.port}": s for s in servers}
            
            # 2. Configure Workload
            if scenario_name == "HeavyTailed":
                # Heavy tail workload
                wg = WorkloadGenerator(zipf_alpha=1.2) # Default
            elif scenario_name == "CacheLocality":
                # High locality workload
                 wg = WorkloadGenerator(zipf_alpha=2.5) # Very skewed
            else:
                wg = WorkloadGenerator(zipf_alpha=1.2)
                
            print(f"-- Testing Strategy: {strat_name}")
            strategy = strat_cls()
            
            # 3. Execution Loop
            stats = {'latencies': [], 'hits': 0, 'misses': 0, 'timeouts': 0, 'drops': 0, 'errors': 0}
            lock = threading.Lock()
            
            # Dynamic control flags
            stop_event = threading.Event()
            
            def fault_injector():
                """Injects faults for Partial Failures scenario"""
                if scenario_name != "PartialFailures": return
                
                # Wait a bit
                time.sleep(2)
                print("    [Injecting] Server 8001 slows down (30%)...")
                if "127.0.0.1:8001" in server_map:
                    server_map["127.0.0.1:8001"].temporary_slowdown_factor = 1.3
                
                time.sleep(3)
                print("    [Injecting] Server 8002 drops 5% packets...")
                if "127.0.0.1:8002" in server_map:
                    server_map["127.0.0.1:8002"].set_packet_drop_rate(0.05)
                
                time.sleep(3)
                print("    [Injecting] Recovery...")
                if "127.0.0.1:8001" in server_map: server_map["127.0.0.1:8001"].temporary_slowdown_factor = 1.0
                if "127.0.0.1:8002" in server_map: server_map["127.0.0.1:8002"].set_packet_drop_rate(0.0)

            def client_worker(client_id):
                reqs_done = 0
                target_per_client = self.base_num_requests // self.concurrent_clients
                
                while reqs_done < target_per_client and not stop_event.is_set():
                    # Burst Logic
                    if scenario_name == "BurstTraffic":
                        # Simulate burst waves
                        # Every 50 requests, sleep a bit, except during burst
                        if reqs_done % 100 < 20: # Burst!
                            time.sleep(0.001) 
                        else:
                            time.sleep(0.01) # Normal spacing
                    else:
                        time.sleep(random.uniform(0.005, 0.015))
                    
                    key, size = wg.generate_request()
                    
                    # Selection
                    healthy = pool.get_healthy_servers()
                    if not healthy:
                        with lock: stats['errors'] += 1
                        continue
                        
                    if hasattr(strategy, 'select_server_with_key'):
                        selected = strategy.select_server_with_key(healthy, key)
                    else:
                        selected = strategy.select_server(healthy)
                    
                    if not selected: continue
                    
                    # Process
                    s_key = f"{selected['host']}:{selected['port']}"
                    srv = server_map.get(s_key)
                    
                    pool.increment_connections(selected['host'], selected['port'])
                    success, lat, is_hit, reason = srv.process_request(key, size)
                    pool.decrement_connections(selected['host'], selected['port'])
                    
                    # Record
                    with lock:
                        if success:
                            stats['latencies'].append(lat)
                            if (is_hit): stats['hits'] += 1
                            else: stats['misses'] += 1
                        else:
                            if reason == "timeout": stats['timeouts'] += 1
                            elif reason == "packet_drop": stats['drops'] += 1
                            else: stats['errors'] += 1
                    
                    # Feedback
                    if hasattr(strategy, 'record_response_time'):
                         strategy.record_response_time(selected['host'], selected['port'], lat / 1000.0)
                    if success:
                         pool.mark_healthy(selected['host'], selected['port'])
                         pool.record_response_time(selected['host'], selected['port'], lat / 1000.0)

                    reqs_done += 1
            
            # Start threads
            threads = []
            injector = None
            if scenario_name == "PartialFailures":
                injector = threading.Thread(target=fault_injector)
                injector.start()
            
            start_time = time.time()
            for i in range(self.concurrent_clients):
                t = threading.Thread(target=client_worker, args=(i,))
                t.start()
                threads.append(t)
            
            for t in threads:
                t.join()
            
            if injector: injector.join()
            
            duration = time.time() - start_time
            
            # Metrics
            latencies = sorted(stats['latencies'])
            p95 = latencies[int(len(latencies)*0.95)] if latencies else 0
            p99 = latencies[int(len(latencies)*0.99)] if latencies else 0
            avg = statistics.mean(latencies) if latencies else 0
            
            total_reqs = stats['hits'] + stats['misses']
            hit_rate = (stats['hits'] / total_reqs * 100) if total_reqs > 0 else 0
            
            result = {
                'Strategy': strat_name,
                'Avg Latency': avg,
                'P95': p95,
                'P99': p99,
                'Hit Rate': hit_rate,
                'Timeouts': stats['timeouts'],
                'Drops': stats['drops']
            }
            scenario_results.append(result)
            print(f"   -> Result: P99={p99:.2f}ms, HitRate={hit_rate:.1f}%")

        return scenario_results

    def print_summary(self, scenario_name, results):
        print(f"\n--- Summary for {scenario_name} ---")
        print(f"{'Strategy':<20} {'P99 (ms)':<10} {'Hit Rate':<10} {'Timeouts':<10} {'Drops':<10}")
        for r in results:
            print(f"{r['Strategy']:<20} {r['P99']:<10.2f} {r['Hit Rate']:<10.1f} {r['Timeouts']:<10} {r['Drops']:<10}")

if __name__ == "__main__":
    suite = RealisticSimulationSuite()
    
    strategies = [
        ("Round Robin", RoundRobinStrategy),
        # ("Least Conn", LeastConnectionsStrategy),
        ("ALPHA1 (Tail-Aware)", ALPHA1Strategy),
        ("BETA1 (Cache-Aware)", BETA1Strategy)
    ]
    
    # Run all scenarios
    scenarios = [
        "Heterogeneous",
        "HeavyTailed",
        "BurstTraffic",
        "PartialFailures",
        "CacheLocality"
    ]
    
    for sc in scenarios:
        results = suite.run_scenario(sc, strategies)
        suite.print_summary(sc, results)
