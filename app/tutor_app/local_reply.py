"""Decode the explicit local chat envelope before its text reaches visual formatting."""
from __future__ import annotations

import json


_LIMIT = 4 * 1024 * 1024
_SPACE = " \t\r\n"
_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}


class ReplyError(ValueError):
    """A local response did not match its requested chat transport."""


def chat_schema(speech: bool = False) -> dict:
    """The outer transport is separate from JSON or code requested inside the reply."""
    fields = {"reply": {"type": "string"}}
    if speech:
        fields["speech"] = {"type": "string"}
    return {"type": "object", "properties": fields, "required": list(fields), "additionalProperties": False}


class ReplyDecoder:
    """Stream only the reply string, with bounded storage and one pass over incoming characters.

    Speech and transport syntax are never emitted. The complete envelope is independently checked by
    json.loads at finish; an incomplete or invalid response must never become successful chat history.
    """

    def __init__(self, speech: bool = False):
        self._fields = {"reply", "speech"} if speech else {"reply"}
        self._chunks: list[str] = []
        self._size = 0
        self._state = "start"
        self._target = ""
        self._key = ""
        self._key_parts: list[str] = []
        self._seen: set[str] = set()
        self._escape = False
        self._unicode: str | None = None
        self._high: int | None = None
        self._failed = False
        self._result: tuple[str, str] | None = None

    def _error(self):
        self._failed = True
        raise ReplyError("The local AI returned an invalid reply; try again.")

    def _emit(self, char: str, out: list[str]) -> None:
        if self._target == "key":
            self._key_parts.append(char)
        elif self._key == "reply":
            code = ord(char)
            if (code < 0x20 and char not in "\b\f\t\r\n") or 0x7F <= code <= 0x9F:
                self._error()
            out.append(char)

    def _codepoint(self, code: int, out: list[str]) -> None:
        if self._high is not None:
            if not 0xDC00 <= code <= 0xDFFF:
                self._error()
            self._emit(chr(0x10000 + ((self._high - 0xD800) << 10) + code - 0xDC00), out)
            self._high = None
        elif 0xD800 <= code <= 0xDBFF:
            self._high = code
        elif 0xDC00 <= code <= 0xDFFF:
            self._error()
        else:
            self._emit(chr(code), out)

    def _string(self, char: str, out: list[str]) -> None:
        if self._unicode is not None:
            if char not in "0123456789abcdefABCDEF":
                self._error()
            self._unicode += char
            if len(self._unicode) == 4:
                code, self._unicode = int(self._unicode, 16), None
                self._codepoint(code, out)
        elif self._escape:
            self._escape = False
            if char == "u":
                self._unicode = ""
            elif self._high is not None or char not in _ESCAPES:
                self._error()
            else:
                self._emit(_ESCAPES[char], out)
        elif char == "\\":
            self._escape = True
        elif self._high is not None:
            self._error()
        elif char == '"':
            if self._target == "key":
                self._key = "".join(self._key_parts)
                if self._key not in self._fields or self._key in self._seen:
                    self._error()
                self._state = "colon"
            else:
                self._seen.add(self._key)
                self._state = "comma"
        elif ord(char) < 0x20 or 0xD800 <= ord(char) <= 0xDFFF:
            self._error()
        else:
            self._emit(char, out)

    def feed(self, chunk: str) -> str:
        """Return newly decoded reply text; hold incomplete escapes across arbitrary chunks."""
        if self._failed or self._result is not None:
            self._error()
        self._size += len(chunk)
        if self._size > _LIMIT:
            self._error()
        self._chunks.append(chunk)
        out: list[str] = []
        for char in chunk:
            if self._state == "string":
                self._string(char, out)
            elif char in _SPACE:
                continue
            elif self._state == "start" and char == "{":
                self._state = "first_key"
            elif self._state in ("first_key", "key") and char == '"':
                self._target, self._key_parts, self._state = "key", [], "string"
            elif self._state == "first_key" and char == "}":
                self._state = "done"
            elif self._state == "colon" and char == ":":
                self._state = "value"
            elif self._state == "value" and char == '"':
                self._target, self._state = "value", "string"
            elif self._state == "comma" and char == ",":
                self._state = "key"
            elif self._state == "comma" and char == "}":
                self._state = "done"
            else:
                self._error()
        return "".join(out)

    def finish(self) -> tuple[str, str]:
        """Strictly validate the entire envelope and return its literal reply and separate speech."""
        if self._failed:
            self._error()
        if self._result is not None:
            return self._result
        if self._state != "done":
            self._error()

        def unique(pairs):
            data = {}
            for key, value in pairs:
                if key in data:
                    self._error()
                data[key] = value
            return data

        try:
            data = json.loads("".join(self._chunks), object_pairs_hook=unique)
        except (ValueError, TypeError):
            self._error()
        if (not isinstance(data, dict) or set(data) != self._fields
                or any(not isinstance(value, str) for value in data.values())):
            self._error()
        self._result = data["reply"], data.get("speech", "")
        return self._result
