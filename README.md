# registrationAPI
A modular user registration and login API designed for Flask because I got tired of writing new ones

## Example usage
```python
import registration_api


x = registration_api.API()

token = x.register("jvadair", "dev@jvadair.com", "password")
x.verify(token)
session = {}  # <-- Use flask's session object, this is for demonstration
resp = x.login(session, "jvadair", "password")  # Will return a redirect or error message
```
