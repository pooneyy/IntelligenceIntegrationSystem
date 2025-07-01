import logging
from typing import Tuple
from pydantic import BaseModel, ValidationError


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def check_sanitize_dict(data: dict, verifier: BaseModel) -> Tuple[dict, str]:
    try:
        validated_data = verifier.model_validate(data).model_dump(exclude_unset=True, exclude_none=True)
        return validated_data, ''
    except ValidationError as e:
        logger.error(f'Collected data field missing: {str(e)}')
        return {}, str(e)
    except Exception as e:
        logger.error(f'Validate Collected data fail: {str(e)}')
        return {}, str(e)