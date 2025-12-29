"""
Bus Bunching Control Optimizer
OR-based optimization model for real-time bus holding and dispatch decisions
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from loguru import logger
from pulp import *
from scipy.optimize import minimize


class BusBunchingOptimizer:
    """
    Implements OR-based optimization for bus bunching control
    using rolling-horizon optimization approach
    """
    
    def __init__(
        self,
        target_headway: float = 300.0,  # 5 minutes in seconds
        bunching_threshold: float = 120.0,  # 2 minutes
        max_holding_time: float = 180.0,  # 3 minutes max hold
        passenger_weight: float = 1.0,
        schedule_weight: float = 0.5,
        bunching_penalty: float = 2.0
    ):
        """
        Initialize optimizer
        
        Args:
            target_headway: Target time between buses (seconds)
            bunching_threshold: Threshold for considering buses bunched
            max_holding_time: Maximum allowed holding time
            passenger_weight: Weight for passenger wait time in objective
            schedule_weight: Weight for schedule adherence
            bunching_penalty: Penalty multiplier for bunching violations
        """
        self.target_headway = target_headway
        self.bunching_threshold = bunching_threshold
        self.max_holding_time = max_holding_time
        self.passenger_weight = passenger_weight
        self.schedule_weight = schedule_weight
        self.bunching_penalty = bunching_penalty
        
        self.optimization_count = 0
        logger.info(f"Initialized Bus Bunching Optimizer with target headway {target_headway}s")
    
    def detect_bunching(
        self,
        bus_positions: pd.DataFrame,
        route_id: str
    ) -> List[Dict]:
        """
        Detect bus bunching on a route
        
        Args:
            bus_positions: DataFrame with vehicle positions
            route_id: Route to analyze
            
        Returns:
            List of bunching events
        """
        route_buses = bus_positions[bus_positions['route_id'] == route_id].copy()
        
        if len(route_buses) < 2:
            return []
        
        # Sort by position along route (using stop_sequence as proxy)
        route_buses = route_buses.sort_values('current_stop_sequence')
        
        bunching_events = []
        
        for i in range(len(route_buses) - 1):
            bus1 = route_buses.iloc[i]
            bus2 = route_buses.iloc[i + 1]
            
            # Calculate time gap between buses
            time_gap = abs((bus2['timestamp'] - bus1['timestamp']))
            
            if time_gap < self.bunching_threshold:
                bunching_events.append({
                    'bus1_id': bus1['vehicle_id'],
                    'bus2_id': bus2['vehicle_id'],
                    'time_gap': time_gap,
                    'severity': (self.bunching_threshold - time_gap) / self.bunching_threshold,
                    'location': bus1['stop_id']
                })
        
        if bunching_events:
            logger.warning(f"Detected {len(bunching_events)} bunching events on route {route_id}")
        
        return bunching_events
    
    def calculate_headway_deviation(
        self,
        bus_positions: pd.DataFrame,
        route_id: str
    ) -> Dict:
        """
        Calculate headway statistics for a route
        
        Args:
            bus_positions: Vehicle positions
            route_id: Route identifier
            
        Returns:
            Dictionary of headway statistics
        """
        route_buses = bus_positions[bus_positions['route_id'] == route_id].copy()
        
        if len(route_buses) < 2:
            return {'mean_headway': 0, 'std_headway': 0, 'cv_headway': 0}
        
        route_buses = route_buses.sort_values('timestamp')
        
        # Calculate actual headways
        headways = []
        for i in range(len(route_buses) - 1):
            headway = (route_buses.iloc[i + 1]['timestamp'] - 
                      route_buses.iloc[i]['timestamp'])
            headways.append(headway)
        
        if not headways:
            return {'mean_headway': 0, 'std_headway': 0, 'cv_headway': 0}
        
        mean_headway = np.mean(headways)
        std_headway = np.std(headways)
        cv_headway = std_headway / mean_headway if mean_headway > 0 else 0
        
        return {
            'mean_headway': mean_headway,
            'std_headway': std_headway,
            'cv_headway': cv_headway,
            'min_headway': min(headways),
            'max_headway': max(headways),
            'target_deviation': abs(mean_headway - self.target_headway)
        }
    
    def optimize_holding_decisions(
        self,
        bus_states: List[Dict],
        passenger_demand: pd.DataFrame,
        horizon_minutes: int = 30
    ) -> Dict[str, float]:
        """
        Optimize bus holding decisions using linear programming
        
        Args:
            bus_states: List of current bus states (position, schedule, etc.)
            passenger_demand: Current passenger demand at stops
            horizon_minutes: Optimization horizon
            
        Returns:
            Dictionary mapping bus_id to optimal holding time
        """
        self.optimization_count += 1
        
        n_buses = len(bus_states)
        if n_buses == 0:
            return {}
        
        # Create optimization problem
        prob = LpProblem("Bus_Holding_Optimization", LpMinimize)
        
        # Decision variables: holding time for each bus (seconds)
        holding_times = {}
        for i, bus in enumerate(bus_states):
            var_name = f"hold_{bus['vehicle_id']}"
            holding_times[bus['vehicle_id']] = LpVariable(
                var_name,
                lowBound=0,
                upBound=self.max_holding_time
            )
        
        # Auxiliary variables for headway deviations
        headway_devs = []
        for i in range(n_buses - 1):
            dev = LpVariable(f"headway_dev_{i}", lowBound=0)
            headway_devs.append(dev)
        
        # Objective function components
        passenger_cost = 0
        schedule_cost = 0
        bunching_cost = 0
        
        for i, bus in enumerate(bus_states):
            bus_id = bus['vehicle_id']
            
            # Passenger wait cost (proportional to holding time and demand)
            stop_demand = passenger_demand[
                passenger_demand['stop_id'] == bus.get('current_stop')
            ]
            n_passengers = len(stop_demand)
            
            passenger_cost += holding_times[bus_id] * n_passengers
            
            # Schedule adherence cost (linearized - avoiding quadratic terms)
            schedule_delay = bus.get('schedule_delay', 0)
            # Use absolute value approximation for LP (linearized)
            schedule_cost += holding_times[bus_id] + abs(schedule_delay)
        
        # Headway deviation cost
        for i in range(n_buses - 1):
            bus1 = bus_states[i]
            bus2 = bus_states[i + 1]
            
            # Current time gap
            current_gap = bus2['position_time'] - bus1['position_time']
            
            # Projected gap after holding
            projected_gap = (current_gap + 
                           holding_times[bus2['vehicle_id']] - 
                           holding_times[bus1['vehicle_id']])
            
            # Add constraint for headway deviation
            prob += (headway_devs[i] >= projected_gap - self.target_headway)
            prob += (headway_devs[i] >= self.target_headway - projected_gap)
            
            bunching_cost += headway_devs[i] * self.bunching_penalty
        
        # Combined objective
        prob += (self.passenger_weight * passenger_cost +
                self.schedule_weight * schedule_cost +
                bunching_cost)
        
        # Solve optimization problem
        try:
            prob.solve(PULP_CBC_CMD(msg=0))
            
            if prob.status == 1:  # Optimal solution found
                results = {
                    bus_id: var.varValue 
                    for bus_id, var in holding_times.items()
                }
                
                logger.info(f"Optimization #{self.optimization_count}: Found optimal holding times")
                return results
            else:
                logger.warning(f"Optimization failed with status {prob.status}")
                return {bus['vehicle_id']: 0 for bus in bus_states}
                
        except Exception as e:
            logger.error(f"Error in optimization: {e}")
            return {bus['vehicle_id']: 0 for bus in bus_states}
    
    def calculate_performance_metrics(
        self,
        actual_headways: List[float],
        passenger_wait_times: List[float]
    ) -> Dict:
        """
        Calculate system performance metrics
        
        Args:
            actual_headways: List of observed headways
            passenger_wait_times: List of passenger wait times
            
        Returns:
            Dictionary of performance metrics
        """
        metrics = {}
        
        if actual_headways:
            metrics['mean_headway'] = np.mean(actual_headways)
            metrics['std_headway'] = np.std(actual_headways)
            metrics['cv_headway'] = metrics['std_headway'] / metrics['mean_headway']
            metrics['headway_regularity'] = 1 - metrics['cv_headway']
            
            # Bunching frequency
            bunched = sum(1 for h in actual_headways if h < self.bunching_threshold)
            metrics['bunching_rate'] = bunched / len(actual_headways)
        
        if passenger_wait_times:
            metrics['mean_wait_time'] = np.mean(passenger_wait_times)
            metrics['median_wait_time'] = np.median(passenger_wait_times)
            metrics['95th_percentile_wait'] = np.percentile(passenger_wait_times, 95)
            metrics['max_wait_time'] = max(passenger_wait_times)
        
        return metrics
    
    def compare_with_baseline(
        self,
        optimized_metrics: Dict,
        baseline_metrics: Dict
    ) -> Dict:
        """
        Compare optimized performance with baseline
        
        Args:
            optimized_metrics: Metrics with optimization
            baseline_metrics: Metrics without optimization
            
        Returns:
            Improvement statistics
        """
        improvements = {}
        
        for key in optimized_metrics:
            if key in baseline_metrics:
                baseline_val = baseline_metrics[key]
                optimized_val = optimized_metrics[key]
                
                if baseline_val != 0:
                    improvement_pct = ((baseline_val - optimized_val) / baseline_val) * 100
                    improvements[f'{key}_improvement'] = improvement_pct
        
        logger.info("Performance comparison:")
        for key, val in improvements.items():
            logger.info(f"  {key}: {val:.2f}%")
        
        return improvements


class DynamicScheduleOptimizer:
    """
    Dynamic schedule adjustment based on real-time demand
    """
    
    def __init__(self, base_frequency: int = 10):
        """
        Initialize dynamic scheduler
        
        Args:
            base_frequency: Base buses per hour
        """
        self.base_frequency = base_frequency
        logger.info("Initialized Dynamic Schedule Optimizer")
    
    def optimize_dispatch_frequency(
        self,
        current_demand: float,
        forecast_demand: float,
        current_capacity: int,
        time_horizon_hours: float = 1.0
    ) -> int:
        """
        Optimize bus dispatch frequency based on demand
        
        Args:
            current_demand: Current passengers per hour
            forecast_demand: Forecasted demand
            current_capacity: Available buses
            time_horizon_hours: Planning horizon
            
        Returns:
            Optimal number of buses to dispatch
        """
        avg_demand = (current_demand + forecast_demand) / 2
        bus_capacity = 50  # Assuming 50 passengers per bus
        
        # Calculate required buses
        required_buses = np.ceil(avg_demand / bus_capacity)
        
        # Constrain by available capacity
        optimal_buses = min(required_buses, current_capacity)
        
        # Ensure minimum service level
        optimal_buses = max(optimal_buses, self.base_frequency // 2)
        
        return int(optimal_buses)


if __name__ == "__main__":
    # Test the optimizer
    optimizer = BusBunchingOptimizer()
    
    # Create sample bus states
    bus_states = [
        {
            'vehicle_id': 'bus_1',
            'current_stop': 'stop_1',
            'position_time': 0,
            'schedule_delay': 120
        },
        {
            'vehicle_id': 'bus_2',
            'current_stop': 'stop_2',
            'position_time': 180,  # 3 minutes behind
            'schedule_delay': 60
        },
        {
            'vehicle_id': 'bus_3',
            'current_stop': 'stop_3',
            'position_time': 600,  # 10 minutes behind bus_1
            'schedule_delay': -30
        }
    ]
    
    # Sample passenger demand
    demand = pd.DataFrame({
        'stop_id': ['stop_1', 'stop_2', 'stop_3'] * 5,
        'passenger_id': [f'pax_{i}' for i in range(15)]
    })
    
    # Run optimization
    holdings = optimizer.optimize_holding_decisions(bus_states, demand)
    
    print("\n=== Optimal Holding Times ===")
    for bus_id, hold_time in holdings.items():
        print(f"{bus_id}: {hold_time:.1f} seconds")
    
    # Test performance metrics
    headways = [300, 180, 450, 240, 360]  # Sample headways
    wait_times = [5, 12, 8, 15, 6, 10, 20, 7]  # Sample wait times
    
    metrics = optimizer.calculate_performance_metrics(headways, wait_times)
    print("\n=== Performance Metrics ===")
    for key, val in metrics.items():
        print(f"{key}: {val:.2f}")

