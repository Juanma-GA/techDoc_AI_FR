package pdf

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"testing"

	"github.com/pdfcpu/pdfcpu/pkg/api"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu/model"

	"pdf-toolkit/services"
)

func TestEditMetadataRoundTripPreservesPagesAnnotationsAndCustomProperties(t *testing.T) {
	tempDir := t.TempDir()
	input := filepath.Join(tempDir, "source.pdf")
	if err := os.WriteFile(input, testPDFWithSensitiveMetadataAndAnnotation(t), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := api.AddPropertiesFile(input, "", map[string]string{"CustomProperty": "keep this"}, nil); err != nil {
		t.Fatal(err)
	}
	source, err := os.ReadFile(input)
	if err != nil {
		t.Fatal(err)
	}
	metadata := services.PDFMetadata{
		Title:    "Révision (2) \\ 東京",
		Author:   "Équipe de rédaction",
		Subject:  "Sujet & <exemple>",
		Keywords: "a, b; mots-clés",
	}
	output := filepath.Join(tempDir, "metadata.pdf")
	if err := NewPDFCPU().EditMetadata(context.Background(), input, output, metadata); err != nil {
		t.Fatal(err)
	}
	assertMetadata(t, output, metadata)
	document := readMetadataContext(t, output)
	info, err := document.DereferenceDict(*document.Info)
	if err != nil {
		t.Fatal(err)
	}
	if custom, err := document.DereferenceText(info["CustomProperty"]); err != nil || custom != "keep this" {
		t.Fatalf("custom property = %q, err = %v", custom, err)
	}
	count, _, err := pdfcpu.ListAnnotations(document.PageAnnots)
	if err != nil || count != 1 || document.PageCount != 1 {
		t.Fatalf("annotations = %d, pages = %d, err = %v", count, document.PageCount, err)
	}
	catalog, err := document.Catalog()
	if err != nil {
		t.Fatal(err)
	}
	if _, exists := catalog["Metadata"]; exists {
		t.Fatal("stale catalog XMP was preserved")
	}
	currentSource, err := os.ReadFile(input)
	if err != nil || string(currentSource) != string(source) {
		t.Fatal("source file was changed")
	}

	cleared := filepath.Join(tempDir, "cleared.pdf")
	if err := NewPDFCPU().EditMetadata(context.Background(), output, cleared, services.PDFMetadata{}); err != nil {
		t.Fatal(err)
	}
	assertMetadata(t, cleared, services.PDFMetadata{})
}

func TestEditMetadataAddsPropertiesWithoutExistingInfo(t *testing.T) {
	tempDir := t.TempDir()
	input := filepath.Join(tempDir, "source.pdf")
	output := filepath.Join(tempDir, "metadata.pdf")
	if err := os.WriteFile(input, testPDF(t, 2), 0o600); err != nil {
		t.Fatal(err)
	}
	metadata := services.PDFMetadata{Title: "New title"}
	if err := NewPDFCPU().EditMetadata(context.Background(), input, output, metadata); err != nil {
		t.Fatal(err)
	}
	assertMetadata(t, output, metadata)
	assertPageCount(t, NewPDFCPU(), output, 2)
	err := NewPDFCPU().EditMetadata(context.Background(), input, output, metadata)
	if !errors.Is(err, services.ErrOutputWrite) {
		t.Fatalf("existing output error = %v, want ErrOutputWrite", err)
	}
}

func readMetadataContext(t *testing.T, path string) *model.Context {
	t.Helper()
	file, err := os.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	document, readErr := api.ReadValidateAndOptimize(file, model.NewDefaultConfiguration())
	if err := errors.Join(readErr, file.Close()); err != nil {
		t.Fatal(err)
	}
	return document
}

func assertMetadata(t *testing.T, path string, want services.PDFMetadata) {
	t.Helper()
	document := readMetadataContext(t, path)
	info, err := document.DereferenceDict(*document.Info)
	if err != nil {
		t.Fatal(err)
	}
	for key, value := range map[string]string{
		"Title": want.Title, "Author": want.Author, "Subject": want.Subject, "Keywords": want.Keywords,
	} {
		object, exists := info[key]
		if value == "" {
			if exists {
				t.Errorf("empty %s property is still present", key)
			}
			continue
		}
		got, err := document.DereferenceText(object)
		if err != nil || got != value {
			t.Errorf("%s = %q, want %q, err = %v", key, got, value, err)
		}
	}
}
