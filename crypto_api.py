import requests
import logging
from datetime import datetime
from app import db
from models import CryptoPrice

class CryptoAPI:
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.supported_coins = ["bitcoin", "ethereum", "tether"]
        
    def get_crypto_prices(self):
        """Fetch real-time crypto prices from CoinGecko API"""
        try:
            coins = ",".join(self.supported_coins)
            url = f"{self.base_url}/simple/price"
            params = {
                "ids": coins,
                "vs_currencies": "usd,inr",
                "include_24hr_change": "true",
                "include_market_cap": "true",
                "include_24hr_vol": "true"
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Update database with latest prices
            self._update_price_database(data)
            
            return data
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching crypto prices: {e}")
            return self._get_fallback_prices()
        except Exception as e:
            logging.error(f"Unexpected error in crypto API: {e}")
            return self._get_fallback_prices()
    
    def _update_price_database(self, data):
        """Update the database with latest crypto prices"""
        try:
            symbol_mapping = {
                "bitcoin": "BTC",
                "ethereum": "ETH", 
                "tether": "USDT"
            }
            
            for coin_id, coin_data in data.items():
                symbol = symbol_mapping.get(coin_id)
                if symbol:
                    price_record = CryptoPrice.query.filter_by(symbol=symbol).first()
                    
                    if not price_record:
                        price_record = CryptoPrice()
                        price_record.symbol = symbol
                        db.session.add(price_record)
                    
                    price_record.current_price_usd = coin_data.get("usd", 0)
                    price_record.current_price_inr = coin_data.get("inr", 0)
                    price_record.price_change_24h = coin_data.get("usd_24h_change", 0)
                    price_record.market_cap = coin_data.get("usd_market_cap", 0)
                    price_record.volume_24h = coin_data.get("usd_24h_vol", 0)
                    price_record.last_updated = datetime.utcnow()
            
            db.session.commit()
            
        except Exception as e:
            logging.error(f"Error updating price database: {e}")
            db.session.rollback()
    
    def _get_fallback_prices(self):
        """Return fallback prices if API fails"""
        return {
            "bitcoin": {
                "usd": 45000,
                "inr": 3742500,
                "usd_24h_change": 2.5,
                "usd_market_cap": 880000000000,
                "usd_24h_vol": 25000000000
            },
            "ethereum": {
                "usd": 3200,
                "inr": 266240,
                "usd_24h_change": 1.8,
                "usd_market_cap": 385000000000,
                "usd_24h_vol": 15000000000
            },
            "tether": {
                "usd": 1.00,
                "inr": 83.12,
                "usd_24h_change": 0.01,
                "usd_market_cap": 95000000000,
                "usd_24h_vol": 40000000000
            }
        }
    
    def get_historical_data(self, coin_id, days=7):
        """Get historical price data for charts"""
        try:
            url = f"{self.base_url}/coins/{coin_id}/market_chart"
            params = {
                "vs_currency": "usd",
                "days": days
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logging.error(f"Error fetching historical data: {e}")
            return {"prices": [], "market_caps": [], "total_volumes": []}
    
    def convert_currency(self, amount, from_currency, to_currency):
        """Convert between cryptocurrencies and fiat"""
        try:
            prices = self.get_crypto_prices()
            
            # Get current rates
            if from_currency == "USD" and to_currency == "INR":
                return amount * 83.12
            elif from_currency == "INR" and to_currency == "USD":
                return amount / 83.12
            
            # Crypto conversions
            coin_mapping = {"BTC": "bitcoin", "ETH": "ethereum", "USDT": "tether"}
            
            if from_currency in coin_mapping:
                coin_data = prices.get(coin_mapping[from_currency], {})
                if to_currency == "USD":
                    return amount * coin_data.get("usd", 0)
                elif to_currency == "INR":
                    return amount * coin_data.get("inr", 0)
            
            return 0
            
        except Exception as e:
            logging.error(f"Error converting currency: {e}")
            return 0

# Global instance
crypto_api = CryptoAPI()
