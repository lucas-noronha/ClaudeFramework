"""`dotnet-layered` census extractor (framework ADR 0019, framework spec 0002 FR-01).

Inventories, from the C# files at the integration ref:

- `handler`    — classes implementing a handler/consumer interface
                 (`IRequestHandler<`, `INotificationHandler<`, `IConsumer<`,
                 `ICommandHandler<`, `IQueryHandler<`, `IEventHandler<`,
                 `IHandleMessages<`) or named `*Handler`; `Namespace.Class`.
- `endpoint`   — `[Http*("...")]` actions combined with the controller's
                 `[Route("...")]`, and minimal-API `Map{Get,Post,...}("...")`;
                 `VERB /route`.
- `collection` — MongoDB `GetCollection<T>("name")` and EF `DbSet<T> Name`.
- `config`     — keys read via `GetValue<T>(...)`, `GetSection(...)`,
                 `GetConnectionString(...)` and `configuration[...]`. A key
                 given as a `const`/`static readonly` string field
                 (`GetValue<int>(Keys.Timeout)`) is resolved to the field's
                 value (AC-02); one that can't be resolved is listed as
                 `?Identifier` rather than dropped.
- `enum`       — members as `Enum.Member`.

Regex over comment-stripped source, no compiler: deliberately simple and
deterministic (NFR-03). It is consistently wrong in known ways, e.g. a
`MapGroup` prefix isn't applied, and that is preferable to being
inconsistently right. Settings: `include`/`exclude` fnmatch globs over
repo paths (defaults: every `*.cs`, minus `bin/` and `obj/`).
"""
import re

DEFAULT_INCLUDE = ["*.cs"]
DEFAULT_EXCLUDE = ["*/bin/*", "*/obj/*", "bin/*", "obj/*"]
HANDLER_BASES = re.compile(r"\b(IRequestHandler|INotificationHandler|IConsumer|ICommandHandler|IQueryHandler|IEventHandler|IHandleMessages)\s*<")
CLASS_DECL = re.compile(r"\b(?:class|record)\s+(\w+)(?:\s*<[^>{]*>)?(?:\s*\([^)]*\))?\s*(?::\s*([^{;]+))?[{;]")
NAMESPACE = re.compile(r"\bnamespace\s+([\w.]+)")
CONST_FIELD = re.compile(r"\b(?:const\s+string|static\s+readonly\s+string)\s+(\w+)\s*=\s*\"((?:[^\"\\]|\\.)*)\"\s*;")
ARG = r"(\"(?:[^\"\\]|\\.)*\"|[A-Za-z_][\w.]*)"
CONFIG_CALLS = [
    re.compile(r"\.GetValue\s*<[^>]+>\s*\(\s*" + ARG),
    re.compile(r"\.GetSection\s*\(\s*" + ARG),
    re.compile(r"\.GetConnectionString\s*\(\s*" + ARG),
    re.compile(r"\b\w*[Cc]onfiguration\s*\[\s*" + ARG + r"\s*\]"),
]
HTTP_ATTR = re.compile(r"\[\s*Http(Get|Post|Put|Delete|Patch)\s*(?:\(\s*\"([^\"]*)\"[^)]*\))?\s*\]")
ROUTE_ATTR = re.compile(r"\[\s*Route\s*\(\s*\"([^\"]*)\"\s*\)\s*\]")
MINIMAL_API = re.compile(r"\.Map(Get|Post|Put|Delete|Patch)\s*\(\s*\"([^\"]*)\"")
MONGO_COLLECTION = re.compile(r"\.GetCollection\s*<[^>]+>\s*\(\s*" + ARG)
DBSET = re.compile(r"\bDbSet\s*<\s*[\w.]+\s*>\s+(\w+)")
ENUM_DECL = re.compile(r"\benum\s+(\w+)\s*(?::\s*[\w.]+)?\s*\{([^}]*)\}")


def strip_comments(code: str) -> str:
    """Blank out `//` and `/* */` comments, keeping string literals and
    every newline (so line numbers stay right).
    """
    out, i, n = [], 0, len(code)
    while i < n:
        c = code[i]
        nxt = code[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            j = code.find("\n", i)
            i = n if j == -1 else j
        elif c == "/" and nxt == "*":
            j = code.find("*/", i + 2)
            end = n if j == -1 else j + 2
            out.append("\n" * code.count("\n", i, end))
            i = end
        elif c == '"' or (c == "@" and nxt == '"') or (c == "$" and nxt == '"'):
            verbatim = c == "@"
            start = i
            i += 2 if c in "@$" else 1
            while i < n:
                if code[i] == "\\" and not verbatim:
                    i += 2
                    continue
                if code[i] == '"':
                    if verbatim and i + 1 < n and code[i + 1] == '"':
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            out.append(code[start:i])
        elif c == "'":
            j = i + 1
            while j < n and code[j] != "'":
                j += 2 if code[j] == "\\" else 1
            out.append(code[i:j + 1])
            i = j + 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def unquote(token: str):
    return token[1:-1] if token.startswith('"') else None


def collect_constants(sources):
    """`{Name: value, Class.Name: value}` over every file, for resolving
    keys held in constants. A name defined twice with different values is
    ambiguous and resolves only through its qualified form.
    """
    simple, qualified, conflicts = {}, {}, set()
    for text in sources.values():
        classes = [(m.start(), m.group(1)) for m in CLASS_DECL.finditer(text)]
        for m in CONST_FIELD.finditer(text):
            owner = None
            for pos, name in classes:
                if pos < m.start():
                    owner = name
            name, value = m.group(1), m.group(2)
            if name in simple and simple[name] != value:
                conflicts.add(name)
            simple.setdefault(name, value)
            if owner:
                qualified[f"{owner}.{name}"] = value
    for name in conflicts:
        simple.pop(name, None)
    return simple, qualified


def resolve(token: str, simple, qualified):
    literal = unquote(token)
    if literal is not None:
        return literal
    parts = token.split(".")
    for length in (2, 1):
        key = ".".join(parts[-length:])
        table = qualified if length == 2 else simple
        if key in table:
            return table[key]
    return "?" + token


def combine_route(prefix: str, route: str, controller: str) -> str:
    if route.startswith("/") or route.startswith("~/"):
        path = route.lstrip("~")
    else:
        path = "/".join(p.strip("/") for p in (prefix, route) if p and p.strip("/"))
        path = "/" + path
    name = controller[:-len("Controller")] if controller.endswith("Controller") else controller
    return re.sub(r"\[controller\]", name, path, flags=re.IGNORECASE) or "/"


def extract(ref, settings):
    include = settings.get("include") or DEFAULT_INCLUDE
    exclude = settings.get("exclude") or DEFAULT_EXCLUDE
    paths = [p for p in ref.files(include, exclude) if p.endswith(".cs")]
    sources = {path: strip_comments(text) for path, text in ref.read_many(paths).items()}
    simple, qualified = collect_constants(sources)
    rows = []

    for path, text in sorted(sources.items()):
        ns_match = NAMESPACE.search(text)
        namespace = ns_match.group(1) if ns_match else ""
        classes = list(CLASS_DECL.finditer(text))

        for m in classes:
            name, bases = m.group(1), m.group(2) or ""
            if HANDLER_BASES.search(bases) or name.endswith("Handler"):
                rows.append(("handler", f"{namespace}.{name}" if namespace else name, f"{path}:{line_of(text, m.start())}"))

        for m in ENUM_DECL.finditer(text):
            for raw in m.group(2).split(","):
                member = re.sub(r"\[[^\]]*\]", "", raw).split("=")[0].strip()
                if re.match(r"^\w+$", member):
                    rows.append(("enum", f"{m.group(1)}.{member}", f"{path}:{line_of(text, m.start())}"))

        for pattern in CONFIG_CALLS:
            for m in pattern.finditer(text):
                rows.append(("config", resolve(m.group(1), simple, qualified), f"{path}:{line_of(text, m.start())}"))

        for m in MONGO_COLLECTION.finditer(text):
            rows.append(("collection", resolve(m.group(1), simple, qualified), f"{path}:{line_of(text, m.start())}"))
        for m in DBSET.finditer(text):
            rows.append(("collection", m.group(1), f"{path}:{line_of(text, m.start())}"))

        for m in MINIMAL_API.finditer(text):
            rows.append(("endpoint", f"{m.group(1).upper()} /{m.group(2).lstrip('/')}", f"{path}:{line_of(text, m.start())}"))

        for index, cls in enumerate(classes):
            end = classes[index + 1].start() if index + 1 < len(classes) else len(text)
            head_start = classes[index - 1].end() if index else 0
            route = ROUTE_ATTR.findall(text[head_start:cls.start()])
            prefix = route[-1] if route else ""
            for m in HTTP_ATTR.finditer(text, cls.end(), end):
                verb, sub = m.group(1).upper(), m.group(2) or ""
                rows.append(("endpoint", f"{verb} {combine_route(prefix, sub, cls.group(1))}", f"{path}:{line_of(text, m.start())}"))
    return rows
