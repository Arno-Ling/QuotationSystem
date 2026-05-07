"""
Safe Jinja2 template evaluation for workflow parameters and conditions.

All expressions run in a `SandboxedEnvironment` with:
- Statement tags (`{% %}`) disabled; only `{{ }}` expressions allowed
- Access to `os`, `sys`, `subprocess`, `__import__`, `open`, `eval`, `exec`,
  and dunder attributes (`__class__`, `__mro__`, etc.) forbidden
- Undefined variables raise `TemplateRenderError` rather than silently
  returning None

Requirements: REQ-009, REQ-054, REQ-055, REQ-068
"""
from __future__ import annotations

import logging
from typing import Any

from jinja2 import StrictUndefined
from jinja2.exceptions import TemplateError, TemplateSyntaxError
from jinja2.sandbox import SandboxedEnvironment

from .errors import SecurityError, TemplateRenderError
from .models import WorkflowContext

logger = logging.getLogger(__name__)


# Forbidden attribute/name fragments. Any of these in a rendered template
# indicates a sandbox-escape attempt.
_FORBIDDEN_FRAGMENTS = (
    "os.",
    "sys.",
    "subprocess",
    "__import__",
    "__class__",
    "__mro__",
    "__bases__",
    "__subclasses__",
    "__globals__",
    "__builtins__",
    "__dict__",
    "__code__",
    "eval(",
    "exec(",
    "open(",
    "compile(",
)


class _HardenedSandbox(SandboxedEnvironment):
    """SandboxedEnvironment with extra hardening for our use case."""

    # Disable statement tags so only `{{ expression }}` is usable
    block_start_string = "<BLOCK_DISABLED>"
    block_end_string = "<BLOCK_DISABLED>"

    def is_safe_attribute(self, obj: Any, attr: str, value: Any) -> bool:
        """Block dunder attributes entirely."""
        if attr.startswith("_"):
            return False
        return super().is_safe_attribute(obj, attr, value)


def _build_env() -> SandboxedEnvironment:
    env = _HardenedSandbox(
        autoescape=False,
        undefined=StrictUndefined,
    )
    # Explicitly clear access to dangerous globals
    env.globals.clear()
    return env


_ENV = _build_env()


def _pre_validate(expr: str) -> None:
    """Reject obviously dangerous expressions before compilation."""
    for frag in _FORBIDDEN_FRAGMENTS:
        if frag in expr:
            raise SecurityError(
                f"Expression contains forbidden fragment: {frag!r} in {expr!r}"
            )


def _render(template_str: str, context_vars: dict[str, Any]) -> str:
    """Render a single Jinja2 template string.

    Raises:
        TemplateRenderError: on syntax errors, undefined vars, or runtime errors.
        SecurityError: on sandbox violations.
    """
    _pre_validate(template_str)
    try:
        template = _ENV.from_string(template_str)
        return template.render(**context_vars)
    except SecurityError:
        raise
    except TemplateSyntaxError as e:
        raise TemplateRenderError(template_str, e) from e
    except TemplateError as e:
        raise TemplateRenderError(template_str, e) from e
    except Exception as e:  # pragma: no cover - catch-all
        # Jinja2 may raise arbitrary exceptions from user expressions
        raise TemplateRenderError(template_str, e) from e


def _context_to_vars(context: WorkflowContext) -> dict[str, Any]:
    """Flatten WorkflowContext into template variables."""
    return {
        "inputs": context.inputs,
        "outputs": context.outputs,
        "variables": context.variables,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_string(template_str: str, context: WorkflowContext) -> str:
    """Render a single template to a string."""
    return _render(template_str, _context_to_vars(context))


def render_value(value: Any, context: WorkflowContext) -> Any:
    """Render a value that may be a template string, dict, or list.

    - If `value` is a string containing `{{`, render it as a template.
    - If `value` is a dict/list, recurse into its items.
    - Otherwise return value unchanged.
    """
    if isinstance(value, str):
        if "{{" in value:
            return _render(value, _context_to_vars(context))
        return value
    if isinstance(value, dict):
        return {k: render_value(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [render_value(v, context) for v in value]
    return value


def render_params(
    params: dict[str, Any], context: WorkflowContext,
) -> dict[str, Any]:
    """Render an entire params dict. REQ-009."""
    return render_value(params, context)  # type: ignore[return-value]


def render_bool(expr: str, context: WorkflowContext) -> bool:
    """Render a template expression and coerce the result to a bool.

    This is used by DecisionNode / Edge conditions. The template is wrapped
    in `{{ ... }}` if it doesn't already contain one.
    """
    # Allow raw expressions (no {{ }}) or full templates
    template_str = expr if "{{" in expr else f"{{{{ ({expr}) }}}}"
    rendered = _render(template_str, _context_to_vars(context))
    stripped = rendered.strip().lower()
    if stripped in ("true", "1", "yes"):
        return True
    if stripped in ("false", "0", "no", ""):
        return False
    # Non-trivial string counts as True
    return True
