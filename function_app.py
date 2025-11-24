import azure.functions as func
from api import app as fastapi_app

# Create the Azure Function App instance
app = func.AsgiFunctionApp(app=fastapi_app, http_auth_level=func.AuthLevel.ANONYMOUS)
