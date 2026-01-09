"""
Cost tracking example

This example demonstrates how to track and analyze costs.
"""

import asyncio
from multi_provider_router import Router
from multi_provider_router.models import GenerationRequest


async def main():
    # Initialize router
    router = Router()

    # Make several requests
    requests = [
        "Explain machine learning",
        "What is quantum computing?",
        "How does the internet work?",
        "Write a poem about technology",
        "Explain neural networks"
    ]

    total_cost = 0.0

    print("Processing requests and tracking costs:\n")

    for i, prompt in enumerate(requests, 1):
        request = GenerationRequest(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=200
        )

        response = await router.generate(request)

        total_cost += response.cost_usd

        print(f"{i}. Provider: {response.provider_used:12} | "
              f"Tokens: {response.input_tokens + response.output_tokens:5} | "
              f"Cost: ${response.cost_usd:.6f}")

    print(f"\n{'='*50}")
    print(f"Total Requests: {len(requests)}")
    print(f"Total Cost: ${total_cost:.6f}")
    print(f"Average Cost per Request: ${total_cost/len(requests):.6f}")
    print(f"{'='*50}")


if __name__ == "__main__":
    asyncio.run(main())
