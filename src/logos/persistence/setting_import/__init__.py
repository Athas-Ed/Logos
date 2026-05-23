"""设定导入 HDL：entity_template 校验与 setting_entry 渲染。"""

from __future__ import annotations

from .overlap import scan_import_overlap, unit_draft_rel_path
from .profile import EntityTemplateProfile, load_entity_template_profile
from .render import RenderedUnit, render_batch_to_setting_entry
from .validate import PipelineValidationError, validate_import_batch

__all__ = [
    "EntityTemplateProfile",
    "PipelineValidationError",
    "RenderedUnit",
    "load_entity_template_profile",
    "render_batch_to_setting_entry",
    "scan_import_overlap",
    "unit_draft_rel_path",
    "validate_import_batch",
]
