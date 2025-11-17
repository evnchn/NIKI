#!/bin/bash

# Script to pack necessary files for Docker build into docker_necessary_files.tar

# List of files and directories to include
FILES=(
    "main.py"
    "niki_ai.py"
    "shared_state.py"
    "niki_utils.py"
    "photos.py"
    "tts.py"
    "camera.py"
    "camera.js"
    "requirements.txt"
    "Dockerfile"
    "assets/"
    "README.md"
    "FLOW.md"
    "NIKI_SCREEN_ELEMENTS.md"
)

# Strip extended attributes from all files and directories
echo "Stripping extended attributes..."
for file in "${FILES[@]}"; do
    if [ -e "$file" ]; then
        xattr -cr "$file"
    fi
done

# Create the tar archive
tar --no-xattr --no-mac-metadata -cf docker_necessary_files.tar "${FILES[@]}"

echo "Created docker_necessary_files.tar with necessary files for Docker build."