from chunker import split_text


def _words(n):
    return " ".join(f"w{i}" for i in range(n))


def test_empty_text_gives_no_chunks():
    assert split_text("") == []


def test_short_text_is_one_chunk():
    assert split_text(_words(10)) == [_words(10)]


def test_windows_overlap_by_50_words():
    chunks = split_text(_words(600), chunk_size=300, overlap=50)
    assert len(chunks) == 3
    first, second = chunks[0].split(), chunks[1].split()
    assert first[-50:] == second[:50]
    assert second[0] == "w250"


def test_every_word_is_covered():
    text = _words(1234)
    covered = set()
    for chunk in split_text(text):
        covered.update(chunk.split())
    assert covered == set(text.split())
