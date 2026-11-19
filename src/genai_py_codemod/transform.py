"""libcst transformers: structure (stage A), renamed types (stage B) and imports (stage C).

Stage A rewrites configure/init, model handles and their calls. Stage B renames types such as
``HarmCategory``. Stage C removes old imports that are no longer used and adds ``from google import genai`` /
``from google.genai import types`` where needed. Every stage is a separate parse so each one stays small.
"""

from __future__ import annotations

from collections.abc import Sequence

import libcst as cst
from libcst.metadata import ParentNodeProvider, PositionProvider, QualifiedNameProvider

from . import symbols
from .config_args import (
    ConfigItem,
    ConfigResult,
    Unsupported,
    call_of,
    comment_of,
    convert_config,
    convert_history,
    keyword_arg,
    layout_call,
)
from .report import Finding, make_finding
from .tracker import Analysis, Handle, import_module_name, split_constructor

ONE_LINE = cst.Call(func=cst.Name("x"), args=[])


def attr_chain(*parts: str) -> cst.BaseExpression:
    node: cst.BaseExpression = cst.Name(parts[0])
    for part in parts[1:]:
        node = cst.Attribute(value=node, attr=cst.Name(part))
    return node


def bind_args(
    updated: cst.Call,
    original: cst.Call,
    positional: Sequence[str],
    keywords: Sequence[str],
) -> dict[str, tuple[cst.Arg, cst.Arg]]:
    """Map old-call arguments to parameter names; unknown or ``*``/``**`` arguments are unsupported."""
    bound: dict[str, tuple[cst.Arg, cst.Arg]] = {}
    index = 0
    for arg, orig in zip(updated.args, original.args, strict=True):
        if arg.star:
            raise Unsupported("call-kwargs", orig)
        if arg.keyword is None:
            if index >= len(positional):
                raise Unsupported("call-args", orig)
            name = positional[index]
            index += 1
        else:
            name = arg.keyword.value
            if name not in keywords and name not in positional:
                raise Unsupported("call-args", orig)
        if name in bound:
            raise Unsupported("call-args", orig)
        bound[name] = (arg, orig)
    return bound


def drop_arg(args: Sequence[cst.Arg], index: int) -> list[cst.Arg]:
    """Remove one argument and keep the closing layout of the call."""
    remaining = list(args)
    removed = remaining.pop(index)
    if index == len(args) - 1 and remaining:
        remaining[-1] = remaining[-1].with_changes(
            comma=removed.comma, whitespace_after_arg=removed.whitespace_after_arg
        )
    return remaining


def is_true(node: cst.BaseExpression) -> bool:
    return isinstance(node, cst.Name) and node.value == "True"


def is_false(node: cst.BaseExpression) -> bool:
    return isinstance(node, cst.Name) and node.value == "False"


class Migrator(cst.CSTTransformer):
    """Stage A: configure/init -> Client, handles -> model names, calls -> client.*"""

    METADATA_DEPENDENCIES = (QualifiedNameProvider, PositionProvider, ParentNodeProvider)

    def __init__(self, analysis: Analysis, path: str, api_version: str) -> None:
        super().__init__()
        self.a = analysis
        self.path = path
        self.api_version = api_version
        self.findings: list[Finding] = []
        self.done: set[cst.CSTNode] = set()
        self.kind = "vertex" if "vertex" in analysis.kinds and "developer" not in analysis.kinds else "developer"
        self.types_name = analysis.types_name
        self.genai_name = analysis.genai_name
        self._taken = set(analysis.names)
        self.client_name = self._fresh("client", "genai_client")
        self.client_defined = False
        self.client_used = False
        self.config_vars: dict[Handle, str] = {}
        for handle in analysis.handles.values():
            if handle.has_config:
                suffix = "CONFIG" if handle.name.isupper() else "config"
                self.config_vars[handle] = self._fresh(f"{handle.name}_{suffix}", f"{handle.name}_generate_{suffix}")

    # -- helpers ---------------------------------------------------------------------------------
    def _fresh(self, preferred: str, alternative: str) -> str:
        name = preferred if preferred not in self._taken else alternative
        counter = 2
        while name in self._taken:
            name = f"{alternative}_{counter}"
            counter += 1
        self._taken.add(name)
        return name

    def qualified(self, node: cst.CSTNode) -> set[str]:
        return {q.name for q in self.get_metadata(QualifiedNameProvider, node, set())}

    def report(self, node: cst.CSTNode, code: str) -> None:
        position = self.get_metadata(PositionProvider, node).start
        finding = make_finding(self.path, position.line, position.column, code)
        if finding not in self.findings:
            self.findings.append(finding)

    def types_ref(self, attr: str) -> cst.Attribute:
        return cst.Attribute(value=cst.Name(self.types_name), attr=cst.Name(attr))

    def client_attr(self, *parts: str) -> cst.BaseExpression:
        return attr_chain(self.client_name, *parts)

    def http_options_arg(self) -> cst.Arg | None:
        version = None
        if self.kind == "developer":
            if self.api_version == "keep" or (self.api_version == "auto" and self.a.beta_models):
                version = "v1beta"
        elif self.api_version == "keep":
            version = "v1"
        if version is None:
            return None
        options = call_of(self.types_name, "HttpOptions", [keyword_arg("api_version", cst.SimpleString(f'"{version}"'))])
        return keyword_arg("http_options", options)

    def _convert_config(self, items: list[ConfigItem], template: cst.Call | None = None) -> ConfigResult | None:
        return convert_config(items, self.types_name, self.qualified, template)

    def _config_call(self, result: ConfigResult, template: cst.Call) -> cst.Call:
        func = self.types_ref("GenerateContentConfig")
        if result.own_layout and result.whitespace_before_args is not None:
            return cst.Call(func=func, args=result.args, whitespace_before_args=result.whitespace_before_args)
        return layout_call(func, result.args, template)

    # -- statements ------------------------------------------------------------------------------
    def leave_SimpleStatementLine(
        self, original_node: cst.SimpleStatementLine, updated_node: cst.SimpleStatementLine
    ) -> cst.BaseStatement | cst.FlattenSentinel[cst.BaseStatement]:
        handle = self.a.handles.get(original_node)
        if handle is not None:
            return self._convert_handle(original_node, updated_node, handle)
        if len(original_node.body) == 1 and isinstance(original_node.body[0], cst.Expr):
            call = original_node.body[0].value
            if call in self.a.configure_calls or call in self.a.init_calls:
                return self._convert_client(original_node, updated_node, call)
        return updated_node

    def _convert_client(
        self, original: cst.SimpleStatementLine, updated: cst.SimpleStatementLine, call: cst.Call
    ) -> cst.BaseStatement:
        parent = self.get_metadata(ParentNodeProvider, original, None)
        if not isinstance(parent, cst.Module) or self.client_defined:
            self.report(call, "configure-scope")
            return updated
        updated_call = updated.body[0].value  # type: ignore[attr-defined]
        is_init = call in self.a.init_calls
        try:
            if is_init:
                bound = bind_args(updated_call, call, ("project", "location"), ("credentials",))
                new_args = [keyword_arg("vertexai", cst.Name("True"))]
                for name in ("project", "location", "credentials"):
                    if name in bound:
                        new_args.append(keyword_arg(name, bound[name][0].value))
            else:
                bound = bind_args(updated_call, call, ("api_key",), ())
                new_args = [keyword_arg("api_key", bound["api_key"][0].value)] if "api_key" in bound else []
        except Unsupported as error:
            self.report(error.node, "configure-args" if error.code == "call-args" else error.code)
            return updated
        http = self.http_options_arg()
        if http is not None:
            new_args.append(http)
        client_call = layout_call(attr_chain(self.genai_name, "Client"), new_args, updated_call)
        assign = cst.Assign(targets=[cst.AssignTarget(target=cst.Name(self.client_name))], value=client_call)
        self.client_defined = True
        self.done.add(call)
        return updated.with_changes(body=[assign])

    def _convert_handle(
        self, original: cst.SimpleStatementLine, updated: cst.SimpleStatementLine, handle: Handle
    ) -> cst.BaseStatement | cst.FlattenSentinel[cst.BaseStatement]:
        assign = updated.body[0]
        assert isinstance(assign, cst.Assign) and isinstance(assign.value, cst.Call)
        ctor = assign.value
        try:
            model_arg, items = split_constructor(ctor, handle.ctor)
            config = self._convert_config(items, ctor)
        except Unsupported as error:
            self.report(handle.ctor, error.code)
            return updated
        assert model_arg is not None
        comments = [text for text in (comment_of(arg.comma) for arg in ctor.args) if text]
        model_stmt = updated.with_changes(body=[assign.with_changes(value=model_arg.value)])
        self.done.add(handle.ctor)
        if config is None:
            return model_stmt
        trailing = cst.TrailingWhitespace(
            whitespace=cst.SimpleWhitespace("  "),
            comment=cst.Comment("  ".join(comments)) if comments else None,
            newline=cst.Newline(),
        )
        config_assign = cst.Assign(
            targets=[cst.AssignTarget(target=cst.Name(self.config_vars[handle]))],
            value=self._config_call(config, ctor),
        )
        config_stmt = cst.SimpleStatementLine(body=[config_assign], trailing_whitespace=trailing if comments else cst.TrailingWhitespace())
        return cst.FlattenSentinel([model_stmt.with_changes(leading_lines=updated.leading_lines), config_stmt])

    # -- calls ---------------------------------------------------------------------------------------
    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.BaseExpression:
        try:
            return self._convert_call(original_node, updated_node)
        except Unsupported as error:
            self.report(original_node, error.code)
            return updated_node

    def _convert_call(self, original: cst.Call, updated: cst.Call) -> cst.BaseExpression:
        func = original.func
        if original in self.a.handled_calls and self.qualified(func) & symbols.EMBED_CONTENT:
            return self._convert_embed(original, updated)
        if not isinstance(func, cst.Attribute) or not isinstance(updated.func, cst.Attribute):
            return updated
        method = func.attr.value
        target = func.value
        if isinstance(target, cst.Name) and target in self.a.model_access:
            handle = self.a.model_access[target]
            return self._model_method(original, updated, method, handle, None, None)
        if isinstance(target, cst.Name) and target in self.a.chat_access:
            return self._chat_method(original, updated, method)
        if original in self.a.inline_calls:
            ctor = self.a.inline_calls[original]
            ctor_updated = updated.func.value
            if not isinstance(ctor_updated, cst.Call):
                return updated
            return self._model_method(original, updated, method, None, ctor, ctor_updated)
        return updated

    def _model_method(
        self,
        original: cst.Call,
        updated: cst.Call,
        method: str,
        handle: Handle | None,
        ctor: cst.Call | None,
        ctor_updated: cst.Call | None,
    ) -> cst.BaseExpression:
        # Where the model name and the configuration come from.
        inline_config: ConfigResult | None = None
        if handle is not None:
            model_value: cst.BaseExpression = cst.Name(handle.name)
            config_name = self.config_vars.get(handle)
            has_system_or_tools = handle.has_system_or_tools
        else:
            assert ctor is not None and ctor_updated is not None
            model_arg, ctor_items = split_constructor(ctor_updated, ctor)
            if model_arg is None:
                raise Unsupported("call-args", ctor)
            model_value = model_arg.value
            inline_config = self._convert_config(ctor_items, ctor_updated)
            if inline_config is not None:
                inline_config.own_layout = False  # the config is embedded in a call argument: keep it compact
            config_name = None
            has_system_or_tools = bool(inline_config and inline_config.has_system_or_tools)
            self.done.add(ctor)
        self.client_used = True

        if method in ("generate_content", "generate_content_async"):
            bound = bind_args(
                updated,
                original,
                ("contents",),
                ("stream", *symbols.CALL_CONFIG_KEYWORDS),
            )
            if "contents" not in bound:
                raise Unsupported("call-args", original)
            stream = False
            if "stream" in bound:
                value = bound["stream"][0].value
                if is_true(value):
                    stream = True
                elif not is_false(value):
                    raise Unsupported("call-args", bound["stream"][1])
            call_items = [
                ConfigItem(name, bound[name][0], bound[name][1]) for name in symbols.CALL_CONFIG_KEYWORDS if name in bound
            ]
            call_config = self._convert_config(call_items) if call_items else None
            has_handle_config = config_name is not None or inline_config is not None
            if call_config is not None and has_handle_config:
                raise Unsupported("call-config-merge", original)
            new_args = [keyword_arg("model", model_value), keyword_arg("contents", bound["contents"][0].value)]
            if config_name is not None:
                new_args.append(keyword_arg("config", cst.Name(config_name)))
            elif inline_config is not None:
                new_args.append(keyword_arg("config", self._config_call(inline_config, ONE_LINE)))
            elif call_config is not None:
                new_args.append(keyword_arg("config", self._config_call(call_config, ONE_LINE)))
            name = "generate_content_stream" if stream else "generate_content"
            if method == "generate_content_async":
                func = self.client_attr("aio", "models", name)
            else:
                func = self.client_attr("models", name)
            return layout_call(func, new_args, updated)

        if method == "count_tokens":
            bound = bind_args(updated, original, ("contents",), ())
            if "contents" not in bound:
                raise Unsupported("call-args", original)
            if has_system_or_tools:
                raise Unsupported("count-tokens-semantics", original)
            new_args = [keyword_arg("model", model_value), keyword_arg("contents", bound["contents"][0].value)]
            return layout_call(self.client_attr("models", "count_tokens"), new_args, updated)

        if method == "start_chat":
            bound = bind_args(updated, original, ("history",), ())
            new_args = [keyword_arg("model", model_value)]
            if config_name is not None:
                new_args.append(keyword_arg("config", cst.Name(config_name)))
            if "history" in bound:
                new_args.append(keyword_arg("history", convert_history(bound["history"][0].value)))
            return layout_call(self.client_attr("chats", "create"), new_args, updated)
        return updated

    def _chat_method(self, original: cst.Call, updated: cst.Call, method: str) -> cst.BaseExpression:
        if method != "send_message":
            return updated
        bound = bind_args(updated, original, ("content",), ("stream",))
        stream = False
        if "stream" in bound:
            value = bound["stream"][0].value
            if is_true(value):
                stream = True
            elif not is_false(value):
                raise Unsupported("call-args", bound["stream"][1])
        args = list(updated.args)
        if "stream" in bound:
            args = drop_arg(args, args.index(bound["stream"][0]))
        func = updated.func
        assert isinstance(func, cst.Attribute)
        if stream:
            func = func.with_changes(attr=cst.Name("send_message_stream"))
        return updated.with_changes(func=func, args=args)

    def _convert_embed(self, original: cst.Call, updated: cst.Call) -> cst.BaseExpression:
        bound = bind_args(updated, original, ("model", "content"), ("task_type", "title", "output_dimensionality"))
        if "model" not in bound or "content" not in bound:
            raise Unsupported("call-args", original)
        new_args = [keyword_arg("model", bound["model"][0].value), keyword_arg("contents", bound["content"][0].value)]
        extra = []
        for name in ("task_type", "title", "output_dimensionality"):
            if name not in bound:
                continue
            value = bound[name][0].value
            if name == "task_type" and isinstance(value, cst.SimpleString):
                # the old SDK accepts "retrieval_document"; google-genai sends the text as is and the API wants the enum name
                value = value.with_changes(value=f"{value.prefix}{value.quote}{value.raw_value.upper()}{value.quote}")
            extra.append(keyword_arg(name, value))
        if extra:
            config = layout_call(self.types_ref("EmbedContentConfig"), extra, ONE_LINE)
            new_args.append(keyword_arg("config", config))
        self.client_used = True
        self.done.add(original)
        self.report(original, "response-shape")
        return layout_call(self.client_attr("models", "embed_content"), new_args, updated)

    # -- module end --------------------------------------------------------------------------------------
    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        for call in self.a.handled_calls:
            if call not in self.done:
                self.report(call, "legacy-api")
        if self.client_used and not self.client_defined:
            args: list[cst.Arg] = [keyword_arg("vertexai", cst.Name("True"))] if self.kind == "vertex" else []
            http = self.http_options_arg()
            if http is not None:
                args.append(http)
            client_call = layout_call(attr_chain(self.genai_name, "Client"), args, ONE_LINE)
            statement = cst.SimpleStatementLine(
                body=[cst.Assign(targets=[cst.AssignTarget(target=cst.Name(self.client_name))], value=client_call)]
            )
            body = list(updated_node.body)
            position = _after_last_import(body)
            blank = [cst.EmptyLine()] if position < len(body) else []
            body.insert(position, statement.with_changes(leading_lines=blank))
            following = position + 1
            if following < len(body) and isinstance(body[following], (cst.FunctionDef, cst.ClassDef)):
                missing = 2 - sum(1 for line in body[following].leading_lines if not line.comment)
                if missing > 0 and not body[following].leading_lines:
                    body[following] = body[following].with_changes(leading_lines=[cst.EmptyLine()] * missing)
            return updated_node.with_changes(body=body)
        return updated_node


def _after_last_import(body: Sequence[cst.BaseStatement]) -> int:
    last = -1
    for index, statement in enumerate(body):
        if isinstance(statement, cst.SimpleStatementLine) and any(
            isinstance(item, (cst.Import, cst.ImportFrom)) for item in statement.body
        ):
            last = index
    return last + 1 if last >= 0 else 0


class TypeRenamer(cst.CSTTransformer):
    """Stage B: ``HarmCategory`` and friends -> ``types.HarmCategory`` (also ``GenerationConfig``)."""

    METADATA_DEPENDENCIES = (QualifiedNameProvider, ParentNodeProvider)

    def __init__(self, types_name: str) -> None:
        super().__init__()
        self.types_name = types_name

    def visit_Import(self, node: cst.Import) -> bool:
        return False

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:
        return False

    def _target(self, node: cst.CSTNode) -> str | None:
        for qualified in self.get_metadata(QualifiedNameProvider, node, set()):
            if qualified.name in symbols.RENAMED_TYPES:
                return symbols.RENAMED_TYPES[qualified.name]
        return None

    def leave_Attribute(self, original_node: cst.Attribute, updated_node: cst.Attribute) -> cst.BaseExpression:
        target = self._target(original_node)
        if target is None:
            return updated_node
        return cst.Attribute(value=cst.Name(self.types_name), attr=cst.Name(target))

    def leave_Name(self, original_node: cst.Name, updated_node: cst.Name) -> cst.BaseExpression:
        parent = self.get_metadata(ParentNodeProvider, original_node, None)
        if isinstance(parent, cst.Attribute) and parent.attr is original_node:
            return updated_node
        if isinstance(parent, cst.Arg) and parent.keyword is original_node:
            return updated_node
        target = self._target(original_node)
        if target is None:
            return updated_node
        return cst.Attribute(value=cst.Name(self.types_name), attr=cst.Name(target))


class _NameCollector(cst.CSTVisitor):
    """Names used in code (outside import statements, attribute names and keyword names)."""

    def __init__(self) -> None:
        super().__init__()
        self.used: set[str] = set()
        self._skip: set[cst.CSTNode] = set()

    def visit_Import(self, node: cst.Import) -> bool:
        return False

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:
        return False

    def visit_Attribute(self, node: cst.Attribute) -> None:
        self._skip.add(node.attr)

    def visit_Arg(self, node: cst.Arg) -> None:
        if node.keyword is not None:
            self._skip.add(node.keyword)

    def visit_Name(self, node: cst.Name) -> None:
        if node not in self._skip:
            self.used.add(node.value)


def fix_imports(code: str, types_name: str, genai_name: str) -> str:
    """Stage C: drop unused old-SDK imports, add the new ones where the code needs them."""
    module = cst.parse_module(code)
    collector = _NameCollector()
    module.visit(collector)
    used = collector.used

    body: list[cst.BaseStatement] = []
    bound: set[str] = set()
    first_removed: int | None = None
    removed_style: cst.SimpleStatementLine | None = None
    for statement in module.body:
        if isinstance(statement, cst.SimpleStatementLine):
            kept: list[cst.BaseSmallStatement] = []
            touched = False
            for item in statement.body:
                if isinstance(item, (cst.Import, cst.ImportFrom)) and import_module_name(item):
                    touched = True
                    # genai / types now name the new SDK, so the old binding of those names is dead.
                    pruned = _prune_import(item, used - {genai_name, types_name})
                    if pruned is not None:
                        kept.append(pruned)
                else:
                    kept.append(item)
            if touched and not kept:
                if first_removed is None:
                    first_removed = len(body)
                    removed_style = statement
                continue
            if touched:
                statement = statement.with_changes(body=kept)
            for item in statement.body:
                bound.update(_bound_names(item))
        body.append(statement)

    additions: list[cst.SimpleStatementLine] = []
    if genai_name in used and genai_name not in bound:
        additions.append(_import_statement("google", "genai", genai_name))
    if types_name in used and types_name not in bound:
        additions.append(_import_statement("google.genai", "types", types_name))
    if additions:
        if first_removed is not None and removed_style is not None:
            additions[0] = additions[0].with_changes(
                leading_lines=removed_style.leading_lines, trailing_whitespace=removed_style.trailing_whitespace
            )
            body[first_removed:first_removed] = additions
        else:
            position = _after_last_import(body)
            body[position:position] = additions
    return module.with_changes(body=body).code


def _import_statement(module: str, name: str, alias: str) -> cst.SimpleStatementLine:
    text = f"from {module} import {name}" + ("" if alias == name else f" as {alias}")
    statement = cst.parse_statement(text + "\n")
    assert isinstance(statement, cst.SimpleStatementLine)
    return statement


def _bound_names(item: cst.BaseSmallStatement) -> set[str]:
    names: set[str] = set()
    if isinstance(item, cst.Import):
        for alias in item.names:
            if alias.asname is not None and isinstance(alias.asname.name, cst.Name):
                names.add(alias.asname.name.value)
            else:
                first = alias.name
                while isinstance(first, cst.Attribute):
                    first = first.value
                if isinstance(first, cst.Name):
                    names.add(first.value)
    elif isinstance(item, cst.ImportFrom) and not isinstance(item.names, cst.ImportStar):
        for alias in item.names:
            if alias.asname is not None and isinstance(alias.asname.name, cst.Name):
                names.add(alias.asname.name.value)
            elif isinstance(alias.name, cst.Name):
                names.add(alias.name.value)
    return names


def _prune_import(item: cst.Import | cst.ImportFrom, used: set[str]) -> cst.BaseSmallStatement | None:
    """Keep only the imported names that code still uses; ``None`` when nothing is left."""
    if isinstance(item, cst.ImportFrom) and isinstance(item.names, cst.ImportStar):
        return item
    aliases = list(item.names)  # type: ignore[arg-type]
    kept = [alias for alias in aliases if _bound_names_of_alias(item, alias) & used]
    if not kept:
        return None
    if len(kept) == len(aliases):
        return item
    kept[-1] = kept[-1].with_changes(comma=cst.MaybeSentinel.DEFAULT)
    return item.with_changes(names=kept)


def _bound_names_of_alias(item: cst.Import | cst.ImportFrom, alias: cst.ImportAlias) -> set[str]:
    probe = item.with_changes(names=[alias.with_changes(comma=cst.MaybeSentinel.DEFAULT)])
    return _bound_names(probe)
