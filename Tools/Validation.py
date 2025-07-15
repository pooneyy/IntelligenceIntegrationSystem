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
        error_details = []
        for error in e.errors():
            # 获取错误字段路径（如：field.sub_field）
            field_path = ".".join(map(str, error['loc']))
            error_msg = error['msg']
            error_type = error['type']
            error_details.append(f"Field [{field_path}]: {error_msg} (Type error: {error_type})")

        error_str = "; ".join(error_details)
        logger.error(f'Dict verification fail: {error_str}')
        return {}, error_str
    except Exception as e:
        logger.error(f'Dict verification got exception: {str(e)}')
        return {}, str(e)

