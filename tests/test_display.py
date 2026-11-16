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


def test_until_reads_naturally():
    from datetime import date
    from bonfire_dates.display import until
    today = date(2026, 11, 16)
    assert until(date(2026, 11, 16), today) == "today"
    assert until(date(2026, 11, 17), today) == "tomorrow"
    assert until(date(2026, 11, 29), today) == "13 days"
    assert until(date(2026, 11, 30), today) == "2 weeks"
    assert until(date(2027, 1, 18), today) == "9 weeks"
    assert until(date(2027, 1, 19), today) == "2 months"
    assert until(date(2027, 10, 23), today) == "11 months"
    assert until(date(2028, 3, 1), today) == "15 months"
