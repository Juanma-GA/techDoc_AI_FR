package pdf

import (
	"bytes"
	"context"
	"fmt"
	"image"
	"image/color"
	"image/png"
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

	imageOne := filepath.Join(tempDir, "one.png")
	imageTwo := filepath.Join(tempDir, "two.png")
	writeTestPNG(t, imageOne)
	writeTestPNG(t, imageTwo)
	imagesPDF := filepath.Join(tempDir, "images.pdf")
	if err := processor.ImagesToPDF(ctx, []string{imageOne, imageTwo}, imagesPDF); err != nil {
		t.Fatalf("ImagesToPDF() error = %v", err)
	}
	assertPageCount(t, processor, imagesPDF, 2)

	compressed := filepath.Join(tempDir, "compressed.pdf")
	if err := processor.Compress(ctx, first, compressed); err != nil {
		t.Fatalf("Compress() error = %v", err)
	}
	assertPageCount(t, processor, compressed, 3)

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

	rotated := filepath.Join(tempDir, "rotated.pdf")
	if err := processor.Rotate(ctx, first, rotated, []int{2}, 90); err != nil {
		t.Fatalf("Rotate() error = %v", err)
	}
	assertPageCount(t, processor, rotated, 3)

	rotatedAll := filepath.Join(tempDir, "rotated-all.pdf")
	if err := processor.Rotate(ctx, first, rotatedAll, nil, 180); err != nil {
		t.Fatalf("Rotate() with empty selection error = %v", err)
	}
	assertPageCount(t, processor, rotatedAll, 3)
}

func TestPDFCPUSplitDocumentReusesSourceContext(t *testing.T) {
	tempDir := t.TempDir()
	input := filepath.Join(tempDir, "source.pdf")
	if err := os.WriteFile(input, testPDF(t, 3), 0o600); err != nil {
		t.Fatal(err)
	}
	document, err := NewPDFCPU().OpenSplitDocument(context.Background(), input)
	if err != nil {
		t.Fatalf("OpenSplitDocument() error = %v", err)
	}
	defer func() {
		if err := document.Close(); err != nil {
			t.Errorf("Close() error = %v", err)
		}
	}()
	if document.PageCount() != 3 {
		t.Fatalf("PageCount() = %d, want 3", document.PageCount())
	}

	for index, pages := range [][]int{{3, 1}, {2}} {
		output := filepath.Join(tempDir, fmt.Sprintf("part-%d.pdf", index+1))
		if err := document.Extract(context.Background(), output, pages); err != nil {
			t.Fatalf("Extract(%v) error = %v", pages, err)
		}
		assertPageCount(t, NewPDFCPU(), output, len(pages))
	}
}

func writeTestPNG(t *testing.T, filePath string) {
	t.Helper()
	file, err := os.Create(filePath)
	if err != nil {
		t.Fatal(err)
	}
	pixel := image.NewRGBA(image.Rect(0, 0, 2, 2))
	pixel.Set(0, 0, color.White)
	if err := png.Encode(file, pixel); err != nil {
		_ = file.Close()
		t.Fatal(err)
	}
	if err := file.Close(); err != nil {
		t.Fatal(err)
	}
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
	widths := make([]int, pageCount)
	for index := range widths {
		widths[index] = 612
	}
	return testPDFWithWidths(t, widths...)
}

// testPDFWithWidths builds one page per width so tests can identify pages after reordering.
func testPDFWithWidths(t *testing.T, widths ...int) []byte {
	t.Helper()
	pageCount := len(widths)
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
		writeObject(page+2, fmt.Sprintf("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d 792] /Resources << >> >>", widths[page-1]))
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
