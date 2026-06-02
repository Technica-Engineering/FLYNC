def test_plugin_registration():
    """Test that the dummy plugin is registered correctly."""
    from flync_converter.registry import registry

    registry.load_plugins()

    assert len(registry) > 0
    assert "dummy" in registry
