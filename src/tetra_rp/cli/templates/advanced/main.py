import asyncio
from dotenv import load_dotenv
from tetra_rp import remote, LiveServerless
from utils import generate_report

# Load environment variables from .env file
load_dotenv()

# Configuration for compute workload
compute_config = LiveServerless(
    name="advanced_compute",
    workersMax=2,
    cpu=2,
    memory=4096,
)


@remote(compute_config)
def analyze_data(data):
    """Process and analyze data remotely."""
    import pandas as pd

    # Convert to DataFrame
    df = pd.DataFrame(data)

    # Perform analysis
    result = {
        "mean": df.mean().to_dict(),
        "std": df.std().to_dict(),
        "count": len(df),
        "summary": df.describe().to_dict(),
    }

    return result


async def main():
    print("🚀 Running advanced Tetra example...")

    # Sample data
    sample_data = {
        "values": [1, 2, 3, 4, 5, 10, 15, 20],
        "categories": ["A", "B", "A", "C", "B", "A", "C", "B"],
    }

    # Process remotely
    result = await analyze_data(sample_data)

    # Generate report
    report = generate_report(result)
    print(report)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"An error occurred: {e}")
