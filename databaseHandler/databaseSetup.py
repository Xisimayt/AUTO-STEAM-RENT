import sqlite3

from datetime import datetime, timedelta

from logger import logger


class SQLiteDB:
    def __init__(self, db_name="database.db"):
        self.db_name = db_name
        # Open a persistent connection to the database
        self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
        self.create_table()

    def create_table(self):
        """Create the 'accounts' table if it does not exist."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                account_name TEXT NOT NULL UNIQUE,
                path_to_maFile TEXT NOT NULL,
                login TEXT NOT NULL,
                password TEXT NOT NULL,
                rental_duration INTEGER NOT NULL,
                owner TEXT DEFAULT NULL,
                rental_start TIMESTAMP DEFAULT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS authorized_users (
                user_id INTEGER PRIMARY KEY,
                authorized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.commit()
        cursor.close()

    def add_account(
        self, account_name, path_to_maFile, login, password, duration, owner=None
    ):
        """Add an account to the database."""
        try:
            # Проверяем, не существует ли уже аккаунт с таким названием
            existing_account = self.get_account_by_name(account_name)
            if existing_account:
                logger.error(f"Account with name '{account_name}' already exists!")
                return False
            
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO accounts (account_name, path_to_maFile, login, password, rental_duration, owner)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (account_name, path_to_maFile, login, password, duration, owner),
            )
            self.conn.commit()
            logger.info(f"Account '{account_name}' added successfully")
            return True
        except Exception as e:
            logger.error(f"Error adding account: {str(e)}")
            return False
        finally:
            cursor.close()

    def get_unowned_accounts(self):
        """Retrieve all accounts with no owner assigned."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT ID, account_name, path_to_maFile, login, password, rental_duration
            FROM accounts 
            WHERE owner IS NULL
            """
        )
        rows = cursor.fetchall()
        cursor.close()
        accounts = [
            {
                "id": row[0],
                "account_name": row[1],
                "path_to_maFile": row[2],
                "login": row[3],
                "password": row[4],
                "rental_duration": row[5],
            }
            for row in rows
        ]
        return accounts

    def set_account_owner(self, account_id: int, owner_id: str) -> bool:
        """
        Set the owner of an account and record the rental start time with a +3 hours offset.
        Also marks all accounts with the same login as 'OTHER_ACCOUNT'.
        """
        try:
            cursor = self.conn.cursor()
            # Update owner and set rental start time
            cursor.execute(
                """
                UPDATE accounts 
                SET owner = ?, rental_start = DATETIME(CURRENT_TIMESTAMP, '+3 hours', '+10 minutes')
                WHERE ID = ? AND owner IS NULL
                """,
                (owner_id, account_id),
            )
            if cursor.rowcount == 0:
                return False
            # Get the login of the updated account
            cursor.execute(
                """
                SELECT login 
                FROM accounts 
                WHERE ID = ?
                """,
                (account_id,),
            )
            login_row = cursor.fetchone()
            if login_row:
                login = login_row[0]
                # Mark all accounts with the same login as 'OTHER_ACCOUNT'
                cursor.execute(
                    """
                    UPDATE accounts 
                    SET owner = 'OTHER_ACCOUNT'
                    WHERE login = ? AND owner IS NULL
                    """,
                    (login,),
                )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error setting account owner: {str(e)}")
            return False
        finally:
            cursor.close()

    def get_active_owners(self):
        """Retrieve all unique owner IDs where owner is not NULL."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT owner 
            FROM accounts 
            WHERE owner IS NOT NULL
            """
        )
        owners = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return owners

    def get_owner_mafile(self, owner_id: str) -> list:
        """
        Retrieve the .maFile path and account details from the most recent account
        associated with the given owner ID.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT ID, account_name, path_to_maFile, login, rental_duration
            FROM accounts 
            WHERE owner = ?
            ORDER BY rental_start DESC
            """,
            (owner_id,),
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def update_password_by_owner(self, owner_name: str, new_password: str) -> bool:
        """
        Update the password for the most recent account owned by the specified owner.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                UPDATE accounts 
                SET password = ?
                WHERE owner = ? 
                AND rental_start = (
                    SELECT MAX(rental_start) 
                    FROM accounts 
                    WHERE owner = ?
                )
                """,
                (new_password, owner_name, owner_name),
            )
            success = cursor.rowcount > 0
            self.conn.commit()
            return success
        except Exception as e:
            logger.error(f"Error updating password: {str(e)}")
            return False
        finally:
            cursor.close()

    def get_active_owners_with_mafiles(self):
        """
        Retrieve all unique owner IDs and their associated maFile paths,
        based on the most recent rental_start for each owner.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT a.owner, a.path_to_maFile
            FROM accounts a
            INNER JOIN (
                SELECT owner, MAX(rental_start) as latest_rental
                FROM accounts
                WHERE owner IS NOT NULL
                GROUP BY owner
            ) b ON a.owner = b.owner AND a.rental_start = b.latest_rental
            """
        )
        owners_data = cursor.fetchall()
        cursor.close()
        return owners_data

    def get_all_accounts(self):
        """Retrieve all accounts from the database."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT ID, account_name, path_to_maFile, login, password, rental_duration, owner
            FROM accounts
            """
        )
        rows = cursor.fetchall()
        cursor.close()
        accounts = [
            {
                "id": row[0],
                "account_name": row[1],
                "path_to_maFile": row[2],
                "login": row[3],
                "password": row[4],
                "rental_duration": row[5],
                "owner": row[6],
            }
            for row in rows
        ]
        return accounts

    def delete_account_by_id(self, account_id: int) -> bool:
        """
        Delete all accounts that share the same login as the account with the given ID.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT login
                FROM accounts
                WHERE ID = ?
                """,
                (account_id,),
            )
            result = cursor.fetchone()
            if not result:
                logger.error(f"No account found with ID {account_id}.")
                return False
            login = result[0]
            cursor.execute(
                """
                DELETE FROM accounts
                WHERE login = ?
                """,
                (login,),
            )
            success = cursor.rowcount > 0
            self.conn.commit()
            return success
        except Exception as e:
            logger.error(f"Error deleting accounts: {str(e)}")
            return False
        finally:
            cursor.close()

    def get_total_accounts(self):
        """Retrieve the total number of accounts."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM accounts")
            total_accounts = cursor.fetchone()[0]
            return total_accounts
        except Exception as e:
            logger.error(f"Error retrieving total accounts: {str(e)}")
            return 0
        finally:
            cursor.close()

    def get_all_account_names(self) -> list:
        """Retrieve all distinct account names."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT account_name FROM accounts")
            account_names = [row[0] for row in cursor.fetchall()]
            return account_names
        except Exception as e:
            logger.error(f"Error retrieving account names: {str(e)}")
            return []
        finally:
            cursor.close()

    def get_unowned_account_names(self) -> list:
        """Retrieve account names for accounts with no owner."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT account_name FROM accounts WHERE owner IS NULL")
            unowned_account_names = [row[0] for row in cursor.fetchall()]
            return unowned_account_names
        except Exception as e:
            logger.error(f"Error retrieving unowned account names: {str(e)}")
            return []
        finally:
            cursor.close()

    def get_account_by_name(self, account_name: str):
        """Get account by its name."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT ID, account_name, path_to_maFile, login, password, rental_duration, owner, rental_start
                FROM accounts 
                WHERE account_name = ?
                """,
                (account_name,)
            )
            row = cursor.fetchone()
            cursor.close()
            
            if row:
                return {
                    "id": row[0],
                    "account_name": row[1],
                    "path_to_maFile": row[2],
                    "login": row[3],
                    "password": row[4],
                    "rental_duration": row[5],
                    "owner": row[6],
                    "rental_start": row[7]
                }
            return None
        except Exception as e:
            logger.error(f"Error getting account by name: {str(e)}")
            return None

    def get_account_by_id(self, account_id: int) -> dict:
        """
        Get account details by ID.
        
        Args:
            account_id (int): The ID of the account
            
        Returns:
            dict: Account details or None if not found
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT ID, account_name, path_to_maFile, login, password, 
                       rental_duration, owner, rental_start
                FROM accounts 
                WHERE ID = ?
                """,
                (account_id,),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "account_name": row[1],
                    "path_to_maFile": row[2],
                    "login": row[3],
                    "password": row[4],
                    "rental_duration": row[5],
                    "owner": row[6],
                    "rental_start": row[7],
                }
            return None
        except Exception as e:
            logger.error(f"Error getting account by ID: {str(e)}")
            return None
        finally:
            cursor.close()

    def get_rental_statistics(self) -> dict:
        """
        Get rental statistics for the system.
        
        Returns:
            dict: Statistics including total accounts, active rentals, etc.
        """
        try:
            cursor = self.conn.cursor()
            
            # Total accounts
            cursor.execute("SELECT COUNT(*) FROM accounts")
            total_accounts = cursor.fetchone()[0]
            
            # Active rentals
            cursor.execute("SELECT COUNT(*) FROM accounts WHERE owner IS NOT NULL")
            active_rentals = cursor.fetchone()[0]
            
            # Available accounts
            cursor.execute("SELECT COUNT(*) FROM accounts WHERE owner IS NULL")
            available_accounts = cursor.fetchone()[0]
            
            # Total rental hours
            cursor.execute("SELECT SUM(rental_duration) FROM accounts WHERE owner IS NOT NULL")
            total_hours = cursor.fetchone()[0] or 0
            
            # Recent rentals (last 24 hours)
            cursor.execute(
                """
                SELECT COUNT(*) FROM accounts 
                WHERE owner IS NOT NULL 
                AND rental_start >= datetime('now', '-1 day')
                """
            )
            recent_rentals = cursor.fetchone()[0]
            
            return {
                "total_accounts": total_accounts,
                "active_rentals": active_rentals,
                "available_accounts": available_accounts,
                "total_hours": total_hours,
                "recent_rentals": recent_rentals
            }
        except Exception as e:
            logger.error(f"Error getting rental statistics: {str(e)}")
            return {}
        finally:
            cursor.close()

    def get_user_rental_history(self, owner_id: str) -> list:
        """
        Get rental history for a specific user.
        
        Args:
            owner_id (str): The owner ID to get history for
            
        Returns:
            list: List of rental records
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT ID, account_name, login, rental_duration, rental_start
                FROM accounts 
                WHERE owner = ?
                ORDER BY rental_start DESC
                """,
                (owner_id,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "account_name": row[1],
                    "login": row[2],
                    "rental_duration": row[3],
                    "rental_start": row[4],
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error getting user rental history: {str(e)}")
            return []
        finally:
            cursor.close()

    def add_time_to_owner_accounts(self, owner: str, hours: int) -> bool:
        """
        Extract the rental_start timestamp, add the specified number of hours to it,
        and update the rental_start field for all accounts with the same owner.
        """
        try:
            cursor = self.conn.cursor()
            # Retrieve the current rental_start timestamps for the owner
            cursor.execute(
                """
                SELECT ID, rental_start
                FROM accounts
                WHERE owner = ? AND rental_start IS NOT NULL
                """,
                (owner,),
            )
            accounts = cursor.fetchall()

            if not accounts:
                logger.info(
                    f"No accounts found for owner {owner} with a valid rental_start."
                )
                return False

            # Update each account with the new timestamp
            for account_id, rental_start in accounts:
                if rental_start:
                    # Parse the timestamp and add the specified hours
                    new_rental_start = datetime.strptime(
                        rental_start, "%Y-%m-%d %H:%M:%S"
                    ) - timedelta(hours=hours)
                    new_rental_start_str = new_rental_start.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )

                    # Update the database with the new timestamp
                    cursor.execute(
                        """
                        UPDATE accounts
                        SET rental_start = ?
                        WHERE ID = ?
                        """,
                        (new_rental_start_str, account_id),
                    )

            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding hours for owner {owner}: {str(e)}")
            return False
        finally:
            cursor.close()

    def get_active_users(self):
        """
        Retrieve all active users from the database along with their account details.
        An active user is one who has a non-null owner and rental_start time.

        Returns:
            list: A list of dictionaries containing active user details
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT 
                    ID,
                    account_name,
                    owner,
                    rental_start,
                    rental_duration,
                    path_to_maFile,
                    login
                FROM accounts 
                WHERE owner IS NOT NULL 
                AND owner != 'OTHER_ACCOUNT'
                AND rental_start IS NOT NULL
                ORDER BY rental_start DESC
                """
            )
            rows = cursor.fetchall()
            active_users = [
                {
                    "id": row[0],
                    "account_name": row[1],
                    "owner": row[2],
                    "rental_start": row[3],
                    "rental_duration": row[4],
                    "path_to_maFile": row[5],
                    "login": row[6],
                }
                for row in rows
            ]
            return active_users
        except Exception as e:
            logger.error(f"Error retrieving active users: {str(e)}")
            return []
        finally:
            cursor.close()

    def get_user_accounts_by_name(self, owner_id: str, account_name: str) -> list:
        """
        Get active accounts of a specific user by account name.
        
        Args:
            owner_id (str): The owner ID
            account_name (str): The name of the account type
            
        Returns:
            list: List of active accounts with the specified name
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT ID, account_name, login, password, rental_duration, rental_start
                FROM accounts 
                WHERE owner = ? AND account_name = ?
                """,
                (owner_id, account_name),
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "account_name": row[1],
                    "login": row[2],
                    "password": row[3],
                    "rental_duration": row[4],
                    "rental_start": row[5],
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error getting user accounts by name: {str(e)}")
            return []
        finally:
            cursor.close()

    def get_user_active_accounts(self, owner_id: str) -> list:
        """
        Get all active accounts of a specific user.
        
        Args:
            owner_id (str): The owner ID
            
        Returns:
            list: List of all active accounts for the user
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT ID, account_name, login, password, rental_duration, rental_start
                FROM accounts 
                WHERE owner = ?
                ORDER BY rental_start DESC
                """,
                (owner_id,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "account_name": row[1],
                    "login": row[2],
                    "password": row[3],
                    "rental_duration": row[4],
                    "rental_start": row[5],
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error getting user active accounts: {str(e)}")
            return []
        finally:
            cursor.close()

    def close(self):
        """Close the persistent database connection."""
        self.conn.close()

    def add_authorized_user(self, user_id: int) -> bool:
        """Add a user to the authorized users list."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO authorized_users (user_id)
                VALUES (?)
                """,
                (user_id,),
            )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding authorized user: {str(e)}")
            return False
        finally:
            cursor.close()

    def get_authorized_users(self) -> list:
        """Retrieve all authorized user IDs."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT user_id FROM authorized_users")
            users = [row[0] for row in cursor.fetchall()]
            return users
        except Exception as e:
            logger.error(f"Error retrieving authorized users: {str(e)}")
            return []
        finally:
            cursor.close()

    def extend_rental_duration(self, account_id: int, additional_hours: int) -> bool:
        """
        Extend the rental duration for a specific account.
        
        Args:
            account_id (int): The ID of the account to extend
            additional_hours (int): Number of hours to add to the rental duration
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                UPDATE accounts 
                SET rental_duration = rental_duration + ?
                WHERE ID = ? AND owner IS NOT NULL
                """,
                (additional_hours, account_id),
            )
            success = cursor.rowcount > 0
            self.conn.commit()
            return success
        except Exception as e:
            logger.error(f"Error extending rental duration: {str(e)}")
            return False
        finally:
            cursor.close()
