import pytest
from app.services.prompt_service import PromptService

@pytest.fixture(scope="module")
def service():
    """Initialize the PromptService, pointing to the project's templates dir."""
    # The service automatically loads templates on init
    return PromptService(templates_dir="gateway/prompts")

def test_template_loading(service):
    """Test that default templates are loaded correctly."""
    assert "plan_generation" in service.templates_cache
    template = service.load_template("plan_generation")
    assert template is not None
    assert template.name == "plan_generation"
    assert len(template.parameters) == 5

def test_render_prompt(service):
    """Test rendering a prompt with parameters."""
    rendered = service.render_prompt(
        "plan_generation",
        project_type="2D Platformer",
        complexity="full",
        project_manifest='{"name": "Test Game"}',
        min_tasks=5,
        max_tasks=10
    )
    
    assert "Tipo de proyecto: 2D Platformer" in rendered
    assert "Complejidad: full" in rendered
    assert '{"name": "Test Game"}' in rendered
    assert "entre 5 y 10 tareas" in rendered
    assert '"tasks": {' in rendered # Check schema was injected

def test_auto_repair_json():
    # Note: service instance not needed as this is a static-like utility method
    ps = PromptService()
    
    # Test 1: Clean JSON
    clean_json_str = '{"key": "value"}'
    assert ps.auto_repair_json(clean_json_str) == {"key": "value"}

    # Test 2: JSON with markdown fences
    md_json_str = '```json\n{"key": "value"}\n```'
    assert ps.auto_repair_json(md_json_str) == {"key": "value"}

    # Test 3: JSON within surrounding text
    text_json_str = 'Here is the JSON you requested: { "data": [1, 2] } Thank you.'
    assert ps.auto_repair_json(text_json_str) == {"data": [1, 2]}

    # Test 4: Invalid JSON
    invalid_str = 'this is not json'
    assert ps.auto_repair_json(invalid_str) is None

    # Test 5: JSON with extra text inside code block
    extra_text_md = '```json\nHere is the plan:\n{"tasks": []}\n```'
    assert ps.auto_repair_json(extra_text_md) == {"tasks": []}
