"""Turn old-SDK configuration arguments into ``types.GenerateContentConfig`` arguments.

Everything here works on libcst nodes and keeps the user's whitespace and comments where it can:
dict elements keep their commas (and trailing comments), the new call reuses the layout of the call
it replaces.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import libcst as cst

from . import symbols

NO_SPACE_EQUAL = cst.AssignEqual(
    whitespace_before=cst.SimpleWhitespace(""), whitespace_after=cst.SimpleWhitespace("")
)

# Fields that `generation_config` (dict or class) may carry and `GenerateContentConfig` accepts as keywords.
GENERATION_FIELDS = frozenset(
    {
        "candidate_count",
        "stop_sequences",
        "max_output_tokens",
        "temperature",
        "top_p",
        "top_k",
        "response_mime_type",
        "response_schema",
        "response_json_schema",
        "presence_penalty",
        "frequency_penalty",
        "response_logprobs",
        "logprobs",
        "seed",
        "response_modalities",
        "thinking_config",
        "media_resolution",
        "speech_config",
        "audio_timestamp",
    }
)


class Unsupported(Exception):
    """The configuration cannot be converted safely; carries a reason code and the offending node."""

    def __init__(self, code: str, node: cst.CSTNode) -> None:
        super().__init__(code)
        self.code = code
        self.node = node


@dataclass
class ConfigItem:
    """One keyword argument of the old call: its name, the (possibly rewritten) arg and the original arg."""

    keyword: str
    arg: cst.Arg
    original: cst.Arg


@dataclass
class ConfigResult:
    args: list[cst.Arg]
    #: True when the args keep the layout of a single dict / class call they were spread from.
    own_layout: bool
    whitespace_before_args: cst.BaseParenthesizableWhitespace | None
    has_system_or_tools: bool


QualifiedNames = Callable[[cst.CSTNode], set[str]]


def type_ref(types_name: str, attr: str) -> cst.Attribute:
    return cst.Attribute(value=cst.Name(types_name), attr=cst.Name(attr))


def keyword_arg(name: str, value: cst.BaseExpression, *, comma: cst.Comma | cst.MaybeSentinel = cst.MaybeSentinel.DEFAULT) -> cst.Arg:
    """A ``name=value`` argument without spaces around ``=`` (PEP 8 style)."""
    return cst.Arg(keyword=cst.Name(name), value=value, equal=NO_SPACE_EQUAL, comma=comma)


def call_of(types_name: str, attr: str, args: Sequence[cst.Arg] = ()) -> cst.Call:
    return cst.Call(func=type_ref(types_name, attr), args=list(args))


def comment_of(comma: cst.Comma | cst.MaybeSentinel) -> str | None:
    if isinstance(comma, cst.Comma) and isinstance(comma.whitespace_after, cst.ParenthesizedWhitespace):
        comment = comma.whitespace_after.first_line.comment
        if comment is not None:
            return comment.value
    return None


def clean_comma(comma: cst.Comma) -> cst.Comma:
    """Copy of a comma without a trailing comment (so the comment is not duplicated)."""
    whitespace = comma.whitespace_after
    if isinstance(whitespace, cst.ParenthesizedWhitespace):
        whitespace = whitespace.with_changes(
            first_line=cst.TrailingWhitespace(whitespace=cst.SimpleWhitespace(""), comment=None, newline=cst.Newline()),
            empty_lines=[],
        )
    return comma.with_changes(whitespace_after=whitespace)


def layout_call(func: cst.BaseExpression, args: Sequence[cst.Arg], template: cst.Call) -> cst.Call:
    """Build ``func(args)`` that looks like ``template`` (one-line or one-argument-per-line)."""
    new_args = list(args)
    before = template.whitespace_before_args
    if isinstance(before, cst.ParenthesizedWhitespace):
        inner = cst.Comma(
            whitespace_after=cst.ParenthesizedWhitespace(
                first_line=cst.TrailingWhitespace(),
                indent=before.indent,
                last_line=before.last_line,
            )
        )
    else:
        inner = cst.Comma(whitespace_after=cst.SimpleWhitespace(" "))
    for index, arg in enumerate(new_args):
        last = index == len(new_args) - 1
        if not last:
            keep = isinstance(arg.comma, cst.Comma) and comment_of(arg.comma) is not None
            new_args[index] = arg.with_changes(
                comma=arg.comma if keep else inner, whitespace_after_arg=cst.SimpleWhitespace("")
            )
        else:
            if template.args:
                tail = template.args[-1]
                new_args[index] = arg.with_changes(
                    comma=tail.comma if isinstance(tail.comma, cst.Comma) else cst.MaybeSentinel.DEFAULT,
                    whitespace_after_arg=tail.whitespace_after_arg,
                )
            else:
                new_args[index] = arg.with_changes(comma=cst.MaybeSentinel.DEFAULT)
    return cst.Call(func=func, args=new_args, whitespace_before_args=before)


def _string_value(node: cst.BaseExpression) -> str | None:
    if isinstance(node, cst.SimpleString):
        value = node.evaluated_value
        return value if isinstance(value, str) else None
    return None


def _spread_dict(node: cst.Dict) -> tuple[list[cst.Arg], cst.BaseParenthesizableWhitespace]:
    args: list[cst.Arg] = []
    for element in node.elements:
        if not isinstance(element, cst.DictElement):
            raise Unsupported("config-dynamic", element)
        key = _string_value(element.key)
        if key is None or key not in GENERATION_FIELDS:
            raise Unsupported("config-dynamic", element)
        args.append(keyword_arg(key, element.value, comma=element.comma))
    if args:
        last = args[-1]
        args[-1] = last.with_changes(whitespace_after_arg=node.rbrace.whitespace_before)
    return args, node.lbrace.whitespace_after


def _dedent(whitespace: cst.BaseParenthesizableWhitespace, unit: int) -> cst.BaseParenthesizableWhitespace:
    """Remove ``unit`` leading spaces from the indentation of a multi-line whitespace."""
    if isinstance(whitespace, cst.ParenthesizedWhitespace):
        value = whitespace.last_line.value
        return whitespace.with_changes(last_line=cst.SimpleWhitespace(value[unit:] if len(value) >= unit else ""))
    return whitespace


def _dedent_arg(arg: cst.Arg, unit: int) -> cst.Arg:
    comma = arg.comma
    if isinstance(comma, cst.Comma):
        comma = comma.with_changes(whitespace_after=_dedent(comma.whitespace_after, unit))
    return arg.with_changes(comma=comma, whitespace_after_arg=_dedent(arg.whitespace_after_arg, unit))


def indent_unit(template: cst.Call | None) -> int | None:
    """Width of one indentation level in a multi-line call, or None when the call is on one line."""
    if template is None or not isinstance(template.whitespace_before_args, cst.ParenthesizedWhitespace):
        return None
    inner = len(template.whitespace_before_args.last_line.value)
    outer = 0
    if template.args:
        tail = template.args[-1]
        if isinstance(tail.comma, cst.Comma) and isinstance(tail.comma.whitespace_after, cst.ParenthesizedWhitespace):
            outer = len(tail.comma.whitespace_after.last_line.value)
        elif isinstance(tail.whitespace_after_arg, cst.ParenthesizedWhitespace):
            outer = len(tail.whitespace_after_arg.last_line.value)
    return inner - outer if inner > outer else None


def _convert_generation_config(
    item: ConfigItem, qualified: QualifiedNames, unit: int | None
) -> tuple[list[cst.Arg], cst.BaseParenthesizableWhitespace | None, bool]:
    """Returns (args, whitespace before the args, whether the source layout can be kept)."""
    value = item.arg.value
    original = item.original.value
    if isinstance(value, cst.Name) and value.value == "None":
        return [], None, False
    if isinstance(value, cst.Dict):
        args, before = _spread_dict(value)
        multiline = isinstance(before, cst.ParenthesizedWhitespace)
        if multiline and unit is not None:
            return [_dedent_arg(a, unit) for a in args], _dedent(before, unit), True
        return args, before, False
    if isinstance(value, cst.Call) and isinstance(original, cst.Call):
        if qualified(original.func) & symbols.GENERATION_CONFIG:
            args = []
            for arg in value.args:
                if arg.keyword is None or arg.star:
                    raise Unsupported("call-kwargs" if arg.star else "config-dynamic", arg)
                args.append(arg.with_changes(equal=NO_SPACE_EQUAL))
            before = value.whitespace_before_args
            if isinstance(before, cst.ParenthesizedWhitespace) and unit is not None:
                return [_dedent_arg(a, unit) for a in args], _dedent(before, unit), True
            return args, before, False
    raise Unsupported("config-dynamic", item.arg)


def _safety_name(node: cst.BaseExpression, table: dict[str, str], prefix: str) -> cst.BaseExpression:
    text = _string_value(node)
    if text is None:
        if isinstance(node, (cst.Attribute, cst.Name)):
            return node
        raise Unsupported("config-dynamic", node)
    lowered = text.lower()
    if text.startswith(prefix):
        return node
    if lowered in table:
        return cst.SimpleString(f'"{table[lowered]}"')
    if text.isupper() and "_" in text:
        return node
    raise Unsupported("config-dynamic", node)


def _convert_safety(item: ConfigItem, types_name: str) -> cst.BaseExpression:
    value = item.arg.value
    if isinstance(value, cst.List):
        return value
    if not isinstance(value, cst.Dict):
        raise Unsupported("config-dynamic", item.arg)
    elements: list[cst.Element] = []
    for element in value.elements:
        if not isinstance(element, cst.DictElement):
            raise Unsupported("config-dynamic", element)
        category = _safety_name(element.key, symbols.SAFETY_CATEGORY_NAMES, "HARM_CATEGORY_")
        threshold = _safety_name(element.value, symbols.SAFETY_THRESHOLD_NAMES, "BLOCK_")
        setting = call_of(
            types_name,
            "SafetySetting",
            [
                keyword_arg("category", category, comma=cst.Comma(whitespace_after=cst.SimpleWhitespace(" "))),
                keyword_arg("threshold", threshold),
            ],
        )
        elements.append(cst.Element(value=setting, comma=element.comma))
    return cst.List(
        elements=elements,
        lbracket=cst.LeftSquareBracket(whitespace_after=value.lbrace.whitespace_after),
        rbracket=cst.RightSquareBracket(whitespace_before=value.rbrace.whitespace_before),
    )


def _tool_expr(node: cst.BaseExpression, types_name: str) -> cst.BaseExpression:
    text = _string_value(node)
    if text is None:
        raise Unsupported("callable-tools-afc", node)
    if text not in symbols.TOOL_STRINGS:
        raise Unsupported("tools-unsupported", node)
    field_name, class_name = symbols.TOOL_STRINGS[text]
    inner = call_of(types_name, class_name)
    return call_of(types_name, "Tool", [keyword_arg(field_name, inner)])


def _convert_tools(item: ConfigItem, types_name: str) -> cst.BaseExpression:
    value = item.arg.value
    if isinstance(value, cst.SimpleString):
        return cst.List(elements=[cst.Element(value=_tool_expr(value, types_name))])
    if isinstance(value, cst.List):
        elements = [el.with_changes(value=_tool_expr(el.value, types_name)) for el in value.elements]
        return value.with_changes(elements=elements)
    raise Unsupported("callable-tools-afc", item.arg)


def _text_part(node: cst.BaseExpression) -> cst.BaseExpression:
    """``"hello"`` -> ``{"text": "hello"}``; dicts stay; anything else cannot be judged."""
    if isinstance(node, (cst.SimpleString, cst.ConcatenatedString, cst.FormattedString)):
        element = cst.DictElement(key=cst.SimpleString('"text"'), value=node)
        return cst.Dict(elements=[element])
    if isinstance(node, cst.Dict):
        return node
    raise Unsupported("history-format", node)


def convert_history(value: cst.BaseExpression) -> cst.BaseExpression:
    """Old chat history allows ``{"role": ..., "parts": ["text"]}``; google-genai wants ``{"text": ...}`` parts."""
    if isinstance(value, cst.Name) and value.value == "None":
        return value
    if not isinstance(value, cst.List):
        raise Unsupported("history-format", value)
    items: list[cst.Element] = []
    for element in value.elements:
        entry = element.value
        if not isinstance(entry, cst.Dict):
            raise Unsupported("history-format", entry)
        new_elements: list[cst.BaseDictElement] = []
        for pair in entry.elements:
            if isinstance(pair, cst.DictElement) and _string_value(pair.key) == "parts":
                parts = pair.value
                if isinstance(parts, (cst.SimpleString, cst.ConcatenatedString, cst.FormattedString)):
                    parts = cst.List(elements=[cst.Element(value=_text_part(parts))])
                elif isinstance(parts, cst.List):
                    parts = parts.with_changes(
                        elements=[part.with_changes(value=_text_part(part.value)) for part in parts.elements]
                    )
                else:
                    raise Unsupported("history-format", parts)
                pair = pair.with_changes(value=parts)
            new_elements.append(pair)
        items.append(element.with_changes(value=entry.with_changes(elements=new_elements)))
    return value.with_changes(elements=items)


def convert_config(
    items: Sequence[ConfigItem],
    types_name: str,
    qualified: QualifiedNames,
    template: cst.Call | None = None,
) -> ConfigResult | None:
    """Convert the configuration keywords of an old call; ``None`` means there is nothing to configure.

    ``template`` is the multi-line call the keywords came from; it lets a single spread dict keep its layout.
    """
    args: list[cst.Arg] = []
    own_layout = False
    whitespace_before: cst.BaseParenthesizableWhitespace | None = None
    has_system_or_tools = False
    pieces = 0
    unit = indent_unit(template)
    for item in items:
        if item.keyword == "generation_config":
            spread, whitespace, keeps_layout = _convert_generation_config(item, qualified, unit)
            if not spread:
                continue
            args.extend(spread)
            whitespace_before = whitespace
            own_layout = keeps_layout
            pieces += 1
        elif item.keyword == "safety_settings":
            args.append(keyword_arg("safety_settings", _convert_safety(item, types_name)))
            pieces += 1
        elif item.keyword == "system_instruction":
            if not (isinstance(item.arg.value, cst.Name) and item.arg.value.value == "None"):
                args.append(keyword_arg("system_instruction", item.arg.value))
                has_system_or_tools = True
                pieces += 1
        elif item.keyword == "tools":
            if not (isinstance(item.arg.value, cst.Name) and item.arg.value.value == "None"):
                args.append(keyword_arg("tools", _convert_tools(item, types_name)))
                has_system_or_tools = True
                pieces += 1
        elif item.keyword == "tool_config":
            raise Unsupported("tool-config", item.arg)
        else:
            raise Unsupported("call-args", item.arg)
    if not args:
        return None
    # Spread layout is only kept when the whole config came from exactly one dict / class call.
    own = own_layout and pieces == 1 and all(item.keyword == "generation_config" for item in items)
    return ConfigResult(args, own, whitespace_before if own else None, has_system_or_tools)
