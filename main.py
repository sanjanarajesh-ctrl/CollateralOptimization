import pandas as pd
import numpy as np
import yfinance as yf
from scipy.optimize import linprog
import matplotlib.pyplot as plt
import json
import os


class CollateralAsset:
    """Represents a single collateral asset."""

    def __init__(self, name, asset_type, market_value, haircut, eligibility):
        self.name = name
        self.asset_type = asset_type
        self.market_value = market_value
        self.haircut = haircut
        self.eligibility = eligibility
        self.allocation = 0

    def to_dict(self):
        return {
            "name": self.name,
            "asset_type": self.asset_type,
            "market_value": self.market_value,
            "haircut": self.haircut,
            "eligibility": self.eligibility,
            "allocation": self.allocation
        }


class CollateralOptimizer:
    """Handles collateral optimization using linear programming."""

    def __init__(self, assets):
        self.assets = assets
        self.df = pd.DataFrame([asset.to_dict() for asset in assets])

    """def optimize(self, margin_call):
        market_values = self.df['market_value'].values
        haircuts = self.df['haircut'].values
        eligibility = self.df['eligibility'].values

        c = market_values * haircuts  # Objective function: minimize haircut loss
        A_ub = - (market_values * (1 - haircuts) * eligibility)
        b_ub = -margin_call

        result = linprog(c, A_ub=A_ub.reshape(1, -1), b_ub=b_ub, bounds=(0, None))

        if result.success:
            self.df['allocation'] = result.x
            self.df['allocated_value'] = self.df['allocation'] * self.df['market_value']
            self.df['post_haircut_value'] = self.df['allocated_value'] * (1 - self.df['haircut'])
            return self.df
        else:
            raise ValueError("Optimization failed: " + result.message)"""

    def optimize(self, margin_call):
        market_values = self.df['market_value'].values
        haircuts = self.df['haircut'].values
        eligibility = self.df['eligibility'].astype(int).values

        c = market_values * haircuts  # Minimize haircut losses
        A_ub = - (market_values * (1 - haircuts) * eligibility)  # Must meet margin call
        b_ub = -margin_call

        # Diversification Constraints
        max_alloc_per_asset = margin_call * 0.25  # No single asset > 25% of total
        min_alloc_per_asset = margin_call * 0.05  # Ensure at least 5% per asset

        A_div_max = np.eye(len(market_values))
        b_div_max = np.full(len(market_values), max_alloc_per_asset)

        A_div_min = -np.eye(len(market_values))
        b_div_min = -np.full(len(market_values), min_alloc_per_asset)

        # Ensure at least 5 different assets are used
        A_min_assets = np.ones((1, len(market_values)))
        b_min_assets = np.array([5])

        # Solve optimization with multiple constraints
        result = linprog(c, A_ub=np.vstack([A_ub.reshape(1, -1), A_div_max, A_div_min, -A_min_assets]),
                         b_ub=np.hstack([b_ub, b_div_max, b_div_min, -b_min_assets]), bounds=(0, None))

        if result.success:
            self.df['allocation'] = result.x
            self.df['allocated_value'] = self.df['allocation'] * self.df['market_value']
            self.df['post_haircut_value'] = self.df['allocated_value'] * (1 - self.df['haircut'])
            return self.df
        else:
            raise ValueError("Optimization failed: " + result.message)

    def save_to_csv(self, filename="collateral_data.csv"):
        self.df.to_csv(filename, index=False)

    def save_to_json(self, filename="collateral_data.json"):
        with open(filename, "w") as f:
            json.dump(self.df.to_dict(orient="records"), f, indent=4)

    def plot_allocation(self):
        plt.figure(figsize=(10, 6))
        plt.bar(self.df['name'], self.df['allocated_value'])
        plt.xlabel("Assets")
        plt.ylabel("Allocated Value")
        plt.title("Collateral Allocation")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.show()


# Fetch real market data using yfinance with error handling
"""def fetch_market_data(tickers):
    try:
        data = yf.download(tickers, period="1d")['Close']
        return data.to_dict()
    except Exception as e:
        print(f"Failed to fetch market data: {e}")
        return {}"""

# Fetch real market data using yfinance with improved error handling
def fetch_market_data(tickers):
    try:
        data = yf.download(tickers, period="1d")['Close']
        if isinstance(data, pd.Series):  # Single ticker case
            return data.dropna().to_dict()
        elif isinstance(data, pd.DataFrame):  # Multiple tickers
            return data.iloc[-1].dropna().to_dict()  # Get latest available prices
        else:
            raise ValueError("Unexpected data format from yfinance.")
    except Exception as e:
        print(f"Error fetching market data: {e}")
        return {}



# Define real-world collateral assets
def get_real_collateral_assets():
    tickers = {
        'Cash': ['USD=X'],
        'Government Bonds': ['TLT', 'IEF', 'SHY'],
        'Corporate Bonds': ['LQD', 'AGG'],
        'Equities': ['AAPL', 'MSFT', 'JPM', 'GS', 'SPY', 'QQQ']
    }

    market_prices = fetch_market_data(sum(tickers.values(), []))
    assets = []

    for asset_type, symbols in tickers.items():
        for symbol in symbols:
            market_value = market_prices.get(symbol, None)

            if market_value is None:
                print(f"Warning: Missing market data for {symbol}. Assigning default value.")
                market_value = np.random.uniform(10000, 500000)

            haircut = {
                'Cash': 0.00,
                'Government Bonds': np.random.uniform(0.01, 0.05),
                'Corporate Bonds': np.random.uniform(0.05, 0.15),
                'Equities': np.random.uniform(0.15, 0.25)
            }[asset_type]
            eligibility = np.random.choice([True, False])
            assets.append(CollateralAsset(symbol, asset_type, market_value, haircut, eligibility))

    return assets


# Example usage
if __name__ == "__main__":
    margin_call = float(input("Enter the margin call amount: "))
    assets = get_real_collateral_assets()
    optimizer = CollateralOptimizer(assets)
    optimized_df = optimizer.optimize(margin_call)

    optimizer.save_to_csv()
    optimizer.save_to_json()
    optimizer.plot_allocation()
