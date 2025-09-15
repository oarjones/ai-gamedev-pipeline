from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
import yaml
import json
import re

class PromptTemplate:
    """Represents a parametrizable prompt template."""
    
    def __init__(self, data: Dict[str, Any]):
        self.name = data.get('name', 'unknown')
        self.version = data.get('version', '1.0')
        self.parameters = data.get('parameters', [])
        self.prompt = data.get('prompt', '')
        self.json_schema = data.get('json_schema', None)
        self.examples = data.get('examples', [])
    
    def render(self, **kwargs) -> str:
        """Render template with parameters."""
        prompt = self.prompt
        
        for param in self.parameters:
            key = param['name']
            value = kwargs.get(key, param.get('default', ''))
            prompt = prompt.replace(f'{{{key}}}', str(value))
        
        if self.json_schema:
            prompt = prompt.replace('{json_schema}', json.dumps(self.json_schema, indent=2))
        
        return prompt

class PromptService:
    """Service for managing prompt templates."""
    
    def __init__(self, templates_dir: str = "gateway/prompts"):
        self.templates_dir = Path(templates_dir)
        self.templates_cache: Dict[str, PromptTemplate] = {}
        self._load_templates()
    
    def _load_templates(self):
        """Load all templates from directory."""
        if not self.templates_dir.exists():
            self.templates_dir.mkdir(parents=True, exist_ok=True)
            self._create_default_templates()
        
        for template_file in self.templates_dir.glob("*.yaml"):
            try:
                with open(template_file, encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    if data and 'name' in data:
                        template = PromptTemplate(data)
                        self.templates_cache[template.name] = template
            except Exception as e:
                print(f"Error loading template {template_file}: {e}")
    
    def load_template(self, name: str) -> Optional[PromptTemplate]:
        """Load a specific template."""
        return self.templates_cache.get(name)
    
    def render_prompt(self, template_name: str, **params) -> str:
        """Render a prompt from template."""
        template = self.load_template(template_name)
        if not template:
            raise ValueError(f"Template {template_name} not found")
        
        return template.render(**params)
    
    def validate_response(self, template_name: str, response: str) -> Tuple[bool, Optional[Dict]]:
        """Validate AI response against template schema."""
        template = self.load_template(template_name)
        if not template or not template.json_schema:
            return True, None
        
        json_data = self.auto_repair_json(response)
        if not json_data:
            return False, None
        
        required_keys = template.json_schema.get('required', [])
        for key in required_keys:
            if key not in json_data:
                return False, json_data
        
        return True, json_data
    
    def auto_repair_json(self, response_text: str) -> Optional[Dict]:
        """Extract and repair JSON from response."""
        # Look for the largest JSON block
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, response_text, re.DOTALL)
        
        for match in sorted(matches, key=len, reverse=True):
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        
        text = response_text.strip()
        if text.startswith('```json'):
            text = text[7:]
        if text.startswith('```'):
            text = text[3:]
        if text.endswith('```'):
            text = text[:-3]
        
        try:
            return json.loads(text)
        except:
            return None
    
    def get_genre_specific_tasks(self, genre: str) -> List[Dict]:
        """Get common tasks for a game genre."""
        genre_tasks = {
            "platformer": [
                {"title": "Setup character controller", "mcp_tools": ["unity"]},
                {"title": "Implement jump mechanics", "mcp_tools": ["unity"]},
                {"title": "Create level tilemap system", "mcp_tools": ["unity"]},
            ],
            "puzzle": [
                {"title": "Create grid system", "mcp_tools": ["unity"]},
                {"title": "Implement piece movement", "mcp_tools": ["unity"]},
                {"title": "Add match detection", "mcp_tools": ["unity"]},
            ],
            "fps": [
                {"title": "Setup first person camera", "mcp_tools": ["unity"]},
                {"title": "Implement weapon system", "mcp_tools": ["unity", "blender"]},
                {"title": "Add enemy AI", "mcp_tools": ["unity"]},
            ]
        }
        return genre_tasks.get(genre, [])
    
    def _create_default_templates(self):
        """Create default templates if they don't exist."""
        plan_template = {
            "name": "plan_generation",
            "version": "1.0",
            "parameters": [
                {"name": "project_type", "type": "string", "default": "generic"},
                {"name": "complexity", "type": "string", "default": "mvp"},
                {"name": "project_manifest", "type": "object"},
                {"name": "min_tasks", "type": "integer", "default": 8},
                {"name": "max_tasks", "type": "integer", "default": 15}
            ],
            "prompt": """Eres un planificador experto de desarrollo de videojuegos.
Tipo de proyecto: {project_type}
Complejidad: {complexity}

MANIFEST DEL PROYECTO:
{project_manifest}

Genera un plan de desarrollo con entre {min_tasks} y {max_tasks} tareas.

Cada tarea debe incluir:
- code: Identificador único (T-001, T-002, etc.)
- title: Título descriptivo
- description: Descripción detallada
- dependencies: Array de códigos de tareas previas
- mcp_tools: Herramientas MCP necesarias
- deliverables: Entregables esperados
- acceptance_criteria: Criterios de aceptación claros
- estimates: story_points (1-13) y time_hours
- priority: 1-5

Responde SOLO con JSON válido:
{json_schema}""",
            "json_schema": {
                "type": "object",
                "required": ["tasks"],
                "properties": {
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["code", "title", "description"]
                        }
                    }
                }
            }
        }
        
        template_file = self.templates_dir / "plan_generation.yaml"
        if not template_file.exists():
            with open(template_file, 'w', encoding='utf-8') as f:
                yaml.dump(plan_template, f, allow_unicode=True)

prompt_service = PromptService()