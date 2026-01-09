"""
Streaming generation example

This example demonstrates how to use streaming responses.
"""

import asyncio
from multi_provider_router import Router
from multi_provider_router.models import GenerationRequest


async def main():
    # Initialize router
    router = Router()

    # Create a request
    request = GenerationRequest(
        messages=[
            {"role": "user", "content": "Write a short story about AI"}
        ],
        temperature=0.8,
        max_tokens=1000
    )

    # Stream response
    print("Streaming response:")
    print("-" * 50)

    async for chunk in router.generate_stream(request):
        print(chunk, end='', flush=True)

    print("\n" + "-" * 50)
    print("Stream complete!")


if __name__ == "__main__":
    asyncio.run(main())
