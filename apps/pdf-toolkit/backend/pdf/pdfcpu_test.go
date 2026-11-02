package pdf

import (
	"archive/zip"
	"bytes"
	"context"
	"errors"
	"fmt"
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/pdfcpu/pdfcpu/pkg/api"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu"

	"pdf-toolkit/services"
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

func TestPDFCPUExtractImagesCreatesZIP(t *testing.T) {
	tempDir := t.TempDir()
	imagePath := filepath.Join(tempDir, "source.png")
	input := filepath.Join(tempDir, "images.pdf")
	output := filepath.Join(tempDir, "extracted-images.zip")
	writeTestPNG(t, imagePath)
	if err := NewPDFCPU().ImagesToPDF(context.Background(), []string{imagePath}, input); err != nil {
		t.Fatalf("ImagesToPDF() error = %v", err)
	}

	if err := NewPDFCPU().ExtractImages(context.Background(), input, output); err != nil {
		t.Fatalf("ExtractImages() error = %v", err)
	}
	archive, err := zip.OpenReader(output)
	if err != nil {
		t.Fatalf("open extracted images archive: %v", err)
	}
	defer archive.Close()
	if len(archive.File) != 1 || archive.File[0].Name != "page-0001-image-0001.png" {
		t.Fatalf("archive files = %+v, want one PNG from page 1", archive.File)
	}
	extracted, err := archive.File[0].Open()
	if err != nil {
		t.Fatalf("open extracted image: %v", err)
	}
	config, decodeErr := png.DecodeConfig(extracted)
	closeErr := extracted.Close()
	if decodeErr != nil || closeErr != nil {
		t.Fatalf("decode extracted image: %v", errors.Join(decodeErr, closeErr))
	}
	if config.Width != 2 || config.Height != 2 {
		t.Fatalf("extracted image size = %dx%d, want 2x2", config.Width, config.Height)
	}
}

func TestPDFCPUExtractImagesRejectsPDFWithoutImages(t *testing.T) {
	tempDir := t.TempDir()
	input := filepath.Join(tempDir, "empty.pdf")
	output := filepath.Join(tempDir, "extracted-images.zip")
	if err := os.WriteFile(input, testPDF(t, 1), 0o600); err != nil {
		t.Fatal(err)
	}

	err := NewPDFCPU().ExtractImages(context.Background(), input, output)
	if !errors.Is(err, services.ErrNoImages) {
		t.Fatalf("ExtractImages() error = %v, want ErrNoImages", err)
	}
	if _, statErr := os.Stat(output); !errors.Is(statErr, os.ErrNotExist) {
		t.Fatalf("empty image archive remains after extraction: %v", statErr)
	}
}

func TestPDFCPUCleanRemovesMetadataAndAnnotations(t *testing.T) {
	tempDir := t.TempDir()
	input := filepath.Join(tempDir, "source.pdf")
	output := filepath.Join(tempDir, "cleaned.pdf")
	if err := os.WriteFile(input, testPDFWithSensitiveMetadataAndAnnotation(t), 0o600); err != nil {
		t.Fatal(err)
	}

	processor := NewPDFCPU()
	if err := processor.Clean(context.Background(), input, output); err != nil {
		t.Fatalf("Clean() error = %v", err)
	}
	assertPageCount(t, processor, output, 1)
	cleanedBytes, err := os.ReadFile(output)
	if err != nil {
		t.Fatal(err)
	}
	for _, privateText := range []string{"private title", "private author", "private annotation", "private xmp metadata"} {
		if bytes.Contains(cleanedBytes, []byte(privateText)) {
			t.Errorf("cleaned PDF still contains %q", privateText)
		}
	}

	file, err := os.Open(output)
	if err != nil {
		t.Fatal(err)
	}
	properties, err := api.Properties(file, nil)
	closeErr := file.Close()
	if err != nil || closeErr != nil {
		t.Fatalf("read cleaned PDF properties: %v", errors.Join(err, closeErr))
	}
	if len(properties) != 0 {
		t.Fatalf("cleaned PDF properties = %v, want none", properties)
	}

	file, err = os.Open(output)
	if err != nil {
		t.Fatal(err)
	}
	annotations, err := api.Annotations(file, nil, nil)
	closeErr = file.Close()
	if err != nil || closeErr != nil {
		t.Fatalf("read cleaned PDF annotations: %v", errors.Join(err, closeErr))
	}
	count, _, err := pdfcpu.ListAnnotations(annotations)
	if err != nil {
		t.Fatalf("list cleaned PDF annotations: %v", err)
	}
	if count != 0 {
		t.Fatalf("cleaned PDF annotation count = %d, want 0", count)
	}
}

func TestPDFCPUCleanAcceptsPDFWithoutMetadataOrAnnotations(t *testing.T) {
	tempDir := t.TempDir()
	input := filepath.Join(tempDir, "source.pdf")
	output := filepath.Join(tempDir, "cleaned.pdf")
	if err := os.WriteFile(input, testPDF(t, 1), 0o600); err != nil {
		t.Fatal(err)
	}

	if err := NewPDFCPU().Clean(context.Background(), input, output); err != nil {
		t.Fatalf("Clean() error = %v", err)
	}
	assertPageCount(t, NewPDFCPU(), output, 1)
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

func testPDFWithSensitiveMetadataAndAnnotation(t *testing.T) []byte {
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

	writeObject(1, "<< /Type /Catalog /Pages 2 0 R /Metadata 6 0 R >>")
	writeObject(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
	writeObject(3, "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << >> /Annots [4 0 R] >>")
	writeObject(4, "<< /Type /Annot /Subtype /Text /Rect [0 0 20 20] /Contents (private annotation) /P 3 0 R >>")
	writeObject(5, "<< /Title (private title) /Author (private author) >>")
	xmp := []byte(`<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description rdf:about="">private xmp metadata</rdf:Description></rdf:RDF></x:xmpmeta>`)
	offsets = append(offsets, output.Len())
	if _, err := fmt.Fprintf(&output, "6 0 obj\n<< /Type /Metadata /Subtype /XML /Length %d >>\nstream\n", len(xmp)); err != nil {
		t.Fatal(err)
	}
	if _, err := output.Write(xmp); err != nil {
		t.Fatal(err)
	}
	output.WriteString("\nendstream\nendobj\n")

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
		"trailer\n<< /Size %d /Root 1 0 R /Info 5 0 R >>\nstartxref\n%d\n%%%%EOF\n",
		len(offsets),
		xrefOffset,
	); err != nil {
		t.Fatal(err)
	}
	return output.Bytes()
}
