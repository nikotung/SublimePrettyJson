"""
JSON5 / JSONC to strict JSON converter.

Supports the JSON5/JSONC features relevant for formatting:
- line (//) and block (/* */) comments
- single-quoted strings
- unquoted object keys (identifiers)
- trailing commas
- hexadecimal numbers
- leading/trailing decimal points and leading plus signs
- multi-line single-quoted strings

Infinity, -Infinity and NaN are kept as-is (simplejson parses them).
"""

import decimal
import re

_NUMBER_RE = re.compile(
    r"[+-]?(?:0[xX][0-9a-fA-F]+|(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?)"
)
_IDENTIFIER_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_WHITESPACE = " \t\r\n"
_PUNCT = ("{", "}", "[", "]", ",", ":")
_WORD_KINDS = ("string", "number", "ident", "block_comment")


def _read_string(text, start):
    """Read a string starting at `start` and return (end_index, json_string).

    The returned string is always double-quoted and valid strict JSON.
    """
    quote = text[start]
    i = start + 1
    n = len(text)
    buf = []
    while i < n:
        c = text[i]
        if c == "\\":
            nxt = text[i + 1] if i + 1 < n else ""
            if nxt == "'":
                # \' inside a single-quoted string is just an apostrophe
                buf.append("'")
                i += 2
                continue
            buf.append("\\" + nxt)
            i += 2
            continue
        if c == quote:
            return i + 1, '"' + "".join(buf) + '"'
        if c == "\n":
            # raw newlines are only legal in single-quoted strings
            if quote == '"':
                raise ValueError("Unterminated string starting at char %d" % start)
            buf.append("\\n")
            i += 1
            continue
        if c == '"':
            buf.append('\\"')
        else:
            buf.append(c)
        i += 1
    raise ValueError("Unterminated string starting at char %d" % start)


def _normalize_number(token):
    """Normalize a JSON5 number token to strict JSON."""
    lowered = token.lower()
    if "x" in lowered:
        sign = -1 if token.startswith("-") else 1
        return str(sign * int(lowered.lstrip("+-"), 16))
    if token.startswith("+"):
        token = token[1:]
    if "." in token or "e" in lowered:
        # handles .5, 2., 2.e5
        return str(decimal.Decimal(token))
    return token


def to_json(text):
    """Convert JSON5/JSONC `text` into strict JSON. Raises ValueError on errors."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in _WHITESPACE:
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            if end == -1:
                raise ValueError("Unterminated block comment starting at char %d" % i)
            i = end + 2
            continue
        if c == '"' or c == "'":
            i, converted = _read_string(text, i)
            out.append(converted)
            continue
        if c.isdigit() or c in "+-.":
            m = _NUMBER_RE.match(text, i)
            if m:
                out.append(_normalize_number(m.group(0)))
                i = m.end()
                continue
        if c.isalpha() or c in "_$":
            m = _IDENTIFIER_RE.match(text, i)
            token = m.group(0)
            j = m.end()
            k = j
            while k < n and text[k] in _WHITESPACE:
                k += 1
            if k < n and text[k] == ":":
                out.append('"%s"' % token)
            else:
                # true / false / null / Infinity / NaN / undefined-ish leftovers
                out.append(token)
            i = j
            continue
        out.append(c)
        i += 1

    result = "".join(out)
    # strip trailing commas
    result = re.sub(r",(\s*[}\]])", r"\1", result)
    return result


def tokenize(text):
    """Split JSON5/JSONC text into (kind, value, same_line) tokens.

    kind is one of: '{', '}', '[', ']', ',', ':', 'string', 'number',
    'ident', 'line_comment', 'block_comment'.
    same_line indicates the token was not preceded by a newline in the source.
    Single-quoted strings are normalized to strict JSON strings and
    numbers are normalized via _normalize_number.
    """
    tokens = []
    i = 0
    n = len(text)
    same_line = True
    while i < n:
        c = text[i]
        if c in _WHITESPACE:
            if c == "\n":
                same_line = False
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            if j == -1:
                j = n
            tokens.append(("line_comment", text[i:j].rstrip(), same_line))
            i = j
            same_line = True
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            if end == -1:
                raise ValueError("Unterminated block comment starting at char %d" % i)
            tokens.append(("block_comment", text[i:end + 2], same_line))
            i = end + 2
            same_line = True
            continue
        if c in _PUNCT:
            tokens.append((c, c, same_line))
            i += 1
            same_line = True
            continue
        if c == '"' or c == "'":
            i, converted = _read_string(text, i)
            tokens.append(("string", converted, same_line))
            same_line = True
            continue
        if c.isdigit() or c in "+-.":
            m = _NUMBER_RE.match(text, i)
            if m:
                # keep the original spelling (0xFF, .5, 2.) - output stays
                # valid JSON5 and nothing the user wrote is rewritten
                tokens.append(("number", m.group(0), same_line))
                i = m.end()
                same_line = True
                continue
            if c in "+-" and i + 1 < n and (
                text[i + 1].isalpha() or text[i + 1] in "_$"
            ):
                # -Infinity / +NaN
                m = _IDENTIFIER_RE.match(text, i + 1)
                signed = c + m.group(0)
                if signed in ("-Infinity", "+Infinity", "-NaN", "+NaN"):
                    tokens.append(("ident", signed, same_line))
                    i = m.end()
                    same_line = True
                    continue
        if c.isalpha() or c in "_$":
            m = _IDENTIFIER_RE.match(text, i)
            tokens.append(("ident", m.group(0), same_line))
            i = m.end()
            same_line = True
            continue
        raise ValueError("Unexpected character %r at char %d" % (c, i))
    return tokens


def format(text, indent=2):
    """Re-indent JSON5/JSONC text, preserving comments and token spelling.

    Comments, key order, trailing commas and original number spelling are
    kept; single-quoted strings are normalized to double-quoted ones.
    Input is expected to be valid - validate first (to_json + json.loads).
    """
    if indent == "\t":
        unit = "\t"
    elif isinstance(indent, int):
        unit = " " * indent
    else:
        unit = str(indent)

    tokens = tokenize(text)
    out = []
    state = {"ind": 0, "bol": True}
    prev_kind = None

    def emit(s):
        if state["bol"]:
            out.append(unit * state["ind"])
            state["bol"] = False
        out.append(s)

    def newline():
        if not state["bol"]:
            out.append("\n")
            state["bol"] = True

    i = 0
    n = len(tokens)
    while i < n:
        kind, val, same_line = tokens[i]
        if not same_line and not state["bol"]:
            newline()
        if kind in "{[":
            close = "}" if kind == "{" else "]"
            if i + 1 < n and tokens[i + 1][0] == close:
                emit(kind + close)
                i += 2
                continue
            emit(val)
            state["ind"] += 1
            newline()
        elif kind in "}]":
            state["ind"] -= 1
            newline()
            emit(val)
        elif kind == ",":
            emit(",")
            # keep a trailing line comment on the same line
            if not (i + 1 < n and tokens[i + 1][0] == "line_comment"
                    and tokens[i + 1][2]):
                newline()
        elif kind == ":":
            emit(": ")
        elif kind == "line_comment":
            if state["bol"]:
                emit(val)
            else:
                out.append(" " + val)
            newline()
        else:
            # scalar: string, number, ident, block_comment
            if (
                not state["bol"]
                and (kind == "block_comment" or prev_kind == "block_comment")
                and not out[-1].endswith((" ", "\t"))
            ):
                out.append(" ")
            emit(val)
        prev_kind = kind
        i += 1
    return "".join(out)


def minify(text):
    """Remove JSON5/JSONC whitespace while preserving comments.

    Line comments force a line break; block comments are kept inline.
    Token spelling is kept (see format()).
    """
    out = []
    prev_word = False
    bol = True
    for kind, val, _same_line in tokenize(text):
        if kind == "line_comment":
            if not bol:
                out.append("\n")
            out.append(val)
            out.append("\n")
            bol = True
            prev_word = False
            continue
        if kind == "block_comment" and not bol and not out[-1].endswith((" ", "\n", "{", "[")):
            out.append(" ")
        word = kind in _WORD_KINDS
        if not bol and prev_word and word:
            out.append(" ")
        out.append(val)
        bol = False
        prev_word = word
    return "".join(out).strip()
