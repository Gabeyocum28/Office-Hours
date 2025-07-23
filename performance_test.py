#!/usr/bin/env python3
"""
Performance testing script for OfficeHours AI
Tests latency and throughput under various conditions
"""

import asyncio
import aiohttp
import time
import json
import statistics
import argparse
from typing import List, Dict, Any
import concurrent.futures
import threading
from datetime import datetime

# Configuration
API_BASE = "http://localhost:5001"
TEST_MESSAGES = [
    "What is the derivative of x squared?",
    "Explain quantum mechanics in simple terms.",
    "How do I solve this calculus problem?",
    "What are the main concepts in linear algebra?",
    "Can you help me understand machine learning?",
    "Explain the difference between supervised and unsupervised learning.",
    "What is the chain rule in calculus?",
    "How does gradient descent work?",
    "What is the fundamental theorem of calculus?",
    "Explain Bayes' theorem with an example."
]

class PerformanceTest:
    def __init__(self, base_url: str = API_BASE):
        self.base_url = base_url
        self.results = {
            'response_times': [],
            'first_token_times': [],
            'total_processing_times': [],
            'throughput_tests': [],
            'error_count': 0,
            'success_count': 0
        }
        
    async def test_single_request(self, session: aiohttp.ClientSession, message: str, session_id: int) -> Dict[str, Any]:
        """Test a single chat request and measure latency"""
        start_time = time.time()
        first_token_time = None
        total_chars = 0
        audio_chunks = 0
        
        try:
            payload = {
                'session_id': session_id,
                'message': message,
                'use_avatar': True
            }
            
            async with session.post(f"{self.base_url}/chat/message", json=payload) as response:
                if response.status != 200:
                    self.results['error_count'] += 1
                    return {'error': f"HTTP {response.status}"}
                
                # Read streaming response
                async for line in response.content:
                    if line.startswith(b'data:'):
                        try:
                            data = json.loads(line[5:].decode().strip())
                            
                            if data['type'] == 'text':
                                if first_token_time is None:
                                    first_token_time = time.time()
                                total_chars += len(data['content'])
                            elif data['type'] == 'audio':
                                audio_chunks += 1
                            elif data['type'] == 'end':
                                break
                                
                        except json.JSONDecodeError:
                            continue
                
                end_time = time.time()
                self.results['success_count'] += 1
                
                return {
                    'total_time': end_time - start_time,
                    'first_token_time': first_token_time - start_time if first_token_time else None,
                    'chars_generated': total_chars,
                    'audio_chunks': audio_chunks,
                    'message_length': len(message)
                }
                
        except Exception as e:
            self.results['error_count'] += 1
            return {'error': str(e)}
    
    async def test_latency(self, num_requests: int = 10) -> None:
        """Test response latency with sequential requests"""
        print(f"\n🧪 Testing latency with {num_requests} sequential requests...")
        
        # First, create a test session
        session_id = await self.create_test_session()
        if not session_id:
            print("❌ Failed to create test session")
            return
        
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
        timeout = aiohttp.ClientTimeout(total=120)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            for i in range(num_requests):
                message = TEST_MESSAGES[i % len(TEST_MESSAGES)]
                print(f"  Request {i+1}/{num_requests}: {message[:50]}...")
                
                result = await self.test_single_request(session, message, session_id)
                
                if 'error' not in result:
                    self.results['response_times'].append(result['total_time'])
                    if result['first_token_time']:
                        self.results['first_token_times'].append(result['first_token_time'])
                    
                    print(f"    ✅ Completed in {result['total_time']:.3f}s (first token: {result['first_token_time']:.3f}s if first_token_time else 'N/A')")
                else:
                    print(f"    ❌ Error: {result['error']}")
                
                # Small delay between requests to avoid overwhelming
                await asyncio.sleep(0.5)
    
    async def test_concurrent_requests(self, num_concurrent: int = 5, requests_per_client: int = 3) -> None:
        """Test system behavior under concurrent load"""
        print(f"\n🔥 Testing concurrent load: {num_concurrent} clients, {requests_per_client} requests each...")
        
        # Create test sessions for each concurrent client
        session_ids = []
        for i in range(num_concurrent):
            session_id = await self.create_test_session()
            if session_id:
                session_ids.append(session_id)
        
        if len(session_ids) != num_concurrent:
            print("❌ Failed to create all test sessions")
            return
        
        start_time = time.time()
        connector = aiohttp.TCPConnector(limit=200, limit_per_host=50)
        timeout = aiohttp.ClientTimeout(total=180)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = []
            
            for client_id in range(num_concurrent):
                for req_id in range(requests_per_client):
                    message = TEST_MESSAGES[(client_id * requests_per_client + req_id) % len(TEST_MESSAGES)]
                    task = self.test_single_request(session, message, session_ids[client_id])
                    tasks.append(task)
            
            # Execute all requests concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            successful_results = [r for r in results if isinstance(r, dict) and 'error' not in r]
            
            self.results['throughput_tests'].append({
                'concurrent_clients': num_concurrent,
                'requests_per_client': requests_per_client,
                'total_requests': len(tasks),
                'successful_requests': len(successful_results),
                'total_time': total_time,
                'throughput_rps': len(successful_results) / total_time,
                'avg_response_time': statistics.mean([r['total_time'] for r in successful_results]) if successful_results else 0
            })
            
            print(f"  ✅ Completed {len(successful_results)}/{len(tasks)} requests in {total_time:.2f}s")
            print(f"  📊 Throughput: {len(successful_results) / total_time:.2f} RPS")
    
    async def create_test_session(self) -> int:
        """Create a test chat session"""
        try:
            connector = aiohttp.TCPConnector()
            timeout = aiohttp.ClientTimeout(total=30)
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                # This is a simplified session creation - you might need to adapt this
                # based on your actual authentication and session creation logic
                payload = {'office_id': 1}  # Assuming office_id 1 exists
                async with session.post(f"{self.base_url}/chat/start_session", json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('session_id')
                    else:
                        print(f"Failed to create session: HTTP {response.status}")
                        return None
        except Exception as e:
            print(f"Error creating test session: {e}")
            return None
    
    def print_results(self) -> None:
        """Print comprehensive performance test results"""
        print("\n" + "="*80)
        print("🏁 PERFORMANCE TEST RESULTS")
        print("="*80)
        
        print(f"\n📊 OVERALL STATISTICS:")
        print(f"  Total Requests: {self.results['success_count'] + self.results['error_count']}")
        print(f"  Successful: {self.results['success_count']}")
        print(f"  Errors: {self.results['error_count']}")
        print(f"  Success Rate: {(self.results['success_count'] / (self.results['success_count'] + self.results['error_count']) * 100):.1f}%")
        
        if self.results['response_times']:
            print(f"\n⚡ RESPONSE TIME ANALYSIS:")
            response_times = self.results['response_times']
            print(f"  Mean: {statistics.mean(response_times):.3f}s")
            print(f"  Median: {statistics.median(response_times):.3f}s")
            print(f"  Min: {min(response_times):.3f}s")
            print(f"  Max: {max(response_times):.3f}s")
            print(f"  Std Dev: {statistics.stdev(response_times):.3f}s")
            
            # Percentiles
            sorted_times = sorted(response_times)
            p95 = sorted_times[int(0.95 * len(sorted_times))]
            p99 = sorted_times[int(0.99 * len(sorted_times))]
            print(f"  95th percentile: {p95:.3f}s")
            print(f"  99th percentile: {p99:.3f}s")
        
        if self.results['first_token_times']:
            print(f"\n🚀 FIRST TOKEN LATENCY:")
            first_token_times = self.results['first_token_times']
            print(f"  Mean: {statistics.mean(first_token_times):.3f}s")
            print(f"  Median: {statistics.median(first_token_times):.3f}s")
            print(f"  Min: {min(first_token_times):.3f}s")
            print(f"  Max: {max(first_token_times):.3f}s")
        
        if self.results['throughput_tests']:
            print(f"\n🔥 CONCURRENT LOAD TEST RESULTS:")
            for test in self.results['throughput_tests']:
                print(f"  {test['concurrent_clients']} concurrent clients:")
                print(f"    Throughput: {test['throughput_rps']:.2f} RPS")
                print(f"    Success Rate: {(test['successful_requests']/test['total_requests']*100):.1f}%")
                print(f"    Avg Response Time: {test['avg_response_time']:.3f}s")
        
        print(f"\n🎯 PERFORMANCE RATING:")
        if self.results['first_token_times']:
            avg_first_token = statistics.mean(self.results['first_token_times'])
            if avg_first_token < 1.0:
                print("  🟢 EXCELLENT - Sub-second first token latency")
            elif avg_first_token < 2.0:
                print("  🟡 GOOD - Fast response times")
            elif avg_first_token < 5.0:
                print("  🟠 ACCEPTABLE - Moderate latency")
            else:
                print("  🔴 NEEDS IMPROVEMENT - High latency detected")
        
        print("\n💡 OPTIMIZATION RECOMMENDATIONS:")
        if self.results['response_times']:
            avg_response = statistics.mean(self.results['response_times'])
            if avg_response > 10:
                print("  • Consider reducing max_tokens or using faster models")
            if self.results['error_count'] > 0:
                print("  • Investigate error causes and improve error handling")
        
        print("\n" + "="*80)

async def main():
    parser = argparse.ArgumentParser(description="OfficeHours AI Performance Testing")
    parser.add_argument("--latency-tests", type=int, default=10, help="Number of latency test requests")
    parser.add_argument("--concurrent-clients", type=int, default=5, help="Number of concurrent clients")
    parser.add_argument("--requests-per-client", type=int, default=3, help="Requests per concurrent client")
    parser.add_argument("--base-url", default=API_BASE, help="Base URL for API")
    
    args = parser.parse_args()
    
    print("🚀 Starting OfficeHours AI Performance Tests")
    print(f"   Target: {args.base_url}")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tester = PerformanceTest(args.base_url)
    
    try:
        # Test latency
        await tester.test_latency(args.latency_tests)
        
        # Test concurrent load
        await tester.test_concurrent_requests(args.concurrent_clients, args.requests_per_client)
        
        # Print results
        tester.print_results()
        
    except KeyboardInterrupt:
        print("\n⏹️  Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Test error: {e}")
    
    print("\n✅ Performance testing completed!")

if __name__ == "__main__":
    asyncio.run(main())