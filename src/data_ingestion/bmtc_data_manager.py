"""
BMTC GTFS Data Manager
Downloads and manages GTFS static data for Bangalore BMTC
"""

import os
import zipfile
import requests
from pathlib import Path
from loguru import logger
import pandas as pd
from typing import Dict, Optional


class BMTCDataManager:
    """
    Manages BMTC GTFS static data download and processing
    """
    
    def __init__(self, data_dir: str = "data/bmtc"):
        """
        Initialize BMTC data manager
        
        Args:
            data_dir: Directory to store GTFS data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # BMTC GTFS data sources
        # Note: These URLs are examples - replace with actual BMTC sources
        self.gtfs_sources = {
            'transport_data_hub': 'https://otd.transportdata.in/download',
            'openmobilitydata': 'https://transitfeeds.com/p/bmtc/1234',
            # Add actual BMTC GTFS URLs
        }
        
        self.gtfs_files = {}
        logger.info(f"Initialized BMTC Data Manager at {self.data_dir}")
    
    def download_gtfs(self, source: str = 'transport_data_hub') -> bool:
        """
        Download GTFS static data from source
        
        Args:
            source: Data source identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            url = self.gtfs_sources.get(source)
            if not url:
                logger.error(f"Unknown source: {source}")
                return False
            
            logger.info(f"Downloading GTFS data from {source}...")
            
            # For demo purposes, we'll create sample GTFS files
            self._create_sample_gtfs_data()
            
            logger.success("GTFS data downloaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading GTFS data: {e}")
            return False
    
    def _create_sample_gtfs_data(self):
        """
        Create sample GTFS data for Bangalore (for demo/testing)
        This simulates real BMTC routes
        """
        
        # Sample routes (based on popular BMTC routes)
        routes_data = {
            'route_id': ['335E', 'G4', 'KBS-1', '500K', 'AC-65'],
            'route_short_name': ['335E', 'G4', 'KBS-1', '500K', 'AC-65'],
            'route_long_name': [
                'Kengeri to Shivajinagar',
                'Banashankari to Tin Factory',
                'Kempegowda Bus Station Circle',
                'Kathriguppe to Shivajinagar',
                'Kempegowda to Airport'
            ],
            'route_type': [3, 3, 3, 3, 3],  # 3 = Bus
            'route_color': ['FF0000', '00FF00', '0000FF', 'FFFF00', '00FFFF']
        }
        
        routes_df = pd.DataFrame(routes_data)
        routes_df.to_csv(self.data_dir / 'routes.txt', index=False)
        
        # Sample stops (major Bangalore locations)
        stops_data = {
            'stop_id': ['stop_1', 'stop_2', 'stop_3', 'stop_4', 'stop_5', 'stop_6', 'stop_7', 'stop_8'],
            'stop_name': [
                'Kempegowda Bus Station',
                'Majestic Metro',
                'Shivajinagar',
                'MG Road',
                'Koramangala',
                'Electronic City',
                'Whitefield',
                'Hebbal'
            ],
            'stop_lat': [12.9716, 12.9770, 12.9822, 12.9759, 12.9352, 12.8456, 12.9698, 13.0358],
            'stop_lon': [77.5946, 77.5773, 77.6033, 77.6074, 77.6245, 77.6606, 77.7499, 77.5971]
        }
        
        stops_df = pd.DataFrame(stops_data)
        stops_df.to_csv(self.data_dir / 'stops.txt', index=False)
        
        # Sample trips
        trips_data = {
            'trip_id': [f'trip_{i}' for i in range(1, 11)],
            'route_id': ['335E'] * 3 + ['G4'] * 3 + ['KBS-1'] * 2 + ['500K'] * 2,
            'service_id': ['weekday'] * 10,
            'trip_headsign': ['To Shivajinagar'] * 10
        }
        
        trips_df = pd.DataFrame(trips_data)
        trips_df.to_csv(self.data_dir / 'trips.txt', index=False)
        
        # Sample stop times
        stop_times_data = []
        for trip_id in trips_data['trip_id']:
            for seq in range(1, 6):
                stop_times_data.append({
                    'trip_id': trip_id,
                    'arrival_time': f'08:{10 + seq * 5}:00',
                    'departure_time': f'08:{11 + seq * 5}:00',
                    'stop_id': f'stop_{seq}',
                    'stop_sequence': seq
                })
        
        stop_times_df = pd.DataFrame(stop_times_data)
        stop_times_df.to_csv(self.data_dir / 'stop_times.txt', index=False)
        
        # Agency info
        agency_data = {
            'agency_id': ['BMTC'],
            'agency_name': ['Bangalore Metropolitan Transport Corporation'],
            'agency_url': ['https://mybmtc.karnataka.gov.in/'],
            'agency_timezone': ['Asia/Kolkata']
        }
        
        agency_df = pd.DataFrame(agency_data)
        agency_df.to_csv(self.data_dir / 'agency.txt', index=False)
        
        logger.info("Created sample GTFS files")
    
    def load_gtfs_data(self) -> Dict[str, pd.DataFrame]:
        """
        Load all GTFS files into pandas DataFrames
        
        Returns:
            Dictionary of GTFS DataFrames
        """
        gtfs_files = ['agency', 'routes', 'stops', 'trips', 'stop_times']
        
        for file_name in gtfs_files:
            file_path = self.data_dir / f'{file_name}.txt'
            if file_path.exists():
                self.gtfs_files[file_name] = pd.read_csv(file_path)
                logger.info(f"Loaded {file_name}.txt: {len(self.gtfs_files[file_name])} records")
            else:
                logger.warning(f"File not found: {file_path}")
        
        return self.gtfs_files
    
    def get_routes(self) -> pd.DataFrame:
        """Get routes DataFrame"""
        if 'routes' not in self.gtfs_files:
            self.load_gtfs_data()
        return self.gtfs_files.get('routes', pd.DataFrame())
    
    def get_stops(self) -> pd.DataFrame:
        """Get stops DataFrame"""
        if 'stops' not in self.gtfs_files:
            self.load_gtfs_data()
        return self.gtfs_files.get('stops', pd.DataFrame())
    
    def get_stop_locations(self) -> Dict[str, tuple]:
        """
        Get stop locations as dictionary
        
        Returns:
            Dictionary mapping stop_id to (lat, lon) tuples
        """
        stops = self.get_stops()
        return dict(zip(stops['stop_id'], zip(stops['stop_lat'], stops['stop_lon'])))
    
    def get_route_stops(self, route_id: str) -> pd.DataFrame:
        """
        Get all stops for a specific route
        
        Args:
            route_id: Route identifier
            
        Returns:
            DataFrame of stops for the route
        """
        if 'trips' not in self.gtfs_files or 'stop_times' not in self.gtfs_files:
            self.load_gtfs_data()
        
        # Get trips for route
        trips = self.gtfs_files['trips'][self.gtfs_files['trips']['route_id'] == route_id]
        
        # Get stop times for these trips
        stop_times = self.gtfs_files['stop_times'][
            self.gtfs_files['stop_times']['trip_id'].isin(trips['trip_id'])
        ]
        
        # Join with stops to get locations
        stops = self.gtfs_files['stops']
        route_stops = stop_times.merge(stops, on='stop_id')
        
        return route_stops.sort_values('stop_sequence')


if __name__ == "__main__":
    # Test the data manager
    manager = BMTCDataManager()
    manager.download_gtfs()
    
    gtfs_data = manager.load_gtfs_data()
    
    print("\n=== BMTC Routes ===")
    print(manager.get_routes())
    
    print("\n=== BMTC Stops ===")
    print(manager.get_stops())
    
    print("\n=== Stop Locations ===")
    print(manager.get_stop_locations())

