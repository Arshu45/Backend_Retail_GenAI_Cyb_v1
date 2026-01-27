import os
import re
from typing import Dict, Optional

class PromptLoader:
    """Loads and parses prompts from a markdown file."""
    
    def __init__(self, file_path: Optional[str] = None):
        if not file_path:
            # Default path relative to this file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(current_dir, "prompts.md")
        
        self.file_path = file_path
        self._prompts: Dict[str, str] = {}
        self._load_prompts()

    def _load_prompts(self):
        """Parses the markdown file for level-2 headers and their contents."""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Prompts file not found at: {self.file_path}")

        with open(self.file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Split by level-2 headers
        # Matches "## PROMPT_NAME" followed by content until the next "## " or end of file
        chunks = re.split(r'^##\s+', content, flags=re.MULTILINE)
        
        for chunk in chunks:
            if not chunk.strip():
                continue
            
            lines = chunk.split("\n", 1)
            if len(lines) < 2:
                continue
            
            prompt_name = lines[0].strip()
            prompt_content = lines[1].strip()
            
            self._prompts[prompt_name] = prompt_content

    def get_prompt(self, name: str) -> str:
        """Retrieves a prompt by its header name."""
        if name not in self._prompts:
            raise KeyError(f"Prompt '{name}' not found in {self.file_path}")
        return self._prompts[name]

# Singleton instance for easy access
_loader = PromptLoader()

def get_prompt(name: str) -> str:
    """Convenience function to get a prompt from the default loader."""
    return _loader.get_prompt(name)
