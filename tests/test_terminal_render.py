"""The terminal window has to show what a terminal shows.

The aim is not to out-do Windows Terminal but to reproduce it inside the app:
256 colours, the usual text attributes, Russian intact whatever encoding a tool
emits, and box drawing that stays drawn. Control characters are not output and
must never reach the page.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from system_core.core.terminal_render import (  # noqa: E402
    _xterm_256_color,
    ansi_to_html,
    decode_output_bytes,
    strip_ansi,
)

RUSSIAN = "Ошибка: не найден файл отчёт.docx"
TABLE = "\n".join(
    (
        "┌────────────┬────────┐",
        "│ Файл       │ Размер │",
        "├────────────┼────────┤",
        "│ отчёт.docx │  1.2 МБ│",
        "└────────────┴────────┘",
    )
)


@pytest.mark.parametrize(
    ("index", "expected"),
    [
        (16, "#000000"),   # first cube entry
        (21, "#0000ff"),   # pure blue corner
        (46, "#00ff00"),   # pure green corner
        (196, "#ff0000"),  # pure red corner
        (208, "#ff8700"),  # the orange every CLI uses for warnings
        (231, "#ffffff"),  # last cube entry
        (232, "#080808"),  # first grey
        (244, "#808080"),  # mid grey
        (255, "#eeeeee"),  # last grey
    ],
)
def test_the_256_palette_matches_the_standard(index: int, expected: str) -> None:
    """Indices 16-255 are the same in xterm and in Windows Terminal."""
    assert _xterm_256_color(index, background=False) == expected


def test_the_first_sixteen_indices_come_from_this_app_palette() -> None:
    """0-15 are the terminal's own scheme, so the window matches the rest of the app."""
    from system_core.core.terminal_render import SGR_BG, SGR_FG

    assert _xterm_256_color(1, background=False) == SGR_FG[31]
    assert _xterm_256_color(9, background=False) == SGR_FG[91]
    assert _xterm_256_color(1, background=True) == SGR_BG[41]


def test_256_colour_reaches_the_page() -> None:
    assert ansi_to_html("\x1b[38;5;208mтекст\x1b[0m") == '<span style="color:#ff8700">текст</span>'
    assert ansi_to_html("\x1b[48;5;22mтекст\x1b[0m") == '<span style="background-color:#005f00">текст</span>'


def test_text_attributes_reach_the_page() -> None:
    assert "text-decoration:underline" in ansi_to_html("\x1b[4mтекст\x1b[24m")
    assert "font-style:italic" in ansi_to_html("\x1b[3mтекст\x1b[23m")
    assert "text-decoration:line-through" in ansi_to_html("\x1b[9mтекст\x1b[29m")
    assert "font-weight:700" in ansi_to_html("\x1b[1mтекст\x1b[22m")


def test_24_bit_colour_is_read_as_colour_and_not_as_dim() -> None:
    """38;2;R;G;B used to land on code 2 and turn the text dim instead of colouring it."""
    rendered = ansi_to_html("\x1b[38;2;120;200;80mтекст\x1b[0m")

    assert "opacity" not in rendered
    assert "color:#87d75f" in rendered


@pytest.mark.parametrize("encoding", ["utf-8", "cp866", "cp1251"])
def test_russian_survives_whatever_a_tool_emits(encoding: str) -> None:
    assert decode_output_bytes(RUSSIAN.encode(encoding)) == RUSSIAN


@pytest.mark.parametrize("encoding", ["utf-8", "cp866"])
def test_box_drawing_survives(encoding: str) -> None:
    """Windows console tools draw tables in cp866; cp1251 has no box characters at all."""
    assert decode_output_bytes(TABLE.encode(encoding)) == TABLE


def test_box_drawing_reaches_the_page_with_its_colour() -> None:
    rendered = ansi_to_html("\x1b[38;5;208m│ Файл ├ Размер │\x1b[0m")

    assert rendered == '<span style="color:#ff8700">│ Файл ├ Размер │</span>'


@pytest.mark.parametrize("char", ["\x00", "\x07", "\x1f", "\x08", "\x7f"])
def test_control_characters_never_reach_the_page(char: str) -> None:
    assert char not in ansi_to_html(f"до{char}после")
    assert char not in strip_ansi(f"до{char}после")


def test_a_tab_and_a_newline_are_not_control_characters() -> None:
    """They carry layout the terminal is expected to keep."""
    assert "\t" in strip_ansi("колонка1\tколонка2")
    assert "\n" in strip_ansi("строка\nстрока")


def test_html_in_the_output_is_escaped() -> None:
    assert "<script>" not in ansi_to_html("<script>alert(1)</script>")


ASCII_TABLES = {
    "rules made of bars": "|--------|--------|\n| Файл   | Размер |\n|--------|--------|",
    "rules made of plus": "+--------+--------+\n| Файл   | Размер |\n+--------+--------+",
    "markdown": "| Файл | Размер |\n|------|--------|\n| отчёт | 1.2 МБ |",
    "plain divider": "Итого\n--------------------\n12 файлов",
    "box drawing": "┌───┬───┐\n│ Ф │ Р │\n└───┴───┘",
    "slashes": "  /\\  \n /  \\ \n/____\\",
}


@pytest.mark.parametrize(("name", "sample"), sorted(ASCII_TABLES.items()))
def test_a_table_arrives_with_every_line_it_had(name: str, sample: str) -> None:
    r"""Tables used to lose their rules and arrive as loose bars.

    Any line made only of `-`, `\`, `|`, `/` counted as a spinner frame, which is
    exactly what the horizontal rule of an ASCII table looks like.
    """
    from system_core.core.terminal_render import _decoded_output_lines

    # Trailing spaces are trimmed per line; what matters is that no line is dropped.
    expected = [line.rstrip() for line in sample.split("\n") if line.strip()]

    assert _decoded_output_lines(sample) == expected


def test_a_progress_bar_leaves_one_line_and_not_one_per_redraw() -> None:
    """tqdm redraws its line with a carriage return and never with a newline.

    The reader splits on newlines, so a whole run arrives as one part. Treating
    each carriage return as a line break turned a hundred redraws into a hundred
    log lines.
    """
    from system_core.core.terminal_render import _decoded_output_lines

    frames = "".join(
        f"\rОбработка: {percent:3d}%|{'█' * (percent // 10):<10}| {percent}/100"
        for percent in (0, 25, 50, 75, 100)
    )

    assert _decoded_output_lines(frames + "\nГотово\n") == [
        "Обработка: 100%|██████████| 100/100",
        "Готово",
    ]


def test_a_spinner_keeps_its_message_and_costs_one_line() -> None:
    r"""Tools write the whole line each frame — `\rРаботаю -`, `\rРаботаю \` — so the
    message is part of the redraw and must survive it."""
    from system_core.core.terminal_render import _decoded_output_lines

    spinner = "".join(f"\rРаботаю {frame}" for frame in "-\\|/")

    assert _decoded_output_lines(spinner + "\nготово\n") == ["Работаю /", "готово"]


def test_a_short_redraw_does_not_swallow_the_tail() -> None:
    """A carriage return returns the cursor; it does not clear the line."""
    from system_core.core.terminal_render import _decoded_output_lines

    assert _decoded_output_lines("работаю долго\rготов") == ["готоваю долго"]


def test_a_bare_frame_left_on_its_own_line_is_still_dropped() -> None:
    from system_core.core.terminal_render import _decoded_output_lines

    assert _decoded_output_lines("шаг\n|\nготово") == ["шаг", "готово"]


@pytest.mark.parametrize(
    ("line", "is_table"),
    [
        ("| Файл | Размер |", True),
        ("┌───┬───┐", True),
        ("+---+---+", True),
        ("|------|------|", True),
        ("--------------------", True),
        ("====================", True),
        ("Обработка: 100% готово", False),
        ("a | b", False),
        (r"E:\TOOLS\Refactor\Audion Project Unifier\input\Андреевское.docx", False),
        ("", False),
    ],
)
def test_only_table_lines_are_marked_unwrappable(line: str, is_table: bool) -> None:
    """Ordinary output still wraps; a long path must not push the panel sideways."""
    from system_core.core.terminal_render import line_holds_a_table

    assert line_holds_a_table(line) is is_table


def test_the_marker_class_reaches_the_markup() -> None:
    from system_core.core.terminal_render import terminal_lines_html

    rendered = terminal_lines_html(["| Файл | Размер |", "обычная строка"])

    assert '<span class="audion-terminal-line audion-terminal-line-table">' in rendered
    assert '<span class="audion-terminal-line">обычная строка</span>' in rendered


def test_the_renderer_keeps_its_colour_between_lines() -> None:
    """A tool opens a colour on one line and closes it on a later one."""
    from system_core.core.terminal_render import AnsiHtmlRenderer

    renderer = AnsiHtmlRenderer()
    first = renderer.render("\x1b[38;5;46mзелёный")
    second = renderer.render(" и дальше тем же цветом")

    assert "color:#00ff00" in first
    assert "color:#00ff00" in second

    renderer.reset()
    assert "<span" not in renderer.render("обычный")


def test_every_name_the_fleet_calls_this_class_by_is_present() -> None:
    """Each app grew its own copy with its own method names; all are kept."""
    from system_core.core.terminal_render import AnsiHtmlRenderer, StatefulAnsiHtmlRenderer

    assert StatefulAnsiHtmlRenderer is AnsiHtmlRenderer
    renderer = AnsiHtmlRenderer()
    assert renderer.feed == renderer.render
    assert renderer.finalize() == ""


def test_a_shared_renderer_carries_the_colour_across_refreshes() -> None:
    from system_core.core.terminal_render import AnsiHtmlRenderer, terminal_lines_html

    shared = AnsiHtmlRenderer()
    first = terminal_lines_html(["\x1b[38;5;196mошибка"], renderer=shared)
    second = terminal_lines_html(["продолжение"], renderer=shared)

    assert "color:#ff0000" in first
    assert "color:#ff0000" in second


def test_without_a_shared_renderer_each_call_starts_clean() -> None:
    from system_core.core.terminal_render import terminal_lines_html

    assert "<span style" not in terminal_lines_html(["обычная строка"])
