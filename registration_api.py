from typing import Any
from pyntree import Node
from pickle import UnpicklingError
from uuid import uuid4
from datetime import datetime
from flask import redirect as _redirect
from os import getenv

# Init database accessors
verified = Node('db/users/_map.pyn', autosave=True)
unverified = Node('db/users/_map-unverified.pyn', autosave=True)
socials = Node('db/users/_map-social.pyn', autosave=True)  # social db format: {'platform': {'social_name': 'id', ...}}

# Handle server-side encryption
ENCRYPTION_KEY = getenv("RAPI_AUTHKEY")


# Helper functions
# noinspection PyUnboundLocalVariable
def find_user(identifier: str):
    """
    Find the user given identifier
    :param identifier: An email or tagged username
    :return: The uuid of the user and their status, or a failure notice (False)
    """

    # Determine whether the identifier is an email or tagged username
    method = 'email' if is_email(identifier) else 'username'

    # Search the database
    if method == 'email':
        found_unverified = unverified.where(email=identifier)
        found_verified = verified.where(email=identifier)
    if method == 'username':
        found_unverified = []  # Only registered users have tagged usernames
        found_verified = verified.where(username=identifier)

    if found_verified:
        return found_verified[0]  # There should only be 1!
    elif found_unverified:
        return found_unverified[0]

    return None  # Not found


def is_email(identifier):
    try:
        username = identifier.split('@')[0]
        domain = identifier.split('@')[1]  # Emails can only have 1 @ symbol
    except IndexError:
        return False

    if not username:
        return False

    if '.' not in domain:
        return False

    return True


def send_verification_link(email):
    pass


class API:
    def __init__(self):
        pass

    # Authentication

    def register(self, username: str, email: str, password: str, redirect='/verify') -> Any:
        """
        :param redirect: Where to redirect the user after successful registration
        :param username:
        :param email:
        :param password:
        :return:
        """

        # Ensure the necessary information has been provided
        if not username or not email or not password:
            return 'Please fill out all required information.', 400  # Bad request

        # Ensure email is valid
        if not is_email(email):
            return 'Please provide a valid email.', 400  # Bad request

        # Ensure email is not taken
        if verified.where(email=email) or unverified.where(email=email):  # Hopefully both are empty lists
            return 'That email is already taken.', 401  # Unauthorized

        # Generate user id
        user_id = str(uuid4())

        # Register into UNVERIFIED database
        unverified.set(user_id, {})
        user = unverified.get(user_id)
        user.email = email
        user.username = username
        user.password = password
        user.token = str(uuid4())  # Verification token
        user.crtime = datetime.now()

        send_verification_link(email)

        return user.token()

    def login(self, session, identifier, password, redirect='/') -> Any:
        """
        :param identifier: The user's email or username + tag
        :param password:
        :return:
        """

        # Ensure the necessary information has been provided
        if not identifier or not password:
            return 'Please fill out all required information.', 400  # Bad request

        # Identifier to UUID
        user_id = find_user(identifier)._name
        if user_id is None:
            return f'User not found: {identifier}', 404  # Not found

        # Verify password
        user_db = Node(f'db/users/{user_id}.pyn', password=ENCRYPTION_KEY)
        if user_db.password() != password:
            return f'Invalid password', 401  # Unauthorized

        # Log in
        session['id'] = user_id

        return _redirect(redirect)

    def logout(self, session, redirect='/'):
        del session['id']
        return _redirect(redirect)

    def verify(self, token):
        """
        Accept confirmation link sent via email
        :param token: The token included in the argument for the url sent via email
        :return:
        """

        # Find user given token
        try:
            user = unverified.where(token=token)[0]
        except IndexError:
            return f'No user found. Maybe you already verified your email?', 404  # Not found

        # Register username and email with ID
        user_id = user._name
        verified.set(user_id, {
            "email": user.email(),
            "username": user.username()
        })

        # Create personal data file for user
        Node(
            {
                "email": user.email(),
                "username": user.username(),
                "crtime": datetime.now(),  # Set crtime to verification time
                "password": user.password()
            }
        ).save(f"db/users/{user_id}.pyn")

        # Remove user from unverified
        unverified.delete(user_id)

        return user_id

    def handle_social_login(self, username, platform, session):
        """
        Logs in social users to their associated accounts, or creates new ones for them
        Example OAuth response:
        {'access_token': '[redacted]', 'token_type': 'Bearer', 'expires_in': 3600, 'refresh_token': '[redacted]', 'user_id': 'jvadair', 'expires_at': 1684416088}
        """
        if not socials.has(platform):
            socials.set(platform, {})

        if socials.get(platform).has(username):
            user_id = socials.get(platform).get(username)()
            session['id'] = user_id  # Log in
            session['social_platform'] = platform
            session['social_id'] = username
        else:
            verification_token = self.register(platform + ':' + username, email=f"{str(uuid4())}@example.notarealtld", password=str(uuid4()))
            user_id = self.verify(verification_token)
            socials.get(platform).set(username, user_id)
            # No email (but random uuid since it can't be blank) or verification for OAuth accounts; random password
            session['id'] = user_id  # Log in
            session['social_platform'] = platform
            session['social_id'] = username
