"""
Simple LoadBalancerSls Example

Shows basic usage of LoadBalancerSls with LoadBalancerSlsResource
"""

import asyncio
import logging

# Add tetra-rp to Python path
# sys.path.insert(0, "/Users/marut/tetra/tetra-rp/src")

from tetra_rp import remote, LoadBalancerSlsResource, endpoint

# Reduce logging noise
logging.getLogger("tetra_rp").setLevel(logging.WARNING)

# Configure LoadBalancerSls resource
lb_config = LoadBalancerSlsResource(name="loadbalancer-sls-test")


# Define class outside main function
@remote(
    resource_config=lb_config,  # Clean resource-based approach
    dependencies=["numpy"],
)
class MLModel:
    def __init__(self):
        self.counter = 0

    @endpoint(methods=["POST"])
    def predict(self, text):
        self.counter += 1
        return {"input": text, "result": f"Processed: {text}", "count": self.counter}

    def compute(self, x, y):
        self.counter += 1
        return {"sum": x + y, "count": self.counter}


async def main():
    print("🚀 LoadBalancerSls Test")
    print("=" * 25)

    # Create model (health check happens automatically)
    print("\n📦 Creating model...")
    model = MLModel()

    # Test remote execution
    print("\n🔄 Remote execution...")
    try:
        result = await model.compute(10, 5)
        print(f"✅ Sum: {result['sum']}, Count: {result['count']}")
    except Exception as e:
        print(f"❌ Remote failed: {e}")

    # Test HTTP endpoint
    print("\n🌐 HTTP endpoint...")
    try:
        result = await model.predict("hello")
        print(f"✅ Result: {result['result']}, Count: {result['count']}")
    except Exception as e:
        print(f"❌ HTTP failed: {e}")

    print("\n🎉 Test completed!")


if __name__ == "__main__":
    asyncio.run(main())
