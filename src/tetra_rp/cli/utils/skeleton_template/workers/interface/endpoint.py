"""
Example CPU Interface
"""

from tetra_rp import remote, CpuLiveServerless


# Configure CPU resource for this interface
config = CpuLiveServerless(name="interface_worker")


@remote(config)
def todo_get_list():
    return {
        "item_1": "Make a list",
        "item_2": "Show a list",
        "item_3": "Delete a list",
    }


@remote(config)
def todo_add_item(item):
    return f"added item: {item}"


@remote(config)
def todo_delete_item(item):
    return f"deleted item: {item}"


# Run this script by itself to test the CPU interface
if __name__ == "__main__":
    import asyncio

    async def test_interface():
        """Test all interface functions in parallel."""
        # Run all functions concurrently
        list_result, add_result, delete_result = await asyncio.gather(
            todo_get_list(),
            todo_add_item("Test task"),
            todo_delete_item("Old task"),
        )

        print("List result:", list_result)
        print("Add result:", add_result)
        print("Delete result:", delete_result)

    asyncio.run(test_interface())
