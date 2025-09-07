import { Restaurant, MenuItem, DeliveryLocation, Drone, DroneStatus, OrderStatus, Coordinates } from './types';

export const RESTAURANTS: Restaurant[] = [
  { id: 'rest-1', name: 'Campus Pizzeria', location: { lat: 16.459, lon: 80.506 } },
  { id: 'rest-2', name: 'University Grill', location: { lat: 16.465, lon: 80.509 } },
];

export const MENU_ITEMS: MenuItem[] = [
  { id: 'item-1', name: 'Margherita Pizza', price: 12.50, restaurantId: 'rest-1' },
  { id: 'item-2', name: 'Pepperoni Pizza', price: 14.00, restaurantId: 'rest-1' },
  { id: 'item-3', name: 'Veggie Burger', price: 10.00, restaurantId: 'rest-2' },
  { id: 'item-4', name: 'Chicken Wrap', price: 9.50, restaurantId: 'rest-2' },
];

const BLOCK_COORDINATES = {
    "A": { lat: 16.4619833645846, lon: 80.50799315633193 },
    "B": { lat: 16.460755182984183, lon: 80.50745167996868 },
    "C": { lat: 16.462577701714427, lon: 80.50755910043569 },
};

export const DELIVERY_LOCATIONS: DeliveryLocation[] = [
  { id: 'loc-a', name: 'Block A', location: BLOCK_COORDINATES.A },
  { id: 'loc-b', name: 'Block B', location: BLOCK_COORDINATES.B },
  { id: 'loc-c', name: 'Block C', location: BLOCK_COORDINATES.C },
];

const DRONE_HOME_1: Coordinates = { lat: 16.4585, lon: 80.5055 };
const DRONE_HOME_2: Coordinates = { lat: 16.4655, lon: 80.5095 };
const DRONE_HOME_3: Coordinates = { lat: 16.462, lon: 80.508 };


export const INITIAL_DRONES: Drone[] = [
  { id: 'D-01', model: 'Aero-1', status: DroneStatus.IDLE, battery: 98, location: DRONE_HOME_1, homeLocation: DRONE_HOME_1, isConnected: false, connectionString: 'udp:127.0.0.1:14550' },
  { id: 'D-02', model: 'Aero-1', status: DroneStatus.IDLE, battery: 100, location: DRONE_HOME_2, homeLocation: DRONE_HOME_2, isConnected: false, connectionString: 'udp:127.0.0.1:14551' },
  { id: 'D-03', model: 'Aero-2', status: DroneStatus.CHARGING, battery: 45, location: DRONE_HOME_3, homeLocation: DRONE_HOME_3, isConnected: false, connectionString: 'udp:127.0.0.1:14552' },
];

export const STATUS_COLORS: { [key in OrderStatus]: string } = {
    [OrderStatus.PLACED]: 'bg-blue-500',
    [OrderStatus.DECLINED]: 'bg-red-600',
    [OrderStatus.ACCEPTED]: 'bg-cyan-500',
    [OrderStatus.COOKING]: 'bg-yellow-500',
    [OrderStatus.READY_FOR_LAUNCH]: 'bg-purple-500',
    [OrderStatus.EN_ROUTE]: 'bg-indigo-500',
    [OrderStatus.DELIVERED]: 'bg-green-500',
    [OrderStatus.FAILED]: 'bg-red-800',
};

export const DRONE_STATUS_COLORS: { [key in DroneStatus]: string } = {
    [DroneStatus.IDLE]: 'bg-green-500',
    [DroneStatus.ON_MISSION]: 'bg-indigo-500',
    [DroneStatus.RETURNING_HOME]: 'bg-sky-500',
    [DroneStatus.CHARGING]: 'bg-yellow-500',
    [DroneStatus.MAINTENANCE]: 'bg-red-500',
};
