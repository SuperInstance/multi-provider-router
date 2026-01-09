"""
Basic usage example for Multi-Provider Router

This example demonstrates how to use the router for simple text generation.
"""

import asyncio
from multi_provider_router import Router
from multi_provider_router.models import GenerationRequest


async def main():
    # Initialize router
    router = Router()

    # Create a simple request
    request = GenerationRequest(
        messages=[
            {"role": "user", "content": "Explain quantum computing in simple terms"}
        ],
        temperature=0.7,
        max_tokens=500
    )

    # Generate response
    print("Sending request to router...")
    response = await router.generate(request)

    # Display results
    print(f"\nProvider Used: {response.provider_used}")
    print(f"Model: {response.model_used}")
    print(f"Cost: ${response.cost_usd:.6f}")
    print(f"Processing Time: {response.processing_time_ms}ms")
    print(f"\nResponse:\n{response.content}")


if __name__ == "__main__":
    asyncio.run(main())
