package pdf

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestPDFCPUOperations(t *testing.T) {
	tempDir := t.TempDir()
	first := filepath.Join(tempDir, "first.pdf")
	second := filepath.Join(tempDir, "second.pdf")
	if err := os.WriteFile(first, testPDF(t, 3), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(second, testPDF(t, 2), 0o600); err != nil {
		t.Fatal(err)
	}

	processor := NewPDFCPU()
	ctx := context.Background()

	merged := filepath.Join(tempDir, "merged.pdf")
	if err := processor.Merge(ctx, []string{first, second}, merged); err != nil {
		t.Fatalf("Merge() error = %v", err)
	}
	assertPageCount(t, processor, merged, 5)

	extracted := filepath.Join(tempDir, "extracted.pdf")
	if err := processor.Extract(ctx, first, extracted, []int{1, 3}); err != nil {
		t.Fatalf("Extract() error = %v", err)
	}
	assertPageCount(t, processor, extracted, 2)

	deleted := filepath.Join(tempDir, "deleted.pdf")
	if err := processor.Delete(ctx, first, deleted, []int{2}); err != nil {
		t.Fatalf("Delete() error = %v", err)
	}
	assertPageCount(t, processor, deleted, 2)

	reordered := filepath.Join(tempDir, "reordered.pdf")
	if err := processor.Reorder(ctx, first, reordered, []int{3, 1, 2}); err != nil {
		t.Fatalf("Reorder() error = %v", err)
	}
	assertPageCount(t, processor, reordered, 3)
}

func assertPageCount(t *testing.T, processor *PDFCPU, file string, want int) {
	t.Helper()
	got, err := processor.PageCount(context.Background(), file)
	if err != nil {
		t.Fatalf("PageCount(%q) error = %v", file, err)
	}
	if got != want {
		t.Fatalf("PageCount(%q) = %d, want %d", file, got, want)
	}
}

func testPDF(t *testing.T, pageCount int) []byte {
	t.Helper()
	var output bytes.Buffer
	output.WriteString("%PDF-1.7\n")
	offsets := []int{0}
	writeObject := func(number int, body string) {
		offsets = append(offsets, output.Len())
		if _, err := fmt.Fprintf(&output, "%d 0 obj\n%s\nendobj\n", number, body); err != nil {
			t.Fatal(err)
		}
	}

	writeObject(1, "<< /Type /Catalog /Pages 2 0 R >>")
	kids := make([]string, pageCount)
	for page := 1; page <= pageCount; page++ {
		kids[page-1] = fmt.Sprintf("%d 0 R", page+2)
	}
	writeObject(2, fmt.Sprintf("<< /Type /Pages /Kids [%s] /Count %d >>", strings.Join(kids, " "), pageCount))
	for page := 1; page <= pageCount; page++ {
		writeObject(page+2, fmt.Sprintf("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << >> >>"))
	}

	xrefOffset := output.Len()
	if _, err := fmt.Fprintf(&output, "xref\n0 %d\n0000000000 65535 f \n", len(offsets)); err != nil {
		t.Fatal(err)
	}
	for _, offset := range offsets[1:] {
		if _, err := fmt.Fprintf(&output, "%010d 00000 n \n", offset); err != nil {
			t.Fatal(err)
		}
	}
	if _, err := fmt.Fprintf(
		&output,
		"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n",
		len(offsets),
		xrefOffset,
	); err != nil {
		t.Fatal(err)
	}
	return output.Bytes()
}
