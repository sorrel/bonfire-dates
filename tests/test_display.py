from bonfire_dates.display import table, width


def test_width_counts_emoji_as_two_columns():
    assert width("🔥 Firle") == 8
    assert width("🕯️ Parade") == 9  # candle + variation selector still takes two columns
    assert width("plain") == 5


def test_table_aligns_rows_with_different_emoji():
    out = table([["🔥 Firle", "92%"], ["🕯️ Parade", "56%"]], ["Event", "Sure"]).splitlines()
    assert width(out[2].split("92%")[0]) == width(out[3].split("56%")[0])


def test_no_line_ends_in_spaces():
    out = table([["a", ("10%", {"fg": "red"})], ["bbbb", "5%"]], ["Event", "Sure"])
    import click
    assert all(not click.unstyle(line).endswith(" ") for line in out.splitlines())
