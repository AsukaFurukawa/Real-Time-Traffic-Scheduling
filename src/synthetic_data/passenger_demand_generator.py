"""
Synthetic Passenger Demand Generator
Generates realistic passenger arrival patterns for bus stops
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger
from scipy import stats


class PassengerDemandGenerator:
    """
    Generates synthetic passenger demand data with realistic patterns
    """
    
    def __init__(self, seed: Optional[int] = None):
        """
        Initialize demand generator
        
        Args:
            seed: Random seed for reproducibility
        """
        if seed:
            np.random.seed(seed)
        
        # Define demand patterns by time of day
        self.time_patterns = {
            'morning_peak': {'hours': (7, 10), 'multiplier': 2.5},
            'midday': {'hours': (10, 17), 'multiplier': 1.0},
            'evening_peak': {'hours': (17, 20), 'multiplier': 2.8},
            'night': {'hours': (20, 24), 'multiplier': 0.3},
            'early_morning': {'hours': (0, 7), 'multiplier': 0.2}
        }
        
        # Day of week patterns (Monday=0, Sunday=6)
        self.day_patterns = {
            0: 1.2,  # Monday - higher
            1: 1.1,  # Tuesday
            2: 1.0,  # Wednesday - baseline
            3: 1.0,  # Thursday
            4: 1.15, # Friday - slightly higher
            5: 0.7,  # Saturday - lower
            6: 0.5   # Sunday - much lower
        }
        
        logger.info("Initialized Passenger Demand Generator")
    
    def get_time_multiplier(self, hour: int) -> float:
        """
        Get demand multiplier based on hour of day
        
        Args:
            hour: Hour (0-23)
            
        Returns:
            Demand multiplier
        """
        for pattern in self.time_patterns.values():
            hours = pattern['hours']
            if hours[0] <= hour < hours[1]:
                return pattern['multiplier']
        
        return 0.2  # Default for any unmatched hours
    
    def get_day_multiplier(self, day_of_week: int) -> float:
        """
        Get demand multiplier based on day of week
        
        Args:
            day_of_week: Day (0=Monday, 6=Sunday)
            
        Returns:
            Demand multiplier
        """
        return self.day_patterns.get(day_of_week, 1.0)
    
    def generate_passenger_arrivals(
        self,
        stop_id: str,
        start_time: datetime,
        duration_minutes: int = 60,
        base_rate: float = 10.0,
        stop_importance: float = 1.0
    ) -> pd.DataFrame:
        """
        Generate passenger arrivals at a stop using Poisson process
        
        Args:
            stop_id: Stop identifier
            start_time: Start time for generation
            duration_minutes: Duration to generate data for
            base_rate: Base arrival rate (passengers per minute)
            stop_importance: Multiplier for stop importance (0.5 to 2.0)
            
        Returns:
            DataFrame with passenger arrival times
        """
        # Calculate effective arrival rate
        hour = start_time.hour
        day_of_week = start_time.weekday()
        
        time_mult = self.get_time_multiplier(hour)
        day_mult = self.get_day_multiplier(day_of_week)
        
        effective_rate = base_rate * time_mult * day_mult * stop_importance
        
        # Generate arrivals using Poisson process
        num_arrivals = np.random.poisson(effective_rate * duration_minutes)
        
        # Generate random arrival times within duration
        arrival_offsets = np.random.uniform(0, duration_minutes, num_arrivals)
        arrival_offsets.sort()
        
        arrival_times = [start_time + timedelta(minutes=float(offset)) 
                        for offset in arrival_offsets]
        
        # Generate destinations (simplified - could be more sophisticated)
        destinations = np.random.choice(
            ['downtown', 'residential', 'commercial', 'industrial'],
            size=num_arrivals,
            p=[0.4, 0.3, 0.2, 0.1]
        )
        
        # Generate boarding preferences (normal, express, etc.)
        bus_preferences = np.random.choice(
            ['any', 'express', 'ac_only'],
            size=num_arrivals,
            p=[0.7, 0.2, 0.1]
        )
        
        df = pd.DataFrame({
            'stop_id': stop_id,
            'arrival_time': arrival_times,
            'passenger_id': [f'pax_{stop_id}_{i}' for i in range(num_arrivals)],
            'destination_type': destinations,
            'bus_preference': bus_preferences,
            'wait_tolerance_minutes': np.random.normal(10, 3, num_arrivals).clip(3, 20)
        })
        
        logger.debug(f"Generated {num_arrivals} passengers at {stop_id} for {duration_minutes} mins")
        return df
    
    def generate_demand_for_route(
        self,
        route_id: str,
        stops: List[str],
        start_time: datetime,
        duration_minutes: int = 60,
        base_rates: Optional[Dict[str, float]] = None
    ) -> pd.DataFrame:
        """
        Generate passenger demand for all stops on a route
        
        Args:
            route_id: Route identifier
            stops: List of stop IDs on route
            start_time: Start time
            duration_minutes: Duration to generate
            base_rates: Optional dict of base rates per stop
            
        Returns:
            Combined DataFrame of all passenger arrivals
        """
        all_arrivals = []
        
        if base_rates is None:
            # Default: major stops have higher rates
            base_rates = {stop: 10.0 for stop in stops}
            # First and last stops typically busier
            if len(stops) > 2:
                base_rates[stops[0]] = 15.0
                base_rates[stops[-1]] = 15.0
        
        for stop in stops:
            stop_importance = 1.0
            # Major hubs get higher importance
            if 'kempegowda' in stop.lower() or 'majestic' in stop.lower():
                stop_importance = 2.0
            elif 'shivajinagar' in stop.lower() or 'mg road' in stop.lower():
                stop_importance = 1.5
            
            base_rate = base_rates.get(stop, 10.0)
            
            arrivals = self.generate_passenger_arrivals(
                stop,
                start_time,
                duration_minutes,
                base_rate,
                stop_importance
            )
            
            arrivals['route_id'] = route_id
            all_arrivals.append(arrivals)
        
        combined = pd.concat(all_arrivals, ignore_index=True)
        combined = combined.sort_values('arrival_time')
        
        logger.info(f"Generated {len(combined)} total passengers for route {route_id}")
        return combined
    
    def generate_boarding_demand(
        self,
        passenger_arrivals: pd.DataFrame,
        bus_arrival_time: datetime,
        stop_id: str,
        bus_capacity: int = 50
    ) -> Dict:
        """
        Calculate boarding demand when bus arrives at stop
        
        Args:
            passenger_arrivals: DataFrame of passenger arrivals
            bus_arrival_time: When bus arrives
            stop_id: Stop identifier
            bus_capacity: Bus capacity
            
        Returns:
            Dictionary with boarding statistics
        """
        # Filter passengers waiting at this stop
        waiting = passenger_arrivals[
            (passenger_arrivals['stop_id'] == stop_id) &
            (passenger_arrivals['arrival_time'] <= bus_arrival_time)
        ]
        
        # Calculate wait times
        waiting['wait_time_minutes'] = (
            bus_arrival_time - waiting['arrival_time']
        ).dt.total_seconds() / 60
        
        # Passengers who gave up waiting (exceeded tolerance)
        gave_up = waiting[waiting['wait_time_minutes'] > waiting['wait_tolerance_minutes']]
        still_waiting = waiting[waiting['wait_time_minutes'] <= waiting['wait_tolerance_minutes']]
        
        # Simulate boarding (some may not board due to capacity/preference)
        boardable = still_waiting.sample(frac=0.95)  # 95% actually board when bus arrives
        actual_boarding = min(len(boardable), bus_capacity)
        
        return {
            'stop_id': stop_id,
            'bus_arrival_time': bus_arrival_time,
            'passengers_waiting': len(still_waiting),
            'passengers_gave_up': len(gave_up),
            'passengers_boarding': actual_boarding,
            'passengers_left_behind': max(0, len(boardable) - actual_boarding),
            'avg_wait_time': waiting['wait_time_minutes'].mean() if len(waiting) > 0 else 0,
            'max_wait_time': waiting['wait_time_minutes'].max() if len(waiting) > 0 else 0
        }
    
    def generate_continuous_stream(
        self,
        stops: List[str],
        interval_seconds: int = 30,
        callback=None
    ):
        """
        Generate continuous passenger arrival stream
        
        Args:
            stops: List of stop IDs
            interval_seconds: Update interval
            callback: Function to call with new data
        """
        import time
        
        logger.info(f"Starting continuous passenger generation for {len(stops)} stops")
        
        while True:
            try:
                current_time = datetime.now()
                
                # Generate arrivals for next interval
                all_arrivals = []
                for stop in stops:
                    arrivals = self.generate_passenger_arrivals(
                        stop,
                        current_time,
                        duration_minutes=interval_seconds / 60,
                        base_rate=10.0
                    )
                    all_arrivals.append(arrivals)
                
                combined = pd.concat(all_arrivals, ignore_index=True)
                
                if callback and len(combined) > 0:
                    callback(combined)
                
                time.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("Stopping passenger generation")
                break
            except Exception as e:
                logger.error(f"Error in generation loop: {e}")
                time.sleep(interval_seconds)


if __name__ == "__main__":
    # Test the generator
    generator = PassengerDemandGenerator(seed=42)
    
    # Test single stop
    start = datetime(2025, 1, 15, 8, 30)  # Morning peak
    arrivals = generator.generate_passenger_arrivals(
        'stop_1',
        start,
        duration_minutes=60,
        base_rate=10.0
    )
    
    print(f"\n=== Generated {len(arrivals)} passengers ===")
    print(arrivals.head(10))
    
    # Test route demand
    stops = ['stop_1', 'stop_2', 'stop_3', 'stop_4']
    route_demand = generator.generate_demand_for_route(
        '335E',
        stops,
        start,
        duration_minutes=60
    )
    
    print(f"\n=== Route demand: {len(route_demand)} passengers across {len(stops)} stops ===")
    print(route_demand.groupby('stop_id').size())

