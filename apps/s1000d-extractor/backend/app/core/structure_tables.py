"""IR construction for source table blocks."""

from app.core.ir import IRNode, RawBlock


def table_node_from_block(block: RawBlock, node_id: str, rows: list[list[str]]) -> IRNode:
    return IRNode(
        id=node_id,
        kind="table",
        form="table",
        page=block.page,
        zone=block.zone,
        table_rows=rows,
        table_header=block.table_header,
        table_cell_bboxes=block.table_cell_bboxes,
        table_cell_titles=block.table_cell_titles,
        page_width=block.page_width,
        page_height=block.page_height,
        confidence=0.6,
    )
