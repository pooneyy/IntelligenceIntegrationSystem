import os
import json
import time
import logging
import threading
from typing import Dict, List

from Tools.OpenAIClient import OpenAICompatibleAPI
from Tools.AiServiceBalanceQuery import get_siliconflow_balance

logger = logging.getLogger(__name__)


class SiliconFlowServiceRotator:
    """
    A service for rotating Silicon Flow API keys based on balance thresholds.
    Automatically manages key validity, balance checking, and key rotation.
    """

    def __init__(self,
                 ai_client: OpenAICompatibleAPI,
                 keys_file: str,
                 threshold: float = 0.2,
                 check_all_balance: bool = True):
        """
        Initialize the key rotator.

        Args:
            ai_client: OpenAI compatible API client instance
            keys_file: Path to file containing API keys (one per line)
            threshold: Balance threshold for key rotation (default: 0.1 USD)
            check_all_balance: Whether to check all keys' balances on startup
        """
        self.ai_client = ai_client
        self.keys_file = keys_file
        self.threshold = threshold
        self.check_all_balance = check_all_balance

        # Key database structure: {key: {'balance': float, 'last_used': timestamp, 'status': str}}
        self.keys_data = {}
        self.current_key = ''
        self.key_record_file = 'key_record.json'
        self.lock = threading.Lock()  # For thread-safe operations
        self.running = False

        # Load keys and initialize service
        self._load_keys()
        self._initialize_current_key()

    def _load_keys(self):
        """
        Load keys from key_record.json and the keys file.
        Merge keys from both sources and maintain key status information.
        """
        # Load existing key records from JSON file
        if os.path.exists(self.key_record_file):
            try:
                with open(self.key_record_file, 'r') as f:
                    self.keys_data = json.load(f)
                logger.info(f"Loaded {len(self.keys_data)} keys from key record")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load key record: {e}, starting fresh")
                self.keys_data = {}
            except Exception as e:
                logger.error(f'Unexpected error when loading {self.key_record_file}')
                logger.error(str(e))

        # Load keys from text file and merge with existing records
        has_update = False
        if os.path.exists(self.keys_file):
            try:
                with open(self.keys_file, 'r') as f:
                    for line in f:
                        key = line.strip()
                        if key and key not in self.keys_data:
                            self.keys_data[key] = {
                                'balance': -1.0,  # Unknown balance
                                'last_used': 0,
                                'status': 'unknown'  # unknown, valid, invalid, error
                            }
                            has_update = True
                            logger.info(f"Added new key from file: {key[:8]}...")
            except Exception as e:
                logger.error(f'Unexpected error when loading {self.keys_file}')
                logger.error(str(e))

        if has_update:
            self._save_key_records()

    def _initialize_current_key(self):
        """Initialize the current key with the first valid key available."""
        valid_keys = self._get_valid_keys()
        if valid_keys:
            self.current_key = valid_keys[0]
            self._change_api_key(self.current_key)
            logger.info(f"Initialized with key: {self.current_key[:8]}...")
        else:
            logger.warning("No valid keys available during initialization")

    def check_update_key(self):
        """
        Check current key balance and rotate if necessary.
        Implements retry logic to avoid discarding keys due to network issues [5](@ref).
        """
        if not self.current_key:
            logger.warning("No current key set")
            return False

        balance = self._fetch_balance_with_retry(self.current_key)
        if balance < 0:
            logger.error(f"Failed to fetch balance for current key")
            return False

        logger.info(f"Current key balance: ${balance:.4f}")

        # Update key record
        with self.lock:
            self.keys_data[self.current_key]['balance'] = balance
            self.keys_data[self.current_key]['last_used'] = time.time()

            if balance < self.threshold:
                logger.warning(f"Key balance below threshold (${balance:.4f} < ${self.threshold}), rotating...")
                self.keys_data[self.current_key]['status'] = 'invalid'
                return self._rotate_to_next_key()
            else:
                self.keys_data[self.current_key]['status'] = 'valid'

        self._save_key_records()
        return True

    def _fetch_balance_with_retry(self, key: str, max_retries: int = 3) -> float:
        """
        Fetch balance with retry logic to handle temporary network issues.

        Args:
            key: API key to check balance for
            max_retries: Maximum number of retry attempts

        Returns:
            Balance amount or -1 if all retries fail
        """
        for attempt in range(max_retries):
            try:
                balance = self._fetch_balance(key)
                if balance >= 0:
                    return balance

                # If fetch failed, wait with exponential backoff [5](@ref)
                wait_time = 2 ** attempt
                logger.warning(f"Balance fetch attempt {attempt + 1} failed, retrying in {wait_time}s")
                time.sleep(wait_time)

            except Exception as e:
                logger.error(f"Exception during balance fetch attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    break
                time.sleep(2 ** attempt)

        return -1

    def run_forever(self, thread_quit_flag):
        """
        Main scheduling loop for key management.
        Monitors key balances and handles automatic rotation.

        Args:
            thread_quit_flag: Threading event to signal when to stop
        """
        self.running = True
        logger.info("Starting key rotator service")

        # Initial balance check for all keys if enabled
        if self.check_all_balance:
            self._check_all_balances()

        while self.running and not thread_quit_flag.is_set():
            try:
                # Check and update current key
                self.check_update_key()

                # Calculate next check time based on balance consumption rate
                check_interval = self._calculate_check_interval()

                # Wait for next check or quit signal
                thread_quit_flag.wait(check_interval)

            except Exception as e:
                logger.error(f"Error in key rotator loop: {e}")
                time.sleep(60)  # Wait before retrying

        self.running = False
        logger.info("Key rotator service stopped")

    def _calculate_check_interval(self) -> int:
        """
        Calculate next check interval based on balance consumption trends.

        Returns:
            Check interval in seconds (minimum 30 seconds, maximum 1 hour)
        """
        if self.current_key not in self.keys_data:
            return 300

        current_balance = self.keys_data[self.current_key].get('balance', 0)

        # More frequent checks when balance is low
        if current_balance < self.threshold * 5:  # Below 5x threshold
            return 30
        elif current_balance < self.threshold * 10:  # Below 10x threshold
            return 60
        else:
            return 600

    def _check_all_balances(self):
        """Check balances for all keys in the database."""
        logger.info("Checking balances for all keys")
        for key in list(self.keys_data.keys()):
            balance = self._fetch_balance_with_retry(key)
            with self.lock:
                if balance >= 0:
                    self.keys_data[key]['balance'] = balance
                    self.keys_data[key]['status'] = 'valid' if balance >= self.threshold else 'invalid'
                else:
                    self.keys_data[key]['status'] = 'error'

        self._save_key_records()
        logger.info("Completed balance check for all keys")

    def _rotate_to_next_key(self) -> bool:
        """
        Rotate to the next available valid key.

        Returns:
            True if rotation successful, False if no valid keys available
        """
        valid_keys = self._get_valid_keys()

        if not valid_keys:
            logger.error("No valid keys available for rotation")
            return False

        # Remove current key from valid keys list
        if self.current_key in valid_keys:
            valid_keys.remove(self.current_key)

        if valid_keys:
            new_key = valid_keys[0]
            self.current_key = new_key
            self._change_api_key(new_key)
            logger.info(f"Rotated to new key: {new_key[:8]}...")
            return True
        else:
            logger.error("No alternative valid keys available")
            self.current_key = ''
            self.ai_client.set_api_token('')
            return False

    def _get_valid_keys(self) -> List[str]:
        """Get list of valid keys (balance above threshold)."""
        with self.lock:
            return [key for key, data in self.keys_data.items()
                    if data.get('status') in ['valid', 'unknown']
                    and data.get('balance', 0) >= self.threshold]

    def _save_key_records(self):
        """Save key records to file using temporary file for atomic writes [4](@ref)."""
        try:
            # Create temporary file
            temp_file = f"{self.key_record_file}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(self.keys_data, f, indent=2)

            # Atomically replace the old file
            os.replace(temp_file, self.key_record_file)
            logger.debug("Key records saved successfully")

        except Exception as e:
            logger.error(f"Failed to save key records: {e}")

    def _fetch_balance(self, key: str) -> float:
        """
        Fetch balance for a specific API key.

        Args:
            key: API key to check balance for

        Returns:
            Balance amount or -1 if fetch fails
        """
        if not key:
            return -1

        try:
            result = get_siliconflow_balance(key)
            if 'total_balance_usd' in result.get('data', { }):
                return float(result['data']['total_balance_usd'])
            else:
                logger.warning(f"Unknown balance response format for key: {key[:8]}...")
                return -1
        except Exception as e:
            logger.error(f"Error fetching balance for key {key[:8]}...: {e}")
            return -1

    def _change_api_key(self, api_key: str):
        """
        Change the API key in the AI client.

        Args:
            api_key: New API key to set
        """
        try:
            self.ai_client.set_api_token(api_key)
            logger.info(f"Successfully changed API key to: {api_key[:8]}...")
        except Exception as e:
            logger.error(f"Failed to change API key: {e}")

    def stop(self):
        """Stop the key rotator service."""
        self.running = False
        logger.info("Key rotator service stopping")

    def get_status(self) -> Dict:
        """
        Get current status of the key rotator.

        Returns:
            Dictionary containing current status information
        """
        with self.lock:
            valid_count = len(self._get_valid_keys())
            total_count = len(self.keys_data)

            return {
                'current_key': self.current_key[:8] + '...' if self.current_key else 'None',
                'valid_keys': valid_count,
                'total_keys': total_count,
                'threshold': self.threshold,
                'current_balance': self.keys_data.get(self.current_key, {}).get('balance', 0) if self.current_key else 0,
                'running': self.running
            }
