from typing import Tuple, Optional

from Tools.ContentHistory import save_content, generate_filepath, ContentDB


def to_file(title, content, category, suffix):
    filepath = generate_filepath(title, content, category, suffix)
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        if filepath.exists():
            filepath.unlink()
        raise RuntimeError(f"Content save failed: {str(e)}") from e


def to_file_and_history(url, content, title, category, suffix='.txt', db: Optional[ContentDB]=None) -> Tuple[bool, str]:
    return save_content(url, content, title, category, suffix, db)
