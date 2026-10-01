from shared import pdf_utils, pipeline, storage


def test_select_for_prompt_keeps_conclusion():
    body = "intro " * 4000
    text = f"Title\n{body}\nConclusion\nThe main finding is X.\nReferences\n[1] ref"
    out = pdf_utils.select_for_prompt(text, max_chars=3000)
    assert "main finding is X" in out and "[1] ref" not in out and len(out) < 3200


def test_top_chunks_finds_relevant_passage():
    text = ("alpha " * 300) + " the learning rate was 0.001 " + ("beta " * 300)
    assert "learning rate" in pdf_utils.top_chunks(text, "What learning rate was used?", k=1)[0]


def test_safe_filename():
    assert storage.safe_filename("../../etc/passwd.pdf") == "passwd.pdf"
    assert storage.safe_filename("my paper (v2).PDF").endswith(".PDF")


def test_derived_keys_handles_uppercase_extension():
    out, txt = pipeline.derived_keys("uploads/2026-01-01/abc_Paper.PDF")
    assert out == "processed/2026-01-01/abc_Paper.json" and txt == "text/2026-01-01/abc_Paper.txt"
