"""Find the old-SDK model handles and decide which ones can be rewritten safely.

Principle: if something cannot be followed to the end, nothing in the file is rewritten and the spot is reported.
A handle is followed when it is a single assignment to a plain name and every use is a direct method call
(``model.generate_content(...)``). Passing it to a function, returning it, storing it or reassigning it makes it
an "escape": turning ``model`` into a model-name string would silently change what the receiving code gets.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import libcst as cst
from libcst._metadata_dependent import LazyValue
from libcst.metadata import (
    Assignment,
    ImportAssignment,
    ParentNodeProvider,
    PositionProvider,
    QualifiedNameProvider,
    ScopeProvider,
)

from . import symbols
from .config_args import ConfigItem, Unsupported, convert_config
from .report import Finding, make_finding


@dataclass(eq=False)
class Handle:
    """A ``model = GenerativeModel(...)`` binding that will become a model-name string."""

    name: str
    ctor: cst.Call
    statement: cst.SimpleStatementLine
    kind: str
    has_system_or_tools: bool = False
    has_config: bool = False
    ok: bool = True


@dataclass(eq=False)
class ChatHandle:
    """A ``chat = model.start_chat(...)`` binding."""

    name: str
    call: cst.Call
    statement: cst.SimpleStatementLine


@dataclass
class Analysis:
    findings: list[Finding] = field(default_factory=list)
    handles: dict[cst.SimpleStatementLine, Handle] = field(default_factory=dict)
    model_access: dict[cst.Name, Handle] = field(default_factory=dict)
    chat_access: dict[cst.Name, ChatHandle] = field(default_factory=dict)
    chat_calls: dict[cst.Call, ChatHandle] = field(default_factory=dict)
    inline_calls: dict[cst.Call, cst.Call] = field(default_factory=dict)  # method call -> constructor call
    handled_calls: list[cst.Call] = field(default_factory=list)  # old-SDK calls the transformer must convert
    configure_calls: list[cst.Call] = field(default_factory=list)
    init_calls: list[cst.Call] = field(default_factory=list)
    kinds: set[str] = field(default_factory=set)
    names: set[str] = field(default_factory=set)
    beta_models: bool = False
    types_name: str = "types"
    genai_name: str = "genai"


def split_constructor(call: cst.Call, original: cst.Call) -> tuple[cst.Arg | None, list[ConfigItem]]:
    """Split ``GenerativeModel(name, generation_config=..., ...)`` into the model-name arg and config items."""
    model_arg: cst.Arg | None = None
    items: list[ConfigItem] = []
    positional = 0
    for arg, orig in zip(call.args, original.args, strict=True):
        if arg.star:
            raise Unsupported("call-kwargs", arg)
        if arg.keyword is None:
            positional += 1
            if positional > 1:
                raise Unsupported("call-args", arg)
            model_arg = arg
        elif arg.keyword.value == "model_name":
            model_arg = arg
        elif arg.keyword.value in symbols.CONFIG_KEYWORDS:
            items.append(ConfigItem(arg.keyword.value, arg, orig))
        else:
            raise Unsupported("call-args", arg)
    return model_arg, items


def dotted_name(node: cst.BaseExpression) -> str:
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        return f"{dotted_name(node.value)}.{node.attr.value}"
    return ""


def import_module_name(node: cst.Import | cst.ImportFrom) -> str | None:
    """The old-SDK module an import statement refers to (None for other imports)."""
    if isinstance(node, cst.ImportFrom):
        if node.module is None or node.relative:
            return None
        name = dotted_name(node.module)
        return name if symbols.is_old_name(name) else None
    for alias in node.names:
        name = dotted_name(alias.name)
        if symbols.is_old_name(name):
            return name
    return None


class Analyzer(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (ScopeProvider, QualifiedNameProvider, PositionProvider, ParentNodeProvider)

    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path
        self.result = Analysis()
        self._candidates: list[Handle] = []
        self._chat_candidates: list[ChatHandle] = []
        self._metadata_maps: dict = {}

    # -- helpers ---------------------------------------------------------------------------------
    def _md_get(self, provider, node, default=None):  # type: ignore[no-untyped-def]
        """Metadata lookup that keeps working after the traversal (``finish`` runs afterwards)."""
        value = self._metadata_maps[provider].get(node, default)
        if isinstance(value, LazyValue):
            value = value()
        return value

    def qualified(self, node: cst.CSTNode) -> set[str]:
        names = self._md_get(QualifiedNameProvider, node, set())
        return {q.name for q in names}

    def parent(self, node: cst.CSTNode) -> cst.CSTNode | None:
        return self._md_get(ParentNodeProvider, node, None)

    def report(self, node: cst.CSTNode, code: str) -> None:
        position = self._md_get(PositionProvider, node).start
        finding = make_finding(self.path, position.line, position.column, code)
        if finding not in self.result.findings:
            self.result.findings.append(finding)

    # -- traversal -------------------------------------------------------------------------------
    def visit_Module(self, node: cst.Module) -> None:
        self._metadata_maps = dict(self.metadata)
        scope = self._md_get(ScopeProvider, node)
        self.result.types_name = self._free_name(scope, "types", "genai_types")
        self.result.genai_name = self._free_name(scope, "genai", "google_genai")

    @staticmethod
    def _free_name(scope, preferred: str, alternative: str) -> str:  # type: ignore[no-untyped-def]
        """``preferred`` unless the module binds it to something that is not an old-SDK import."""
        for assignment in scope.assignments[preferred]:
            if isinstance(assignment, ImportAssignment) and isinstance(assignment.node, (cst.Import, cst.ImportFrom)):
                if import_module_name(assignment.node):
                    continue
            return alternative
        return preferred

    def visit_Name(self, node: cst.Name) -> None:
        self.result.names.add(node.value)

    def visit_SimpleString(self, node: cst.SimpleString) -> None:
        value = node.evaluated_value
        if isinstance(value, str) and value.startswith(("gemini", "models/gemini", "learnlm")):
            if any(marker in value for marker in symbols.BETA_MODEL_MARKERS):
                self.result.beta_models = True

    def visit_Import(self, node: cst.Import) -> bool:
        self._check_import_scope(node)
        return False

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:
        self._check_import_scope(node)
        return False

    def _check_import_scope(self, node: cst.Import | cst.ImportFrom) -> None:
        if import_module_name(node) is None:
            return
        statement = self.parent(node)
        top = self.parent(statement) if statement is not None else None
        if not isinstance(top, cst.Module):
            self.report(node, "import-scope")

    def visit_Attribute(self, node: cst.Attribute) -> None:
        self._check_reference(node)

    def leave_Name(self, original_node: cst.Name) -> None:
        parent = self.parent(original_node)
        if isinstance(parent, cst.Attribute) and parent.attr is original_node:
            return
        if isinstance(parent, cst.Arg) and parent.keyword is original_node:
            return
        self._check_reference(original_node)

    def _check_reference(self, node: cst.Attribute | cst.Name) -> None:
        """Flag references to old-SDK names that the tool does not convert."""
        parent = self.parent(node)
        if isinstance(parent, cst.Attribute) and parent.value is node:
            return  # inner part of a longer dotted name
        base = node
        while isinstance(base, cst.Attribute):
            base = base.value
        if not isinstance(base, cst.Name):
            return  # chain starts at a call or subscript, e.g. GenerativeModel(...).generate_content
        is_callee = isinstance(parent, cst.Call) and parent.func is node
        for qualified in self.qualified(node):
            kind = symbols.sdk_kind(qualified)
            if kind is None:
                continue
            self.result.kinds.add(kind)
            if qualified in symbols.HANDLED_PREFIXES:
                continue
            if qualified in symbols.CONVERTED_CALLS:
                if not is_callee:
                    self.report(node, "unsupported-api")  # e.g. used as a type annotation
                continue
            if qualified in symbols.RENAMED_TYPES or any(
                qualified.startswith(renamed + ".") for renamed in symbols.RENAMED_TYPES
            ):
                continue
            self.report(node, symbols.legacy_code(qualified))

    def visit_Call(self, node: cst.Call) -> None:
        names = self.qualified(node.func)
        if names & symbols.GENERATIVE_MODEL:
            self._model_constructor(node)
        elif names & symbols.CONFIGURE:
            self.result.configure_calls.append(node)
            self.result.handled_calls.append(node)
        elif names & symbols.VERTEX_INIT:
            self.result.init_calls.append(node)
            self.result.handled_calls.append(node)
        elif names & symbols.EMBED_CONTENT:
            self.result.handled_calls.append(node)
        elif isinstance(node.func, cst.Attribute) and node.func.attr.value == "start_chat":
            self._chat_constructor(node)

    # -- model handles -----------------------------------------------------------------------------
    def _model_constructor(self, node: cst.Call) -> None:
        kind = "vertex" if any(q.startswith("vertexai.") for q in self.qualified(node.func)) else "developer"
        self.result.handled_calls.append(node)
        parent = self.parent(node)
        if isinstance(parent, cst.Assign) and parent.value is node:
            statement = self.parent(parent)
            if (
                len(parent.targets) == 1
                and isinstance(parent.targets[0].target, cst.Name)
                and isinstance(statement, cst.SimpleStatementLine)
                and len(statement.body) == 1
            ):
                self._candidates.append(Handle(parent.targets[0].target.value, node, statement, kind))
                return
        if isinstance(parent, cst.Attribute) and parent.value is node:
            call = self.parent(parent)
            if (
                isinstance(call, cst.Call)
                and call.func is parent
                and parent.attr.value in symbols.MODEL_METHODS
                and parent.attr.value != "start_chat"
            ):
                self.result.inline_calls[call] = node
                return
        self.report(node, "handle-untracked")

    def _chat_constructor(self, node: cst.Call) -> None:
        parent = self.parent(node)
        statement = self.parent(parent) if parent is not None else None
        if (
            isinstance(parent, cst.Assign)
            and parent.value is node
            and len(parent.targets) == 1
            and isinstance(parent.targets[0].target, cst.Name)
            and isinstance(statement, cst.SimpleStatementLine)
            and len(statement.body) == 1
        ):
            self._chat_candidates.append(ChatHandle(parent.targets[0].target.value, node, statement))

    # -- finishing -----------------------------------------------------------------------------------
    def _references(self, statement: cst.SimpleStatementLine, name: str) -> list[cst.Name] | None:
        """References of the single assignment of ``name`` made by ``statement``; None if reassigned."""
        scope = self._md_get(ScopeProvider, statement)
        assignments = [a for a in scope.assignments[name] if isinstance(a, Assignment)]
        if len(assignments) != 1:
            return None
        return [ref.node for ref in assignments[0].references if isinstance(ref.node, cst.Name)]

    def _direct_calls(
        self, refs: list[cst.Name], allowed: frozenset[str]
    ) -> list[tuple[cst.Name, cst.Call, str]] | None:
        """Pair each reference with its ``name.method(...)`` call; report escapes. None if any escapes."""
        calls: list[tuple[cst.Name, cst.Call, str]] = []
        clean = True
        for ref in refs:
            attribute = self.parent(ref)
            call = self.parent(attribute) if attribute is not None else None
            if (
                isinstance(attribute, cst.Attribute)
                and attribute.value is ref
                and isinstance(call, cst.Call)
                and call.func is attribute
                and attribute.attr.value in allowed
            ):
                calls.append((ref, call, attribute.attr.value))
            elif (
                isinstance(attribute, cst.Attribute)
                and attribute.value is ref
                and attribute.attr.value == "send_message_async"
                and isinstance(call, cst.Call)
            ):
                self.report(ref, "async-chat")
                clean = False
            else:
                self.report(ref, "handle-escapes")
                clean = False
        return calls if clean else None

    def finish(self) -> Analysis:
        result = self.result
        for handle in self._candidates:
            refs = self._references(handle.statement, handle.name)
            if refs is None:
                self.report(handle.ctor, "handle-reassigned")
                handle.ok = False
                continue
            calls = self._direct_calls(refs, symbols.MODEL_METHODS)
            if calls is None:
                handle.ok = False
                continue
            self._check_constructor(handle)
            if not handle.ok:
                continue
            result.handles[handle.statement] = handle
            for ref, call, method in calls:
                result.model_access[ref] = handle
                if method == "count_tokens" and handle.has_system_or_tools:
                    self.report(call, "count-tokens-semantics")
        chat_call_nodes = {chat.call for chat in self._chat_candidates}
        for chat in self._chat_candidates:
            func = chat.call.func
            if not (isinstance(func, cst.Attribute) and isinstance(func.value, cst.Name)):
                continue
            if func.value not in result.model_access:
                continue  # not an old-SDK handle (some other object with a start_chat method)
            refs = self._references(chat.statement, chat.name)
            if refs is None:
                self.report(chat.call, "handle-reassigned")
                continue
            calls = self._direct_calls(refs, symbols.CHAT_METHODS)
            if calls is None:
                continue
            result.chat_calls[chat.call] = chat
            for ref, _call, _method in calls:
                result.chat_access[ref] = chat
        for ref in list(result.model_access):
            attribute = self.parent(ref)
            call = self.parent(attribute) if attribute is not None else None
            if (
                isinstance(attribute, cst.Attribute)
                and attribute.attr.value == "start_chat"
                and isinstance(call, cst.Call)
                and call not in result.chat_calls
                and call not in chat_call_nodes
            ):
                self.report(call, "handle-untracked")
        if {"developer", "vertex"} <= result.kinds and result.handled_calls:
            self.report(result.handled_calls[0], "mixed-sdk")
        return result

    def _check_constructor(self, handle: Handle) -> None:
        """Dry-run the config conversion so problems are found before anything is rewritten."""
        try:
            model_arg, items = split_constructor(handle.ctor, handle.ctor)
            if model_arg is None:
                raise Unsupported("call-args", handle.ctor)
            if not isinstance(model_arg.value, (cst.SimpleString, cst.ConcatenatedString)):
                self.report(handle.ctor, "dynamic-model")
            config = convert_config(items, self.result.types_name, self.qualified, handle.ctor)
        except Unsupported as error:
            self.report(error.node, error.code)
            handle.ok = False
            return
        if config is not None:
            handle.has_config = True
            handle.has_system_or_tools = config.has_system_or_tools
