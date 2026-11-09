"""Hosted demo settings. Render never reads a developer's dotenv file."""
import os


def hosted():
    return os.getenv('RENDER', '').lower() == 'true' or os.getenv('APP_ENV') == 'production'
