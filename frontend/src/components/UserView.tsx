import React, { useState, useContext, useMemo } from 'react';
import { AppContext } from '../context/AppContext';
import { MenuItem, CartItem, Order, OrderStatus, Restaurant, DeliveryLocation, Drone } from '../types';
import { MENU_ITEMS, DELIVERY_LOCATIONS, RESTAURANTS, STATUS_COLORS } from '../constants';
import Map from './Map';
import { PlusIcon, CheckIcon, DroneIcon } from './Icons';

const OrderStatusTracker: React.FC<{ order: Order }> = ({ order }) => {
    const statuses = Object.values(OrderStatus).filter(s => s !== OrderStatus.DECLINED && s !== OrderStatus.FAILED);
    const currentStatusIndex = statuses.findIndex(s => s === order.status);

    return (
        <div className="w-full">
            <div className="flex items-center justify-between">
                {statuses.map((status, index) => (
                    <React.Fragment key={status}>
                        <div className="flex flex-col items-center">
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center transition-all duration-300 ${index <= currentStatusIndex ? STATUS_COLORS[status] : 'bg-gray-600'}`}>
                                {index < currentStatusIndex ? <CheckIcon/> : (
                                    <div className={`w-3 h-3 rounded-full ${index === currentStatusIndex ? 'bg-white animate-ping' : 'bg-gray-400'}`}></div>
                                )}
                            </div>
                            <p className={`mt-2 text-xs text-center font-semibold ${index <= currentStatusIndex ? 'text-white' : 'text-gray-400'}`}>{status}</p>
                        </div>
                        {index < statuses.length - 1 && (
                            <div className={`flex-1 h-1 mx-2 transition-all duration-300 ${index < currentStatusIndex ? 'bg-green-500' : 'bg-gray-600'}`}></div>
                        )}
                    </React.Fragment>
                ))}
            </div>
            {order.status === OrderStatus.DECLINED && <p className="text-center text-red-500 font-bold mt-4">Order was declined by the restaurant.</p>}
            {order.status === OrderStatus.FAILED && <p className="text-center text-red-500 font-bold mt-4">Order failed (e.g., no available drones or manual RTL).</p>}
        </div>
    );
};


const UserView: React.FC = () => {
    const context = useContext(AppContext);
    const [selectedRestaurantId, setSelectedRestaurantId] = useState<string>(RESTAURANTS[0].id);
    const [cart, setCart] = useState<CartItem[]>([]);
    const [deliveryLocationId, setDeliveryLocationId] = useState<string>(DELIVERY_LOCATIONS[0].id);

    const activeOrder = useMemo(() => 
        context?.orders.find(o => o.user === 'Student-1' && o.status !== OrderStatus.DELIVERED && o.status !== OrderStatus.DECLINED && o.status !== OrderStatus.FAILED), 
    [context?.orders]);

    const handleAddToCart = (item: MenuItem) => {
        setCart(prevCart => {
            const existingItem = prevCart.find(cartItem => cartItem.id === item.id);
            if (existingItem) {
                return prevCart.map(cartItem =>
                    cartItem.id === item.id ? { ...cartItem, quantity: cartItem.quantity + 1 } : cartItem
                );
            }
            return [...prevCart, { ...item, quantity: 1 }];
        });
    };
    
    const handleRestaurantChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        setSelectedRestaurantId(e.target.value);
        setCart([]); // Clear cart when changing restaurant
    };

    const cartTotal = useMemo(() => cart.reduce((sum, item) => sum + item.price * item.quantity, 0), [cart]);

    const handlePlaceOrder = () => {
        if (cart.length === 0 || !context) return;
        context.placeOrder(cart, cartTotal, deliveryLocationId, selectedRestaurantId);
        setCart([]);
    };

    const menuForSelectedRestaurant = useMemo(() => MENU_ITEMS.filter(item => item.restaurantId === selectedRestaurantId), [selectedRestaurantId]);

    // For the map
    const droneForOrder = context?.drones.find(d => d.id === activeOrder?.droneId);
    const restaurantForOrder = RESTAURANTS.find(r => r.id === activeOrder?.restaurantId);
    const locationForOrder = DELIVERY_LOCATIONS.find(l => l.id === activeOrder?.deliveryLocationId);

    return (
      <>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 p-8 max-w-7xl mx-auto">
            {/* Order Placement Section */}
            <div className={`bg-gray-800 p-6 rounded-xl shadow-2xl transition-opacity duration-500 ${activeOrder ? 'opacity-30 pointer-events-none' : 'opacity-100'}`}>
                <h2 className="text-3xl font-bold mb-6 text-cyan-300 border-b-2 border-cyan-300/20 pb-2">Place an Order</h2>
                
                <div className="mb-4">
                    <label htmlFor="restaurant-select" className="block text-sm font-medium text-gray-300 mb-1">Restaurant</label>
                    <select id="restaurant-select" value={selectedRestaurantId} onChange={handleRestaurantChange} className="w-full bg-gray-700 border border-gray-600 rounded-md py-2 px-3 focus:ring-cyan-500 focus:border-cyan-500">
                        {RESTAURANTS.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
                    </select>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-h-60 overflow-y-auto pr-2">
                    {menuForSelectedRestaurant.map(item => (
                        <div key={item.id} className="bg-gray-700/50 p-3 rounded-lg flex justify-between items-center">
                            <div>
                                <p className="font-semibold">{item.name}</p>
                                <p className="text-sm text-gray-400">${item.price.toFixed(2)}</p>
                            </div>
                            <button onClick={() => handleAddToCart(item)} className="bg-cyan-500 hover:bg-cyan-600 text-white rounded-full p-2 transition-transform duration-200 hover:scale-110">
                                <PlusIcon />
                            </button>
                        </div>
                    ))}
                </div>

                <div className="mt-6 border-t border-gray-700 pt-4">
                    <h3 className="font-bold text-lg">Your Cart</h3>
                    {cart.length === 0 ? (
                        <p className="text-gray-400 mt-2">Your cart is empty.</p>
                    ) : (
                        <ul className="mt-2 space-y-2 max-h-32 overflow-y-auto">
                            {cart.map(item => (
                                <li key={item.id} className="flex justify-between items-center text-sm">
                                    <span>{item.name} x {item.quantity}</span>
                                    <span>${(item.price * item.quantity).toFixed(2)}</span>
                                </li>
                            ))}
                        </ul>
                    )}
                    <p className="text-right font-bold text-xl mt-4">Total: ${cartTotal.toFixed(2)}</p>
                </div>
                
                <div className="mt-4">
                    <label htmlFor="location-select" className="block text-sm font-medium text-gray-300 mb-1">Delivery Location</label>
                    <select id="location-select" value={deliveryLocationId} onChange={(e) => setDeliveryLocationId(e.target.value)} className="w-full bg-gray-700 border border-gray-600 rounded-md py-2 px-3 focus:ring-cyan-500 focus:border-cyan-500">
                        {DELIVERY_LOCATIONS.map(loc => <option key={loc.id} value={loc.id}>{loc.name}</option>)}
                    </select>
                </div>

                <button 
                    onClick={handlePlaceOrder} 
                    disabled={cart.length === 0}
                    className="w-full mt-6 bg-green-500 hover:bg-green-600 text-white font-bold py-3 rounded-lg transition disabled:bg-gray-500 disabled:cursor-not-allowed">
                    Place Order
                </button>
            </div>

            {/* Order Tracking Section */}
            <div className="bg-gray-800 p-6 rounded-xl shadow-2xl flex flex-col items-center">
                {activeOrder ? (
                    <div className='w-full flex flex-col h-full'>
                        <h2 className="text-3xl font-bold mb-6 text-cyan-300 border-b-2 border-cyan-300/20 pb-2">Live Mission Tracking</h2>
                        <OrderStatusTracker order={activeOrder} />
                        {(activeOrder.status === OrderStatus.EN_ROUTE || activeOrder.status === OrderStatus.DELIVERED) && droneForOrder && restaurantForOrder && locationForOrder ? (
                            <div className="mt-6 w-full flex-grow min-h-[300px]">
                                <Map 
                                    dronesToDisplay={[droneForOrder]}
                                    restaurantsToDisplay={[restaurantForOrder]}
                                    locationsToDisplay={[locationForOrder]}
                                    mapStyle='satellite'
                                />
                            </div>
                        ) : (
                           <div className="flex-grow flex items-center justify-center text-center text-gray-400">
                               <p>Map will appear here once drone is launched.</p>
                           </div>
                        )}
                    </div>
                ) : (
                    <div className="text-center my-auto">
                        <h2 className="text-2xl font-bold text-gray-400">Your order status will appear here.</h2>
                        <p className="text-gray-500 mt-2">Place an order to begin tracking.</p>
                    </div>
                )}
            </div>
        </div>
      </>
    );
};

export default UserView;