# registrationAPI
A modular user registration and login API designed for Flask because I got tired of writing new ones

## Example usage
```python
from registrationAPI import registration_api


x = registration_api.API()

token = x.register("jvadair", "dev@jvadair.com", "password")
x.verify(token)
session = {}  # <-- Use flask's session object, this is for demonstration
resp = x.login(session, "jvadair", "password")  # Will return a redirect or error message
```

## Prerequisites
For email verification:
1. You must create templates/email/verify.html in Jinja format for your application. It can utilize two variables: `token` and `unsub_id`.
2. You must set the following parameters in the config.json file for your application:
```
SMTP_EMAIL:    str
SMTP_ENVPASS:  str  (the name of the environment variable holding the password)
SMTP_SERVER:   str
SMTP_PORT:     int
```
