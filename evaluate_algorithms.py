#!/usr/bin/env python3
"""
Algorithm Evaluation Script
Stress tests each load balancing algorithm and compares performance metrics.
"""

import time
import threading
import socket
import statistics
from collections import defaultdict
from datetime import datetime
import sys

from load_balancer.server_pool import ServerPool
from load_balancer.strategies import (
    RoundRobinStrategy, 
    LeastConnectionsStrategy,
    HealthScoreBasedStrategy, 
    HistoricalFailureWeightedRoundRobin,
    ResponseTimeBasedStrategy, 
    ALPHA1Strategy, 
    BETA1Strategy
)


class AlgorithmEvaluator:
    """Evaluates load balancing algorithms under stress test conditions"""
    
    def __init__(self, num_servers=5, num_requests=1000, concurrent_clients=50):
        self.num_servers = num_servers
        self.num_requests = num_requests
        self.concurrent_clients = concurrent_clients
        
        # Metrics to collect
        self.metrics = {}
        
    def create_mock_servers(self, pool):
        """Create mock backend servers with varying characteristics"""
        servers = [
            {'host': '127.0.0.1', 'port': 8001, 'latency': 0.01, 'failure_rate': 0.0},
            {'host': '127.0.0.1', 'port': 8002, 'latency': 0.02, 'failure_rate': 0.05},
            {'host': '127.0.0.1', 'port': 8003, 'latency': 0.015, 'failure_rate': 0.0},
            {'host': '127.0.0.1', 'port': 8004, 'latency': 0.03, 'failure_rate': 0.1},
            {'host': '127.0.0.1', 'port': 8005, 'latency': 0.01, 'failure_rate': 0.02},
        ]
        
        for srv in servers[:self.num_servers]:
            pool.add_server(srv['host'], srv['port'])
        
        return servers[:self.num_servers]
    
    def simulate_request(self, strategy, pool, server_configs, metrics_dict, request_id):
        """Simulate a single request"""
        start_time = time.time()
        
        # Get healthy servers
        healthy_servers = pool.get_healthy_servers()
        if not healthy_servers:
            metrics_dict['failed_requests'] += 1
            return
        
        # Select server using strategy
        selected = strategy.select_server(healthy_servers)
        if not selected:
            metrics_dict['failed_requests'] += 1
            return
        
        server_key = f"{selected['host']}:{selected['port']}"
        
        # Increment connections
        pool.increment_connections(selected['host'], selected['port'])
        
        # Find server config
        server_config = next(
            (s for s in server_configs if s['host'] == selected['host'] and s['port'] == selected['port']),
            None
        )
        
        # Simulate request processing
        if server_config:
            # Simulate latency
            time.sleep(server_config['latency'])
            
            # Simulate failure
            import random
            if random.random() < server_config['failure_rate']:
                pool.mark_unhealthy(selected['host'], selected['port'])
                metrics_dict['failed_requests'] += 1
                metrics_dict['server_failures'][server_key] += 1
            else:
                pool.mark_healthy(selected['host'], selected['port'])
                metrics_dict['successful_requests'] += 1
        
        # Decrement connections
        pool.decrement_connections(selected['host'], selected['port'])
        
        # Record metrics
        end_time = time.time()
        response_time = end_time - start_time
        
        metrics_dict['response_times'].append(response_time)
        metrics_dict['server_selections'][server_key] += 1
        
        # Record response time in strategy if supported
        if hasattr(strategy, 'record_response_time'):
            strategy.record_response_time(selected['host'], selected['port'], response_time)
        
        # Record in pool
        pool.record_response_time(selected['host'], selected['port'], response_time)
    
    def run_stress_test(self, strategy_name, strategy_class):
        """Run stress test for a specific strategy"""
        print(f"Testing {strategy_name}...", end=' ', flush=True)
        
        # Initialize
        pool = ServerPool()
        strategy = strategy_class()
        server_configs = self.create_mock_servers(pool)
        
        # Metrics collection
        metrics_dict = {
            'successful_requests': 0,
            'failed_requests': 0,
            'response_times': [],
            'server_selections': defaultdict(int),
            'server_failures': defaultdict(int),
        }
        
        # Run stress test
        start_time = time.time()
        threads = []
        requests_per_client = self.num_requests // self.concurrent_clients
        
        for client_id in range(self.concurrent_clients):
            for req_id in range(requests_per_client):
                thread = threading.Thread(
                    target=self.simulate_request,
                    args=(strategy, pool, server_configs, metrics_dict, req_id)
                )
                threads.append(thread)
                thread.start()
                
                # Limit concurrent threads
                if len(threads) >= self.concurrent_clients:
                    for t in threads:
                        t.join()
                    threads = []
        
        # Wait for remaining threads
        for t in threads:
            t.join()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Calculate metrics
        total_requests = metrics_dict['successful_requests'] + metrics_dict['failed_requests']
        success_rate = (metrics_dict['successful_requests'] / max(total_requests, 1)) * 100
        
        response_times = metrics_dict['response_times']
        avg_response_time = statistics.mean(response_times) if response_times else 0
        median_response_time = statistics.median(response_times) if response_times else 0
        
        # Calculate percentiles
        if response_times:
            sorted_times = sorted(response_times)
            p95 = sorted_times[int(len(sorted_times) * 0.95)]
            p99 = sorted_times[int(len(sorted_times) * 0.99)]
        else:
            p95 = p99 = 0
        
        # Calculate load distribution (standard deviation of server selections)
        selections = list(metrics_dict['server_selections'].values())
        load_balance_score = statistics.stdev(selections) if len(selections) > 1 else 0
        
        # Calculate throughput
        throughput = total_requests / total_time if total_time > 0 else 0
        
        print("Done")
        
        return {
            'strategy': strategy_name,
            'total_requests': total_requests,
            'successful_requests': metrics_dict['successful_requests'],
            'failed_requests': metrics_dict['failed_requests'],
            'success_rate': success_rate,
            'avg_response_time_ms': avg_response_time * 1000,
            'median_response_time_ms': median_response_time * 1000,
            'p95_latency_ms': p95 * 1000,
            'p99_latency_ms': p99 * 1000,
            'throughput_rps': throughput,
            'load_balance_stdev': load_balance_score,
            'total_time_sec': total_time,
            'server_selections': dict(metrics_dict['server_selections']),
            'server_failures': dict(metrics_dict['server_failures']),
        }
    
    def evaluate_all_algorithms(self):
        """Evaluate all load balancing algorithms"""
        strategies = [
            ('Round Robin', RoundRobinStrategy),
            ('Least Connections', LeastConnectionsStrategy),
            ('Health Score', HealthScoreBasedStrategy),
            ('Weighted RR', HistoricalFailureWeightedRoundRobin),
            ('Response Time', ResponseTimeBasedStrategy),
            ('ALPHA1', ALPHA1Strategy),
            ('BETA1', BETA1Strategy),
        ]
        
        results = []
        
        print(f"\n{'='*80}")
        print(f"LOAD BALANCER ALGORITHM EVALUATION")
        print(f"{'='*80}")
        print(f"Configuration:")
        print(f"  - Servers: {self.num_servers}")
        print(f"  - Total Requests: {self.num_requests}")
        print(f"  - Concurrent Clients: {self.concurrent_clients}")
        print(f"{'='*80}\n")
        
        for strategy_name, strategy_class in strategies:
            result = self.run_stress_test(strategy_name, strategy_class)
            results.append(result)
            time.sleep(0.5)  # Brief pause between tests
        
        return results
    
    def print_comparison_table(self, results):
        """Print comparison table in terminal"""
        print(f"\n{'='*120}")
        print(f"PERFORMANCE COMPARISON TABLE")
        print(f"{'='*120}\n")
        
        # Main metrics table
        print(f"{'Strategy':<20} {'Success%':<10} {'Avg(ms)':<10} {'P95(ms)':<10} {'P99(ms)':<10} {'RPS':<10} {'Balance':<10}")
        print(f"{'-'*120}")
        
        for r in results:
            print(f"{r['strategy']:<20} "
                  f"{r['success_rate']:<10.2f} "
                  f"{r['avg_response_time_ms']:<10.2f} "
                  f"{r['p95_latency_ms']:<10.2f} "
                  f"{r['p99_latency_ms']:<10.2f} "
                  f"{r['throughput_rps']:<10.2f} "
                  f"{r['load_balance_stdev']:<10.2f}")
        
        print(f"\n{'='*120}\n")
        
        # Detailed metrics table
        print(f"DETAILED METRICS")
        print(f"{'-'*120}")
        print(f"{'Strategy':<20} {'Total':<10} {'Success':<10} {'Failed':<10} {'Median(ms)':<12} {'Time(s)':<10}")
        print(f"{'-'*120}")
        
        for r in results:
            print(f"{r['strategy']:<20} "
                  f"{r['total_requests']:<10} "
                  f"{r['successful_requests']:<10} "
                  f"{r['failed_requests']:<10} "
                  f"{r['median_response_time_ms']:<12.2f} "
                  f"{r['total_time_sec']:<10.2f}")
        
        print(f"\n{'='*120}\n")
        
        # Rankings
        print(f"RANKINGS")
        print(f"{'-'*120}")
        
        # Best success rate
        best_success = max(results, key=lambda x: x['success_rate'])
        print(f"🏆 Best Success Rate:     {best_success['strategy']} ({best_success['success_rate']:.2f}%)")
        
        # Lowest average latency
        best_avg_latency = min(results, key=lambda x: x['avg_response_time_ms'])
        print(f"⚡ Lowest Avg Latency:    {best_avg_latency['strategy']} ({best_avg_latency['avg_response_time_ms']:.2f}ms)")
        
        # Lowest P99 latency
        best_p99 = min(results, key=lambda x: x['p99_latency_ms'])
        print(f"🎯 Lowest P99 Latency:    {best_p99['strategy']} ({best_p99['p99_latency_ms']:.2f}ms)")
        
        # Highest throughput
        best_throughput = max(results, key=lambda x: x['throughput_rps'])
        print(f"🚀 Highest Throughput:    {best_throughput['strategy']} ({best_throughput['throughput_rps']:.2f} req/s)")
        
        # Best load balance
        best_balance = min(results, key=lambda x: x['load_balance_stdev'])
        print(f"⚖️  Best Load Balance:     {best_balance['strategy']} (stdev: {best_balance['load_balance_stdev']:.2f})")
        
        print(f"\n{'='*120}\n")
        
        # Server distribution for each algorithm
        print(f"SERVER LOAD DISTRIBUTION")
        print(f"{'-'*120}")
        
        for r in results:
            print(f"\n{r['strategy']}:")
            total_selections = sum(r['server_selections'].values())
            for server, count in sorted(r['server_selections'].items()):
                percentage = (count / total_selections * 100) if total_selections > 0 else 0
                bar = '█' * int(percentage / 2)
                failures = r['server_failures'].get(server, 0)
                print(f"  {server:<20} {count:>6} requests ({percentage:>5.1f}%) {bar:<50} [{failures} failures]")
        
        print(f"\n{'='*120}\n")


def main():
    """Main entry point"""
    print("\n" + "="*120)
    print(" " * 35 + "LOAD BALANCER ALGORITHM EVALUATOR")
    print("="*120)
    
    # Configuration
    num_servers = 5
    num_requests = 1000
    concurrent_clients = 50
    
    # Allow command line arguments
    if len(sys.argv) > 1:
        try:
            num_requests = int(sys.argv[1])
        except ValueError:
            print(f"Invalid number of requests: {sys.argv[1]}")
            return
    
    if len(sys.argv) > 2:
        try:
            concurrent_clients = int(sys.argv[2])
        except ValueError:
            print(f"Invalid number of concurrent clients: {sys.argv[2]}")
            return
    
    # Create evaluator
    evaluator = AlgorithmEvaluator(
        num_servers=num_servers,
        num_requests=num_requests,
        concurrent_clients=concurrent_clients
    )
    
    # Run evaluation
    start_time = datetime.now()
    results = evaluator.evaluate_all_algorithms()
    end_time = datetime.now()
    
    # Print results
    evaluator.print_comparison_table(results)
    
    # Summary
    total_duration = (end_time - start_time).total_seconds()
    print(f"Evaluation completed in {total_duration:.2f} seconds")
    print(f"Timestamp: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nUsage: python evaluate_algorithms.py [num_requests] [concurrent_clients]")
    print(f"Example: python evaluate_algorithms.py 2000 100\n")


if __name__ == '__main__':
    main()
