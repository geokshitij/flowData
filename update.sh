#!/bin/bash

# Exit on error
set -e

# Add all changes
git add .

# Commit with a default message, allow override
MESSAGE=${1:-"code update"}
git commit -m "$MESSAGE"

# Push to main branch
git push origin main

