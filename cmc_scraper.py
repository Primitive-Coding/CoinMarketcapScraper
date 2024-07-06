import os
import json
import requests

from web3 import Web3

from dotenv import load_dotenv

load_dotenv()

import pandas as pd

pd.set_option("display.float_format", "{:.0f}".format)


# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    StaleElementReferenceException,
)

import logging

# Suppress logging from Selenium and other related modules
logging.getLogger("selenium").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("http").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)


chain_ids = {
    "Arbitrum": 42161,
    "BNB Smart Chain (BEP20)": 56,
    "Optimism": 10,
    "Polygon": 137,
    "Polygon zkEVM": 1101,
}


class CoinMarketcapScraper:
    def __init__(self, log: bool = True) -> None:
        self.key = os.getenv("COINMARKETCAP_KEY")
        self.base_url = "https://pro-api.coinmarketcap.com"
        self.export_path = self._get_data_export_path()
        os.makedirs(self.export_path, exist_ok=True)
        self.log = log

        # Paths to files
        self.chain_id_path = f"{self.export_path}\\chain_id.csv"
        self.token_address_path = f"{self.export_path}\\token_address.csv"

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

    """-----------------------------------"""
    """----------------------------------- Browser Operations -----------------------------------"""

    def _get_chrome_driver_path(self):
        try:
            internal_path = f"{os.getcwd()}\\config.json"
            with open(internal_path, "r") as file:
                data = json.load(file)
            return data["chrome_driver_path"]
        except FileNotFoundError:
            external_path = f"{os.getcwd()}\\CoinMarketcapScraper\\config.json"
            with open(external_path, "r") as file:
                data = json.load(file)
            return data["chrome_driver_path"]

    def _create_browser(self, url=None):
        """
        :param url: The website to visit.
        :return: None
        """
        service = Service(executable_path=self.chrome_driver_path)
        self.browser = webdriver.Chrome(service=service, options=self.chrome_options)
        # Default browser route
        if url == None:
            self.browser.get(url=self.sec_annual_url)
        # External browser route
        else:
            self.browser.get(url=url)

    def _clean_close(self) -> None:
        self.browser.close()
        self.browser.quit()

    def _read_data(
        self, xpath: str, wait: bool = False, _wait_time: int = 5, tag: str = ""
    ) -> str:
        """
        :param xpath: Path to the web element.
        :param wait: Boolean to determine if selenium should wait until the element is located.
        :param wait_time: Integer that represents how many seconds selenium should wait, if wait is True.
        :return: (str) Text of the element.
        """

        if wait:
            try:
                data = (
                    WebDriverWait(self.browser, _wait_time)
                    .until(EC.presence_of_element_located((By.XPATH, xpath)))
                    .text
                )
            except TimeoutException:
                print(f"[Failed Xpath] {xpath}")
                if tag != "":
                    print(f"[Tag]: {tag}")
                raise NoSuchElementException("Element not found")
            except NoSuchElementException:
                print(f"[Failed Xpath] {xpath}")
                return "N\A"
        else:
            try:
                data = self.browser.find_element("xpath", xpath).text
            except NoSuchElementException:
                data = "N\A"
        # Return the text of the element found.
        return data

    def _click_button(
        self,
        xpath: str,
        wait: bool = False,
        _wait_time: int = 5,
        scroll: bool = False,
        tag: str = "",
    ) -> None:
        """
        :param xpath: Path to the web element.
        :param wait: Boolean to determine if selenium should wait until the element is located.
        :param wait_time: Integer that represents how many seconds selenium should wait, if wait is True.
        :return: None. Because this function clicks the button but does not return any information about the button or any related web elements.
        """

        if wait:
            try:
                element = WebDriverWait(self.browser, _wait_time).until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )
                # If the webdriver needs to scroll before clicking the element.
                if scroll:
                    self.browser.execute_script("arguments[0].click();", element)
                element.click()
            except TimeoutException:
                print(f"[Failed Xpath] {xpath}")
                if tag != "":
                    print(f"[Tag]: {tag}")
                raise NoSuchElementException("Element not found")
        else:
            element = self.browser.find_element("xpath", xpath)
            if scroll:
                self.browser.execute_script("arguments[0].click();", element)
            element.click()

    """--------------------------------------------------------------------------- Token Info ---------------------------------------------------------------------------"""

    def get_token_info(self, ticker: str):
        """
        Get the token info.
            - Attempts to get locally first.
            - If not found locally, will query from 'Coinmarketcap' API.

        Parameters
        ----------
        ticker : str
            Ticker symbol of the token.

        Returns
        -------
        pd.Series
            Series containing token information.
        """
        path = f"{self.export_path}\\token_info.csv"
        ticker = ticker.upper()
        try:
            df = pd.read_csv(path)
            df.rename(columns={"Unnamed: 0": "symbol"}, inplace=True)
            df.set_index("symbol", inplace=True)
            try:
                data = df.loc[ticker]
                return data
            except KeyError:
                new_df = self._query_token_info(ticker)
                new_data = new_df.loc[ticker]
                df.loc[ticker] = new_data
                df.to_csv(path)
                return new_data
        except FileNotFoundError:
            df = self._query_token_info(ticker)
            df.to_csv(path)
            data = df.loc[ticker]
            return data

    def _query_token_info(self, ticker: str):
        url = f"{self.base_url}/v1/cryptocurrency/quotes/latest"
        ticker = ticker.upper()
        params = self._get_request_params(ticker)

        # Make the API request
        response = requests.get(
            url, headers=params["headers"], params=params["parameters"]
        )

        # Check if the request was successful
        if response.status_code == 200:
            data = response.json()
            token_data = data["data"][ticker]

            data = {
                "id": token_data["id"],
                "name": token_data["name"],
                "slug": token_data["slug"],
                "max_supply": token_data["max_supply"],
                "infinite_supply": token_data["infinite_supply"],
            }
            df = pd.DataFrame(columns=list(data.keys()))
            df.loc[ticker] = data
            if self.log:
                print(f"[TokenInfo] Info queried from Coinmarketcap.")
            return df

        else:
            print("ERROR")

    """--------------------------------------------------------------------------- Token Address ---------------------------------------------------------------------------"""

    def get_token_address(self, ticker, chain_id):
        path = f"{self.export_path}\\token_address.csv"
        try:
            df = pd.read_csv(path)
            df.rename(columns={"Unnamed: 0": "ticker"}, inplace=True)
            df.set_index("ticker", inplace=True)
            platform = self.get_network_name(chain_id)
            try:
                address = df.loc[ticker, platform]
                return address
            except KeyError:
                base_cols = self.get_supported_platforms()
                new_df = self._query_token_address(ticker)

                merged_df = self._merge_dataframes(df, new_df)
                merged_df.to_csv(self.token_address_path)

                if self.log:
                    new_cols = new_df.columns
                    untracked_networks = [
                        item for item in new_cols if item not in base_cols
                    ]

                    print(
                        f"Untracked Networks: {untracked_networks}\nAdd these networks with 'cmc.add_chain_id(network, chain_id)'"
                    )

        except FileNotFoundError:
            df = self._query_token_address(ticker)
            df.to_csv(path)
            platform = self.get_network_name(chain_id)
            address = df.loc[ticker, platform]
            return address

    def _query_token_address(self, ticker):
        ticker = ticker.upper()
        url = f"{self.base_url}/v1/cryptocurrency/info"
        params = self._get_request_params(ticker)
        # Make the API request
        response = requests.get(
            url, headers=params["headers"], params=params["parameters"]
        )
        # Dataframe to hold token data.
        df = pd.DataFrame()
        # Check if the request was successful
        if response.status_code == 200:
            data = response.json()
            data = data["data"][ticker]["contract_address"]

            for d in data:
                contract_address = d["contract_address"]
                platform = d["platform"]["name"]
                try:
                    contract_address = Web3.to_checksum_address(contract_address)
                except ValueError:
                    pass
                df.loc[ticker, platform] = contract_address
            if self.log:
                print(f"[TokenAddress] Address queried from Coinmarketcap.")
            return df

    def update_token_address(self, ticker: str):
        ticker = ticker.upper()

        df = pd.read_csv(self.token_address_path)
        df.set_index("ticker", inplace=True)
        new_df = self._query_token_address(ticker)
        merged_df = self._merge_dataframes(df, new_df)
        print(f"Merged: {merged_df}")
        # merged_df.to_csv()
        # print(df)

    def delete_token_address(self, ticker: str, chain_id):
        """
        Delete token address from local csv file.

        Parameters
        ----------
        ticker : str
            Ticker of the token to delete.
        chain_id : _type_
            Id of the network to delete the address for.
        """
        df = self.read_local_address_file()
        print(f"DF: {df}")

    def read_local_address_file(self) -> pd.DataFrame:
        """
        Read the address information from the local csv file.

        Returns
        -------
        pd.DataFrame
            Dataframe containing address information.
        """
        df = pd.read_csv(self.token_address_path)
        df.set_index("ticker", inplace=True)
        return df

    def _get_request_params(self, ticker: str):
        # Parameters for the API request
        parameters = {
            "symbol": ticker,  # Symbol for Ethereum
        }
        # Headers for the API request
        headers = {
            "Accepts": "application/json",
            "X-CMC_PRO_API_KEY": self.key,
        }

        return {"parameters": parameters, "headers": headers}

    """--------------------------------------------------------------------------- Chain Ids ---------------------------------------------------------------------------"""

    def add_chain_id(self, network_name: str, chain_id: int):
        path = f"{self.export_path}\\chain_id.csv"
        try:
            df = pd.read_csv(path)
            df.rename(columns={"Unnamed: 0": "name"}, inplace=True)
            df.set_index("name", inplace=True)
            try:
                # If no errors occur up to this point, the data is already in the file and nothing further needs to be done.
                _id = df.loc[network_name, "id"]
                if self.log:
                    print(
                        f"[add_chain_id()] '{network_name}' already saved locally with ID '{chain_id}'"
                    )
            except KeyError:
                df.loc[network_name, "id"] = chain_id
                df.to_csv(path)
                if self.log:
                    print(
                        f"[add_chain_id()] '{network_name}' was added with ID '{chain_id}'"
                    )

        except FileNotFoundError:
            df = pd.DataFrame()
            df.loc[network_name, "id"] = chain_id
            df.to_csv(path)
            if self.log:
                print(
                    f"[add_chain_id()] '{network_name}' was added with ID '{chain_id}'"
                )

    def update_chain_id(self, network_name: str, chain_id: str):
        df = pd.read_csv(self.chain_id_path)
        df.set_index("name", inplace=True)
        prev_value = df.loc[network_name, "id"]
        df.loc[network_name, "id"] = chain_id
        df.to_csv(self.chain_id_path)
        if self.log:
            print(
                f"[update_chain_id()] '{network_name}' was updated from '{prev_value}' to '{chain_id}'."
            )

    def get_chain_id(self, network_name: str) -> int:
        path = f"{self.export_path}\\chain_id.csv"

        try:
            df = pd.read_csv(path)
            df.set_index("name", inplace=True)
            _id = df.loc[network_name, "id"]
            return _id
        except FileNotFoundError:
            pass

    def get_network_name(self, chain_id) -> str:
        """
        Get the name of a platform based on the chain id.
        Naming scheme is based on Coinmarketcap API.

        Parameters
        ----------
        chain_id : int
            Id of the blockchain network.

        Returns
        -------
        str
            Name of the platform.
        """
        try:
            df = pd.read_csv(self.chain_id_path)
            _id = df.loc[df["id"] == str(chain_id)]
            return _id["name"].values[0]
        except FileNotFoundError:
            pass

    def delete_chain_id(self, value, by: str = "id"):
        """
        Delete the chain id from the local csv file.

        Parameters
        ----------
        value : _type_
            Value used to search dataframe, and delete rows based on matchin values.
        by : str, optional
            Determine what to element to delete the id "by".
            For example, if you want to delete the "id" by the name of the blockchain network, set 'by="name"'
            If you want to delte the "id" by the "id" of the network, set 'by="id"'.
            , by default "id"
        """
        by = by.lower()
        path = f"{self.export_path}\\chain_id.csv"
        try:
            df = pd.read_csv(path)
            df.rename(columns={"Unnamed: 0": "name"}, inplace=True)
            df.set_index("name", inplace=True)

            if by == "id":
                value = int(value)
                # Identify the index of the row(s) where 'id' column equals 'chain_id'
                indices_to_delete = df.index[df["id"] == value].tolist()
                try:
                    df.drop(indices_to_delete[0], inplace=True)
                    df.to_csv(path)
                except IndexError:
                    print(
                        f"[delete_chain_id()]: [{value}] could not be found in file: 'chain_id.csv'."
                    )

            elif by == "name":
                try:
                    df.drop(value, inplace=True)
                    df.to_csv(path)
                except KeyError:
                    print(
                        f"[delete_chain_id()]: [{value}] could not be found in file: 'chain_id.csv'."
                    )

        except FileNotFoundError:
            print(f"[delete_chain_id()] Could not find 'chain_id.csv' file. ")

    def _clean_chain_ids(self):
        df = pd.read_csv(self.chain_id_path)
        df.set_index("name", inplace=True)

        for i in df.iterrows():
            name, id = i
            id = id["id"]
            if "." in id:
                id = id.split(".")[0]
            df.loc[name, "id"] = id
        df.to_csv(self.chain_id_path)

    def get_supported_chains(self):
        path = f"{self.export_path}\\chain_id.csv"

        try:
            df = pd.read_csv(path)
            df.rename(columns={"Unnamed: 0": "name"}, inplace=True)
            if not df.empty:
                sorted_df = df.sort_values(by="name", ascending=True)
                sorted_df.set_index("name", inplace=True)
                return sorted_df
            else:
                print(f"[get_supported_chains()] No supported chains.")
        except FileNotFoundError:
            print(f"[get_supported_chains()] Could not find 'chain_id.csv' file. ")

    def get_supported_platforms(self):
        path = f"{self.export_path}\\chain_id.csv"

        try:
            df = pd.read_csv(path)
            df.rename(columns={"Unnamed: 0": "name"}, inplace=True)
            if not df.empty:
                sorted_df = df.sort_values(by="name", ascending=True)
                return sorted_df["name"].to_list()
            else:
                print(f"[get_supported_platforms()] No supported chains.")
        except FileNotFoundError:
            print(f"[get_supported_platforms()] Could not find 'chain_id.csv' file. ")

    def read_local_chain_id_file(self):

        df = pd.read_csv(self.chain_id_path)
        df.set_index("name", inplace=True)
        return df

    def get_untracked_networks(self) -> list:

        address_df = self.read_local_address_file()
        chain_id_df = self.read_local_chain_id_file()
        chain_ids = chain_id_df.index.to_list()
        untracked_networks = [
            item for item in address_df.columns if item not in chain_ids
        ]
        return untracked_networks

    """--------------------------------------------------------------------------- Merging Data ---------------------------------------------------------------------------"""

    def _merge_dataframes(
        self, base_df: pd.DataFrame, alt_df: pd.DataFrame
    ) -> pd.DataFrame:
        for i in alt_df.iterrows():
            index, value = i
            value_index = value.index.to_list()

            for vi in value_index:
                base_df.loc[index, vi] = alt_df.loc[index, vi]

        return base_df

    def _merge_lists(self, base_list: list, alt_list: list) -> list:
        """
        Combine the lists in the function parameters, and avoid merging duplicate elements.

        Example:
        base_list = [1, 2, 3]
        alt_list = [3, 4, 5]
        return [1, 2, 3, 4, 5]

        Parameters
        ----------
        base_list : list
            List used as the source for operations.
        alt_list : list
            List used to add to 'base_list'.

        Returns
        -------
        list
            List containing elements from both list, while avoiding duplicates.
        """
        combined_list = []
        seen = set()

        # Add elements from the first list
        for item in base_list:
            if item not in seen:
                combined_list.append(item)
                seen.add(item)
        # Add elements from the second list
        for item in alt_list:
            if item not in seen:
                combined_list.append(item)
                seen.add(item)
        return combined_list

    def _get_list_difference(self, base_list: list, alt_list: list) -> list:
        """
        Find elements that are in 'alt_list' but not in 'base_list'. Return the unmatched elements.

        Example:
        base_list = ["A", "B", "C"]
        alt_list = ["A", "B", "D"]
        return ["D"]

        Parameters
        ----------
        base_list : list
            Base list used for comparison.
        alt_list : list
            List used to compare against 'base_list'.

        Returns
        -------
        list
            List of elements that appear in 'alt_list' but not 'base_list'.

        """
        different_elements = [item for item in alt_list if item not in base_list]
        return different_elements


if __name__ == "__main__":

    cmc = CoinMarketcapScraper()

    # cmc.read_local_address_file()
    # cmc.add_chain_id("Stacks", 78225)
    # u = cmc.get_untracked_networks()
    # print(f"U: {u}")
    # chain_id = cmc.get_chain_id("Merlin")
    # print(chain_id)
    # cmc.delete_token_address("WBTC", )
    # cmc.get_supported_chains()
    # cmc.add_chain_id("Terra Classic", "columbus-5")
    # address = cmc.get_token_address("WBTC", 1)
    # print(f"Address: {address}")
    # address = cmc.get_token_address("USDC", 1)
    # cmc.update_token_address("WBTC")
    # print(f"Address: {address}")
    # cmc.update_chain_id("Injective", "injective-1")
    # file_address = pd.read_csv(cmc.token_address_path)
    # file_address.rename(columns={"Unnamed: 0": "symbol"}, inplace=True)
    # file_address.set_index("symbol", inplace=True)
    # print(f"File: {file_address}")
    # token_address = cmc._query_token_address("USDC")
    # print(f"Token: {token_address}")

    # merged = cmc._merge_dataframes(file_address, token_address)

    # print(f"Merged: {merged}")
