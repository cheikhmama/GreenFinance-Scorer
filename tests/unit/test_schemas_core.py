from app.core.schemas import Page


def test_page_serializes_generic_items_and_envelope_fields() -> None:
    page: Page[str] = Page(items=["a", "b"], page=1, page_size=20, total=2, pages=1)

    assert page.model_dump() == {
        "items": ["a", "b"],
        "page": 1,
        "page_size": 20,
        "total": 2,
        "pages": 1,
    }
