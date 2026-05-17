"""
Pure Python SentencePiece model reader and decoder.
Only supports decoding (token IDs → text), no training or encoding.
Reads .model files directly without protobuf dependency.
"""

import struct
from pathlib import Path
from typing import List, Optional, Tuple


class SentencePieceModel:
    """Lightweight SentencePiece model reader for decoding only."""

    def __init__(self):
        self.pieces: List[Tuple[str, float]] = []  # (piece, score)
        self.piece_to_id: dict = {}
        self.id_to_piece: dict = {}

    @classmethod
    def from_file(cls, path: str) -> "SentencePieceModel":
        """Load a sentencepiece .model file."""
        import os
        model = cls()

        # 用 os.open 读取，兼容 Windows 中文路径
        flags = os.O_RDONLY
        if hasattr(os, 'O_BINARY'):
            flags |= os.O_BINARY
        fd = os.open(path, flags)
        try:
            data = b""
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                data += chunk
        finally:
            os.close(fd)

        # Parse protobuf manually - we only need the pieces field
        model._parse_pieces(data)
        return model

    def _parse_pieces(self, data: bytes):
        """Parse the pieces from protobuf binary data."""
        pos = 0
        pieces = []

        while pos < len(data):
            # Read field tag
            tag, new_pos = self._read_varint(data, pos)
            if new_pos is None:
                break
            pos = new_pos

            field_number = tag >> 3
            wire_type = tag & 0x7

            if wire_type == 2:  # Length-delimited (string/bytes/message)
                length, pos = self._read_varint(data, pos)
                if pos is None:
                    break
                field_data = data[pos:pos + length]
                pos += length

                # Field 1 = pieces (repeated message)
                if field_number == 1:
                    piece, score = self._parse_piece_message(field_data)
                    if piece is not None:
                        pieces.append((piece, score))
            elif wire_type == 0:  # Varint
                _, pos = self._read_varint(data, pos)
            elif wire_type == 5:  # 32-bit
                pos += 4
            elif wire_type == 1:  # 64-bit
                pos += 8

        # Build mappings
        self.pieces = pieces
        for i, (piece, score) in enumerate(pieces):
            self.piece_to_id[piece] = i
            self.id_to_piece[i] = piece

    def _parse_piece_message(self, data: bytes) -> Tuple[Optional[str], float]:
        """Parse a single piece message (piece string + score float)."""
        piece = None
        score = 0.0
        pos = 0

        while pos < len(data):
            tag, new_pos = self._read_varint(data, pos)
            if new_pos is None:
                break
            pos = new_pos

            field_number = tag >> 3
            wire_type = tag & 0x7

            if wire_type == 2 and field_number == 1:  # piece (string)
                length, pos = self._read_varint(data, pos)
                if pos is None:
                    break
                piece = data[pos:pos + length].decode("utf-8", errors="replace")
                pos += length
            elif wire_type == 5 and field_number == 2:  # score (float)
                if pos + 4 <= len(data):
                    score = struct.unpack("<f", data[pos:pos + 4])[0]
                    pos += 4
                else:
                    break
            elif wire_type == 0:  # varint (type field)
                _, pos = self._read_varint(data, pos)
            else:
                break

        return piece, score

    @staticmethod
    def _read_varint(data: bytes, pos: int) -> Tuple[Optional[int], Optional[int]]:
        """Read a protobuf varint from data at pos."""
        result = 0
        shift = 0
        while pos < len(data):
            byte = data[pos]
            result |= (byte & 0x7F) << shift
            pos += 1
            if not (byte & 0x80):
                return result, pos
            shift += 7
        return None, None

    def decode(self, ids: List[int]) -> str:
        """Decode token IDs to text."""
        text = ""
        for token_id in ids:
            if token_id in self.id_to_piece:
                piece = self.id_to_piece[token_id]
                # SentencePiece uses ▁ (U+2581) as space marker
                piece = piece.replace("▁", " ")
                text += piece
            else:
                text += f"<{token_id}>"
        # Strip leading space
        if text.startswith(" "):
            text = text[1:]
        return text

    def encode(self, text: str) -> List[int]:
        """Encode text to token IDs (basic greedy matching)."""
        # Prepend ▁ for space
        text = "▁" + text.replace(" ", "▁")
        ids = []
        pos = 0
        while pos < len(text):
            # Try longest match first
            best_len = 0
            best_id = None
            for length in range(min(32, len(text) - pos), 0, -1):
                substr = text[pos:pos + length]
                if substr in self.piece_to_id:
                    best_len = length
                    best_id = self.piece_to_id[substr]
                    break
            if best_id is not None:
                ids.append(best_id)
                pos += best_len
            else:
                pos += 1  # Skip unknown character
        return ids

    @property
    def vocab_size(self) -> int:
        return len(self.pieces)
