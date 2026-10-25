"""Bounded GPT-OSS Harmony framing without retaining or decoding reasoning.

Only control IDs and the short current header are inspected. Body tokens are
classified, never accumulated. Generation and logits lookahead each own a parser.
"""
from __future__ import annotations

from dataclasses import dataclass


class HarmonyError(ValueError):
    """The model did not produce a complete supported assistant reply."""


@dataclass(frozen=True)
class HarmonyTokens:
    start: int = 200006
    end: int = 200007
    message: int = 200008
    channel: int = 200005
    constrain: int = 200003
    done: int = 200002
    eos: frozenset[int] = frozenset({200002})

    @classmethod
    def from_tokenizer(cls, tokenizer) -> HarmonyTokens:
        expected = {"start": 200006, "end": 200007, "message": 200008,
                    "channel": 200005, "constrain": 200003, "return": 200002}
        for name, token_id in expected.items():
            ids = tokenizer.encode(f"<|{name}|>", add_special_tokens=False)
            if list(ids) != [token_id]:
                raise HarmonyError("The GPT-OSS tokenizer does not match the pinned checkpoint.")
        eos = frozenset(tokenizer.eos_token_ids)
        if 200002 not in eos:
            raise HarmonyError("The GPT-OSS tokenizer is missing its assistant stop token.")
        return cls(eos=eos)


class HarmonyParser:
    """Start at the official template's unfinished ``<|start|>assistant``.

    ``feed`` returns True only for a final body token. Callers only decode token
    text while ``needs_text`` is true, so hidden reasoning is never detokenized.
    A final response requires the assistant return token, not a message end.
    """
    def __init__(self, tokens: HarmonyTokens):
        self.tokens = tokens
        self.state = "header"
        self._role = "assistant"
        self._channel: str | None = None
        self._content_type: str | None = None
        self._header_field = "role"
        self._header_tokens = 0
        self.saw_analysis = False
        self.final_tokens = 0

    @property
    def needs_text(self) -> bool:
        return self.state == "header"

    @property
    def header_size(self) -> int:
        return len(self._role) + len(self._channel or "") + len(self._content_type or "")

    @property
    def final(self) -> bool:
        return self.state == "final"

    def feed(self, token: int, text: str = "") -> bool:
        t = self.tokens
        if self.state == "done":
            raise HarmonyError("GPT-OSS sent tokens after its completed reply.")
        if token == t.done:
            if self.state != "final" or not self.final_tokens:
                raise HarmonyError("GPT-OSS ended before a complete final answer.")
            self.state = "done"
            return False
        if token in t.eos:
            raise HarmonyError("GPT-OSS ended before its assistant return boundary.")
        if self.state == "between":
            if token != t.start:
                raise HarmonyError("GPT-OSS sent a malformed assistant boundary.")
            self.state, self._role, self._channel = "header", "", None
            self._content_type, self._header_field = None, "role"
            self._header_tokens = 0
            return False
        if self.state == "header":
            if token == t.channel:
                if self._role.strip() != "assistant" or self._channel is not None:
                    raise HarmonyError("GPT-OSS sent an unsupported assistant header.")
                self._channel, self._header_field = "", "channel"
            elif token == t.constrain:
                if self._role.strip() != "assistant" or self._content_type is not None:
                    raise HarmonyError("GPT-OSS sent an unsupported assistant header.")
                self._content_type, self._header_field = "", "content_type"
            elif token == t.message:
                # Harmony permits an optional JSON content-type annotation after
                # the channel, with or without its own constrain control token.
                # The explicit channel still determines privacy and activation.
                parts = self._channel.split() if self._channel is not None else []
                channel = parts[0] if parts else None
                content_type = self._content_type.strip() if self._content_type is not None else None
                if (self._role.strip() != "assistant" or channel not in {"analysis", "final"}
                        or (len(parts) > 1 and ([part.casefold() for part in parts[1:]] != ["json"]
                                               or content_type is not None))
                        or (content_type is not None and content_type.casefold() != "json")):
                    raise HarmonyError("GPT-OSS sent an unsupported assistant header.")
                self.state = channel
                self.saw_analysis |= channel == "analysis"
                self._role, self._channel = "", None
                self._content_type, self._header_field = None, "role"
                self._header_tokens = 0
            elif token in {t.start, t.end}:
                raise HarmonyError("GPT-OSS sent an unfinished assistant header.")
            else:
                self._header_tokens += 1
                if self._header_tokens > 64 or self.header_size + len(text) > 128:
                    raise HarmonyError("GPT-OSS sent an oversized assistant header.")
                if self._header_field == "role":
                    self._role += text
                elif self._header_field == "channel":
                    self._channel += text
                else:
                    self._content_type += text
            return False
        if token in {t.start, t.message, t.channel, t.constrain}:
            raise HarmonyError("GPT-OSS sent an unexpected assistant control token.")
        if token == t.end:
            if self.state != "analysis":
                raise HarmonyError("GPT-OSS ended a final message without completing the reply.")
            self.state = "between"
            return False
        if self.state == "final":
            self.final_tokens += 1
            return True
        return False

    def finish(self) -> None:
        if self.state != "done":
            raise HarmonyError("GPT-OSS did not complete a final answer; try again.")


class FinalOnlyLogitsProcessor:
    """Constrain structural headers and give llguidance only final body tokens.

    MLX-LM supplies a growing 1-D sequence including the uncached prompt. Its
    one-token lookahead means this parser cannot be shared with output filtering.
    The first grammar call receives an empty sequence to initialize its state.
    Finite header tries leave analysis body logits unchanged and preserve both
    analysis and final channel choices; they never select an effort or body cap.
    """
    def __init__(self, tokens: HarmonyTokens, processor, decode, *, skip: int,
                 encode=None, mask=None):
        self.parser = HarmonyParser(tokens)
        self._processor, self._decode = processor, decode
        self._seen = skip
        self._final_start: int | None = None
        self._mask = mask
        self._later_headers = None
        self._header_node = None
        if (encode is None) != (mask is None):
            raise HarmonyError("Harmony header constraints require both tokenizer and masking functions.")
        if encode is not None:
            headers = []
            for channel in ("analysis", "final"):
                base = f"<|channel|>{channel}"
                headers.append(base + "<|message|>")
                for content_type in ("json", "JSON"):
                    headers.append(base + f" {content_type}<|message|>")
                    for before in ("", " "):
                        for after in ("", " "):
                            headers.append(base + f"{before}<|constrain|>{after}{content_type}<|message|>")
                            for trailing in ("", " "):
                                headers.append(f"{before}<|constrain|>{after}{content_type}{trailing}"
                                               f"<|channel|>{channel}<|message|>")

            def trie(prefix):
                root = {}
                for header in headers:
                    node = root
                    sequence = encode(prefix + header)
                    if not sequence or len(sequence) > 64 or sequence[-1] != tokens.message:
                        raise HarmonyError("The tokenizer cannot encode bounded Harmony headers.")
                    for token in sequence:
                        node = node.setdefault(int(token), {})
                return root

            self._header_node = trie("")
            self._later_headers = trie("<|start|>assistant")

    def __call__(self, tokens, logits):
        if len(tokens) < self._seen:
            raise HarmonyError("The MLX generation token sequence moved backwards.")
        for index in range(self._seen, len(tokens)):
            token = int(tokens[index])
            before = self.parser.state
            if self._mask is not None and before in {"header", "between"}:
                if self._header_node is None or token not in self._header_node:
                    raise HarmonyError("GPT-OSS sent a token outside the supported Harmony headers.")
                self._header_node = self._header_node[token]
            text = self._decode(token) if self.parser.needs_text else ""
            visible = self.parser.feed(token, text)
            if self._mask is not None:
                if before == "analysis" and self.parser.state == "between":
                    self._header_node = self._later_headers
                elif before == "header" and self.parser.state in {"analysis", "final"}:
                    self._header_node = None
            if self.parser.final and self._final_start is None:
                self._final_start = index + 1
                if self._processor is not None:
                    logits = self._processor(tokens[index + 1:index + 1], logits)
            elif visible and self._processor is not None:
                logits = self._processor(tokens[self._final_start:index + 1], logits)
        self._seen = len(tokens)
        if self._header_node is not None:
            logits = self._mask(logits, tuple(self._header_node))
        return logits
