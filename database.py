import os
import json
import sqlite3
from enum import Enum, auto

import pandas as pd

pd.set_option("display.float_format", "{:,.0f}".format)

import struct

from cmc_scraper import CoinMarketcapScraper


class By(Enum):
    ID = auto()
    Network = auto()


class Database:
    def __init__(self, log: bool = True) -> None:

        self.export_path = self._get_data_export_path()
        self.database_file = f"{self.export_path}\\crypto.db"
        self.conn = sqlite3.connect(self.database_file)
        self.cursor = self.conn.cursor()
        self.cmc = CoinMarketcapScraper(log=False)
        self.log = log

    def _get_data_export_path(self):
        try:
            internal_path = f"{os.getcwd()}\\config.json"
            with open(internal_path, "r") as file:
                data = json.load(file)
            return data["data_export_path"]
        except FileNotFoundError:
            external_path = f"{os.getcwd()}\\CoinMarketcapScraper\\config.json"
            with open(external_path, "r") as file:
                data = json.load(file)
            return data["data_export_path"]

    """
    ===================================================================
    Table Creation
    ===================================================================
    """

    def create_network_table(self):
        # Create Networks table
        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS Networks (
            NetworkID INTEGER PRIMARY KEY AUTOINCREMENT,
            NetworkName TEXT NOT NULL,
            NativeCurrency TEXT NOT NULL,
            ChainId TEXT NOT NULL
        )
        """
        )
        self.conn.commit()

    def create_token_table(self):
        # Create a table to store JSON data
        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS Tokens (
            TokenId INTEGER PRIMARY KEY AUTOINCREMENT,
            TokenSymbol TEXT,
            TokenSlug TEXT,
            NetworkAddresses TEXT,
            MaxSupply INTEGER, 
            InfiniteSupply BOOLEAN
        )
        """
        )
        self.conn.commit()

    def drop_token_table(self):
        with self.conn:
            self.cursor.execute(
                """
                DROP TABLE IF EXISTS Tokens
                """
            )

    """
    ===================================================================
    Network data
    ===================================================================
    """

    def _query_network_info_by_chain_id(self, chain_id: str) -> pd.Series:
        self.cursor.execute("""SELECT * FROM Networks WHERE ChainId = ?""", (chain_id,))
        try:
            results = self.cursor.fetchall()[0]
            df = pd.DataFrame(
                {
                    "name": [results[1]],
                    "native": [results[2]],
                    "chain_id": [results[3]],
                }
            ).set_index("chain_id")
            info = df.loc[str(chain_id)]
            return info
        except IndexError:
            if self.log:
                print(
                    f"[_query_network_info_by_chain_id()]: '{chain_id}' could not be found in table 'Networks'. "
                )
            return pd.Series()

    def _query_network_info_by_name(self, network_name: str) -> pd.Series:
        self.cursor.execute(
            """SELECT * FROM Networks WHERE NetworkName = ?""", (network_name,)
        )
        try:
            results = self.cursor.fetchall()[0]
            df = pd.DataFrame(
                {
                    "name": [results[1]],
                    "native": [results[2]],
                    "chain_id": [results[3]],
                }
            ).set_index("name")
            info = df.loc[network_name]

            return info
        except IndexError:
            if self.log:
                print(
                    f"[_query_network_info_by_name()]: '{network_name}' could not be found in table 'Networks'. "
                )
            return pd.Series()

    def get_network_info(self, network_name: str):
        info = self._query_network_info_by_name(network_name)
        return info

    def get_chain_id(self, network_name: str):
        info = self._query_network_info_by_name(network_name)
        try:
            chain_id = info["chain_id"]
            if self.log:
                print(
                    f"[get_chain_id()]: ChainId '{chain_id}' retrieved for '{network_name}'. "
                )
            return chain_id
        except KeyError:
            if self.log:
                print(
                    f"[get_chain_id()]: ChainId could not be found for network '{network_name}'. "
                )
            return None

    def get_native_currency(self, network_name: str):
        info = self._query_network_info(network_name)
        try:
            native_currency = info["native"]
            if self.log:
                print(
                    f"[get_native_currency()]: Native currency '{native_currency}' retrieved for '{network_name}'. "
                )
            return native_currency
        except KeyError:
            if self.log:
                print(
                    f"[get_native_currency()]: Native currency could not be found for network '{network_name}'. "
                )
            return None

    def get_all_networks(self) -> pd.DataFrame:
        self.cursor.execute("""SELECT * FROM Networks""")
        results = self.cursor.fetchall()
        df = pd.DataFrame()
        # Get column names from the cursor description
        column_names = [description[0] for description in self.cursor.description]
        # Create a DataFrame using the results and column names
        df = pd.DataFrame(results, columns=column_names)
        df.set_index("NetworkID", inplace=True)
        return df

    """
    ===================================================================
    Token Data
    ===================================================================
    """

    def _query_address(self, symbol: str):
        symbol = symbol.upper()
        self.cursor.execute(
            """
        SELECT NetworkAddresses
        FROM Tokens
        WHERE TokenSymbol = ?
        """,
            (symbol,),
        )
        result = self.cursor.fetchone()
        return result

    def _query_token_info(self, symbol: str):
        symbol = symbol.upper()

        self.cursor.execute("""SELECT * FROM Tokens WHERE TokenSymbol = ?""", (symbol,))
        try:
            result = self.cursor.fetchall()[0]
            df = pd.DataFrame(
                {
                    "TokenId": [result[0]],
                    "TokenSymbol": [result[1]],
                    "TokenSlug": [result[2]],
                    "NetworkAddresses": [result[3]],
                    "MaxSupply": [result[4]],
                    "InfiniteSupply": [result[5]],
                }
            ).set_index("TokenSymbol")

            token_info = df.loc[symbol]
            return token_info
        except IndexError as e:
            return pd.Series()

    def get_token_info(self, symbol: str):
        symbol = symbol.upper()
        token_info = self._query_token_info(symbol)

        if token_info.empty:
            self.insert_token_data(symbol)
            token_info = self._query_token_info(symbol)

        return token_info

    def get_token_addresses(self, symbol: str):
        token_info = self.get_token_info(symbol)
        if token_info.empty:
            return {}
        else:
            addresses = json.loads(token_info["NetworkAddresses"])
            return addresses

    def get_token_address(self, symbol: str, value: str, search_by: By):
        symbol = symbol.upper()
        addresses = self.get_token_addresses(symbol)
        if search_by == By.ID:
            info = self._query_network_info_by_chain_id(value)
            try:
                network = info["name"]
                address = addresses[network]
                return address
            except KeyError:
                return ""
        elif search_by == By.Network:
            try:
                address = addresses[value]
                return address
            except KeyError:
                return ""

    def insert_token_data(self, symbol: str):
        symbol = symbol.upper()
        token_exists = self.token_symbol_exists(symbol)
        try:
            if not token_exists:
                token_info = self.cmc._query_token_info(symbol)
                print(f"Token: {token_info}")
                token_address = self.cmc._query_token_address(symbol)
                # Convert the DataFrame to a dictionary
                network_addresses = token_address.T.squeeze().to_dict()
                network_addresses = json.dumps(network_addresses)
                with self.conn:
                    # Insert data into the table
                    self.cursor.execute(
                        """
                    INSERT INTO Tokens (TokenSymbol, TokenSlug, NetworkAddresses, MaxSupply, InfiniteSupply)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                        (
                            symbol.upper(),
                            token_info.loc[symbol, "slug"],
                            network_addresses,
                            token_info.loc[symbol, "max_supply"],
                            token_info.loc[symbol, "infinite_supply"],
                        ),
                    )

            else:
                if self.log:
                    print(
                        f"[Tokens] {symbol.upper()} records already in table 'Tokens'."
                    )
        except sqlite3.OperationalError:
            if self.log:
                print(f"[Tokens] Table Created")
            self.create_token_table()
            self.insert_token_data(symbol.upper())

    """
    ===================================================================
    Table Creation
    ===================================================================
    """

    """
    ===================================================================
    Element Exists
    ===================================================================
    """

    def token_symbol_exists(self, symbol: str):
        """
        Check if token symbols exists in "Tokens" table.

        Parameters
        ----------
        symbol : str
            Ticker symbol of the token to check.

        Returns: bool
            True if token exists in table, False if not.
        """
        try:
            self.cursor.execute(
                """
                SELECT TokenSlug 
                FROM Tokens
                WHERE TokenSymbol = ? 
            """,
                (symbol.upper(),),
            )
            try:
                result = self.cursor.fetchone()[0]
                return True
            except TypeError:
                return False
        except sqlite3.OperationalError:
            self.create_token_table()
            if self.log:
                print(f"[Tokens] Table Created")
            return False


if __name__ == "__main__":

    d = Database()
    network = "Arbitrum"

    info = d.get_network_info("Polygon")
    print(info)
