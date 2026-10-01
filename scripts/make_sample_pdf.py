"""Generates samples/sample_paper.pdf — a small fake research paper for testing.
Run:  python scripts/make_sample_pdf.py"""
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:
    import fitz

SECTIONS = [
    ("Food Waste Reduction with Agile Circular Supply Chains", 18),
    ("Abstract", 13),
    ("Food waste in retail supply chains causes economic and environmental losses. "
     "This paper studies how agile project management and circular economy principles "
     "can be combined to reduce food waste. We run a twelve-week pilot with three "
     "regional retailers using two-week sprints, demand forecasting and redistribution "
     "of surplus food to food banks. Waste fell by 23 percent compared to a control group.", 10),
    ("1 Introduction", 13),
    ("Roughly one third of food produced is lost or wasted. Traditional waterfall "
     "planning in supply chains reacts slowly to demand changes. Agile methods such as "
     "Scrum emphasise short feedback loops, which may help perishable inventory decisions. "
     "Circular economy thinking treats surplus as a resource rather than waste.", 10),
    ("2 Methodology", 13),
    ("We used a quasi-experimental design. Three stores adopted sprint-based replenishment "
     "planning with daily stand-ups between store managers and logistics planners. Demand "
     "forecasting used gradient boosted trees trained on two years of point-of-sale data. "
     "Surplus items were routed to partner food banks and composting facilities.", 10),
    ("3 Results", 13),
    ("Pilot stores reduced food waste by 23 percent and stock-outs by 6 percent. Forecast "
     "error decreased from 18 to 12 percent MAPE. Staff reported that sprint reviews "
     "improved coordination between purchasing and store operations.", 10),
    ("4 Conclusion", 13),
    ("Combining agile project management with circular economy practices measurably reduces "
     "retail food waste. Limitations include the small sample of three stores and a short "
     "pilot. Future work should test the approach across seasons and in other countries.", 10),
    ("References", 13),
    ("[1] Schwaber, K. Agile Project Management with Scrum. 2004.", 9),
]


def main():
    doc = fitz.open()
    page = doc.new_page()
    y = 60
    for text, size in SECTIONS:
        rect = fitz.Rect(60, y, 540, y + 400)
        page.insert_textbox(rect, text, fontsize=size, fontname="helv")
        lines = max(1, len(text) * size // 900 + 1)
        y += lines * (size + 6) + 14
        if y > 760:
            page, y = doc.new_page(), 60
    doc.set_metadata({"title": SECTIONS[0][0]})
    out = Path(__file__).resolve().parent.parent / "samples" / "sample_paper.pdf"
    out.parent.mkdir(exist_ok=True)
    doc.save(out)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
