from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
SCREENSHOTS = ROOT / "docs" / "screenshots" / "catia-toolbox"
OUTPUT = ROOT / "docs" / "Catia_Toolbox_User_Guide_EN.docx"


def add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run("CATIA TOOLBOX  |  ")
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(100, 116, 139)


def add_screenshot(document, filename):
    path = SCREENSHOTS / "en" / filename
    if not path.exists():
        return
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.add_run().add_picture(str(path), width=Inches(6.55))


def add_screen_section(document, title, route, description, filename, notes):
    document.add_heading(title, level=1)
    paragraph = document.add_paragraph()
    paragraph.add_run("Route  ").bold = True
    paragraph.add_run(route)
    document.add_paragraph(description)
    add_screenshot(document, filename)
    notes_paragraph = document.add_paragraph()
    notes_paragraph.add_run("Key actions  ").bold = True
    notes_paragraph.add_run(notes)


document = Document()
section = document.sections[0]
section.top_margin = Inches(0.65)
section.bottom_margin = Inches(0.65)
section.left_margin = Inches(0.75)
section.right_margin = Inches(0.75)
add_page_number(section.footer.paragraphs[0])

styles = document.styles
styles["Normal"].font.name = "Aptos"
styles["Normal"].font.size = Pt(10)
styles["Normal"].font.color.rgb = RGBColor(51, 65, 85)
for style_name in ("Title", "Heading 1", "Heading 2"):
    styles[style_name].font.name = "Aptos Display"
    styles[style_name].font.color.rgb = RGBColor(15, 23, 42)
styles["Title"].font.size = Pt(30)
styles["Heading 1"].font.size = Pt(18)

small = styles.add_style("Small note", WD_STYLE_TYPE.PARAGRAPH)
small.font.name = "Aptos"
small.font.size = Pt(8)
small.font.color.rgb = RGBColor(100, 116, 139)

cover = document.add_paragraph()
cover.space_after = Pt(18)
run = cover.add_run("CATIA TOOLBOX")
run.bold = True
run.font.name = "Aptos Display"
run.font.size = Pt(34)
run.font.color.rgb = RGBColor(37, 99, 235)

subtitle = document.add_paragraph("User guide | English edition")
subtitle.style = "Subtitle"
subtitle.paragraph_format.space_after = Pt(28)

document.add_paragraph(
    "A concise visual guide to the CATIA Toolbox workflow: identify CATParts, prepare Composer conversions, "
    "inspect assembly structure, and export reviewable plans."
)

meta = document.add_paragraph()
meta.paragraph_format.space_before = Pt(30)
meta.add_run("Purpose\n").bold = True
meta.add_run("Support CATIA and Composer preparation using exported, neutral data.\n")
meta.add_run("Operating model\n").bold = True
meta.add_run("Plan-first and non-destructive: the application generates reviewable CSV and script outputs; it does not modify CATIA files.\n")
meta.add_run("Audience\n").bold = True
meta.add_run("Engineering, technical documentation, and quality-control teams.")

document.add_page_break()
document.add_heading("Workflow at a glance", level=1)
document.add_paragraph(
    "CATIA Toolbox is organized around a five-step production workflow. Each step can be reviewed independently "
    "before any generated script is executed."
)
workflow = [
    ("1. Identification", "Read the nomenclature workbook and DE archive metadata to identify CATParts and single-body parts."),
    ("2. Preparation", "Create a CATIA 3D to Composer conversion plan."),
    ("3. Processing", "Review structure, colorization, SMGXML color changes, and optimization proposals."),
    ("4. Integration", "Prepare SMGXML rename and part-replacement plans."),
    ("5. Quality control", "Complete the assembly checklist and export the review result."),
]
for label, text in workflow:
    paragraph = document.add_paragraph(style="List Bullet")
    paragraph.add_run(f"{label}: ").bold = True
    paragraph.add_run(text)

document.add_heading("Design principles", level=1)
for text in (
    "Metadata-first processing keeps source files untouched.",
    "Dry-run outputs make every proposed action reviewable.",
    "Local folders, synchronized OneDrive folders, and neutral listings can be used as sources.",
    "Exports are designed for traceability: CSV plans, scripts, macros, and visual previews.",
):
    document.add_paragraph(text, style="List Bullet")

document.add_page_break()
document.add_heading("Screen-by-screen reference", level=1)
document.add_paragraph(
    "The captures below were taken with the EN language switch enabled. Empty states are intentional: they show "
    "the interface before a source import is selected."
)
screens = [
    ("1. Identification", "/identification", "Identification.png", "Reads the nomenclature workbook and DE archive metadata to identify CATParts and single-body parts.", "Select the workbook, preview its tabs, configure the mapping, and launch analysis. Operational when source files are configured."),
    ("2. Compare", "/diff", "Compare.png", "Compares two imports and reports added, removed, and modified parts.", "Select the two imports, run the comparison, review entries, and export the result. Requires imported listings."),
    ("3. Composer conversion", "/conversion", "Conversion.png", "Prepares a CATIA 3D to Composer conversion plan with a reviewable mapping and script.", "Select an import, review the plan, and export the script. Execution remains user-controlled and dry-run by default."),
    ("4. SMGXML color", "/smgxml-recolor", "SMGXML-color.png", "Inspects and prepares color changes for mono-color SIN parts in an SMGXML file.", "Inspect the SMGXML, review proposed changes, and choose dry-run or apply mode. Exact attributes depend on the target file format."),
    ("5. Colorization", "/colorization", "Colorization.png", "Assigns RGB colors by change, type, or depth and provides a visual simulation.", "Choose a strategy, generate the plan, inspect the tile preview, and export CSV, macro, or Composer script."),
    ("6. Tree", "/tree", "Tree.png", "Displays the current import hierarchy and structural metrics such as depth and nesting.", "Expand the tree and use the metrics to identify structural hotspots. Requires an import."),
    ("7. Suggestions", "/suggestions", "Suggestions.png", "Generates a reorganization proposal for an imported structure.", "Review each proposed action and accept or reject it before exporting. LLM-assisted suggestions depend on configuration."),
    ("8. Export", "/export", "Export.png", "Exports reviewable plans and scripts generated by the toolbox.", "Choose the run and output format. No source CATIA file is changed by the export action."),
    ("9. SMGXML rename", "/smgxml-rename", "SMGXML-rename.png", "Prepares replacement of an old part name with a new name in SMGXML.", "Inspect the proposed rename, review the change set, and apply only after validation. Dry-run is the default."),
    ("10. Replacement", "/replacement", "Replacement.png", "Creates a part replacement plan from a CSV or JSON mapping.", "Upload the mapping, review the proposed replacements, and export the CATIA macro skeleton."),
    ("11. Quality control", "/qc", "Quality-control.png", "Provides an interactive checklist for verifying parts in the assembly.", "Create or open a checklist, mark items as OK, KO, or N/A, add comments, and export the review."),
    ("12. Checks", "/checks", "Checks.png", "Runs configurable checks for depth, naming, forbidden extensions, duplicates, and empty folders.", "Select an import, run the checks, review findings, and export the results."),
    ("13. Data", "/data", "Data.png", "Shows stored import, run, and suggestion data and provides reset operations.", "Review counters and use reset actions deliberately. Persistent configuration is preserved by convention."),
    ("14. Settings", "/settings", "Settings.png", "Configures Mistral connectivity, models, source roots, and output roots.", "Set runtime values, test the LLM connection, and verify the health badge before using AI-assisted modules."),
]
for index, screen in enumerate(screens):
    if index:
        document.add_page_break()
    add_screen_section(document, screen[0], screen[1], screen[3], screen[2], screen[4])

document.add_page_break()
document.add_heading("Outputs and review", level=1)
document.add_paragraph(
    "All generated outputs are intended to be reviewed by the user before execution. Typical deliverables include "
    "CSV plans, batch or shell scripts, Python Composer scripts, CATIA macros, SMGXML change sets, and visual colorization previews."
)
document.add_heading("Operational safeguards", level=2)
for text in (
    "The backend does not move, rename, delete, or convert CATIA files automatically.",
    "Dry-run is the default for Composer and SMGXML operations.",
    "Apply-mode SMGXML changes preserve a backup before writing.",
    "Input scanning is metadata-oriented and remains confined to configured roots.",
):
    document.add_paragraph(text, style="List Bullet")

document.add_paragraph("CATIA Toolbox | Internal product documentation", style="Small note")
document.save(OUTPUT)
print(f"created {OUTPUT}")
