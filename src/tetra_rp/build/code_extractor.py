"""
Code extraction and processing for production builds.

Handles extracting source code, removing decorators, and generating code hashes.
"""

import hashlib
import inspect
import logging
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class ExtractedCode:
    """Container for extracted code information."""

    source_code: str
    cleaned_code: str
    callable_name: str
    callable_type: str  # "function" or "class"
    code_hash: str


class CodeExtractor:
    """Extract and process source code from callable objects."""

    def extract(self, func_or_class: Any) -> ExtractedCode:
        """
        Extract source code from a function or class.

        Args:
            func_or_class: The function or class to extract code from

        Returns:
            ExtractedCode object containing source and metadata

        Raises:
            ValueError: If source code cannot be extracted
        """
        callable_name = func_or_class.__name__

        try:
            source_code = inspect.getsource(func_or_class)
        except (OSError, TypeError) as e:
            raise ValueError(
                f"Failed to extract source code for {callable_name}: {e}"
            ) from e

        # Determine callable type
        callable_type = "class" if inspect.isclass(func_or_class) else "function"

        # Clean the code (remove decorators)
        cleaned_code = self._remove_remote_decorator(source_code)

        # Generate hash for versioning
        code_hash = self._generate_code_hash(source_code)

        log.debug(
            f"Extracted {callable_type} '{callable_name}' "
            f"({len(source_code)} bytes, hash: {code_hash})"
        )

        return ExtractedCode(
            source_code=source_code,
            cleaned_code=cleaned_code,
            callable_name=callable_name,
            callable_type=callable_type,
            code_hash=code_hash,
        )

    def _remove_remote_decorator(self, source_code: str) -> str:
        """
        Remove @remote decorator from source code.

        Uses line-based approach to handle both single-line and multi-line decorators.

        Args:
            source_code: Original source code with decorators

        Returns:
            Cleaned source code without @remote decorator
        """
        lines = source_code.splitlines()
        cleaned_lines = []
        in_decorator = False

        for line in lines:
            stripped = line.strip()

            # Start of @remote decorator
            if stripped.startswith("@remote"):
                in_decorator = True
                # Check if it's a multi-line decorator
                if "(" in stripped and ")" not in stripped:
                    continue  # Multi-line, skip this line
                elif "(" in stripped and ")" in stripped:
                    # Single-line decorator, skip it
                    continue
                else:
                    # Just @remote without parens
                    continue

            # Continuation of multi-line decorator
            if in_decorator:
                if ")" in stripped:
                    in_decorator = False
                continue

            cleaned_lines.append(line)

        cleaned = "\n".join(cleaned_lines)

        # Add header if needed
        if "import" not in cleaned[:100]:
            cleaned = "# Auto-generated baked code\n" + cleaned

        return cleaned

    def _generate_code_hash(self, source_code: str) -> str:
        """
        Generate a short hash from source code for versioning.

        Args:
            source_code: Source code to hash

        Returns:
            8-character hex hash
        """
        return hashlib.sha256(source_code.encode()).hexdigest()[:8]
