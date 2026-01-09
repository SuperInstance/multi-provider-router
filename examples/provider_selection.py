"""
Provider selection example

This example demonstrates how to control provider selection.
"""

import asyncio
from multi_provider_router import Router
from multi_provider_router.models import GenerationRequest


async def main():
    # Initialize router
    router = Router()

    # Example 1: Let router choose best provider
    print("Example 1: Automatic provider selection")
    print("-" * 50)

    request1 = GenerationRequest(
        messages=[{"role": "user", "content": "What is 2+2?"}],
        temperature=0.7
    )

    response1 = await router.generate(request1)
    print(f"Provider Selected: {response1.provider_used}")
    print(f"Reasoning: Cost optimization (GLM-4 default)")
    print()

    # Example 2: Prefer specific provider
    print("Example 2: Preferred provider")
    print("-" * 50)

    request2 = GenerationRequest(
        messages=[{"role": "user", "content": "Write Python code to sort a list"}],
        temperature=0.7,
        preferred_provider="deepseek"  # Prefer DeepSeek for coding
    )

    response2 = await router.generate(request2)
    print(f"Provider Selected: {response2.provider_used}")
    print(f"Reasoning: Coding task -> DeepSeek")
    print()

    # Example 3: Use specialty model
    print("Example 3: Specialty model for complex reasoning")
    print("-" * 50)

    request3 = GenerationRequest(
        messages=[{"role": "user", "content": "Solve this complex math problem..."}],
        temperature=0.7,
        force_specialty_model="wizardlm-2-8x22b"
    )

    response3 = await router.generate(request3)
    print(f"Provider Selected: {response3.provider_used}")
    print(f"Model: {response3.model_used}")
    print(f"Reasoning: Complex reasoning -> Specialty model")
    print()


if __name__ == "__main__":
    asyncio.run(main())
