import abc
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, Field

class Skill(abc.ABC):
    """Abstract base class for all Skills."""
    
    name: str
    description: str
    version: str = "1.0.0"
    
    # Optional: Input schema for the skill using Pydantic
    input_schema: Optional[Type[BaseModel]] = None
    
    @abc.abstractmethod
    def execute(self, **kwargs) -> Any:
        """Execute the skill logic."""
        pass
    
    def to_json(self) -> Dict[str, Any]:
        """Serialize skill metadata."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "input_schema": self.input_schema.model_json_schema() if self.input_schema else None
        }

class SkillRegistry:
    """Registry to manage available skills."""
    
    _skills: Dict[str, Skill] = {}
    
    @classmethod
    def register(cls, skill: Skill):
        """Register a new skill."""
        if skill.name in cls._skills:
            print(f"Warning: Overwriting existing skill '{skill.name}'")
        cls._skills[skill.name] = skill
        print(f"Registered skill: {skill.name}")

    @classmethod
    def get_skill(cls, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        return cls._skills.get(name)

    @classmethod
    def list_skills(cls) -> Dict[str, Dict[str, Any]]:
        """List all registered skills metadata."""
        return {name: skill.to_json() for name, skill in cls._skills.items()}

    @classmethod
    def clear(cls):
        """Clear all registered skills."""
        cls._skills = {}
