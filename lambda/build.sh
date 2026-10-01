#!/usr/bin/env bash
# Builds lambda/lambda_function.zip with the shared/ package and Linux-compatible
# dependencies (works from macOS too — pip downloads manylinux wheels).
set -euo pipefail
cd "$(dirname "$0")"

rm -rf build lambda_function.zip
mkdir -p build
cp lambda_function.py build/
cp -r ../shared build/shared
find build -name "__pycache__" -type d -prune -exec rm -rf {} +

python3 -m pip install -r requirements.txt --target build/ \
  --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 \
  --only-binary=:all: --upgrade --quiet

(cd build && zip -qr ../lambda_function.zip . -x "*.pyc" "*/__pycache__/*")
echo "Built lambda/lambda_function.zip ($(du -h lambda_function.zip | cut -f1))"
echo "Update an existing function with:"
echo "  aws lambda update-function-code --function-name paper-processor --zip-file fileb://lambda_function.zip"
