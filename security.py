import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()

def basic_auth(credentials: HTTPBasicCredentials = Depends(security)):
    """
    Checks for valid basic auth credentials.
    In a real app, you would check the credentials against a database of users.
    """
    # Use secrets.compare_digest to prevent timing attacks
    correct_username = secrets.compare_digest(credentials.username, "admin")
    correct_password = secrets.compare_digest(credentials.password, "admin")
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return {"sub": credentials.username, "username": credentials.username}