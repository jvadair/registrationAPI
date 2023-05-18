import registration_api


x = registration_api.API()
session = {}


x.handle_social_login("jvadair", "nexus", session)
