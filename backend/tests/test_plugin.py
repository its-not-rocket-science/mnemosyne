from backend.plugins.spanish_mvp import SpanishMVPPlugin


def test_spanish_plugin_extracts_objects() -> None:
    plugin = SpanishMVPPlugin()
    result = plugin.analyze_sentence("La casa roja habla.")
    kinds = {obj.type for obj in result.learnable_objects}
    assert "vocabulary" in kinds
    assert "agreement" in kinds
    assert "conjugation" in kinds


def test_spanish_plugin_stores_lessons() -> None:
    plugin = SpanishMVPPlugin()
    result = plugin.analyze_sentence("Yo hablo.")
    lesson = plugin.get_lesson(result.learnable_objects[0].id)
    assert lesson is not None
