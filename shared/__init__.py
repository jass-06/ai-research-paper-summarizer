"""Shared core used by BOTH the FastAPI backend and the AWS Lambda function.

Keeping PDF extraction, AI calls, storage and the processing pipeline in one
package means the inline (local) path and the serverless (Lambda) path can
never drift apart.
"""
