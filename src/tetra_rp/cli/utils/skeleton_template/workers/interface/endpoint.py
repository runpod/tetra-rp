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
