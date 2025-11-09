import json
import os
import secrets
import string
import sys


sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger import logger
from steampassword.chpassword import SteamPasswordChange
from steampassword.steam import CustomSteam


def generate_password(length: int = 12) -> str:
    """
    Generate a secure random password.

    Args:
        length (int): Length of the password. Default is 12.

    Returns:
        str: A randomly generated password.
    """
    if length < 8:
        raise ValueError("Password length should be at least 8 characters.")

    # Define the character pool
    alphabet = string.ascii_letters + string.digits
    # Generate a secure random password
    password = "".join(secrets.choice(alphabet) for _ in range(length))
    return password


async def changeSteamPassword(path_to_maFile: str, password: str) -> str:

    logger.info("Started changing password")

    with open(path_to_maFile, "r") as f:
        data = json.load(f)
        logger.info(f"Started changing password for {data['account_name']}")
    steam = CustomSteam(
        login=data["account_name"],
        password=password,
        shared_secret=data["shared_secret"],
        identity_secret=data["identity_secret"],
        device_id=data["device_id"],
        steamid=int(data["Session"]["SteamID"]),
    )

    new_password = generate_password(12)

    await SteamPasswordChange(steam).change(new_password)

    logger.info(f"{data['account_name']} new password -> {new_password}")

    return new_password
