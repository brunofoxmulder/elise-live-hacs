"""Focused regression checks for Gemini Live audio turn handoff."""

import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "custom_components" / "elise_live"
PACKAGE = "_elise_live_turn_test"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(SOURCE)]
sys.modules[PACKAGE] = package

constants = types.ModuleType(f"{PACKAGE}.const")
constants.GEMINI_BLOCKING_TOOL_MODELS = ()
sys.modules[constants.__name__] = constants

homeassistant = types.ModuleType("homeassistant")
homeassistant.__path__ = []
core = types.ModuleType("homeassistant.core")
core.Context = type("Context", (), {})
core.HomeAssistant = type("HomeAssistant", (), {})
sys.modules["homeassistant"] = homeassistant
sys.modules["homeassistant.core"] = core


def load_module(name):
    spec = importlib.util.spec_from_file_location(
        f"{PACKAGE}.{name}", SOURCE / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


live = load_module("live")
gemini = load_module("gemini")
runtime = load_module("runtime")


def server_message(*, audio=None, transcript=None, generation=False, turn=False):
    parts = []
    if audio is not None:
        parts.append(
            types.SimpleNamespace(
                text=None, inline_data=types.SimpleNamespace(data=audio)
            )
        )
    content = types.SimpleNamespace(
        model_turn=types.SimpleNamespace(parts=parts) if parts else None,
        output_transcription=(
            types.SimpleNamespace(text=transcript) if transcript else None
        ),
        input_transcription=None,
        generation_complete=generation,
        turn_complete=turn,
    )
    return types.SimpleNamespace(
        tool_call=None,
        server_content=content,
        go_away=None,
        session_resumption_update=None,
    )


class FakeSession:
    async def receive(self):
        yield server_message(audio=b"voice", transcript="Bonjour")
        yield server_message(generation=True)
        yield server_message(turn=True)


class LiveTurnTests(unittest.IsolatedAsyncioTestCase):
    async def test_nullable_string_enum_is_accepted_by_gemini_schema(self):
        schema = {"type": "object", "properties": {"compare": {
            "type": "string", "enum": ["eq", "ne", None],
        }}}
        result = gemini._gemini_schema(schema)
        compare = result["properties"]["compare"]
        self.assertEqual(compare["type"], "STRING")
        self.assertEqual(compare["enum"], ["eq", "ne"])
        self.assertTrue(compare["nullable"])
        self.assertNotIn(None, compare["enum"])

    async def test_nullable_only_enum_does_not_send_invalid_enum(self):
        result = gemini._gemini_schema({"type": "string", "enum": [None]})
        self.assertNotIn("enum", result)
        self.assertTrue(result["nullable"])

    async def test_non_nullable_enum_keeps_values(self):
        result = gemini._gemini_schema({"type": "string", "enum": ["on", "off"]})
        self.assertEqual(result["enum"], ["on", "off"])
        self.assertNotIn("nullable", result)

    async def test_generation_completion_precedes_turn_completion(self):
        events = [
            event
            async for event in gemini.GeminiLiveSession(FakeSession()).receive()
        ]
        self.assertEqual([event.audio for event in events if event.audio], [b"voice"])
        self.assertEqual(
            [event.output_transcript for event in events if event.output_transcript],
            ["Bonjour"],
        )
        self.assertEqual(
            [(event.generation_complete, event.turn_complete) for event in events[-2:]],
            [(True, False), (False, True)],
        )

    async def test_fallback_key_claims_audio_before_transcript_arrives(self):
        store = runtime.TurnStore()
        transcript = runtime.TextStream()
        audio = runtime.AudioStream()
        store.add_streaming_audio(transcript, audio, "-- elise live -- turn")
        self.assertIs(store.take_streaming_audio("-- elise live -- turn"), audio)
        self.assertIsNone(store.take_streaming_audio("-- elise live -- turn"))

    async def test_transcript_prefix_claims_audio(self):
        store = runtime.TurnStore()
        transcript = runtime.TextStream()
        transcript.add_chunk("Bonjour")
        audio = runtime.AudioStream()
        store.add_streaming_audio(transcript, audio, "-- elise live -- another")
        self.assertIs(store.take_streaming_audio("Bon"), audio)


if __name__ == "__main__":
    unittest.main()
