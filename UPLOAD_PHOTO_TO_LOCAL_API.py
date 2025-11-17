#!/usr/bin/env python3
"""
Photo Upload Script for NIKI Photo Booth

This script uploads a local image file (LOCAL.JPG) to the NIKI photo booth API.
It converts the image to base64 format and sends it to the /api/save_photo endpoint.
"""

import base64
import os

import requests


def upload_photo_to_api(image_path: str, api_url: str = "http://localhost:11011/api/save_photo") -> dict:
    """
    Upload a local image file to the NIKI photo booth API.

    Args:
        image_path: Path to the local image file
        api_url: API endpoint URL (default: localhost:11011)

    Returns:
        dict: API response containing success status and filename

    Raises:
        FileNotFoundError: If the image file doesn't exist
        requests.RequestException: If the API request fails
    """
    # Check if file exists
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")

    # Read and encode the image
    with open(image_path, "rb") as image_file:
        image_data = image_file.read()

    # Convert to base64 and create data URL
    b64_encoded = base64.b64encode(image_data).decode("utf-8")
    # Assume JPEG format for LOCAL.JPG
    b64url = f"data:image/jpeg;base64,{b64_encoded}"

    # Prepare the request payload
    payload = {"b64url": b64url}

    # Send POST request to API
    try:
        response = requests.post(api_url, json=payload)
        response.raise_for_status()  # Raise exception for bad status codes

        return response.json()

    except requests.RequestException as e:
        print(f"Error uploading photo: {e}")
        raise


def main():
    """Main function to upload LOCAL.JPG to the API."""
    image_path = "LOCAL.JPG"

    try:
        result = upload_photo_to_api(image_path)
        print("Photo uploaded successfully!")
        print(f"Response: {result}")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Make sure LOCAL.JPG exists in the current directory.")

    except requests.RequestException as e:
        print(f"API request failed: {e}")
        print("Make sure the NIKI server is running on http://localhost:11011")


if __name__ == "__main__":
    main()
