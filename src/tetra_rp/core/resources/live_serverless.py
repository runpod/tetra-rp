# Ship serverless code as you write it. No builds, no deploys — just run.
from .serverless import ServerlessResource


class LiveServerless(ServerlessResource):
    _locked_fields = {"templateId"}

    def __init__(self, **data):
        data.pop("templateId", None) # Remove templateId from data
        super().__init__(templateId="tetradev", **data)

    def __setattr__(self, name, value):
        if name in self._locked_fields and hasattr(self, name):
            raise AttributeError(f"Field '{name}' is locked and cannot be changed.")
        super().__setattr__(name, value)
