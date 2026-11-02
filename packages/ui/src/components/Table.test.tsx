import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "./Table";

describe("Table", () => {
  it("renders an accessible table with column headers", () => {
    render(
      <Table>
        <TableCaption>Synthetic rows</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>Alpha</TableCell>
            <TableCell>ok</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    );
    expect(screen.getByRole("table", { name: "Synthetic rows" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Name" })).toHaveAttribute("scope", "col");
    expect(screen.getByRole("cell", { name: "Alpha" })).toBeInTheDocument();
  });
});
