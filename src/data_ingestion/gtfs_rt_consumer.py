"""
GTFS-Realtime Data Consumer
Fetches and parses GTFS-RT feeds for Bangalore BMTC buses
"""

import time
import requests
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger
from google.transit import gtfs_realtime_pb2


class GTFSRealtimeConsumer:
    """
    Consumes GTFS-Realtime feeds and parses vehicle positions and trip updates
    """
    
    def __init__(self, feed_url: str, feed_type: str = "vehicle_positions"):
        """
        Initialize GTFS-RT consumer
        
        Args:
            feed_url: URL of the GTFS-RT feed
            feed_type: Type of feed ('vehicle_positions', 'trip_updates', 'service_alerts')
        """
        self.feed_url = feed_url
        self.feed_type = feed_type
        self.last_fetch_time = None
        self.fetch_count = 0
        
        logger.info(f"Initialized GTFS-RT Consumer for {feed_type}")
    
    def fetch_feed(self) -> Optional[gtfs_realtime_pb2.FeedMessage]:
        """
        Fetch and parse GTFS-RT feed
        
        Returns:
            Parsed FeedMessage object or None if error
        """
        try:
            response = requests.get(
                self.feed_url,
                timeout=10,
                headers={'User-Agent': 'BMTC-Realtime-System/1.0'}
            )
            response.raise_for_status()
            
            feed = gtfs_realtime_pb2.FeedMessage()
            feed.ParseFromString(response.content)
            
            self.last_fetch_time = datetime.now()
            self.fetch_count += 1
            
            logger.debug(f"Fetched feed with {len(feed.entity)} entities")
            return feed
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching GTFS-RT feed: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing GTFS-RT feed: {e}")
            return None
    
    def parse_vehicle_positions(self, feed: gtfs_realtime_pb2.FeedMessage) -> List[Dict]:
        """
        Parse vehicle position entities from feed
        
        Args:
            feed: GTFS-RT FeedMessage
            
        Returns:
            List of vehicle position dictionaries
        """
        vehicles = []
        
        for entity in feed.entity:
            if entity.HasField('vehicle'):
                vehicle = entity.vehicle
                
                vehicle_data = {
                    'vehicle_id': vehicle.vehicle.id if vehicle.HasField('vehicle') else None,
                    'trip_id': vehicle.trip.trip_id if vehicle.HasField('trip') else None,
                    'route_id': vehicle.trip.route_id if vehicle.HasField('trip') else None,
                    'latitude': vehicle.position.latitude if vehicle.HasField('position') else None,
                    'longitude': vehicle.position.longitude if vehicle.HasField('position') else None,
                    'bearing': vehicle.position.bearing if vehicle.HasField('position') else None,
                    'speed': vehicle.position.speed if vehicle.HasField('position') else None,
                    'timestamp': vehicle.timestamp if vehicle.HasField('timestamp') else None,
                    'current_stop_sequence': vehicle.current_stop_sequence if vehicle.HasField('current_stop_sequence') else None,
                    'stop_id': vehicle.stop_id if vehicle.HasField('stop_id') else None,
                    'current_status': vehicle.current_status if vehicle.HasField('current_status') else None,
                    'congestion_level': vehicle.congestion_level if vehicle.HasField('congestion_level') else None,
                    'occupancy_status': vehicle.occupancy_status if vehicle.HasField('occupancy_status') else None,
                }
                
                vehicles.append(vehicle_data)
        
        logger.info(f"Parsed {len(vehicles)} vehicle positions")
        return vehicles
    
    def parse_trip_updates(self, feed: gtfs_realtime_pb2.FeedMessage) -> List[Dict]:
        """
        Parse trip update entities from feed
        
        Args:
            feed: GTFS-RT FeedMessage
            
        Returns:
            List of trip update dictionaries
        """
        trip_updates = []
        
        for entity in feed.entity:
            if entity.HasField('trip_update'):
                trip = entity.trip_update
                
                # Parse stop time updates
                stop_updates = []
                for stu in trip.stop_time_update:
                    stop_update = {
                        'stop_sequence': stu.stop_sequence if stu.HasField('stop_sequence') else None,
                        'stop_id': stu.stop_id if stu.HasField('stop_id') else None,
                        'arrival_delay': stu.arrival.delay if stu.HasField('arrival') else None,
                        'arrival_time': stu.arrival.time if stu.HasField('arrival') else None,
                        'departure_delay': stu.departure.delay if stu.HasField('departure') else None,
                        'departure_time': stu.departure.time if stu.HasField('departure') else None,
                    }
                    stop_updates.append(stop_update)
                
                trip_data = {
                    'trip_id': trip.trip.trip_id if trip.HasField('trip') else None,
                    'route_id': trip.trip.route_id if trip.HasField('trip') else None,
                    'vehicle_id': trip.vehicle.id if trip.HasField('vehicle') else None,
                    'timestamp': trip.timestamp if trip.HasField('timestamp') else None,
                    'delay': trip.delay if trip.HasField('delay') else None,
                    'stop_time_updates': stop_updates
                }
                
                trip_updates.append(trip_data)
        
        logger.info(f"Parsed {len(trip_updates)} trip updates")
        return trip_updates
    
    def stream_data(self, interval: int = 10, callback=None):
        """
        Continuously stream GTFS-RT data at specified interval
        
        Args:
            interval: Fetch interval in seconds
            callback: Optional callback function to process parsed data
        """
        logger.info(f"Starting GTFS-RT stream with {interval}s interval")
        
        while True:
            try:
                feed = self.fetch_feed()
                
                if feed:
                    if self.feed_type == 'vehicle_positions':
                        data = self.parse_vehicle_positions(feed)
                    elif self.feed_type == 'trip_updates':
                        data = self.parse_trip_updates(feed)
                    else:
                        data = []
                    
                    if callback and data:
                        callback(data)
                
                time.sleep(interval)
                
            except KeyboardInterrupt:
                logger.info("Stopping GTFS-RT stream")
                break
            except Exception as e:
                logger.error(f"Error in stream loop: {e}")
                time.sleep(interval)


if __name__ == "__main__":
    # Example usage with simulated feed URL
    # Replace with actual BMTC GTFS-RT URL when available
    
    def print_vehicles(vehicles):
        print(f"\n=== Received {len(vehicles)} vehicles at {datetime.now()} ===")
        for v in vehicles[:3]:  # Print first 3
            print(f"Vehicle {v['vehicle_id']}: Route {v['route_id']}, "
                  f"Position: ({v['latitude']}, {v['longitude']})")
    
    # For testing, use a public GTFS-RT feed
    # Example: San Francisco Muni
    test_url = "https://gtfs.piemadd.com/test/vehicle_positions.pb"
    
    consumer = GTFSRealtimeConsumer(test_url, "vehicle_positions")
    consumer.stream_data(interval=10, callback=print_vehicles)

