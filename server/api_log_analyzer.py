#!/usr/bin/env python3
"""
FTC API Log Analyzer

This script analyzes server logs to identify slow API calls and performance bottlenecks.
It can be run periodically or on-demand to provide insights on API performance.
"""

import re
import sys
import argparse
from collections import defaultdict
from datetime import datetime
import statistics

class APILogAnalyzer:
    def __init__(self):
        self.api_calls = defaultdict(list)
        self.timeouts = defaultdict(int)
        self.errors = defaultdict(int)
        self.request_counts = defaultdict(int)
        self.total_times = []
        self.slow_threshold = 5.0  # Seconds

    def parse_log_line(self, line):
        """Parse a single log line for API timing information."""
        # Match successful API calls
        success_match = re.search(r'\[API REQUEST\] SUCCESS: (.*?) completed in (\d+\.\d+)s total', line)
        if success_match:
            endpoint, time_taken = success_match.groups()
            self.api_calls[endpoint].append(float(time_taken))
            self.request_counts[endpoint] += 1
            self.total_times.append(float(time_taken))
            return
            
        # Match timeout API calls
        timeout_match = re.search(r'\[API REQUEST\] TIMEOUT: (.*?) after (\d+\.\d+)s', line)
        if timeout_match:
            endpoint, _ = timeout_match.groups()
            self.timeouts[endpoint] += 1
            self.request_counts[endpoint] += 1
            return
            
        # Match failed API calls
        failed_match = re.search(r'\[API REQUEST\] FAILED: (.*?) (failed|timed out) after (\d+\.\d+)s', line)
        if failed_match:
            endpoint = failed_match.group(1)
            self.errors[endpoint] += 1
            self.request_counts[endpoint] += 1
            return

    def analyze_logs(self, log_file=None, log_content=None):
        """Analyze logs from a file or content string."""
        if log_file:
            try:
                with open(log_file, 'r') as f:
                    for line in f:
                        self.parse_log_line(line)
            except FileNotFoundError:
                print(f"Error: Log file '{log_file}' not found")
                return False
        elif log_content:
            for line in log_content.splitlines():
                self.parse_log_line(line)
        else:
            print("Error: No log file or content provided")
            return False
            
        return True

    def generate_report(self):
        """Generate a report of API call performance."""
        if not self.api_calls and not self.timeouts and not self.errors:
            return "No API calls found in logs."
            
        report = []
        report.append("=" * 80)
        report.append(f"FTC API PERFORMANCE REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 80)
        
        # Overall statistics
        total_requests = sum(self.request_counts.values())
        total_errors = sum(self.errors.values())
        total_timeouts = sum(self.timeouts.values())
        error_rate = (total_errors + total_timeouts) / total_requests * 100 if total_requests > 0 else 0
        
        report.append(f"\nTotal API Requests: {total_requests}")
        report.append(f"Total Errors: {total_errors}")
        report.append(f"Total Timeouts: {total_timeouts}")
        report.append(f"Error Rate: {error_rate:.2f}%")
        
        if self.total_times:
            average_time = sum(self.total_times) / len(self.total_times)
            max_time = max(self.total_times)
            min_time = min(self.total_times)
            try:
                median_time = statistics.median(self.total_times)
                p95_time = sorted(self.total_times)[int(0.95 * len(self.total_times))]
            except:
                median_time = "N/A"
                p95_time = "N/A"
                
            report.append(f"Average Response Time: {average_time:.2f}s")
            report.append(f"Median Response Time: {median_time:.2f}s" if isinstance(median_time, float) else f"Median Response Time: {median_time}")
            report.append(f"95th Percentile Response Time: {p95_time:.2f}s" if isinstance(p95_time, float) else f"95th Percentile Response Time: {p95_time}")
            report.append(f"Min Response Time: {min_time:.2f}s")
            report.append(f"Max Response Time: {max_time:.2f}s")
        
        # Slow API calls
        report.append("\n" + "=" * 80)
        report.append("SLOWEST API CALLS (Average Time)")
        report.append("=" * 80)
        
        slow_calls = []
        for endpoint, times in self.api_calls.items():
            avg_time = sum(times) / len(times) if times else 0
            if avg_time >= self.slow_threshold:
                slow_calls.append((endpoint, avg_time, len(times)))
                
        slow_calls.sort(key=lambda x: x[1], reverse=True)
        
        if slow_calls:
            for endpoint, avg_time, count in slow_calls:
                report.append(f"Endpoint: {endpoint}")
                report.append(f"   Average Time: {avg_time:.2f}s")
                report.append(f"   Call Count: {count}")
                report.append(f"   Error Count: {self.errors.get(endpoint, 0)}")
                report.append(f"   Timeout Count: {self.timeouts.get(endpoint, 0)}")
                report.append("")
        else:
            report.append("No slow API calls found (threshold: {}s)".format(self.slow_threshold))
            
        # Most frequent API calls
        report.append("\n" + "=" * 80)
        report.append("MOST FREQUENT API CALLS")
        report.append("=" * 80)
        
        frequent_calls = sorted(self.request_counts.items(), key=lambda x: x[1], reverse=True)
        
        for endpoint, count in frequent_calls[:10]:
            avg_time = sum(self.api_calls.get(endpoint, [0])) / len(self.api_calls.get(endpoint, [1])) if self.api_calls.get(endpoint) else 0
            report.append(f"Endpoint: {endpoint}")
            report.append(f"   Call Count: {count}")
            report.append(f"   Average Time: {avg_time:.2f}s")
            report.append(f"   Error Count: {self.errors.get(endpoint, 0)}")
            report.append(f"   Timeout Count: {self.timeouts.get(endpoint, 0)}")
            report.append("")
            
        # Error-prone endpoints
        report.append("\n" + "=" * 80)
        report.append("ERROR-PRONE ENDPOINTS")
        report.append("=" * 80)
        
        error_endpoints = []
        for endpoint in set(list(self.errors.keys()) + list(self.timeouts.keys())):
            total_errors = self.errors.get(endpoint, 0) + self.timeouts.get(endpoint, 0)
            total_calls = self.request_counts.get(endpoint, 0)
            if total_calls > 0:
                error_rate = total_errors / total_calls * 100
                error_endpoints.append((endpoint, total_errors, total_calls, error_rate))
                
        error_endpoints.sort(key=lambda x: x[3], reverse=True)
        
        if error_endpoints:
            for endpoint, total_errors, total_calls, error_rate in error_endpoints:
                report.append(f"Endpoint: {endpoint}")
                report.append(f"   Error Rate: {error_rate:.2f}%")
                report.append(f"   Total Errors: {total_errors}")
                report.append(f"   Total Calls: {total_calls}")
                report.append(f"   Timeouts: {self.timeouts.get(endpoint, 0)}")
                report.append("")
        else:
            report.append("No endpoints with errors found.")
            
        return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description='Analyze FTC API logs to identify performance issues')
    parser.add_argument('-f', '--file', help='Path to the log file')
    parser.add_argument('-t', '--threshold', type=float, default=5.0, 
                        help='Threshold in seconds to identify slow API calls (default: 5.0)')
    
    args = parser.parse_args()
    
    analyzer = APILogAnalyzer()
    analyzer.slow_threshold = args.threshold
    
    if analyzer.analyze_logs(log_file=args.file):
        print(analyzer.generate_report())
    

if __name__ == "__main__":
    main()
