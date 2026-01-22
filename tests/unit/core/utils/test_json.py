"""Tests for JSON normalization utilities."""

from enum import Enum

from pydantic import BaseModel

from tetra_rp.core.utils.json import normalize_for_json


class Color(Enum):
    """Test enum for color values."""

    RED = "red"
    GREEN = "green"
    BLUE = "blue"


class Status(Enum):
    """Test enum for status values."""

    ACTIVE = 1
    INACTIVE = 0


class SimpleModel(BaseModel):
    """Simple Pydantic model for testing."""

    name: str
    value: int


class NestedModel(BaseModel):
    """Nested Pydantic model for testing."""

    simple: SimpleModel
    color: Color


class ModelWithList(BaseModel):
    """Model containing a list."""

    items: list[int]
    tags: list[str]


class ModelWithEnum(BaseModel):
    """Model with enum field."""

    status: Status
    color: Color


class TestNormalizeForJsonPrimitives:
    """Test normalize_for_json with primitive types."""

    def test_integer_passthrough(self) -> None:
        """Test integer passes through unchanged."""
        assert normalize_for_json(42) == 42
        assert normalize_for_json(0) == 0
        assert normalize_for_json(-100) == -100

    def test_string_passthrough(self) -> None:
        """Test string passes through unchanged."""
        assert normalize_for_json("hello") == "hello"
        assert normalize_for_json("") == ""

    def test_float_passthrough(self) -> None:
        """Test float passes through unchanged."""
        assert normalize_for_json(3.14) == 3.14
        assert normalize_for_json(0.0) == 0.0
        assert normalize_for_json(-1.5) == -1.5

    def test_boolean_passthrough(self) -> None:
        """Test boolean values pass through unchanged."""
        assert normalize_for_json(True) is True
        assert normalize_for_json(False) is False

    def test_none_passthrough(self) -> None:
        """Test None passes through unchanged."""
        assert normalize_for_json(None) is None


class TestNormalizeForJsonEnums:
    """Test normalize_for_json with enum types."""

    def test_enum_returns_value(self) -> None:
        """Test enum is converted to its value."""
        assert normalize_for_json(Color.RED) == "red"
        assert normalize_for_json(Color.GREEN) == "green"
        assert normalize_for_json(Color.BLUE) == "blue"

    def test_integer_enum_returns_value(self) -> None:
        """Test integer enum is converted to its value."""
        assert normalize_for_json(Status.ACTIVE) == 1
        assert normalize_for_json(Status.INACTIVE) == 0

    def test_enum_in_dict(self) -> None:
        """Test enum values are normalized in dicts."""
        result = normalize_for_json({"color": Color.RED, "status": Status.ACTIVE})
        assert result == {"color": "red", "status": 1}

    def test_enum_in_list(self) -> None:
        """Test enum values are normalized in lists."""
        result = normalize_for_json([Color.RED, Color.GREEN, Status.ACTIVE])
        assert result == ["red", "green", 1]


class TestNormalizeForJsonBaseModel:
    """Test normalize_for_json with Pydantic BaseModel."""

    def test_simple_model_conversion(self) -> None:
        """Test simple model is converted to dict."""
        model = SimpleModel(name="test", value=42)
        result = normalize_for_json(model)
        assert result == {"name": "test", "value": 42}
        assert isinstance(result, dict)

    def test_model_with_enum_field(self) -> None:
        """Test model with enum field normalizes enum values."""
        model = ModelWithEnum(status=Status.ACTIVE, color=Color.RED)
        result = normalize_for_json(model)
        assert result == {"status": 1, "color": "red"}

    def test_nested_model_conversion(self) -> None:
        """Test nested models are recursively converted."""
        simple = SimpleModel(name="nested", value=10)
        nested = NestedModel(simple=simple, color=Color.GREEN)
        result = normalize_for_json(nested)
        assert result == {
            "simple": {"name": "nested", "value": 10},
            "color": "green",
        }

    def test_model_with_list_field(self) -> None:
        """Test model with list field is normalized."""
        model = ModelWithList(items=[1, 2, 3], tags=["a", "b"])
        result = normalize_for_json(model)
        assert result == {"items": [1, 2, 3], "tags": ["a", "b"]}


class TestNormalizeForJsonCollections:
    """Test normalize_for_json with collections."""

    def test_empty_dict(self) -> None:
        """Test empty dictionary passes through."""
        assert normalize_for_json({}) == {}

    def test_empty_list(self) -> None:
        """Test empty list passes through."""
        assert normalize_for_json([]) == []

    def test_empty_tuple(self) -> None:
        """Test empty tuple passes through."""
        assert normalize_for_json(()) == ()

    def test_dict_with_primitive_values(self) -> None:
        """Test dict with primitive values."""
        data = {"a": 1, "b": "hello", "c": 3.14, "d": None}
        assert normalize_for_json(data) == data

    def test_dict_with_mixed_values(self) -> None:
        """Test dict with mixed nested types."""
        data = {"int": 42, "enum": Color.RED, "list": [1, 2, 3]}
        result = normalize_for_json(data)
        assert result == {"int": 42, "enum": "red", "list": [1, 2, 3]}

    def test_list_with_mixed_types(self) -> None:
        """Test list with mixed types."""
        data = [1, "hello", 3.14, Color.RED, None]
        result = normalize_for_json(data)
        assert result == [1, "hello", 3.14, "red", None]

    def test_tuple_preserves_type(self) -> None:
        """Test tuple values are normalized but type is preserved."""
        data = (1, "hello", Color.RED)
        result = normalize_for_json(data)
        assert result == (1, "hello", "red")
        assert isinstance(result, tuple)

    def test_list_of_models(self) -> None:
        """Test list of models is normalized."""
        models = [
            SimpleModel(name="m1", value=1),
            SimpleModel(name="m2", value=2),
        ]
        result = normalize_for_json(models)
        assert result == [{"name": "m1", "value": 1}, {"name": "m2", "value": 2}]


class TestNormalizeForJsonNested:
    """Test normalize_for_json with deeply nested structures."""

    def test_deeply_nested_dict(self) -> None:
        """Test deeply nested dictionary structure."""
        data = {"a": {"b": {"c": {"d": {"e": Color.RED}}}}}
        result = normalize_for_json(data)
        assert result == {"a": {"b": {"c": {"d": {"e": "red"}}}}}

    def test_deeply_nested_list(self) -> None:
        """Test deeply nested list structure."""
        data = [[[["value", Color.GREEN]]]]
        result = normalize_for_json(data)
        assert result == [[[["value", "green"]]]]

    def test_mixed_nested_collections(self) -> None:
        """Test mixed nested dicts and lists."""
        data = {
            "items": [
                {"id": 1, "color": Color.RED},
                {"id": 2, "color": Color.BLUE},
            ],
            "status": Status.ACTIVE,
        }
        result = normalize_for_json(data)
        assert result == {
            "items": [
                {"id": 1, "color": "red"},
                {"id": 2, "color": "blue"},
            ],
            "status": 1,
        }

    def test_model_with_nested_list_of_models(self) -> None:
        """Test model containing list of models."""

        class Container(BaseModel):
            items: list[SimpleModel]

        container = Container(
            items=[
                SimpleModel(name="a", value=1),
                SimpleModel(name="b", value=2),
            ]
        )
        result = normalize_for_json(container)
        assert result == {
            "items": [
                {"name": "a", "value": 1},
                {"name": "b", "value": 2},
            ]
        }

    def test_complex_nested_structure(self) -> None:
        """Test complex structure with models, enums, and collections."""
        model = ModelWithEnum(status=Status.ACTIVE, color=Color.RED)
        data = {
            "model": model,
            "colors": [Color.RED, Color.GREEN, Color.BLUE],
            "nested": {
                "items": [1, 2, 3],
                "status": Status.INACTIVE,
            },
        }
        result = normalize_for_json(data)
        assert result == {
            "model": {"status": 1, "color": "red"},
            "colors": ["red", "green", "blue"],
            "nested": {
                "items": [1, 2, 3],
                "status": 0,
            },
        }
