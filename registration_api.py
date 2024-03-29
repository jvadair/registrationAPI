import os
from typing import Any
from pyntree import Node
from pickle import UnpicklingError
from uuid import uuid4
from datetime import datetime, timedelta
from flask import redirect as _redirect
from os import getenv, path, mkdir
import string
from registrationAPI import sendmail

USERNAME_ALLOWED = string.ascii_letters + string.digits + "_-"

# Create needed folders and files if they don't exist
for d in ('db', 'db/users', 'db/groups', 'db/orgs'):
    if not path.isdir(d):
        mkdir(d)

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


def send_verification_link(email, email_change=None):
    """
    :param email: The email to send the link to
    :param email_change: Provide with user ID to send the user an email change verification
    :return:
    """
    if email_change:
        user_db = Node(f'db/users/{email_change}.pyn', password=ENCRYPTION_KEY)
        sendmail.send_template('email/verify.html', 'Verify your new HashCards email', user_db.pending_email(),
                               token=user_db.pending_email_token())
    else:
        user = find_user(email)
        if not user.email().endswith('@website.tld'):  # Do not email the fake emails given to OAuth accounts
            sendmail.send_template('email/verify.html', 'Verify your HashCards account', user.email(), token=user.token())


def clear_unverified_accounts(age=0):
    """
    :param age: How long the entry has existed, in minutes
    :return:
    """
    for user in unverified._values:
        user_info = unverified.get(user)
        if user_info.has('crtime'):
            if datetime.now() - timedelta(minutes=age) >= user_info.crtime():
                unverified.delete(user)


class API:
    def __init__(self):
        pass

    # Authentication

    def register(self, username: str, email: str, password: str, redirect='/verify', validate_username: bool = True,
                 send_email=True) -> Any:
        """
        :param redirect: Where to redirect the user after successful registration
        :param username:
        :param email:
        :param password:
        :param validate_username: Whether to ensure usernames contain only valid characters
        :return:
        """

        # Ensure the necessary information has been provided
        if not username or not email or not password:
            return 'Please fill out all required information.', 400  # Bad request

        # Ensure username is valid unless disabled
        if validate_username:
            for char in username:
                if char not in USERNAME_ALLOWED:
                    return 'Usernames may only contain alphanumeric characters, as well as _ and -', 400  # Bad request

        # Ensure email is valid
        if not is_email(email):
            return 'Please provide a valid email.', 400  # Bad request

        # Ensure email is not taken
        if verified.where(email=email) or unverified.where(email=email):  # Hopefully both are empty lists
            return 'That email is already taken.', 401  # Unauthorized

        # Ensure username is not taken
        if verified.where(username=username) or unverified.where(username=username):  # Hopefully both are empty lists
            return 'That username is already taken.', 401  # Unauthorized

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

        if send_email:
            send_verification_link(email)

        return user.token()

    def login(self, session, identifier, password, redirect='/', finduser=True) -> Any:
        """
        :param finduser: Whether to use email/password (True) or user id (False)
        :param redirect:
        :param identifier: The user's email or username + tag, or their user ID if finduser = False
        :param password:
        :return:
        """

        # Ensure the necessary information has been provided
        if not identifier or not password:
            return 'Please fill out all required information.', 400  # Bad request

        # Identifier to UUID
        if finduser:
            user = find_user(identifier)
        else:
            try:
                user = verified.get(identifier)
            except AttributeError:
                user = None
        if user is None:
            return f'User not found: {identifier}', 404  # Not found
        else:
            user_id = user._name
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

        if user.has('email_change'):
            user_id = user.user_id()
            user_db = Node(f'db/users/{user_id}.pyn', password=ENCRYPTION_KEY)
            user_db.email = user_db.pending_email()
            user_db.delete('pending_email_token')
            user_db.delete('pending_email')
            user_db.save()
            user_info = verified.get(user_id)
            user_info.email = user_db.email()
            user.delete()
            return _redirect('/account?updated=True')

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
                "password": user.password(),
                "id": user_id,
                "socials": {},
                "groups": [],
                "orgs": [],
            }
        ).save(
            f"db/users/{user_id}.pyn",
            password=ENCRYPTION_KEY
        )

        # Remove user from unverified
        unverified.delete(user_id)

        return user_id

    def change_email(self, user_id, new_email, require_verification=True):
        # Ensure email is valid
        if not is_email(new_email):
            return 'Please provide a valid email.', 400  # Bad request

        # Ensure email is not taken
        if verified.where(email=new_email) or unverified.where(email=new_email):  # Hopefully both are empty lists
            return 'That email is already taken.', 401  # Unauthorized

        user_db = Node(f'db/users/{user_id}.pyn', password=ENCRYPTION_KEY)
        if require_verification:
            token = str(uuid4())
            user_db.pending_email = new_email
            user_db.pending_email_token = token
            user_db.save()
            unverified.set(token, {
                "user_id": user_id,
                "email_change": True,
                "token": token,
                "crtime": datetime.now(),
            })
            send_verification_link(new_email, email_change=user_id)
            return token
        else:
            user_db.email = new_email
            return None

    def change_username(self, user_id, new_username):
        if not new_username:
            return 'Please provide a valid username', 400

        if len(new_username) > 32:
            return 'Your username is too long (>32 characters).', 400

        # Ensure username is valid
        for char in new_username:
            if char not in USERNAME_ALLOWED:
                return 'Usernames may only contain alphanumeric characters, as well as _ and -', 400  # Bad request

        # Ensure email is not taken
        if verified.where(username=new_username) or unverified.where(username=new_username):  # Hopefully both are empty lists
            return 'That username is already taken.', 401  # Unauthorized

        user_db = Node(f'db/users/{user_id}.pyn', password=ENCRYPTION_KEY)
        user_db.username = new_username
        user_db.save()
        user_info = verified.get(user_id)
        user_info.username = new_username

    def change_password(self, user_id, new_password):
        if not new_password:
            return 'A password was not provided.', 400

        user_db = Node(f'db/users/{user_id}.pyn', password=ENCRYPTION_KEY)
        user_db.password = new_password
        user_db.save()

    def handle_social_login(self, username, platform, session):
        """
        Logs in social users to their associated accounts, or creates new ones for them

        Example OAuth response:
        {'access_token': '[redacted]', 'token_type': 'Bearer', 'expires_in': 3600, 'refresh_token': '[redacted]', 'user_id': 'jvadair', 'expires_at': 1684416088}

        :return: Whether an account was created
        """
        if not socials.has(platform):
            socials.set(platform, {})

        if socials.get(platform).has(username):
            user_id = socials.get(platform).get(username)()
            session['id'] = user_id  # Log in
            session['social_platform'] = platform
            session['social_id'] = username
            return False
        else:
            verification_token = self.register(platform + ':' + username, email=f"{str(uuid4())}@website.tld",
                                               password=str(uuid4()), validate_username=False)
            user_id = self.verify(verification_token)
            self.link_social_account(user_id, username, platform)
            # No email (but random uuid since it can't be blank) or verification for OAuth accounts; random password
            session['id'] = user_id  # Log in
            session['social_platform'] = platform
            session['social_id'] = username
            return True

    def link_social_account(self, user_id, social_name, social_platform):
        """
        :param user_id: The local ID of the user
        :param social_name: The social ID of the user
        :param social_platform: The platform used to connect
        :return: Whether the linking operation was successful. If False, the user has already linked that platform or the social account is in use by another account.
        """
        if not socials.has(social_platform):
            socials.set(social_platform, {})
        user_db = Node(f'db/users/{user_id}.pyn', password=ENCRYPTION_KEY)
        if user_db.socials.has(social_platform) or socials.get(social_platform).has(social_name):
            return False
        user_db.socials.set(social_platform, social_name)
        user_db.save()
        socials.get(social_platform).set(social_name, user_id)
        return True

    def unlink_social_account(self, user_id, social_platform):
        """
        :param user_id: The local ID of the user
        :param social_platform: The associated platform
        :return: Whether the unlinking operation was successful
        """
        user_db = Node(f'db/users/{user_id}.pyn', password=ENCRYPTION_KEY)
        if not user_db.socials.has(social_platform):
            return False
        social_name = user_db.socials.get(social_platform)()
        socials.get(social_platform).delete(social_name)
        user_db.socials.delete(social_platform)
        user_db.save()
        return True

    def delete_account(self, user_id: str, session: dict = None) -> None:
        """
        Delete the account of the specified user
        :param user_id: The user to delete
        :param session: If provided, will also log out the user first
        :return:
        """
        if session:
            self.logout(session)
        # Remove social login ties, if any. Must be done before deleting user data.
        user_db = Node(f'db/users/{user_id}.pyn', password=ENCRYPTION_KEY)
        for platform in user_db.socials._values:
            socials.get(platform).delete(user_db.socials.get(platform)())
        os.remove(f'db/users/{user_id}.pyn')  # Remove user data file
        verified.delete(user_id)  # Remove user from account map

    # Group management functions
    def create_group(self, owner_id: str, name: str) -> str:
        """
        Creates a new group
        :param owner_id: The user id to set as the owner
        :param name: The name of the group
        :return: The group ID
        """
        new_group = Node({
            "id": str(uuid4()),
            "name": name,
            "owner": owner_id,
            "members": [owner_id],
        })
        new_group.save(f"db/groups/{new_group.id()}.pyn")
        return new_group.id()

    def modify_group(self, group_id: str, **kwargs) -> None:
        """
        :param group_id: The ID of the group
        :param kwargs: The group properties to change and their respective new values
        :return:
        """
        group = Node(f"db/groups/{group_id}.pyn")
        for kwarg in kwargs:
            group.set(kwarg, kwargs[kwarg])
        group.save()

    def delete_group(self, group_id: str) -> None:
        """
        Deletes a group
        :param self:
        :param group_id: The ID of the group to delete
        :return:
        """
        os.remove(f'db/groups/{group_id}.pyn')

    # Organization management functions

    def create_org(self, owner_id: str, name: str) -> str:
        """
        Creates a new organization
        :param owner_id: The user id to set as the owner
        :param name: The name of the organization
        :return: The org ID
        """
        new_org = Node({
            "id": str(uuid4()),
            "name": name,
            "owner": owner_id,
            "members": [owner_id],
            "groups": [],
        })
        new_org.save(f"db/orgs/{new_org.id()}.pyn")
        return new_org.id()

    def modify_org(self, org_id: str, **kwargs) -> None:
        """
        :param org_id: The ID of the organization
        :param kwargs: The org properties to change and their respective new values
        :return:
        """
        org = Node(f"db/orgs/{org_id}.pyn")
        for kwarg in kwargs:
            org.set(kwarg, kwargs[kwarg])
        org.save()

    def delete_org(self, org_id: str) -> None:
        """
        Deletes an organization
        :param self:
        :param org_id: The ID of the organization to delete
        :return:
        """
        os.remove(f'db/orgs/{org_id}.pyn')
