import ast
import hashlib
import os
import re
from pathlib import Path

from pydantic import BaseModel, Field

# Constants for source inspection safety limits
MAX_FILE_SIZE_BYTES = 100 * 1024  # 100 KB limit per file
MAX_FILES_PER_SESSION = 10

# Banned filename substrings or patterns to protect sensitive files
SENSITIVE_PATTERNS = {
    ".env",
    "credentials",
    "secret",
    "password",
    "token",
    ".git",
    "node_modules",
    "__pycache__",
    ".key",
    ".pem",
    "id_rsa",
}


class InspectedFunction(BaseModel):
    """Result of safe AST inspection of a repository function."""

    file_path: str = Field(..., description="Repository-relative file path")
    function_name: str = Field(..., description="Function or method name")
    line_start: int = Field(..., ge=1, description="1-indexed starting line")
    line_end: int = Field(..., ge=1, description="1-indexed ending line")
    parameters: list[str] = Field(
        default_factory=list, description="Extracted parameter names"
    )
    docstring: str | None = Field(
        default=None, description="Extracted docstring if present"
    )
    source_hash: str = Field(
        ..., description="SHA-256 hash of the inspected source file"
    )


class SourceInspectionError(Exception):
    """Raised when source inspection encounters security violations or unreadable files."""


class SourceInspector:
    """Safe, read-only AST-based source code inspector.
    Guarantees:
    - No code execution or dynamic imports.
    - Path traversal and symlink escape prevention.
    - Size and secret file filtering.
    - Deterministic SHA-256 source hashing.
    """

    def __init__(self, repo_root: str | Path):
        self.repo_root = Path(repo_root).resolve()
        if not self.repo_root.is_dir():
            raise SourceInspectionError(
                f"Repository root directory does not exist: {self.repo_root}"
            )
        self._inspected_files_count = 0

    def _validate_path(self, relative_path: str) -> Path:
        """Validate and resolve target file path, strictly enforcing repository boundary."""
        # Clean relative path
        cleaned = os.path.normpath(relative_path).lstrip("/\\")
        target = (self.repo_root / cleaned).resolve()

        # Symlink / path traversal check: target must be within repo_root
        try:
            target.relative_to(self.repo_root)
        except ValueError:
            raise SourceInspectionError(
                f"Path traversal detected: {relative_path} escapes repository root"
            )

        # Sensitive file check
        lower_parts = [p.lower() for p in target.parts]
        for part in lower_parts:
            for pattern in SENSITIVE_PATTERNS:
                if pattern in part:
                    raise SourceInspectionError(
                        f"Access to sensitive path or file blocked: {relative_path}"
                    )

        if not target.is_file():
            raise SourceInspectionError(f"Target file not found: {relative_path}")

        # File size check
        file_size = target.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            raise SourceInspectionError(
                f"File size {file_size} exceeds maximum inspection limit of {MAX_FILE_SIZE_BYTES} bytes"
            )

        return target

    def inspect_function(
        self, file_path: str, function_name: str
    ) -> InspectedFunction | None:
        """Inspect a specific function inside a Python file using AST parsing without code execution."""
        if self._inspected_files_count >= MAX_FILES_PER_SESSION:
            raise SourceInspectionError(
                f"Maximum files inspected limit ({MAX_FILES_PER_SESSION}) reached for session"
            )

        target_file = self._validate_path(file_path)
        self._inspected_files_count += 1

        try:
            content = target_file.read_bytes()
        except OSError as e:
            raise SourceInspectionError(f"Failed to read file {file_path}: {e}")

        # Compute SHA-256 hash of raw file content
        source_hash = hashlib.sha256(content).hexdigest()

        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            # Not a readable text/python file
            return None

        if target_file.suffix in (".ts", ".js"):
            return self._inspect_typescript(
                target_file, text, function_name, source_hash
            )

        try:
            tree = ast.parse(text, filename=str(target_file))
        except SyntaxError:
            # File has syntax errors, cannot parse AST
            return None

        # Search AST for function definition
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == function_name
            ):
                # Extract parameter names

                args: list[str] = []
                # posonlyargs (Python 3.8+)
                for arg in getattr(node.args, "posonlyargs", []):
                    args.append(arg.arg)
                for arg in node.args.args:
                    args.append(arg.arg)
                for arg in getattr(node.args, "kwonlyargs", []):
                    args.append(arg.arg)

                # Exclude 'self' or 'cls' for instance/class methods
                filtered_args = [a for a in args if a not in ("self", "cls")]

                line_start = node.lineno
                line_end = getattr(node, "end_lineno", line_start)
                docstring = ast.get_docstring(node)

                # Convert back to repo-relative path using forward slashes
                rel_path = str(target_file.relative_to(self.repo_root)).replace(
                    "\\", "/"
                )

                return InspectedFunction(
                    file_path=rel_path,
                    function_name=function_name,
                    line_start=line_start,
                    line_end=line_end or line_start,
                    parameters=filtered_args,
                    docstring=docstring,
                    source_hash=source_hash,
                )

        return None

    def _inspect_typescript(
        self, target_file: Path, text: str, function_name: str, source_hash: str
    ) -> InspectedFunction | None:
        """Locate a TypeScript/JavaScript method without executing or compiling anything.

        For a tool implementation such as NexaCart's ``execute(args, context)`` the reported
        ``parameters`` are the argument keys the body actually reads (``args['x']``,
        ``args["x"]``, ``args.x``): that is what an argument-mapping defect changes.
        """
        header = re.compile(
            rf"^[ \t]*(?:(?:public|private|protected|static|async|export|function)\s+)*"
            rf"{re.escape(function_name)}\s*\(",
            re.MULTILINE,
        )
        match = header.search(text)
        if match is None:
            return None
        # Skip the parameter list (balanced parentheses), then find the body's opening brace.
        idx = match.end() - 1
        depth = 0
        while idx < len(text):
            if text[idx] == "(":
                depth += 1
            elif text[idx] == ")":
                depth -= 1
                if depth == 0:
                    break
            idx += 1
        params_text = text[match.end() : idx]
        body_start = text.find("{", idx)
        if body_start < 0:
            return None
        body_end = _matching_brace(text, body_start)
        if body_end < 0:
            return None
        body = text[body_start : body_end + 1]
        arg_name = (params_text.split(":")[0].split(",")[0].strip() or "args").lstrip(
            "_"
        )
        keys = set(
            re.findall(
                rf"\b_?{re.escape(arg_name)}\s*\[\s*['\"]([A-Za-z0-9_]+)['\"]\s*\]",
                body,
            )
        ) | set(
            re.findall(rf"\b_?{re.escape(arg_name)}\.([A-Za-z_][A-Za-z0-9_]*)", body)
        )
        doc = re.search(r"/\*\*(.*?)\*/\s*$", text[: match.start()], re.DOTALL)
        rel_path = str(target_file.relative_to(self.repo_root)).replace("\\", "/")
        return InspectedFunction(
            file_path=rel_path,
            function_name=function_name,
            line_start=text.count("\n", 0, match.start()) + 1,
            line_end=text.count("\n", 0, body_end) + 1,
            parameters=sorted(keys),
            docstring=" ".join(doc.group(1).replace("*", " ").split()) if doc else None,
            source_hash=source_hash,
        )


def _matching_brace(text: str, open_idx: int) -> int:
    """Index of the brace closing ``text[open_idx]``, skipping strings and comments; -1 if none."""
    depth = 0
    i = open_idx
    quote: str | None = None
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in ("'", '"', "`"):
            quote = ch
        elif text.startswith("//", i):
            nl = text.find("\n", i)
            i = len(text) if nl < 0 else nl
            continue
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = len(text) if end < 0 else end + 2
            continue
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1
