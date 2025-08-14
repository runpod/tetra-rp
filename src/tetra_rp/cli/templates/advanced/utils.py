"""Utility functions for advanced example."""


def process_data(data):
    """Process raw data before analysis."""
    # Add any preprocessing logic here
    return data


def generate_report(analysis_result):
    """Generate a formatted report from analysis results."""
    report = "\n=== Analysis Report ===\n"

    if "mean" in analysis_result:
        report += "\nMean values:\n"
        for key, value in analysis_result["mean"].items():
            report += f"  {key}: {value:.2f}\n"

    if "count" in analysis_result:
        report += f"\nTotal records: {analysis_result['count']}\n"

    report += "\n" + "=" * 25

    return report
